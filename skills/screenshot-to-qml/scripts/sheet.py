#!/usr/bin/env python3
"""Contact sheets: many small crops in one image, so an agent looks once instead of N times.

Usage:
  python sheet.py compare SOURCE.png RENDER.png --spec design-spec.json --report report.json --out worst.png [--max 8]
  python sheet.py ocr SOURCE.png --spec design-spec.draft.json --out ocr_sheet.png [--max 48]

compare: for the worst items of a check (failing or lowest regions, geometry offsets, text off
target), the source crop and the render crop side by side, labelled with the id and the
number that failed. check.py writes it as worst.png after every failed diff.
ocr: every text run of a draft spec as a crop labelled with its id (t0, t1 …), in reading
order, so all OCR strings can be checked against the pixels in one look. analyze.py writes it
as ocr_sheet.png (several sheets when there are many runs).

All boxes are design px (screenshot px / DPR). Exit codes: 0 ok, 2 error.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

FONT_PATHS = ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "C:/Windows/Fonts/segoeui.ttf",
              "/System/Library/Fonts/Supplemental/Arial.ttf", "/Library/Fonts/Arial.ttf")
BG, INK, DIM, BAD = (24, 26, 32), (235, 238, 245), (150, 156, 170), (255, 120, 110)


def font(size: int) -> ImageFont.ImageFont:
    for p in FONT_PATHS:
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default(size=size)


def crop(img: Image.Image, bbox, dpr: float, pad: float, max_w: int, max_h: int) -> Image.Image:
    x, y, w, h = bbox
    box = (max(0, int((x - pad) * dpr)), max(0, int((y - pad) * dpr)),
           min(img.width, int((x + w + pad) * dpr + 0.999)), min(img.height, int((y + h + pad) * dpr + 0.999)))
    if box[2] <= box[0] or box[3] <= box[1]:
        return Image.new("RGB", (8, 8), BG)
    c = img.crop(box)
    s = min(max_w / c.width, max_h / c.height, 4.0)       # up to 4× for small items, nearest-neighbour
    return c.resize((max(1, int(c.width * s)), max(1, int(c.height * s))),
                    Image.NEAREST if s >= 1 else Image.LANCZOS)


def grid(tiles: list[Image.Image], cols: int, gap: int = 10) -> Image.Image:
    rows = [tiles[i:i + cols] for i in range(0, len(tiles), cols)]
    w = max(sum(t.width for t in r) + gap * (len(r) + 1) for r in rows)
    h = sum(max(t.height for t in r) for r in rows) + gap * (len(rows) + 1)
    out = Image.new("RGB", (w, h), BG)
    y = gap
    for r in rows:
        x = gap
        for t in r:
            out.paste(t, (x, y))
            x += t.width + gap
        y += max(t.height for t in r) + gap
    return out


def labelled(parts: list[Image.Image], label: str, note: str = "", width: int | None = None) -> Image.Image:
    f, fs = font(15), font(13)
    body_w = sum(p.width for p in parts) + 6 * (len(parts) - 1)
    w = max(width or 0, body_w, 120)
    h = 22 + (18 if note else 0) + max(p.height for p in parts)
    tile = Image.new("RGB", (w, h), BG)
    d = ImageDraw.Draw(tile)
    d.text((2, 2), label, fill=INK, font=f)
    if note:
        d.text((2, 21), note, fill=BAD, font=fs)
    x, y = 0, 22 + (18 if note else 0)
    for p in parts:
        tile.paste(p, (x, y))
        x += p.width + 6
    return tile


# ---- compare (check) -------------------------------------------------------------------------

def worst_items(report: dict, spec: dict, limit: int) -> list[dict]:
    """The items to look at, most severe first: (id, bbox, note)."""
    nodes = {n["id"]: n for n in spec.get("nodes", []) if n.get("bbox")}
    texts = spec.get("text", [])
    det = report.get("details", {})
    items = []
    for r in sorted(det.get("regions", []), key=lambda r: r["ssim"]):
        if r["ssim"] < r.get("limit", 0.9) or len(items) < 3:
            items.append({"id": r["id"], "bbox": r["bbox"], "note": f"region SSIM {r['ssim']}",
                          "score": (r.get("limit", 0.9) - r["ssim"]) * 40})
    lim_g = report.get("thresholds", {}).get("geometryPx", 2)
    for g in det.get("geometry", []):
        if g.get("offset", 0) > lim_g and g["id"] in nodes:
            items.append({"id": g["id"], "bbox": nodes[g["id"]]["bbox"],
                          "note": f"off by ({g['dx']:+.1f}, {g['dy']:+.1f}) px", "score": g["offset"] / lim_g})
    lim_t = report.get("thresholds", {}).get("textPositionPx", 2)
    by_string = {}
    for t in texts:
        by_string.setdefault(t.get("string"), t)
    for t in det.get("text", {}).get("runs", []):
        if t.get("offset", 0) > lim_t and t.get("string") in by_string:
            items.append({"id": f"'{t['string'][:28]}'", "bbox": by_string[t["string"]]["bbox"],
                          "note": f"text off by ({t['dx']:+.1f}, {t['dy']:+.1f}) px", "score": t["offset"] / lim_t})
    for s in det.get("text", {}).get("missing", [])[:4]:
        if s in by_string:
            items.append({"id": f"'{s[:28]}'", "bbox": by_string[s]["bbox"], "note": "text missing in render", "score": 3})
    seen, out = set(), []
    for it in sorted(items, key=lambda i: -i["score"]):
        key = (it["id"], tuple(round(v) for v in it["bbox"]))
        if key not in seen:
            seen.add(key)
            out.append(it)
    return out[:limit]


def compare_sheet(source: Path, render: Path, spec: dict, report: dict, out: Path, limit: int = 8) -> int:
    dpr = float(spec["meta"].get("dpr", 1))
    src, ren = Image.open(source).convert("RGB"), Image.open(render).convert("RGB")
    items = worst_items(report, spec, limit)
    if not items:
        return 0
    tiles = []
    for it in items:
        a = crop(src, it["bbox"], dpr, 6, 300, 200)
        b = crop(ren, it["bbox"], dpr, 6, 300, 200)
        tiles.append(labelled([a, b], f"{it['id']}   source | render", it["note"]))
    grid(tiles, cols=2).save(out, optimize=True)
    return len(items)


# ---- OCR review ------------------------------------------------------------------------------

def ocr_sheets(source: Path, spec: dict, out: Path, per_sheet: int = 48) -> list[Path]:
    dpr = float(spec["meta"].get("dpr", 1))
    src = Image.open(source).convert("RGB")
    runs = [dict(t, id=t.get("id") or f"#{i}") for i, t in enumerate(spec.get("text", [])) if t.get("bbox")]
    runs.sort(key=lambda t: (round(t["bbox"][1] / 8), t["bbox"][0]))     # reading order
    paths = []
    for k in range(0, len(runs), per_sheet):
        tiles = [labelled([crop(src, t["bbox"], dpr, 2, 420, 46)], t["id"] + ("  (verify)" if t.get("verify") else ""))
                 for t in runs[k:k + per_sheet]]
        p = out if k == 0 else out.with_name(f"{out.stem}_{k // per_sheet + 1}{out.suffix}")
        grid(tiles, cols=3).save(p, optimize=True)
        paths.append(p)
    return paths


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("compare")
    c.add_argument("source", type=Path)
    c.add_argument("render", type=Path)
    c.add_argument("--spec", type=Path, required=True)
    c.add_argument("--report", type=Path, required=True)
    c.add_argument("--out", type=Path, required=True)
    c.add_argument("--max", type=int, default=8)
    o = sub.add_parser("ocr")
    o.add_argument("source", type=Path)
    o.add_argument("--spec", type=Path, required=True)
    o.add_argument("--out", type=Path, required=True)
    o.add_argument("--max", type=int, default=48, help="runs per sheet")
    args = ap.parse_args(argv)
    try:
        spec = json.loads(args.spec.read_text(encoding="utf-8"))
        if args.cmd == "compare":
            n = compare_sheet(args.source, args.render, spec, json.loads(args.report.read_text(encoding="utf-8")),
                              args.out, args.max)
            print(f"{args.out}: {n} items" if n else "nothing to show")
        else:
            paths = ocr_sheets(args.source, spec, args.out, args.max)
            print(", ".join(str(p) for p in paths) or "no text runs")
    except (OSError, KeyError, ValueError) as e:
        print(f"[error] {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
