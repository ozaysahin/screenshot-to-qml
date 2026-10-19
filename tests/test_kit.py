"""v0.5 production kit: control roles, scaffold pruning, the kit itself, and the a11y /
states / i18n gates (static logic here, the live probe on the controls gallery)."""
import json
import shutil
import subprocess
import sys

import quality_gate
from conftest import SCRIPTS, SKILL, requires_render

KIT = SKILL / "assets" / "templates" / "project"
GALLERY = SKILL / "examples" / "controls-gallery" / "project"
CONTRACT = ["bg", "surface", "text", "textMuted", "placeholder", "accent", "accentInk", "accentHover", "accentPressed",
            "border", "borderStrong", "surfaceHover", "surfacePressed", "danger", "dangerInk", "dangerHover",
            "dangerPressed", "dangerSoft", "focusRing", "track", "knob", "controlHeight", "controlHeightSm",
            "controlPadding", "controlSpacing", "touchTarget", "radiusControl", "borderWidth", "focusRingWidth",
            "motionFast", "disabledOpacity", "fontControl", "fontInput", "fontIcon"]


def spec(colors, profile="desktop", width=1440):
    return {"meta": {"designSize": [width, 900], "dpr": 1, "profile": profile},
            "tokens": {"color": {k: {"hex": v, "alpha": 1} for k, v in colors.items()},
                       "radius": {"sm": 6, "lg": 12},
                       "typeScale": [{"name": "body", "family": "Inter", "px": 14, "weight": 400}]},
            "nodes": [], "text": []}


def theme_props(text):
    import re
    return dict(re.findall(r"readonly property \w+ (\w+): ([^\n]+)", text))


def test_gen_theme_emits_the_whole_control_contract():
    import gen_theme
    props = theme_props(gen_theme.build_theme(spec({"page": "#FFFFFF", "ink": "#111827", "primary": "#4F46E5"})))
    assert [name for name in CONTRACT if name not in props] == []
    assert props["accent"] == "primary" and props["bg"] == "page" and props["text"] == "ink"   # aliases
    assert props["accentHover"].startswith("Qt.darker")                                       # light UI
    assert props["radiusControl"].startswith("radiusSm")
    assert props["fontInput"].startswith("body")


def test_gen_theme_roles_follow_dark_ui_and_touch_profile():
    import gen_theme
    props = theme_props(gen_theme.build_theme(spec({"bg": "#0B0F14", "text": "#E6EDF5", "accent": "#0EA5E9"},
                                                   profile="embedded-gpu")))
    assert props["accentHover"].startswith("Qt.lighter")
    assert props["controlHeight"].startswith("48")
    assert props["accentInk"].strip('"').startswith("#0B0F14")          # dark ink on a light-blue accent


def test_spec_tokens_win_over_derived_roles():
    import gen_theme
    text = gen_theme.build_theme(spec({"bg": "#FFFFFF", "text": "#111111", "accent": "#2563EB", "accentHover": "#1D4ED8"}))
    assert text.count("property color accentHover") == 1 and 'accentHover: "#1D4ED8"' in text


def test_scaffold_keeps_only_requested_controls(tmp_path):
    res = subprocess.run([sys.executable, str(SCRIPTS / "scaffold.py"), str(tmp_path / "p"), "--name", "T",
                          "--controls", "Slider,TabBar"], capture_output=True, text=True)
    assert res.returncode == 0, res.stderr
    ctrl = tmp_path / "p" / "qml" / "App" / "Controls"
    assert sorted(p.stem for p in ctrl.glob("*.qml")) == ["FocusRing", "Slider", "TabBar", "TabButton"]
    assert "Slider 1.0 Slider.qml" in (ctrl / "qmldir").read_text()
    assert (tmp_path / "p" / "i18n").is_dir()
    bad = subprocess.run([sys.executable, str(SCRIPTS / "scaffold.py"), str(tmp_path / "q"), "--name", "T",
                          "--controls", "Knob"], capture_output=True, text=True)
    assert bad.returncode == 2 and "unknown controls" in bad.stderr


def test_kit_is_lint_format_and_literal_clean():
    files = sorted((KIT / "qml" / "App" / "Controls").glob("*.qml"))
    assert len(files) == 15
    errors, warnings = quality_gate.gate_hardcode(KIT, files, "production")
    assert errors == [] and warnings == []
    errors, _ = quality_gate.gate_format(KIT, files)
    assert errors == []
    lint = shutil.which("pyside6-qmllint") or shutil.which("qmllint")
    if lint:
        res = subprocess.run([lint, "--max-warnings", "0", "-I", str(KIT / "qml"), *map(str, files)],
                             capture_output=True, text=True)
        assert res.returncode == 0, res.stdout + res.stderr


