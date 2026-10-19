#!/usr/bin/env python3
"""Measure a linear gradient fill: angle and color stops.

Usage:
  python gradient_fit.py IMG --box X Y W H [--radius 12] [--dpr 2] [--mask X Y W H ...]
  python gradient_fit.py IMG --spec design-spec.json [--ids promo,fab] [--out gradients.json]

Model: CSS linear-gradient(θ). For an angle θ each pixel gets a position along the gradient
line, t = ((x − cx)·sin θ − (y − cy)·cos θ) / L + 0.5 with L = |w·sin θ| + |h·cos θ|, so the
box corners sit at t = 0 and t = 1 exactly as in CSS. The color is piecewise linear in t
(2–4 stops, interior stop positions searched). θ starts from the direction of steepest color
change (a plane fitted per channel) and is refined by a bounded 1-D search. Interpolation is
in sRGB, like browsers. Content inside the box (text, icons, descendants: --mask or the spec) and
a 2 px band along the (rounded) edge plus the border are ignored; pixels the model still cannot
explain (decorations missing from the spec) are trimmed as outliers and the fit is repeated.

Output: angle in (0, 180] (a gradient at θ + 180° is the same gradient with the stops
reversed; 180° = top to bottom), stops [{t, rgb, hex}], `css`, Qt hints (`qt.orientation` for 0°/90°/180°, else
ShapePath LinearGradient x1/y1/x2/y2 in item px), `residual` (RMS in 8-bit levels) against
`flatResidual` (a solid fill) and `isGradient`. Exit codes: 0 ok, 2 error.
"""
from __future__ import annotations

import argparse
import contextlib
import functools
import itertools
import json
import math
import sys
from pathlib import Path

import cv2
import numpy as np
from scipy.optimize import minimize_scalar

try:  # small matrices: BLAS threads only add overhead
    from threadpoolctl import threadpool_limits  # (7× slower when the cores are busy)
except ImportError:  # pragma: no cover
    threadpool_limits = None


def _single_threaded(fn):
    @functools.wraps(fn)
    def run(*args, **kwargs):
        with threadpool_limits(1) if threadpool_limits else contextlib.nullcontext():
            return fn(*args, **kwargs)
    return run


WORK_PX = 160          # longest side of the working grid (gradients are smooth)
EDGE = 2.0             # design px along the outline that are skipped (anti-aliasing, borders)
MIN_PX = 40
MIN_CHANGE = 3.0       # ΔE between the end colors below which the fill is solid


def load_rgb(path: Path) -> np.ndarray:
    img = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if img is None:
        raise SystemExit(f"[error] cannot read {path}")
    return cv2.cvtColor(img, cv2.COLOR_BGR2RGB).astype(np.float32)


def delta_e(rgb_a, rgb_b) -> float:
    """CIEDE2000 between two sRGB colors (0–255)."""
    from skimage.color import deltaE_ciede2000, rgb2lab
    a = rgb2lab(np.asarray(rgb_a, float).reshape(1, 1, 3) / 255.0)
    b = rgb2lab(np.asarray(rgb_b, float).reshape(1, 1, 3) / 255.0)
    return float(deltaE_ciede2000(a, b)[0, 0])


def _hex(rgb) -> str:
    return "#{:02X}{:02X}{:02X}".format(*(int(round(min(255, max(0, v)))) for v in rgb))


def _t(px, py, w, h, theta):
    s, c = math.sin(math.radians(theta)), math.cos(math.radians(theta))
    L = abs(w * s) + abs(h * c)
    return (px * s - py * c) / max(L, 1e-6) + 0.5


def _hat(t, knots):
    """Piecewise-linear basis (one column per knot), constant outside [knots[0], knots[-1]]."""
    t = np.clip(t, knots[0], knots[-1])
    B = np.zeros((len(t), len(knots)))
    for k in range(len(knots) - 1):
        a, b = knots[k], knots[k + 1]
        sel = (t >= a) & (t <= b) if k == len(knots) - 2 else (t >= a) & (t < b)
        u = (t[sel] - a) / max(b - a, 1e-9)
        B[sel, k] += 1 - u
        B[sel, k + 1] += u
    return B


