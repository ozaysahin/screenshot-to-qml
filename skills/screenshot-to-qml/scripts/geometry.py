#!/usr/bin/env python3
"""Detect solid surfaces (cards, panels, buttons, chips, bars) in a UI screenshot.

Usage:
  python geometry.py IMG [--dpr 2] [--palette palette.json] [--out geometry.json]

For every flat palette color that covers enough of the frame, the pixels of that color are
grouped into connected regions (text and icons inside a surface leave holes, which are
ignored). A region becomes a surface when its filled outline covers >= 75 % of its box.
For each surface it reports, in design px:

  bbox     outer box (border included when a border was found)
  fill     the surface color
  radius   from the pixels missing in the corners (area of a quarter circle cut-out)
  border   {width, color} when a thin ring of one color surrounds the fill
  parent   smallest detected surface that contains it
and groups siblings with the same size and fill into `repeat` hints (models).

Exit codes: 0 ok, 2 error.
"""
from __future__ import annotations

import argparse
import json
import sys

import cv2
import numpy as np
import palette as palette_mod

MIN_SIDE = 12          # design px; smaller regions are icons/glyph parts, not surfaces
MIN_SOLIDITY = 0.75    # filled outline area / box area (a circle is 0.785)
COLOR_TOL = 6          # max per-channel distance to belong to a fill color
MIN_COVERAGE = 0.0004  # share of the frame a fill color needs to be considered
CORNER_CUT = 1 - np.pi / 4


def to_design(img: np.ndarray, dpr: float) -> np.ndarray:
    if abs(dpr - 1) < 1e-6:
        return img
    h, w = img.shape[:2]
    return cv2.resize(img, (round(w / dpr), round(h / dpr)), interpolation=cv2.INTER_AREA)


def hex_to_rgb(h: str) -> np.ndarray:
    return np.array([int(h[i:i + 2], 16) for i in (1, 3, 5)], dtype=np.int16)


