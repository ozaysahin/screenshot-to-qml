#!/usr/bin/env python3
"""Package a project for its target: a desktop bundle, or a kiosk service on an embedded board.

Usage:
  python deploy.py PROJECT_DIR --target pyside6|cpp --platform desktop|device
                   [--name "Dolum HMI"] [--profile desktop|embedded-gpu|embedded-sw]
                   (--name defaults to the app name the hosts were generated with)
                   [--display eglfs|linuxfb|wayland|xcb] [--gpu kms|jetson]
                   [--user kiosk] [--prefix /opt/<slug>] [--mode onefile|standalone]
                   [--qt /path/to/Qt] [--build]

desktop (writes, and with --build runs):
  pyside6  pysidedeploy.spec for pyside6-deploy (Nuitka): the qml/, assets/, i18n/ and mock/
           folders are shipped as data next to main.py (pyside6-deploy's own qml_files list
           misses qmldir files and fonts); checks, C++ sources and builds are left out;
           --build → dist/<name>.dist/ (standalone, default) or dist/<name>.bin|.exe (onefile)
  cpp      cmake build + `cmake --install` into dist/; the binary carries the QML, fonts and
           translations, and Qt is bundled when it comes from an SDK (online installer, aqt)

device (Linux boards such as Raspberry Pi and Jetson; writes deploy/device/):
  app.env        Qt platform settings: eglfs (GPU, full screen without a compositor), linuxfb
                 (no GPU; the embedded-sw default) or a compositor (wayland, xcb); cursor
                 hidden, software scene graph for embedded-sw
  kms.json       eglfs_kms output config (which connector, which mode) when --display eglfs
  <slug>.service systemd unit: starts on boot on the console, restarts on crash
  install.sh     run on the board: copies the app to --prefix, creates a venv with PySide6
                 (pyside6) or builds with the board's Qt (cpp), installs and starts the service
The profile defaults to design-spec.json's meta.profile (PROJECT or its parent), else the
profile the hosts were generated with.

Exit codes: 0 ok, 1 --build failed, 2 error.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import stat
import subprocess
import sys
import unicodedata
from pathlib import Path

HERE = Path(__file__).resolve().parent


def slug(name: str) -> str:
    """ASCII file/target name: 'Hat 3 Dolum Çay' -> 'hat-3-dolum-cay' (ı/İ → i, accents dropped)."""
    ascii_name = unicodedata.normalize("NFKD", name.replace("ı", "i").replace("İ", "I")).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", ascii_name.lower()).strip("-") or "app"


def guess_profile(project: Path) -> str:
    for cand in (project / "design-spec.json", project.parent / "design-spec.json"):
        if cand.exists():
            try:
                return json.loads(cand.read_text()).get("meta", {}).get("profile", "desktop")
            except json.JSONDecodeError:
                pass
    return host_profile(project) or "desktop"


def host_profile(project: Path) -> str | None:
    """The profile a host was generated with (main.py APP_PROFILE, CMake S2Q_PROFILE)."""
    for f, rx in (("main.py", r'APP_PROFILE = "([a-z-]+)"'), ("CMakeLists.txt", r'set\(S2Q_PROFILE "([a-z-]+)"')):
        path = project / f
        m = re.search(rx, path.read_text()) if path.exists() else None
        if m and m.group(1) in ("desktop", "embedded-gpu", "embedded-sw"):
            return m.group(1)
    return None


def app_name(project: Path) -> str:
    """The name the hosts were generated with (scaffold --name), else the folder name."""
    for f, rx in (("CMakeLists.txt", r'APP_NAME="([^"]+)"'), ("main.py", r'setApplicationName\("([^"]+)"\)')):
        path = project / f
        m = re.search(rx, path.read_text()) if path.exists() else None
        if m and m.group(1).strip():
            return m.group(1)
    return project.name


def cpp_output_name(project: Path, fallback: str) -> str:
    """The executable's name: CMake OUTPUT_NAME (scaffold writes it), else the fallback."""
    m = re.search(r'OUTPUT_NAME\s+"?([A-Za-z0-9_.-]+)"?', (project / "CMakeLists.txt").read_text()) \
        if (project / "CMakeLists.txt").exists() else None
    return m.group(1) if m else fallback


# ------------------------------------------------------------------ desktop

