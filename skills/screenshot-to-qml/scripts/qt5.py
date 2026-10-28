#!/usr/bin/env python3
"""Qt 5.15 support: port a project's QML to the Qt 5.15 dialect, and list what 5.15 lacks.

Usage:
  python qt5.py port PROJECT_DIR [--dry-run]
  python qt5.py check PROJECT_DIR [--json out.json]

port   rewrites qml/**/*.qml and qml/**/qmldir in place (the mechanical part):
         versioned imports (QtQuick 2.15, QtQuick.Templates 2.15, QtQuick.Layouts 1.15 …,
         project modules 1.0), Qt5Compat.GraphicalEffects → QtGraphicalEffects 1.15,
         `import QtQuick.Window 2.15` where a file uses Window, no `pragma ComponentBehavior`,
         no Qt 6 rendering hints (a Shape's CurveRenderer becomes a multisampled layer),
         a version on every qmldir type entry;
       then prints what still needs a hand-written replacement (the check below).
check  lists every construct Qt 5.15 cannot load, with its 5.15 replacement: Qt 6 modules and
       types (MultiEffect, VectorImage, RectangularShadow, PathRectangle …), Qt 6 properties
       (per-corner radius, Layout stretch factors, font.variableAxes …), versionless imports,
       Qt 6 pragmas, ShaderEffect (Qt 6 takes .qsb files, Qt 5 GLSL source).
       Patterns: references/target-qt5.md.

The check loop still renders with PySide6: render.py and the lint gate add assets/qt5-shim to
the import path, which maps `import QtGraphicalEffects 1.15` to Qt 6's Qt5Compat module. The
real Qt 5.15 run is the C++ host: build_cpp.py / check.py --qt <Qt 5.15 prefix>.

Exit codes: 0 nothing left to do, 1 items need a hand-written replacement, 2 error.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

SHIM = Path(__file__).resolve().parent.parent / "assets" / "qt5-shim"

# the version Qt 5.15 ships for each module that Qt 6 imports without one
VERSIONS = {
    "QtQuick": "2.15", "QtQuick.Window": "2.15", "QtQuick.Controls": "2.15", "QtQuick.Templates": "2.15",
    "QtQuick.Controls.Material": "2.15", "QtQuick.Controls.Universal": "2.15",
    "QtQuick.Controls.Imagine": "2.15", "QtQuick.Controls.Fusion": "2.15",
    "QtQuick.Layouts": "1.15", "QtQuick.Shapes": "1.15", "QtQuick.Particles": "2.15",
    "QtQuick.VirtualKeyboard": "2.15", "QtQuick.Timeline": "1.0", "QtQuick.LocalStorage": "2.15",
    "QtQml": "2.15", "QtQml.Models": "2.15", "QtQml.WorkerScript": "2.15", "QtQml.StateMachine": "1.15",
    "QtGraphicalEffects": "1.15", "Qt.labs.qmlmodels": "1.0", "Qt.labs.settings": "1.0",
    "QtMultimedia": "5.15", "QtPositioning": "5.15", "QtLocation": "5.15", "QtCharts": "2.15",
    "QtWebSockets": "1.15", "QtTest": "1.15", "QtQuick3D": "1.15",
}
# Qt 6 module → its Qt 5.15 equivalent (same types)
RENAMED = {"Qt5Compat.GraphicalEffects": "QtGraphicalEffects", "QtQuick.Controls.Basic": "QtQuick.Controls"}
DROP_PRAGMAS = ("ComponentBehavior",)    # Qt 6.4+; Bound only restricts id lookups, so dropping it is safe
# rendering hints Qt 5.15 does not have; they change nothing a 5.15 build could show
HINTS = "renderTypeQuality|retainWhileLoading|popupType|contextFontMerging|preferTypoLineMetrics|pathHints"
HINT_LINE = re.compile(r"^\s*(?:" + HINTS + r")\s*:\s*[^;{}]*$")
CURVE_RENDERER = re.compile(r"^(\s*)preferredRendererType\s*:\s*Shape\.CurveRenderer\s*$")

IMPORT = re.compile(r"^(?P<indent>\s*)import\s+(?P<uri>[A-Za-z_][\w.]*)(?P<ver>\s+\d+(?:\.\d+)?)?"
                    r"(?P<alias>\s+as\s+\w+)?\s*;?\s*(?P<comment>//.*)?$")
QMLDIR_TYPE = re.compile(r"^(?P<kw>singleton\s+)?(?P<type>[A-Z]\w*)\s+(?P<file>\S+\.(?:qml|js|mjs))\s*$")

# (pattern, what is missing, the 5.15 replacement)
CHECKS: list[tuple[re.Pattern, str, str]] = [(re.compile(p, re.M), what, fix) for p, what, fix in [
    (r"^\s*import\s+QtQuick\.Effects\b", "QtQuick.Effects is Qt 6.5+",
     "import QtGraphicalEffects 1.15 (DropShadow, FastBlur, ColorOverlay, OpacityMask)"),
    (r"^\s*MultiEffect\s*\{", "MultiEffect is Qt 6.5+",
     "DropShadow / InnerShadow / FastBlur / ColorOverlay from QtGraphicalEffects 1.15"),
    (r"^\s*RectangularShadow\s*\{", "RectangularShadow is Qt 6.9+", "DropShadow on the Rectangle (QtGraphicalEffects)"),
    (r"^\s*import\s+QtQuick\.VectorImage\b", "QtQuick.VectorImage is Qt 6.8+",
     'Image { source: "icon.svg"; sourceSize } (+ ColorOverlay for a Theme color)'),
    (r"^\s*VectorImage\s*\{", "VectorImage is Qt 6.8+",
     'Image { source: "icon.svg"; sourceSize.width/height set } (+ ColorOverlay for a Theme color)'),
    (r"^\s*PathRectangle\s*\{", "PathRectangle is Qt 6.8+", "PathSvg with the rounded-rect path, or PathLine/PathArc"),
    (r"^\s*(?:FlexboxLayout|SearchField|TreeView|TreeViewDelegate|FrameAnimation|HorizontalHeaderViewDelegate)\s*\{",
     "a Qt 6 type", "Flow/RowLayout, TextField, ListView, Timer { interval: 16; repeat: true }"),
    (r"\b(?:top|bottom)(?:Left|Right)Radius\s*:", "per-corner radius is Qt 6.7+",
     "Shape + PathSvg rounded-rect path, or radius plus square patches over the sharp corners"),
    (r"\bLayout\.(?:horizontal|vertical)StretchFactor\s*:", "Layout stretch factors are Qt 6.5+",
     "Layout.preferredWidth in proportion + Layout.fillWidth"),
    (r"\bvariableAxes\s*:|\bfont\.variableAxes\b", "font.variableAxes is Qt 6.7+",
     "bundle a static instance of the variable font (match.py --fonts-dir writes them)"),
    (r"\bfont\.features\b|^\s*features\s*:", "font.features is Qt 6.6+", "leave it out (the font's default features)"),
    (r"\b(?:" + HINTS + r")\s*:", "a Qt 6 rendering hint", "leave it out (qt5.py port drops it)"),
    (r"\bpreferredRendererType\s*:", "Shape.preferredRendererType is Qt 6.6+",
     "layer.enabled: true + layer.samples: 4 on the Shape (qt5.py port swaps the CurveRenderer for it)"),
    (r"\bfillMode\s*:\s*Shape\.", "Shape.fillMode is Qt 6.7+", "scale the path coordinates yourself"),
    (r"\bQt\.alpha\s*\(", "Qt.alpha() is Qt 6", "Qt.rgba(c.r, c.g, c.b, a) or Theme.alpha(c, a)"),
    (r"(?<![=!<>])(?:\?\?=|\|\|=|&&=)", "logical assignment (ES2021) is not in Qt 5.15's JavaScript",
     "write the assignment out: a = a ?? b"),
    (r"\bproperty\s+list<(?:int|real|double|string|bool|color|url|var|date|point|rect|size|font)>",
     "lists of value types are Qt 6", "property var (a JS array)"),
    (r"^\s*pragma\s+(?:ValueTypeBehavior|FunctionSignatureBehavior|NativeMethodBehavior|ComponentBehavior)\b",
     "a Qt 6 pragma", "remove it (qt5.py port drops ComponentBehavior)"),
    (r"^\s*ShaderEffect\s*\{", "ShaderEffect: Qt 6 loads .qsb files, Qt 5.15 takes GLSL source",
     "GLSL in fragmentShader/vertexShader, or an effect from QtGraphicalEffects"),
    (r"^\s*import\s+QtCore\b", "QtCore (Settings, StandardPaths) is the Qt 6 module", "import Qt.labs.settings 1.0"),
    (r"^\s*import\s+QtQuick\.Dialogs\b", "QtQuick.Dialogs in 5.15 is the 1.3 API (different types and properties)",
     "a QtQuick.Controls Popup/Dialog, or QtQuick.Dialogs 1.3 written against its API"),
    (r"^\s*import\s+(?:QtGraphs|QtQuick\.Controls\.(?:FluentWinUI3|macOS|iOS|Windows))\b", "not in Qt 5.15",
     "QtCharts 2.15 / the Default or Material style"),
    (r"\bloadFromModule\s*\(", "loadFromModule is Qt 6.5+", 'engine.load(QUrl("qrc:/qml/App/Main.qml"))'),
]]


def strip_comment(line: str, blank_strings: bool = False) -> str:
    """The line without a // comment (not inside a string); blank_strings also hides string contents."""
    out, quote = [], None
    i = 0
    while i < len(line):
        ch = line[i]
        if quote:
            if ch == "\\":
                out.append("__" if blank_strings else line[i:i + 2])
                i += 2
                continue
            if ch == quote:
                quote = None
            elif blank_strings:
                ch = "_"
        elif ch in "\"'`":
            quote = ch
        elif line.startswith("//", i):
            break
        out.append(ch)
        i += 1
    return "".join(out)