def _fit_knots(t, C, knots):
    B = _hat(t, knots)
    coef, *_ = np.linalg.lstsq(B, C, rcond=None)
    res = C - B @ coef
    return float(np.sqrt((res ** 2).mean())), coef


MIN_GAP = 0.1          # interior stops at least this far apart (in t)
MAX_SLOPE = 2.0        # ΔE per design px along the gradient line: steeper is a shape edge (a knob,
                       # a circle, an image), not a gradient
TAU = 6.0              # a pixel within this many levels (max channel) of the model is an inlier
ACCEPT_RATIO = 0.35    # accept(): residual / solid-fill residual below this …
ACCEPT_RESIDUAL = 4.0  # … residual below this many levels …
ACCEPT_OUTLIERS = 0.45  # … and at most this share of the pixels unexplained (a switch knob: 40 %)
SEGMENT_SUPPORT = 0.6  # every segment between stops must fit this share of its pixels (a step edge
                       # smoothed into a short ramp does not)
_LINE = [1.0]          # gradient-line length of the current fit (design px), set by _fit_once


def _plausible(knots, coef) -> bool:
    for k in range(len(knots) - 1):
        if delta_e(coef[k], coef[k + 1]) > MAX_SLOPE * max(knots[k + 1] - knots[k], 1e-6) * _LINE[0]:
            return False
    return True


def _best_stops(t, C, n, coarse=False):
    """Best piecewise-linear fit with n stops (ends at 0 and 1, interior positions searched)."""
    if n == 2:
        rms, coef = _fit_knots(t, C, [0.0, 1.0])
        return rms, [0.0, 1.0], coef
    grid = np.linspace(0.1, 0.9, 9 if coarse else 17)
    best = None
    for inner in itertools.combinations(grid, n - 2):
        knots = [0.0, *inner, 1.0]
        if min(np.diff(knots)) < MIN_GAP - 1e-9:
            continue
        rms, coef = _fit_knots(t, C, knots)
        if (best is None or rms < best[0]) and _plausible(knots, coef):
            best = (rms, knots, coef)
    if best is None or coarse:
        return best
    # local refinement of the interior positions (±half a grid step)
    rms, knots, coef = best
    for _ in range(2):
        for i in range(1, n - 1):
            for d in (-0.025, 0.025):
                k2 = list(knots)
                k2[i] = min(max(k2[i] + d, k2[i - 1] + MIN_GAP), k2[i + 1] - MIN_GAP)
                r2, c2 = _fit_knots(t, C, k2)
                if r2 < rms and _plausible(k2, c2):
                    rms, knots, coef = r2, k2, c2
    return rms, knots, coef


def sample(img, dpr, bbox, mask_boxes=(), radius=0.0, border=0.0):
    """Colors and design-px coordinates (relative to the box center) of the usable pixels."""
    H, W = img.shape[:2]
    x, y, w, h = bbox
    X0, Y0 = max(0, int(round(x * dpr))), max(0, int(round(y * dpr)))
    X1, Y1 = min(W, int(round((x + w) * dpr))), min(H, int(round((y + h) * dpr)))
    if X1 - X0 < 4 or Y1 - Y0 < 4:
        return None
    s = min(1.0, WORK_PX / max(w, h))                     # work px per design px
    cw, ch = max(4, int(round(w * s))), max(4, int(round(h * s)))
    crop = cv2.resize(img[Y0:Y1, X0:X1], (cw, ch), interpolation=cv2.INTER_AREA)
    xs = (np.arange(cw) + 0.5) / cw * w - w / 2
    ys = (np.arange(ch) + 0.5) / ch * h - h / 2
    gx, gy = np.meshgrid(xs, ys)
    # inside the rounded rectangle shrunk by EDGE
    inset = EDGE + (border or 0.0)
    r = max(0.0, min(radius or 0.0, w / 2, h / 2) - inset)
    hw, hh = w / 2 - inset, h / 2 - inset
    qx, qy = np.maximum(np.abs(gx) - (hw - r), 0), np.maximum(np.abs(gy) - (hh - r), 0)
    valid = (np.abs(gx) <= hw) & (np.abs(gy) <= hh) & (qx ** 2 + qy ** 2 <= r ** 2)
    for mx, my, mw, mh in mask_boxes:
        mx, my = mx - x - w / 2, my - y - h / 2
        valid &= ~((gx >= mx - EDGE) & (gx < mx + mw + EDGE) & (gy >= my - EDGE) & (gy < my + mh + EDGE))
    if valid.sum() < MIN_PX:
        return None
    return crop[valid].astype(np.float64), gx[valid], gy[valid]


