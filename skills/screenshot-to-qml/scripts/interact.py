"""Interaction probe used by render.py --interact (runs inside the rendered window).

Finds the interactive controls, then drives the real window with synthetic input:

  Tab walk     presses Tab until focus cycles; records which controls take keyboard focus,
               in which order, and whether the focused control's pixels change (a visible
               focus indication)
  hover/press  for each enabled control: pointer away → over it → pressed (then dragged off
               and released outside, so no click fires) and whether its pixels change
  names        the accessible name a screen reader gets (Accessible.name, else the control's
               text / placeholder, as Qt does) and the accessible role

Result: a dict for interaction.json, read by quality_gate.py (a11y and states gates).
"""
from __future__ import annotations

import re

INTERACTIVE = ("QQuickAbstractButton", "QQuickSlider", "QQuickRangeSlider", "QQuickComboBox", "QQuickSpinBox",
               "QQuickDial", "QQuickTextField", "QQuickTextArea")
TEXT_EDITORS = ("QQuickTextInput", "QQuickTextEdit")
PRESS_KINDS = ("button", "slider", "combobox", "spinbox", "dial")
# a hand-made control is acceptable when it takes Tab focus and announces an interactive role
INTERACTIVE_ROLES = {"Button", "CheckBox", "RadioButton", "PageTab", "ListItem", "MenuItem", "Link", "ComboBox",
                     "Slider", "SpinBox", "ButtonMenu", "ButtonDropDown", "Cell", "Row", "TreeItem", "EditableText"}
FOCUS_PAD = 6          # logical px around a control to look for its focus ring
CHANGE_LEVEL = 4       # 8-bit levels (max over R, G, B) that count as a changed pixel
SETTLE_MS = 40


def _key(item) -> int:
    import shiboken6
    return shiboken6.getCppPointer(item)[0]


def _kind(item) -> str:
    for cls, kind in (("QQuickAbstractButton", "button"), ("QQuickSlider", "slider"), ("QQuickRangeSlider", "slider"),
                      ("QQuickComboBox", "combobox"), ("QQuickSpinBox", "spinbox"), ("QQuickDial", "dial")):
        if item.inherits(cls):
            return kind
    return "text"


def _type_name(item) -> str:
    return re.sub(r"(?:_QMLTYPE_\d+|_QML_\d+)+$", "", item.metaObject().className()).removeprefix("QQuick")


def _visible(item) -> bool:
    while item is not None:
        if not item.isVisible() or item.opacity() <= 0.001:
            return False
        item = item.parentItem()
    return True


def collect(root) -> tuple[list, list]:
    """Interactive controls (enabled or not) and MouseAreas outside controls, in tree order."""
    controls, mouse_areas = [], []

    def walk(item, inside: bool) -> None:
        if not item.isVisible() or item.opacity() <= 0.001:
            return
        is_ctrl = any(item.inherits(c) for c in INTERACTIVE)
        if not is_ctrl and not inside and any(item.inherits(c) for c in TEXT_EDITORS):
            is_ctrl = not bool(item.property("readOnly"))
        if is_ctrl:
            controls.append(item)
        elif not inside and item.inherits("QQuickMouseArea") and item.isEnabled():
            mouse_areas.append(item)
        for child in item.childItems():
            walk(child, inside or is_ctrl)

    walk(root, False)
    return controls, mouse_areas


def accessible(item) -> tuple[str, str]:
    from PySide6.QtGui import QAccessible
    name, role = "", ""
    iface = QAccessible.queryAccessibleInterface(item)
    if iface is not None and iface.isValid():
        name = iface.text(QAccessible.Text.Name) or ""
        role = iface.role().name
    if not name:   # without an AT attached Qt fills the name lazily; these are the defaults it uses
        for prop in ("text", "placeholderText"):
            if item.inherits("QQuickAbstractButton") or prop == "placeholderText":
                v = item.property(prop)
                if isinstance(v, str) and v.strip():
                    name = v.strip()
                    break
    return name, role


