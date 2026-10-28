#!/usr/bin/env python3
"""One-shot verification: render -> pixel/structure diff -> quality gates.

Usage:
  python check.py PROJECT_DIR --source input.png --spec design-spec.json
                  [--thresholds thresholds.json] [--out-dir PROJECT_DIR/.check]
                  [--mode production|fidelity] [--backend backend.py] [--no-interact]
                  [--qt /path/to/Qt/6.8.3/gcc_64] [--no-cpp]

Size, DPR and profile come from spec.meta (designSize, dpr, profile). The render also drives
the window with Tab, hover and press (render.py --interact; hover is skipped on touch
profiles) for the a11y and states gates. The embedded-sw profile renders with the software
scene graph, as the device will. When the project has a C++ host (CMakeLists.txt), it is
built, run and grabbed at the same size (build_cpp.py) and compared with the PySide6 render
(the cpp gate); without a Qt SDK that gate is skipped with a note. A Qt 5.15 project
(meta.minQt 5.15) renders here with PySide6 through assets/qt5-shim; its C++ host built
against Qt 5.15 is the real 5.15 run. Writes to --out-dir:
  render.png  scene.json  interaction.json  diff.png  report.json  gate.json  summary.json
  worst.png   (when the diff fails) source and render crops of the worst items, side by side
  cpp.png  cpp.json  cpp-build/   (C++ host)

Prints one PASS/FAIL line per stage and the worst regions to fix next. Look at worst.png, not
at the full render or crops of your own.
Exit codes: 0 everything passes, 1 a stage failed, 2 could not run.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def run(cmd: list[str]) -> int:
    res = subprocess.run(cmd, capture_output=True, text=True)
    sys.stdout.write(res.stdout)
    if res.returncode not in (0, 1):
        sys.stderr.write(res.stderr)
    return res.returncode


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("project", type=Path)
    ap.add_argument("--source", type=Path, required=True)
    ap.add_argument("--spec", type=Path, required=True)
    ap.add_argument("--thresholds", type=Path)
    ap.add_argument("--out-dir", type=Path)
    ap.add_argument("--mode", choices=["production", "fidelity"], default="production")
    ap.add_argument("--backend", type=Path)
    ap.add_argument("--no-interact", action="store_true", help="skip the keyboard/pointer probe (a11y, states)")
    ap.add_argument("--qt", type=Path, help="Qt prefix for the C++ host (else $QT_DIR or the system Qt; "
                    "Qt 5.15 for a --min-qt 5.15 project)")
    ap.add_argument("--no-cpp", action="store_true", help="do not build the C++ host")
    args = ap.parse_args(argv)

    spec = json.loads(args.spec.read_text())
    w, h = spec["meta"]["designSize"]
    dpr = spec["meta"].get("dpr", 1)
    out = (args.out_dir or args.project / ".check").resolve()
    out.mkdir(parents=True, exist_ok=True)
    for stale in ("render.png", "scene.json", "interaction.json", "report.json", "diff.png", "worst.png", "gate.json", "summary.json",
                  "cpp.png", "cpp.json"):
        (out / stale).unlink(missing_ok=True)     # never report an older run's numbers
    py = sys.executable

    print("== render")
    cmd = [py, str(HERE / "render.py"), str(args.project), "--size", str(w), str(h), "--dpr", str(dpr),
           "--out", str(out / "render.png"), "--scene", str(out / "scene.json")]
    if args.backend:
        cmd += ["--backend", str(args.backend)]
    profile = spec["meta"].get("profile", "desktop")
    if profile == "embedded-sw":
        cmd += ["--scenegraph", "software"]
    if not args.no_interact:
        cmd += ["--interact", "--interaction", str(out / "interaction.json")]
        if profile in ("embedded-gpu", "embedded-sw"):
            cmd.append("--no-hover")
    rc = run(cmd)
    if rc not in (0, 1, 2):         # a crash (SIGSEGV/SIGABRT), not a QML error: retry without the idle scan
        print(f"[warn] render crashed (exit {rc}); rendering again without the idle-animation scan")
        rc = run(cmd + ["--no-idle-scan"])
    if rc == 2:
        print("FAIL render (QML did not load; fix the errors above first)")
        return 2

    print("== diff")
    cmd = [py, str(HERE / "diff.py"), str(args.source), str(out / "render.png"), "--spec", str(args.spec),
           "--scene", str(out / "scene.json"), "--out", str(out / "report.json"), "--heatmap", str(out / "diff.png")]
    if args.thresholds:
        cmd += ["--thresholds", str(args.thresholds)]
    diff_rc = run(cmd)
    if diff_rc == 2:
        print("ERROR diff (see the message above)")
        return 2
    if diff_rc == 1 and (out / "report.json").exists():
        import sheet
        try:
            n = sheet.compare_sheet(args.source, out / "render.png", spec,
                                    json.loads((out / "report.json").read_text(encoding="utf-8")), out / "worst.png")
            if n:
                print(f"worst items, source | render: {out / 'worst.png'} ({n})")
        except (OSError, KeyError, ValueError) as e:
            print(f"[warn] worst.png not written: {e}")

    cpp_json = None
    if (args.project / "CMakeLists.txt").exists() and not args.no_cpp:
        print("== C++ host")
        cmd = [py, str(HERE / "build_cpp.py"), str(args.project), "--build-dir", str(out / "cpp-build"),
               "--grab", str(out / "cpp.png"), "--size", str(w), str(h), "--dpr", str(dpr),
               "--compare", str(out / "render.png"), "--json", str(out / "cpp.json"),
               "--cmake-arg", f"S2Q_PROFILE={profile}"]      # render both hosts the same way
        if args.qt:
            cmd += ["--qt", str(args.qt)]
        run(cmd)
        cpp_json = out / "cpp.json"

    print("== quality gates")
    cmd = [py, str(HERE / "quality_gate.py"), str(args.project), "--scene", str(out / "scene.json"),
           "--interaction", str(out / "interaction.json"), "--profile", profile,
           "--source", str(args.source), "--mode", args.mode, "--out", str(out / "gate.json"),
           "--min-qt", str(spec["meta"].get("minQt", "6.8"))]
    if cpp_json is not None:
        cmd += ["--cpp", str(cpp_json)]
    gate_rc = run(cmd)

    ok = diff_rc == 0 and gate_rc == 0
    summary = {"pass": ok, "diff": diff_rc == 0, "gates": gate_rc == 0,
               "metrics": json.loads((out / "report.json").read_text())["metrics"] if (out / "report.json").exists() else None}
    (out / "summary.json").write_text(json.dumps(summary, indent=1))
    print(f"== {'PASS' if ok else 'FAIL'}  (artifacts in {out})")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
