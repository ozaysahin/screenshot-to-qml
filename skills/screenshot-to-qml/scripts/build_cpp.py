#!/usr/bin/env python3
"""Build a project's C++ host with CMake, run it, and grab a frame.

Usage:
  python build_cpp.py PROJECT_DIR [--qt /path/to/Qt/6.8.3/gcc_64] [--build-dir DIR] [--config Release]
                      [--grab out.png --size W H [--dpr 2] [--lang xx]] [--compare render.png]
                      [--install DIR] [--json cpp.json]

PROJECT_DIR holds CMakeLists.txt + src/main.cpp (scaffold.py --target cpp, or --add-host cpp).
Qt is found through --qt, $QT_DIR, $Qt6_DIR / $Qt5_DIR or CMAKE_PREFIX_PATH, else the system's Qt
(Qt 6.8+, or Qt 5.15 for a project scaffolded with --min-qt 5.15: the real 5.15 run of its QML).

Steps:
  configure  cmake -S PROJECT -B BUILD (Ninja when available)
  build      cmake --build; compiler and qmlcachegen warnings are counted
  grab       runs the binary with APP_GRAB (see src/main.cpp) at --size × --dpr, under Xvfb on
             headless Linux (GPU path) — the same frame render.py takes from the PySide6 host
  compare    SSIM of the grab against another render (the PySide6 one): both hosts run the same
             qml/ tree and normally match at 1.000; below 0.98 fails (exit 1): a file missing
             from the binary (an image outside qml/ or assets/, a folder without qmldir) or a
             C++-only difference. A Qt 5.15 host is compared by blurred 32-px tiles instead
             (text lays out up to ~2 px differently in Qt 5); a tile above 24 fails
  install    cmake --install BUILD --prefix DIR (bundles Qt when it comes from an SDK)

Writes a JSON report (--json): {configured, built, warnings, binary, grab: {...}, parity, installed}.
Exit codes: 0 ok, 1 built but the run, the QML or the parity check failed, 2 could not build.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path


def qt_prefix(arg: Path | None) -> str | None:
    for cand in (arg, os.environ.get("QT_DIR"), os.environ.get("Qt6_DIR"), os.environ.get("Qt5_DIR")):
        if cand:
            return str(Path(cand).resolve())
    return None


def run(cmd, cwd=None, env=None, timeout=1800):
    t = time.time()
    res = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout)
    return res, round(time.time() - t, 1)


def binary_name(build: Path, project: Path) -> Path | None:
    text = (project / "CMakeLists.txt").read_text()
    m = re.search(r'OUTPUT_NAME\s+"?([A-Za-z0-9_.-]+)"?', text)
    names = [m.group(1)] if m else []
    names.append("app")
    for n in names:
        for cand in (build / n, build / f"{n}.exe", build / "Release" / f"{n}.exe", build / f"{n}.app" / "Contents" / "MacOS" / n):
            if cand.exists():
                return cand
    return None


def ssim(a: Path, b: Path) -> float | None:
    try:
        import cv2
        from skimage.metrics import structural_similarity
    except ImportError:
        return None
    x, y = cv2.imread(str(a), cv2.IMREAD_GRAYSCALE), cv2.imread(str(b), cv2.IMREAD_GRAYSCALE)
    if x is None or y is None or x.shape != y.shape:
        return None
    return float(structural_similarity(x, y))


# Qt 5.15 vs the Qt 6 (PySide6) render: text lays out up to ~2 px differently, so a plain SSIM
# says little. Compare blurred 32-px tiles instead: a missing image, icon or panel moves a tile
# far more than text drift does (gallery: drift peaks at ~18, a missing 30-px icon at ~28).
QT5_TILE_LIMIT = 24.0


def tile_diff(a: Path, b: Path, tile: int = 32, blur: int = 7) -> float | None:
    """Largest mean |a - b| (0-255) over tile×tile blocks of the blurred frames."""
    try:
        import cv2
        import numpy as np
    except ImportError:
        return None
    x, y = cv2.imread(str(a)), cv2.imread(str(b))
    if x is None or y is None or x.shape != y.shape:
        return None
    d = np.abs(cv2.GaussianBlur(x, (blur, blur), 0).astype(np.float32)
               - cv2.GaussianBlur(y, (blur, blur), 0).astype(np.float32)).mean(axis=2)
    h, w = d.shape
    return float(max(d[r:r + tile, c:c + tile].mean() for r in range(0, h, tile) for c in range(0, w, tile)))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("project", type=Path)
    ap.add_argument("--qt", type=Path, help="Qt prefix (the folder with lib/cmake/Qt6)")
    ap.add_argument("--build-dir", type=Path)
    ap.add_argument("--config", default="Release")
    ap.add_argument("--grab", type=Path)
    ap.add_argument("--size", type=int, nargs=2, metavar=("W", "H"))
    ap.add_argument("--dpr", type=float, default=1.0)
    ap.add_argument("--lang")
    ap.add_argument("--wait-ms", type=int, default=500)
    ap.add_argument("--compare", type=Path, help="another render of the same screen (PySide6 host)")
    ap.add_argument("--install", type=Path, help="cmake --install into this folder")
    ap.add_argument("--json", type=Path)
    ap.add_argument("--cmake-arg", action="append", default=[], help="extra -D… for configure")
    args = ap.parse_args(argv)

    project = args.project.resolve()
    report: dict = {"project": str(project), "configured": False, "built": False}

    def done(code: int) -> int:
        report["exit"] = code
        if args.json:
            args.json.parent.mkdir(parents=True, exist_ok=True)
            args.json.write_text(json.dumps(report, indent=1))
        return code

    if not (project / "CMakeLists.txt").exists():
        print(f"[error] {project} has no CMakeLists.txt (scaffold.py --add-host cpp)", file=sys.stderr)
        report["error"] = "no CMakeLists.txt"
        return done(2)
    cmake = shutil.which("cmake")
    if not cmake:
        print("[error] cmake not found", file=sys.stderr)
        report["error"] = "cmake not found"
        return done(2)
    prefix = qt_prefix(args.qt)
    report["qtPrefix"] = prefix
    qt5 = "find_package(Qt5" in (project / "CMakeLists.txt").read_text()
    report["qtMajor"] = 5 if qt5 else 6
    build = (args.build_dir or project / "build").resolve()
    cfg = [cmake, "-S", str(project), "-B", str(build), f"-DCMAKE_BUILD_TYPE={args.config}"]
    if shutil.which("ninja") and not (build / "CMakeCache.txt").exists():
        cfg += ["-G", "Ninja"]
    if prefix:
        cfg.append(f"-DCMAKE_PREFIX_PATH={prefix}")
    cfg += [f"-D{a}" for a in args.cmake_arg]
    env = dict(os.environ, LANG=os.environ.get("LANG") or "C.UTF-8")

    res, secs = run(cfg, env=env)
    report["configureSeconds"] = secs
    if res.returncode != 0:
        tail = (res.stdout + res.stderr).strip().splitlines()[-25:]
        print("[error] configure failed:\n  " + "\n  ".join(tail), file=sys.stderr)
        report["error"] = "configure failed"
        report["log"] = tail
        log = res.stdout + res.stderr
        if re.search(r'provided by\s+"Qt[56]"|Qt[56]_FOUND to FALSE|Failed to find required Qt component|'
                     r'Could not find a (?:configuration file for )?package', log):
            need = "Qt 5.15 (qtdeclarative5-dev / the board SDK)" if qt5 else "Qt 6.8+"
            report["error"] = f"{need} CMake package not found or incomplete (pass --qt or set QT_DIR)"
        return done(2)
    report["configured"] = True
    cfg_warn = len(re.findall(r"CMake Warning", res.stdout + res.stderr))

    res, secs = run([cmake, "--build", str(build), "--config", args.config, "--parallel"], env=env)
    report["buildSeconds"] = secs
    out = res.stdout + res.stderr
    warn_lines = [ln.strip() for ln in out.splitlines()
                  if re.search(r"\bwarning\b|Warning:", ln, re.I) and "locale" not in ln.lower()]
    report["warnings"] = {"cmake": cfg_warn, "build": len(warn_lines), "samples": warn_lines[:10]}
    if res.returncode != 0:
        tail = [ln for ln in out.splitlines() if "error" in ln.lower()][:20] or out.splitlines()[-20:]
        print("[error] build failed:\n  " + "\n  ".join(tail), file=sys.stderr)
        report["error"] = "build failed"
        report["log"] = tail
        return done(2)
    report["built"] = True
    binary = binary_name(build, project)
    report["binary"] = str(binary) if binary else None
    print(f"built {binary} in {report['buildSeconds']} s ({len(warn_lines)} warnings)")
    code = 0

    if args.grab:
        if not binary:
            print("[error] built, but the executable was not found", file=sys.stderr)
            report["error"] = "executable not found after the build"
            report["grab"] = {"ok": False, "qmlWarnings": [], "stderr": ["executable not found after the build"]}
            return done(2)
        if not args.size:
            print("[error] --grab needs --size W H", file=sys.stderr)
            return done(2)
        w, h = args.size
        grab = args.grab.resolve()
        grab.parent.mkdir(parents=True, exist_ok=True)
        grab.unlink(missing_ok=True)
        # Qt 6 already rounds scale factors PassThrough (1.25 stays 1.25); setting the variable
        # only makes Qt warn that the policy was set too late
        genv = dict(env, APP_GRAB=str(grab), APP_GRAB_SIZE=f"{w}x{h}", APP_GRAB_WAIT_MS=str(args.wait_ms),
                    QT_SCALE_FACTOR=f"{args.dpr:g}")
        genv.pop("QT_SCALE_FACTOR_ROUNDING_POLICY", None)
        if "cv2" in genv.get("QT_QPA_PLATFORM_PLUGIN_PATH", ""):   # set by `import cv2` (opencv-python's own Qt)
            genv.pop("QT_QPA_PLATFORM_PLUGIN_PATH")
        if qt5:     # Qt 5 adds a factor from the screen's DPI (Xvfb: 1.04); the grab uses QT_SCALE_FACTOR only
            genv["QT_ENABLE_HIGHDPI_SCALING"] = "0"
        if args.lang:
            genv["APP_LANG"] = args.lang
        cmd = [str(binary)]
        headless = platform.system() == "Linux" and not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))
        if headless and shutil.which("xvfb-run"):
            sw, sh = int(w * args.dpr) + 64, int(h * args.dpr) + 64
            cmd = ["xvfb-run", "-a", "-n", str(100 + (os.getpid() * 7919) % 20000), "-s", f"-screen 0 {sw}x{sh}x24"] + cmd
        elif headless:
            genv["QT_QPA_PLATFORM"] = "offscreen"
        res, secs = run(cmd, cwd=str(binary.parent), env=genv, timeout=300)
        qml_warn = [ln[6:] for ln in res.stderr.splitlines() if ln.startswith("[qml] ")]
        report["grab"] = {"file": str(grab), "ok": res.returncode == 0 and grab.exists(), "seconds": secs,
                          "qmlWarnings": qml_warn, "stdout": res.stdout.strip()[-400:],
                          "stderr": [ln for ln in res.stderr.splitlines() if not ln.startswith("app: font")][-15:]}
        if not report["grab"]["ok"]:
            print(f"[error] the binary did not produce a frame (exit {res.returncode}):\n  "
                  + "\n  ".join(report["grab"]["stderr"]), file=sys.stderr)
            code = 1
        else:
            print(res.stdout.strip())
            for m in qml_warn:
                print(f"[qml] {m}", file=sys.stderr)
            if qml_warn:
                code = 1
        if args.compare and grab.exists():
            v = ssim(grab, args.compare)
            report["parity"] = {"against": str(args.compare), "ssim": None if v is None else round(v, 5)}
            if qt5:
                t = tile_diff(grab, args.compare)
                report["parity"].update(qt=5, maxTileDiff=None if t is None else round(t, 1), limit=QT5_TILE_LIMIT)
                print(f"parity with {args.compare.name} (Qt 5.15 vs Qt 6): SSIM {v:.4f}, max tile difference {t:.1f} "
                      f"(limit {QT5_TILE_LIMIT:g})" if v is not None and t is not None else "parity: sizes differ")
                if t is None or t > QT5_TILE_LIMIT:
                    code = 1
            else:
                print(f"parity with {args.compare.name}: SSIM {v:.5f}" if v is not None else "parity: sizes differ")
                if v is None or v < 0.98:
                    code = 1

    if args.install:
        res, secs = run([cmake, "--install", str(build), "--prefix", str(args.install.resolve()), "--config", args.config], env=env)
        report["installed"] = res.returncode == 0
        report["installSeconds"] = secs
        if res.returncode != 0:
            print("[error] install failed:\n  " + "\n  ".join((res.stdout + res.stderr).splitlines()[-15:]), file=sys.stderr)
            code = max(code, 1)
        else:
            print(f"installed to {args.install}")
    return done(code)


if __name__ == "__main__":
    sys.exit(main())