def _fit_once(C, px, py, w, h, max_stops):
    _LINE[0] = max(w, h)
    # 1. direction of steepest change: plane per channel, top right-singular vector
    A = np.stack([np.ones_like(px), px, py], axis=1)
    coef, *_ = np.linalg.lstsq(A, C, rcond=None)
    G = coef[1:].T                                        # (3, 2): d color / d(x, y)
    _, _, vt = np.linalg.svd(G)
    dx, dy = vt[0]
    theta0 = math.degrees(math.atan2(dx, -dy)) % 180.0     # CSS: 0° = to top, 90° = to right

    # 2. refine θ for the 2-stop model (±25°, wrapping)
    def cost(th):
        return _fit_knots(_t(px, py, w, h, th % 180.0), C, [0.0, 1.0])[0]
    res = minimize_scalar(cost, bounds=(theta0 - 25, theta0 + 25), method="bounded", options={"xatol": 0.05})
    theta = float(res.x) % 180.0
    if max_stops > 2:
        # a multi-stop gradient can fool the plane's direction: scan all angles with 3 stops
        sub = np.linspace(0, len(C) - 1, min(len(C), 2500)).astype(int)
        cs, pxs, pys = C[sub], px[sub], py[sub]

        def cost3(th):
            r = _best_stops(_t(pxs, pys, w, h, th % 180.0), cs, 3, coarse=True)
            return r[0] if r else 1e9
        scan = min(np.arange(0.0, 180.0, 5.0), key=cost3)
        if cost3(scan) < 0.8 * cost3(theta):
            r = minimize_scalar(cost3, bounds=(scan - 5, scan + 5), method="bounded", options={"xatol": 0.05})
            theta = float(r.x) % 180.0

    # 3. number of stops: add one while it removes ≥25 % of the residual and ≥0.5 levels
    _LINE[0] = abs(w * math.sin(math.radians(theta))) + abs(h * math.cos(math.radians(theta)))
    t = _t(px, py, w, h, theta)
    best = _best_stops(t, C, 2)
    for n in range(3, max_stops + 1):
        cand = _best_stops(t, C, n)
        if cand is not None and cand[0] < 0.75 * best[0] and best[0] - cand[0] >= 0.5:
            best = cand
        else:
            break
    rms, knots, cols = best
    if len(knots) > 2:                                    # re-refine θ with the chosen stops
        def cost_n(th):
            return _fit_knots(_t(px, py, w, h, th % 180.0), C, knots)[0]
        r2 = minimize_scalar(cost_n, bounds=(theta - 5, theta + 5), method="bounded", options={"xatol": 0.05})
        if r2.fun < rms:
            theta = float(r2.x) % 180.0
            rms, cols = _fit_knots(_t(px, py, w, h, theta), C, knots)
    return theta, rms, knots, cols


