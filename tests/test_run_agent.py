"""evals/run_agent.py: skips finished cases, stops on a failed attempt, continues it next time."""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUN_AGENT = ROOT / "evals" / "run_agent.py"

# Fake agent: fails once per case (as a usage limit would), then builds `project/`.
FAKE = """
import pathlib, sys
p = pathlib.Path(".")
prompts = sorted((p / ".agent").glob("prompt-*.md"))
print('{"type": "turn.completed", "usage": {"input_tokens": 10, "output_tokens": 2}}')
if len(prompts) > 1 and "cut off" in prompts[-1].read_text():
    (p / "project").mkdir()
    sys.exit(0)
sys.exit(3)
"""


def run(runs: Path, *extra):
    fake = runs.parent / "fake_agent.py"
    fake.write_text(FAKE)
    cmd = f"{sys.executable} {fake} {{prompt_file}}"
    return subprocess.run([sys.executable, str(RUN_AGENT), str(runs), "--cmd", cmd, *extra],
                          capture_output=True, text=True)


def test_stop_continue_skip(tmp_path):
    tmp_path = tmp_path / "runs"
    for name in ("05-a", "09-b"):
        (tmp_path / name).mkdir(parents=True)
        (tmp_path / name / "PROMPT.md").write_text("Rebuild this screen.\n")

    first = run(tmp_path)
    assert first.returncode == 1 and "stopped (exit 3)" in first.stdout
    assert not (tmp_path / "09-b" / ".agent").exists()          # the loop stopped at the first failure

    second = run(tmp_path, "--keep-going")
    st = json.loads((tmp_path / "05-a" / ".agent" / "status.json").read_text())
    assert st["done"] and [a["continued"] for a in st["attempts"]] == [False, True]
    assert "cut off" in (tmp_path / "05-a" / ".agent" / "prompt-2.md").read_text()
    assert st["attempts"][0]["usage"] == {"input_tokens": 10, "output_tokens": 2}
    assert second.returncode == 1                                 # 09-b failed its first attempt

    third = run(tmp_path)
    assert third.returncode == 0 and "05-a                       done (skipped)" in third.stdout
    status = subprocess.run([sys.executable, str(RUN_AGENT), str(tmp_path), "--status"],
                            capture_output=True, text=True).stdout
    assert "05-a" in status and "done" in status and "20 / — / 4" in status


def test_errors(tmp_path):
    res = subprocess.run([sys.executable, str(RUN_AGENT), str(tmp_path / "missing")], capture_output=True, text=True)
    assert res.returncode == 2
    res = subprocess.run([sys.executable, str(RUN_AGENT), str(tmp_path)], capture_output=True, text=True)
    assert res.returncode == 2 and "no prepared case" in res.stderr
