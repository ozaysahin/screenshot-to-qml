#!/usr/bin/env python3
"""Measure the drop shadow around a surface: offset, blur, spread and color.

Usage:
  python shadow_fit.py IMG --box X Y W H [--radius 12] [--dpr 2]
  python shadow_fit.py IMG --spec design-spec.json [--ids card1,card2] [--dpr 2] [--out shadows.json]

Model (CSS box-shadow, one layer): the surface's rectangle, moved by (x, y), grown by
`spread` and blurred with a Gaussian of σ = blur / 2, is added to a smooth background:

    pixel = background(x, y) + mask(x, y) · u,     u = alpha · (color − background)

Only the ring of pixels around the box is used (the box hides its own shadow). For a given
(x, y, blur, spread) the background (a quadratic surface per painted surface underneath, a
constant where the ring sees it on fewer than three sides) and u are a linear
least-squares solve, so only those four numbers are searched (bounded Nelder–Mead from
several starts, with a weak prior towards x = 0 and spread = 0). Rectangles blur in closed
form (erf profiles) and the ring skips their rounded corners; circles and pills are
rasterised instead.

With --spec every painted node is fitted as one scene: other surfaces, text and icons are
masked out; equal-sized siblings (a card grid) are first fitted as casters of one shared
shadow; then two back-fitting rounds subtract each neighbour's fitted shadow from the ring
before refitting, so a card's shadow does not leak into the next card's estimate.

Output per surface: x, y, blur, spread (design px), color (hex), alpha, u (the premultiplied
color change), a CSS `box-shadow` string, `residual` / `rawResidual` (RMS in 8-bit levels on
the ring with and without the shadow term), `atBound` (a parameter ended on its search limit:
|x| 16, |y| 32, blur 96, spread −24…16 — the fit is unreliable) and `hasShadow` (a visible,
reliable shadow: ≥ 2 levels deep, the ring's RMS drops by ≥ 20 % with it, and it is not a
crisp line far from the box, an opaque edge, or a light halo on a light background). On one background only u is
observable: the reported color is the most saturated one consistent with it (near-black for
ordinary shadows), so alpha and color trade off but the rendered look is the same. Multi-layer
CSS shadows come back as one equivalent layer. Map to Qt with references/effects.md
(RectangularShadow). Exit codes: 0 ok, 2 error.
"""
from __future__ import annotations

import argparse
import contextlib
import functools
import json
import sys
from pathlib import Path

import cv2
import numpy as np
from scipy.optimize import minimize
from scipy.special import erf

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


RING = 64             # design px around the box that are fitted
MIN_RING_PX = 150     # need at least this many usable pixels
SEARCH_PX = 12000     # pixels sampled during the search (all are used for the final solve)
EDGE = 0.6            # design px next to a box edge that are skipped (anti-aliasing)
PRIOR = 0.001         # weight of the x = 0, spread = 0 prior (per design px², in levels²)
BG_ORDER = 2          # background under the ring: 1 = plane, 2 = quadratic (per surface)
LO = np.array([-16.0, -32.0, 0.0, -24.0])     # x, y, blur, spread
HI = np.array([16.0, 32.0, 96.0, 16.0])
STARTS = ((0, 2, 4, 0), (0, 8, 20, 0), (0, 20, 48, 0), (0, -8, 24, 0), (0, 0, 32, 0))


def load_rgb(path: Path) -> np.ndarray:
    img = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if img is None:
        raise SystemExit(f"[error] cannot read {path}")
    return cv2.cvtColor(img, cv2.COLOR_BGR2RGB).astype(np.float32)


def rounded_rect(shape, x, y, w, h, r) -> np.ndarray:
    """Anti-aliased rounded-rectangle coverage in pixel units (float32, supersampled ×4)."""
    ss = 4
    m = np.zeros((shape[0] * ss, shape[1] * ss), np.uint8)
    x0, y0, x1, y1 = (int(round(v * ss)) for v in (x, y, x + w, y + h))
    r = int(max(0, min(r * ss, (x1 - x0) / 2, (y1 - y0) / 2)))
    if x1 > x0 and y1 > y0:
        cv2.rectangle(m, (x0 + r, y0), (x1 - r - 1, y1 - 1), 255, -1)
        cv2.rectangle(m, (x0, y0 + r), (x1 - 1, y1 - r - 1), 255, -1)
        for cx, cy in ((x0 + r, y0 + r), (x1 - r - 1, y0 + r), (x0 + r, y1 - r - 1), (x1 - r - 1, y1 - r - 1)):
            cv2.circle(m, (cx, cy), r, 255, -1)
    return cv2.resize(m, (shape[1], shape[0]), interpolation=cv2.INTER_AREA).astype(np.float32) / 255.0


