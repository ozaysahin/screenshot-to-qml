#!/usr/bin/env python3
"""Identify the font family, weight and size of text runs in a screenshot.

Usage:
  python font_match.py fetch [--families "Inter,Roboto"]         # download candidates (once)
  python font_match.py match IMG --spec design-spec.json [--dpr 2]
                             [--families "Inter,Barlow"] [--max-runs 40] [--out fonts.json]
  python font_match.py bundle "Family Name" --weights 400,600 --out assets/fonts

`fetch --families` also takes open families outside the catalog (any google/fonts family, by
name); `match --families` can then use them, and `bundle` writes static TTFs + the license.

`fetch` downloads the families in assets/catalog/fonts.json (63 UI sans and mono families)
from github.com/google/fonts into the cache (~/.cache/screenshot-to-qml, or $S2Q_CACHE).

`match` reads text runs (string + bbox) from the spec, cuts each run out of the screenshot,
turns it into an ink-coverage map, and compares it with every candidate family rendered at
several weights, sized so the ink heights agree. Score per candidate:
  family  NCC of the two coverage maps (same box) − |log(rendered / screenshot width)|
  weight  NCC − 0.5·|log width ratio| − 2·|log ink-mass ratio| (heavier strokes, more ink)
Runs vote for families (top-1 per run). The screen's families: the most-voted one, a
monospace family when mono candidates win ≥ 15 % of runs together, and any other family
winning ≥ 20 %; each run then gets the best of these (at most three).

Output (--out, and a summary on stdout):
  runs[]      string, bbox, family, weight, px (design px), score, alternatives
  families[]  family, category, runs won, mean score, agreement
  outsideCatalog  true when the primary family's runs disagree: on the median run another
              family fits better by more than 0.08 (OUTSIDE_AGREEMENT). Then the face is probably not
              in the catalog (proprietary or rare) and `family` is only the nearest substitute.
Proprietary fonts (SF Pro, Segoe UI, Helvetica) are not in the catalog; the closest open
family is returned (Inter for SF, Open Sans/Noto Sans for Segoe) and should be reported as
a substitute. Exit codes: 0 ok, 2 error.
"""
from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import cv2
import numpy as np

import fontlib

# Tuned on the eval set (evals/score_matching.py): the family is decided by shape + width,
# the weight inside a family by shape + ink mass.
FAMILY_WIDTH = 1.0         # family score = NCC − FAMILY_WIDTH·|log width ratio|
WEIGHT_WIDTH = 0.5         # weight score = NCC − WEIGHT_WIDTH·|log width ratio| − WEIGHT_DENSITY·|log ink ratio|
WEIGHT_DENSITY = 2.0
SECOND_FAMILY_SHARE = 0.2  # a further proportional family must win this share of runs
MONO_SHARE = 0.15          # monospace families together must win this share of runs
SECOND_FAMILY_MARGIN = 0.03  # …and beat the primary by this much (mean) on the runs it wins
COARSE_WEIGHTS = (400, 700)
KEEP_FAMILIES = 12
# agreement = median over a family's runs of (its score − the best other family's score).
# Catalog faces: ≥ −0.063 on the 19 eval cases that use them and ≥ 0 on the 17 hold-out sheets.
# Faces outside the catalog scatter the runs over look-alikes: case 20 −0.19, and 7 of 12
# outside sheets below −0.08 (the other 5 have a close catalog twin, e.g. Libre Franklin →
# Public Sans). evals/synthetic_matching.py --only fonts,outside
OUTSIDE_AGREEMENT = -0.08
MIN_CHARS = 3


def load_rgb(path: Path) -> np.ndarray:
    img = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if img is None:
        raise SystemExit(f"[error] cannot read {path}")
    return cv2.cvtColor(img, cv2.COLOR_BGR2RGB).astype(np.float32)


def coverage(img: np.ndarray, bbox, dpr: float) -> np.ndarray | None:
    """Ink coverage (0..1) of a text run, cropped to its ink box."""
    x, y, w, h = bbox
    # a text box already spans ascent..descent: little vertical slack, so the next line's
    # ascenders do not leak in; more horizontal slack for side bearings
    px_, py_ = max(2, int(round(0.3 * h * dpr))), max(1, int(round(0.06 * h * dpr)))
    x0, y0 = max(0, int(x * dpr) - px_), max(0, int(y * dpr) - py_)
    x1, y1 = min(img.shape[1], int((x + w) * dpr) + px_ + 1), min(img.shape[0], int((y + h) * dpr) + py_ + 1)
    crop = img[y0:y1, x0:x1]
    if crop.size == 0 or min(crop.shape[:2]) < 4:
        return None
    border = np.concatenate([crop[0], crop[-1], crop[:, 0], crop[:, -1]])
    bg = np.median(border, axis=0)
    d = np.linalg.norm(crop - bg, axis=2)
    if d.max() < 20:
        return None
    ink = np.median(crop[d >= np.percentile(d, 97)], axis=0)
    v = ink - bg
    cov = np.clip(((crop - bg) @ v) / float(v @ v), 0, 1)
    ys, xs = np.nonzero(cov > 0.25)
    if len(xs) < 4:
        return None
    return cov[ys.min():ys.max() + 1, xs.min():xs.max() + 1].astype(np.float32)


