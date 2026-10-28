#!/usr/bin/env python3
"""Static and runtime quality gates for a generated Qt Quick project.

Usage:
  python quality_gate.py PROJECT_DIR [--source screenshot.png] [--scene scene.json]
                         [--interaction interaction.json] [--profile desktop|embedded-gpu|embedded-sw]
                         [--cpp cpp.json] [--min-qt 6.8] [--mode production|fidelity] [--out gate.json]
                         [--skip lint,format,runtime,hardcode,embed,fonts,webengine,a11y,states,i18n,effects,perf,cpp]

Gates (error = fails the gate, warning = reported only):
  lint       qmllint over qml/**.qml with -I qml                        error per warning
             types newer than --min-qt (RectangularShadow 6.9, …)       error
             --min-qt 5.15: everything 5.15 cannot load (qt5.py check)  error
  format     qmlformat drift (file differs from its formatted output)  error per file
  runtime    QML warnings recorded by render.py in scene.json          error per warning
  hardcode   color / font literals outside Style files (production)    error per hit
             radius / spacing literals outside Style files             warning
  embed      raster covering >= 25% of the window, or a raster that
             matches the source screenshot (anti-cheat)                 error
  fonts      assets/fonts empty, or a Theme family Qt did not load      error
  webengine  QtWebEngine / WebView imports                              error
  a11y       (needs interaction.json from render.py --interact)
             enabled control Tab cannot reach, or no visible focus        error
             control without an accessible name                         error
             clickable MouseArea outside a control that is not itself
             Tab-focusable with an interactive Accessible.role          error (production)
             duplicate Tab stops, touch targets < 44 px on touch profiles warning
  states     (needs interaction.json) no visible pressed state          error (production)
             no visible hover state (desktop profile)                   warning
  i18n       user-visible string literal not wrapped in qsTr()          error (production)
             (text, title, placeholderText, Accessible.name/description,
             ToolTip.text, string-list models; mock data and ListElement
             data are exempt)
  effects    shader effects (MultiEffect, RectangularShadow, ShaderEffect,
             layer.effect, Qt5Compat.GraphicalEffects) on embedded-sw:
             the software scene graph does not draw them              error
             blur, Qt5Compat effects and > 4 layers on embedded-gpu     warning
             Qt5Compat.GraphicalEffects on desktop (use MultiEffect)    warning
  perf       (needs scene.json) images decoded ≥ 4× the pixels they
             are drawn with on embedded profiles                        error
             the same at 2×, infinite animations and < 250 ms repeating
             timers running while idle, > 4 layers, > 3000 items,
             first frame later than 1.5 s (embedded)                    warning
  cpp        (needs cpp.json from build_cpp.py, when the project has a
             C++ host) configure/build failure, no frame, QML warnings
             in the C++ run, SSIM < 0.98 against the PySide6 render     error
             SSIM < 0.995, compiler/qmlcachegen warnings                warning

Style files are qml/**/Style/*.qml, Theme*.qml and Icons*.qml.
Tools are looked up as pyside6-qmllint / pyside6-qmlformat, then qmllint / qmlformat.

Exit codes: 0 all gates pass, 1 at least one error, 2 could not run.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

GATES = ["lint", "format", "runtime", "hardcode", "embed", "fonts", "webengine", "a11y", "states", "i18n",
         "effects", "perf", "cpp"]
TOUCH_PROFILES = ("embedded-gpu", "embedded-sw")
TOUCH_TARGET = 44
I18N_PROP = re.compile(r"(?:^|[;{])\s*(?:text|title|placeholderText|Accessible\.name|Accessible\.description|ToolTip\.text)"
                       r"\s*:\s*([\"'])((?:(?!\1).)*[^\W\d_](?:(?!\1).)*)\1")
I18N_MODEL = re.compile(r"\bmodel\s*:\s*\[\s*([\"'])[^\"']*[^\W\d_]")
COLOR_LITERAL = re.compile(r'"#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})"|Qt\.rgba\s*\(|Qt\.hsla\s*\(|Qt\.hsva\s*\(')
NAMED_COLOR = re.compile(r'\b(?:color|border\.color|strokeColor|fillColor)\s*:\s*"(?!transparent")[a-zA-Z]+"')
FONT_LITERAL = re.compile(r'\bfont\.(?:pixelSize|pointSize)\s*:\s*\d|\bfont\.family\s*:\s*"|pixelSize\s*:\s*\d+\s*[,}]')
SOFT_LITERAL = re.compile(r'\b(?:radius|spacing|columnSpacing|rowSpacing)\s*:\s*([1-9]\d*(?:\.\d+)?)\s*$')
SHADER_EFFECT = re.compile(r"^\s*(MultiEffect|RectangularShadow|ShaderEffect)\s*\{|\blayer\.effect\s*:"
                           r"|^\s*import\s+(?:Qt5Compat\.GraphicalEffects|QtGraphicalEffects)\b")
BLUR = re.compile(r"\bblurEnabled\s*:\s*true|\bblurMax\s*:|^\s*(FastBlur|GaussianBlur|DropShadow|Glow|RecursiveBlur)\s*\{")
LAYER = re.compile(r"\blayer\.enabled\s*:\s*true")
WEBENGINE = re.compile(r'^\s*import\s+Qt(?:WebEngine|WebView)\b|QWebEngine|QtWebEngine', re.M)


def tool(*names: str) -> str | None:
    for n in names:
        p = shutil.which(n)
        if p:
            return p
    return None


def is_style_file(path: Path) -> bool:
    return "Style" in path.parts or path.stem.startswith(("Theme", "Icons"))


def strip_comments(line: str) -> str:
    return line.split("//", 1)[0]


# QML types newer than the Qt 6.8 floor: qmllint from a newer PySide6 accepts them, but a board
# with Qt 6.8 (C++ host, or PySide6 6.8.0.2 on older glibc) fails to load the file
NEWER_TYPES = {"RectangularShadow": (6, 9), "FlexboxLayout": (6, 10), "SearchField": (6, 10)}


def parse_qt(v: str) -> tuple[int, int]:
    parts = [int(x) for x in re.findall(r"\d+", v)[:2]] + [0, 0]
    return parts[0], parts[1]


def newer_than(project: Path, qml_files: list[Path], min_qt: str) -> list[str]:
    floor = parse_qt(min_qt)
    if floor < (6, 0):      # Qt 5.15: the whole dialect (imports, modules, types, properties)
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import qt5
        return [f"{item} (meta.minQt {min_qt})" for item in qt5.check_project(project)]
    out = []
    rx = re.compile(r"^\s*(" + "|".join(NEWER_TYPES) + r")\s*\{")
    for f in qml_files:
        for i, raw in enumerate(f.read_text().splitlines(), 1):
            m = rx.search(strip_comments(raw))
            if m and NEWER_TYPES[m.group(1)] > floor:
                need = "{}.{}".format(*NEWER_TYPES[m.group(1)])
                out.append(f"{f.relative_to(project)}:{i}: {m.group(1)} needs Qt {need}; the project's minimum is "
                           f"{min_qt} (meta.minQt): use the fallback in SKILL.md's Qt version table")
    return out


def gate_lint(project: Path, qml_files: list[Path], min_qt: str = "6.8") -> tuple[list, list]:
    compat = newer_than(project, qml_files, min_qt)
    exe = tool("pyside6-qmllint", "qmllint")
    if not exe:
        return compat, ["qmllint not found; lint skipped"]
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
        out = Path(tmp.name)
    # absolute paths: qmllint 6.12 misses a file's own qmldir entry (singletons) for relative paths
    project = project.resolve()
    shim = Path(__file__).resolve().parent.parent / "assets" / "qt5-shim"     # Qt 5.15: QtGraphicalEffects
    root, offset = project, 0
    tmpdir = None
    if parse_qt(min_qt) < (6, 0):
        # Qt 5.15 has no `pragma ComponentBehavior`, and Qt 6's qmllint reports every outer id used in
        # a delegate without it. Lint a copy with the pragma added: code valid when bound is valid
        # unbound too. Line numbers are mapped back (-1).
        tmpdir = tempfile.TemporaryDirectory()
        root, offset = Path(tmpdir.name), 1
        shutil.copytree(project / "qml", root / "qml")
        for f in (root / "qml").rglob("*.qml"):
            f.write_text("pragma ComponentBehavior: Bound\n" + f.read_text(encoding="utf-8"), encoding="utf-8")
        qml_files = [root / f.resolve().relative_to(project) for f in qml_files]
    subprocess.run([exe, "-I", str(root / "qml"), "-I", str(shim), "--json", str(out),
                    *(str(f.resolve()) for f in qml_files)], capture_output=True, text=True)
    try:
        data = json.loads(out.read_text())
    except (OSError, json.JSONDecodeError):
        return ["qmllint produced no JSON output"], []
    finally:
        if tmpdir is not None:
            tmpdir.cleanup()
    errors = []
    for f in data.get("files", []):
        for w in f.get("warnings", []):
            if w.get("type") in ("warning", "critical"):
                name = f["filename"]
                rel = Path(name).relative_to(root) if name.startswith(str(root)) else name
                line = w.get("line")
                errors.append(f"{rel}:{line - offset if isinstance(line, int) else line}: [{w.get('id')}] {w.get('message')}")
    return errors + compat, []


def gate_format(project: Path, qml_files: list[Path]) -> tuple[list, list]:
    exe = tool("pyside6-qmlformat", "qmlformat")
    if not exe:
        return [], ["qmlformat not found; format skipped"]
    errors = []
    for f in qml_files:
        res = subprocess.run([exe, str(f)], capture_output=True, text=True)
        if res.returncode != 0:
            errors.append(f"{f.relative_to(project)}: qmlformat failed: {res.stderr.strip()[:200]}")
        elif res.stdout != f.read_text():
            errors.append(f"{f.relative_to(project)}: not qmlformat-clean (run qmlformat -i)")
    return errors, []


def gate_runtime(scene: dict | None) -> tuple[list, list]:
    if scene is None:
        return [], ["no scene.json; runtime gate skipped (run render.py first)"]
    return [f"QML: {w}" for w in scene.get("warnings", [])], []


def gate_hardcode(project: Path, qml_files: list[Path], mode: str) -> tuple[list, list]:
    errors, warns = [], []
    for f in qml_files:
        if is_style_file(f):
            continue
        for i, raw in enumerate(f.read_text().splitlines(), 1):
            line = strip_comments(raw)
            rel = f"{f.relative_to(project)}:{i}"
            if COLOR_LITERAL.search(line) or NAMED_COLOR.search(line):
                (errors if mode == "production" else warns).append(f"{rel}: color literal: {raw.strip()[:90]}")
            if FONT_LITERAL.search(line):
                (errors if mode == "production" else warns).append(f"{rel}: font literal: {raw.strip()[:90]}")
            if SOFT_LITERAL.search(line):
                warns.append(f"{rel}: size literal (prefer Theme): {raw.strip()[:90]}")
    return errors, warns


def gate_embed(project: Path, scene: dict | None, source: Path | None) -> tuple[list, list]:
    errors, warns = [], []
    if scene:
        w, h = scene.get("render", {}).get("logicalSize", [0, 0])
        area = max(1, w * h)
        for img in scene.get("images", []):
            bw, bh = img["bbox"][2], img["bbox"][3]
            if bw * bh >= 0.25 * area:
                errors.append(f"raster covers {bw * bh / area:.0%} of the window: {img['source']}")
    if source is not None:
        try:
            import cv2
            import numpy as np
        except ImportError:
            return errors, ["opencv not installed; screenshot-match check skipped"]
        src = cv2.imread(str(source), cv2.IMREAD_GRAYSCALE)
        if src is None:
            return errors, [f"cannot read source {source}"]
        small = cv2.resize(src, (64, 64), interpolation=cv2.INTER_AREA).astype(np.float32)
        code = "\n".join(f.read_text(errors="ignore") for f in project.rglob("*")
                          if f.suffix in (".qml", ".py", ".qrc", ".js") and f.is_file())
        used = {Path(i["source"]).name for i in (scene or {}).get("images", []) if i.get("source")}
        for p in project.rglob("*"):
            if p.suffix.lower() not in (".png", ".jpg", ".jpeg", ".webp", ".bmp") or "render" in p.stem:
                continue
            img = cv2.imread(str(p), cv2.IMREAD_GRAYSCALE)
            if img is None or img.shape[0] < 64 or img.shape[1] < 64:
                continue
            cand = cv2.resize(img, (64, 64), interpolation=cv2.INTER_AREA).astype(np.float32)
            ncc = float(cv2.matchTemplate(cand, small, cv2.TM_CCOEFF_NORMED)[0, 0])
            if ncc > 0.9:
                if p.name in used or p.name in code:
                    errors.append(f"{p.relative_to(project)} looks like the source screenshot (ncc {ncc:.2f})")
                else:   # a stray preview/render file, not used by the UI
                    warns.append(f"{p.relative_to(project)} looks like the source screenshot but is not used; "
                                 "keep previews out of the project")
    return errors, warns


def gate_fonts(project: Path, scene: dict | None, qml_files: list[Path]) -> tuple[list, list]:
    errors, warns = [], []
    fonts = [p for p in (project / "assets" / "fonts").glob("*") if p.suffix.lower() in (".ttf", ".otf", ".ttc")]
    if not fonts:
        errors.append("assets/fonts has no font files; bundle the fonts the design uses")
    loaded = set()
    if scene:
        for fams in (scene.get("fonts") or {}).values():
            loaded.update(fams or [])
    wanted = set()
    for f in qml_files:
        if is_style_file(f):
            wanted.update(re.findall(r'property\s+string\s+font\w*\s*:\s*"([^"]+)"', f.read_text()))
    if scene:
        for fam in sorted(wanted - loaded):
            errors.append(f"Theme uses font family '{fam}' but Qt did not load it (loaded: {sorted(loaded)})")
    elif wanted:
        warns.append("no scene.json; could not verify font families")
    return errors, warns


def gate_webengine(project: Path) -> tuple[list, list]:
    errors = []
    for p in list(project.rglob("*.qml")) + list(project.rglob("*.py")):
        if WEBENGINE.search(p.read_text(errors="ignore")):
            errors.append(f"{p.relative_to(project)} uses a web engine / WebView")
    return errors, []


def _where(c: dict) -> str:
    x, y = c["bbox"][:2]
    label = c.get("name") or c.get("text") or ""
    return f"{c['type']}{' ' + repr(label[:30]) if label else ''} at ({x:.0f}, {y:.0f})"


def gate_a11y(interaction: dict | None, profile: str, mode: str = "production") -> tuple[list, list] | None:
    if interaction is None:
        return None
    errors, warns = [], []
    if interaction.get("error"):
        errors.append(f"{interaction['error']}: keyboard and pointer access could not be checked "
                      "(do not quit or close the window from a plain press during a check)")
    for c in interaction["controls"]:
        if not c["name"]:
            errors.append(f"{_where(c)}: no accessible name (set Accessible.name)")
        if not c["enabled"]:
            continue
        if not c["tabReached"]:
            errors.append(f"{_where(c)}: Tab never reaches it (focusPolicy: Qt.StrongFocus / activeFocusOnTab)")
        elif c["focusVisible"] is False:
            errors.append(f"{_where(c)}: keyboard focus is not visible (draw a ring on visualFocus)")
        if profile in TOUCH_PROFILES and min(c["bbox"][2], c["bbox"][3]) < TOUCH_TARGET - 0.5:
            warns.append(f"{_where(c)}: touch target {c['bbox'][2]:.0f}×{c['bbox'][3]:.0f} < {TOUCH_TARGET} px")
    for d in interaction.get("duplicateTabStops", []):
        warns.append(f"{d}: takes Tab focus more than once (an inner item is also a Tab stop)")
    fake = [m for m in interaction.get("mouseAreas", []) if m.get("clickable", True) and not m.get("accessibleControl")]
    for m in fake:
        x, y, w, h = m["bbox"]
        msg = (f"MouseArea in {m['parent']} at ({x:.0f}, {y:.0f}) {w:.0f}×{h:.0f} acts as a control without "
               "keyboard focus or an accessible role (use a Template control)")
        (errors if mode == "production" else warns).append(msg)
    return errors, warns


def gate_states(interaction: dict | None, mode: str, profile: str) -> tuple[list, list] | None:
    if interaction is None:
        return None
    errors, warns = [], []
    for c in interaction["controls"]:
        if not c["enabled"]:
            continue
        if c.get("pressChanges") is False:
            (errors if mode == "production" else warns).append(f"{_where(c)}: no visible pressed state (control.down)")
        if c.get("hoverChanges") is False and profile not in TOUCH_PROFILES:
            warns.append(f"{_where(c)}: no visible hover state (control.hovered)")
    if not interaction.get("hoverChecked") and profile not in TOUCH_PROFILES:
        warns.append("hover could not be checked in this environment")
    return errors, warns


def gate_i18n(project: Path, qml_files: list[Path], mode: str) -> tuple[list, list]:
    errors, warns = [], []
    for f in qml_files:
        rel = f.relative_to(project)
        if is_style_file(f) or "mock" in f.stem.lower() or "mock" in {p.lower() for p in rel.parts[:-1]}:
            continue
        depth = None   # inside a ListElement block (model data, not UI text)
        for i, raw in enumerate(f.read_text(errors="ignore").splitlines(), 1):
            line = strip_comments(raw)
            if depth is None and re.search(r"\bListElement\s*\{", line):
                depth = 0
            if depth is not None:
                depth += line.count("{") - line.count("}")
                if depth <= 0:
                    depth = None
                continue
            if "qsTr" in line or "qsTranslate" in line or "qsTrId" in line:
                continue
            if I18N_PROP.search(line) or I18N_MODEL.search(line):
                (errors if mode == "production" else warns).append(
                    f"{rel}:{i}: user-visible string without qsTr(): {raw.strip()[:80]}")
    return errors, warns


def gate_effects(project: Path, qml_files: list[Path], profile: str, min_qt: str = "6.8") -> tuple[list, list]:
    errors, warns = [], []
    layers = []
    for f in qml_files:
        rel = f.relative_to(project)
        for i, raw in enumerate(f.read_text().splitlines(), 1):
            line = strip_comments(raw)
            m = SHADER_EFFECT.search(line)
            if m:
                what = m.group(1) or line.strip()
                if profile == "embedded-sw":
                    errors.append(f"{rel}:{i}: {what.strip()} is not drawn by the software scene graph "
                                  "(embedded-sw): flat fallback (effects.md)")
                elif "Qt5Compat" in line and parse_qt(min_qt) >= (6, 0):
                    warns.append(f"{rel}:{i}: Qt5Compat.GraphicalEffects is legacy; use MultiEffect (RectangularShadow from Qt 6.9)")
            if profile == "embedded-gpu" and BLUR.search(line):
                warns.append(f"{rel}:{i}: blur on embedded-gpu costs full-screen passes; prefer a static tint")
            if LAYER.search(line):
                layers.append(f"{rel}:{i}")
    if profile != "desktop" and len(layers) > 4:
        warns.append(f"{len(layers)} layer.enabled items (each is an offscreen texture): {', '.join(layers[:6])}")
    return errors, warns


def gate_perf(scene: dict | None, profile: str) -> tuple[list, list] | None:
    if scene is None or "perf" not in scene:
        return None
    perf = scene["perf"]
    embedded = profile in TOUCH_PROFILES
    errors, warns = [], []
    if perf.get("idleScan") is False:
        warns.append("idle animations and timers were not checked (the scan crashed this render; see render.py --no-idle-scan)")
    for im in perf.get("oversizedImages", []):
        msg = (f"image {im['source']} is decoded at {im['decoded'][0]}×{im['decoded'][1]} and drawn at "
               f"{im['drawn'][0]}×{im['drawn'][1]} px ({im['ratio']}× the pixels): set sourceSize")
        (errors if embedded and im["ratio"] >= 4 else warns).append(msg)
    if embedded:
        for a in perf.get("animations", []):
            warns.append(f"infinite {a['class']} in {a['owner']} keeps the scene graph busy while idle")
        for t in perf.get("timers", []):
            warns.append(f"Timer every {t['interval']} ms in {t['owner']} runs while idle")
        if len(perf.get("layers", [])) > 4:
            warns.append(f"{len(perf['layers'])} visible layers (offscreen textures)")
        ms = perf.get("firstFrameMs")
        if ms and ms > 1500:
            warns.append(f"first frame after {ms} ms on this machine; expect several times longer on the device")
    if perf.get("items", 0) > 3000:
        warns.append(f"{perf['items']} visible items; use Loader/ListView to create only what is on screen")
    return errors, warns


def gate_cpp(cpp: dict | None) -> tuple[list, list] | None:
    if cpp is None:
        return None
    errors, warns = [], []
    if not cpp.get("built"):
        err = cpp.get("error", "build failed")
        if "not found" in err:           # no Qt SDK or cmake here: say so, do not fail
            return [], [f"C++ host not built: {err}"]
        return [f"C++ host: {err}: {' | '.join(cpp.get('log', [])[-3:])}"], []
    grab = cpp.get("grab")
    if grab is not None:
        if not grab.get("ok"):
            errors.append("C++ binary did not produce a frame: " + " | ".join(grab.get("stderr", [])[-3:]))
        errors += [f"C++ run QML: {w}" for w in grab.get("qmlWarnings", [])]
    par = (cpp.get("parity") or {}).get("ssim")
    if (cpp.get("parity") or {}).get("qt") == 5:
        t, limit = cpp["parity"].get("maxTileDiff"), cpp["parity"].get("limit", 24)
        if t is None:
            errors.append("C++ (Qt 5.15) frame and PySide6 render differ in size")
        elif t > limit:
            errors.append(f"Qt 5.15 frame differs from the PySide6 render (max tile difference {t} > {limit}): "
                          "a file missing from the resource, or a type Qt 5.15 draws differently")
    elif cpp.get("parity") is not None:
        if par is None:
            errors.append("C++ frame and PySide6 render differ in size")
        elif par < 0.98:
            errors.append(f"C++ frame differs from the PySide6 render (SSIM {par}): a file missing from the binary?")
        elif par < 0.995:
            warns.append(f"C++ frame vs PySide6 render SSIM {par}")
    n = (cpp.get("warnings") or {}).get("build", 0)
    if n:
        warns.append(f"{n} build warnings, e.g. {(cpp['warnings'].get('samples') or [''])[0][:160]}")
    return errors, warns


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("project", type=Path)
    ap.add_argument("--source", type=Path, help="source screenshot (enables the screenshot-match check)")
    ap.add_argument("--scene", type=Path, help="scene.json from render.py (default: PROJECT/scene.json if present)")
    ap.add_argument("--interaction", type=Path, help="interaction.json from render.py --interact "
                    "(default: next to the scene if present); enables the a11y and states gates")
    ap.add_argument("--profile", choices=["desktop", "embedded-gpu", "embedded-sw"], default="desktop")
    ap.add_argument("--cpp", type=Path, help="cpp.json from build_cpp.py (C++ host build, run and parity)")
    ap.add_argument("--min-qt", default="6.8", help="oldest Qt the project must run on (spec meta.minQt)")
    ap.add_argument("--mode", choices=["production", "fidelity"], default="production")
    ap.add_argument("--out", type=Path)
    ap.add_argument("--skip", default="", help="comma-separated gates to skip")
    args = ap.parse_args(argv)

    project = args.project.resolve()
    qml_dir = project / "qml"
    if not qml_dir.is_dir():
        print(f"[error] {qml_dir} not found", file=sys.stderr)
        return 2
    qml_files = sorted(qml_dir.rglob("*.qml"))
    scene_path = args.scene or (project / "scene.json")
    scene = json.loads(scene_path.read_text()) if scene_path.exists() else None
    skip = {s.strip() for s in args.skip.split(",") if s.strip()}
    ipath = args.interaction or scene_path.with_name("interaction.json")
    interaction = json.loads(ipath.read_text()) if ipath.exists() else None
    cpp = json.loads(args.cpp.read_text()) if args.cpp and args.cpp.exists() else None

    runners = {
        "lint": lambda: gate_lint(project, qml_files, args.min_qt),
        "format": lambda: gate_format(project, qml_files),
        "runtime": lambda: gate_runtime(scene),
        "hardcode": lambda: gate_hardcode(project, qml_files, args.mode),
        "embed": lambda: gate_embed(project, scene, args.source),
        "fonts": lambda: gate_fonts(project, scene, qml_files),
        "webengine": lambda: gate_webengine(project),
        "a11y": lambda: gate_a11y(interaction, args.profile, args.mode),
        "states": lambda: gate_states(interaction, args.mode, args.profile),
        "i18n": lambda: gate_i18n(project, qml_files, args.mode),
        "effects": lambda: gate_effects(project, qml_files, args.profile, args.min_qt),
        "perf": lambda: gate_perf(scene, args.profile),
        "cpp": lambda: gate_cpp(cpp),
    }
    results = {}
    for name in GATES:
        if name in skip:
            results[name] = {"status": "skipped", "errors": [], "warnings": []}
            continue
        out = runners[name]()
        if out is None:   # needs input that was not produced (render.py --interact, build_cpp.py)
            need = {"perf": "no scene.json", "cpp": "no C++ host"}.get(name, "no interaction.json")
            results[name] = {"status": "skipped", "errors": [], "warnings": [need]}
            continue
        errors, warns = out
        results[name] = {"status": "fail" if errors else "pass", "errors": errors, "warnings": warns}

    ok = all(r["status"] != "fail" for r in results.values())
    report = {"pass": ok, "mode": args.mode, "files": len(qml_files), "gates": results}
    if args.out:
        args.out.write_text(json.dumps(report, indent=1, ensure_ascii=False))
    for name, r in results.items():
        extra = f" ({len(r['errors'])} errors, {len(r['warnings'])} warnings)" if r["status"] != "skipped" else ""
        print(f"{r['status'].upper():7s} {name}{extra}")
        for e in r["errors"][:10]:
            print(f"   ✗ {e}")
        for w in r["warnings"][:5]:
            print(f"   ! {w}")
    print("PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
