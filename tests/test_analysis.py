import json
import shutil

import cv2
import geometry
import numpy as np
import palette
import pytest
import validate_spec

from conftest import EVALS

CASE = EVALS / "cases" / "05-settings-form"


def synthetic(tmp_path):
    img = np.full((200, 320, 3), 246, np.uint8)                                  # page #F6F6F6
    cv2.rectangle(img, (20, 20), (299, 179), (0xE2, 0xE8, 0xF0)[::-1], -1)        # border ring
    cv2.rectangle(img, (21, 21), (298, 178), (255, 255, 255), -1)                  # white card
    cv2.rectangle(img, (40, 40), (140, 80), (0xE5, 0x46, 0x4F), -1)               # indigo button (BGR)
    path = tmp_path / "s.png"
    cv2.imwrite(str(path), img)
    return path


def test_palette_finds_solid_colors(tmp_path):
    pal = palette.extract(palette.load(str(synthetic(tmp_path))), 1, 12, 1.2)
    hexes = [c["hex"] for c in pal["colors"]]
    assert pal["background"] == "#F6F6F6"
    for h in ("#FFFFFF", "#4F46E5", "#E2E8F0"):
        assert h in hexes


def test_geometry_detects_card_border_and_button(tmp_path):
    img = palette.load(str(synthetic(tmp_path)))
    nodes = geometry.detect(img, 1)["nodes"]
    card = next(n for n in nodes if n["style"]["fill"]["hex"] == "#FFFFFF")
    assert card["bbox"] == [20, 20, 280, 160]
    assert card["style"]["border"]["width"] == 1
    button = next(n for n in nodes if n["style"]["fill"]["hex"] == "#4F46E5")
    assert button["bbox"] == [40, 40, 101, 41] and button["parent"] == card["id"]


def test_eval_case_surfaces_found():
    golden = json.loads((CASE / "golden-spec.json").read_text())
    img = palette.load(str(CASE / "input.png"))
    boxes = [n["bbox"] for n in geometry.detect(img, 1)["nodes"]]
    field = next(n for n in golden["nodes"] if n["id"] == "deviceNameField")["bbox"]
    assert any(max(abs(a - b) for a, b in zip(field, box, strict=True)) <= 1 for box in boxes)


def test_validate_catches_errors(tmp_path):
    spec = json.loads((CASE / "golden-spec.json").read_text())
    assert validate_spec.validate(spec)[0] == []
    spec["nodes"][1]["parent"] = "nope"
    spec["tokens"]["color"]["onAccent"] = {"hex": "#000000", "alpha": 1}
    errors, _, _ = validate_spec.validate(spec)
    assert any("parent 'nope'" in e for e in errors)
    assert any("onAccent" in e for e in errors)


def test_gen_theme_output_is_valid_qml(tmp_path):
    import gen_theme
    assert gen_theme.main([str(EVALS / "cases/01-hmi-dolum/golden-spec.json"), str(tmp_path)]) == 0
    theme = (tmp_path / "Theme.qml").read_text()
    assert 'readonly property color okSoft: "#2422C55E"' in theme
    assert 'readonly property string fontIcon: "Font Awesome 7 Free"' in theme
    assert '"\\uf275"' in (tmp_path / "Icons.qml").read_text()
    lint = shutil.which("pyside6-qmllint") or shutil.which("qmllint")
    if lint:
        import subprocess
        # as in a scaffolded project (qml/App/Style): qmllint 6.12 wants the singletons declared in a qmldir
        (tmp_path / "qmldir").write_text("module App.Style\nsingleton Theme 1.0 Theme.qml\nsingleton Icons 1.0 Icons.qml\n")
        res = subprocess.run([lint, "--max-warnings", "0", str(tmp_path / "Theme.qml"), str(tmp_path / "Icons.qml")],
                             capture_output=True, text=True)
        assert res.returncode == 0, res.stdout + res.stderr


def test_gen_theme_names_are_qml_safe():
    import gen_theme
    assert gen_theme.qml_name("on-accent") == "accentInk"
    assert gen_theme.qml_name("panel-2") == "panel2"
    assert gen_theme.qml_name("2xl", "radius") == "radius2xl"
    assert gen_theme.qml_name("text-muted") == "textMuted"


@pytest.mark.skipif(shutil.which("tesseract") is None, reason="tesseract not installed")
def test_ocr_reads_turkish(tmp_path):
    import text_ocr
    img = palette.load(str(EVALS / "cases/01-hmi-dolum/input.png"))[100:240, 1368:1888]
    runs = text_ocr.recognize(np.ascontiguousarray(img), 1)["runs"]
    joined = " ".join(r["string"] for r in runs)
    assert "Aktif Alarmlar" in joined
    assert "kritik eşiğe" in joined


def test_analyze_draft_is_schema_valid(tmp_path):
    import analyze
    out = tmp_path / "a"
    assert analyze.main([str(CASE / "input.png"), "--out-dir", str(out), "--no-ocr"]) == 0
    spec = json.loads((out / "design-spec.draft.json").read_text())
    errors, warnings, _ = validate_spec.validate(spec)
    assert errors == []
    assert any("draft" in w for w in warnings)
    assert (out / "overlay.png").exists()