def _profile(c: np.ndarray, a: float, b: float, sig: float) -> np.ndarray:
    k = 1.0 / (np.sqrt(2.0) * sig)
    return 0.5 * (erf((c - a) * k) - erf((c - b) * k))


def _inside(xs, ys, box, grow=0.0):
    x, y, w, h = box
    return ((xs[None, :] >= x - grow) & (xs[None, :] < x + w + grow)
            & (ys[:, None] >= y - grow) & (ys[:, None] < y + h + grow))


def _is_round(w, h, r) -> bool:
    return r >= 0.35 * min(w, h)


def corner_radius(radius) -> float:
    """A spec radius as one number: per-corner lists [tl, tr, br, bl] use their largest corner."""
    if isinstance(radius, (list, tuple)):
        return float(max(radius)) if radius else 0.0
    return float(radius or 0.0)


class _Ring:
    """Pixels around one box, resampled to ≈1 px per design px, with background segments."""

    def __init__(self, img, dpr, bbox, radius, exclude, casters, surfaces, ring):
        H, W = img.shape[:2]
        x, y, w, h = bbox
        self.ok = False
        X0, Y0 = max(0, int((x - ring) * dpr)), max(0, int((y - ring) * dpr))
        X1, Y1 = min(W, int(np.ceil((x + w + ring) * dpr))), min(H, int(np.ceil((y + h + ring) * dpr)))
        if X1 - X0 < 4 or Y1 - Y0 < 4:
            return
        cw, ch = max(4, int(round((X1 - X0) / dpr))), max(4, int(round((Y1 - Y0) / dpr)))
        crop = cv2.resize(img[Y0:Y1, X0:X1], (cw, ch), interpolation=cv2.INTER_AREA)
        self.sx, self.sy = (X1 - X0) / dpr / cw, (Y1 - Y0) / dpr / ch
        xs = X0 / dpr + (np.arange(cw) + 0.5) * self.sx
        ys = Y0 / dpr + (np.arange(ch) + 0.5) * self.sy
        self.xs, self.ys, self.shape = xs, ys, (ch, cw)

        valid = ~_inside(xs, ys, bbox, EDGE)
        for ex in exclude:
            valid &= ~_inside(xs, ys, ex, 1.0)
        for cb, _ in casters:
            valid &= ~_inside(xs, ys, cb, EDGE)
        for sb in surfaces:                              # ancestor edges are not background
            valid &= ~(_inside(xs, ys, sb, 1.5) & ~_inside(xs, ys, sb, -1.5))
        r = min(corner_radius(radius), w / 2, h / 2)
        if r >= 2:                                       # erf model: skip the rounded corners
            for (bx, by, bw, bh), br in [(bbox, r)] + list(casters):
                if _is_round(bw, bh, min(br or 0, bw / 2, bh / 2)):
                    continue
                cz = min(br or 0, bw / 2, bh / 2) + 2
                nx = (xs < bx + cz) | (xs > bx + bw - cz)
                ny = (ys < by + cz) | (ys > by + bh - cz)
                valid &= ~(ny[:, None] & nx[None, :])
        if valid.sum() < MIN_RING_PX:
            return

        seg = np.full((ch, cw), len(surfaces), np.int32)
        for i in range(len(surfaces) - 1, -1, -1):
            seg[_inside(xs, ys, surfaces[i])] = i
        ii, jj = np.nonzero(valid)
        segv = seg[ii, jj]
        parts = []
        for s in np.unique(segv):
            sel = np.nonzero(segv == s)[0]
            if len(sel) < 60:
                continue
            gx, gy = xs[jj[sel]], ys[ii[sel]]
            sides = ((gx < x).any(), (gx > x + w).any(), (gy < y).any(), (gy > y + h).any())
            parts.append((sel, sum(sides) >= 3))
        if not parts:
            return
        order = np.concatenate([p[0] for p in parts])
        self.ii, self.jj = ii[order], jj[order]
        self.groups, start = [], 0
        for sel, plane in parts:
            self.groups.append((np.arange(start, start + len(sel)), plane))
            start += len(sel)
        self.D = crop[self.ii, self.jj].astype(np.float64)
        self.GX = (xs[self.jj] - (x + w / 2)) / 100.0
        self.GY = (ys[self.ii] - (y + h / 2)) / 100.0
        self.n = len(self.D)
        self.ok = True

    def mask(self, shapes, p, idx=None, clip_inside=False) -> np.ndarray:
        """Shadow coverage (0..1) at ring pixels `idx` for shapes [(bbox, radius)] with params p."""
        px, py, blur, spread = (float(v) for v in p)
        sig = float(np.sqrt((max(0.0, blur) / 2) ** 2 + 0.3 ** 2))
        ii = self.ii if idx is None else self.ii[idx]
        jj = self.jj if idx is None else self.jj[idx]
        m = np.zeros(len(ii))
        for (bx, by, bw, bh), br in shapes:
            gx0, gy0 = bx + px - spread, by + py - spread
            gw, gh = bw + 2 * spread, bh + 2 * spread
            if gw <= 0 or gh <= 0:
                continue
            br = min(corner_radius(br), bw / 2, bh / 2)
            if _is_round(bw, bh, br):
                sx, sy = self.sx, self.sy
                rr = rounded_rect(self.shape, (gx0 - self.xs[0]) / sx + 0.5, (gy0 - self.ys[0]) / sy + 0.5,
                                  gw / sx, gh / sy, (br + max(0.0, spread)) / sx)
                if blur > 0.2:
                    rr = cv2.GaussianBlur(rr, (0, 0), max(0.3, sig / sx))
                v = rr[ii, jj]
            else:
                v = _profile(self.ys[ii], gy0, gy0 + gh, sig) * _profile(self.xs[jj], gx0, gx0 + gw, sig)
            if clip_inside:                               # an outer shadow is clipped by its own box
                v = v * ~((self.xs[jj] >= bx) & (self.xs[jj] < bx + bw) & (self.ys[ii] >= by) & (self.ys[ii] < by + bh))
            m += v
        return np.minimum(m, 1.0)

    def subsets(self, idx):
        """Group index arrays restricted to `idx` (positions into idx)."""
        if idx is None:
            return [(g, plane) for g, plane in self.groups]
        pos = np.full(self.n, -1)
        pos[idx] = np.arange(len(idx))
        out = []
        for g, plane in self.groups:
            q = pos[g]
            q = q[q >= 0]
            if len(q) >= 10:
                out.append((q, plane))
        return out