def compare(target: np.ndarray, cand: np.ndarray) -> tuple[float, float, float]:
    """Shape NCC after fitting cand to target's box, |log width ratio| at equal height, and
    |log ink-mass ratio| in that box (heavier weights put more ink in the same box)."""
    th, tw = target.shape
    ch, cw = cand.shape
    width_err = abs(np.log((cw * th / ch) / tw)) if ch and tw else 9.0
    c = cv2.resize(cand, (tw, th), interpolation=cv2.INTER_AREA)
    k = max(1.0, th / 24)
    density_err = abs(np.log(max(c.sum(), 1e-3) / max(target.sum(), 1e-3)))
    a = cv2.GaussianBlur(target, (0, 0), 0.6 * k)
    b = cv2.GaussianBlur(c, (0, 0), 0.6 * k)
    a, b = a - a.mean(), b - b.mean()
    den = float(np.sqrt((a * a).sum() * (b * b).sum()))
    return (float((a * b).sum()) / den if den > 0 else 0.0), float(width_err), float(density_err)


def score_candidate(target, text: str, family: str, weight: int, px_guess: float) -> tuple[float, float, float]:
    """(family score, weight score, px) for one family/weight: rendered, rescaled to the
    target's ink height, and re-rendered at that size."""
    cand = fontlib.render(family, weight, px_guess, text)
    if cand.shape[0] < 2:
        return -9.0, -9.0, px_guess
    px = px_guess * target.shape[0] / cand.shape[0]
    if abs(px - px_guess) > 0.5:
        cand = fontlib.render(family, weight, px, text)
    ncc, werr, derr = compare(target, cand)
    return ncc - FAMILY_WIDTH * werr, ncc - WEIGHT_WIDTH * werr - WEIGHT_DENSITY * derr, px


def score_family(target, text: str, m: dict, px_guess: float, dpr: float) -> dict | None:
    """Best family score over weights, and the weight/size chosen by the weight score."""
    fam_best, pick = -9.0, None
    for w in fontlib.weights(m):
        if not 200 <= w <= 900:
            continue
        fs, ws, px = score_candidate(target, text, m["family"], w, px_guess)
        fam_best = max(fam_best, fs)
        if pick is None or ws > pick[0]:
            pick = (ws, w, px)
    if pick is None:
        return None
    return {"family": m["family"], "category": m["category"], "weight": pick[1], "px": round(pick[2] / dpr, 1),
            "score": round(fam_best, 4)}


def match_run(img, dpr, run: dict, families: list[dict]) -> dict | None:
    target = coverage(img, run["bbox"], dpr)
    text = run["string"].strip()
    if target is None or len(text.replace(" ", "")) < 1:
        return None
    px_guess = (run.get("font", {}).get("px") or run["bbox"][3] * 0.75) * dpr
    coarse = []
    for m in families:
        ws = fontlib.weights(m)
        best = max((score_candidate(target, text, m["family"], min(ws, key=lambda x: abs(x - w)), px_guess)[0]
                    for w in COARSE_WEIGHTS), default=-9)
        coarse.append((best, m))
    coarse.sort(key=lambda t: -t[0])
    scored = [r for r in (score_family(target, text, m, px_guess, dpr) for _, m in coarse[:KEEP_FAMILIES]) if r]
    scored.sort(key=lambda r: -r["score"])
    return {"string": run["string"], "bbox": run["bbox"], "candidates": scored, "_target": target, "_px": px_guess}


