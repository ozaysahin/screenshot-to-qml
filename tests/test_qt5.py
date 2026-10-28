"""v1.1: the Qt 5.15 target — dialect port and check, scaffold, gates, render shim, C++ host.

The C++ build needs a Qt 5.15 CMake package (Qt5Config.cmake: a distro's qtdeclarative5-dev,
or $QT5_DIR); it is skipped without one. CI installs Qt 5.15 from Ubuntu's archive.
"""
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

import build_cpp
import deploy
import gen_theme
import qt5
import quality_gate
import scaffold
from conftest import ROOT, SCRIPTS, SKILL, can_render, requires_render

CLUSTER = SKILL / "examples" / "auto-cluster"

QT6_SNIPPET = """pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Shapes
import QtQuick.Templates as T
import Qt5Compat.GraphicalEffects
import App.Style
import Some.Vendor.Module

Window {
    Shape {
        preferredRendererType: Shape.CurveRenderer
        renderTypeQuality: 100
    }
    Text { text: "http://example.com" }   // a comment with topLeftRadius: 3
}
"""


def qt5_cmake() -> str | None:
    """A Qt 5.15 CMake package dir ($QT5_DIR, or a distro's), else None."""
    if not shutil.which("cmake"):
        return None
    roots = [os.environ.get("QT5_DIR"), "/usr/lib/x86_64-linux-gnu/cmake", "/usr/lib/aarch64-linux-gnu/cmake", "/usr/lib/cmake"]
    for r in filter(None, roots):
        for cfg in Path(r).glob("**/Qt5ConfigVersion.cmake"):
            if re.search(r'PACKAGE_VERSION "?5\.15', cfg.read_text()):
                return str(cfg.parent)
    return None


requires_qt5 = pytest.mark.skipif(not (qt5_cmake() and can_render()), reason="needs Qt 5.15 (CMake package) and a display/Xvfb")


# ------------------------------------------------------------------ dialect

def test_port_text_writes_the_515_dialect():
    out, notes = qt5.port_text(QT6_SNIPPET, {"App.Style"})
    lines = out.splitlines()
    assert "pragma ComponentBehavior: Bound" not in out
    assert lines[:8] == ["import QtQuick 2.15", "import QtQuick.Window 2.15", "import QtQuick.Shapes 1.15",
                         "import QtQuick.Templates 2.15 as T", "import QtGraphicalEffects 1.15", "import App.Style 1.0",
                         "import Some.Vendor.Module", ""]
    assert "layer.enabled: true" in out and "layer.samples: 4" in out and "preferredRendererType" not in out
    assert "renderTypeQuality" not in out
    assert notes == ["import Some.Vendor.Module has no version: add the one your Qt 5.15 ships"]
    # idempotent
    assert qt5.port_text(out, {"App.Style"})[0] == out


def test_check_text_lists_what_515_cannot_load():
    code = """import QtQuick 2.15
import QtQuick.Effects
Item {
    property list<string> names
    Rectangle { topLeftRadius: 8 }
    MultiEffect { shadowEnabled: true }
    VectorImage { source: "a.svg" }
    Item { Layout.horizontalStretchFactor: 2 }
    ShaderEffect { }
    Component.onCompleted: { let a; a ??= 3 }
    Text { text: "// topLeftRadius: 1 is only text" }
    // RectangularShadow { }
}
"""
    items = qt5.check_text(code)
    whats = " | ".join(w for _, w, _ in items)
    for needle in ("QtQuick.Effects", "lists of value types", "per-corner radius", "MultiEffect", "VectorImage",
                   "stretch factors", "ShaderEffect", "logical assignment"):
        assert needle in whats, needle
    assert "RectangularShadow" not in whats            # commented out
    assert [ln for ln, w, _ in items if "per-corner" in w] == [5]    # not the string on line 11
    assert qt5.check_text(qt5.port_text(QT6_SNIPPET, {"App.Style"})[0]) == [
        (7, "import Some.Vendor.Module has no version (Qt 5.15 needs one)", "qt5.py port adds it")]


def test_port_qmldir_versions_every_type():
    out = qt5.port_qmldir("module App\nsingleton Theme Theme.qml\nMain Main.qml\nCard 1.0 Card.qml\nprefer :/qt/qml/App/\n")
    assert out == "module App\nsingleton Theme 1.0 Theme.qml\nMain 1.0 Main.qml\nCard 1.0 Card.qml\n"
    assert qt5.check_qmldir("Main Main.qml\n")


