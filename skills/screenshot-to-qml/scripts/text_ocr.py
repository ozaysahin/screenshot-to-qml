#!/usr/bin/env python3
"""Read the text of a UI screenshot: strings, boxes, font size and color.

Usage:
  python text_ocr.py IMG [--dpr 2] [--lang tur+eng] [--palette palette.json] [--out text.json]

Needs the `tesseract` binary with language data (Debian/Ubuntu: tesseract-ocr-tur).

Pipeline:
  1. upscale so 1 design px is ~2 px, find words (psm 11, sparse text) on a local-contrast map
     and on the gray image in both polarities
  2. words without letters/digits become icon candidates (icon fonts read as ©, @, & …)
  3. words are grouped into runs by baseline, height and gap
  4. every run is re-read as a single line (psm 7) on a polarity-normalized crop, which
     restores spaces and punctuation the sparse pass drops
  5. the ink box is measured from pixels; font px comes from the ink height and the
     letters present (caps, ascenders, descenders, Turkish accents)
  6. the text color is the most contrasting ink, snapped to the palette when one is close

Output: runs [{string, bbox, conf, font.px, color}] and icons [{bbox, color, guess}] in
design px. OCR mixes up ı/i, 0/O/6, l/1 and middle dots in small or monospaced text —
verify every string against the image before building.

Exit codes: 0 ok, 2 error (tesseract missing).
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys

import cv2
import numpy as np
import palette as palette_mod
from skimage.color import deltaE_ciede2000, rgb2lab

TARGET_SCALE = 2.0      # detection pass: OCR px per design px (runs are re-read at ~44 px ink height)
CAP = 0.72              # cap height / font px (typical UI sans; 0.69–0.75)
ASC = 0.74              # ascender (b d f h k l t) / font px
XH = 0.52               # x-height / font px
ACCENT_TOP = 0.90       # top of Ğ Ü Ö İ marks / font px
DESC = 0.21             # descender depth / font px
SNAP_DE = 8.0           # snap text color to a palette color within this CIEDE2000
UPPER_OR_DIGIT = set("ABCDEFGHIJKLMNOPQRSTUVWXYZÇŞ0123456789%#&@$?!")
ASCENDERS = set("bdfhklt")
TALL_MARKS = set("ĞÜÖİÂÊÎÔÛÁÉÍÓÚ")
DESCENDERS = set("gjpqyçşÇŞ,;")


def estimate_px(text: str, ink_h: float) -> float | None:
    chars = set(text)
    if not chars or ink_h <= 0:
        return None
    if chars & TALL_MARKS:
        top = ACCENT_TOP
    elif chars & ASCENDERS:
        top = ASC
    elif chars & UPPER_OR_DIGIT or chars & set("iıjüöğ/()[]|"):
        top = CAP
    else:
        top = XH
    bottom = DESC if chars & DESCENDERS else 0.0
    return ink_h / (top + bottom)


def tesseract_words(gray: np.ndarray, lang: str, psm: int, min_conf: float) -> list[dict]:
    import pytesseract
    cfg = f"--psm {psm} --oem 1 -c preserve_interword_spaces=1"
    data = pytesseract.image_to_data(gray, lang=lang, config=cfg, output_type=pytesseract.Output.DICT)
    words = []
    for i, txt in enumerate(data["text"]):
        txt = (txt or "").strip()
        conf = float(data["conf"][i])
        if txt and conf >= min_conf:
            words.append({"text": txt, "conf": conf,
                          "box": [data["left"][i], data["top"][i], data["width"][i], data["height"][i]]})
    return words


def overlap(a, b) -> float:
    ix = max(0, min(a[0] + a[2], b[0] + b[2]) - max(a[0], b[0]))
    iy = max(0, min(a[1] + a[3], b[1] + b[3]) - max(a[1], b[1]))
    return ix * iy / max(1, min(a[2] * a[3], b[2] * b[3]))


def merge_passes(*passes):
    words = []
    for w in sorted((w for p in passes for w in p), key=lambda w: -w["conf"]):
        if all(overlap(w["box"], k["box"]) < 0.4 for k in words):
            words.append(w)
    return words


def split_icons(words):
    text, icons = [], []
    heights = sorted(w["box"][3] for w in words) or [1]
    typical = heights[len(heights) // 2]
    for w in words:
        alnum = [c for c in w["text"] if c.isalnum()]
        bw, bh = w["box"][2], w["box"][3]
        square = 0.6 < bw / max(1, bh) < 1.6
        if not alnum and square:
            icons.append(w)
        elif not alnum:
            continue                                  # rules, dashes, chart strokes
        elif len(w["text"]) == 1 and square and w["conf"] < 90 and not w["text"].isdigit():
            icons.append(w)                           # a glyph read as a letter
        elif bh > 4 * typical and len(w["text"]) <= 3:
            continue                                  # tall garbage (bars, gauges)
        else:
            text.append(w)
    return text, icons


def group_runs(words):
    runs = []
    for w in sorted(words, key=lambda w: w["box"][0]):
        x, y, bw, bh = w["box"]
        cy = y + bh / 2
        target = None
        for r in runs:
            rx, ry, rw, rh = r["box"]
            h = min(bh, r["h"])
            if max(bh, r["h"]) > 1.8 * h:
                continue
            gap = x - (rx + rw)
            if abs(cy - r["cy"]) < 0.4 * h and -0.2 * h < gap < 1.3 * h:
                target = r
                break
        if target is None:
            runs.append({"words": [w], "box": [x, y, bw, bh], "cy": cy, "h": bh})
        else:
            target["words"].append(w)
            rx, ry, rw, rh = target["box"]
            x0, y0 = min(rx, x), min(ry, y)
            x1, y1 = max(rx + rw, x + bw), max(ry + rh, y + bh)
            target["box"] = [x0, y0, x1 - x0, y1 - y0]
            target["h"] = max(target["h"], bh)
    return runs


def reread_line(rgb: np.ndarray, box, lang: str):
    """Re-read one run as a single line on a local contrast map (ink vs this run's own
    background), resized so the ink is ~44 px tall — the size tesseract reads best."""
    x, y, w, h = box
    pad = int(0.5 * h) + 4
    H, W = rgb.shape[:2]
    x0, y0, x1, y1 = max(0, x - pad), max(0, y - pad), min(W, x + w + pad), min(H, y + h + pad)
    crop = rgb[y0:y1, x0:x1].astype(np.int16)
    if crop.size == 0:
        return None, 0.0
    ring = np.concatenate([crop[0], crop[-1], crop[:, 0], crop[:, -1]])
    dist = np.abs(crop - np.median(ring, axis=0)).max(axis=2).astype(np.float32)
    if dist.max() < 20:
        return None, 0.0
    norm = (255 - np.clip(dist * (255.0 / dist.max()) * 1.4, 0, 255)).astype(np.uint8)
    f = float(np.clip(44.0 / max(1, h), 0.35, 3.0))
    if abs(f - 1) > 0.05:
        norm = cv2.resize(norm, None, fx=f, fy=f, interpolation=cv2.INTER_AREA if f < 1 else cv2.INTER_CUBIC)
    norm = cv2.copyMakeBorder(norm, 12, 12, 12, 12, cv2.BORDER_CONSTANT, value=255)
    words = tesseract_words(norm, lang, 7, 0)
    if not words:
        return None, 0.0
    return " ".join(w["text"] for w in words), float(np.mean([w["conf"] for w in words]))


def ink_box(rgb: np.ndarray, box):
    """Tight ink box inside `box` (same pixel space as rgb), by contrast to the local background."""
    x, y, w, h = (int(round(v)) for v in box)
    pad = max(2, int(0.12 * h))        # small: stay inside chips/buttons and off neighbouring lines
    H, W = rgb.shape[:2]
    x0, y0, x1, y1 = max(0, x - pad), max(0, y - pad), min(W, x + w + pad), min(H, y + h + pad)
    reg = rgb[y0:y1, x0:x1].astype(np.int16)
    if reg.size == 0:
        return None
    ring = np.concatenate([reg[0], reg[-1], reg[:, 0], reg[:, -1]])
    bg = np.median(ring, axis=0)
    dist = np.abs(reg - bg).sum(axis=2)
    if dist.max() < 30:
        return None
    ink = dist >= 0.5 * dist.max()
    rows, cols = np.nonzero(ink.any(axis=1))[0], np.nonzero(ink.any(axis=0))[0]
    return [x0 + cols[0], y0 + rows[0], cols[-1] - cols[0] + 1, rows[-1] - rows[0] + 1], bg, reg, dist


def ink_color(reg, dist, pal_lab, pal_hex):
    far = reg[dist >= np.percentile(dist, 97)]
    c = np.median(far, axis=0)
    hexc = palette_mod.hexstr(c)
    if pal_lab is not None and len(pal_lab):
        lab = rgb2lab((c / 255.0).reshape(1, 1, 3)).reshape(3)
        d = deltaE_ciede2000(np.repeat(lab[None], len(pal_lab), 0), pal_lab)
        j = int(np.argmin(d))
        if d[j] <= SNAP_DE:
            return pal_hex[j], True
    return hexc, False


def text_map(rgb: np.ndarray, ksize: int) -> np.ndarray:
    """Dark-on-white rendering of 'ink vs local background', independent of polarity and of
    the surface color (white text on blue, dark text on yellow, gray on gray all come out dark)."""
    k = ksize if ksize % 2 else ksize + 1
    bg = cv2.medianBlur(rgb, k)
    diff = np.abs(rgb.astype(np.int16) - bg.astype(np.int16)).max(axis=2).astype(np.float32)
    return (255 - np.clip(diff * 2.2, 0, 255)).astype(np.uint8)


def recognize(img: np.ndarray, dpr: float, lang: str = "tur+eng", min_conf: float = 40, pal: dict | None = None) -> dict:
    if not shutil.which("tesseract"):
        raise SystemExit("[error] tesseract not found (install tesseract-ocr and tesseract-ocr-tur)")
    s = max(1.0, TARGET_SCALE / dpr)
    big = cv2.resize(img, None, fx=s, fy=s, interpolation=cv2.INTER_CUBIC) if s > 1 else img
    tmap = text_map(big, int(14 * s * dpr) | 1)
    gray = cv2.cvtColor(big, cv2.COLOR_RGB2GRAY)
    # three detection passes: local-contrast map (text on colored surfaces), and plain gray in
    # both polarities (large bold text, whose thick strokes the contrast map hollows out)
    words = merge_passes(tesseract_words(tmap, lang, 11, min_conf),
                         tesseract_words(gray, lang, 11, min_conf),
                         tesseract_words(255 - gray, lang, 11, min_conf))
    words, icon_words = split_icons(words)
    k = 1.0 / (s * dpr)                     # big px -> design px
    pal_hex = [c["hex"] for c in pal["colors"]] if pal else []
    pal_lab = (rgb2lab((np.array([[int(h[i:i + 2], 16) for i in (1, 3, 5)] for h in pal_hex], float) / 255).reshape(-1, 1, 3)).reshape(-1, 3)
               if pal_hex else None)

    runs = []
    for r in group_runs(words):
        joined = " ".join(w["text"] for w in sorted(r["words"], key=lambda w: w["box"][0]))
        conf = float(np.mean([w["conf"] for w in r["words"]]))
        again, again_conf = reread_line(big, r["box"], lang)
        if again and again_conf >= conf - 5 and len(again.replace(" ", "")) >= 0.6 * len(joined.replace(" ", "")):
            string, conf = again, again_conf
        else:
            string = joined
        measured = ink_box(big, r["box"])
        if measured:
            ib, _bg, reg, dist = measured
            box = [round(v * k, 2) for v in ib]
            color, snapped = ink_color(reg, dist, pal_lab, pal_hex)
        else:
            box = [round(v * k, 2) for v in r["box"]]
            color, snapped = None, False
        px = estimate_px(string, box[3])
        runs.append({"string": string, "bbox": box, "conf": round(conf, 1),
                     "font": {"px": int(round(px)) if px else None}, "color": color,
                     "colorSnapped": snapped, "src": "measured"})
    runs.sort(key=lambda t: (round(t["bbox"][1] / 8), t["bbox"][0]))

    icons = []
    for w in icon_words:
        measured = ink_box(big, w["box"])
        box = [round(v * k, 2) for v in (measured[0] if measured else w["box"])]
        color = ink_color(measured[2], measured[3], pal_lab, pal_hex)[0] if measured else None
        icons.append({"bbox": box, "color": color, "ocrGuess": w["text"], "match": None, "kind": None})
    return {"runs": runs, "icons": icons, "lang": lang, "scale": s}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("image")
    ap.add_argument("--dpr", type=float, default=1.0)
    ap.add_argument("--lang", default="tur+eng")
    ap.add_argument("--min-conf", type=float, default=40)
    ap.add_argument("--palette")
    ap.add_argument("--out")
    args = ap.parse_args(argv)
    pal = json.loads(open(args.palette).read()) if args.palette else None
    res = recognize(palette_mod.load(args.image), args.dpr, args.lang, args.min_conf, pal)
    text = json.dumps(res, indent=1, ensure_ascii=False)
    if args.out:
        with open(args.out, "w") as f:
            f.write(text)
        print(f"{len(res['runs'])} text runs, {len(res['icons'])} icon candidates -> {args.out}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