def local_modules(qml_root: Path) -> set[str]:
    """URIs of the project's own modules (qml/**/qmldir 'module' lines)."""
    uris = set()
    for qd in qml_root.rglob("qmldir"):
        m = re.search(r"^module\s+([\w.]+)", qd.read_text(), re.M)
        if m:
            uris.add(m.group(1))
    return uris


def uses_window(text: str) -> bool:
    code = "\n".join(strip_comment(ln) for ln in text.splitlines())
    return bool(re.search(r"(?<![\w.])Window\s*\{|(?<![\w.])Window\.\w", code))


def port_text(text: str, modules: set[str]) -> tuple[str, list[str]]:
    """Qt 6 QML → Qt 5.15 dialect (imports, pragmas). Returns (text, notes on imports it could not version)."""
    notes = []
    out = []
    has_window_import = False
    for line in text.splitlines():
        if re.match(r"^\s*pragma\s+(" + "|".join(DROP_PRAGMAS) + r")\b", line) or HINT_LINE.match(line):
            continue
        c = CURVE_RENDERER.match(line)
        if c:       # Qt 5.15 antialiases a Shape only through a multisampled layer
            out += [f"{c.group(1)}layer.enabled: true", f"{c.group(1)}layer.samples: 4"]
            continue
        m = IMPORT.match(line)
        if m:
            uri = RENAMED.get(m.group("uri"), m.group("uri"))
            ver = (m.group("ver") or "").strip()
            if uri != m.group("uri"):
                ver = ""
            if not ver:
                ver = VERSIONS.get(uri) or ("1.0" if uri in modules else "")
                if not ver:
                    notes.append(f"import {uri} has no version: add the one your Qt 5.15 ships")
            line = f"{m.group('indent')}import {uri}{' ' + ver if ver else ''}{m.group('alias') or ''}" \
                   f"{'  ' + m.group('comment') if m.group('comment') else ''}"
            has_window_import |= uri == "QtQuick.Window"
        out.append(line)
    if uses_window(text) and not has_window_import:
        for i, line in enumerate(out):
            if re.match(r"^\s*import\s+QtQuick\s+2\.\d+", line):
                out.insert(i + 1, "import QtQuick.Window 2.15")
                break
    return "\n".join(out) + ("\n" if text.endswith("\n") else ""), notes


