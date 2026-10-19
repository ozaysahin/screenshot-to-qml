#!/usr/bin/env python3
"""Score the v0.6 matchers against the eval cases' ground truth.

Usage:
  python evals/score_matching.py [--cases 01,03] [--only fonts,icons,shadows,gradients] [--verbose] [--jobs 2]

  fonts      font_match.py on the golden text runs → family accuracy per run (catalog of 63
             families, all candidates), weight exact / within 100, size error
  icons      icon_match.py on the golden icon boxes → top-1 / top-3 accuracy over every
             indexed set (a prediction whose drawing is identical to the truth counts, so
             aliases such as lucide home/house are not errors)
  shadows    shadow_fit.py on nodes with a box-shadow → blur / offset / alpha error of the
             dominant layer, and the ring residual after the fit
  gradients  gradient_fit.py on nodes with a linear-gradient → angle error, end-color ΔE

Writes evals/matching-results.{json,md}.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "skills" / "screenshot-to-qml" / "scripts"))
CASES = ROOT / "evals" / "cases"

import font_match  # noqa: E402
import fontlib  # noqa: E402


def score_fonts(case: Path, verbose: bool) -> dict:
    spec = json.loads((case / "golden-spec.json").read_text())
    dpr = float(spec["meta"]["dpr"])
    img = font_match.load_rgb(case / "input.png")
    runs = font_match.pick_runs(spec, 40)
    runs_nopx = [{k: v for k, v in r.items() if k != "font"} for r in runs]   # do not leak the true size
    res = font_match.match(img, dpr, runs_nopx, fontlib.available())
    truth = {(r["string"], tuple(r["bbox"])): r["font"] for r in runs}
    fam_ok = w_ok = w_near = n = 0
    px_err = []
    for r in res["runs"]:
        t = truth.get((r["string"], tuple(r["bbox"])))
        if not t:
            continue
        n += 1
        ok = r["family"].lower() == t["family"].lower()
        fam_ok += ok
        if ok:
            w_ok += r["weight"] == t["weight"]
            w_near += abs(r["weight"] - t["weight"]) <= 100
            px_err.append(abs(r["px"] - t["px"]))
        if verbose and not ok:
            print(f"    ✗ {r['string'][:30]:30s} {r['family']} {r['weight']} (truth {t['family']} {t['weight']})")
    return {"runs": n, "familyAcc": fam_ok / n if n else None, "weightExact": w_ok / fam_ok if fam_ok else None,
            "weightWithin100": w_near / fam_ok if fam_ok else None,
            "pxMAE": float(np.mean(px_err)) if px_err else None,
            "families": [f["family"] for f in res["families"]],
            "agreement": {f["family"]: f.get("agreement") for f in res["families"]},
            "outsideCatalog": res.get("outsideCatalog"),
            "truthFamilies": sorted({t["family"] for t in truth.values()})}


def score_icons(case: Path, verbose: bool) -> dict | None:
    import icon_match
    spec = json.loads((case / "golden-spec.json").read_text())
    if not spec.get("icons"):
        return None
    dpr = float(spec["meta"]["dpr"])
    img = icon_match.load_rgb(case / "input.png")
    index = icon_match.load_index()
    top1 = top3 = n = 0
    matched = icon_match.match_many(img, dpr, [ic["bbox"] for ic in spec["icons"]], index, top=3)
    for ic, res in zip(spec["icons"], matched, strict=True):
        truth = ic["match"]
        tset, tname = truth.split(":", 1)
        if res is None:
            continue
        n += 1
        names = [c["id"] for c in res["candidates"]]
        same = [icon_match.same_drawing(index, c, tset, tname) for c in names]
        top1 += bool(same and same[0])
        top3 += any(same)
        if verbose and not (same and same[0]):
            print(f"    ✗ {truth:28s} → {', '.join(names)}")
    return {"icons": n, "top1": top1 / n if n else None, "top3": top3 / n if n else None}


def parse_shadows(style) -> list:
    return [s for s in (style.get("shadow") or []) if not s.get("inset")]


def score_shadows(case: Path, verbose: bool) -> dict | None:
    import shadow_fit
    spec = json.loads((case / "golden-spec.json").read_text())
    nodes = [n for n in spec["nodes"] if parse_shadows(n.get("style", {}))]
    if not nodes:
        return None
    dpr = float(spec["meta"]["dpr"])
    img = shadow_fit.load_rgb(case / "input.png")
    # the fitter sees geometry only: strip every node's shadow before building the jobs
    blind = json.loads(json.dumps(spec))
    for n in blind["nodes"]:
        (n.get("style") or {}).pop("shadow", None)
    jobs = shadow_fit.jobs_from_spec(blind)
    fits = shadow_fit.fit_scene(img, dpr, jobs)
    rows = []
    for nd in nodes:
        fit = fits.get(nd["id"])
        if nd["id"] not in fits:          # a surface painted only by its shadow: fit it on its own
            fit = shadow_fit.fit_node(img, dpr, nd["bbox"], nd["style"].get("radius", 0) or 0)
        if fit is None:
            continue
        layers = parse_shadows(nd["style"])
        dom = max(layers, key=lambda s: s["color"]["alpha"] * (s["blur"] + 1))
        rows.append({"id": nd["id"], "blurErr": abs(fit["blur"] - dom["blur"]), "detected": fit["hasShadow"],
                     "yErr": abs(fit["y"] - dom["y"]), "residual": fit["residual"], "rawResidual": fit["rawResidual"]})
        if verbose:
            print(f"    {nd['id']:14s} {'✓' if fit['hasShadow'] else '·'} fit {fit['x']:.0f}/{fit['y']:.1f}/{fit['blur']:.1f}/"
                  f"{fit['spread']:.1f} a {fit['alpha']:.2f} c{fit['casters']} (truth {dom['y']:.0f}/{dom['blur']:.0f} "
                  f"a {dom['color']['alpha']:.2f}{' +' + str(len(layers) - 1) if len(layers) > 1 else ''}); "
                  f"residual {fit['residual']:.2f} (raw {fit['rawResidual']:.2f})")
    if not rows:
        return None
    shadowed = {n["id"] for n in nodes}
    clean = [f for i, f in fits.items() if i not in shadowed and f is not None]
    if verbose:
        for i, f in fits.items():
            if i not in shadowed and f is not None and f["hasShadow"]:
                print(f"    {i:14s} false alarm: {f['css']} residual {f['residual']:.2f} (raw {f['rawResidual']:.2f})")
    det = [r for r in rows if r["detected"]]
    return {"nodes": len(rows), "detected": float(np.mean([r["detected"] for r in rows])),
            "clean": len(clean), "falseAlarms": sum(f["hasShadow"] for f in clean),
            "detectedBlurErrs": [round(r["blurErr"], 2) for r in det], "detectedYErrs": [round(r["yErr"], 2) for r in det],
            "blurMAE": float(np.mean([r["blurErr"] for r in rows])),
            "blurMedAE": float(np.median([r["blurErr"] for r in rows])),
            "yMAE": float(np.mean([r["yErr"] for r in rows])),
            "residual": float(np.mean([r["residual"] for r in rows])),
            "rawResidual": float(np.mean([r["rawResidual"] for r in rows]))}


GRAD = re.compile(r"linear-gradient\((\d+(?:\.\d+)?)deg,(.*)\)\s*$")
COLOR = re.compile(r"rgba?\(([^)]*)\)")


def truth_gradient(fill_image: str):
    """(angle, [(r, g, b, a), ...]) of a CSS linear-gradient."""
    m = GRAD.match(fill_image.strip())
    if not m:
        return None
    stops = []
    for c in COLOR.findall(m.group(2)):
        v = [float(x) for x in c.split(",")]
        stops.append((*v[:3], v[3] if len(v) > 3 else 1.0))
    return float(m.group(1)) % 360, stops


def orient(fit_angle: float, angle: float, stops: list):
    """The truth written the way the fit reports it: θ or θ − 180° with the stops reversed."""
    if abs((fit_angle - angle + 180) % 360 - 180) > 90:
        return (angle + 180) % 360, stops[::-1]
    return angle, stops


def score_gradients(case: Path, verbose: bool) -> dict | None:
    import gradient_fit
    spec = json.loads((case / "golden-spec.json").read_text())
    nodes = [n for n in spec["nodes"] if truth_gradient(n.get("style", {}).get("fillImage") or "")]
    if not nodes:
        return None
    dpr = float(spec["meta"]["dpr"])
    img = gradient_fit.load_rgb(case / "input.png")
    jobs = {j["id"]: j for j in gradient_fit.jobs_from_spec(spec, {n["id"] for n in nodes})}
    rows, skipped = [], 0
    for nd in nodes:
        angle, stops = truth_gradient(nd["style"]["fillImage"])
        if any(s[3] < 1 for s in stops):      # translucent stops: the observed color depends on the backdrop
            skipped += 1
            continue
        j = jobs[nd["id"]]
        fit = gradient_fit.fit_region(img, dpr, j["bbox"], j["mask"], radius=j["radius"], border=j["border"])
        if fit is None:
            continue
        angle, stops = orient(fit["angle"], angle, stops)
        d_angle = abs((fit["angle"] - angle + 180) % 360 - 180)
        e0 = gradient_fit.delta_e(fit["stops"][0]["rgb"], stops[0][:3])
        e1 = gradient_fit.delta_e(fit["stops"][-1]["rgb"], stops[-1][:3])
        rows.append({"id": nd["id"], "angleErr": d_angle, "endDeltaE": (e0 + e1) / 2, "accepted": gradient_fit.accept(fit),
                     "stops": len(fit["stops"]), "truthStops": len(stops)})
        if verbose:
            print(f"    {nd['id']:14s} {'✓' if gradient_fit.accept(fit) else '·'} fit {fit['css'][:80]} (truth {angle:.0f}°, {len(stops)} stops); "
                  f"ΔE ends {e0:.1f}/{e1:.1f}; residual {fit['residual']} (solid {fit['flatResidual']})")
    if not rows:
        return None
    # false positives: painted surfaces without a gradient that match.py would call one
    import shadow_fit
    plain = [n for n in spec["nodes"] if shadow_fit.painted(n) and not (n.get("style") or {}).get("fillImage")
             and n.get("role") != "background" and n["bbox"][2] * n["bbox"][3] >= 600]
    translucent = {n["id"] for n in plain if ((n.get("style") or {}).get("fill") or {}).get("alpha", 1) < 0.99}
    pj = {j["id"]: j for j in gradient_fit.jobs_from_spec(spec, {n["id"] for n in plain})}
    false = []
    for n in plain:
        j = pj[n["id"]]
        f = gradient_fit.fit_region(img, dpr, j["bbox"], j["mask"], radius=j["radius"], border=j["border"])
        if gradient_fit.accept(f):
            false.append(n["id"])
            if verbose:
                kind = "glass read as gradient" if n["id"] in translucent else "false gradient"
                print(f"    {n['id']:14s} {kind}: {f['css'][:70]} residual {f['residual']} (solid {f['flatResidual']})")
    return {"nodes": len(rows), "skippedTranslucent": skipped, "plain": len(plain) - len(translucent),
            "falseGradients": len([i for i in false if i not in translucent]),
            "translucent": len(translucent), "translucentAsGradient": len([i for i in false if i in translucent]),
            "accepted": sum(r["accepted"] for r in rows),
            "angleMAE": float(np.mean([r["angleErr"] for r in rows])),
            "angleMax": float(np.max([r["angleErr"] for r in rows])),
            "endDeltaE": float(np.mean([r["endDeltaE"] for r in rows])),
            "stopCountOK": float(np.mean([r["stops"] == r["truthStops"] for r in rows]))}


def score_case(case: Path, only: set, verbose: bool) -> dict:
    scorers = {"fonts": score_fonts, "icons": score_icons, "shadows": score_shadows, "gradients": score_gradients}
    res = {}
    for name in ("fonts", "icons", "shadows", "gradients"):
        if name not in only:
            continue
        t = time.time()
        r = scorers[name](case, verbose)
        if r is not None:
            r["seconds"] = round(time.time() - t, 1)
            res[name] = r
            shown = {k: (round(v, 3) if isinstance(v, float) else v) for k, v in r.items()}
            print(f"{case.name:22s} {name:9s} {shown}", flush=True)
    return res


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cases", default="")
    ap.add_argument("--only", default="fonts,icons,shadows,gradients")
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--jobs", type=int, default=1, help="cases scored in parallel processes")
    args = ap.parse_args(argv)
    prefixes = tuple(c.strip() for c in args.cases.split(",") if c.strip())
    only = {s.strip() for s in args.only.split(",")}
    cases = sorted(p for p in CASES.iterdir() if p.is_dir() and (not prefixes or p.name.startswith(prefixes)))
    out = {}
    if args.jobs > 1:
        from concurrent.futures import ProcessPoolExecutor
        with ProcessPoolExecutor(max_workers=args.jobs) as pool:
            for name, res in zip([c.name for c in cases], pool.map(score_case, cases, [only] * len(cases),
                                                                   [args.verbose] * len(cases)), strict=True):
                out[name] = res
    else:
        for case in cases:
            out[case.name] = score_case(case, only, args.verbose)
    out = {k: out[k] for k in sorted(out)}

    def pooled(kind, key, weight_key):
        rows = [v[kind] for v in out.values() if kind in v and v[kind].get(key) is not None]
        tot = sum(r[weight_key] for r in rows)
        return sum(r[key] * r[weight_key] for r in rows) / tot if tot else None

    if not prefixes:                       # partial runs (--only) update the saved results
        saved = ROOT / "evals" / "matching-results.json"
        if saved.exists() and only != {"fonts", "icons", "shadows", "gradients"}:
            old = json.loads(saved.read_text())["cases"]
            for case_name, res in old.items():
                for k, v in res.items():
                    if k not in only:
                        out.setdefault(case_name, {})[k] = v

    def total(kind, key):
        return sum(v[kind][key] for v in out.values() if kind in v and key in v[kind])

    def gather(kind, key):
        return [e for v in out.values() if kind in v for e in v[kind].get(key, [])]

    sh_n = total("shadows", "nodes")
    summary = {
        "fontFamilyAcc": pooled("fonts", "familyAcc", "runs"),
        "fontWeightWithin100": pooled("fonts", "weightWithin100", "runs"),
        "iconTop1": pooled("icons", "top1", "icons"), "iconTop3": pooled("icons", "top3", "icons"),
        "shadowBlurMAE": pooled("shadows", "blurMAE", "nodes"), "shadowResidual": pooled("shadows", "residual", "nodes"),
        "shadowRawResidual": pooled("shadows", "rawResidual", "nodes"),
        "shadowDetected": (sum(v["shadows"]["detected"] * v["shadows"]["nodes"] for v in out.values() if "shadows" in v) / sh_n
                           if sh_n else None),
        "shadowFalseAlarms": total("shadows", "falseAlarms"), "shadowClean": total("shadows", "clean"),
        "shadowDetectedBlurMedAE": float(np.median(gather("shadows", "detectedBlurErrs"))) if gather("shadows", "detectedBlurErrs") else None,
        "shadowDetectedYMedAE": float(np.median(gather("shadows", "detectedYErrs"))) if gather("shadows", "detectedYErrs") else None,
        "gradientAccepted": total("gradients", "accepted"), "gradientNodes": total("gradients", "nodes"),
        "gradientFalse": total("gradients", "falseGradients"), "gradientPlain": total("gradients", "plain"),
        "gradientGlass": total("gradients", "translucentAsGradient"), "gradientTranslucent": total("gradients", "translucent"),
        "gradientAngleMAE": pooled("gradients", "angleMAE", "nodes"),
        "gradientEndDeltaE": pooled("gradients", "endDeltaE", "nodes"),
    }
    print("pooled:", json.dumps({k: (round(v, 3) if v is not None else None) for k, v in summary.items()}))
    if not prefixes:
        (ROOT / "evals" / "matching-results.json").write_text(json.dumps({"cases": out, "pooled": summary}, indent=1))
        lines = ["| Case | Font family (runs) | Weight ±100 | Icon top-1 / top-3 | Shadows found · false | Shadow blur / y error (found) | Gradient angle / end ΔE |",
                 "| --- | --- | --- | --- | --- | --- | --- |"]

        def f(v, fmt):
            return "—" if v is None else format(v, fmt)
        for name, v in out.items():
            fo, ic, sh, gr = v.get("fonts", {}), v.get("icons", {}), v.get("shadows", {}), v.get("gradients", {})
            found = (f"{round(sh['detected'] * sh['nodes'])}/{sh['nodes']} · {sh['falseAlarms']}/{sh['clean']}" if sh else "—")
            be, ye = sh.get("detectedBlurErrs") or [], sh.get("detectedYErrs") or []
            errs = f"{np.median(be):.1f} / {np.median(ye):.1f} px" if be else "—"
            lines.append(f"| {name} | {f(fo.get('familyAcc'), '.0%')} ({fo.get('runs', 0)}) | {f(fo.get('weightWithin100'), '.0%')} | "
                         f"{f(ic.get('top1'), '.0%')} / {f(ic.get('top3'), '.0%')} | {found} | {errs} | "
                         f"{f(gr.get('angleMAE'), '.1f')}° / {f(gr.get('endDeltaE'), '.1f')} |")
        s = summary
        found = (f"{round(s['shadowDetected'] * sh_n)}/{sh_n} · {s['shadowFalseAlarms']}/{s['shadowClean']}"
                 if s["shadowDetected"] is not None else "—")
        errs = (f"{s['shadowDetectedBlurMedAE']:.1f} / {s['shadowDetectedYMedAE']:.1f} px (median)"
                if s["shadowDetectedBlurMedAE"] is not None else "—")
        lines.append(f"| **pooled** | **{f(s['fontFamilyAcc'], '.0%')}** | {f(s['fontWeightWithin100'], '.0%')} | "
                     f"**{f(s['iconTop1'], '.0%')}** / {f(s['iconTop3'], '.0%')} | {found} | {errs} | "
                     f"{f(s['gradientAngleMAE'], '.1f')}° / {f(s['gradientEndDeltaE'], '.1f')} |")
        lines += ["", "Shadows: found = surfaces with a CSS shadow where the fit reports `hasShadow`; false = surfaces "
                  "without one where it does. Errors are for the dominant layer on the found ones. Gradients: "
                  f"{s['gradientAccepted']}/{s['gradientNodes']} opaque gradients accepted, {s['gradientFalse']}/{s['gradientPlain']} "
                  f"solid surfaces called gradients, {s['gradientGlass']}/{s['gradientTranslucent']} translucent glass surfaces "
                  "read as gradients (a static stand-in for the blurred backdrop)."]
        (ROOT / "evals" / "matching-results.md").write_text("\n".join(lines) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
