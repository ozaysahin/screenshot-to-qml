#!/usr/bin/env python3
"""Validate a design-spec.json: schema plus consistency checks.

Usage:
  python validate_spec.py design-spec.json [--strict]

Errors (exit 1):   schema violations, duplicate node ids, unknown parent ids,
                   model counts that do not match the children present
Warnings:          child box outside its parent (> 2 px), box outside the canvas,
                   solid fills not close to any color token (ΔE2000 > 1.5),
                   draft markers left (meta.draft, text.verify, typeScale family "?"),
                   values with conf < 0.7 (listed for the README)
--strict turns warnings into errors.

Exit codes: 0 valid, 1 invalid, 2 could not run.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

SCHEMA = Path(__file__).resolve().parent.parent / "assets" / "schema" / "design-spec.schema.json"


def delta_e(h1: str, h2: str) -> float:
    import numpy as np
    from skimage.color import deltaE_ciede2000, rgb2lab
    a = np.array([[int(h[i:i + 2], 16) for i in (1, 3, 5)] for h in (h1, h2)], float) / 255
    lab = rgb2lab(a.reshape(-1, 1, 3)).reshape(-1, 3)
    return float(deltaE_ciede2000(lab[0], lab[1]))


def inside(child, parent, tol=2.0) -> bool:
    cx, cy, cw, ch = child
    px, py, pw, ph = parent
    return cx >= px - tol and cy >= py - tol and cx + cw <= px + pw + tol and cy + ch <= py + ph + tol


def validate(spec: dict) -> tuple[list[str], list[str], list[str]]:
    errors, warnings, low_conf = [], [], []
    try:
        import jsonschema
        schema = json.loads(SCHEMA.read_text())
        for e in sorted(jsonschema.Draft202012Validator(schema).iter_errors(spec), key=lambda e: list(e.path)):
            errors.append(f"schema: {'/'.join(map(str, e.path)) or '(root)'}: {e.message}")
    except ImportError:
        warnings.append("jsonschema not installed; schema not checked")
    if errors:
        return errors, warnings, low_conf

    W, H = spec["meta"]["designSize"]
    nodes = spec.get("nodes", [])
    ids = [n["id"] for n in nodes]
    for dup in sorted({i for i in ids if ids.count(i) > 1}):
        errors.append(f"duplicate node id '{dup}'")
    by_id = {n["id"]: n for n in nodes}
    token_hex = [t["hex"] for t in spec["tokens"].get("color", {}).values() if t.get("alpha", 1) >= 0.999]

    for n in nodes:
        p = n.get("parent")
        if p and p not in by_id:
            errors.append(f"node '{n['id']}': parent '{p}' does not exist")
        elif p and not inside(n["bbox"], by_id[p]["bbox"]):
            warnings.append(f"node '{n['id']}' extends outside its parent '{p}'")
        x, y, w, h = n["bbox"]
        if x < -1 or y < -1 or x + w > W + 1 or y + h > H + 1:
            warnings.append(f"node '{n['id']}' extends outside the {W}x{H} canvas (fine if clipped on purpose)")
        fill = n.get("style", {}).get("fill")
        if isinstance(fill, dict) and fill.get("alpha", 1) >= 0.999 and token_hex:
            best = min(delta_e(fill["hex"], t) for t in token_hex)
            if best > 1.5:
                warnings.append(f"node '{n['id']}' fill {fill['hex']} is not a color token (closest ΔE {best:.1f})")
        if "model" in n:
            item = n["model"].get("itemId")
            if item:
                kids = [m for m in nodes if m.get("parent") == n["id"] and re.fullmatch(rf"{re.escape(item)}(\[\d+\])?", m["id"])]
                if kids and len(kids) != n["model"]["count"]:
                    errors.append(f"node '{n['id']}': model count {n['model']['count']} but {len(kids)} '{item}' children")
        if n.get("conf", 1) < 0.7:
            low_conf.append(f"node {n['id']} (conf {n['conf']})")

    for name, t in spec["tokens"].get("color", {}).items():
        if t.get("conf", 1) < 0.7:
            low_conf.append(f"color {name} {t['hex']} (conf {t['conf']}, {t.get('src', '?')})")
        if re.match(r"on[A-Z]", name):
            errors.append(f"color token '{name}': names starting with 'on' + capital are QML signal handlers; use e.g. '{name[2].lower() + name[3:]}Ink'")
    if spec["meta"].get("draft"):
        warnings.append("meta.draft is still true (remove it after reviewing the analysis)")
    unverified = [t.get("id", t["string"][:20]) for t in spec.get("text", []) if t.get("verify")]
    if unverified:
        warnings.append(f"{len(unverified)} text runs still marked verify=true: {unverified[:8]}")
    if any(ts.get("family") == "?" for ts in spec["tokens"].get("typeScale", [])):
        warnings.append("typeScale has unknown families ('?')")
    for t in spec.get("text", []):
        if t.get("ocrConf", 100) < 70:
            low_conf.append(f"text '{t['string'][:30]}' (OCR conf {t['ocrConf']})")
    return errors, warnings, low_conf


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("spec", type=Path)
    ap.add_argument("--strict", action="store_true")
    args = ap.parse_args(argv)
    try:
        spec = json.loads(args.spec.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        print(f"[error] cannot read {args.spec}: {exc}", file=sys.stderr)
        return 2
    errors, warnings, low = validate(spec)
    for e in errors:
        print(f"ERROR   {e}")
    for w in warnings:
        print(f"WARNING {w}")
    if low:
        print(f"LOW CONFIDENCE (list in the README): {len(low)}")
        for item in low[:15]:
            print(f"        {item}")
    bad = errors or (args.strict and warnings)
    print("INVALID" if bad else "VALID", f"({len(errors)} errors, {len(warnings)} warnings)")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
