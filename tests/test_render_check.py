import json
import subprocess
import sys

import pytest

from conftest import EXAMPLE, SCRIPTS, requires_render


@requires_render
def test_example_check_passes(tmp_path):
    out = tmp_path / "check"
    res = subprocess.run([sys.executable, str(SCRIPTS / "check.py"), str(EXAMPLE / "project"),
                          "--source", str(EXAMPLE / "input.png"), "--spec", str(EXAMPLE / "design-spec.json"),
                          "--out-dir", str(out)], capture_output=True, text=True, timeout=180)
    assert res.returncode == 0, res.stdout + res.stderr
    summary = json.loads((out / "summary.json").read_text())
    assert summary["metrics"]["globalSSIM"] >= 0.99
    assert summary["metrics"]["textMatchRate"] == 1.0
    scene = json.loads((out / "scene.json").read_text())
    assert scene["warnings"] == []
    assert scene["render"]["size"] == [1920, 1080]


@requires_render
@pytest.mark.parametrize("dpr,expected", [(2, [800, 480]), (1.25, [500, 300])])
def test_render_respects_dpr(tmp_path, dpr, expected):
    subprocess.run([sys.executable, str(SCRIPTS / "scaffold.py"), str(tmp_path / "p"), "--name", "T"], check=True,
                   capture_output=True)
    res = subprocess.run([sys.executable, str(SCRIPTS / "render.py"), str(tmp_path / "p"), "--size", "400", "240",
                          "--dpr", str(dpr), "--out", str(tmp_path / "r.png")], capture_output=True, text=True, timeout=120)
    assert res.returncode == 0, res.stderr
    scene = json.loads((tmp_path / "scene.json").read_text())
    assert scene["render"]["size"] == expected


@requires_render
def test_scene_reads_text_areas(tmp_path):
    """TextArea/TextEdit content is in the scene dump, line by line (plain and rich text)."""
    app = tmp_path / "p" / "qml" / "App"
    app.mkdir(parents=True)
    (app / "qmldir").write_text("module App\nMain 1.0 Main.qml\n")
    (app / "Main.qml").write_text(
        "import QtQuick\nimport QtQuick.Controls.Basic\nWindow {\n    width: 300; height: 220; visible: true; color: 'white'\n"
        "    TextArea { x: 10; y: 10; width: 200; height: 90; padding: 8; wrapMode: TextEdit.Wrap; font.pixelSize: 15\n"
        "        background: null; text: 'Yükleme rampasının sol üst köşesine bakacak şekilde' }\n"
        "    TextArea { x: 10; y: 110; width: 260; height: 90; padding: 8; font.pixelSize: 15; background: null\n"
        "        textFormat: TextEdit.RichText; text: \"<p style='line-height:22px'>Birinci satır<br>İkinci satır</p>\" }\n}\n")
    scene = tmp_path / "scene.json"
    subprocess.run([sys.executable, str(SCRIPTS / "render.py"), str(tmp_path / "p"), "--size", "300", "220",
                    "--out", str(tmp_path / "r.png"), "--scene", str(scene)], check=True, capture_output=True)
    texts = [t for t in json.loads(scene.read_text())["texts"] if t.get("edit")]
    assert len(texts) == 2
    plain, rich = texts
    assert len(plain["lines"]) >= 2 and " ".join(ln["string"] for ln in plain["lines"]).startswith("Yükleme rampasının")
    assert [ln["string"] for ln in rich["lines"]] == ["Birinci satır", "İkinci satır"]
    assert abs((rich["lines"][1]["baseline"] - rich["lines"][0]["baseline"]) - 22) < 0.6


@requires_render
def test_probe_survives_controls_that_quit_or_close(tmp_path):
    """A button that quits the app or closes the window when pressed must not end the probe."""
    app = tmp_path / "p" / "qml" / "App"
    app.mkdir(parents=True)
    (app / "qmldir").write_text("module App\nMain 1.0 Main.qml\n")
    (app / "Main.qml").write_text(
        "import QtQuick\nimport QtQuick.Controls.Basic\nWindow {\n    id: win; width: 300; height: 200; visible: true\n"
        "    Column {\n        Button { text: 'Quit'; onPressed: Qt.quit() }\n"
        "        Button { text: 'Close'; onPressed: win.close() }\n        Button { text: 'After' }\n    }\n}\n")
    inter = tmp_path / "i.json"
    subprocess.run([sys.executable, str(SCRIPTS / "render.py"), str(tmp_path / "p"), "--size", "300", "200",
                    "--out", str(tmp_path / "r.png"), "--interact", "--interaction", str(inter)], check=True, capture_output=True)
    data = json.loads(inter.read_text())
    assert [c["name"] for c in data["controls"]] == ["Quit", "Close", "After"]
    assert data["quitCalls"] == ["Qt.quit()"] and data["controls"][1].get("closesWindow")
    assert all(c["tabReached"] for c in data["controls"])


@requires_render
def test_idle_scan_finds_animations_and_can_be_skipped(tmp_path):
    """Infinite animations (also `on` value sources) and fast timers are found; --no-idle-scan skips the
    scan (check.py's fallback when it crashes PySide) and the perf gate says so."""
    sys.path.insert(0, str(SCRIPTS))
    import quality_gate
    app = tmp_path / "p" / "qml" / "App"
    app.mkdir(parents=True)
    (app / "qmldir").write_text("module App\nMain 1.0 Main.qml\n")
    (app / "Main.qml").write_text(
        "import QtQuick\nWindow {\n    width: 200; height: 100; visible: true; color: 'white'\n"
        "    Rectangle { width: 20; height: 20; color: 'red'; border.width: 1\n"
        "        RotationAnimation on rotation { from: 0; to: 360; duration: 1000; loops: Animation.Infinite } }\n"
        "    Item { Timer { interval: 16; repeat: true; running: true } }\n}\n")
    for flag, idle in (([], True), (["--no-idle-scan"], False)):
        scene = tmp_path / f"scene{idle}.json"
        subprocess.run([sys.executable, str(SCRIPTS / "render.py"), str(tmp_path / "p"), "--size", "200", "100",
                        "--out", str(tmp_path / "r.png"), "--scene", str(scene), *flag], check=True, capture_output=True)
        perf = json.loads(scene.read_text())["perf"]
        assert perf["idleScan"] is idle
        assert (len(perf["animations"]), len(perf["timers"])) == ((1, 1) if idle else (0, 0))
        _, warns = quality_gate.gate_perf({"perf": perf}, "desktop")
        assert any("not checked" in w for w in warns) is (not idle)
