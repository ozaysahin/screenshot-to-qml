#!/usr/bin/env python3
"""Measure things in a screenshot instead of guessing them.

All coordinates are DESIGN px (screenshot px / dpr). Pass --dpr for retina/scaled input.

  python probe.py IMG [--dpr 2] color X Y [X Y ...]
        exact color at points (median of a 3x3 device-px patch) -> hex

  python probe.py IMG [--dpr 2] region X Y W H [X Y W H ...] [--k 3]
        dominant colors of a box (k-means) with coverage -> fill / text / border candidates

  python probe.py IMG [--dpr 2] edges X Y W H [X Y W H ...] [--all]
        solid-run boundaries along the box's center row and column -> element edges,
        border width, padding (the first and last 4 runs; --all for every run)

  python probe.py IMG [--dpr 2] crop X Y W H [--zoom 4] --out crop.png
        enlarged crop with a design-px grid, for looking at small details

  python probe.py IMG [--dpr 2] ruler [--step 100] --out ruler.png
        full image with a labeled coordinate grid, for reading positions

Output is compact JSON on stdout, one line per box or point list (except crop/ruler, which
write an image). Measure many boxes in one call rather than one call per box.
Exit codes: 0 ok, 2 error.
"""
from __future__ import annotations

import argparse
import json
import sys

import cv2
import numpy as np


def load(path: str) -> np.ndarray:
    img = cv2.imread(path, cv2.IMREAD_COLOR)
    if img is None:
        raise SystemExit(f"[error] cannot read {path}")
    return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)


def hx(rgb) -> str:
    r, g, b = (int(round(v)) for v in rgb)
    return f"#{r:02X}{g:02X}{b:02X}"


def box_px(x, y, w, h, dpr, shape):
    H, W = shape[:2]
    x0, y0 = int(round(x * dpr)), int(round(y * dpr))
    x1, y1 = int(round((x + w) * dpr)), int(round((y + h) * dpr))
    return max(0, x0), max(0, y0), min(W, x1), min(H, y1)


def cmd_color(img, dpr, pts):
    out = []
    for x, y in zip(pts[::2], pts[1::2], strict=True):
        cx, cy = int(round(x * dpr)), int(round(y * dpr))
        patch = img[max(0, cy - 1):cy + 2, max(0, cx - 1):cx + 2].reshape(-1, 3)
        out.append({"x": x, "y": y, "hex": hx(np.median(patch, axis=0)),
                    "spread": int(patch.max(axis=0).astype(int).max() - patch.min(axis=0).astype(int).min())})
    return out


def cmd_region(img, dpr, x, y, w, h, k):
    x0, y0, x1, y1 = box_px(x, y, w, h, dpr, img.shape)
    px = img[y0:y1, x0:x1].reshape(-1, 3).astype(np.float32)
    if len(px) < k:
        raise SystemExit("[error] region too small")
    crit = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.5)
    _, labels, centers = cv2.kmeans(px, k, None, crit, 3, cv2.KMEANS_PP_CENTERS)
    counts = np.bincount(labels.ravel(), minlength=k)
    order = np.argsort(-counts)
    clusters = []
    for i in order:
        members = px[labels.ravel() == i]
        clusters.append({"hex": hx(np.median(members, axis=0)), "coverage": round(float(counts[i] / len(px)), 3)})
    return {"box": [x, y, w, h], "median": hx(np.median(px, axis=0)), "clusters": clusters}


def runs(line: np.ndarray, tol: int = 6):
    """Split a pixel line into runs of near-constant color."""
    out, start = [], 0
    for i in range(1, len(line) + 1):
        if i == len(line) or np.abs(line[i].astype(int) - line[start].astype(int)).max() > tol:
            out.append((start, i - start, hx(line[start:i].mean(axis=0))))
            start = i
    return out


