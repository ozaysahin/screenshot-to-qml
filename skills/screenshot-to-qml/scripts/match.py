#!/usr/bin/env python3
"""Fill a design spec with measured fonts, icons, shadows and gradients.

Usage:
  python match.py IMG SPEC [--only fonts,icons,shadows,gradients] [--out SPEC_OUT]
                  [--report match-report.json] [--fonts-dir PROJECT/assets/fonts] [--max-runs 40]

Runs the four matchers on a (draft or edited) design-spec.json and writes the results into
a copy of it (--out, default SPEC with suffix .matched.json; pass --out SPEC to update in place):

  fonts      font_match: the screen's families (voted over the longest runs), then family,
             weight and px for every text run; meta.fonts and typeScale entries whose family
             is "?" are filled. --fonts-dir writes static TTFs of the used weights + license.
             Needs the font cache (python font_match.py fetch).
  icons      icon_match: icons[].match / score / strokeWidth (+ alternatives in the report).
             Below score 0.6 nothing is written; below 0.9 the match is listed to confirm.
             Needs the icon index (python icon_match.py fetch).
  shadows    shadow_fit (scene mode): style.shadow on painted nodes with a reliable shadow.
  gradients  gradient_fit: style.fillImage on painted nodes whose fill is a linear gradient.

Values written are measurements, not truth: the report (--report, default next to --out)
lists every value with its score and alternatives, and entries to check by eye. Existing
values in the spec are kept unless --overwrite. Exit codes: 0 ok, 1 some matcher was skipped
(missing cache), 2 error.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np

MIN_ICON_SCORE = 0.6         # below: no match written (on the eval set every top-1 below 0.6 was wrong)
CHECK_ICON_SCORE = 0.9       # below: written, but listed to confirm by eye (most wrong top-1s)
GRAD_MIN_AREA = 600          # design px²: smaller surfaces are left alone


def _fonts(img, dpr, spec, args, report) -> bool:
    import font_match
    import fontlib
    families = fontlib.available()
    if not families:
        report["skipped"].append("fonts: no candidate fonts in the cache — run: python font_match.py fetch")
        return False
    runs = [t for t in spec.get("text", []) if t.get("bbox") and t.get("string", "").strip()]
    if not runs:
        return True
    blind = [{k: v for k, v in t.items() if k != "font"} | ({"font": {"px": t["font"]["px"]}} if t.get("font", {}).get("px") else {})
             for t in font_match.pick_runs({"text": runs}, args.max_runs)]
    first = font_match.match(img, dpr, blind, families)
    chosen = [f["family"] for f in first["families"]]
    if not chosen:
        report["skipped"].append("fonts: no run could be measured")
        return True
    by_name = {m["family"]: m for m in families}
    screen = [by_name[f] for f in chosen if f in by_name]
    fits = font_match.assign(img, dpr, runs, screen)
    rows = []
    for t, f in zip(runs, fits, strict=True):
        if f is not None:
            px = (t.get("font") or {}).get("px") or f["px"]
            rows.append({"string": t["string"], "bbox": t["bbox"], "family": f["family"], "weight": f["weight"],
                         "px": px, "measuredPx": f["px"], "score": f["score"], "_t": t,
                         "short": len(t["string"].replace(" ", "")) < font_match.MIN_CHARS})

    def peers(px, family=None):
        return [r for r in rows if not r["short"] and abs(r["px"] - px) <= 1.0 and (family is None or r["family"] == family)]

    for r in rows:                   # 1–2 characters say little about weight: use same-size runs
        if r["short"]:
            same = peers(r["px"])
            if same:
                (r["family"], r["weight"]), _ = Counter((q["family"], q["weight"]) for q in same).most_common(1)[0]
                r["fromPeers"] = True
        t = r.pop("_t")
        font = t.setdefault("font", {})
        if args.overwrite or not font.get("family") or font.get("family") == "?":
            font["family"], font["weight"] = r["family"], r["weight"]
            font.setdefault("px", r["measuredPx"])
    # typeScale: majority family/weight of the runs within 1 px of each size
    for ts in spec.get("tokens", {}).get("typeScale", []):
        size = ts.get("px", 0)
        got = (peers(size) or [r for r in rows if abs(r["px"] - size) <= 1.0]
               or [r for r in rows if not r["short"] and abs(r["px"] - size) <= 0.12 * size])   # measured px are ±10 %
        if got and (args.overwrite or ts.get("family") in (None, "?")):
            (fam, wt), _ = Counter((r["family"], r["weight"]) for r in got).most_common(1)[0]
            ts["family"], ts["weight"] = fam, wt
    # bundle the weights that at least two runs use (one odd run is more likely a mis-measure)
    counts = Counter((r["family"], r["weight"]) for r in rows)
    used: dict = {}
    for (fam, wt), n in counts.items():
        if n >= 2 or len(rows) < 5:
            used.setdefault(fam, set()).add(wt)
    for ts in spec.get("tokens", {}).get("typeScale", []):
        if ts.get("family") in used:
            used[ts["family"]].add(ts["weight"])
    meta_fonts = spec.setdefault("meta", {}).setdefault("fonts", [])
    have = {f.get("css") for f in meta_fonts}
    for fam, ws in used.items():
        entry = {"css": fam, "qtFamily": fam, "files": [], "weights": sorted(ws), "src": "measured"}
        if args.fonts_dir:
            entry["files"] = [n for n in fontlib.bundle(fam, sorted(ws), args.fonts_dir) if n.endswith((".ttf", ".otf"))]
        if fam in have:
            if args.overwrite:
                meta_fonts[:] = [f for f in meta_fonts if f.get("css") != fam] + [entry]
        else:
            meta_fonts.append(entry)
    report["fonts"] = {"families": first["families"], "runs": rows, "bundledWeights": {f: sorted(w) for f, w in used.items()},
                       "outsideCatalog": first.get("outsideCatalog", False),
                       "note": "proprietary faces (SF Pro, Segoe UI, Helvetica) come back as their closest open "
                               "family: say so in the README"}
    if first.get("outsideCatalog"):
        report["fonts"]["check"] = (f"the screen's font is probably not in the catalog (runs disagree, agreement "
                                    f"{first['families'][0]['agreement']}): {first['families'][0]['family']} is the nearest "
                                    "substitute. Ask for the font if possible; otherwise fit sizes so text widths match "
                                    "and name the substitute in the README (typography.md)")
    return True


def _icons(img, dpr, spec, args, report) -> bool:
    import icon_match
    icons = [ic for ic in spec.get("icons", []) if ic.get("bbox")]
    if not icons:
        return True
    try:
        index = icon_match.load_index()
    except (FileNotFoundError, OSError, SystemExit):
        report["skipped"].append("icons: no icon index — run: python icon_match.py fetch")
        return False
    rows = []
    for ic, r in zip(icons, icon_match.match_many(img, dpr, [ic["bbox"] for ic in icons], index, top=3), strict=True):
        best = r["candidates"][0] if r and r["candidates"] else None
        row = {"id": ic.get("id"), "bbox": ic["bbox"], "candidates": (r or {}).get("candidates", [])}
        if best and best["score"] >= MIN_ICON_SCORE:
            if args.overwrite or not ic.get("match"):
                ic["match"], ic["score"], ic["kind"] = best["id"], best["score"], "svg"
                if best.get("strokeWidth"):
                    ic["strokeWidth"] = best["strokeWidth"]
            if best["score"] < CHECK_ICON_SCORE:
                row["check"] = "low score: compare with the alternatives at zoom 8"
        else:
            row["check"] = "no confident match: pick from the candidates or draw it (icons-vectors.md)"
        rows.append(row)
    report["icons"] = rows
    return True


def _shadows(img, dpr, spec, args, report) -> bool:
    import shadow_fit
    jobs = shadow_fit.jobs_from_spec(spec)
    fits = shadow_fit.fit_scene(img, dpr, jobs)
    by_id = {n["id"]: n for n in spec.get("nodes", [])}
    rows = []
    for j in jobs:
        f = fits.get(j["id"])
        if not f:
            continue
        rows.append({"id": j["id"], **{k: f[k] for k in ("css", "hasShadow", "atBound", "residual", "rawResidual")}})
        st = by_id[j["id"]].setdefault("style", {})
        if f["hasShadow"] and (args.overwrite or not st.get("shadow")):
            st["shadow"] = [{"x": f["x"], "y": f["y"], "blur": f["blur"], "spread": f["spread"],
                             "color": {"hex": f["color"], "alpha": f["alpha"]}, "inset": False, "src": "measured"}]
        elif st.get("shadow") and not f["hasShadow"]:
            rows[-1]["check"] = "the spec has a shadow here but none was measured"
    report["shadows"] = rows
    return True


def _gradients(img, dpr, spec, args, report) -> bool:
    import gradient_fit
    import shadow_fit
    nodes = [n for n in spec.get("nodes", []) if n.get("role") != "background" and shadow_fit.painted(n)
             and n["bbox"][2] * n["bbox"][3] >= GRAD_MIN_AREA]
    jobs = {j["id"]: j for j in gradient_fit.jobs_from_spec(spec, {n["id"] for n in nodes})}
    rows = []
    for n in nodes:
        j = jobs[n["id"]]
        f = gradient_fit.fit_region(img, dpr, j["bbox"], j["mask"], j["radius"], border=j["border"])
        if not f:
            continue
        ok = gradient_fit.accept(f)
        st = n.setdefault("style", {})
        declared = (st.get("fillImage") or "").startswith("linear-gradient")
        if ok or declared:
            rows.append({"id": n["id"], "css": f["css"], "accepted": ok, "residual": f["residual"],
                         "flatResidual": f["flatResidual"], "outliers": f["outliers"], "qt": f["qt"]})
        if ok and (args.overwrite or not st.get("fillImage") or st.get("fillImage", "").startswith("linear-gradient(")
                   and n.get("src") == "inferred"):
            st["fillImage"] = f["css"]
            st["gradient"] = {"angle": f["angle"], "stops": f["stops"], "qt": f["qt"], "src": "measured"}
        elif declared and not ok:
            rows[-1]["check"] = "declared gradient not confirmed (solid fill, or content covers it)"
    report["gradients"] = rows
    return True


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("image", type=Path)
    ap.add_argument("spec", type=Path)
    ap.add_argument("--only", default="fonts,icons,shadows,gradients")
    ap.add_argument("--out", type=Path)
    ap.add_argument("--report", type=Path)
    ap.add_argument("--fonts-dir", type=Path, help="write static TTFs of the matched fonts here (+ license)")
    ap.add_argument("--max-runs", type=int, default=40, help="runs used to decide the screen's families")
    ap.add_argument("--dpr", type=float)
    ap.add_argument("--overwrite", action="store_true", help="replace values already in the spec")
    args = ap.parse_args(argv)
    for p in (args.image, args.spec):
        if not p.exists():
            print(f"[error] no such file: {p}", file=sys.stderr)
            return 2
    import font_match
    img = font_match.load_rgb(args.image)
    spec = json.loads(args.spec.read_text())
    dpr = args.dpr or float(spec.get("meta", {}).get("dpr", 1))
    only = [s.strip() for s in args.only.split(",") if s.strip()]
    unknown = set(only) - {"fonts", "icons", "shadows", "gradients"}
    if unknown:
        print(f"[error] unknown matcher(s): {', '.join(sorted(unknown))}", file=sys.stderr)
        return 2
    report: dict = {"image": str(args.image), "spec": str(args.spec), "skipped": []}
    steps = {"fonts": _fonts, "icons": _icons, "shadows": _shadows, "gradients": _gradients}
    complete = True
    for name in only:
        complete &= steps[name](img, dpr, spec, args, report)
    out = args.out or args.spec.with_suffix(".matched.json")
    out.write_text(json.dumps(spec, indent=1, ensure_ascii=False))
    rep = args.report or out.with_name(out.stem.replace(".matched", "") + ".match-report.json")
    rep.write_text(json.dumps(report, indent=1, ensure_ascii=False, default=lambda o: o.tolist() if isinstance(o, np.ndarray) else str(o)))

    if "fonts" in report:
        fams = ", ".join(f"{f['family']} ({f['runs']} runs)" for f in report["fonts"]["families"])
        print(f"fonts      {fams}" + ("  — OUTSIDE THE CATALOG: substitute, see the report" if report["fonts"]["outsideCatalog"] else ""))
    if "icons" in report:
        n_ok = sum("check" not in r for r in report["icons"])
        print(f"icons      {n_ok}/{len(report['icons'])} confident"
              + (f"; check {len(report['icons']) - n_ok} (see the report)" if n_ok < len(report["icons"]) else ""))
    if "shadows" in report:
        sh = [r for r in report["shadows"] if r["hasShadow"]]
        print(f"shadows    {len(sh)} of {len(report['shadows'])} surfaces: " + "; ".join(f"{r['id']} {r['css']}" for r in sh[:6])
              + (" …" if len(sh) > 6 else ""))
    if "gradients" in report:
        gr = [r for r in report["gradients"] if r["accepted"]]
        print(f"gradients  {len(gr)}: " + "; ".join(f"{r['id']} {r['css']}" for r in gr[:4]) + (" …" if len(gr) > 4 else ""))
    for s in report["skipped"]:
        print(f"[skipped] {s}")
    print(f"-> {out}, {rep}")
    return 0 if complete else 1


if __name__ == "__main__":
    sys.exit(main())