def pyside6_spec(project: Path, name: str, mode: str) -> Path:
    spec = project / "pysidedeploy.spec"
    if not spec.exists():
        exe = shutil.which("pyside6-deploy")
        if not exe:
            raise SystemExit("[error] pyside6-deploy not found (pip install PySide6)")
        res = subprocess.run([exe, "--init", "main.py"], cwd=project, capture_output=True, text=True)
        if not spec.exists():
            raise SystemExit(f"[error] pyside6-deploy --init failed:\n{res.stdout}{res.stderr}")
    text = spec.read_text()
    data = [d for d in ("qml", "assets", "i18n", "mock") if (project / d).is_dir()]
    extra = " ".join(f"--include-data-dir={d}={d}" for d in data)

    def setkey(section: str, key: str, value: str) -> None:
        nonlocal text
        block = re.search(rf"(?ms)^\[{section}\]\n(.*?)(?=^\[|\Z)", text)
        if not block:
            text += f"\n[{section}]\n{key} = {value}\n"
            return
        body = block.group(1)
        if re.search(rf"(?m)^{re.escape(key)}\s*=", body):
            body2 = re.sub(rf"(?m)^{re.escape(key)}\s*=.*$", f"{key} = {value}", body)
        else:
            body2 = body.rstrip("\n") + f"\n{key} = {value}\n\n"
        text = text[:block.start(1)] + body2 + text[block.end(1):]

    setkey("app", "title", name)
    setkey("app", "exec_directory", "dist")
    icon = next((p for p in (project / "assets" / "icon.png", project / "assets" / "icon.ico") if p.exists()), None)
    if icon:
        setkey("app", "icon", str(icon.relative_to(project)))
    # leave out the QML modules the UI never imports (Qt 3D, Charts, WebEngine … are 100+ MB)
    used = set()
    for f in (project / "qml").rglob("*.qml"):
        used |= set(re.findall(r"(?m)^\s*import\s+(Qt[A-Za-z0-9]*)", f.read_text()))
    heavy = ["Qt3D", "QtQuick3D", "QtCharts", "QtDataVisualization", "QtGraphs", "QtLocation", "QtPositioning",
             "QtMultimedia", "QtWebEngine", "QtWebView", "QtWebChannel", "QtWebSockets", "QtSensors", "QtTest",
             "QtRemoteObjects", "QtScxml", "QtTextToSpeech", "QtBluetooth", "QtNfc", "QtSpatialAudio", "Qt5Compat",
             "QtQuickUltralite", "QtVirtualKeyboard", "QtCanvasPainter"]
    setkey("qt", "excluded_qml_plugins", ",".join(h for h in heavy if h not in used))
    setkey("nuitka", "mode", mode)
    # pyside6-deploy adds every project subfolder as data: keep the C++ host, builds and
    # packaging files out of the bundle
    skip = " ".join(f"--noinclude-data-files={d}" for d in ("src", "cmake", "build", "deploy", "dist"))
    setkey("nuitka", "extra_args", f"--quiet --noinclude-qt-translations {extra} {skip}")
    spec.write_text(text)
    return spec


def desktop(args, project: Path, name: str) -> int:
    if args.target == "pyside6":
        spec = pyside6_spec(project, name, args.mode)
        print(f"wrote {spec.relative_to(project)} (data: qml, assets, i18n, mock; mode {args.mode})")
        if args.build:
            import time
            start = time.time()
            cmd = [shutil.which("pyside6-deploy") or "pyside6-deploy", "-c", str(spec), "-f"]
            res = subprocess.run(cmd, cwd=project)
            # pyside6-deploy can exit 0 when Nuitka failed: trust only fresh output
            dist = project / "dist"
            built = [p for p in dist.glob(f"{name}*") if p.stat().st_mtime >= start] if dist.exists() else []
            if res.returncode != 0 or not built:
                print("[error] pyside6-deploy produced nothing (see its output above)", file=sys.stderr)
                return 1
            print(f"built {', '.join(str(p.relative_to(project)) for p in built)}")
        return 0
    cmd = [sys.executable, str(HERE / "build_cpp.py"), str(project), "--install", str(project / "dist")]
    if args.qt:
        cmd += ["--qt", str(args.qt)]
    if not args.build:
        print("C++ desktop bundle: python build_cpp.py PROJECT --install PROJECT/dist (run with --build)")
        return 0
    if subprocess.call(cmd) != 0:
        return 1
    if is_qt5(project):     # Qt 5 has no CMake deploy step: run the platform's deploy tool when the SDK has it
        bins = [Path(args.qt) / "bin"] if args.qt else []
        tool = next((str(b / t) for b in bins for t in ("windeployqt.exe", "windeployqt", "macdeployqt")
                     if (b / t).exists()), None) or shutil.which("windeployqt") or shutil.which("macdeployqt")
        dist = project / "dist"
        target = None
        if tool:
            target = next(dist.rglob("*.exe"), None) if "windeployqt" in tool else next(dist.rglob("*.app"), None)
        if tool and target:
            return 0 if subprocess.call([tool, "--qmldir", str(project / "qml"), str(target)]) == 0 else 1
        print("Qt 5.15: the binary is in dist/; bundle Qt with windeployqt / macdeployqt --qmldir qml, "
              "or run it on a system with Qt 5.15 (a board image, a distro)")
    return 0