def cmd_edges(img, dpr, x, y, w, h, keep_all=False):
    """Runs along the center row and column. Borders and padding sit at the two ends, so by
    default only the first and last 4 runs are kept (the middle, often text, is counted)."""
    x0, y0, x1, y1 = box_px(x, y, w, h, dpr, img.shape)
    row = img[(y0 + y1) // 2, x0:x1]
    col = img[y0:y1, (x0 + x1) // 2]

    def fmt(rs, o):
        out = [{"from": round((o + s) / dpr, 2), "len": round(n / dpr, 2), "hex": c} for s, n, c in rs if n >= 1]
        if keep_all or len(out) <= 9:
            return out
        return out[:4] + [{"skipped": len(out) - 8}] + out[-4:]
    return {"box": [x, y, w, h], "horizontal": fmt(runs(row), x0), "vertical": fmt(runs(col), y0)}


def cmd_crop(img, dpr, x, y, w, h, zoom, out):
    x0, y0, x1, y1 = box_px(x, y, w, h, dpr, img.shape)
    crop = cv2.cvtColor(img[y0:y1, x0:x1], cv2.COLOR_RGB2BGR)
    z = cv2.resize(crop, None, fx=zoom, fy=zoom, interpolation=cv2.INTER_NEAREST)
    step = zoom * dpr
    for i in range(0, int(w) + 1):
        if i % 10 == 0:
            cv2.line(z, (int(i * step), 0), (int(i * step), z.shape[0]), (0, 200, 255), 1)
            cv2.putText(z, str(int(x + i)), (int(i * step) + 2, 12), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 200, 255), 1)
    for j in range(0, int(h) + 1):
        if j % 10 == 0:
            cv2.line(z, (0, int(j * step)), (z.shape[1], int(j * step)), (0, 200, 255), 1)
            cv2.putText(z, str(int(y + j)), (2, int(j * step) + 12), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 200, 255), 1)
    cv2.imwrite(out, z)
    return {"written": out, "size": [z.shape[1], z.shape[0]]}


def cmd_ruler(img, dpr, step, out):
    vis = cv2.cvtColor(img, cv2.COLOR_RGB2BGR).copy()
    H, W = vis.shape[:2]
    for v in range(0, int(W / dpr) + 1, step):
        cv2.line(vis, (int(v * dpr), 0), (int(v * dpr), H), (255, 0, 255), 1)
        cv2.putText(vis, str(v), (int(v * dpr) + 3, int(14 * dpr)), cv2.FONT_HERSHEY_SIMPLEX, 0.45 * dpr, (255, 0, 255), max(1, int(dpr)))
    for v in range(0, int(H / dpr) + 1, step):
        cv2.line(vis, (0, int(v * dpr)), (W, int(v * dpr)), (255, 0, 255), 1)
        cv2.putText(vis, str(v), (3, int(v * dpr) - 3), cv2.FONT_HERSHEY_SIMPLEX, 0.45 * dpr, (255, 0, 255), max(1, int(dpr)))
    cv2.imwrite(out, vis)
    return {"written": out, "designSize": [round(W / dpr, 2), round(H / dpr, 2)]}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("image")
    ap.add_argument("--dpr", type=float, default=1.0)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("color"); c.add_argument("xy", type=float, nargs="+")
    r = sub.add_parser("region"); r.add_argument("box", type=float, nargs="+"); r.add_argument("--k", type=int, default=3)
    e = sub.add_parser("edges"); e.add_argument("box", type=float, nargs="+"); e.add_argument("--all", action="store_true", help="every run, not just the ends")
    k = sub.add_parser("crop"); k.add_argument("box", type=float, nargs=4); k.add_argument("--zoom", type=int, default=4); k.add_argument("--out", required=True)
    u = sub.add_parser("ruler"); u.add_argument("--step", type=int, default=100); u.add_argument("--out", required=True)
    args = ap.parse_args(argv)
    img = load(args.image)
    if args.cmd == "color":
        if len(args.xy) % 2:
            raise SystemExit("[error] color needs X Y pairs")
        res = cmd_color(img, args.dpr, args.xy)
    elif args.cmd in ("region", "edges"):
        if len(args.box) % 4:
            raise SystemExit(f"[error] {args.cmd} needs X Y W H groups")
        boxes = [args.box[i:i + 4] for i in range(0, len(args.box), 4)]
        fn = (lambda b: cmd_region(img, args.dpr, *b, args.k)) if args.cmd == "region" else (lambda b: cmd_edges(img, args.dpr, *b, args.all))
        res = fn(boxes[0]) if len(boxes) == 1 else [fn(b) for b in boxes]
    elif args.cmd == "crop":
        res = cmd_crop(img, args.dpr, *args.box, args.zoom, args.out)
    else:
        res = cmd_ruler(img, args.dpr, args.step, args.out)
    # compact: one line per result (agents pay for every line they read)
    if isinstance(res, list):
        print("[" + ",\n".join(json.dumps(x, ensure_ascii=False, separators=(",", ":")) for x in res) + "]")
    else:
        print(json.dumps(res, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