def _bg_cols(GX, GY, q, plane):
    if not plane:
        return [np.ones(len(q))]
    cols = [np.ones(len(q)), GX[q], GY[q]]
    if BG_ORDER >= 2:
        cols += [GX[q] ** 2, GX[q] * GY[q], GY[q] ** 2]
    return cols


def _solve(D, GX, GY, mv, subsets, with_shadow=True):
    sse, parts = 0.0, []
    for q, plane in subsets:
        cols = _bg_cols(GX, GY, q, plane) + ([mv[q]] if with_shadow else [])
        A = np.stack(cols, axis=1)
        coef, *_ = np.linalg.lstsq(A, D[q], rcond=None)
        res = D[q] - A @ coef
        sse += float((res ** 2).sum())
        parts.append((q, coef, res, plane))
    return sse, parts


@_single_threaded
def fit_node(img: np.ndarray, dpr: float, bbox, radius: float = 0.0, exclude=(), casters=(),
             surfaces=(), known=(), ring: float = RING, starts=STARTS) -> dict | None:
    """Fit one shadow layer around `bbox` (design px).

    exclude:  boxes painted above the shadow (other surfaces, text, icons) — masked out
    casters:  [(bbox, radius)] of other surfaces assumed to cast the same shadow
    surfaces: bboxes of painted ancestors, innermost first — the backgrounds under the ring
    known:    fitted shadows of neighbours ({bbox, radius, x, y, blur, spread, u}) to subtract
    """
    R = _Ring(img, dpr, bbox, radius, exclude, casters, surfaces, ring)
    if not R.ok:
        return None
    D = R.D.copy()
    for k in known:
        mk = R.mask([(k["bbox"], k.get("radius", 0))], (k["x"], k["y"], k["blur"], k["spread"]), clip_inside=True)
        D -= mk[:, None] * np.asarray(k["u"], float)[None, :]
    r = min(corner_radius(radius), bbox[2] / 2, bbox[3] / 2)
    shapes = [(tuple(bbox), r)] + [(tuple(cb), cr) for cb, cr in casters]
    lo, hi = LO.copy(), HI.copy()
    lo[3] = max(lo[3], -min(bbox[2], bbox[3]) / 2 + 1)

    rng = np.random.default_rng(0)
    search = np.sort(rng.choice(R.n, SEARCH_PX, replace=False)) if R.n > SEARCH_PX else np.arange(R.n)

    def prepare(idx):
        """Per background segment: the fixed parts of the normal equations (only the shadow
        column changes during the search)."""
        Dq, GXq, GYq = D[idx], R.GX[idx], R.GY[idx]
        pre = []
        for q, plane in R.subsets(idx):
            B = np.ascontiguousarray(np.stack(_bg_cols(GXq, GYq, q, plane), axis=0))   # (k, n)
            Dg = np.ascontiguousarray(Dq[q])
            sl = slice(int(q[0]), int(q[-1]) + 1) if q[-1] - q[0] + 1 == len(q) else q      # groups are contiguous
            pre.append((sl, B, B @ B.T, B @ Dg, Dg, float((Dg ** 2).sum())))
        return pre

    def objective(p, idx, pre):
        q = np.clip(p, lo, hi)
        pen = float(((p - q) ** 2).sum()) * 50.0 + PRIOR * (q[0] ** 2 + q[3] ** 2)
        mv = R.mask(shapes, q, idx)
        sse = 0.0
        for qi, B, G, E, Dg, dd in pre:
            m = mv[qi]
            k = G.shape[0]
            N = np.empty((k + 1, k + 1))
            N[:k, :k], N[:k, k] = G, B @ m
            N[k, :k], N[k, k] = N[:k, k], float(m @ m) + 1e-9
            rhs = np.vstack([E, m @ Dg])
            try:
                coef = np.linalg.solve(N + 1e-9 * np.eye(k + 1), rhs)
            except np.linalg.LinAlgError:
                coef = np.linalg.lstsq(N, rhs, rcond=None)[0]
            sse += max(0.0, dd - float((coef * rhs).sum()))
        return sse / len(idx) + pen

    def run(idx, p0s, maxiter, xatol):
        pre = prepare(idx)
        best = None
        for p0 in p0s:
            res = minimize(objective, np.array(p0, float), args=(idx, pre), method="Nelder-Mead",
                           options={"xatol": xatol, "fatol": 1e-5, "maxiter": maxiter})
            if best is None or res.fun < best.fun:
                best = res
        return np.clip(best.x, lo, hi)

    p = run(search, starts, 220, 0.05)
    # trimmed refit on every ring pixel: drop outliers (unmodelled content) once
    everything = np.arange(R.n)
    _, parts = _solve(D, R.GX, R.GY, R.mask(shapes, p), R.subsets(None))
    resid = np.zeros(R.n)
    for q, _, res, _ in parts:
        resid[q] = np.abs(res).max(axis=1)
    cut = max(6.0, 4.0 * 1.4826 * float(np.median(resid)))
    good = everything[resid <= cut]
    if len(good) < MIN_RING_PX:
        good = everything
    refine = good if len(good) <= 2 * SEARCH_PX else np.sort(rng.choice(good, 2 * SEARCH_PX, replace=False))
    p = run(refine, [p], 160, 0.02)

    subs = R.subsets(good)
    Dg, GXg, GYg = D[good], R.GX[good], R.GY[good]
    mv = R.mask(shapes, p, good)
    sse, parts = _solve(Dg, GXg, GYg, mv, subs)
    raw_sse, _ = _solve(Dg, GXg, GYg, mv, subs, with_shadow=False)
    err, raw = sse / len(good) / 3, raw_sse / len(good) / 3

    # u and the background under the shadow, from the segment where the shadow weighs most
    q, coef, _, plane = max(parts, key=lambda pr: float((mv[pr[0]] ** 2).sum()))
    u = coef[-1]
    wts = mv[q] ** 2 + 1e-9
    A_bg = np.stack(_bg_cols(GXg, GYg, q, plane), axis=1)
    bg = (A_bg @ coef[:-1] * wts[:, None]).sum(axis=0) / wts.sum()
    need = np.where(u < 0, -u / np.maximum(bg, 1.0), u / np.maximum(255.0 - bg, 1.0))
    alpha = float(np.clip(need.max(), 0.0, 1.0))
    color = np.clip(bg + u / max(alpha, 1e-3), 0, 255)
    px, py, blur, spread = (float(v) for v in p)
    rgb = tuple(int(round(v)) for v in color)
    out = {"x": round(px, 2), "y": round(py, 2), "blur": round(max(0.0, blur), 2), "spread": round(spread, 2),
           "color": "#{:02X}{:02X}{:02X}".format(*rgb), "alpha": round(alpha, 3), "u": [round(float(v), 2) for v in u],
           "residual": round(float(np.sqrt(err)), 2), "rawResidual": round(float(np.sqrt(raw)), 2),
           "casters": len(casters)}
    out["css"] = (f"{out['x']:g}px {out['y']:g}px {out['blur']:g}px {out['spread']:g}px "
                  f"rgba({rgb[0]}, {rgb[1]}, {rgb[2]}, {alpha:.2f})")
    peak = float(np.abs(u).max()) * float(mv.max()) if len(mv) else 0.0
    # a fit that ends on the search box edge does not describe the data (a neighbour's glow,
    # an undeclared surface): report it, but do not call it a shadow
    out["atBound"] = bool(np.any(np.isclose(p, lo, atol=0.05) & (lo != 0)) or np.any(np.isclose(p, hi, atol=0.05)))
    # what fits but is not a shadow: a crisp far-off or opaque "shadow" is an edge or a line of a
    # neighbour; a shadow lighter than a light background is an anti-aliasing halo
    crisp = blur < 0.75
    implausible = ((crisp and (abs(px) > 4 or abs(py) > 4 or abs(spread) > 4 or alpha > 0.6))
                   or (float(bg.mean()) > 180 and float(u.mean()) > 0))
    out["hasShadow"] = bool(peak >= 2.0 and not out["atBound"] and not implausible
                            and out["residual"] <= 0.8 * out["rawResidual"])
    return out


