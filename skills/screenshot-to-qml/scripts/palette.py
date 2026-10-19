#!/usr/bin/env python3
"""Extract the color palette of a UI screenshot.

Usage:
  python palette.py IMG [--dpr 2] [--out palette.json] [--min-px 12] [--merge-de 1.2]

Finds colors that are painted as solid ink — surfaces, borders, text stems, icon strokes —
and ignores antialiased edges and noise:

  1. a pixel is "solid" when it equals (max channel diff <= 2) both neighbors along the same
     axis (horizontal or vertical); this keeps fills, 1 px lines and glyph stems, drops edges
  2. solid pixels are counted per exact color, colors with fewer than --min-px design px are dropped
  3. colors closer than --merge-de (CIEDE2000) are merged into the most frequent one
  4. clusters whose members spread over a wide range are marked as gradients (flat=false)

Output (JSON): background, and colors sorted by coverage with hex, coverage (share of the
frame), pixels, flat, and a few sample points in design px. Use it to name tokens; confirm
roles by looking at where the samples are.

Exit codes: 0 ok, 2 error.
"""
from __future__ import annotations

import argparse
import json
import sys

import cv2
import numpy as np
from skimage.color import deltaE_ciede2000, rgb2lab

SOLID_TOL = 2          # max per-channel difference for "same color" neighbors
GRADIENT_SPREAD = 4.0  # ΔE spread inside a cluster above which it is reported as a gradient


def load(path: str) -> np.ndarray:
    img = cv2.imread(path, cv2.IMREAD_COLOR)
    if img is None:
        raise SystemExit(f"[error] cannot read {path}")
    return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)


def hexstr(rgb) -> str:
    r, g, b = (int(v) for v in rgb)
    return f"#{r:02X}{g:02X}{b:02X}"


def solid_mask(img: np.ndarray) -> np.ndarray:
    a = img.astype(np.int16)

    def same(x, y):
        return np.abs(x - y).max(axis=2) <= SOLID_TOL

    h = np.zeros(img.shape[:2], bool)
    v = np.zeros(img.shape[:2], bool)
    h[:, 1:-1] = same(a[:, 1:-1], a[:, :-2]) & same(a[:, 1:-1], a[:, 2:])
    v[1:-1, :] = same(a[1:-1, :], a[:-2, :]) & same(a[1:-1, :], a[2:, :])
    return h | v


def extract(img: np.ndarray, dpr: float, min_px: float, merge_de: float) -> dict:
    H, W = img.shape[:2]
    mask = solid_mask(img)
    px = img[mask]
    packed = (px[:, 0].astype(np.int64) << 16) | (px[:, 1].astype(np.int64) << 8) | px[:, 2].astype(np.int64)
    uniq, inv, counts = np.unique(packed, return_inverse=True, return_counts=True)
    min_count = max(1, int(min_px * dpr * dpr))
    keep = counts >= min_count
    colors = np.stack([(uniq >> 16) & 255, (uniq >> 8) & 255, uniq & 255], axis=1)[keep]
    counts_k = counts[keep]
    if len(colors) == 0:
        return {"background": None, "colors": []}
    order = np.argsort(-counts_k)
    colors, counts_k = colors[order], counts_k[order]
    lab = rgb2lab(colors.reshape(-1, 1, 3).astype(np.float64) / 255.0).reshape(-1, 3)

    # greedy merge: every color joins the most frequent earlier cluster within merge_de
    heads: list[int] = []
    members: dict[int, list[int]] = {}
    for i in range(len(colors)):
        if heads:
            hl = lab[heads]
            d = deltaE_ciede2000(np.repeat(lab[i][None], len(heads), 0), hl)
            j = int(np.argmin(d))
            if d[j] <= merge_de:
                members[heads[j]].append(i)
                continue
        heads.append(i)
        members[i] = [i]

    ys, xs = np.nonzero(mask)
    total = float(H * W)
    out = []
    for hidx in heads:
        idx = members[hidx]
        n = int(counts_k[idx].sum())
        spread = float(deltaE_ciede2000(np.repeat(lab[hidx][None], len(idx), 0), lab[idx]).max()) if len(idx) > 1 else 0.0
        # sample points: a few pixels that have exactly the head color
        head_packed = (int(colors[hidx][0]) << 16) | (int(colors[hidx][1]) << 8) | int(colors[hidx][2])
        where = np.nonzero(packed == head_packed)[0]
        pick = where[np.linspace(0, len(where) - 1, num=min(4, len(where)), dtype=int)] if len(where) else []
        samples = [[round(float(xs[k]) / dpr, 1), round(float(ys[k]) / dpr, 1)] for k in pick]
        out.append({"hex": hexstr(colors[hidx]), "coverage": round(n / total, 5), "pixels": round(n / dpr / dpr),
                    "flat": spread <= GRADIENT_SPREAD, "spread": round(spread, 2), "samples": samples})
    out.sort(key=lambda c: -c["coverage"])
    # background = the color that owns most of the frame border
    border = np.concatenate([img[0], img[-1], img[:, 0], img[:, -1]])
    bpacked = (border[:, 0].astype(np.int64) << 16) | (border[:, 1].astype(np.int64) << 8) | border[:, 2].astype(np.int64)
    bu, bc = np.unique(bpacked, return_counts=True)
    bg = bu[np.argmax(bc)]
    bg_hex = hexstr([(bg >> 16) & 255, (bg >> 8) & 255, bg & 255])
    return {"background": bg_hex, "solidShare": round(float(mask.mean()), 3), "colors": out}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("image")
    ap.add_argument("--dpr", type=float, default=1.0)
    ap.add_argument("--out")
    ap.add_argument("--min-px", type=float, default=12, help="minimum solid area in design px")
    ap.add_argument("--merge-de", type=float, default=1.2, help="CIEDE2000 radius for merging colors")
    ap.add_argument("--top", type=int, default=48, help="max colors to report")
    args = ap.parse_args(argv)
    res = extract(load(args.image), args.dpr, args.min_px, args.merge_de)
    res["colors"] = res["colors"][: args.top]
    text = json.dumps(res, indent=1)
    if args.out:
        with open(args.out, "w") as f:
            f.write(text)
        print(f"{len(res['colors'])} colors, background {res['background']} -> {args.out}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