def estimate_radius(filled: np.ndarray) -> float:
    h, w = filled.shape
    s = max(1, min(h, w) // 2)
    corners = [filled[:s, :s], filled[:s, w - s:], filled[h - s:, :s], filled[h - s:, w - s:]]
    radii = []
    for c in corners:
        missing = float((c == 0).sum())
        radii.append(np.sqrt(missing / CORNER_CUT) if missing > 0 else 0.0)
    r = float(np.median(radii))
    return round(min(r, min(h, w) / 2), 1)


def detect_border(img: np.ndarray, box, fill: np.ndarray):
    """Walk outward from the middle of each side; a short run of one color that differs
    from the fill and from what lies beyond is a border."""
    x, y, w, h = box
    H, W = img.shape[:2]
    rays = [((x - 1, y + h // 2), (-1, 0)), ((x + w, y + h // 2), (1, 0)),
            ((x + w // 2, y - 1), (0, -1)), ((x + w // 2, y + h), (0, 1))]
    found = []
    for (px, py), (dx, dy) in rays:
        if not (0 <= px < W and 0 <= py < H):
            return None
        c0 = img[py, px].astype(np.int16)
        if np.abs(c0 - fill).max() <= COLOR_TOL:
            return None
        n = 0
        while 0 <= px < W and 0 <= py < H and np.abs(img[py, px].astype(np.int16) - c0).max() <= COLOR_TOL and n < 6:
            px += dx
            py += dy
            n += 1
        if n > 4 or not (0 <= px < W and 0 <= py < H):
            return None
        found.append((n, c0))
    widths = [n for n, _ in found]
    cols = np.array([c for _, c in found])
    if max(widths) - min(widths) > 1 or np.abs(cols - cols[0]).max() > COLOR_TOL:
        return None
    return int(round(np.median(widths))), palette_mod.hexstr(cols[0])


def detect(img: np.ndarray, dpr: float, pal: dict | None = None) -> dict:
    d = to_design(img, dpr)
    H, W = d.shape[:2]
    if pal is None:
        pal = palette_mod.extract(img, dpr, 12, 1.2)
    fills = [c for c in pal["colors"] if c["flat"] and c["coverage"] >= MIN_COVERAGE]
    di = d.astype(np.int16)
    boxes = []
    for c in fills:
        rgb = hex_to_rgb(c["hex"])
        mask = (np.abs(di - rgb).max(axis=2) <= COLOR_TOL).astype(np.uint8)
        # Both connectivities: with 4 an antialiased 1 px rounded border separates an input's
        # interior from the same-colored card around it; with 8 thin rings (bordered boxes
        # whose inside is not one flat color) stay closed. Duplicates are removed below.
        for conn in (4, 8):
            boxes.extend(_components(d, mask, rgb, c["hex"], conn, W, H))
    return _finish(boxes, W, H)


def _components(d, mask, rgb, hex_color, conn, W, H) -> list[dict]:
    """Surfaces of one fill color: connected regions whose filled outline is box-like."""
    found = []
    n, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=conn)
    for lab in range(1, n):
        x, y, w, h, _area = (int(v) for v in stats[lab])
        if w < MIN_SIDE or h < MIN_SIDE:
            continue
        comp = (labels[y:y + h, x:x + w] == lab).astype(np.uint8)
        contours, _ = cv2.findContours(comp, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        filled = np.zeros((h, w), np.uint8)
        cv2.drawContours(filled, contours, -1, 1, thickness=cv2.FILLED)
        solidity = float(filled.mean())
        if solidity < MIN_SOLIDITY:
            continue
        role = "background" if (w >= W - 1 and h >= H - 1) else None
        radius = estimate_radius(filled)
        border = detect_border(d, (x, y, w, h), rgb) if role is None else None
        if border:
            bw = border[0]
            x, y, w, h = x - bw, y - bw, w + 2 * bw, h + 2 * bw
            radius = round(radius + bw, 1) if radius else 0.0
        found.append({"bbox": [x, y, w, h], "fill": hex_color, "radius": radius,
                      "border": {"width": border[0], "color": border[1]} if border else None,
                      "solidity": round(solidity, 3), "role": role})
    return found


def _lab(hex_color: str) -> np.ndarray:
    from skimage.color import rgb2lab
    rgb = np.array([int(hex_color[i:i + 2], 16) for i in (1, 3, 5)], float).reshape(1, 1, 3) / 255
    return rgb2lab(rgb).reshape(3)


def _de(a: str, b: str) -> float:
    from skimage.color import deltaE_ciede2000
    return float(deltaE_ciede2000(_lab(a), _lab(b)))


def _contains(a, b, tol=1):
    return (a["bbox"][0] - tol <= b["bbox"][0] and a["bbox"][1] - tol <= b["bbox"][1]
            and a["bbox"][0] + a["bbox"][2] + tol >= b["bbox"][0] + b["bbox"][2]
            and a["bbox"][1] + a["bbox"][3] + tol >= b["bbox"][1] + b["bbox"][3])


def _assign_parents(boxes):
    boxes.sort(key=lambda b: -(b["bbox"][2] * b["bbox"][3]))
    for i, b in enumerate(boxes):
        b["parent_idx"] = None
        for j in range(i - 1, -1, -1):
            if _contains(boxes[j], b) and boxes[j]["bbox"] != b["bbox"]:
                b["parent_idx"] = j
                break


def _gradient_groups(boxes):
    """Stacked bands of close colors (a gradient rendered as flat steps) -> index groups."""
    idx = [i for i, b in enumerate(boxes) if not b["border"] and b["role"] != "background"]
    parent = {i: i for i in idx}

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for a in idx:
        ax, ay, aw, ah = boxes[a]["bbox"]
        for b in idx:
            if b <= a:
                continue
            bx, by, bw, bh = boxes[b]["bbox"]
            # bands of one gradient touch or overlap along one axis and line up on the other
            # (the color tolerance makes neighbouring steps overlap by a few rows)
            y_touch = min(ay + ah, by + bh) - max(ay, by) >= -1
            x_touch = min(ax + aw, bx + bw) - max(ax, bx) >= -1
            vert = y_touch and min(ax + aw, bx + bw) - max(ax, bx) >= 0.6 * min(aw, bw) and abs(aw - bw) <= 0.4 * max(aw, bw)
            horiz = x_touch and min(ay + ah, by + bh) - max(ay, by) >= 0.6 * min(ah, bh) and abs(ah - bh) <= 0.4 * max(ah, bh)
            if vert and horiz:        # nested/overlapping boxes, not bands
                continue
            if (vert or horiz) and 0.3 < _de(boxes[a]["fill"], boxes[b]["fill"]) < 10:
                parent[find(a)] = find(b)
    groups: dict[int, list[int]] = {}
    for i in idx:
        groups.setdefault(find(i), []).append(i)
    out = []
    for g in groups.values():
        if len(g) < 3:
            continue
        boxes_g = [boxes[i]["bbox"] for i in g]
        ux0, uy0 = min(b[0] for b in boxes_g), min(b[1] for b in boxes_g)
        ux1, uy1 = max(b[0] + b[2] for b in boxes_g), max(b[1] + b[3] for b in boxes_g)
        union = (ux1 - ux0) * (uy1 - uy0)
        if max(b[2] * b[3] for b in boxes_g) <= 0.6 * union:   # many small steps, not a few big panels
            out.append(g)
    return out


def _finish(boxes, W, H):
    # dedupe identical boxes (keep the higher solidity)
    uniq = {}
    for b in sorted(boxes, key=lambda b: -b["solidity"]):
        key = tuple(round(v) for v in b["bbox"])
        uniq.setdefault(key, b)
    boxes = list(uniq.values())
    _assign_parents(boxes)

    # a region with its parent's color and no border is not a visible surface
    # (glyph bowls, gaps between siblings, inner padding boxes)
    boxes = [b for b in boxes if not (b["parent_idx"] is not None and not b["border"]
                                      and b["fill"] == boxes[b["parent_idx"]]["fill"])]
    _assign_parents(boxes)

    # gradients drawn as stacked flat bands -> one gradient candidate
    gradients = []
    drop = set()
    for g in _gradient_groups(boxes):
        xs = [boxes[i]["bbox"] for i in g]
        x0, y0 = min(b[0] for b in xs), min(b[1] for b in xs)
        x1, y1 = max(b[0] + b[2] for b in xs), max(b[1] + b[3] for b in xs)
        ordered = sorted(g, key=lambda i: (boxes[i]["bbox"][1], boxes[i]["bbox"][0]))
        vertical = (y1 - y0) >= (x1 - x0) or len({boxes[i]["bbox"][1] for i in g}) > 1
        gradients.append({"bbox": [x0, y0, x1 - x0, y1 - y0], "direction": "vertical" if vertical else "horizontal",
                          "from": boxes[ordered[0]]["fill"], "to": boxes[ordered[-1]]["fill"], "bands": len(g)})
        drop.update(g)
    boxes = [b for i, b in enumerate(boxes) if i not in drop]
    _assign_parents(boxes)
    for i, b in enumerate(boxes):
        b["id"] = "bg" if b["role"] == "background" else f"s{i}"
    for b in boxes:
        b["parent"] = boxes[b["parent_idx"]]["id"] if b["parent_idx"] is not None else None

    # repeated siblings -> model hints
    groups: dict[tuple, list] = {}
    for b in boxes:
        if b["role"] == "background":
            continue
        key = (b["parent"], b["fill"], round(b["bbox"][2] / 2), round(b["bbox"][3] / 2))
        groups.setdefault(key, []).append(b["id"])
    repeats = [{"parent": k[0], "fill": k[1], "size": [k[2] * 2, k[3] * 2], "ids": v, "count": len(v)}
               for k, v in groups.items() if len(v) >= 2]

    nodes = []
    for b in boxes:
        style = {"fill": {"hex": b["fill"], "alpha": 1.0}}
        if b["radius"]:
            style["radius"] = b["radius"]
        if b["border"]:
            style["border"] = {"width": b["border"]["width"], "color": {"hex": b["border"]["color"], "alpha": 1.0}}
        nodes.append({"id": b["id"], "role": b["role"], "parent": b["parent"], "bbox": b["bbox"],
                      "style": style, "src": "measured", "conf": round(min(1.0, b["solidity"] + 0.1), 2)})
    for k, g in enumerate(gradients):
        g["id"] = f"g{k}"
    return {"designSize": [W, H], "nodes": nodes, "repeats": repeats, "gradients": gradients}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("image")
    ap.add_argument("--dpr", type=float, default=1.0)
    ap.add_argument("--palette")
    ap.add_argument("--out")
    args = ap.parse_args(argv)
    img = palette_mod.load(args.image)
    pal = json.loads(open(args.palette).read()) if args.palette else None
    res = detect(img, args.dpr, pal)
    text = json.dumps(res, indent=1)
    if args.out:
        with open(args.out, "w") as f:
            f.write(text)
        print(f"{len(res['nodes'])} surfaces, {len(res['repeats'])} repeat groups -> {args.out}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