def test_i18n_gate(tmp_path):
    app = tmp_path / "qml" / "App"
    app.mkdir(parents=True)
    (app / "Main.qml").write_text(
        'Item {\n    Text { text: "Kaydet" }\n    Text { text: qsTr("İptal") }\n    Text { text: "%" }\n'
        '    ListModel { ListElement { name: "Tank A"; text: "veri" } }\n'
        '    Repeater { model: ["Gün", "Hafta"] }\n'
        '    Rectangle { border.color: ok ? Theme.text : "transparent" }\n}\n')
    (app / "MockData.qml").write_text('QtObject { property string title: "Hat 3"\n  property var t: { text: "x" } }\n')
    errors, _ = quality_gate.gate_i18n(tmp_path, sorted(tmp_path.rglob("*.qml")), "production")
    assert [e.split(":")[1] for e in errors] == ["2", "6"]
    _, warns = quality_gate.gate_i18n(tmp_path, sorted(tmp_path.rglob("*.qml")), "fidelity")
    assert len(warns) == 2


def control(**kw):
    c = {"type": "Button", "kind": "button", "bbox": [10, 10, 80, 40], "enabled": True, "name": "Kaydet",
         "role": "Button", "text": "Kaydet", "tabReached": True, "focusVisible": True, "hoverChanges": True,
         "pressChanges": True}
    c.update(kw)
    return c


def test_a11y_and_states_gates():
    inter = {"controls": [control(), control(tabReached=False, focusVisible=None), control(focusVisible=False),
                          control(name="", text=""), control(enabled=False, tabReached=False, name="Off"),
                          control(pressChanges=False, hoverChanges=False)],
             "duplicateTabStops": ["SpinBox:"], "hoverChecked": True,
             "mouseAreas": [{"bbox": [0, 0, 40, 40], "parent": "Rectangle", "clickable": True, "accessibleControl": False},
                            {"bbox": [0, 0, 40, 40], "parent": "Chip", "clickable": True, "accessibleControl": True},
                            {"bbox": [0, 0, 800, 600], "parent": "Item", "clickable": False, "accessibleControl": False}]}
    errors, warns = quality_gate.gate_a11y(inter, "desktop", "production")
    assert sum("Tab never reaches" in e for e in errors) == 1        # the disabled one is exempt
    assert sum("not visible" in e for e in errors) == 1
    assert sum("no accessible name" in e for e in errors) == 1
    assert sum("MouseArea" in e for e in errors) == 1                # only the plain clickable one
    assert any("more than once" in w for w in warns)
    _, warns_touch = quality_gate.gate_a11y({**inter, "controls": [control(bbox=[0, 0, 30, 30])], "mouseAreas": []},
                                            "embedded-gpu")
    assert any("touch target" in w for w in warns_touch)
    errors, warns = quality_gate.gate_states(inter, "production", "desktop")
    assert len(errors) == 1 and "pressed" in errors[0] and any("hover" in w for w in warns)
    assert quality_gate.gate_a11y(None, "desktop") is None


@requires_render
def test_gallery_passes_every_gate_with_a_live_probe(tmp_path):
    out = tmp_path / "r"
    res = subprocess.run([sys.executable, str(SCRIPTS / "render.py"), str(GALLERY), "--size", "1200", "760",
                          "--out", str(out / "render.png"), "--interact"], capture_output=True, text=True, timeout=300)
    assert res.returncode == 0, res.stderr
    inter = json.loads((out / "interaction.json").read_text())
    enabled = [c for c in inter["controls"] if c["enabled"]]
    assert len(enabled) == 27 and inter["duplicateTabStops"] == [] and inter["mouseAreas"] == []
    assert all(c["tabReached"] and c["focusVisible"] and c["pressChanges"] is not False for c in enabled)
    assert all(c["name"] for c in inter["controls"])
    gate = subprocess.run([sys.executable, str(SCRIPTS / "quality_gate.py"), str(GALLERY), "--scene",
                           str(out / "scene.json"), "--interaction", str(out / "interaction.json")],
                          capture_output=True, text=True, timeout=300)
    assert gate.returncode == 0, gate.stdout


@requires_render
def test_render_loads_a_translation(tmp_path):
    res = subprocess.run([sys.executable, str(SCRIPTS / "render.py"), str(GALLERY), "--size", "1200", "760",
                          "--lang", "tr", "--out", str(tmp_path / "r.png")], capture_output=True, text=True, timeout=180)
    assert res.returncode == 0, res.stderr
    strings = {t["string"] for t in json.loads((tmp_path / "scene.json").read_text())["texts"]}
    assert {"Kontrol galerisi", "Kaydet", "Güvenlik"} <= strings
