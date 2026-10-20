"""Token-saving tools: contact sheets, the compact spec view, batched probes."""
import json
import subprocess
import sys

from PIL import Image

from conftest import EVALS, SCRIPTS

CASE = EVALS / "cases" / "05-settings-form"


def run(*args):
    return subprocess.run([sys.executable, *map(str, args)], capture_output=True, text=True)


def test_spec_view_is_compact_and_filters(tmp_path):
    spec = CASE / "golden-spec.json"
    full = run(SCRIPTS / "spec_view.py", spec)
    assert full.returncode == 0 and "## nodes" in full.stdout and "## text" in full.stdout
    assert len(full.stdout) < spec.stat().st_size / 2          # much smaller than the JSON
    one = run(SCRIPTS / "spec_view.py", spec, "--nodes", "--ids", "saveButton")
    lines = [ln for ln in one.stdout.splitlines() if not ln.startswith("#")]
    assert len(lines) == 1 and lines[0].startswith("saveButton")


def test_ocr_sheet_and_compare_sheet(tmp_path):
    spec = json.loads((CASE / "golden-spec.json").read_text())
    sheet = run(SCRIPTS / "sheet.py", "ocr", CASE / "input.png", "--spec", CASE / "golden-spec.json",
                "--out", tmp_path / "ocr.png", "--max", "20")
    assert sheet.returncode == 0
    sheets = sorted(tmp_path.glob("ocr*.png"))
    assert len(sheets) == -(-len(spec["text"]) // 20)          # 20 runs per sheet
    assert max(Image.open(p).width for p in sheets) <= 1400

    # a fake report: one bad region, one offset node, one text run off target
    node = next(n for n in spec["nodes"] if n.get("bbox") and n["bbox"][2] > 40)
    text = spec["text"][0]
    report = {"thresholds": {"geometryPx": 2, "textPositionPx": 2},
              "details": {"regions": [{"id": node["id"], "bbox": node["bbox"], "ssim": 0.71, "limit": 0.9}],
                          "geometry": [{"id": node["id"], "dx": 4.0, "dy": 0.0, "offset": 4.0}],
                          "text": {"runs": [{"string": text["string"], "dx": 3.0, "dy": 0.0, "offset": 3.0}], "missing": []}}}
    (tmp_path / "report.json").write_text(json.dumps(report))
    res = run(SCRIPTS / "sheet.py", "compare", CASE / "input.png", CASE / "input.png", "--spec", CASE / "golden-spec.json",
              "--report", tmp_path / "report.json", "--out", tmp_path / "worst.png")
    assert res.returncode == 0 and "2 items" in res.stdout    # the node's region and offset share one crop
    assert Image.open(tmp_path / "worst.png").width <= 1400


def test_probe_takes_many_boxes_in_one_call():
    res = run(SCRIPTS / "probe.py", CASE / "input.png", "region", 304, 104, 458, 434, 782, 104, 458, 289)
    data = json.loads(res.stdout)
    assert isinstance(data, list) and len(data) == 2 and data[0]["median"] == "#FFFFFF"
    one = json.loads(run(SCRIPTS / "probe.py", CASE / "input.png", "edges", 325, 187, 416, 40).stdout)
    assert isinstance(one, dict) and one["horizontal"]
    assert run(SCRIPTS / "probe.py", CASE / "input.png", "region", 1, 2, 3).returncode != 0
