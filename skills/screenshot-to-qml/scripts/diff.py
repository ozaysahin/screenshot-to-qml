#!/usr/bin/env python3
"""Compare a rendered Qt Quick screen with the source screenshot.

Usage:
  python diff.py SOURCE.png RENDER.png --spec design-spec.json
                 [--scene scene.json] [--thresholds thresholds.json]
                 [--out report.json] [--heatmap diff.png] [--top 3]

Metrics (all coordinates in design px; images are compared at full pixel size):
  globalSSIM   mean SSIM over the frame with text boxes masked out
               (text rasterizers never match pixel-for-pixel; text is checked separately)
  regionSSIM   SSIM inside every spec node bbox (text masked), at the best alignment within
               1 design px (position is geometryPx's job); worst regions are listed
  colorDeltaE  CIEDE2000 between median colors of each solid-fill node (source vs render)
  geometryPx   displacement of each node found by template matching (source crop in render)
  text         (needs --scene from render.py) string match rate and position error of
               every spec text run; a run may match a whole Text, one of its lines or a
               substring of a line (split or merged runs are fine); onTargetRate = share of
               runs found within textPositionPx

Pass/fail uses --thresholds (evals/cases/*/thresholds.json format) or built-in defaults.
Exit codes: 0 pass, 1 below threshold, 2 error.
"""
from __future__ import annotations

import argparse
import json
import sys
import unicodedata
from pathlib import Path

import cv2
import numpy as np
from skimage.color import deltaE_ciede2000, rgb2lab
from skimage.metrics import structural_similarity

DEFAULTS = {
    "globalSSIM": 0.98,
    "regionSSIM": 0.90,
    "colorDeltaE2000": 2.0,
    "geometryPx": 2.0,
    "textStringMatch": 1.0,
    "textPositionPx": 2.0,
    "regionOverrides": {},
}
MIN_REGION_PX = 24          # design px; smaller nodes are too small for a stable SSIM
TEXT_MASK_PAD = 2           # design px around each text box
GEOMETRY_SEARCH = 12        # design px search radius for template matching
FLAT_STD = 3.0              # grey-level std below which a crop has no structure to match
REGION_ALIGN_PX = 1         # design px: region SSIM is taken at the best alignment within this
ALIGNED_ABOVE = 0.99        # regions already this similar are not re-aligned (speed)
SSIM_CONTEXT = 6            # device px of context around a region crop (gaussian window radius)


def load_rgb(path: Path) -> np.ndarray:
    img = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if img is None:
        raise SystemExit(f"[error] cannot read image: {path}")
    return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)


def hexstr(rgb) -> str:
    r, g, b = (int(v) for v in rgb)
    return f"#{r:02X}{g:02X}{b:02X}"


def to_px(bbox, dpr, shape, pad=0.0):
    x, y, w, h = bbox
    x0 = int(np.floor((x - pad) * dpr)); y0 = int(np.floor((y - pad) * dpr))
    x1 = int(np.ceil((x + w + pad) * dpr)); y1 = int(np.ceil((y + h + pad) * dpr))
    H, W = shape[:2]
    return max(0, x0), max(0, y0), min(W, x1), min(H, y1)


def norm_text(s: str) -> str:
    return norm_map(s)[0]


def text_mask(spec: dict, dpr: float, shape) -> np.ndarray:
    mask = np.zeros(shape[:2], dtype=bool)
    for t in spec.get("text", []):
        x0, y0, x1, y1 = to_px(t["bbox"], dpr, shape, TEXT_MASK_PAD)
        mask[y0:y1, x0:x1] = True
    for i in spec.get("icons", []):  # glyph rasterization differs like text
        x0, y0, x1, y1 = to_px(i["bbox"], dpr, shape, 1)
        mask[y0:y1, x0:x1] = True
    return mask


