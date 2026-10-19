#!/usr/bin/env python3
"""Controlled and hold-out tests for the v0.6 matchers, rendered by Chromium.

Usage:
  python evals/synthetic_matching.py [--only fonts,shadows,gradients] [--n 24] [--seed 7] [--keep DIR]

  fonts      hold-out: 17 catalog families that no eval case uses (the matcher's constants were
             tuned on the eval cases). One sheet per family, like a screen: 10 runs of UI text
             and numbers at 12–32 px and the weights the family has, dpr 1 or 2. Per-run
             family accuracy against all 63 candidates, weight within 100, and whether the
             sheet's family (the most-voted) is right.
  outside    12 open families that are NOT in the catalog (stand-ins for proprietary faces), one
             sheet each like the hold-out test: how often the matcher flags `outsideCatalog`
             (and, for the hold-out sheets above, how often it flags a catalog face by mistake).
             The families are fetched into the font cache but stay out of the candidates.
  shadows    one card per image on a flat or slightly graded background with a random CSS
             box-shadow (y 0–24, blur 0–48, spread −4–4, alpha 0.06–0.4, x mostly 0), radius
             0–24, dpr 1 or 2. Errors of x, y, blur, spread, alpha; detection.
  gradients  random linear-gradient boxes: angle 0–359°, 2 or 3 stops, radius 0–32, half of them
             with a text label inside (declared as a mask). Angle error (mod 180, stops
             reversed), end-stop ΔE, stop-count accuracy.

Nothing here is used for tuning. Writes evals/synthetic-results.{json,md}.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import tempfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "skills" / "screenshot-to-qml" / "scripts"))

HOLDOUT = ["Roboto", "Open Sans", "Lato", "Montserrat", "Poppins", "Rubik", "Work Sans", "Fira Sans",
           "Source Sans 3", "Figtree", "Lexend", "Urbanist", "IBM Plex Sans", "Ubuntu", "Fira Code",
           "Source Code Pro", "Roboto Mono"]
STRINGS = ["Dashboard overview", "Settings", "Temperature 23,5 °C", "Kayıtlı cihazlar", "Last sync 14:32",
           "Günlük üretim", "Export CSV", "1.248 kWh", "Notifications", "Şarj durumu %87", "Add new device",
           "Order #40213", "Kalan süre 02:14:36", "Save changes", "Weekly report", "Çıkış yap"]


def shoot(page_html: str, size, dpr: float, out: Path, probe_js: str):
    from playwright.sync_api import sync_playwright
    html = out.with_suffix(".html")
    html.write_text(page_html)
    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--font-render-hinting=none"])
        ctx = browser.new_context(viewport={"width": size[0], "height": size[1]}, device_scale_factor=dpr)
        page = ctx.new_page()
        page.goto(html.as_uri())
        page.evaluate("document.fonts.ready")
        page.wait_for_timeout(150)
        info = page.evaluate(probe_js)
        page.screenshot(path=str(out))
        browser.close()
    return info


# ------------------------------------------------------------------ fonts

def font_face(family: str) -> str:
    import fontlib
    m = json.loads((fontlib.cache_dir() / fontlib.slug(family) / "manifest.json").read_text())
    folder = fontlib.cache_dir() / fontlib.slug(family)
    css = []
    for f in m["files"]:
        path = folder / f["file"]
        ax = fontlib._axes(str(path)).get("wght")
        weight = f"{int(ax[0])} {int(ax[2])}" if ax else str(f["weight"])
        css.append(f"@font-face {{ font-family: 'T {family}'; src: url('{path.as_uri()}'); font-weight: {weight}; }}")
    return "\n".join(css)


OUTSIDE = ["Epilogue", "Chivo", "Commissioner", "Golos Text", "Gabarito", "Kumbh Sans", "Libre Franklin", "Cabin",
           "Jost", "Overpass", "Bricolage Grotesque", "Wix Madefor Text"]


def test_outside(rng: random.Random, keep: Path, verbose: bool) -> dict:
    import fontlib
    manifests = []
    for fam in OUTSIDE:
        m = fontlib.fetch(fam)
        if m is None:
            print(f"  [skip] {fam}: could not fetch")
            continue
        manifests.append(m)
    res = test_fonts(len(manifests), rng, keep, verbose, sheet_families=manifests)
    flagged = [s for s in res["perSheet"] if s["outside"]]
    return {"sheets": res["sheets"], "flagged": len(flagged), "flaggedRate": len(flagged) / res["sheets"] if res["sheets"] else None,
            "perSheet": res["perSheet"]}


def test_fonts(n_sheets: int, rng: random.Random, keep: Path, verbose: bool, sheet_families: list | None = None) -> dict:
    import font_match
    import fontlib
    families = fontlib.available()
    probe = """() => [...document.querySelectorAll('span[data-w]')].map(s => { const r = s.getBoundingClientRect();
      return {string: s.textContent, bbox: [r.x, r.y, r.width, r.height], weight: +s.dataset.w, px: +s.dataset.px}; })"""
    rows, sheets = [], []
    pool = sheet_families or [next((f for f in families if f["family"] == fam), {"family": fam, "missing": True})
                              for fam in HOLDOUT[:n_sheets]]
    for m in pool:
        fam = m["family"]
        if m.get("missing"):
            print(f"  [skip] {fam}: not in the font cache")
            continue
        ws = [w for w in fontlib.weights(m) if 300 <= w <= 800]
        dpr = rng.choice([1, 2])
        spans, y = [], 24
        for s in rng.sample(STRINGS, 10):
            px, w = rng.choice([12, 13, 14, 16, 18, 20, 24, 28, 32]), rng.choice(ws)
            spans.append(f"<div style='position:absolute;left:24px;top:{y}px;font:{w} {px}px \"T {fam}\";color:#1F2430'>"
                         f"<span data-w='{w}' data-px='{px}'>{s}</span></div>")
            y += int(px * 1.6) + 10
        html = (f"<!doctype html><meta charset=utf-8><style>{font_face(fam)} body{{margin:0;background:#FAFAF7}}</style>"
                + "".join(spans))
        out = keep / f"font-{fontlib.slug(fam)}.png"
        runs = shoot(html, (640, y + 16), dpr, out, probe)
        img = font_match.load_rgb(out)
        res = font_match.match(img, dpr, [{"string": r["string"], "bbox": r["bbox"]} for r in runs], families)
        truth = {tuple(round(v, 2) for v in r["bbox"]): r for r in runs}
        fam_top = res["families"][0]["family"] if res["families"] else None
        sheets.append({"family": fam, "screenFamily": fam_top, "ok": fam_top == fam, "outside": res["outsideCatalog"],
                       "agreement": res["families"][0]["agreement"] if res["families"] else None})
        for r in res["runs"]:
            t = truth.get(tuple(round(v, 2) for v in r["bbox"]))
            if not t:
                continue
            ok = r["family"] == fam
            rows.append({"family": fam, "ok": ok, "weightOK": ok and abs(r["weight"] - t["weight"]) <= 100,
                         "pxErr": abs(r["px"] - t["px"]) if ok else None})
        if verbose:
            got = sum(r["ok"] for r in rows if r["family"] == fam)
            print(f"  {fam:20s} dpr {dpr}: screen → {fam_top} (agreement {sheets[-1]['agreement']}"
                  f"{', OUTSIDE' if sheets[-1]['outside'] else ''}); runs {got}/{sum(r['family'] == fam for r in rows)}")
    n = len(rows)
    fam_ok = [r for r in rows if r["ok"]]
    return {"sheets": len(sheets), "screenFamilyAcc": float(np.mean([s["ok"] for s in sheets])) if sheets else None,
            "runs": n, "runFamilyAcc": len(fam_ok) / n if n else None,
            "weightWithin100": float(np.mean([r["weightOK"] for r in fam_ok])) if fam_ok else None,
            "pxMAE": float(np.mean([r["pxErr"] for r in fam_ok])) if fam_ok else None,
            "falseOutside": sum(s["outside"] for s in sheets), "perSheet": sheets}


# ------------------------------------------------------------------ shadows

def test_shadows(n: int, rng: random.Random, keep: Path, verbose: bool) -> dict:
    import shadow_fit
    probe = "() => { const r = document.getElementById('c').getBoundingClientRect(); return [r.x, r.y, r.width, r.height]; }"
    rows = []
    for i in range(n):
        dark = rng.random() < 0.3
        bg = rng.choice(["#0F172A", "#1E1B2E", "#111827"]) if dark else rng.choice(["#F4F5F7", "#FFFFFF", "#F6F1EA", "#EEF2F7"])
        graded = rng.random() < 0.4
        card = "#1F2937" if dark else "#FFFFFF"
        y = rng.choice([0, 1, 2, 4, 6, 8, 10, 12, 16, 20, 24])
        blur = rng.choice([2, 4, 8, 12, 16, 20, 24, 32, 40, 48])
        spread = rng.choice([0, 0, 0, 0, -2, -4, 2, 4])
        x = rng.choice([0] * 6 + [-4, 4])
        alpha = round(rng.uniform(0.3, 0.6) if dark else rng.uniform(0.06, 0.4), 2)
        radius = rng.choice([0, 4, 8, 12, 16, 24])
        w, h = rng.randint(160, 280), rng.randint(100, 200)
        dpr = rng.choice([1, 2])
        back = f"linear-gradient(180deg, {bg}, color-mix(in srgb, {bg} 92%, #7C3AED))" if graded else bg
        html = (f"<!doctype html><style>body{{margin:0;background:{back};width:480px;height:400px}}"
                f"#c{{position:absolute;left:{(480 - w) // 2}px;top:{(400 - h) // 2 - 10}px;width:{w}px;height:{h}px;"
                f"border-radius:{radius}px;background:{card};box-shadow:{x}px {y}px {blur}px {spread}px rgba(0,0,0,{alpha})}}</style>"
                f"<div id=c></div>")
        out = keep / f"shadow-{i:02d}.png"
        box = shoot(html, (480, 400), dpr, out, probe)
        img = shadow_fit.load_rgb(out)
        f = shadow_fit.fit_node(img, dpr, box, radius)
        if f is None:
            continue
        a_err = abs(f["alpha"] - alpha)
        rows.append({"detected": f["hasShadow"], "xErr": abs(f["x"] - x), "yErr": abs(f["y"] - y),
                     "blurErr": abs(f["blur"] - blur), "spreadErr": abs(f["spread"] - spread), "alphaErr": a_err})
        if verbose:
            print(f"  #{i:02d} truth {x}/{y}/{blur}/{spread} a{alpha} r{radius} {'dark' if dark else 'light'}{' graded' if graded else ''}"
                  f" @{dpr}x → {f['x']:.1f}/{f['y']:.1f}/{f['blur']:.1f}/{f['spread']:.1f} a{f['alpha']:.2f}"
                  f" {'✓' if f['hasShadow'] else '·'}")
    k = {key: [r[key] for r in rows] for key in ("xErr", "yErr", "blurErr", "spreadErr", "alphaErr")}
    return {"cards": len(rows), "detected": float(np.mean([r["detected"] for r in rows])),
            **{f"{key[:-3]}MAE": float(np.mean(v)) for key, v in k.items()},
            **{f"{key[:-3]}P90": float(np.percentile(v, 90)) for key, v in k.items()}}


# ------------------------------------------------------------------ gradients

def test_gradients(n: int, rng: random.Random, keep: Path, verbose: bool) -> dict:
    import gradient_fit
    probe = """() => { const r = document.getElementById('g').getBoundingClientRect();
      const t = document.getElementById('t'); const q = t ? t.getBoundingClientRect() : null;
      return {box: [r.x, r.y, r.width, r.height], text: q ? [q.x, q.y, q.width, q.height] : null}; }"""
    rows = []
    for i in range(n):
        angle = rng.randrange(0, 360)
        k = rng.choice([2, 2, 3])
        cols = [tuple(rng.randrange(0, 256) for _ in range(3)) for _ in range(k)]
        while gradient_fit.delta_e(cols[0], cols[-1]) < 15:
            cols[-1] = tuple(rng.randrange(0, 256) for _ in range(3))
        pos = [0, rng.randint(30, 70), 100][: k] if k == 3 else [0, 100]
        if k == 3:
            pos = [0, pos[1], 100]
        stops = ", ".join(f"rgb{c} {p}%" for c, p in zip(cols, pos, strict=True))
        w, h = rng.randint(80, 420), rng.randint(40, 260)
        radius = rng.choice([0, 8, 16, 32, 999])
        label = rng.random() < 0.5
        dpr = rng.choice([1, 2])
        html = (f"<!doctype html><style>body{{margin:0;background:#F4F4F5}}"
                f"#g{{position:absolute;left:30px;top:30px;width:{w}px;height:{h}px;border-radius:{radius}px;"
                f"background:linear-gradient({angle}deg, {stops});display:flex;align-items:center;justify-content:center;"
                f"font:600 15px sans-serif;color:#fff}}</style><div id=g>{'<span id=t>Label</span>' if label else ''}</div>")
        out = keep / f"gradient-{i:02d}.png"
        info = shoot(html, (w + 60, h + 60), dpr, out, probe)
        img = gradient_fit.load_rgb(out)
        f = gradient_fit.fit_region(img, dpr, info["box"], [info["text"]] if info["text"] else [], radius=radius)
        if f is None:
            continue
        ta, tc = angle, cols
        if abs((f["angle"] - ta + 180) % 360 - 180) > 90:        # same gradient written the other way round
            ta, tc = (ta + 180) % 360, cols[::-1]
        d_angle = abs((f["angle"] - ta + 180) % 360 - 180)
        e0 = gradient_fit.delta_e(f["stops"][0]["rgb"], tc[0])
        e1 = gradient_fit.delta_e(f["stops"][-1]["rgb"], tc[-1])
        # a gradient whose ends lie outside the visible box is still fine if the look matches
        rows.append({"angleErr": d_angle, "endDeltaE": (e0 + e1) / 2, "stopsOK": len(f["stops"]) == k,
                     "residual": f["residual"], "isGradient": f["isGradient"]})
        if verbose:
            print(f"  #{i:02d} {angle:3d}° {k} stops {w}x{h} r{radius}{' +text' if label else ''} @{dpr}x → "
                  f"{f['css'][:70]}  Δangle {d_angle:.1f} ΔE {e0:.1f}/{e1:.1f}")
    return {"boxes": len(rows), "angleMAE": float(np.mean([r["angleErr"] for r in rows])),
            "angleP90": float(np.percentile([r["angleErr"] for r in rows], 90)),
            "endDeltaE": float(np.mean([r["endDeltaE"] for r in rows])),
            "endDeltaEP90": float(np.percentile([r["endDeltaE"] for r in rows], 90)),
            "stopCountAcc": float(np.mean([r["stopsOK"] for r in rows])),
            "residual": float(np.mean([r["residual"] for r in rows]))}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", default="fonts,outside,shadows,gradients")
    ap.add_argument("--n", type=int, default=24, help="cards / boxes per test (font sheets: all hold-out families)")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--keep", type=Path, help="keep the rendered images here")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args(argv)
    only = {s.strip() for s in args.only.split(",") if s.strip()}
    keep = args.keep or Path(tempfile.mkdtemp(prefix="s2q-synth-"))
    keep.mkdir(parents=True, exist_ok=True)
    out = {}
    tests = {"fonts": lambda rng: test_fonts(len(HOLDOUT), rng, keep, args.verbose),
             "outside": lambda rng: test_outside(rng, keep, args.verbose),
             "shadows": lambda rng: test_shadows(args.n, rng, keep, args.verbose),
             "gradients": lambda rng: test_gradients(args.n, rng, keep, args.verbose)}
    for name in ("fonts", "outside", "shadows", "gradients"):
        if name in only:
            out[name] = tests[name](random.Random(f"{args.seed}-{name}"))
            print(name, json.dumps({k: (round(v, 3) if isinstance(v, float) else v) for k, v in out[name].items()
                                    if k != "perSheet"}))
    if only == {"fonts", "outside", "shadows", "gradients"} and args.n == 24 and args.seed == 7:
        (ROOT / "evals" / "synthetic-results.json").write_text(json.dumps(out, indent=1))
        f, o, s, g = out["fonts"], out["outside"], out["shadows"], out["gradients"]
        md = ["| Test | Items | Result |", "| --- | --- | --- |",
              f"| Fonts, hold-out families | {f['sheets']} sheets / {f['runs']} runs | screen family {f['screenFamilyAcc']:.0%}, "
              f"run family {f['runFamilyAcc']:.0%}, weight ±100 {f['weightWithin100']:.0%}, size error {f['pxMAE']:.2f} px; "
              f"flagged outside the catalog by mistake: {f['falseOutside']}/{f['sheets']} |",
              f"| Fonts outside the catalog | {o['sheets']} sheets | flagged `outsideCatalog` {o['flagged']}/{o['sheets']} |",
              f"| Shadows, isolated card | {s['cards']} | detected {s['detected']:.0%}; mean error y {s['yMAE']:.1f} px, "
              f"blur {s['blurMAE']:.1f} px, spread {s['spreadMAE']:.1f} px, alpha {s['alphaMAE']:.3f} "
              f"(90th pct: y {s['yP90']:.1f}, blur {s['blurP90']:.1f}) |",
              f"| Gradients | {g['boxes']} | angle error {g['angleMAE']:.2f}° (90th pct {g['angleP90']:.1f}°), end ΔE {g['endDeltaE']:.2f} "
              f"(90th pct {g['endDeltaEP90']:.1f}), stop count {g['stopCountAcc']:.0%} |"]
        (ROOT / "evals" / "synthetic-results.md").write_text("\n".join(md) + "\n")
    print(f"images: {keep}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