# ------------------------------------------------------------------ scaffold, theme, deploy

def test_scaffold_qt5_project(tmp_path):
    out = tmp_path / "app"
    assert scaffold.main([str(out), "--name", "Demo Cluster", "--min-qt", "5.15", "--layout", "canvas",
                          "--profile", "embedded-gpu", "--controls", "Button,ComboBox"]) == 0
    cm = (out / "CMakeLists.txt").read_text()
    assert "find_package(Qt5 5.15" in cm and 'OUTPUT_NAME "demo-cluster"' in cm and "{{" not in cm
    assert (out / "cmake" / "S2qQml5.cmake").exists() and not (out / "main.py").exists()
    assert "qrc:/qml/App/Main.qml" in (out / "src" / "main.cpp").read_text()
    assert "SvgIcon 1.0 SvgIcon.qml" in (out / "qml" / "App" / "Controls" / "qmldir").read_text()
    assert qt5.is_qt5_project(out)
    assert qt5.check_project(out) == []
    assert "Qt 5.15" in (out / "README.md").read_text()
    # adding a host keeps the dialect: cpp → the Qt 5 host; pyside6 is refused
    (out / "CMakeLists.txt").unlink()
    assert scaffold.main([str(out), "--add-host", "cpp", "--name", "Demo Cluster", "--force"]) == 0
    assert "find_package(Qt5" in (out / "CMakeLists.txt").read_text()
    assert scaffold.main([str(out), "--add-host", "pyside6", "--name", "Demo Cluster"]) == 2


def test_scaffold_qt5_refuses_a_python_host(tmp_path):
    assert scaffold.main([str(tmp_path / "a"), "--name", "X", "--min-qt", "5.15", "--target", "pyside6"]) == 2
    assert scaffold.main([str(tmp_path / "b"), "--name", "X", "--min-qt", "5.15", "--target", "both"]) == 2


def test_gen_theme_writes_515_imports(tmp_path, tiny_spec):
    tiny_spec["meta"]["minQt"] = "5.15"
    spec = tmp_path / "spec.json"
    spec.write_text(json.dumps(tiny_spec))
    assert gen_theme.main([str(spec), str(tmp_path / "Style"), "--no-format"]) == 0
    for name in ("Theme.qml", "Icons.qml"):
        text = (tmp_path / "Style" / name).read_text()
        assert "import QtQuick 2.15" in text and qt5.check_text(text) == []


def test_device_installer_builds_with_the_boards_qt5(tmp_path):
    out = tmp_path / "app"
    scaffold.main([str(out), "--name", "Panel", "--min-qt", "5.15", "--controls", "none"])
    assert deploy.main([str(out), "--target", "cpp", "--platform", "device"]) == 0
    sh = (out / "deploy" / "device" / "install.sh").read_text()
    assert "Qt 5.15" in sh and "S2Q_DEPLOY_QT" not in sh


def test_prepare_run_prompt_asks_for_qt5():
    sys.path.insert(0, str(ROOT / "evals"))
    import prepare_run
    meta = json.loads((ROOT / "evals" / "cases" / "21-auto-cluster" / "golden-spec.json").read_text())["meta"]
    assert meta["minQt"] == "5.15" and meta["target"] == "cpp"
    text = prepare_run.prompt(meta, None)
    assert "Qt 5.15" in text and "C++ (CMake)" in text


# ------------------------------------------------------------------ gates

def test_lint_gate_applies_the_515_rules(tmp_path):
    out = tmp_path / "app"
    scaffold.main([str(out), "--name", "X", "--min-qt", "5.15", "--controls", "none"])
    (out / "qml" / "App" / "Bad.qml").write_text("import QtQuick 2.15\nRectangle { topLeftRadius: 4 }\n")
    errors, _ = quality_gate.gate_lint(out, sorted((out / "qml").rglob("*.qml")), "5.15")
    assert any("Bad.qml:2" in e and "per-corner radius" in e for e in errors)
    # the Qt 6 floor does not apply these rules
    errors6, _ = quality_gate.gate_lint(out, sorted((out / "qml").rglob("*.qml")), "6.8")
    assert not any("per-corner" in e for e in errors6)


