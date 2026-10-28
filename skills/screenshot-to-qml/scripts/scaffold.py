#!/usr/bin/env python3
"""Create a new Qt Quick project from the bundled template, or add a host to an existing one.

Usage:
  python scaffold.py OUT_DIR --name "Hat 3 HMI" [--target pyside6|cpp|both]
                     [--layout canvas|responsive] [--profile desktop|embedded-gpu|embedded-sw]
                     [--controls all|none|Button,TextField,...]
                     [--fonts path/to/Font-Regular.ttf ...] [--org "Acme"] [--min-qt 6.8|5.15] [--force]
  python scaffold.py PROJECT_DIR --add-host cpp|pyside6 --name "Hat 3 HMI" [--profile …]

A project is one qml/ tree plus one or two hosts that run it:
  shared      qml/App/{qmldir, Main.qml}            Main from the chosen layout variant
              qml/App/Style/{qmldir, Theme.qml, Icons.qml}
              qml/App/Controls/  the control kit (QtQuick.Templates + Theme roles); --controls
                                 keeps only the listed ones (FocusRing always; TabBar brings TabButton;
                                 SvgIcon with --min-qt 5.15)
              assets/fonts/ (copies of --fonts), i18n/, mock/, README.md
  pyside6     main.py, requirements.txt, pyproject.toml
  cpp         CMakeLists.txt, src/main.cpp, cmake/S2qQml.cmake (every qmldir becomes a compiled
              QML module; fonts, translations and mock data are embedded in the binary)

--min-qt 5.15 (Qt 5.15 LTS boards: automotive and industrial BSPs) writes the qml/ tree in the
Qt 5.15 dialect (qt5.py port: versioned imports, QtGraphicalEffects) and a Qt 5 C++ host
(CMake + one embedded resource, qmlcachegen when available); the target is cpp. PySide2 has no
wheels for Python 3.11+, so there is no Python host for 5.15; check.py still renders the QML
with PySide6 (assets/qt5-shim) and builds the C++ host against the Qt 5.15 given with --qt.

Both hosts load fonts from assets/fonts, the translation from i18n/app_<locale>.qm and the App
module's Main, and default to the software scene graph for the embedded-sw profile.
--add-host adds the other host's files to a project made earlier (the qml/ tree is not touched).

Layouts:
  canvas      fixed design canvas scaled to the window (kiosk, HMI, embedded panel)
  responsive  resizable window, Layouts reflow (desktop apps)

Next: python gen_theme.py design-spec.json OUT_DIR/qml/App/Style  (overwrites Theme/Icons)

Exit codes: 0 ok, 2 error.
"""
from __future__ import annotations

import argparse
import re
import shutil
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import qt5  # noqa: E402

TEMPLATES = Path(__file__).resolve().parent.parent / "assets" / "templates"
SHARED = TEMPLATES / "project"
QT5_EXTRA = TEMPLATES / "qt5"      # files only Qt 5.15 projects get (SvgIcon: Image + ColorOverlay)
HOSTS = {"pyside6": TEMPLATES / "pyside6", "cpp": TEMPLATES / "cpp", "cpp5": TEMPLATES / "cpp-qt5"}
TEXT_SUFFIXES = (".py", ".qml", ".toml", ".md", ".txt", ".cpp", ".h", ".cmake")

RUN = {
    "pyside6": """### PySide6

```bash
pip install -r requirements.txt
python main.py
```
""",
    "cpp": """### C++ (CMake, Qt 6.8+)

```bash
cmake -S . -B build -G Ninja -DCMAKE_PREFIX_PATH=/path/to/Qt/6.8.3/gcc_64   # omit for a system Qt
cmake --build build
./build/{package}
cmake --install build --prefix dist        # a self-contained bundle when Qt comes from an SDK
```
""",
    "cpp5": """### C++ (CMake, Qt 5.15)

```bash
cmake -S . -B build -G Ninja -DCMAKE_PREFIX_PATH=/path/to/Qt/5.15.2/gcc_64   # omit for a system or Yocto SDK Qt
cmake --build build
./build/{package}
```

The QML is the Qt 5.15 dialect (versioned imports, QtGraphicalEffects): keep it that way
(`python <skill>/scripts/qt5.py check .`). A desktop bundle: `cmake --install build --prefix dist`, then
`windeployqt --qmldir qml dist/bin/{package}.exe` (or `macdeployqt`); a board uses the image's Qt 5.15.
""",
}