def _robust(C, px, py, w, h, max_stops):
    """(inliers, θ, knots, colors, rms): consensus fit — refit on the pixels within TAU of the
    model until stable, from three starts (all pixels, each half along the gradient), and keep
    the start that explains the most pixels."""
    theta0 = _fit_once(C, px, py, w, h, max_stops)[0]
    t0 = _t(px, py, w, h, theta0)
    best = None
    for start in (np.ones(len(C), bool), t0 <= np.median(t0), t0 >= np.median(t0)):
        keep = start
        for _ in range(6):
            theta, rms, knots, cols = _fit_once(C[keep], px[keep], py[keep], w, h, max_stops)
            err = np.abs(C - _hat(_t(px, py, w, h, theta), knots) @ cols).max(axis=1)
            new = err <= TAU
            if new.sum() < MIN_PX or (new == keep).all():
                break
            keep = new
        inl = err <= TAU
        if best is None or inl.sum() > best[0].sum():
            best = (inl, theta, knots, cols, rms)
    keep = best[0]
    if keep.sum() < MIN_PX:                      # nothing fits well (noise, texture): use everything
        keep = np.ones(len(C), bool)
    theta, rms, knots, cols = _fit_once(C[keep], px[keep], py[keep], w, h, max_stops)
    t = _t(px, py, w, h, theta)
    err = np.abs(C - _hat(t, knots) @ cols).max(axis=1)
    supported = True
    for k in range(len(knots) - 1):
        seg = (t >= knots[k]) & (t <= knots[k + 1])
        if seg.sum() >= 20 and float((err[seg] <= TAU).mean()) < SEGMENT_SUPPORT:
            supported = False
    return keep, theta, knots, cols, rms, supported


@_single_threaded
def fit_region(img, dpr, bbox, mask_boxes=(), radius=0.0, max_stops=4, border=0.0) -> dict | None:
    got = sample(img, dpr, bbox, mask_boxes, radius, border)
    if got is None:
        return None
    C, px, py = got
    w, h = bbox[2], bbox[3]
    flat = float(np.sqrt(((C - C.mean(axis=0)) ** 2).mean()))
    # robust: consensus fits (undeclared content such as a knob or decorative circles is left
    # out), with 2 stops and with up to max_stops; more stops win only when they explain
    # clearly more of the box (a real 3-stop gradient: ≥ 85 % of it) and every segment is
    # supported by its pixels (no shape edge smoothed into a short ramp).
    best = _robust(C, px, py, w, h, 2)
    if max_stops > 2:
        multi = _robust(C, px, py, w, h, max_stops)
        if len(multi[2]) > 2 and multi[5] and multi[0].mean() >= max(0.85, best[0].mean() + 0.08):
            best = multi
    keep, theta, knots, cols, rms, _ = best
    trimmed = 1.0 - float(keep.mean())
    cols = np.clip(cols, 0, 255)
    ang = round(theta, 1) % 180.0
    if ang < 0.5:                                         # report (0°, 180°]: "to bottom" is 180°, not 0°
        ang, knots, cols = 180.0, [1.0 - k for k in knots[::-1]], cols[::-1]
    stops = [{"t": round(float(k), 3), "rgb": [int(round(v)) for v in c], "hex": _hex(c)} for k, c in zip(knots, cols, strict=True)]
    is_grad = delta_e(cols[0], cols[-1]) >= MIN_CHANGE or any(delta_e(cols[0], c) >= MIN_CHANGE for c in cols[1:-1])

    css = "linear-gradient({:g}deg, {})".format(ang, ", ".join(f"{s['hex']} {s['t'] * 100:g}%" for s in stops))
    s_, c_ = math.sin(math.radians(ang)), math.cos(math.radians(ang))
    L = abs(w * s_) + abs(h * c_)
    qt = {"x1": round(w / 2 - s_ * L / 2, 2), "y1": round(h / 2 + c_ * L / 2, 2),
          "x2": round(w / 2 + s_ * L / 2, 2), "y2": round(h / 2 - c_ * L / 2, 2)}
    if abs(ang) < 1.0 or abs(ang - 180) < 1.0:
        qt["orientation"] = "Gradient.Vertical"          # 0° runs bottom→top: reverse the stops
        qt["reverseStops"] = abs(ang) < 1.0
    elif abs(ang - 90) < 1.0:
        qt["orientation"] = "Gradient.Horizontal"
    return {"angle": ang, "stops": stops, "css": css, "qt": qt, "residual": round(rms, 2),
            "flatResidual": round(flat, 2), "isGradient": bool(is_grad), "pixels": int(keep.sum()),
            "outliers": round(trimmed, 3)}