def choose_families(results: list[dict], families: list[dict]) -> list[str]:
    """Families the screen uses: the one winning most runs; a monospace family when mono
    candidates win enough runs together (the best mono by score on those runs); any other
    family winning SECOND_FAMILY_SHARE of runs. At most three."""
    if not results:
        return []
    cat = {m["family"]: m["category"] for m in families}
    wins: dict[str, int] = {}
    for r in results:
        wins[r["candidates"][0]["family"]] = wins.get(r["candidates"][0]["family"], 0) + 1
    ranked = sorted(wins, key=lambda f: -wins[f])
    chosen = [ranked[0]]
    mono_runs = [r for r in results if cat.get(r["candidates"][0]["family"]) == "mono"]
    if cat.get(chosen[0]) != "mono" and len(mono_runs) >= max(2, MONO_SHARE * len(results)):
        totals: dict[str, float] = {}
        for r in mono_runs:
            for c in r["candidates"]:
                if c["category"] == "mono":
                    totals[c["family"]] = totals.get(c["family"], 0.0) + c["score"]
        if totals:
            chosen.append(max(totals, key=totals.get))
    primary = chosen[0]
    for f in ranked[1:]:
        if len(chosen) >= 3:
            break
        if f in chosen or cat.get(f) == "mono" or wins[f] < SECOND_FAMILY_SHARE * len(results):
            continue
        # it must beat the primary clearly on the runs it wins, not by a hair
        won = [r for r in results if r["candidates"][0]["family"] == f]
        margins = []
        for r in won:
            prim = next((c["score"] for c in r["candidates"] if c["family"] == primary), None)
            if prim is not None:
                margins.append(r["candidates"][0]["score"] - prim)
        if margins and float(np.mean(margins)) >= SECOND_FAMILY_MARGIN:
            chosen.append(f)
    return chosen


def match(img, dpr: float, runs: list[dict], families: list[dict]) -> dict:
    results = [r for r in (match_run(img, dpr, run, families) for run in runs) if r]
    by_name = {m["family"]: m for m in families}
    if results:                            # score the most-voted family everywhere first (margins)
        votes: dict[str, int] = {}
        for r in results:
            votes[r["candidates"][0]["family"]] = votes.get(r["candidates"][0]["family"], 0) + 1
        top = max(votes, key=votes.get)
        for r in results:
            if top in by_name and all(c["family"] != top for c in r["candidates"]):
                c = score_family(r["_target"], r["string"].strip(), by_name[top], r["_px"], dpr)
                if c:
                    r["candidates"].append(c)
                    r["candidates"].sort(key=lambda c: -c["score"])
    chosen = choose_families(results, families)
    for r in results:                      # make sure every chosen family was scored on every run
        have = {c["family"] for c in r["candidates"]}
        for f in chosen:
            if f not in have and f in by_name:
                c = score_family(r["_target"], r["string"].strip(), by_name[f], r["_px"], dpr)
                if c:
                    r["candidates"].append(c)
        r["candidates"].sort(key=lambda c: -c["score"])
    wins: dict[str, int] = {}
    for r in results:
        top = r["candidates"][0]["family"]
        wins[top] = wins.get(top, 0) + 1
    out_runs = []
    for r in results:
        pool = [c for c in r["candidates"] if c["family"] in chosen] or r["candidates"][:1]
        best = pool[0]
        alts = [c for c in r["candidates"] if c is not best][:3]
        out_runs.append({"string": r["string"], "bbox": r["bbox"], "family": best["family"], "weight": best["weight"],
                         "px": best["px"], "score": best["score"],
                         "alternatives": [{k: a[k] for k in ("family", "weight", "score")} for a in alts]})
    fams = []
    for f in chosen:
        own = [r for r in out_runs if r["family"] == f]
        margins = [r["score"] - next((a["score"] for a in r["alternatives"] if a["family"] != f), r["score"]) for r in own]
        fams.append({"family": f, "category": by_name[f]["category"] if f in by_name else "sans", "runs": len(own),
                     "wins": wins.get(f, 0),
                     "meanScore": round(float(np.mean([r["score"] for r in own])), 4) if own else None,
                     "agreement": round(float(np.median(margins)), 4) if margins else None})
    primary = fams[0] if fams else None
    outside = bool(primary and primary["agreement"] is not None and primary["runs"] >= 5
                   and primary["agreement"] < OUTSIDE_AGREEMENT)
    return {"runs": out_runs, "families": fams, "outsideCatalog": outside}


def assign(img, dpr: float, runs: list[dict], families: list[dict]) -> list[dict | None]:
    """Family, weight and size for each run, choosing only among `families` (the screen's
    families from match()). Cheap: no coarse pass over the catalog."""
    out = []
    for run in runs:
        target = coverage(img, run["bbox"], dpr)
        text = run["string"].strip()
        if target is None or not text.replace(" ", ""):
            out.append(None)
            continue
        px_guess = (run.get("font", {}).get("px") or run["bbox"][3] * 0.75) * dpr
        scored = [r for r in (score_family(target, text, m, px_guess, dpr) for m in families) if r]
        scored.sort(key=lambda r: -r["score"])
        out.append(scored[0] if scored else None)
    return out