# ------------------------------------------------------------------ device

def env_file(args, profile: str) -> str:
    """systemd EnvironmentFile: one KEY=value per line, comments on their own lines only."""
    display = args.display or ("linuxfb" if profile == "embedded-sw" else "eglfs")
    lines = ["# Qt settings for the kiosk service (EnvironmentFile of the systemd unit)",
             "LANG=C.UTF-8", f"QT_QPA_PLATFORM={display}"]
    if display == "eglfs":
        integration = "eglfs_kms_egldevice" if args.gpu == "jetson" else "eglfs_kms"
        lines += ["# eglfs_kms for Raspberry Pi (vc4/v3d) and most Mesa GPUs, eglfs_kms_egldevice for Jetson",
                  f"QT_QPA_EGLFS_INTEGRATION={integration}",
                  f"QT_QPA_EGLFS_KMS_CONFIG={args.prefix}/deploy/kms.json",
                  "QT_QPA_EGLFS_HIDECURSOR=1",
                  "QT_QPA_EGLFS_ALWAYS_SET_MODE=1"]
    elif display == "linuxfb":
        lines += ["QT_QPA_FB_HIDECURSOR=1"]
    elif display == "wayland":
        lines += ["# under a compositor (e.g. cage, weston) started for the same user as this service:",
                  "WAYLAND_DISPLAY=wayland-0",
                  "# XDG_RUNTIME_DIR=/run/user/<uid of that user>"]
    else:
        lines += ["DISPLAY=:0", "# XAUTHORITY=/home/<X session user>/.Xauthority"]
    if profile == "embedded-sw":
        lines += ["# no GPU: the software scene graph (shader effects are not drawn)", "QT_QUICK_BACKEND=software"]
    lines += ["# touch without libinput, or a rotated panel:",
              "# QT_QPA_GENERIC_PLUGINS=evdevtouch:/dev/input/event0",
              "# QT_QPA_EVDEV_TOUCHSCREEN_PARAMETERS=/dev/input/event0:rotate=90",
              "# APP_LANG=tr",
              "# QT_LOGGING_RULES=qt.qpa.*=true", ""]
    return "\n".join(lines)


def kms_json() -> str:
    return json.dumps({"hwcursor": False, "pbuffers": True,
                       "outputs": [{"name": "HDMI1", "mode": "preferred"}]}, indent=2) + "\n"


def service(args, name: str, exe: str) -> str:
    if args.target == "pyside6":
        start = f"{args.prefix}/.venv/bin/python {args.prefix}/main.py"
    else:
        start = f"{args.prefix}/bin/{exe}"
    return f"""[Unit]
Description={name} (Qt Quick kiosk)
After=systemd-user-sessions.service systemd-udev-settle.service
Conflicts=getty@tty1.service

[Service]
Type=simple
User={args.user}
SupplementaryGroups=video render input
WorkingDirectory={args.prefix}
EnvironmentFile={args.prefix}/deploy/app.env
ExecStart={start}
Restart=always
RestartSec=2
# take the console: without StandardInput=tty, TTYPath has no effect
TTYPath=/dev/tty1
StandardInput=tty
TTYReset=yes
TTYVHangup=yes
TTYVTDisallocate=yes
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
"""


def is_qt5(project: Path) -> bool:
    cm = project / "CMakeLists.txt"
    return cm.exists() and "find_package(Qt5" in cm.read_text()


