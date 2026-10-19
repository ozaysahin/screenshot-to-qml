#!/usr/bin/env python3
"""Measure how well the analysis scripts recover each eval case's ground truth.

Usage:
  python evals/score_analysis.py [--cases 01,03] [--out evals/analysis-results] [--verbose]

Per case (input.png at the case DPR vs golden-spec.json):
  palette   recall of solid (alpha = 1) colors used in the design, within ΔE2000 <= 2
  surfaces  recall of solid-fill nodes >= 16x16 matched by a detected box with IoU >= 0.85,
            and the mean box error of the matches
  text      share of golden text runs recovered exactly (normalized), character error rate,
            and mean |font px| error
Exit criterion for v0.4: pooled palette recall >= 0.90.
"""
from __future__ import annotations

import argparse
import json
import sys
import unicodedata
from pathlib import Path

import numpy as np
from skimage.color import deltaE_ciede2000, rgb2lab

ROOT = Path(__file__).resolve().parent.parent
CASES = ROOT / "evals" / "cases"
sys.path.insert(0, str(ROOT / "skills" / "screenshot-to-qml" / "scripts"))

import geometry  # noqa: E402
import palette  # noqa: E402
import text_ocr  # noqa: E402


def lab_of(hexes):
    rgb = np.array([[int(h[i:i + 2], 16) for i in (1, 3, 5)] for h in hexes], dtype=np.float64) / 255.0
    return rgb2lab(rgb.reshape(-1, 1, 3)).reshape(-1, 3)


def palette_score(golden, pal):
    want = sorted({c["color"]["hex"] for c in golden["colorsUsed"] if c["color"].get("alpha", 1) >= 0.999})
    got = [c["hex"] for c in pal["colors"]]
    if not want or not got:
        return {"recall": 0.0, "missing": want}
    lw, lg = lab_of(want), lab_of(got)
    missing, hits = [], 0
    for i, h in enumerate(want):
        d = deltaE_ciede2000(np.repeat(lw[i][None], len(lg), 0), lg).min()
        if d <= 2.0:
            hits += 1
        else:
            missing.append(f"{h} (ΔE {d:.1f})")
    return {"recall": round(hits / len(want), 3), "n": len(want), "found": hits, "missing": missing, "paletteSize": len(got)}


def iou(a, b):
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    ix = max(0.0, min(ax + aw, bx + bw) - max(ax, bx))
    iy = max(0.0, min(ay + ah, by + bh) - max(ay, by))
    inter = ix * iy
    return inter / (aw * ah + bw * bh - inter) if inter else 0.0


def surface_score(golden, nodes):
    want = [n for n in golden["nodes"] if isinstance(n.get("style", {}).get("fill"), dict)
            and n["style"]["fill"].get("alpha", 1) >= 0.999 and n["bbox"][2] >= 16 and n["bbox"][3] >= 16]
    got = [n["bbox"] for n in nodes]
    W, H = golden["meta"]["designSize"]
    hits, errs, missing = 0, [], []
    for n in want:
        x, y, w, h = n["bbox"]            # clip to the canvas (items can overflow the screen edge)
        x0, y0, x1, y1 = max(0, x), max(0, y), min(W, x + w), min(H, y + h)
        box = [x0, y0, x1 - x0, y1 - y0]
        best = max((iou(box, g), g) for g in got) if got else (0, None)
        if best[0] >= 0.85:
            hits += 1
            errs.append(float(np.mean(np.abs(np.array(box) - np.array(best[1])))))
        else:
            missing.append(n["id"])
    return {"recall": round(hits / len(want), 3) if want else 1.0, "n": len(want), "found": hits,
            "meanBoxErrPx": round(float(np.mean(errs)), 2) if errs else None, "missing": missing[:12],
            "detected": len(got)}


def norm(s):
    return " ".join(unicodedata.normalize("NFC", s).split())


def cer(a, b):
    import difflib
    sm = difflib.SequenceMatcher(None, a, b)
    return 1 - sm.ratio()


