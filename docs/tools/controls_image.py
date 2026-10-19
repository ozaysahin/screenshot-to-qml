#!/usr/bin/env python3
"""Build docs/img/controls.png: the controls gallery plus a strip of interaction states.

Usage (Linux without a display: wrap in xvfb-run -a -s "-screen 0 1400x1200x24"):
  python docs/tools/controls_image.py

Loads skills/screenshot-to-qml/examples/controls-gallery at 2x, grabs the page, then drives
a few controls with QTest (hover, press, Tab focus) and crops each state.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROJECT = ROOT / "skills" / "screenshot-to-qml" / "examples" / "controls-gallery" / "project"
OUT = ROOT / "docs" / "img" / "controls.png"
DPR = 2
os.environ.setdefault("QT_QPA_PLATFORM", "xcb")
os.environ["QT_SCALE_FACTOR"] = str(DPR)
os.environ["QT_SCALE_FACTOR_ROUNDING_POLICY"] = "PassThrough"

import numpy as np  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402
from PySide6.QtCore import QPoint, QRectF, Qt, QTimer  # noqa: E402
from PySide6.QtGui import QFontDatabase, QGuiApplication, QImage  # noqa: E402
from PySide6.QtQml import QQmlApplicationEngine  # noqa: E402
from PySide6.QtQuick import QQuickWindow  # noqa: F401,E402
from PySide6.QtTest import QTest  # noqa: E402


def to_pil(img: QImage) -> Image.Image:
    img = img.convertToFormat(QImage.Format.Format_RGB888)
    w, h, bpl = img.width(), img.height(), img.bytesPerLine()
    arr = np.frombuffer(img.constBits(), np.uint8, bpl * h).reshape(h, bpl)[:, :w * 3].reshape(h, w, 3)
    return Image.fromarray(arr.copy())


def find(item, text):
    if str(item.property("text") or "") == text and item.inherits("QQuickControl"):
        return item
    for c in item.childItems():
        r = find(c, text)
        if r is not None:
            return r
    return None


def clear_focus(win) -> None:
    item = win.activeFocusItem()
    if item is not None and item is not win.contentItem():
        item.setFocus(False)
    QTest.qWait(30)


def focus_by_tab(win, item) -> None:
    """Give `item` keyboard focus the way a user would: Tab from the first control."""
    first = find(win.contentItem(), "Notifications")
    first.forceActiveFocus(Qt.FocusReason.TabFocusReason)
    for _ in range(80):
        if item.hasActiveFocus():
            break
        QTest.keyClick(win, Qt.Key.Key_Tab)
        QTest.qWait(10)
    QTest.qWait(40)
    if not item.property("visualFocus"):
        print(f"[warn] no visualFocus on {item.property('text')}", file=sys.stderr)


def main() -> int:
    app = QGuiApplication(sys.argv[:1])
    for f in (PROJECT / "assets" / "fonts").iterdir():
        QFontDatabase.addApplicationFont(str(f))
    engine = QQmlApplicationEngine()
    engine.addImportPath(str(PROJECT / "qml"))
    engine.loadFromModule("App", "Main")
    win = engine.rootObjects()[0]
    win.show()
    result = {}

    def shoot():
        try:
            win.requestActivate()
            QTest.qWait(150)
            page = to_pil(win.grabWindow())
            clear_focus(win)                              # no focus ring in the "default" column
            away = QPoint(win.width() - 2, win.height() - 2)
            strip = []
            for label, pad in (("Save", 8), ("Cancel", 8), ("Automatic updates", 8)):
                item = find(win.contentItem(), label)
                r = item.mapRectToScene(QRectF(0, 0, item.width(), item.height()))
                box = tuple(int(v * DPR) for v in (r.x() - pad, r.y() - pad, r.right() + pad, r.bottom() + pad))
                center = QPoint(int(r.center().x()), int(r.center().y()))
                states = []
                clear_focus(win)
                QTest.mouseMove(win, away)
                QTest.qWait(60)
                states.append(("default", to_pil(win.grabWindow()).crop(box)))
                QTest.mouseMove(win, center)
                QTest.qWait(60)
                states.append(("hover", to_pil(win.grabWindow()).crop(box)))
                QTest.mousePress(win, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, center)
                QTest.qWait(60)
                states.append(("pressed", to_pil(win.grabWindow()).crop(box)))
                checked = item.property("checked")
                QTest.mouseMove(win, away)
                QTest.mouseRelease(win, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, away)
                item.setProperty("checked", checked)      # a switch toggles when dragged off
                focus_by_tab(win, item)
                QTest.qWait(60)
                states.append(("keyboard focus", to_pil(win.grabWindow()).crop(box)))
                item.setProperty("enabled", False)
                QTest.qWait(60)
                states.append(("disabled", to_pil(win.grabWindow()).crop(box)))
                item.setProperty("enabled", True)
                clear_focus(win)
                strip.append(states)
            result["page"], result["strip"] = page, strip
        finally:
            app.quit()

    QTimer.singleShot(400, shoot)
    app.exec()
    page, strip = result["page"], result["strip"]

    bg = (244, 245, 250)
    cell_w = max(img.width for row in strip for _, img in row)
    cell_h = max(img.height for row in strip for _, img in row)
    gap, label_h = 24 * DPR // 2, 22 * DPR
    strip_w = 5 * cell_w + 4 * gap
    strip_h = label_h + len(strip) * cell_h + (len(strip) - 1) * gap // 2
    canvas = Image.new("RGB", (page.width, page.height + strip_h + 56 * DPR), bg)
    canvas.paste(page, (0, 0))
    draw = ImageDraw.Draw(canvas)
    pad = 16 * DPR
    draw.rounded_rectangle((32 * DPR, page.height - 8 * DPR, page.width - 32 * DPR, page.height + strip_h + 24 * DPR),
                           radius=14 * DPR, fill=(255, 255, 255), outline=(229, 231, 235), width=DPR)
    font_path = PROJECT / "assets" / "fonts" / "Inter-SemiBold.ttf"
    font = ImageFont.truetype(str(font_path), 13 * DPR)
    x0 = (page.width - strip_w) // 2
    y0 = page.height + 8 * DPR + pad // 2
    for col, (name, _) in enumerate(strip[0]):
        draw.text((x0 + col * (cell_w + gap) + 4, y0), name, fill=(107, 114, 128), font=font)
    for row, states in enumerate(strip):
        for col, (_, img) in enumerate(states):
            x = x0 + col * (cell_w + gap)
            y = y0 + label_h + row * (cell_h + gap // 2)
            canvas.paste(img, (x, y))
    canvas = canvas.resize((canvas.width // 2, canvas.height // 2), Image.LANCZOS)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(OUT, optimize=True)
    print(f"wrote {OUT} ({canvas.width}x{canvas.height})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