def port_qmldir(text: str) -> str:
    """Give every type entry a version (Qt 5.15 needs one: 'Main 1.0 Main.qml')."""
    out = []
    for line in text.splitlines():
        m = QMLDIR_TYPE.match(line.strip())
        if m:
            line = f"{m.group('kw') or ''}{m.group('type')} 1.0 {m.group('file')}"
        elif line.strip().startswith("prefer "):     # Qt 6 resource-path hint
            continue
        out.append(line)
    return "\n".join(out) + "\n"


def check_text(text: str, modules: set[str] | None = None) -> list[tuple[int, str, str]]:
    """[(line, what, replacement)] for everything Qt 5.15 cannot load."""
    items = []
    lines = text.splitlines()
    code = [strip_comment(ln, blank_strings=not IMPORT.match(ln)) for ln in lines]
    has_window_import = any(re.match(r"^\s*import\s+QtQuick\.Window\b", ln) for ln in code)
    for i, line in enumerate(code, 1):
        m = IMPORT.match(line)
        if m and not m.group("ver") and m.group("uri") not in RENAMED:
            items.append((i, f"import {m.group('uri')} has no version (Qt 5.15 needs one)", "qt5.py port adds it"))
        if m and m.group("uri") in RENAMED:
            items.append((i, f"{m.group('uri')} is the Qt 6 name", f"import {RENAMED[m.group('uri')]} "
                          f"{VERSIONS[RENAMED[m.group('uri')]]} (qt5.py port renames it)"))
        for rx, what, fix in CHECKS:
            if rx.search(line):
                items.append((i, what, fix))
    if uses_window(text) and not has_window_import:
        items.append((1, "Window needs import QtQuick.Window 2.15 in Qt 5", "qt5.py port adds it"))
    return items