def pick_runs(spec: dict, max_runs: int) -> list[dict]:
    """The longest runs, plus numeric runs (they separate mono from proportional digits)."""
    runs = [t for t in spec.get("text", []) if len(t["string"].replace(" ", "")) >= MIN_CHARS]
    runs.sort(key=lambda t: -len(t["string"]))
    numeric = [t for t in runs if sum(ch.isdigit() for ch in t["string"]) >= 3]
    picked = runs[: max_runs - max_runs // 4]
    for t in numeric:
        if len(picked) >= max_runs:
            break
        if t not in picked:
            picked.append(t)
    return picked


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("fetch", help="download candidate families into the cache")
    f.add_argument("--families", default="", help="comma-separated subset of the catalog, or other google/fonts families")
    b = sub.add_parser("bundle", help="write static TTFs of a cached family for the given weights")
    b.add_argument("family")
    b.add_argument("--weights", default="400,700", help="comma-separated weights (default 400,700)")
    b.add_argument("--out", type=Path, required=True)
    m = sub.add_parser("match", help="identify fonts of the spec's text runs")
    m.add_argument("image", type=Path)
    m.add_argument("--spec", type=Path, required=True)
    m.add_argument("--dpr", type=float, default=None, help="default: spec meta.dpr")
    m.add_argument("--families", default="", help="restrict candidates (comma-separated)")
    m.add_argument("--max-runs", type=int, default=40)
    m.add_argument("--out", type=Path)
    args = ap.parse_args(argv)

    if args.cmd == "fetch":
        wanted = {s.strip() for s in args.families.split(",") if s.strip()}
        missing = []
        known = {e["family"] for e in fontlib.catalog()}
        todo = [e for e in fontlib.catalog() + [{"family": w, "category": "sans"} for w in sorted(wanted - known)]
                if not wanted or e["family"] in wanted]
        with ThreadPoolExecutor(4) as pool:          # ~60 families, a few files each; GitHub rate-limits bursts
            got = list(pool.map(lambda e: fontlib.fetch(e["family"], e["category"]), todo))
        missing = [e["family"] for e, m in zip(todo, got, strict=True) if not m]
        print(f"cache: {fontlib.cache_dir()} ({len(fontlib.available())} families)"
              + (f"; not found: {', '.join(missing)}" if missing else ""))
        if missing and fontlib.NET_ERRORS:
            print(f"[error] downloads from raw.githubusercontent.com failed ({fontlib.NET_ERRORS[0]}). The "
                  "font catalog needs network access to GitHub: allow it (agent sandbox, proxy) and re-run fetch "
                  "until no family is missing; a partial catalog makes the matcher pick a wrong family.",
                  file=sys.stderr)
        return 0 if not missing else 2

    if args.cmd == "bundle":
        if not (fontlib.cache_dir() / fontlib.slug(args.family) / "manifest.json").exists() and not fontlib.fetch(args.family):
            print(f"[error] {args.family} is not in the cache and not on google/fonts", file=sys.stderr)
            return 2
        files = fontlib.bundle(args.family, [int(w) for w in args.weights.split(",")], args.out)
        print(f"{args.out}: {', '.join(files)}")
        return 0

    spec = json.loads(args.spec.read_text())
    dpr = args.dpr or float(spec.get("meta", {}).get("dpr", 1))
    families = fontlib.available()
    wanted = {s.strip() for s in args.families.split(",") if s.strip()}
    if wanted:
        have = {fm["family"] for fm in families}
        for w in wanted - have:                      # cached families outside the catalog
            mf = fontlib.cache_dir() / fontlib.slug(w) / "manifest.json"
            if mf.exists():
                families.append(json.loads(mf.read_text()))
        families = [fm for fm in families if fm["family"] in wanted]
    if not families:
        print("[error] no candidate fonts in the cache; run: python font_match.py fetch", file=sys.stderr)
        return 2
    img = load_rgb(args.image)
    res = match(img, dpr, pick_runs(spec, args.max_runs), families)
    if args.out:
        args.out.write_text(json.dumps(res, indent=1, ensure_ascii=False))
    for fam in res["families"]:
        print(f"{fam['family']:22s} {fam['category']:5s} runs {fam['runs']:3d}  mean score {fam['meanScore']}  agreement {fam['agreement']}")
    if res["outsideCatalog"]:
        print("OUTSIDE THE CATALOG: the runs disagree; the family above is only the nearest substitute")
    for r in res["runs"][:12]:
        alts = ", ".join(f"{a['family']} {a['weight']}" for a in r["alternatives"][:2])
        print(f"  {r['string'][:28]:28s} {r['family']} {r['weight']} {r['px']}px  ({r['score']:.3f}; alt: {alts})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