README = """# {name}

Native Qt Quick UI generated with screenshot-to-qml. Profile: `{profile}`.

## Run

{run}
Headless check: `python <skill>/scripts/check.py . --source input.png --spec design-spec.json`

## Structure

- `qml/App/Style` — Theme (all tokens) and Icons
- `qml/App/Controls` — the control kit (QtQuick.Templates, Theme roles only); delete unused ones
- `qml/App` — screens and screen-specific components
- `assets/fonts` — bundled fonts, loaded by the host from the folder
- `i18n` — translations: `pyside6-lupdate qml/App/*.qml qml/App/Controls/*.qml -ts i18n/app_en.ts`,
  translate, `pyside6-lrelease i18n/app_en.ts -qm i18n/app_en.qm`; `APP_LANG=en` picks the language
{hosts}
## Fidelity report

<!-- filled in by the agent: measured metrics, assumed values, approximations -->
"""

HOST_LINES = {
    "pyside6": "- `main.py` — PySide6 host",
    "cpp": "- `CMakeLists.txt`, `src/main.cpp`, `cmake/S2qQml.cmake` — C++ host; each `qmldir` is compiled "
           "into the binary",
    "cpp5": "- `CMakeLists.txt`, `src/main.cpp`, `cmake/S2qQml5.cmake` — C++ host (Qt 5.15); qml/, assets/, "
            "i18n/ and mock/ are embedded as one resource",
}


def slug(name: str) -> str:
    """ASCII file/target name: 'Hat 3 Dolum Çay' -> 'hat-3-dolum-cay' (ı/İ → i, accents dropped)."""
    ascii_name = unicodedata.normalize("NFKD", name.replace("ı", "i").replace("İ", "I")).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", ascii_name.lower()).strip("-") or "app"


def prune_controls(folder: Path, spec: str) -> list[str] | None:
    """Keep the requested kit controls (plus their dependencies) and rewrite the qmldir."""
    available = sorted(p.stem for p in folder.glob("*.qml"))
    if spec == "all":
        keep = set(available)
    elif spec == "none":
        keep = set()
    else:
        keep = {c.strip() for c in spec.split(",") if c.strip()}
        unknown = keep - set(available)
        if unknown:
            print(f"[error] unknown controls: {', '.join(sorted(unknown))} (have: {', '.join(available)})",
                  file=sys.stderr)
            return None
    if keep:
        keep.add("FocusRing")
    if "TabBar" in keep:
        keep.add("TabButton")
    for p in folder.glob("*.qml"):
        if p.stem not in keep:
            p.unlink()
    lines = ["module App.Controls"] + [f"{c} 1.0 {c}.qml" for c in sorted(keep)]
    (folder / "qmldir").write_text("\n".join(lines) + "\n")
    return sorted(keep - {"FocusRing"})


def existing_profile(project: Path) -> str | None:
    """The profile the project's other host was generated with, so both hosts agree."""
    for f, rx in (("main.py", r'APP_PROFILE = "([a-z-]+)"'), ("CMakeLists.txt", r'set\(S2Q_PROFILE "([a-z-]+)"')):
        path = project / f
        m = re.search(rx, path.read_text()) if path.exists() else None
        if m:
            return m.group(1)
    return None


def substitute(files, subs: dict) -> None:
    for p in files:
        if p.is_file() and p.suffix in TEXT_SUFFIXES:
            text = p.read_text()
            for k, v in subs.items():
                text = text.replace(k, v)
            p.write_text(text)


def is_qt5(min_qt: str) -> bool:
    m = re.match(r"\s*(\d+)", min_qt or "")
    return bool(m) and int(m.group(1)) < 6