def check_qmldir(text: str) -> list[tuple[int, str, str]]:
    return [(i, f"qmldir entry '{ln.strip()}' has no version", "qt5.py port adds 1.0")
            for i, ln in enumerate(text.splitlines(), 1) if QMLDIR_TYPE.match(ln.strip())]


def project_files(project: Path) -> tuple[Path, list[Path], list[Path]]:
    qml_root = project / "qml"
    if not qml_root.is_dir():
        raise FileNotFoundError(f"{qml_root} not found")
    qml = sorted(p for p in qml_root.rglob("*.qml") if not re.search(r"Main\.(canvas|responsive)\.qml$", p.name))
    return qml_root, qml, sorted(qml_root.rglob("qmldir"))


def check_project(project: Path) -> list[str]:
    qml_root, qml, qmldirs = project_files(project)
    mods = local_modules(qml_root)
    out = []
    for f in qml:
        for line, what, fix in check_text(f.read_text(encoding="utf-8"), mods):
            out.append(f"{f.relative_to(project)}:{line}: {what} → {fix}")
    for f in qmldirs:
        for line, what, fix in check_qmldir(f.read_text(encoding="utf-8")):
            out.append(f"{f.relative_to(project)}:{line}: {what} → {fix}")
    return out


def port_project(project: Path, dry_run: bool = False) -> tuple[list[str], list[str]]:
    """Rewrite the tree; returns (changed files, notes)."""
    qml_root, qml, qmldirs = project_files(project)
    mods = local_modules(qml_root)
    changed, notes = [], []
    for f in qml:
        text = f.read_text(encoding="utf-8")
        new, n = port_text(text, mods)
        notes += [f"{f.relative_to(project)}: {x}" for x in n]
        if new != text:
            changed.append(str(f.relative_to(project)))
            if not dry_run:
                f.write_text(new, encoding="utf-8")
    for f in qmldirs:
        text = f.read_text(encoding="utf-8")
        new = port_qmldir(text)
        if new != text:
            changed.append(str(f.relative_to(project)))
            if not dry_run:
                f.write_text(new, encoding="utf-8")
    return changed, notes


def is_qt5_project(project: Path) -> bool:
    main = project / "qml" / "App" / "Main.qml"
    return main.exists() and bool(re.search(r"^\s*import\s+QtQuick\s+2\.\d+", main.read_text(encoding="utf-8"), re.M))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["port", "check"])
    ap.add_argument("project", type=Path)
    ap.add_argument("--dry-run", action="store_true", help="port: list the files it would change")
    ap.add_argument("--json", type=Path, help="check: write the items as JSON")
    args = ap.parse_args(argv)
    project = args.project.resolve()
    try:
        if args.command == "port":
            changed, notes = port_project(project, args.dry_run)
            verb = "would change" if args.dry_run else "ported"
            print(f"{verb} {len(changed)} files" + (": " + ", ".join(changed[:12]) if changed else ""))
            for n in notes:
                print(f"  ! {n}")
        items = check_project(project)
    except FileNotFoundError as e:
        print(f"[error] {e}", file=sys.stderr)
        return 2
    if args.json:
        args.json.write_text(json.dumps({"items": items}, indent=1, ensure_ascii=False))
    if args.command == "port" and args.dry_run:
        items = [i for i in items if "qt5.py port" not in i]
    if items:
        print(f"{len(items)} items need a Qt 5.15 replacement (references/target-qt5.md):")
        for it in items[:40]:
            print(f"  ✗ {it}")
        if len(items) > 40:
            print(f"  … {len(items) - 40} more")
        return 1
    print("Qt 5.15: nothing left")
    return 0


if __name__ == "__main__":
    sys.exit(main())
