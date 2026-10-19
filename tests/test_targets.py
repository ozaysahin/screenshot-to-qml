"""v0.7: the C++ host, embedded-profile gates, deployment files.

C++ builds need Qt 6.8+ with its CMake package; they are skipped without one (CI installs Qt).
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

import build_cpp
import deploy
import quality_gate
import scaffold
from conftest import SCRIPTS, SKILL, can_render

GALLERY = SKILL / "examples" / "controls-gallery"


def qt6_cmake() -> bool:
    """A Qt 6.8+ CMake package cmake can find ($QT_DIR, $Qt6_DIR, CMAKE_PREFIX_PATH or /usr)."""
    if not shutil.which("cmake"):
        return False
    roots = [os.environ.get(k) for k in ("QT_DIR", "Qt6_DIR", "QT_ROOT_DIR")] + os.environ.get("CMAKE_PREFIX_PATH", "").split(os.pathsep)
    roots += ["/usr/lib/x86_64-linux-gnu/cmake", "/usr/lib/aarch64-linux-gnu/cmake", "/usr/lib/cmake"]
    for r in filter(None, roots):
        for cfg in Path(r).glob("**/Qt6Config.cmake"):
            ver = cfg.with_name("Qt6ConfigVersionImpl.cmake")
            text = ver.read_text() if ver.exists() else ""
            if 'PACKAGE_VERSION "6.' in text and int(text.split('PACKAGE_VERSION "6.')[1].split(".")[0]) >= 8:
                return True
    return False


requires_qt_sdk = pytest.mark.skipif(not (qt6_cmake() and can_render()), reason="needs Qt 6.8+ (CMake package) and a display/Xvfb")


def qt_prefix() -> list[str]:
    root = os.environ.get("QT_ROOT_DIR") or os.environ.get("QT_DIR")
    return ["--qt", root] if root else []


# ------------------------------------------------------------------ scaffold

def test_scaffold_both_hosts_share_one_qml_tree(tmp_path):
    out = tmp_path / "app"
    assert scaffold.main([str(out), "--name", "Demo Panel", "--target", "both", "--profile", "embedded-sw",
                          "--layout", "canvas", "--controls", "Button"]) == 0
    for rel in ("main.py", "CMakeLists.txt", "src/main.cpp", "cmake/S2qQml.cmake", "qml/App/qmldir", "README.md"):
        assert (out / rel).exists(), rel
    cm = (out / "CMakeLists.txt").read_text()
    assert 'OUTPUT_NAME "demo-panel"' in cm and 'S2Q_PROFILE "embedded-sw"' in cm and "{{" not in cm
    assert 'APP_PROFILE = "embedded-sw"' in (out / "main.py").read_text()
    readme = (out / "README.md").read_text()
    assert "cmake --build" in readme and "python main.py" in readme


def test_scaffold_cpp_only_and_add_host(tmp_path):
    out = tmp_path / "c"
    assert scaffold.main([str(out), "--name", "Only Cpp", "--target", "cpp"]) == 0
    assert (out / "CMakeLists.txt").exists() and not (out / "main.py").exists()
    assert scaffold.main([str(out), "--add-host", "pyside6", "--name", "Only Cpp"]) == 0
    assert (out / "main.py").exists()
    assert scaffold.main([str(out), "--add-host", "pyside6", "--name", "Only Cpp"]) == 2      # exists, no --force
    assert scaffold.main([str(tmp_path / "nothing"), "--add-host", "cpp", "--name", "X"]) == 2


def test_examples_carry_both_hosts():
    for ex in ("hmi-dolum", "controls-gallery"):
        proj = SKILL / "examples" / ex / "project"
        assert (proj / "main.py").exists() and (proj / "CMakeLists.txt").exists(), ex
        assert (proj / "cmake" / "S2qQml.cmake").read_text() == (SKILL / "assets/templates/cpp/cmake/S2qQml.cmake").read_text()


# ------------------------------------------------------------------ gates

def test_effects_gate_by_profile(tmp_path):
    q = tmp_path / "qml" / "App"
    q.mkdir(parents=True)
    f = q / "Card.qml"
    f.write_text("import QtQuick\nimport QtQuick.Effects\nItem {\n    RectangularShadow { }\n"
                 "    MultiEffect { blurEnabled: true; blurMax: 32 }\n    Rectangle { layer.enabled: true }\n}\n")
    err, warn = quality_gate.gate_effects(tmp_path, [f], "embedded-sw")
    assert len(err) == 2 and all("software scene graph" in e for e in err)
    err, warn = quality_gate.gate_effects(tmp_path, [f], "embedded-gpu")
    assert not err and any("blur" in w for w in warn)
    assert quality_gate.gate_effects(tmp_path, [f], "desktop") == ([], [])


def test_types_newer_than_min_qt(tmp_path):
    q = tmp_path / "qml" / "App"
    q.mkdir(parents=True)
    f = q / "Card.qml"
    f.write_text("import QtQuick\nimport QtQuick.Effects\nItem {\n    RectangularShadow {\n    }\n}\n")
    assert len(quality_gate.newer_than(tmp_path, [f], "6.8")) == 1
    assert quality_gate.newer_than(tmp_path, [f], "6.9") == []


def test_perf_gate():
    scene = {"perf": {"items": 120, "layers": [], "effects": [], "firstFrameMs": 300,
                      "oversizedImages": [{"source": "big.png", "decoded": [4000, 3000], "drawn": [400, 300], "ratio": 100.0}],
                      "animations": [{"class": "QQuickNumberAnimation", "owner": "Spinner"}], "timers": []}}
    err, warn = quality_gate.gate_perf(scene, "embedded-gpu")
    assert len(err) == 1 and "sourceSize" in err[0] and any("infinite" in w for w in warn)
    err, warn = quality_gate.gate_perf(scene, "desktop")
    assert not err and len(warn) == 1
    assert quality_gate.gate_perf({}, "desktop") is None


def test_cpp_gate():
    assert quality_gate.gate_cpp(None) is None
    ok = {"built": True, "grab": {"ok": True, "qmlWarnings": []}, "parity": {"ssim": 0.9999}, "warnings": {"build": 0}}
    assert quality_gate.gate_cpp(ok) == ([], [])
    bad = dict(ok, parity={"ssim": 0.93}, grab={"ok": True, "qmlWarnings": ["Main.qml:3: ReferenceError: x"]})
    err, _ = quality_gate.gate_cpp(bad)
    assert len(err) == 2
    no_qt = {"built": False, "error": "Qt 6 CMake package not found (pass --qt or set QT_DIR)"}
    assert quality_gate.gate_cpp(no_qt)[0] == []


# ------------------------------------------------------------------ deploy

def test_device_files(tmp_path):
    proj = tmp_path / "p"
    scaffold.main([str(proj), "--name", "Line Panel", "--target", "both", "--profile", "embedded-sw"])
    assert deploy.main([str(proj), "--target", "cpp", "--platform", "device", "--name", "Line Panel"]) == 0
    d = proj / "deploy" / "device"
    env = (d / "app.env").read_text()
    assert "QT_QPA_PLATFORM=linuxfb" in env and "QT_QUICK_BACKEND=software" in env
    assert all(" #" not in ln for ln in env.splitlines() if not ln.startswith("#"))   # systemd: no inline comments
    unit = (d / "line-panel.service").read_text()
    assert "ExecStart=/opt/line-panel/bin/line-panel" in unit and "Restart=always" in unit
    assert "-DS2Q_DEPLOY_QT=OFF" in (d / "install.sh").read_text()
    assert deploy.main([str(proj), "--target", "pyside6", "--platform", "device", "--name", "Line Panel",
                        "--profile", "embedded-gpu", "--gpu", "jetson"]) == 0
    env = (d / "app.env").read_text()
    assert "QT_QPA_EGLFS_INTEGRATION=eglfs_kms_egldevice" in env and (d / "kms.json").exists()
    assert ".venv/bin/python /opt/line-panel/main.py" in (d / "line-panel.service").read_text()


@pytest.mark.skipif(not shutil.which("pyside6-deploy"), reason="pyside6-deploy not installed")
def test_pyside6_spec(tmp_path):
    proj = tmp_path / "p"
    scaffold.main([str(proj), "--name", "Spec App"])
    assert deploy.main([str(proj), "--target", "pyside6", "--platform", "desktop", "--name", "Spec App"]) == 0
    spec = (proj / "pysidedeploy.spec").read_text()
    assert "title = Spec App" in spec and "--include-data-dir=assets=assets" in spec
    assert "excluded_qml_plugins = " in spec and "Qt3D" in spec


# ------------------------------------------------------------------ C++ build (Qt SDK only)

@requires_qt_sdk
def test_cpp_host_matches_pyside6(tmp_path):
    render = tmp_path / "py.png"
    subprocess.run([sys.executable, str(SCRIPTS / "render.py"), str(GALLERY / "project"), "--size", "1200", "760",
                    "--out", str(render), "--scene", str(tmp_path / "scene.json")], check=True, capture_output=True)
    rc = build_cpp.main([str(GALLERY / "project"), "--build-dir", str(tmp_path / "build"), "--grab", str(tmp_path / "cpp.png"),
                         "--size", "1200", "760", "--compare", str(render), "--json", str(tmp_path / "cpp.json"), *qt_prefix()])
    rep = json.loads((tmp_path / "cpp.json").read_text())
    assert rc == 0, rep
    assert rep["grab"]["qmlWarnings"] == [] and rep["parity"]["ssim"] >= 0.99
