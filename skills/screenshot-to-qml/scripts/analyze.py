#!/usr/bin/env python3
"""Draft a design-spec.json from a screenshot (palette + surfaces + OCR) and draw an overlay.

Usage:
  python analyze.py IMG [--dpr 2] [--out-dir analysis] [--lang tur+eng]
                    [--profile desktop] [--layout canvas|responsive] [--no-ocr] [--match]

Writes to --out-dir:
  palette.json  geometry.json  text.json   raw results of the three analyzers
  design-spec.draft.json                    schema-valid draft (validate_spec.py checks it)
  overlay.png                               surfaces (cyan, s#), text runs (magenta, t#),
                                            icon candidates (yellow, i#) with their ids
  ocr_sheet.png (+ _2, _3 …)                every text run's crop labelled with its id, to check
                                            all OCR strings in one look (spec_view.py --text lists them)
  with --match: match.py on the draft (fonts, icons, shadows, gradients written into it,
  design-spec.draft.match-report.json). A first look only: run match.py again on the
  corrected spec, since the matchers measure inside the draft's boxes.

The draft is a starting point, not the answer. Next steps for the agent:
  1. open overlay.png and ocr_sheet.png once; compare `spec_view.py draft --text` with the
     sheet and fix the strings, delete false surfaces, add missed ones, mark roles
  2. rename color tokens by role (bg, surface, text, textMuted, accent …)
  3. python match.py IMG design-spec.json --out design-spec.json (fonts, icons, shadows,
     gradients); confirm what its report lists; add models for repeats
  4. python validate_spec.py design-spec.json

Exit codes: 0 ok, 2 error.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

import cv2
import geometry
import numpy as np
import palette as palette_mod

MIN_TOKEN_COVERAGE = 0.001   # unused colors below this share of the frame are left out


def contains(box, x, y, tol=1.0) -> bool:
    bx, by, bw, bh = box
    return bx - tol <= x <= bx + bw + tol and by - tol <= y <= by + bh + tol


def owner_of(nodes, box):
    cx, cy = box[0] + box[2] / 2, box[1] + box[3] / 2
    best = None
    for n in nodes:
        if contains(n["bbox"], cx, cy):
            if best is None or n["bbox"][2] * n["bbox"][3] < best["bbox"][2] * best["bbox"][3]:
                best = n
    return best["id"] if best else None


def spacing_values(nodes) -> list[int]:
    by_id = {n["id"]: n for n in nodes}
    vals = Counter()
    for n in nodes:
        p = by_id.get(n.get("parent"))
        if not p or p.get("role") == "background":
            continue
        x, y, w, h = n["bbox"]
        px, py, pw, ph = p["bbox"]
        for v in (x - px, y - py, px + pw - (x + w), py + ph - (y + h)):
            if 2 <= v <= 64:
                vals[int(round(v))] += 1
    sibs: dict = {}
    for n in nodes:
        sibs.setdefault(n.get("parent"), []).append(n["bbox"])
    for boxes in sibs.values():
        boxes = sorted(boxes)
        for a, b in zip(boxes, boxes[1:], strict=False):
            gap = b[0] - (a[0] + a[2])
            if 2 <= gap <= 64 and abs(a[1] - b[1]) < 2:
                vals[int(round(gap))] += 1
    return sorted(v for v, c in vals.items() if c >= 2)


def build_spec(img_path: Path, dpr: float, pal: dict, geo: dict, txt: dict | None, args) -> dict:
    W, H = geo["designSize"]
    used = {nd["style"]["fill"]["hex"] for nd in geo["nodes"]}
    used |= {nd["style"]["border"]["color"]["hex"] for nd in geo["nodes"] if nd["style"].get("border")}
    used |= {g[k] for g in geo.get("gradients", []) for k in ("from", "to")}
    colors = {}
    name_of = {}
    n = 0
    for c in pal["colors"]:
        if c["hex"] != pal["background"] and c["hex"] not in used and c["coverage"] < MIN_TOKEN_COVERAGE:
            continue
        if c["hex"] == pal["background"]:
            name = "bg"
        else:
            n += 1
            name = f"c{n}"
        name_of[c["hex"]] = name
        conf = 0.95 if c["flat"] else 0.6
        colors[name] = {"hex": c["hex"], "alpha": 1.0, "src": "measured", "conf": conf,
                        "coverage": c["coverage"], "samples": c["samples"][:2]}
    t = 0
    for r in (txt or {}).get("runs", []):
        if r.get("color") and r["color"] not in name_of:
            t += 1
            name_of[r["color"]] = f"text{t}"
            colors[f"text{t}"] = {"hex": r["color"], "alpha": 1.0, "src": "inferred", "conf": 0.6}

    radii = sorted({round(nd["style"].get("radius", 0)) for nd in geo["nodes"] if nd["style"].get("radius", 0) >= 1})
    nodes = []
    for nd in geo["nodes"]:
        nd = dict(nd)
        nd["fillToken"] = name_of.get(nd["style"]["fill"]["hex"])
        nodes.append(nd)
    for g in geo.get("gradients", []):
        angle = 180 if g["direction"] == "vertical" else 90
        nodes.append({"id": g["id"], "role": "Gradient?", "parent": owner_of(nodes, g["bbox"]), "bbox": g["bbox"],
                      "style": {"fillImage": f"linear-gradient({angle}deg, {g['from']} 0%, {g['to']} 100%)"},
                      "src": "inferred", "conf": 0.6})
    text = []
    sizes = Counter()
    for i, r in enumerate((txt or {}).get("runs", [])):
        entry = {"id": f"t{i}", "string": r["string"], "owner": owner_of(nodes, r["bbox"]), "bbox": r["bbox"],
                 "font": {"px": r["font"]["px"]} if r["font"].get("px") else {}, "ocrConf": r["conf"],
                 "verify": r["conf"] < 90 or any(ch.isdigit() for ch in r["string"])}
        if r.get("color"):
            entry["color"] = {"hex": r["color"], "alpha": 1.0}
        text.append(entry)
        if r["font"].get("px"):
            sizes[r["font"]["px"]] += 1
    icons = [dict(ic, id=f"i{k}", owner=owner_of(nodes, ic["bbox"])) for k, ic in enumerate((txt or {}).get("icons", []))]
    for ic in icons:
        if ic.get("color"):
            ic["color"] = {"hex": ic["color"], "alpha": 1.0}
        else:
            ic.pop("color", None)
        ic.pop("kind", None)

    return {
        "meta": {"source": img_path.name, "designSize": [W, H], "dpr": dpr,
                 "captureSize": [round(W * dpr), round(H * dpr)], "profile": args.profile,
                 "mode": "production", "target": "pyside6", "layout": args.layout, "minQt": "6.8",
                 "draft": True, "fonts": []},
        "tokens": {
            "color": colors,
            "space": {str(i + 1): v for i, v in enumerate(spacing_values(nodes))},
            "radius": {f"r{v}": v for v in radii},
            "typeScale": [{"family": "?", "px": px, "weight": 400, "count": cnt} for px, cnt in sorted(sizes.items(), reverse=True)],
        },
        "nodes": nodes,
        "text": text,
        "icons": icons,
        "hints": {"repeats": geo.get("repeats", []),
                  "todo": ["verify every text string (entries with verify=true first)",
                           "rename color tokens by role",
                           "set roles for surfaces; add missed surfaces; delete false ones",
                           "run match.py (fonts, icons, shadows, gradients) and confirm its report",
                           "add models for repeats"]},
        "states": {},
    }


def draw_overlay(img: np.ndarray, dpr: float, spec: dict, path: Path) -> None:
    vis = cv2.cvtColor(img, cv2.COLOR_RGB2BGR).copy()
    vis = cv2.addWeighted(vis, 0.55, np.zeros_like(vis), 0.45, 0)
    th = max(1, int(round(dpr)))
    fs = 0.38 * dpr

    def rect(box, color, label):
        x, y, w, h = (int(round(v * dpr)) for v in box)
        cv2.rectangle(vis, (x, y), (x + w - 1, y + h - 1), color, th)
        cv2.putText(vis, label, (x + 2, y + int(11 * dpr)), cv2.FONT_HERSHEY_SIMPLEX, fs, color, th, cv2.LINE_AA)

    for nd in spec["nodes"]:
        if nd.get("role") != "background":
            rect(nd["bbox"], (255, 220, 0), nd["id"])
    for t in spec["text"]:
        rect(t["bbox"], (255, 0, 255), t["id"])
    for ic in spec["icons"]:
        rect(ic["bbox"], (0, 230, 255), ic["id"])
    cv2.imwrite(str(path), vis)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("image", type=Path)
    ap.add_argument("--dpr", type=float, default=1.0)
    ap.add_argument("--out-dir", type=Path, default=Path("analysis"))
    ap.add_argument("--lang", default="tur+eng")
    ap.add_argument("--profile", choices=["desktop", "embedded-gpu", "embedded-sw"], default="desktop")
    ap.add_argument("--layout", choices=["canvas", "responsive"], default="responsive")
    ap.add_argument("--no-ocr", action="store_true", help="skip text recognition (no tesseract)")
    ap.add_argument("--match", action="store_true", help="also run match.py on the draft (first look)")
    args = ap.parse_args(argv)

    img = palette_mod.load(str(args.image))
    out = args.out_dir
    out.mkdir(parents=True, exist_ok=True)
    pal = palette_mod.extract(img, args.dpr, 12, 1.2)
    (out / "palette.json").write_text(json.dumps(pal, indent=1))
    geo = geometry.detect(img, args.dpr, pal)
    (out / "geometry.json").write_text(json.dumps(geo, indent=1))
    txt = None
    if not args.no_ocr:
        import text_ocr
        txt = text_ocr.recognize(img, args.dpr, args.lang, 40, pal)
        (out / "text.json").write_text(json.dumps(txt, indent=1, ensure_ascii=False))
    spec = build_spec(args.image, args.dpr, pal, geo, txt, args)
    (out / "design-spec.draft.json").write_text(json.dumps(spec, indent=1, ensure_ascii=False))
    draw_overlay(img, args.dpr, spec, out / "overlay.png")
    sheets = []
    if spec["text"]:
        import sheet
        sheets = sheet.ocr_sheets(args.image, spec, out / "ocr_sheet.png")
    if args.match:
        import match
        draft = out / "design-spec.draft.json"
        match.main([str(args.image), str(draft), "--out", str(draft), "--dpr", str(args.dpr),
                    "--report", str(out / "design-spec.draft.match-report.json")])
        spec = json.loads(draft.read_text())
    simple = len(spec["text"]) <= 70 and len(spec["nodes"]) <= 60
    print(f"suggested effort: {'quick' if simple else 'standard'} ({len(spec['text'])} text runs, "
          f"{len(spec['nodes'])} surfaces; quick ≤ 70 and ≤ 60)")
    print(f"design {spec['meta']['designSize'][0]}x{spec['meta']['designSize'][1]} @{args.dpr:g}x: "
          f"{len(spec['tokens']['color'])} colors, {len(spec['nodes'])} surfaces, {len(spec['text'])} text runs "
          f"({sum(t['verify'] for t in spec['text'])} to verify), {len(spec['icons'])} icon candidates "
          f"-> {out}/design-spec.draft.json, overlay.png"
          + (f", {', '.join(p.name for p in sheets)}" if sheets else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