def install_sh(args, sl: str, exe: str, qt5: bool = False) -> str:
    common = f"""#!/bin/sh
# Run on the board from the project folder: sudo sh deploy/device/install.sh
set -e
PREFIX={args.prefix}
USER_NAME={args.user}
id "$USER_NAME" >/dev/null 2>&1 || useradd --system --create-home --groups video,render,input "$USER_NAME"
mkdir -p "$PREFIX/deploy"
cp deploy/device/app.env "$PREFIX/deploy/"
[ -f deploy/device/kms.json ] && cp deploy/device/kms.json "$PREFIX/deploy/"
"""
    if args.target == "pyside6":
        body = """cp -r main.py requirements.txt qml assets "$PREFIX/"
for d in i18n mock; do [ -d "$d" ] && cp -r "$d" "$PREFIX/"; done
# PySide6 aarch64 wheels: 6.8.0.2 needs glibc 2.31, 6.8.1+ need 2.39; pip picks what the board supports
python3 -m venv "$PREFIX/.venv"
"$PREFIX/.venv/bin/pip" install --upgrade pip
"$PREFIX/.venv/bin/pip" install -r "$PREFIX/requirements.txt"
"""
    elif qt5:
        body = f"""# builds with the board's Qt 5.15 (apt install qtdeclarative5-dev qml-module-qtquick-shapes
# qml-module-qtgraphicaleffects libqt5svg5 cmake ninja-build g++, or the Yocto/Buildroot SDK's meta-qt5)
cmake -S . -B build-device -G Ninja -DCMAKE_BUILD_TYPE=Release
cmake --build build-device
cmake --install build-device --prefix "$PREFIX"
test -x "$PREFIX/bin/{exe}"
"""
    else:
        body = f"""# builds with the board's Qt 6.8+ (apt install qt6-declarative-dev qt6-base-dev cmake ninja-build g++)
cmake -S . -B build-device -G Ninja -DCMAKE_BUILD_TYPE=Release -DS2Q_DEPLOY_QT=OFF
cmake --build build-device
cmake --install build-device --prefix "$PREFIX"
test -x "$PREFIX/bin/{exe}"
"""
    tail = f"""chown -R "$USER_NAME" "$PREFIX"
cp deploy/device/{sl}.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now {sl}.service
echo "installed: systemctl status {sl} · journalctl -u {sl} -f"
"""
    return common + body + tail


def device(args, project: Path, name: str, profile: str) -> int:
    sl = slug(name)
    exe = cpp_output_name(project, sl)
    out = project / "deploy" / "device"
    out.mkdir(parents=True, exist_ok=True)
    files = {"app.env": env_file(args, profile), f"{sl}.service": service(args, name, exe),
             "install.sh": install_sh(args, sl, exe, is_qt5(project))}
    display = args.display or ("linuxfb" if profile == "embedded-sw" else "eglfs")
    if display == "eglfs":
        files["kms.json"] = kms_json()
    for fname, content in files.items():
        (out / fname).write_text(content)
    (out / "install.sh").chmod((out / "install.sh").stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    print(f"wrote deploy/device/: {', '.join(files)} (target {args.target}, profile {profile}, display {display})")
    print("on the board: copy the project, then `sudo sh deploy/device/install.sh`")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("project", type=Path)
    ap.add_argument("--target", choices=["pyside6", "cpp"], required=True)
    ap.add_argument("--platform", choices=["desktop", "device"], required=True)
    ap.add_argument("--name")
    ap.add_argument("--profile", choices=["desktop", "embedded-gpu", "embedded-sw"])
    ap.add_argument("--display", choices=["eglfs", "linuxfb", "wayland", "xcb"])
    ap.add_argument("--gpu", choices=["kms", "jetson"], default="kms", help="eglfs backend: KMS/DRM or NVIDIA EGLDevice")
    ap.add_argument("--user", default="kiosk")
    ap.add_argument("--prefix")
    ap.add_argument("--mode", choices=["onefile", "standalone"], default="standalone")
    ap.add_argument("--qt", type=Path)
    ap.add_argument("--build", action="store_true", help="desktop: also build the bundle")
    args = ap.parse_args(argv)

    project = args.project.resolve()
    if not (project / "qml").is_dir():
        print(f"[error] {project} has no qml/ folder", file=sys.stderr)
        return 2
    host = project / ("main.py" if args.target == "pyside6" else "CMakeLists.txt")
    if not host.exists():
        print(f"[error] no {host.name}: add the host first (scaffold.py {project} --add-host {args.target})", file=sys.stderr)
        return 2
    name = args.name or app_name(project)
    args.prefix = args.prefix or f"/opt/{slug(name)}"
    profile = args.profile or guess_profile(project)
    if args.platform == "desktop":
        return desktop(args, project, name)
    return device(args, project, name, profile)


if __name__ == "__main__":
    sys.exit(main())
