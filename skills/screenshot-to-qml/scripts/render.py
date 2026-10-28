#!/usr/bin/env python3
"""Render a Qt Quick project headlessly to PNG and dump its scene.

Usage:
  python render.py PROJECT_DIR --size 1920 1080 [--dpr 2] [--out render.png]
                   [--scene scene.json] [--module App] [--component Main]
                   [--backend path/to/backend.py] [--wait-ms 500]
                   [--platform auto|native|xvfb|offscreen] [--strict]
                   [--interact [--no-hover]] [--interaction interaction.json] [--lang en]
                   [--scenegraph auto|software]

PROJECT_DIR should contain qml/<Module>/qmldir (loaded with loadFromModule); without one,
qml/<Module>/<Component>.qml (or main.qml) is loaded by file path. Fonts in
assets/fonts/*.ttf|otf are registered before loading. Qt 5.15 projects (qt5.py) load too:
assets/qt5-shim maps `import QtGraphicalEffects 1.15` to Qt 6's Qt5Compat module.

The root object must be a Window/ApplicationWindow; it is resized to --size
(logical px) and rendered at --dpr, so the PNG is size x dpr pixels.

Platform selection (auto):
  - a display is available (Windows, macOS, X11/Wayland)  -> native, window kept hidden-ish
  - Linux without display and xvfb-run present            -> re-run under Xvfb (GPU path, shaders work)
  - otherwise                                             -> offscreen + software backend
    (WARNING: shader effects such as MultiEffect/RectangularShadow do not render)

scene.json lists every visible text item (string, bbox in logical px, font, color),
every Image/VectorImage source with bbox, QML warnings, render metadata, and a `perf` block
for the embedded checks: visible item count, layers, shader-effect items, images decoded larger
than they are drawn, infinite animations and fast repeating timers running while idle, and the
time from loading QML to the first frame. --scenegraph software renders the way an
embedded-sw device does.

--interact (after the screenshot is taken) drives the window with Tab, pointer hover and
press, and writes interaction.json: every control's accessible name and role, whether Tab
reaches it, whether focus/hover/press visibly change it, and MouseAreas used as buttons
(see interact.py). --no-hover skips the hover check (touch profiles).
--lang xx installs PROJECT/i18n/app_xx.qm first, to check a translated layout (longer strings).

Exit codes: 0 rendered, 1 rendered with QML warnings and --strict, 2 failed.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

REEXEC_FLAG = "S2Q_UNDER_XVFB"


def parse_args(argv: list[str]) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("project", type=Path)
    ap.add_argument("--size", type=int, nargs=2, metavar=("W", "H"), required=True)
    ap.add_argument("--dpr", type=float, default=1.0)
    ap.add_argument("--out", type=Path, default=None, help="default: PROJECT/render.png")
    ap.add_argument("--scene", type=Path, default=None, help="default: next to --out as scene.json")
    ap.add_argument("--module", default="App")
    ap.add_argument("--component", default="Main")
    ap.add_argument("--backend", type=Path, default=None, help="Python file to import before loading QML")
    ap.add_argument("--wait-ms", type=int, default=500)
    ap.add_argument("--platform", choices=["auto", "native", "xvfb", "offscreen"], default="auto")
    ap.add_argument("--strict", action="store_true", help="exit 1 when QML emitted warnings")
    ap.add_argument("--interact", action="store_true", help="probe keyboard, pointer and accessibility")
    ap.add_argument("--no-hover", action="store_true", help="with --interact: skip the hover check")
    ap.add_argument("--interaction", type=Path, default=None, help="default: next to --out as interaction.json")
    ap.add_argument("--lang", default=None, help="load PROJECT/i18n/app_<lang>.qm before loading QML")
    ap.add_argument("--scenegraph", choices=["auto", "software"], default="auto",
                    help="software: the GPU-less scene graph an embedded-sw device uses (no shader effects)")
    ap.add_argument("--no-idle-scan", action="store_true",
                    help="skip the scan for idle animations and timers (check.py retries with it when the scan crashes)")
    return ap.parse_args(argv)


def has_display() -> bool:
    if platform.system() in ("Windows", "Darwin"):
        return True
    return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))


def maybe_reexec_under_xvfb(args: argparse.Namespace) -> None:
    want_xvfb = args.platform == "xvfb" or (args.platform == "auto" and not has_display())
    if not want_xvfb or os.environ.get(REEXEC_FLAG):
        return
    xvfb = shutil.which("xvfb-run")
    if not xvfb:
        if args.platform == "xvfb":
            print("[error] --platform xvfb requested but xvfb-run is not installed", file=sys.stderr)
            sys.exit(2)
        return
    w = int(args.size[0] * args.dpr) + 64
    h = int(args.size[1] * args.dpr) + 64
    env = dict(os.environ, **{REEXEC_FLAG: "1"})
    # random start display so parallel renders do not race for :99
    start = str(100 + (os.getpid() * 7919) % 20000)
    cmd = [xvfb, "-a", "-n", start, "-s", f"-screen 0 {w}x{h}x24", sys.executable, os.path.abspath(__file__), *sys.argv[1:]]
    sys.exit(subprocess.call(cmd, env=env))


def configure_env(args: argparse.Namespace) -> str:
    if args.scenegraph == "software":
        os.environ["QT_QUICK_BACKEND"] = "software"
    os.environ["QT_SCALE_FACTOR"] = f"{args.dpr:g}"
    os.environ["QT_SCALE_FACTOR_ROUNDING_POLICY"] = "PassThrough"
    os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")
    if os.environ.get(REEXEC_FLAG):
        os.environ["QT_QPA_PLATFORM"] = "xcb"
        return "xvfb"
    if args.platform == "offscreen" or (args.platform == "auto" and not has_display()):
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        return "offscreen"
    return "native"


def import_backend(path: Path) -> None:
    import importlib.util
    spec = importlib.util.spec_from_file_location("s2q_backend", path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"[error] cannot import backend {path}")
    sys.path.insert(0, str(path.parent))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)


_JS = {}


def prop_int(item, name: str, default: int = 0) -> int:
    """Read an int or enum property. PySide has no converter for QQuickText's enums
    (TextFormat, WrapMode, HAlignment), so enums are read through the QML engine as numbers."""
    try:
        v = item.property(name)
        return default if v is None else int(v)
    except (RuntimeError, TypeError):
        pass
    engine = _JS.get("engine")
    if engine is None:
        return default
    from PySide6.QtQml import QQmlEngine
    QQmlEngine.setObjectOwnership(item, QQmlEngine.ObjectOwnership.CppOwnership)
    v = engine.newQObject(item).property(name)
    return v.toInt() if v.isNumber() else default


def js_value(item, name: str):
    """A property read through the QML engine (for types PySide cannot convert), or None."""
    engine = _JS.get("engine")
    if engine is None:
        return None
    from PySide6.QtQml import QQmlEngine
    QQmlEngine.setObjectOwnership(item, QQmlEngine.ObjectOwnership.CppOwnership)
    v = engine.newQObject(item).property(name)
    return None if v.isUndefined() or v.isNull() else v


def displayed_text(item) -> str:
    """The string as painted: markup stripped, font capitalization applied, NFC."""
    import html
    import re
    import unicodedata

    from PySide6.QtGui import QFont

    s = str(item.property("text") or "")
    if prop_int(item, "textFormat", 2) != 0 and re.search(r"</?[a-zA-Z][^>]*>", s):   # 0 = PlainText
        s = re.sub(r"<br\s*/?>", "\n", s, flags=re.I)
        s = html.unescape(re.sub(r"<[^>]+>", "", s))
    cap = item.property("font").capitalization()
    if cap == QFont.Capitalization.AllUppercase:
        s = s.upper()           # Qt uppercases without locale rules too (i -> I), so this matches the pixels
    elif cap == QFont.Capitalization.AllLowercase:
        s = s.lower()
    return unicodedata.normalize("NFC", s.replace(" ", "\n"))


def text_lines(item, s: str, tb) -> list[dict]:
    """Per-line string, box and cumulative advances, so a scorer can place substrings.

    Line breaks come from explicit newlines plus Qt's own wrapping (QTextLayout with the item's
    font, width and wrap mode). Returns [] when the result disagrees with Text.lineCount.
    """
    from PySide6.QtGui import QFontMetricsF, QTextLayout, QTextOption

    font = item.property("font")
    fm = QFontMetricsF(font)
    n = max(1, prop_int(item, "lineCount", 1))
    wrap = prop_int(item, "wrapMode", 0)
    avail = item.width() - float(item.property("leftPadding") or 0) - float(item.property("rightPadding") or 0)
    lines: list[str] = []
    for part in s.split("\n"):
        if wrap == 0 or avail <= 0 or fm.horizontalAdvance(part) <= avail:
            lines.append(part)
            continue
        layout = QTextLayout(part, font)
        opt = QTextOption()
        opt.setWrapMode(QTextOption.WrapMode(wrap))
        layout.setTextOption(opt)
        layout.beginLayout()
        while True:
            line = layout.createLine()
            if not line.isValid():
                break
            line.setLineWidth(avail)
            lines.append(part[line.textStart(): line.textStart() + line.textLength()].rstrip(" "))
        layout.endLayout()
    if len(lines) != n or tb.height() <= 0:
        return []
    from PySide6.QtCore import QPointF
    local = item.boundingRect()
    sx, sy = scene_scale(item)
    # vertical box = font content area around each baseline (what a browser's Range rect is);
    # the first baseline is the item's own, following lines are evenly spaced over the text box
    base0 = item.mapToScene(QPointF(0, float(item.property("baselineOffset") or 0))).y()
    step = local.height() * sy / n
    asc, desc = fm.ascent() * sy, fm.descent() * sy
    halign = prop_int(item, "effectiveHorizontalAlignment", 1)
    lp = float(item.property("leftPadding") or 0)
    out = []
    for i, ln in enumerate(lines):
        adv = [round(fm.horizontalAdvance(ln[:k]) * sx, 2) for k in range(len(ln) + 1)]
        # horizontal position from the item's own padding and alignment (boundingRect ignores padding)
        w_local = fm.horizontalAdvance(ln)
        local_x = lp + (avail - w_local if halign == 2 else (avail - w_local) / 2 if halign == 4 else 0)
        x = item.mapToScene(QPointF(local_x, 0)).x()
        base = base0 + i * step
        lead = len(ln) - len(ln.lstrip())
        end = len(ln.rstrip())
        x0, x1 = x + adv[lead], x + adv[max(end, lead)]       # box of the visible (trimmed) run
        out.append({"string": ln, "baseline": round(base, 2), "origin": round(x, 2), "adv": adv,
                    "box": [round(x0, 2), round(base - asc, 2), round(x1 - x0, 2), round(asc + desc, 2)]})
    return out


def scene_scale(item) -> tuple[float, float]:
    """How much one local px of the item is in scene px (Item.scale / transforms)."""
    from PySide6.QtCore import QPointF
    o = item.mapToScene(QPointF(0, 0))
    ex, ey = item.mapToScene(QPointF(100, 0)), item.mapToScene(QPointF(0, 100))
    return (ex.x() - o.x()) / 100, (ey.y() - o.y()) / 100


def input_text(item, txt: str, bbox: list) -> dict:
    """Scene entry for a TextInput: box from its padding, alignment and glyph advances."""
    import unicodedata

    from PySide6.QtCore import QPointF
    from PySide6.QtGui import QFontMetricsF

    txt = unicodedata.normalize("NFC", txt)
    font = item.property("font")
    color = item.property("color")
    fm = QFontMetricsF(font)
    lp = float(item.property("leftPadding") or 0)
    rp = float(item.property("rightPadding") or 0)
    avail = item.width() - lp - rp
    sx, sy = scene_scale(item)
    adv = [round(fm.horizontalAdvance(txt[:k]) * sx, 2) for k in range(len(txt) + 1)]
    w = adv[-1]
    halign = prop_int(item, "effectiveHorizontalAlignment", 1)
    local_x = lp + (avail - w / sx if halign == 2 else (avail - w / sx) / 2 if halign == 4 else 0)
    x = item.mapToScene(QPointF(local_x, 0)).x()
    # baseline from padding + verticalAlignment (TextInput.baselineOffset ignores AlignVCenter)
    tp = float(item.property("topPadding") or 0)
    bp = float(item.property("bottomPadding") or 0)
    h = fm.ascent() + fm.descent()
    valign = prop_int(item, "verticalAlignment", 0x20)
    if valign == 0x80:
        top = tp + (item.height() - tp - bp - h) / 2
    elif valign == 0x40:
        top = item.height() - bp - h
    else:
        top = tp
    base = item.mapToScene(QPointF(0, top + fm.ascent())).y()
    asc, desc = fm.ascent() * sy, fm.descent() * sy
    lead = len(txt) - len(txt.lstrip())
    end = max(len(txt.rstrip()), lead)
    box = [round(x + adv[lead], 2), round(base - asc, 2), round(adv[end] - adv[lead], 2), round(asc + desc, 2)]
    return {"string": txt, "bbox": bbox, "textBox": box, "input": True,
            "lines": [{"string": txt, "baseline": round(base, 2), "origin": round(x, 2), "adv": adv, "box": box}],
            "font": {"family": font.family(), "px": font.pixelSize(), "weight": int(font.weight()),
                     "letterSpacing": font.letterSpacing()},
            "color": color.name(color.NameFormat.HexArgb) if hasattr(color, "name") else str(color)}


def edit_text(item, bbox: list) -> dict | None:
    """Scene entry for a TextEdit/TextArea: lines, baselines and advances from its QTextDocument
    layout (plain or rich text, wrapping and block line height as Qt laid them out)."""
    import unicodedata

    from PySide6.QtCore import QPointF
    from PySide6.QtGui import QFontMetricsF

    tdoc = item.property("textDocument")
    doc = tdoc.textDocument() if tdoc is not None and hasattr(tdoc, "textDocument") else None
    if doc is None:
        return None
    font = item.property("font")
    color = item.property("color")
    fm = QFontMetricsF(font)
    sx, sy = scene_scale(item)
    lp = float(item.property("leftPadding") or 0)
    tp = float(item.property("topPadding") or 0)
    # verticalAlignment moves the whole document inside the padded box (TextEdit.AlignVCenter …)
    free = item.height() - tp - float(item.property("bottomPadding") or 0) - float(item.property("contentHeight") or 0)
    valign = prop_int(item, "verticalAlignment", 0x20)
    tp += max(0.0, free) / 2 if valign == 0x80 else max(0.0, free) if valign == 0x40 else 0.0
    asc, desc = fm.ascent() * sy, fm.descent() * sy

    def cx(line, pos: int) -> float:
        r = line.cursorToX(pos)
        return float(r[0] if isinstance(r, tuple) else r)

    lines = []
    block = doc.begin()
    while block.isValid():
        lay, text = block.layout(), block.text()
        bp = lay.position()
        for i in range(lay.lineCount()):
            ln = lay.lineAt(i)
            start, n = ln.textStart(), ln.textLength()
            seg = text[start:start + n].rstrip("\u2028\n")
            if not seg.strip():
                continue
            xs = [cx(ln, start + k) for k in range(len(seg) + 1)]
            origin = item.mapToScene(QPointF(lp + bp.x() + xs[0], 0)).x()
            adv = [round((x - xs[0]) * sx, 2) for x in xs]
            base = item.mapToScene(QPointF(0, tp + bp.y() + ln.y() + ln.ascent())).y()
            lead = len(seg) - len(seg.lstrip())
            end = max(len(seg.rstrip()), lead)
            box = [round(origin + adv[lead], 2), round(base - asc, 2), round(adv[end] - adv[lead], 2), round(asc + desc, 2)]
            lines.append({"string": unicodedata.normalize("NFC", seg.rstrip()), "baseline": round(base, 2),
                          "origin": round(origin, 2), "adv": adv, "box": box})
        block = block.next()
    if not lines:
        return None
    x0 = min(ln["box"][0] for ln in lines)
    y0 = min(ln["box"][1] for ln in lines)
    x1 = max(ln["box"][0] + ln["box"][2] for ln in lines)
    y1 = max(ln["box"][1] + ln["box"][3] for ln in lines)
    return {"string": "\n".join(ln["string"] for ln in lines), "bbox": bbox,
            "textBox": [round(x0, 2), round(y0, 2), round(x1 - x0, 2), round(y1 - y0, 2)], "lines": lines, "edit": True,
            "font": {"family": font.family(), "px": font.pixelSize(), "weight": int(font.weight()),
                     "letterSpacing": font.letterSpacing()},
            "color": color.name(color.NameFormat.HexArgb) if hasattr(color, "name") else str(color)}


def dump_scene(root_item, engine=None, idle_scan: bool = True) -> dict:
    """Walk the item tree and collect texts and images in logical px."""
    from PySide6.QtCore import QRectF
    from PySide6.QtQuick import QQuickItem

    texts, images = [], []
    perf = {"items": 0, "layers": [], "effects": [], "oversizedImages": [], "animations": [], "timers": [],
            "idleScan": idle_scan}
    _JS["engine"] = engine
    effect_classes = ("ShaderEffect", "MultiEffect", "RectangularShadow", "Blur", "DropShadow", "Glow",
                      "OpacityMask", "ColorOverlay", "Desaturate", "BrightnessContrast")

    def idle_work(item) -> None:
        """Infinite animations and fast repeating timers owned by this item.

        Wrapping every child QObject (pens, delivery agents …) can crash PySide on some scenes
        (seen with PySide6 6.11 on a Codex-built project); check.py then renders again with
        --no-idle-scan and the perf gate reports the scan as skipped.
        """
        if not idle_scan:
            return
        from PySide6.QtCore import QObject, Qt
        for obj in item.findChildren(QObject, "", Qt.FindChildOption.FindDirectChildrenOnly):
            mo = obj.metaObject()
            name = mo.className()
            try:
                if obj.inherits("QQuickAbstractAnimation") and obj.property("running") and int(obj.property("loops") or 1) < 0:
                    perf["animations"].append({"class": name, "owner": item.metaObject().className()})
                elif obj.inherits("QQmlTimer") and obj.property("running") and obj.property("repeat"):
                    interval = int(obj.property("interval") or 0)
                    if interval < 250:
                        perf["timers"].append({"interval": interval, "owner": item.metaObject().className()})
            except (RuntimeError, TypeError):
                continue

    def effective_visible(item: QQuickItem) -> bool:
        return item.isVisible() and item.opacity() > 0.001

    def walk(item: QQuickItem) -> None:
        if not effective_visible(item):
            return
        cls = item.metaObject().className()
        rect = item.mapRectToScene(QRectF(0, 0, item.width(), item.height()))
        bbox = [round(rect.x(), 2), round(rect.y(), 2), round(rect.width(), 2), round(rect.height(), 2)]
        perf["items"] += 1
        layer = js_value(item, "layer")      # QQuickItemLayer has no PySide converter
        if layer is not None and layer.property("enabled").toBool():
            effect = layer.property("effect")
            perf["layers"].append({"class": cls, "bbox": bbox, "effect": not (effect.isNull() or effect.isUndefined())})
        if any(k in cls for k in effect_classes):
            perf["effects"].append({"class": cls, "bbox": bbox})
        idle_work(item)
        # inherits(), not the class name: QML components wrapping Text (AppText_QMLTYPE_3) and
        # Controls' Label (QQuickLabel) are texts too
        if item.inherits("QQuickText"):
            txt = displayed_text(item)
            if txt.strip():
                font = item.property("font")
                color = item.property("color")
                tb = item.mapRectToScene(item.boundingRect())
                lines = text_lines(item, txt, tb)
                if lines:   # union of the per-line boxes (padding and alignment applied)
                    x0 = min(ln["box"][0] for ln in lines)
                    y0 = min(ln["box"][1] for ln in lines)
                    x1 = max(ln["box"][0] + ln["box"][2] for ln in lines)
                    y1 = max(ln["box"][1] + ln["box"][3] for ln in lines)
                    box = [round(x0, 2), round(y0, 2), round(x1 - x0, 2), round(y1 - y0, 2)]
                else:       # fallback: QQuickText::boundingRect (ignores padding)
                    box = [round(tb.x(), 2), round(tb.y(), 2), round(tb.width(), 2), round(tb.height(), 2)]
                texts.append({
                    "string": txt, "bbox": bbox, "textBox": box, "lines": lines,
                    "font": {"family": font.family(), "px": font.pixelSize(), "weight": int(font.weight()),
                             "letterSpacing": font.letterSpacing()},
                    "color": color.name(color.NameFormat.HexArgb) if hasattr(color, "name") else str(color),
                })
        elif item.inherits("QQuickTextInput"):
            # TextField/TextInput values (displayText applies echo mode); one line, no wrapping
            txt = str(item.property("displayText") or "")
            if txt.strip():
                texts.append(input_text(item, txt, bbox))
        elif item.inherits("QQuickTextEdit"):
            # TextArea/TextEdit: multi-line, possibly rich text
            entry = edit_text(item, bbox)
            if entry:
                texts.append(entry)
        elif item.inherits("QQuickImage") or item.inherits("QQuickVectorImage"):
            src = item.property("source")
            source = src.toString() if hasattr(src, "toString") else str(src)
            images.append({"class": cls, "source": source, "bbox": bbox})
            if item.inherits("QQuickImage") and not source.lower().endswith(".svg"):
                decoded = item.property("sourceSize")
                dw, dh = (decoded.width(), decoded.height()) if decoded is not None else (0, 0)
                dpr = item.window().effectiveDevicePixelRatio() if item.window() else 1.0
                need = max(1.0, rect.width() * dpr) * max(1.0, rect.height() * dpr)
                if dw > 0 and dh > 0 and dw * dh > 2.0 * need:
                    perf["oversizedImages"].append({"source": source, "decoded": [dw, dh],
                                                    "drawn": [round(rect.width() * dpr), round(rect.height() * dpr)],
                                                    "ratio": round(dw * dh / need, 1)})
        for child in item.childItems():
            walk(child)

    walk(root_item)
    return {"texts": texts, "images": images, "perf": perf}


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    project = args.project.resolve()
    module_dir = project / "qml" / args.module.replace(".", "/")
    main_file = None
    if not (module_dir / "qmldir").exists():
        # no module: fall back to loading the component by file path (scores projects that skip qmldir)
        candidates = [module_dir / f"{args.component}.qml", project / "qml" / f"{args.component}.qml",
                      project / f"{args.component.lower()}.qml", project / f"{args.component}.qml"]
        main_file = next((c for c in candidates if c.exists()), None)
        if main_file is None:
            print(f"[error] {module_dir}/qmldir not found (and no {args.component}.qml to load by path)", file=sys.stderr)
            return 2
        print(f"[warn] no qmldir: loading {main_file.relative_to(project)} by file path", file=sys.stderr)
    maybe_reexec_under_xvfb(args)
    mode = configure_env(args)

    from PySide6.QtCore import QTimer
    from PySide6.QtGui import QFontDatabase, QGuiApplication
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtQuick import QQuickWindow

    app = QGuiApplication(sys.argv[:1])
    fonts = {}
    font_dir = project / "assets" / "fonts"
    if font_dir.is_dir():
        for f in sorted(font_dir.iterdir()):
            if f.suffix.lower() in (".ttf", ".otf", ".ttc"):
                fid = QFontDatabase.addApplicationFont(str(f))
                fonts[f.name] = QFontDatabase.applicationFontFamilies(fid) if fid != -1 else None
    if args.backend:
        import_backend(args.backend.resolve())
    if args.lang:
        from PySide6.QtCore import QLocale, QTranslator
        translator = QTranslator(app)
        if not translator.load(QLocale(args.lang), "app", "_", str(project / "i18n")):
            print(f"[error] no translation for '{args.lang}' in {project / 'i18n'} (app_{args.lang}.qm)", file=sys.stderr)
            return 2
        app.installTranslator(translator)

    import time
    t_load = time.perf_counter()
    first_frame: dict = {}
    warnings: list[str] = []
    engine = QQmlApplicationEngine()
    engine.warnings.connect(lambda ws: warnings.extend(w.toString() for w in ws))
    engine.addImportPath(str(project / "qml"))
    # Qt 5.15 projects import QtGraphicalEffects 1.15: the shim maps it to Qt5Compat.GraphicalEffects
    engine.addImportPath(str(Path(__file__).resolve().parent.parent / "assets" / "qt5-shim"))
    if main_file is None:
        engine.loadFromModule(args.module, args.component)
    else:
        from PySide6.QtCore import QUrl
        engine.load(QUrl.fromLocalFile(str(main_file)))
    roots = engine.rootObjects()
    if not roots:
        print("[error] QML failed to load:\n  " + "\n  ".join(warnings), file=sys.stderr)
        return 2
    window = roots[0]
    if not isinstance(window, QQuickWindow):
        print("[error] root object is not a Window; wrap the UI in Window/ApplicationWindow", file=sys.stderr)
        return 2
    w, h = args.size
    window.resize(w, h)
    window.setWidth(w)
    window.setHeight(h)
    if mode == "native":
        window.setPosition(-10 * w, -10 * h)  # keep it out of sight
    window.frameSwapped.connect(lambda: first_frame.setdefault("ms", round((time.perf_counter() - t_load) * 1000)))
    window.show()

    out = (args.out or project / "render.png").resolve()
    scene_path = (args.scene or out.with_name("scene.json")).resolve()
    result = {"code": 2}

    def grab() -> None:
        try:
            _grab()
        except Exception as exc:  # never leave the event loop hanging
            print(f"[error] render failed: {exc!r}", file=sys.stderr)
            result["code"] = 2
            app.quit()

    def _grab() -> None:
        img = window.grabWindow()
        expected = (round(w * args.dpr), round(h * args.dpr))
        if (img.width(), img.height()) != expected:
            warnings.append(f"render size {img.width()}x{img.height()} != expected {expected[0]}x{expected[1]}")
        out.parent.mkdir(parents=True, exist_ok=True)
        img.save(str(out))
        scene = dump_scene(window.contentItem(), engine, idle_scan=not args.no_idle_scan)
        scene["perf"]["firstFrameMs"] = first_frame.get("ms")
        scene.update({
            "render": {"file": out.name, "size": [img.width(), img.height()], "logicalSize": [w, h],
                       "dpr": args.dpr, "platform": mode, "graphicsApi": str(QQuickWindow.graphicsApi()),
                       "scenegraph": args.scenegraph,
                       "sceneGraphBackend": QQuickWindow.sceneGraphBackend() or "rhi"},
            "fonts": fonts,
            "warnings": warnings,
        })
        scene_path.write_text(json.dumps(scene, indent=1, ensure_ascii=False))
        if mode == "offscreen":
            print("[warn] offscreen/software rendering: shader effects are not drawn", file=sys.stderr)
        for m in warnings:
            print(f"[qml] {m}", file=sys.stderr)
        print(f"rendered {out} ({img.width()}x{img.height()}, {mode}); scene {scene_path.name}: "
              f"{len(scene['texts'])} texts, {len(scene['images'])} images, {len(warnings)} warnings")
        result["code"] = 1 if (warnings and args.strict) else 0
        if args.interact:
            sys.path.insert(0, str(Path(__file__).resolve().parent))
            import interact
            # a pressed control may quit the app (Qt.quit()) or close the window: keep both alive
            # for the probe and record it instead of letting the event loop end under it
            app.setQuitOnLastWindowClosed(False)
            for sig in (engine.quit, engine.exit):
                try:
                    sig.disconnect()
                except (RuntimeError, TypeError):
                    pass
            quit_calls: list[str] = []
            engine.quit.connect(lambda: quit_calls.append("Qt.quit()"))
            engine.exit.connect(lambda code: quit_calls.append(f"Qt.exit({code})"))
            # a fresh wrapper: walking the scene can leave the Python wrapper of the root stale
            # (the C++ window is alive; findChildren/window() hand out new wrappers for it)
            roots_now = engine.rootObjects()
            probe_window = roots_now[0] if roots_now and isinstance(roots_now[0], QQuickWindow) else window
            try:
                data = interact.probe(probe_window, args.dpr, check_hover=not args.no_hover)
            except RuntimeError as exc:     # the window was deleted anyway
                data = {"error": f"interaction probe stopped: {exc}", "controls": [], "mouseAreas": []}
                print(f"[warn] {data['error']} (a control quit the app or closed the window when pressed)", file=sys.stderr)
            if quit_calls:
                data["quitCalls"] = sorted(set(quit_calls))
            ipath = (args.interaction or out.with_name("interaction.json")).resolve()
            ipath.write_text(json.dumps(data, indent=1, ensure_ascii=False))
            n = len(data["controls"])
            reached = sum(c["tabReached"] for c in data["controls"])
            print(f"interaction {ipath.name}: {n} controls, {reached} reached by Tab, "
                  f"{len(data['mouseAreas'])} MouseAreas")
        app.quit()

    QTimer.singleShot(args.wait_ms, grab)  # grabWindow renders a fresh frame itself
    app.exec()
    return result["code"]


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