def accept(fit: dict | None) -> bool:
    """Is this fill really a gradient (and explained well enough to write into the spec)?"""
    return bool(fit and fit["isGradient"] and fit["residual"] <= ACCEPT_RATIO * max(fit["flatResidual"], 1e-6)
                and fit["residual"] <= ACCEPT_RESIDUAL and fit["outliers"] <= ACCEPT_OUTLIERS)


def jobs_from_spec(spec: dict, ids=None) -> list[dict]:
    """Nodes whose fill may be a gradient; their text, icons and child boxes are masked."""
    nodes = spec.get("nodes", [])
    kids: dict = {}
    for n in nodes:
        kids.setdefault(n.get("parent"), []).append(n)

    def descendants(nid):
        out, todo = [], list(kids.get(nid, []))
        while todo:
            c = todo.pop()
            out.append(c["bbox"])
            todo.extend(kids.get(c["id"], []))
        return out
    flat = [t["bbox"] for t in spec.get("text", [])] + [i["bbox"] for i in spec.get("icons", [])]
    out = []
    for n in nodes:
        st = n.get("style") or {}
        if ids and n["id"] not in ids:
            continue
        if not ids and not (st.get("fillImage") or "").startswith("linear-gradient") and not st.get("gradient"):
            continue
        border = st.get("border")
        bw = max([b.get("width", 0) or 0 for b in border] if isinstance(border, list) else [(border or {}).get("width", 0) or 0])
        rad = st.get("radius", 0) or 0
        rad = max(rad) if isinstance(rad, list) and rad else rad           # per-corner radii: the largest
        out.append({"id": n["id"], "bbox": n["bbox"], "radius": rad, "border": bw,
                    "mask": flat + descendants(n["id"])})
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("image", type=Path)
    ap.add_argument("--box", type=float, nargs=4, metavar=("X", "Y", "W", "H"))
    ap.add_argument("--radius", type=float, default=0.0)
    ap.add_argument("--border", type=float, default=0.0, help="border width to skip along the edge (design px)")
    ap.add_argument("--mask", type=float, nargs=4, action="append", default=[], metavar=("X", "Y", "W", "H"))
    ap.add_argument("--spec", type=Path)
    ap.add_argument("--ids", default="", help="with --spec: fit these nodes (default: nodes with a linear-gradient fill)")
    ap.add_argument("--stops", type=int, default=4, help="most color stops to try (2–6)")
    ap.add_argument("--dpr", type=float, default=None)
    ap.add_argument("--out", type=Path)
    args = ap.parse_args(argv)
    if not args.image.exists():
        print(f"[error] no such image: {args.image}", file=sys.stderr)
        return 2
    img = load_rgb(args.image)
    spec = json.loads(args.spec.read_text()) if args.spec else {}
    dpr = args.dpr or float(spec.get("meta", {}).get("dpr", 1))
    if args.box:
        todo = [{"id": "box", "bbox": list(args.box), "radius": args.radius, "mask": args.mask, "border": args.border}]
    else:
        want = {s.strip() for s in args.ids.split(",") if s.strip()}
        todo = jobs_from_spec(spec, want or None)
    if not todo:
        print("[error] nothing to fit: pass --box, or --spec with gradient nodes / --ids", file=sys.stderr)
        return 2
    out = []
    for j in todo:
        r = fit_region(img, dpr, j["bbox"], j["mask"], j["radius"], max(2, min(6, args.stops)), j.get("border", 0))
        out.append({"id": j["id"], **(r or {"error": "not enough unmasked pixels"})})
        if r:
            kind = "gradient" if accept(r) else ("unsure  " if r["isGradient"] else "solid   ")
            print(f"{j['id']:18s} {kind} {r['css']}   residual {r['residual']} (solid: {r['flatResidual']})")
    if args.out:
        args.out.write_text(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
