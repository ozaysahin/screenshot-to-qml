"""Scorer behaviour found while running the baseline: what the scene dump sees and how text
runs are matched. Each test is a case where an earlier version scored a correct build as wrong."""
import json
import subprocess
import sys

import numpy as np
import pytest

import diff
from conftest import SCRIPTS, requires_render

MAIN_QML = """
import QtQuick
import QtQuick.Controls.Basic

Window {
    width: 400; height: 240; visible: true; color: "#FFFFFF"
    // a component wrapping Text (class name AppText_QMLTYPE_n, not QQuickText)
    component AppText: Text { font.pixelSize: 16; color: "#111111" }
    AppText { id: padded; x: 10; y: 10; leftPadding: 28; text: "Hata bildirimleri" }
    AppText { x: 10; y: 50; text: "Bugün ne\\niçmek istersin?"; lineHeight: 1.0 }
    TextField { x: 10; y: 120; width: 200; height: 40; leftPadding: 12; text: "Lobi-Kiosk-02"
                verticalAlignment: TextInput.AlignVCenter; font.pixelSize: 14 }
    Label { x: 10; y: 180; text: "aktif"; font.capitalization: Font.AllUppercase; font.pixelSize: 14 }
}
"""


@pytest.fixture(scope="module")
def scene(tmp_path_factory):
    p = tmp_path_factory.mktemp("scene") / "p"
    (p / "qml" / "App").mkdir(parents=True)
    (p / "qml" / "App" / "qmldir").write_text("module App\nMain 1.0 Main.qml\n")
    (p / "qml" / "App" / "Main.qml").write_text(MAIN_QML)
    res = subprocess.run([sys.executable, str(SCRIPTS / "render.py"), str(p), "--size", "400", "240",
                          "--out", str(p / "r.png")], capture_output=True, text=True, timeout=120)
    assert res.returncode == 0, res.stderr
    return json.loads((p / "scene.json").read_text())


@requires_render
def test_scene_sees_wrapped_text_inputs_and_labels(scene):
    strings = [t["string"] for t in scene["texts"]]
    assert "Hata bildirimleri" in strings            # custom component around Text
    assert "Lobi-Kiosk-02" in strings                # TextField value
    assert "AKTIF" in strings                        # capitalization applied (Qt: i -> I)


@requires_render
def test_scene_boxes_include_padding_and_valign(scene):
    by = {t["string"]: t for t in scene["texts"]}
    assert by["Hata bildirimleri"]["textBox"][0] == pytest.approx(10 + 28, abs=0.5)
    field = by["Lobi-Kiosk-02"]["lines"][0]
    assert field["box"][0] == pytest.approx(10 + 12, abs=0.5)
    # vertically centred in the 40 px field: baseline well below the top padding
    assert 120 + 20 < field["baseline"] < 120 + 32


@requires_render
def test_scene_splits_lines(scene):
    multi = next(t for t in scene["texts"] if t["string"].startswith("Bugün"))
    assert [ln["string"] for ln in multi["lines"]] == ["Bugün ne", "içmek istersin?"]
    assert multi["lines"][1]["baseline"] > multi["lines"][0]["baseline"] + 10


def _scene_line(s, x, base, adv_px=8.0):
    adv = [round(i * adv_px, 2) for i in range(len(s) + 1)]
    box = [x, base - 12, adv[-1], 16]
    return {"string": s, "textBox": box, "bbox": box, "font": {"px": 14},
            "lines": [{"string": s, "baseline": base, "origin": x, "adv": adv, "box": box}]}


def test_text_runs_may_be_merged_split_or_repeated():
    scene = {"texts": [_scene_line("1–10 arası · 248 kayıttan", 200, 825),     # footer: one merged Text
                       _scene_line("1", 1192, 825), _scene_line("2", 1227, 825)]}
    spec = {"text": [
        {"string": "1", "bbox": [200, 813, 8, 16], "baseline": 825, "font": {"px": 14}},     # footer's own "1"
        {"string": "248", "bbox": [200 + 13 * 8, 813, 24, 16], "baseline": 825, "font": {"px": 14}},
        {"string": "1", "bbox": [1192, 813, 8, 16], "baseline": 825, "font": {"px": 14}},    # pager "1"
        {"string": "2", "bbox": [1227, 813, 8, 16], "baseline": 825, "font": {"px": 14}},
    ]}
    res = diff.text_checks(spec, scene)
    assert res["missing"] == []
    assert res["maxOffset"] <= 0.01
    assert {r["matchedAs"] for r in res["runs"]} == {"substring", "item"}


def test_text_separators_and_ellipsis_are_tolerated():
    scene = {"texts": [_scene_line("Hedef 1.200", 601, 237), _scene_line("Ara...", 10, 20)]}
    spec = {"text": [{"string": "Hedef 1.200 ·", "bbox": [601, 225, 80, 17], "baseline": 237},
                     {"string": "Ara…", "bbox": [10, 8, 40, 16], "baseline": 20}]}
    res = diff.text_checks(spec, scene)
    assert res["missing"] == [] and res["onTargetRate"] == 1.0


def test_region_ssim_forgives_one_pixel_shift():
    rng = np.random.default_rng(0)
    src = np.full((80, 120, 3), 240, np.uint8)
    src[20:60, 30:90] = 60
    src[30:50, 40:80] = rng.integers(0, 255, (20, 40, 1))
    ren = np.roll(src, 1, axis=1)
    spec = {"nodes": [{"id": "button", "bbox": [30, 20, 60, 40]}]}
    mask = np.zeros(src.shape[:2], bool)
    smap = diff.ssim_map(src, ren)
    plain = diff.region_ssim(spec, smap, mask, 1)[0]["ssim"]
    aligned = diff.region_ssim(spec, smap, mask, 1, src, ren)[0]
    assert plain < 0.9 and aligned["ssim"] > 0.99 and aligned["alignShift"] == [1.0, 0.0]
