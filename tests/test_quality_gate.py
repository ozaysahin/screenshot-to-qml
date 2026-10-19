import json
import shutil

import cv2

import quality_gate
from conftest import EXAMPLE


def copy_example(tmp_path):
    dst = tmp_path / "project"
    shutil.copytree(EXAMPLE / "project", dst)
    return dst


def test_example_passes_static_gates(tmp_path):
    project = copy_example(tmp_path)
    rc = quality_gate.main([str(project), "--scene", str(EXAMPLE / "check" / "scene.json"),
                            "--source", str(EXAMPLE / "input.png"), "--out", str(tmp_path / "g.json")])
    report = json.loads((tmp_path / "g.json").read_text())
    assert rc == 0, report
    assert report["gates"]["hardcode"]["warnings"] == []


def test_color_literal_is_rejected(tmp_path):
    project = copy_example(tmp_path)
    f = project / "qml" / "App" / "StatusBar.qml"
    f.write_text(f.read_text().replace("color: Theme.panel", 'color: "#121821"', 1))
    errors, _ = quality_gate.gate_hardcode(project, sorted((project / "qml").rglob("*.qml")), "production")
    assert any("color literal" in e for e in errors)


def test_embedded_screenshot_is_rejected(tmp_path):
    project = copy_example(tmp_path)
    img = cv2.imread(str(EXAMPLE / "input.png"))
    cv2.imwrite(str(project / "assets" / "bg.jpg"), cv2.resize(img, (960, 540)))
    (project / "qml" / "App" / "Bg.qml").write_text('import QtQuick\nImage { source: "../../assets/bg.jpg" }\n')
    errors, _ = quality_gate.gate_embed(project, None, EXAMPLE / "input.png")
    assert errors and "looks like the source" in errors[0]


def test_unused_preview_render_is_only_a_warning(tmp_path):
    project = copy_example(tmp_path)
    img = cv2.imread(str(EXAMPLE / "input.png"))
    cv2.imwrite(str(project / "preview.png"), img)          # an agent's own screenshot of its build
    errors, warnings = quality_gate.gate_embed(project, None, EXAMPLE / "input.png")
    assert errors == [] and any("not used" in w for w in warnings)


def test_large_raster_in_scene_is_rejected(tmp_path):
    scene = {"render": {"logicalSize": [100, 100]}, "images": [{"source": "file:bg.png", "bbox": [0, 0, 80, 80]}]}
    errors, _ = quality_gate.gate_embed(tmp_path, scene, None)
    assert errors


def test_webengine_is_rejected(tmp_path):
    (tmp_path / "Main.qml").write_text("import QtWebEngine\nWebEngineView {}\n")
    errors, _ = quality_gate.gate_webengine(tmp_path)
    assert errors