# ---------------------------------------------------------------- spec helpers

def painted(node: dict) -> bool:
    st = node.get("style") or {}
    fill = st.get("fill") or {}
    border = st.get("border")
    borders = border if isinstance(border, list) else ([border] if border else [])
    visible_border = any(b.get("width", 0) and ((b.get("color") or {}).get("alpha", 1) or 0) > 0.01 for b in borders)
    return bool((fill.get("alpha", 0) or 0) > 0.01 or st.get("fillImage") or st.get("shadow") or visible_border
                or node.get("role") in ("Image", "Avatar"))


def jobs_from_spec(spec: dict, ids=None) -> list[dict]:
    """Per painted node: box, radius, masks, same-size casters and background surfaces."""
    nodes = spec.get("nodes", [])
    by_id = {n["id"]: n for n in nodes}
    flat = [t["bbox"] for t in spec.get("text", [])] + [i["bbox"] for i in spec.get("icons", [])]
    out = []
    for n in nodes:
        if ids and n["id"] not in ids or n.get("role") == "background" or not painted(n):
            continue
        anc, p = [], n.get("parent")
        while p and p in by_id and p not in anc:
            anc.append(p)
            p = by_id[p].get("parent")
        rad = corner_radius((n.get("style") or {}).get("radius", 0))
        others = [o for o in nodes if o is not n and o["id"] not in anc and painted(o)]
        same = [o for o in others if o.get("parent") == n.get("parent")
                and abs(o["bbox"][2] - n["bbox"][2]) <= 1 and abs(o["bbox"][3] - n["bbox"][3]) <= 1
                and corner_radius((o.get("style") or {}).get("radius", 0)) == rad]
        out.append({"id": n["id"], "bbox": n["bbox"], "radius": rad, "ancestors": anc,
                    "exclude": [o["bbox"] for o in others if o not in same] + flat,
                    "casters": [(o["bbox"], rad) for o in same],
                    "surfaces": [by_id[a]["bbox"] for a in anc if painted(by_id[a])]})
    return out