def probe(window, dpr: float, check_hover: bool = True) -> dict:
    import numpy as np
    from PySide6.QtCore import QEvent, QObject, QPoint, QRectF, Qt
    from PySide6.QtGui import QImage
    from PySide6.QtTest import QTest

    class _KeepOpen(QObject):
        """Refuse Close events while probing: a control that closes the window on press must not
        take the window (and the probe) down with it."""
        attempts = 0

        def eventFilter(self, obj, ev):           # noqa: N802 (Qt API)
            if ev.type() == QEvent.Type.Close:
                _KeepOpen.attempts += 1
                ev.ignore()
                return True
            return False

    keep_open = _KeepOpen()
    window.installEventFilter(keep_open)
    root = window.contentItem()
    controls, mouse_areas = collect(root)
    index = {_key(c): i for i, c in enumerate(controls)}
    W, H = window.width(), window.height()

    def rect(item):
        r = item.mapRectToScene(QRectF(0, 0, item.width(), item.height()))
        return [round(r.x(), 2), round(r.y(), 2), round(r.width(), 2), round(r.height(), 2)]

    def grab():
        img = window.grabWindow().convertToFormat(QImage.Format.Format_RGB888)
        w, h, bpl = img.width(), img.height(), img.bytesPerLine()
        return np.frombuffer(img.constBits(), np.uint8, bpl * h).reshape(h, bpl)[:, :w * 3].reshape(h, w, 3).copy()

    def changed(a, b, box, pad=0.0) -> bool:
        x, y, w, h = box
        x0, y0 = max(0, int((x - pad) * dpr)), max(0, int((y - pad) * dpr))
        x1, y1 = min(a.shape[1], int((x + w + pad) * dpr + 1)), min(a.shape[0], int((y + h + pad) * dpr + 1))
        if x1 <= x0 or y1 <= y0:
            return False
        d = np.abs(a[y0:y1, x0:x1].astype(np.int16) - b[y0:y1, x0:x1].astype(np.int16)).max(axis=2) > CHANGE_LEVEL
        return int(d.sum()) >= max(4, 0.002 * d.size)

    def owner(item):
        while item is not None:
            i = index.get(_key(item))
            if i is not None:
                return i
            item = item.parentItem()
        return None

    info = []
    for c in controls:
        name, role = accessible(c)
        info.append({"type": _type_name(c), "kind": _kind(c), "bbox": rect(c), "enabled": c.isEnabled(),
                     "name": name, "role": role, "text": str(c.property("text") or "")[:60],
                     "tabReached": False, "focusVisible": None, "hoverChanges": None, "pressChanges": None})

    window.requestActivate()
    QTest.qWait(SETTLE_MS)

    # --- keyboard: Tab until focus comes back to the first control it reached
    order, first, prev = [], None, grab()
    for _ in range(3 * len(controls) + 10):
        QTest.keyClick(window, Qt.Key.Key_Tab)
        QTest.qWait(SETTLE_MS // 2)
        img = grab()
        o = owner(window.activeFocusItem())
        if o is not None:
            if o == first:
                break
            first = o if first is None else first
            if not info[o]["tabReached"]:
                info[o]["tabReached"] = True
                info[o]["focusVisible"] = changed(prev, img, info[o]["bbox"], FOCUS_PAD)
        order.append(o)
        prev = img
    stops = [o for o in order if o is not None]
    duplicates = sorted({info[o]["type"] + ":" + info[o]["text"] for o in stops if stops.count(o) > 1})

    # --- pointer: hover and press on every enabled, on-screen control
    away = QPoint(W - 2, H - 2)
    for i, c in enumerate(controls):
        x, y, w, h = info[i]["bbox"]
        if not info[i]["enabled"] or w < 2 or h < 2 or x + w < 0 or y + h < 0 or x > W or y > H or not _visible(c):
            continue
        center = QPoint(int(min(max(x + w / 2, 1), W - 2)), int(min(max(y + h / 2, 1), H - 2)))
        QTest.mouseMove(window, away)
        QTest.qWait(SETTLE_MS)
        base = grab()
        QTest.mouseMove(window, center)
        QTest.qWait(SETTLE_MS)
        hover = grab()
        if check_hover:
            info[i]["hoverChanges"] = changed(base, hover, info[i]["bbox"], 2)
        if info[i]["kind"] in PRESS_KINDS:
            QTest.mousePress(window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, center)
            QTest.qWait(SETTLE_MS)
            pressed = grab()
            info[i]["pressChanges"] = changed(hover, pressed, info[i]["bbox"], 2) or changed(base, pressed, info[i]["bbox"], 2)
            QTest.mouseMove(window, away)        # drag off before releasing: no click, no side effects
            QTest.mouseRelease(window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, away)
            QTest.qWait(SETTLE_MS // 2)
            if _KeepOpen.attempts:               # the press tried to close the window: note it
                info[i]["closesWindow"] = True
                _KeepOpen.attempts = 0
            if not window.isVisible():
                window.show()
                QTest.qWait(SETTLE_MS)
        QTest.keyClick(window, Qt.Key.Key_Escape)   # close a popup a press may have opened

    hover_seen = any(v["hoverChanges"] for v in info)
    if check_hover and not hover_seen:           # hover events not delivered here: unknown, not failed
        for v in info:
            v["hoverChanges"] = None
    areas = []
    for m in mouse_areas:
        try:
            buttons = int(m.property("acceptedButtons"))
        except (TypeError, ValueError, RuntimeError):
            buttons = 1
        box = rect(m)
        host = m.parentItem()
        _, role = accessible(host) if host is not None else ("", "")
        custom_ok = host is not None and bool(host.property("activeFocusOnTab")) and role in INTERACTIVE_ROLES
        backdrop = box[2] * box[3] >= 0.5 * W * H          # click-outside / background handlers
        areas.append({"bbox": box, "parent": _type_name(host) if host is not None else None,
                      "clickable": buttons != 0 and not backdrop, "accessibleControl": custom_ok})
    window.removeEventFilter(keep_open)
    return {
        "controls": info,
        "tabOrder": stops,
        "duplicateTabStops": duplicates,
        "mouseAreas": areas,
        "hoverChecked": bool(check_hover and hover_seen),
    }