def add_host(out: Path, host: str, subs: dict, force: bool) -> list[Path] | None:
    src = HOSTS[host]
    files = [f for f in sorted(src.rglob("*")) if f.is_file() and f.name != ".gitkeep"]
    clash = [out / f.relative_to(src) for f in files if (out / f.relative_to(src)).exists()]
    if clash and not force:
        print(f"[error] {', '.join(str(c.relative_to(out)) for c in clash)} exist (use --force)", file=sys.stderr)
        return None
    written = []
    for f in files:
        dst = out / f.relative_to(src)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(f, dst)
        written.append(dst)
    substitute(written, subs)
    return written


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("out", type=Path)
    ap.add_argument("--name", required=True)
    ap.add_argument("--org", default="")
    ap.add_argument("--target", choices=["pyside6", "cpp", "both"], help="default: pyside6 (cpp with --min-qt 5.15)")
    ap.add_argument("--add-host", choices=["pyside6", "cpp"], help="add a host to an existing project")
    ap.add_argument("--layout", choices=["canvas", "responsive"], default="responsive")
    ap.add_argument("--profile", choices=["desktop", "embedded-gpu", "embedded-sw"],
                    help="default: desktop; with --add-host, the existing host's profile")
    ap.add_argument("--fonts", type=Path, nargs="*", default=[])
    ap.add_argument("--controls", default="all", help="all | none | comma-separated control names")
    ap.add_argument("--min-qt", default="6.8", help="oldest Qt the app must run on: 6.8 (default) or 5.15")
    ap.add_argument("--force", action="store_true", help="overwrite a non-empty OUT_DIR / existing host files")
    args = ap.parse_args(argv)

    out = args.out.resolve()
    legacy = is_qt5(args.min_qt) or (args.add_host is not None and qt5.is_qt5_project(out))
    if legacy and "pyside6" in (args.target, args.add_host) or legacy and args.target == "both":
        print("[error] Qt 5.15 projects have the C++ host only: PySide2 has no wheels for Python 3.11+. "
              "check.py still renders the QML with PySide6; use --target cpp", file=sys.stderr)
        return 2
    args.target = args.target or ("cpp" if legacy else "pyside6")
    if args.profile is None:
        args.profile = (existing_profile(out) if args.add_host else None) or "desktop"
    subs = {"{{APP_NAME}}": args.name, "{{ORG_NAME}}": args.org, "{{PACKAGE_NAME}}": slug(args.name),
            "{{PROFILE}}": args.profile}
    for d in [SHARED, *HOSTS.values()]:
        if not d.is_dir():
            print(f"[error] template missing: {d}", file=sys.stderr)
            return 2

    if args.add_host:
        if not (out / "qml" / "App" / "qmldir").exists():
            print(f"[error] {out} has no qml/App/qmldir: not a project made by scaffold.py", file=sys.stderr)
            return 2
        written = add_host(out, "cpp5" if legacy and args.add_host == "cpp" else args.add_host, subs, args.force)
        if written is None:
            return 2
        print(f"added the {args.add_host} host to {out}: {', '.join(str(p.relative_to(out)) for p in written)}")
        return 0

    if out.exists() and any(out.iterdir()) and not args.force:
        print(f"[error] {out} is not empty (use --force)", file=sys.stderr)
        return 2
    shutil.copytree(SHARED, out, dirs_exist_ok=True, ignore=shutil.ignore_patterns("Main.*.qml", ".gitkeep"))
    shutil.copy(SHARED / "qml" / "App" / f"Main.{args.layout}.qml", out / "qml" / "App" / "Main.qml")
    for d in ("assets/fonts", "mock", "i18n"):
        (out / d).mkdir(parents=True, exist_ok=True)
    substitute(list(out.rglob("*")), subs)

    hosts = ["pyside6", "cpp"] if args.target == "both" else [args.target]
    if legacy:
        hosts = ["cpp5"]
    for h in hosts:
        add_host(out, h, subs, True)
    run = "\n".join(RUN[h].format(package=slug(args.name)) for h in hosts)
    (out / "README.md").write_text(README.format(name=args.name, profile=args.profile, run=run,
                                                 hosts="\n".join(HOST_LINES[h] for h in hosts) + "\n"))

    kit = prune_controls(out / "qml" / "App" / "Controls", args.controls)
    if kit is None:
        return 2
    if legacy:
        shutil.copytree(QT5_EXTRA, out, dirs_exist_ok=True)
        qmldir = out / "qml" / "App" / "Controls" / "qmldir"
        extra = sorted(p.stem for p in (QT5_EXTRA / "qml" / "App" / "Controls").glob("*.qml"))
        qmldir.write_text(qmldir.read_text() + "".join(f"{c} 1.0 {c}.qml\n" for c in extra))
        kit += extra
        qt5.port_project(out)
        left = qt5.check_project(out)
        for item in left:
            print(f"[warn] Qt 5.15: {item}", file=sys.stderr)

    missing = [f for f in args.fonts if not f.is_file()]
    for f in args.fonts:
        if f.is_file():
            shutil.copy(f, out / "assets" / "fonts" / f.name)
    for f in missing:
        print(f"[warn] font not found: {f}", file=sys.stderr)

    host_names = ["cpp (Qt 5.15)" if h == "cpp5" else h for h in hosts]
    print(f"created {out} (host: {' + '.join(host_names)}, layout: {args.layout}, profile: {args.profile}, "
          f"controls: {', '.join(kit) or 'none'}, fonts: {len(args.fonts) - len(missing)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