def fit_job(img: np.ndarray, dpr: float, job: dict, known=(), starts=STARTS) -> dict | None:
    """fit_node for a jobs_from_spec entry. With casters (equal-sized siblings), also fit them
    as one shared shadow and keep whichever explains the ring better. `known`: neighbours'
    fitted shadows to subtract (the casters' own entries are skipped in the shared fit)."""
    caster_boxes = [c[0] for c in job["casters"]]
    alone = fit_node(img, dpr, job["bbox"], job["radius"], job["exclude"] + caster_boxes, (), job["surfaces"],
                     known, starts=starts)
    if not job["casters"]:
        return alone
    others = [k for k in known if list(k["bbox"]) not in [list(b) for b in caster_boxes]]
    group = fit_node(img, dpr, job["bbox"], job["radius"], job["exclude"], job["casters"], job["surfaces"],
                     others, starts=starts)
    if group is None:
        return alone
    return group if alone is None or group["residual"] <= alone["residual"] else alone


def _near(a, b, d) -> bool:
    return not (a[0] > b[0] + b[2] + d or b[0] > a[0] + a[2] + d or a[1] > b[1] + b[3] + d or b[1] > a[1] + a[3] + d)


def fit_scene(img: np.ndarray, dpr: float, jobs: list[dict], rounds: int = 2, log=None) -> dict:
    """Fit every job, then back-fit: refit each with its neighbours' shadows subtracted."""
    fits = {j["id"]: fit_job(img, dpr, j) for j in jobs}
    for _ in range(rounds):
        new = {}
        for j in jobs:
            known = []
            for o in jobs:
                f = fits.get(o["id"])
                if o is j or not f or not f["hasShadow"] or not _near(o["bbox"], j["bbox"], 2 * RING):
                    continue
                known.append({"bbox": o["bbox"], "radius": o["radius"], **{k: f[k] for k in ("x", "y", "blur", "spread", "u")}})
            prev = fits.get(j["id"])
            starts = ([(prev["x"], prev["y"], prev["blur"], prev["spread"])] if prev else []) + list(STARTS[:3])
            f = fit_job(img, dpr, j, known, starts) if known else prev
            new[j["id"]] = f
        fits = new
    if log:
        for j in jobs:
            log(j["id"], fits.get(j["id"]))
    return fits


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("image", type=Path)
    ap.add_argument("--box", type=float, nargs=4, metavar=("X", "Y", "W", "H"))
    ap.add_argument("--radius", type=float, default=0.0)
    ap.add_argument("--spec", type=Path)
    ap.add_argument("--ids", default="", help="with --spec: only report these node ids (the scene is still fitted)")
    ap.add_argument("--rounds", type=int, default=2, help="with --spec: back-fitting rounds (default 2)")
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
        r = fit_node(img, dpr, list(args.box), args.radius)
        fits, order = {"box": r}, ["box"]
    else:
        jobs = jobs_from_spec(spec)
        if not jobs:
            print("[error] nothing to fit: pass --box or a --spec with painted nodes", file=sys.stderr)
            return 2
        fits = fit_scene(img, dpr, jobs, args.rounds)
        want = {s.strip() for s in args.ids.split(",") if s.strip()}
        order = [j["id"] for j in jobs if not want or j["id"] in want]
    out = []
    for i in order:
        r = fits.get(i)
        out.append({"id": i, **(r or {"error": "not enough background around the box"})})
        if r:
            flag = "shadow" if r["hasShadow"] else "none  "
            print(f"{i:18s} {flag} box-shadow: {r['css']}   residual {r['residual']} (no shadow: {r['rawResidual']})")
    if args.out:
        args.out.write_text(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