@pytest.mark.skipif(not quality_gate.tool("pyside6-qmllint", "qmllint"), reason="needs qmllint")
def test_lint_gate_accepts_outer_ids_in_515_delegates(tmp_path):
    """Qt 5.15 has no ComponentBehavior pragma; Qt 6's qmllint must not fail outer ids in delegates."""
    out = tmp_path / "app"
    scaffold.main([str(out), "--name", "X", "--min-qt", "5.15", "--controls", "none"])
    (out / "qml" / "App" / "List.qml").write_text("""import QtQuick 2.15

Column {
    id: root

    property int base: 2

    Repeater {
        model: 3

        Text {
            required property int index

            text: index * root.base
        }
    }
}
""")
    (out / "qml" / "App" / "qmldir").write_text((out / "qml" / "App" / "qmldir").read_text() + "List 1.0 List.qml\n")
    errors, _ = quality_gate.gate_lint(out, sorted((out / "qml").rglob("*.qml")), "5.15")
    assert errors == []


def test_cpp_gate_reads_qt5_tile_parity():
    ok = {"built": True, "grab": {"ok": True, "qmlWarnings": []},
          "parity": {"ssim": 0.95, "qt": 5, "maxTileDiff": 14.7, "limit": 24}}
    assert quality_gate.gate_cpp(ok)[0] == []
    bad = dict(ok, parity={"ssim": 0.99, "qt": 5, "maxTileDiff": 31.0, "limit": 24})
    assert "Qt 5.15 frame differs" in quality_gate.gate_cpp(bad)[0][0]


def test_tile_diff_separates_drift_from_missing_items(tmp_path):
    import numpy as np
    from PIL import Image
    a = np.full((128, 256, 3), 20, np.uint8)
    a[40:80, 30:220] = 200
    b = a.copy()
    b[40:80, 31:221] = 200                          # 1 px drift
    c = a.copy()
    c[40:72, 96:128] = 20                           # a 32 px item missing
    for name, arr in (("a", a), ("b", b), ("c", c)):
        Image.fromarray(arr).save(tmp_path / f"{name}.png")
    assert build_cpp.tile_diff(tmp_path / "a.png", tmp_path / "a.png") == 0
    assert build_cpp.tile_diff(tmp_path / "a.png", tmp_path / "b.png") < 24
    assert build_cpp.tile_diff(tmp_path / "a.png", tmp_path / "c.png") > 24


# ------------------------------------------------------------------ the example, render, C++ host

def test_cluster_example_is_515_clean():
    assert qt5.is_qt5_project(CLUSTER / "project")
    assert qt5.check_project(CLUSTER / "project") == []
    spec = json.loads((CLUSTER / "design-spec.json").read_text())
    assert spec["meta"]["minQt"] == "5.15"
    summary = json.loads((CLUSTER / "check" / "summary.json").read_text())
    assert summary["pass"] and summary["metrics"]["textMatchRate"] == 1.0


@requires_render
def test_render_loads_qt5_effects_through_the_shim(tmp_path):
    out = tmp_path / "app"
    scaffold.main([str(out), "--name", "X", "--min-qt", "5.15", "--layout", "canvas", "--controls", "none"])
    main = out / "qml" / "App" / "Main.qml"
    text = main.read_text().replace("import App.Style 1.0", "import App.Style 1.0\nimport QtGraphicalEffects 1.15")
    text = text.replace("// screen content, laid out with Layouts inside the fixed canvas",
                        "Rectangle { id: card; Layout.preferredWidth: 200; Layout.preferredHeight: 100; color: Theme.surface }")
    main.write_text(text)
    res = subprocess.run([sys.executable, str(SCRIPTS / "render.py"), str(out), "--size", "400", "300",
                          "--out", str(tmp_path / "r.png"), "--strict"], capture_output=True, text=True, timeout=300)
    assert res.returncode == 0, res.stderr


@requires_qt5
def test_cluster_cpp_host_builds_and_runs_on_qt515(tmp_path):
    """The example's Qt 5 host: build, run headless, no QML warnings, same frame as the reference render."""
    project = tmp_path / "project"
    shutil.copytree(CLUSTER / "project", project)
    rc = build_cpp.main([str(project), "--build-dir", str(tmp_path / "build"), "--grab", str(tmp_path / "cpp.png"),
                         "--size", "1920", "720", "--compare", str(CLUSTER / "check" / "render.png"),
                         "--json", str(tmp_path / "cpp.json")])
    report = json.loads((tmp_path / "cpp.json").read_text())
    assert rc == 0, json.dumps(report, indent=1)[:3000]
    assert report["qtMajor"] == 5 and report["grab"]["qmlWarnings"] == []
    assert "Qt 5.15" in report["grab"]["stdout"]
    assert report["parity"]["maxTileDiff"] <= 24