def text_score(golden, runs):
    want = golden["text"]
    exact, cers, px_err, missing = 0, [], [], []
    for t in want:
        gx, gy, gw, gh = t["bbox"]
        cx, cy = gx + gw / 2, gy + gh / 2
        cand = [r for r in runs if r["bbox"][0] - 2 <= cx <= r["bbox"][0] + r["bbox"][2] + 2
                and r["bbox"][1] - 2 <= cy <= r["bbox"][1] + r["bbox"][3] + 2]
        g = norm(t["string"])
        if not cand:
            missing.append(g)
            cers.append(1.0)
            continue
        best = min(cand, key=lambda r: cer(g, norm(r["string"])) if g not in norm(r["string"]) else 0)
        s = norm(best["string"])
        if s == g or g in s.split("  "):
            exact += 1
            cers.append(0.0)
        elif g in s:
            exact += 1
            cers.append(0.0)
        else:
            cers.append(cer(g, s))
        if best.get("font", {}).get("px") and t.get("font", {}).get("px"):
            px_err.append(abs(best["font"]["px"] - t["font"]["px"]))
    return {"exact": round(exact / len(want), 3), "n": len(want), "cer": round(float(np.mean(cers)), 3),
            "pxMAE": round(float(np.mean(px_err)), 2) if px_err else None, "missing": missing[:10]}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cases", default="")
    ap.add_argument("--out", type=Path, default=ROOT / "evals" / "analysis-results")
    ap.add_argument("--skip", default="", help="comma list of: palette,surfaces,text")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args(argv)
    prefixes = [c for c in args.cases.split(",") if c]
    skip = set(args.skip.split(","))
    rows = []
    for case in sorted(CASES.iterdir()):
        if prefixes and not case.name.startswith(tuple(prefixes)):
            continue
        golden = json.loads((case / "golden-spec.json").read_text())
        dpr = golden["meta"]["dpr"]
        img = palette.load(str(case / "input.png"))
        row = {"case": case.name}
        pal = palette.extract(img, dpr, 12, 1.2)
        if "palette" not in skip:
            row["palette"] = palette_score(golden, pal)
        if "surfaces" not in skip:
            row["surfaces"] = surface_score(golden, geometry.detect(img, dpr, pal)["nodes"])
        if "text" not in skip:
            row["text"] = text_score(golden, text_ocr.recognize(img, dpr, pal=pal)["runs"])
        rows.append(row)
        msg = [case.name.ljust(22)]
        if "palette" in row:
            msg.append(f"palette {row['palette']['found']}/{row['palette']['n']}")
        if "surfaces" in row:
            msg.append(f"surfaces {row['surfaces']['found']}/{row['surfaces']['n']} err {row['surfaces']['meanBoxErrPx']}")
        if "text" in row:
            msg.append(f"text exact {row['text']['exact']} cer {row['text']['cer']} pxMAE {row['text']['pxMAE']}")
        print("  ".join(msg))
        if args.verbose:
            for k in ("palette", "surfaces", "text"):
                if k in row and row[k].get("missing"):
                    print(f"     {k} missing: {row[k]['missing']}")

    def pooled(key, num, den):
        rs = [r[key] for r in rows if key in r]
        n = sum(r[den] for r in rs)
        return round(sum(r[num] for r in rs) / n, 3) if n else None

    summary = {"paletteRecall": pooled("palette", "found", "n"), "surfaceRecall": pooled("surfaces", "found", "n")}
    if any("text" in r for r in rows):
        ts = [r["text"] for r in rows if "text" in r]
        summary["textExact"] = round(sum(t["exact"] * t["n"] for t in ts) / sum(t["n"] for t in ts), 3)
        summary["textCER"] = round(float(np.mean([t["cer"] for t in ts])), 3)
        pxs = [t["pxMAE"] for t in ts if t["pxMAE"] is not None]
        summary["fontPxMAE"] = round(float(np.mean(pxs)), 2) if pxs else None
    print("pooled:", json.dumps(summary))
    args.out.with_suffix(".json").write_text(json.dumps({"summary": summary, "cases": rows}, indent=1, ensure_ascii=False))
    lines = ["| Case | Palette recall | Surface recall (IoU≥0.85) | Box err px | Text exact | CER | Font px MAE |",
             "| --- | --- | --- | --- | --- | --- | --- |"]
    for r in rows:
        p, s, t = r.get("palette", {}), r.get("surfaces", {}), r.get("text", {})
        lines.append(f"| {r['case']} | {p.get('found', '—')}/{p.get('n', '—')} | {s.get('found', '—')}/{s.get('n', '—')} | "
                     f"{s.get('meanBoxErrPx', '—')} | {t.get('exact', '—')} | {t.get('cer', '—')} | {t.get('pxMAE', '—')} |")
    lines.append(f"| **pooled** | **{summary['paletteRecall']}** | **{summary['surfaceRecall']}** | | "
                 f"**{summary.get('textExact', '—')}** | **{summary.get('textCER', '—')}** | **{summary.get('fontPxMAE', '—')}** |")
    args.out.with_suffix(".md").write_text("\n".join(lines) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