def ssim_map(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    ga = cv2.cvtColor(a, cv2.COLOR_RGB2GRAY).astype(np.float64)
    gb = cv2.cvtColor(b, cv2.COLOR_RGB2GRAY).astype(np.float64)
    _, smap = structural_similarity(ga, gb, data_range=255, gaussian_weights=True, sigma=1.5,
                                    use_sample_covariance=False, full=True)
    return smap


def region_ssim(spec, smap, mask, dpr, src=None, ren=None):
    """Mean SSIM (text masked) inside every node box.

    With src/ren given, a region below ALIGNED_ABOVE is re-scored at the best alignment within
    REGION_ALIGN_PX (design px): a control drawn 1 px to the side is a position error, which
    geometryPx already measures, not an appearance error. The unaligned value is kept too.
    """
    ga = gb = None
    if src is not None and ren is not None:
        ga = cv2.cvtColor(src, cv2.COLOR_RGB2GRAY).astype(np.float64)
        gb = cv2.cvtColor(ren, cv2.COLOR_RGB2GRAY).astype(np.float64)
    s = max(1, round(REGION_ALIGN_PX * dpr))
    pad = SSIM_CONTEXT + s
    H, W = smap.shape[:2]
    out = []
    for n in spec.get("nodes", []):
        x, y, w, h = n["bbox"]
        if w < MIN_REGION_PX or h < MIN_REGION_PX:
            continue
        x0, y0, x1, y1 = to_px(n["bbox"], dpr, smap.shape)
        keep = ~mask[y0:y1, x0:x1]
        sub = smap[y0:y1, x0:x1][keep]
        if sub.size < 64:
            continue
        plain = float(sub.mean())
        best, shift = plain, [0.0, 0.0]
        if ga is not None and plain < ALIGNED_ABOVE:
            X0, Y0, X1, Y1 = max(0, x0 - pad), max(0, y0 - pad), min(W, x1 + pad), min(H, y1 + pad)
            a = ga[Y0:Y1, X0:X1]
            for dy in range(-s, s + 1):
                for dx in range(-s, s + 1):
                    if (dx or dy) and Y0 + dy >= 0 and X0 + dx >= 0 and Y1 + dy <= H and X1 + dx <= W:
                        _, sm = structural_similarity(a, gb[Y0 + dy:Y1 + dy, X0 + dx:X1 + dx], data_range=255,
                                                      gaussian_weights=True, sigma=1.5, use_sample_covariance=False,
                                                      full=True)
                        v = float(sm[y0 - Y0:y1 - Y0, x0 - X0:x1 - X0][keep].mean())
                        if v > best:
                            best, shift = v, [round(dx / dpr, 2), round(dy / dpr, 2)]
        r = {"id": n["id"], "role": n.get("role"), "ssim": round(best, 4), "bbox": n["bbox"]}
        if shift != [0.0, 0.0]:
            r.update(ssimUnaligned=round(plain, 4), alignShift=shift)
        out.append(r)
    return out


def child_boxes(spec):
    kids: dict[str, list] = {}
    for n in spec.get("nodes", []):
        if n.get("parent"):
            kids.setdefault(n["parent"], []).append(n["bbox"])
    return kids


def color_checks(spec, src, ren, mask, dpr):
    kids = child_boxes(spec)
    res = []
    for n in spec.get("nodes", []):
        fill = n.get("style", {}).get("fill")
        if not isinstance(fill, dict) or fill.get("alpha", 1) < 0.999 or n.get("style", {}).get("fillImage"):
            continue
        st = n.get("style", {})
        r = st.get("radius", 0)
        r = max(r) if isinstance(r, list) else r
        inset = min(r, 12) * 0.35 + 3 + (st.get("border", {}).get("width", 0) if isinstance(st.get("border"), dict) else 0)
        x, y, w, h = n["bbox"]
        if w - 2 * inset < 4 or h - 2 * inset < 4:
            continue
        x0, y0, x1, y1 = to_px([x + inset, y + inset, w - 2 * inset, h - 2 * inset], dpr, src.shape)
        m = ~mask[y0:y1, x0:x1].copy()
        for cb in kids.get(n["id"], []):
            cx0, cy0, cx1, cy1 = to_px(cb, dpr, src.shape, 2)
            m[max(0, cy0 - y0):max(0, cy1 - y0), max(0, cx0 - x0):max(0, cx1 - x0)] = False
        if m.sum() < 32:
            continue
        a = src[y0:y1, x0:x1][m]
        b = ren[y0:y1, x0:x1][m]
        # the fill is the source's dominant color: decorations that are not nodes (a status dot,
        # a ::before knob, a checkmark) must not move the median. Compare both images on the
        # pixels where the source shows that color.
        q = (a.astype(np.int32) // 8) @ np.array([1024, 32, 1])
        keys, counts = np.unique(q, return_counts=True)
        dom = q == keys[counts.argmax()]
        if dom.sum() >= max(16, 0.25 * len(a)):
            ref = rgb2lab(np.median(a[dom], axis=0).reshape(1, 1, 3) / 255.0)
            near = deltaE_ciede2000(rgb2lab(a.reshape(-1, 1, 3) / 255.0), np.broadcast_to(ref, (len(a), 1, 3)))[:, 0] < 3.0
            a, b = a[near], b[near]
        ma, mb = np.median(a, axis=0), np.median(b, axis=0)
        la = rgb2lab(ma.reshape(1, 1, 3) / 255.0)
        lb = rgb2lab(mb.reshape(1, 1, 3) / 255.0)
        de = float(deltaE_ciede2000(la, lb)[0, 0])
        res.append({"id": n["id"], "deltaE": round(de, 2), "expected": hexstr(ma), "rendered": hexstr(mb)})
    return res


def subpixel_peak(score: np.ndarray, loc) -> tuple[float, float]:
    """Refine an integer correlation peak with a 1-D parabola fit per axis."""
    x, y = loc

    def refine(a, b, c):
        den = a - 2 * b + c
        return 0.0 if abs(den) < 1e-9 else float(np.clip(0.5 * (a - c) / den, -0.5, 0.5))

    fx, fy = float(x), float(y)
    if 0 < x < score.shape[1] - 1:
        fx += refine(score[y, x - 1], score[y, x], score[y, x + 1])
    if 0 < y < score.shape[0] - 1:
        fy += refine(score[y - 1, x], score[y, x], score[y + 1, x])
    return fx, fy


def geometry_checks(spec, src, ren, dpr):
    gs = cv2.cvtColor(src, cv2.COLOR_RGB2GRAY)
    gr = cv2.cvtColor(ren, cv2.COLOR_RGB2GRAY)
    H, W = gs.shape
    s = int(round(GEOMETRY_SEARCH * dpr))
    res = []
    for n in spec.get("nodes", []):
        x, y, w, h = n["bbox"]
        if w < MIN_REGION_PX or h < MIN_REGION_PX:
            continue
        x0, y0, x1, y1 = to_px(n["bbox"], dpr, gs.shape)
        tpl = gs[y0:y1, x0:x1]
        if tpl.size == 0 or tpl.std() < FLAT_STD:
            continue
        sx0, sy0, sx1, sy1 = max(0, x0 - s), max(0, y0 - s), min(W, x1 + s), min(H, y1 + s)
        win = gr[sy0:sy1, sx0:sx1]
        if win.shape[0] < tpl.shape[0] or win.shape[1] < tpl.shape[1]:
            continue
        score = cv2.matchTemplate(win, tpl, cv2.TM_CCOEFF_NORMED)
        _, best, _, loc = cv2.minMaxLoc(score)
        fx, fy = subpixel_peak(score, loc)
        dx = (sx0 + fx - x0) / dpr
        dy = (sy0 + fy - y0) / dpr
        res.append({"id": n["id"], "dx": round(dx, 2), "dy": round(dy, 2),
                    "offset": round(float(np.hypot(dx, dy)), 2), "match": round(float(best), 3)})
    return res


def text_offset(gold_bbox, rendered: dict, align: str, gold_baseline=None) -> tuple[float, float]:
    """Offset of a rendered text from the spec run: horizontally from the aligned edge,
    vertically between baselines when both are known (else between box centers, which also
    moves when the two fonts' ascent/descent differ)."""
    gx, gy, gw, gh = gold_bbox
    rx, ry, rw, rh = rendered.get("textBox") or rendered["bbox"]
    if align == "center":
        ex = (rx + rw / 2) - (gx + gw / 2)
    elif align in ("end", "right"):
        ex = (rx + rw) - (gx + gw)
    else:
        ex = rx - gx
    if gold_baseline is not None and rendered.get("baseline") is not None:
        ey = rendered["baseline"] - gold_baseline
    else:
        ey = (ry + rh / 2) - (gy + gh / 2)
    return ex, ey


SEPARATORS = " ·•|/-–—:,"   # a design's separators may be drawn as their own item or shape
# characters a screenshot cannot tell apart from their ASCII spelling
FOLD = {"\u2026": "...", "\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"'}


def norm_map(raw: str) -> tuple[str, list[int]]:
    """Whitespace collapsed and trimmed, NFC, look-alike punctuation folded (… -> ...),
    plus, for every output character, its index in the NFC raw string."""
    raw = unicodedata.normalize("NFC", raw)
    out, idx, space = [], [], True
    for i, ch in enumerate(raw):
        if ch.isspace():
            if not space:
                out.append(" ")
                idx.append(i)
            space = True
        else:
            for c in FOLD.get(ch, ch):
                out.append(c)
                idx.append(i)
            space = False
    if out and out[-1] == " ":
        out.pop()
        idx.pop()
    return "".join(out), idx


def text_segments(scene) -> list[dict]:
    """Everything a spec text run may match: whole texts, their lines, and (via adv) substrings."""
    segs = []
    for ti, t in enumerate(scene.get("texts", [])):
        px = t.get("font", {}).get("px")
        lines = t.get("lines") or []
        # single-line items: the baseline-anchored, whitespace-trimmed line box
        whole = lines[0]["box"] if len(lines) == 1 else (t.get("textBox") or t["bbox"])   # textBox = union of lines
        base = lines[0].get("baseline") if lines else None
        segs.append({"item": ti, "line": None, "s": norm_text(t["string"]), "box": whole, "baseline": base, "px": px,
                     "itemBox": t["bbox"]})
        for li, ln in enumerate(lines):
            s, idx = norm_map(ln["string"])
            segs.append({"item": ti, "line": li, "s": s, "idx": idx, "box": ln["box"], "adv": ln.get("adv"),
                         "origin": ln.get("origin", ln["box"][0]), "baseline": ln.get("baseline"), "px": px})
        # a run that starts inside one line and wraps onto the next (a tinted second half of a
        # headline): line i joined with line i+1, positioned by line i
        for li in range(len(lines) - 1):
            s0, idx0 = norm_map(lines[li]["string"])
            s1, _ = norm_map(lines[li + 1]["string"])
            if s0 and s1 and lines[li].get("adv"):
                segs.append({"item": ti, "line": ("join", li), "s": s0 + " " + s1, "idx": idx0, "split": len(s0),
                             "box": lines[li]["box"], "next": lines[li + 1]["box"], "adv": lines[li]["adv"],
                             "origin": lines[li].get("origin", lines[li]["box"][0]),
                             "baseline": lines[li].get("baseline"), "px": px, "itemBox": t["bbox"]})
    return segs


NEAR_PX = 24          # design px: short strings ("1", "°C") may match a substring only this close


def text_checks(spec, scene, limit_px: float = 2.0):
    """Match every spec text run to rendered text.

    A run may match a whole Text item, one line of a multi-line item, or a substring of a line
    (its box from the line's glyph advances); separators trimmed from both ends are tried too.
    Pairs are assigned globally, nearest first (right font size before wrong), so a repeated
    string ("1" in a footer and in a pager) goes to the copy that is actually there. A rendered
    item can host several runs as long as their spans do not overlap.
    """
    segs = text_segments(scene)
    runs = spec.get("text", [])

    def box_of(sg, span):
        if span is None or not sg.get("adv") or span == (0, len(sg["s"])):
            return sg["box"]
        a, b = span
        _, y, _, h = sg["box"]
        x0 = sg["adv"][sg["idx"][a]]
        if "split" in sg:     # joined lines: union of the part on the first line and the next line, like a browser's rects
            fx0, fx1 = sg["origin"] + x0, sg["origin"] + sg["adv"][sg["idx"][sg["split"] - 1] + 1]
            nx, ny, nw, nh = sg["next"]
            return [min(fx0, nx), y, max(fx1, nx + nw) - min(fx0, nx), ny + nh - y]
        x1 = sg["adv"][sg["idx"][b - 1] + 1]
        return [sg["origin"] + x0, y, x1 - x0, h]

    def candidates(want):
        out = []
        for si, sg in enumerate(segs):
            if sg["line"] is None:
                if sg["s"] == want:
                    out.append((si, None, 0))
                continue
            if "split" in sg:                               # must start on the first line and cross the break
                start = sg["s"].find(want)
                while start != -1:
                    if start < sg["split"] < start + len(want):
                        out.append((si, (start, start + len(want)), 2))
                    start = sg["s"].find(want, start + 1)
                continue
            if sg["s"] == want:
                out.append((si, (0, len(want)), 1))
            elif sg.get("adv") and want:
                start = sg["s"].find(want)
                while start != -1:
                    out.append((si, (start, start + len(want)), 2))
                    start = sg["s"].find(want, start + 1)
        return out

    pairs = []
    for ti, t in enumerate(runs):
        want = norm_text(t["string"])
        trimmed = want.strip(SEPARATORS)
        cands = [(c, 0) for c in candidates(want)]
        if trimmed and trimmed != want:
            cands += [(c, 1) for c in candidates(trimmed)]
        align = t.get("align", "start")
        px = t.get("font", {}).get("px")
        gx, gy, gw, gh = t["bbox"]
        vertical = t.get("lines", 1) == 1 and len(want) > 2 and gh > 2 * gw     # rotated / vertical writing mode
        lead_cut = len(want) - len(want.lstrip(SEPARATORS))
        tail_cut = len(want) - len(want.rstrip(SEPARATORS))
        for (si, span, tier), trim in cands:
            sg = segs[si]
            a = align
            if trim:   # separators drawn elsewhere: compare the edge that was not cut
                a = "end" if lead_cut and not tail_cut else "start" if tail_cut and not lead_cut else "center"
            ex, ey = text_offset(t["bbox"], {"textBox": box_of(sg, span), "baseline": sg.get("baseline")},
                                 a, t.get("baseline"))
            if trim and lead_cut and tail_cut:
                ex = 0.0                                    # both ends cut: only the baseline is comparable
            if vertical:   # baselines and line boxes do not apply: compare the centers of the turned boxes
                rx, ry, rw, rh = sg.get("itemBox") or sg["box"]
                ex, ey = (rx + rw / 2) - (gx + gw / 2), (ry + rh / 2) - (gy + gh / 2)
            d = float(np.hypot(ex, ey))
            if tier == 2 and len(want) <= 2 and d > NEAR_PX:
                continue                                    # a lone digit somewhere else is not a match
            pairs.append(((d > NEAR_PX, sg["px"] != px, trim, d, tier), ti, si, span, ex, ey))
    pairs.sort(key=lambda p: p[0])

    whole_used: set[int] = set()
    spans: dict[tuple[int, int], list[tuple[int, int]]] = {}
    done: dict[int, dict] = {}
    for _, ti, si, span, ex, ey in pairs:
        if ti in done:
            continue
        sg = segs[si]
        item = sg["item"]
        if item in whole_used:
            continue
        if span is None:
            if any(k[0] == item for k in spans):
                continue
            whole_used.add(item)
        else:
            key = (item, sg["line"])
            if any(not (span[1] <= a or span[0] >= b) for a, b in spans.get(key, [])):
                continue
            spans.setdefault(key, []).append(span)
        done[ti] = {"string": runs[ti]["string"], "dx": round(ex, 2), "dy": round(ey, 2),
                    "offset": round(float(np.hypot(ex, ey)), 2),
                    "matchedAs": "item" if span is None else ("line" if span == (0, len(sg["s"])) else "substring")}
    res = [done[i] for i in range(len(runs)) if i in done]
    missing = [t["string"] for i, t in enumerate(runs) if i not in done]
    total = len(runs)
    on_target = sum(r["offset"] <= limit_px for r in res)
    return {"matchRate": round((total - len(missing)) / total, 4) if total else 1.0,
            "onTargetRate": round(on_target / total, 4) if total else 1.0,
            "missing": missing, "runs": res,
            "maxOffset": round(max((r["offset"] for r in res), default=0.0), 2)}


def heatmap(src, ren, mask, worst, dpr, path):
    """Dimmed source with per-pixel differences in hot colors; worst regions boxed."""
    d = np.abs(src.astype(np.int16) - ren.astype(np.int16)).max(axis=2).astype(np.float32)
    gray = cv2.cvtColor(cv2.cvtColor(src, cv2.COLOR_RGB2GRAY), cv2.COLOR_GRAY2BGR)
    vis = (gray * 0.45).astype(np.uint8)
    hot = cv2.applyColorMap(np.clip(d * 4, 0, 255).astype(np.uint8), cv2.COLORMAP_INFERNO)
    sel = d > 12
    vis[sel] = hot[sel]
    vis[mask & sel] = (hot[mask & sel] * 0.4).astype(np.uint8)   # text differences are expected; muted
    for r in worst:
        x0, y0, x1, y1 = to_px(r["bbox"], dpr, src.shape)
        cv2.rectangle(vis, (x0, y0), (x1 - 1, y1 - 1), (80, 220, 255), max(1, int(2 * dpr)))
        cv2.putText(vis, f"{r['id']} {r['ssim']:.3f}", (x0 + 4, max(14, y0 - 6)), cv2.FONT_HERSHEY_SIMPLEX,
                    0.5 * dpr, (80, 220, 255), max(1, int(dpr)), cv2.LINE_AA)
    cv2.imwrite(str(path), vis)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source", type=Path)
    ap.add_argument("render", type=Path)
    ap.add_argument("--spec", type=Path, required=True)
    ap.add_argument("--scene", type=Path)
    ap.add_argument("--thresholds", type=Path)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--heatmap", type=Path)
    ap.add_argument("--top", type=int, default=3)
    args = ap.parse_args(argv)

    spec = json.loads(args.spec.read_text())
    th = dict(DEFAULTS)
    if args.thresholds:
        th.update(json.loads(args.thresholds.read_text()))
    dpr = float(spec.get("meta", {}).get("dpr", 1))
    src, ren = load_rgb(args.source), load_rgb(args.render)
    if src.shape != ren.shape:
        print(f"[error] size mismatch: source {src.shape[1]}x{src.shape[0]} vs render {ren.shape[1]}x{ren.shape[0]}. "
              f"Render with --size {spec['meta']['designSize'][0]} {spec['meta']['designSize'][1]} --dpr {dpr:g}",
              file=sys.stderr)
        return 2

    mask = text_mask(spec, dpr, src.shape)
    smap = ssim_map(src, ren)
    g_ssim = float(smap[~mask].mean())
    regions = sorted(region_ssim(spec, smap, mask, dpr, src, ren), key=lambda r: r["ssim"])
    colors = sorted(color_checks(spec, src, ren, mask, dpr), key=lambda c: -c["deltaE"])
    geom = sorted(geometry_checks(spec, src, ren, dpr), key=lambda g: -g["offset"])
    text = text_checks(spec, json.loads(args.scene.read_text()), th["textPositionPx"]) if args.scene else None

    failures = []
    if g_ssim < th["globalSSIM"]:
        failures.append(f"global SSIM {g_ssim:.4f} < {th['globalSSIM']}")
    for r in regions:
        limit = th.get("regionOverrides", {}).get(r["id"].split("[")[0], {}).get("regionSSIM", th["regionSSIM"])
        r["limit"] = limit
        if r["ssim"] < limit:
            failures.append(f"region {r['id']} SSIM {r['ssim']:.4f} < {limit}")
    for c in colors:
        if c["deltaE"] > th["colorDeltaE2000"]:
            failures.append(f"color {c['id']} ΔE {c['deltaE']} > {th['colorDeltaE2000']} ({c['expected']} → {c['rendered']})")
    for g in geom:
        if g["offset"] > th["geometryPx"] and g["match"] > 0.5:
            failures.append(f"geometry {g['id']} off by ({g['dx']:+}, {g['dy']:+}) px")
    if text is not None:
        if text["matchRate"] < th["textStringMatch"]:
            failures.append(f"text match {text['matchRate']:.3f} < {th['textStringMatch']}; missing: {text['missing'][:8]}")
        for r in text["runs"]:
            if r["offset"] > th["textPositionPx"]:
                failures.append(f"text '{r['string'][:30]}' off by ({r['dx']:+}, {r['dy']:+}) px")

    worst = regions[: args.top]
    report = {
        "pass": not failures,
        "metrics": {
            "globalSSIM": round(g_ssim, 4),
            "regionSSIMMin": regions[0]["ssim"] if regions else None,
            "colorDeltaEMax": colors[0]["deltaE"] if colors else None,
            "geometryMaxPx": geom[0]["offset"] if geom else None,
            "textMatchRate": text["matchRate"] if text else None,
            "textMaxOffsetPx": text["maxOffset"] if text else None,
            "textOnTargetRate": text["onTargetRate"] if text else None,
        },
        "worstRegions": worst,
        "failures": failures,
        "details": {"regions": regions, "colors": colors, "geometry": geom, "text": text},
        "thresholds": th,
    }
    if args.out:
        args.out.write_text(json.dumps(report, indent=1, ensure_ascii=False))
    if args.heatmap:
        heatmap(src, ren, mask, worst, dpr, args.heatmap)

    m = report["metrics"]
    print(f"{'PASS' if report['pass'] else 'FAIL'}  globalSSIM={m['globalSSIM']}  regionMin={m['regionSSIMMin']}  "
          f"ΔEmax={m['colorDeltaEMax']}  geomMax={m['geometryMaxPx']}px  "
          f"text={m['textMatchRate']} (max off {m['textMaxOffsetPx']}px)")
    print("worst regions: " + ", ".join(f"{r['id']}={r['ssim']}" for r in worst))
    for f in failures[:25]:
        print("  - " + f)
    if len(failures) > 25:
        print(f"  … {len(failures) - 25} more (see report)")
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
