import json

import cv2
import numpy as np

import diff


def draw(path, dx=0, color=(0xCC, 0x66, 0x33)):
    img = np.full((120, 200, 3), (245, 245, 245), np.uint8)
    cv2.rectangle(img, (20 + dx, 20), (139 + dx, 99), color, -1)
    cv2.rectangle(img, (30 + dx, 30), (60 + dx, 60), (40, 40, 40), -1)   # structure for matching
    cv2.imwrite(str(path), img)


def run(tmp_path, spec, **kw):
    src, ren = tmp_path / "src.png", tmp_path / "ren.png"
    draw(src)
    draw(ren, **kw)
    (tmp_path / "spec.json").write_text(json.dumps(spec))
    rc = diff.main([str(src), str(ren), "--spec", str(tmp_path / "spec.json"), "--out", str(tmp_path / "r.json")])
    return rc, json.loads((tmp_path / "r.json").read_text())


def test_identical_images_pass(tmp_path, tiny_spec):
    rc, rep = run(tmp_path, tiny_spec)
    assert rc == 0 and rep["pass"]
    assert rep["metrics"]["globalSSIM"] > 0.999
    assert rep["metrics"]["colorDeltaEMax"] < 0.5


def test_shift_is_measured(tmp_path, tiny_spec):
    rc, rep = run(tmp_path, tiny_spec, dx=4)
    assert rc == 1
    g = rep["details"]["geometry"][0]
    assert abs(g["dx"] - 4) < 0.6 and abs(g["dy"]) < 0.6


def test_color_change_is_caught(tmp_path, tiny_spec):
    rc, rep = run(tmp_path, tiny_spec, color=(0xCC, 0x66, 0x66))
    assert rc == 1
    assert rep["metrics"]["colorDeltaEMax"] > 2.0


def test_text_matching(tiny_spec):
    tiny_spec["text"] = [{"string": "Hat 3", "bbox": [10, 10, 40, 20], "align": "start", "font": {"px": 16}}]
    scene = {"texts": [{"string": "Hat 3", "bbox": [0, 0, 100, 20], "textBox": [11, 10.5, 40, 20], "font": {"px": 16}}]}
    res = diff.text_checks(tiny_spec, scene)
    assert res["matchRate"] == 1.0 and res["maxOffset"] < 1.2
    res = diff.text_checks(tiny_spec, {"texts": []})
    assert res["matchRate"] == 0.0 and res["missing"] == ["Hat 3"]


def test_fill_color_ignores_undeclared_decorations(tmp_path, tiny_spec):
    """A status dot or ::before knob that is not a node must not move the fill color."""
    def card(path, deco_x, fill=(0xCC, 0x66, 0x33)):
        img = np.full((120, 200, 3), (245, 245, 245), np.uint8)
        cv2.rectangle(img, (20, 20), (139, 99), fill, -1)
        cv2.circle(img, (deco_x, 60), 26, (255, 255, 255), -1)          # a big knob, ~30 % of the card
        cv2.imwrite(str(path), img)
    src, ren = tmp_path / "s.png", tmp_path / "r.png"
    card(src, 60)
    card(ren, 64)                                                         # knob drawn 4 px to the side
    mask = np.zeros((120, 200), bool)
    s, r = cv2.imread(str(src))[..., ::-1], cv2.imread(str(ren))[..., ::-1]
    assert diff.color_checks(tiny_spec, s, r, mask, 1)[0]["deltaE"] < 0.5
    card(ren, 64, fill=(0xCC, 0x66, 0x66))                                # wrong fill is still caught
    r = cv2.imread(str(ren))[..., ::-1]
    assert diff.color_checks(tiny_spec, s, r, mask, 1)[0]["deltaE"] > 2.0


def scene_item(string, lines):
    return {"string": string, "bbox": [0, 0, 400, 60], "font": {"px": 16}, "lines": [
        {"string": s, "baseline": b, "origin": x, "box": [x, b - 13, 9 * len(s), 17], "adv": [9 * k for k in range(len(s) + 1)]}
        for s, x, b in lines]}


def test_run_that_wraps_matches_across_lines(tiny_spec):
    # "…, tek bir" ends line 1, "güvenli kasada." starts line 2: a tinted span in a headline
    tiny_spec["text"] = [{"string": "tek bir güvenli kasada.", "bbox": [20, 17, 225, 39], "baseline": 30, "lines": 2,
                          "align": "start", "font": {"px": 16}}]
    scene = {"texts": [scene_item("Tüm şifreleriniz, tek bir\ngüvenli kasada.",
                                  [("Tüm şifreleriniz, tek bir", 20, 30), ("güvenli kasada.", 20, 52)])]}
    res = diff.text_checks(tiny_spec, scene)
    assert res["matchRate"] == 1.0 and res["maxOffset"] < 0.5


def test_trimmed_separators_compare_the_uncut_edge(tiny_spec):
    # "•••• 4821": the bullets are dots drawn on their own, the digits a Text
    tiny_spec["text"] = [{"string": "•••• 4821", "bbox": [100, 17, 81, 17], "baseline": 30, "align": "start", "font": {"px": 16}}]
    scene = {"texts": [scene_item("4821", [("4821", 145, 30)])]}
    res = diff.text_checks(tiny_spec, scene)
    assert res["matchRate"] == 1.0 and res["maxOffset"] < 0.5        # right edges agree (181)


def test_vertical_text_compares_centers(tiny_spec):
    tiny_spec["text"] = [{"string": "HAFTALIK", "bbox": [10, 20, 16, 100], "baseline": 33, "lines": 1, "align": "start",
                          "font": {"px": 12}}]
    item = scene_item("HAFTALIK", [("HAFTALIK", -24, 76)])            # rotated item: line math does not apply
    item["bbox"] = [10.5, 20, 16, 100]
    res = diff.text_checks(tiny_spec, {"texts": [item]})
    assert res["matchRate"] == 1.0 and res["maxOffset"] < 1.0
