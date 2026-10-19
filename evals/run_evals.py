#!/usr/bin/env python3
"""Score generated projects against the eval cases.

Usage:
  python evals/run_evals.py RUNS_DIR [--cases 01,03] [--out RUNS_DIR/results] [--jobs 4]

RUNS_DIR/<case-id>/project/ holds the project an agent produced for evals/cases/<case-id>/
(see evals/README.md, "Running agents"). For every case this runs the skill's check.py with the
case's golden spec and thresholds, then writes:

  RUNS_DIR/results.json   all metrics per case
  RUNS_DIR/results.md     a markdown table (paste into PRs / the README)

Exit codes: 0 all present cases pass, 1 some fail or are missing, 2 error.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CASES = ROOT / "evals" / "cases"
CHECK = ROOT / "skills" / "screenshot-to-qml" / "scripts" / "check.py"


def fmt(v, digits=3):
    return "—" if v is None else (f"{v:.{digits}f}" if isinstance(v, float) else str(v))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("runs", type=Path)
    ap.add_argument("--cases", default="", help="comma-separated id prefixes (default: all)")
    ap.add_argument("--out", type=Path, help="output prefix (default: RUNS_DIR/results)")
    ap.add_argument("--jobs", type=int, default=1, help="cases scored in parallel (each check renders under its own Xvfb)")
    args = ap.parse_args(argv)

    prefixes = [c.strip() for c in args.cases.split(",") if c.strip()]
    cases = sorted(p for p in CASES.iterdir() if p.is_dir() and (not prefixes or p.name.startswith(tuple(prefixes))))
    if not cases:
        print("[error] no cases matched", file=sys.stderr)
        return 2
    def score(case: Path) -> dict:
        project = args.runs / case.name / "project"
        row = {"case": case.name, "status": "missing"}
        if project.is_dir():
            out = args.runs / case.name / "check"
            res = subprocess.run([sys.executable, str(CHECK), str(project), "--source", str(case / "input.png"),
                                  "--spec", str(case / "golden-spec.json"), "--thresholds", str(case / "thresholds.json"),
                                  "--out-dir", str(out)], capture_output=True, text=True, timeout=900)
            row["status"] = {0: "pass", 1: "fail"}.get(res.returncode, "error")
            summary = out / "summary.json"
            if summary.exists():
                s = json.loads(summary.read_text())
                row.update(s.get("metrics") or {})
                row["gates"] = "pass" if s.get("gates") else "fail"
            if res.returncode == 2:
                row["error"] = (res.stdout + res.stderr)[-400:]
        print(f"{case.name:24s} {row['status']}", flush=True)
        return row

    with ThreadPoolExecutor(max_workers=max(1, args.jobs)) as pool:
        rows = list(pool.map(score, cases))

    prefix = args.out or (args.runs / "results")
    prefix.parent.mkdir(parents=True, exist_ok=True)
    Path(f"{prefix}.json").write_text(json.dumps(rows, indent=1, ensure_ascii=False))
    lines = ["| Case | Status | Global SSIM | Worst region | ΔE max | Geometry max px | Text found | Text on target | Text max off px | Gates |",
             "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for r in rows:
        lines.append(f"| {r['case']} | {r['status']} | {fmt(r.get('globalSSIM'), 4)} | {fmt(r.get('regionSSIMMin'))} | "
                     f"{fmt(r.get('colorDeltaEMax'), 2)} | {fmt(r.get('geometryMaxPx'), 2)} | {fmt(r.get('textMatchRate'))} | "
                     f"{fmt(r.get('textOnTargetRate'))} | "
                     f"{fmt(r.get('textMaxOffsetPx'), 2)} | {r.get('gates', '—')} |")
    present = [r for r in rows if r["status"] != "missing"]
    passed = sum(r["status"] == "pass" for r in present)
    lines.append(f"\n{passed}/{len(present)} passing ({len(rows) - len(present)} missing)")
    Path(f"{prefix}.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0 if present and passed == len(present) == len(rows) else 1


if __name__ == "__main__":
    sys.exit(main())
