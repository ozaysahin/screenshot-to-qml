import json

import cv2
import numpy as np

import probe


def make_image(tmp_path, dpr=1):
    img = np.full((int(100 * dpr), int(200 * dpr), 3), (240, 240, 240), np.uint8)
    cv2.rectangle(img, (int(40 * dpr), int(20 * dpr)), (int(140 * dpr) - 1, int(80 * dpr) - 1), (0xCC, 0x66, 0x33), -1)  # BGR
    path = tmp_path / "img.png"
    cv2.imwrite(str(path), img)
    return path


def test_color_reads_design_coordinates(tmp_path, capsys):
    path = make_image(tmp_path, dpr=2)
    probe.main([str(path), "--dpr", "2", "color", "50", "30", "10", "10"])
    out = json.loads(capsys.readouterr().out)
    assert out[0]["hex"] == "#3366CC"
    assert out[1]["hex"] == "#F0F0F0"


def test_edges_find_box(tmp_path, capsys):
    path = make_image(tmp_path)
    probe.main([str(path), "edges", "0", "0", "200", "100"])
    out = json.loads(capsys.readouterr().out)
    runs = [(r["from"], r["len"], r["hex"]) for r in out["horizontal"]]
    assert (40.0, 100.0, "#3366CC") in runs


def test_region_dominant_color(tmp_path, capsys):
    path = make_image(tmp_path)
    probe.main([str(path), "region", "30", "10", "120", "80", "--k", "2"])
    out = json.loads(capsys.readouterr().out)
    assert out["clusters"][0]["hex"] == "#3366CC"
