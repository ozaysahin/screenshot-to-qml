#!/usr/bin/env python3
"""Compare scored run sets (e.g. baseline, skill vX, skill vY) case by case.

Usage:
  python evals/compare_runs.py RUNS_A RUNS_B [RUNS_C ...] [--labels a b c] [--out comparison.md]
                               [--results results]

Every folder must already be scored with run_evals.py (RUNS_X/<results>.json and
RUNS_X/<case>/check/{gate,report,interaction}.json). Writes a markdown report: a summary
table (full passes, visual passes, gate errors by kind, keyboard/accessibility counts, mean
scores) and a per-case table, and prints it.

Exit codes: 0 ok, 2 error.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from statistics import mean

GATES = ("lint", "format", "runtime", "hardcode", "embed", "fonts", "webengine", "a11y", "states", "i18n")
NAMES = {"lint": "Lint errors (qmllint)", "format": "Files not qmlformat-clean", "runtime": "Runtime QML warnings",
         "hardcode": "Hard-coded colors/fonts outside Theme", "embed": "Screenshot embedded",
         "fonts": "Font errors", "webengine": "Web engine used", "a11y": "Accessibility errors",
         "states": "Controls without a visible pressed state", "i18n": "Strings not wrapped in qsTr()"}


def load(runs: Path, results: str) -> dict:
    res = runs / f"{results}.json"
    if not res.exists():
        raise SystemExit(f"[error] {res} not found; run evals/run_evals.py {runs} first")
    rows = {r["case"]: r for r in json.loads(res.read_text())}
    for case, r in rows.items():
        check = runs / case / "check"
        r["gateErrors"] = {}
        if (check / "gate.json").exists():
            g = json.loads((check / "gate.json").read_text())["gates"]
            r["gateErrors"] = {k: len(g.get(k, {}).get("errors", [])) for k in GATES}
        r["diffPass"] = json.loads((check / "report.json").read_text()).get("pass") if (check / "report.json").exists() else None
        r["controls"] = r["reached"] = r["fakeButtons"] = 0
        if (check / "interaction.json").exists():
            it = json.loads((check / "interaction.json").read_text())
            enabled = [c for c in it["controls"] if c["enabled"]]
            r["controls"] = len(enabled)
            r["reached"] = sum(c["tabReached"] and c["focusVisible"] is not False for c in enabled)
            r["fakeButtons"] = sum(m.get("clickable", True) and not m.get("accessibleControl") for m in it["mouseAreas"])
        qml = list((runs / case / "project").rglob("*.qml")) if (runs / case / "project").is_dir() else []
        r["qmlFiles"] = len(qml)
        r["qmlLines"] = sum(len(p.read_text(errors="ignore").splitlines()) for p in qml)
    return rows


def summarize(rows: dict) -> dict:
    present = [r for r in rows.values() if r.get("status") not in ("missing", "error")]

    def avg(key):
        vals = [r[key] for r in present if r.get(key) is not None]
        return mean(vals) if vals else float("nan")

    return {
        "cases": len(present),
        "pass": sum(r["status"] == "pass" for r in present),
        "visualPass": sum(bool(r.get("diffPass")) for r in present),
        "gatesPass": sum(r.get("gates") == "pass" for r in present),
        "globalSSIM": avg("globalSSIM"), "regionMin": avg("regionSSIMMin"), "textOnTarget": avg("textOnTargetRate"),
        "errors": {k: sum(r["gateErrors"].get(k, 0) for r in present) for k in GATES},
        "controls": sum(r["controls"] for r in present), "reached": sum(r["reached"] for r in present),
        "fakeButtons": sum(r["fakeButtons"] for r in present),
        "qmlFiles": avg("qmlFiles"), "qmlLines": avg("qmlLines"),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("runs", type=Path, nargs="+")
    ap.add_argument("--labels", nargs="+", default=None)
    ap.add_argument("--results", default="results", help="results file stem inside each folder (default: results)")
    ap.add_argument("--out", type=Path)
    args = ap.parse_args(argv)
    if len(args.runs) < 2:
        print("[error] give at least two run folders", file=sys.stderr)
        return 2
    labels = args.labels or [p.name for p in args.runs]
    if len(labels) != len(args.runs):
        print("[error] one label per run folder", file=sys.stderr)
        return 2
    sets = [load(p, args.results) for p in args.runs]
    sums = [summarize(s) for s in sets]

    def row(title, fn):
        return f"| {title} | " + " | ".join(fn(s) for s in sums) + " |"

    L = [f"# {' vs '.join(labels)}", "", "| | " + " | ".join(labels) + " |", "| --- |" + " --- |" * len(labels),
         row("**Full pass** (visual + all gates)", lambda s: f"**{s['pass']}/{s['cases']}**"),
         row("Visual checks pass", lambda s: f"{s['visualPass']}/{s['cases']}"),
         row("All quality gates pass", lambda s: f"{s['gatesPass']}/{s['cases']}"),
         row("Mean global SSIM", lambda s: f"{s['globalSSIM']:.4f}"),
         row("Mean worst-region SSIM", lambda s: f"{s['regionMin']:.3f}"),
         row("Text on target (≤ 2 px)", lambda s: f"{s['textOnTarget']:.1%}"),
         row("Real controls (Template-based, enabled)", lambda s: str(s["controls"])),
         row("… reachable with Tab, focus visible", lambda s: f"{s['reached']}/{s['controls']}"),
         row("MouseArea used as a button", lambda s: str(s["fakeButtons"]))]
    for k in GATES:
        if any(s["errors"][k] for s in sums):
            L.append(row(f"{NAMES[k]} (total)", lambda s, k=k: str(s["errors"][k])))
    L += [row("QML files / lines per project", lambda s: f"{s['qmlFiles']:.0f} / {s['qmlLines']:.0f}"), "",
          "## Per case", "",
          "| Case | Global SSIM | Worst region | Text on target | Gate errors | Result |",
          "| --- | --- | --- | --- | --- | --- |"]

    def f(r, k, d=3):
        v = r.get(k)
        return "—" if v is None else f"{v:.{d}f}"

    for case in sorted(set().union(*sets)):
        rs = [s.get(case, {}) for s in sets]
        L.append(f"| {case} | " + " → ".join(f(r, "globalSSIM", 4) for r in rs) + " | "
                 + " → ".join(f(r, "regionSSIMMin") for r in rs) + " | "
                 + " → ".join(f(r, "textOnTargetRate") for r in rs) + " | "
                 + " → ".join(str(sum(r.get("gateErrors", {}).values())) for r in rs) + " | "
                 + " → ".join(r.get("status", "—") for r in rs) + " |")
    L.append(f"\nPer-case columns read {' → '.join(labels)}.")
    text = "\n".join(L) + "\n"
    if args.out:
        args.out.write_text(text)
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
