#!/usr/bin/env python3
"""Prepare agent work folders for an eval run (any agent: Claude Code, Codex CLI, Gemini CLI …).

Usage:
  python evals/prepare_run.py RUNS_DIR [--cases 09,10] [--skill PATH] [--force] [--os windows] [--portable]

For every case this creates RUNS_DIR/<case-id>/ holding only what the agent may see:
  input.png              screenshot cases
  source/                HTML-input cases (index.html + fonts/)
  PROMPT.md              the task, identical for every agent and arm

With --skill PATH (a `screenshot-to-qml` skill folder) the prompt tells the agent to read the
skill first; the skill is copied to RUNS_DIR/_skill/full/screenshot-to-qml, and case 01 gets a
copy without `examples/hmi-dolum` (that example is the answer to case 01). Without --skill the
run is a baseline. --os windows changes the environment line for agents on Windows; --portable
writes the skill path relative to the case folder, for a RUNS_DIR handed to another machine.

Then run one fresh agent session per case folder with PROMPT.md as the prompt, e.g.
`python evals/run_agent.py RUNS_DIR --agent codex` (it handles logs, usage limits and
continuing an interrupted case), or by hand:

  cd RUNS_DIR/09-dashboard-sales && codex exec "$(cat PROMPT.md)"

and score the projects with `python evals/run_evals.py RUNS_DIR`.

Exit codes: 0 ok, 2 error (unknown case, skill folder without SKILL.md, existing folders without --force).
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CASES = ROOT / "evals" / "cases"

SCREENSHOT_TASK = (
    "Rebuild this screen (`input.png`) as a native PySide6 Qt Quick project in `./project`.\n"
    "Screenshot DPR: {dpr}. Target: {profile}. Use a `Window` root in `qml/App/Main.qml` (module `App`)\n"
    "and bundle fonts in `project/assets/fonts`."
)
QT5_TASK = (
    "Rebuild this screen (`input.png`) as a native Qt Quick project for Qt 5.15 with a C++ (CMake) host in\n"
    "`./project`; the QML must load on Qt 5.15. Screenshot DPR: {dpr}. Target: {profile}. Use a `Window` root in\n"
    "`qml/App/Main.qml` (module `App`) and bundle fonts in `project/assets/fonts`. Qt 5.15 for the build: Linux\n"
    "`apt install qtdeclarative5-dev qtquickcontrols2-5-dev qml-module-qtquick-controls2 qml-module-qtquick-shapes\n"
    "qml-module-qtgraphicaleffects`, Windows `aqt install-qt windows desktop 5.15.2 win64_msvc2019_64`."
)
HTML_TASK = (
    "Rebuild this page (`source/index.html`, its fonts are in `source/fonts`) as a native PySide6 Qt Quick\n"
    "project in `./project`. The page is designed for a {w}×{h} viewport; the result is compared with the\n"
    "page rendered at DPR {dpr}. Target: {profile}. Use a `Window` root in `qml/App/Main.qml` (module `App`)\n"
    "and bundle fonts in `project/assets/fonts`."
)
RULES = (
    "You work alone: nobody will answer questions, so make reasonable assumptions and list them in\n"
    "`project/README.md`. Work only in this folder{skill_note}; do not look at other folders.\n"
    "{env}"
)
ENV = {
    "linux": ("Environment: Linux without a display (use `xvfb-run` to render), Python 3 with PySide6 6.8+,\n"
              "Playwright with Chromium; network access to pip, npm and GitHub only."),
    "windows": ("Environment: Windows with a display (renders open a window), network access; install what\n"
                "is missing (Python 3 with PySide6 6.8+, Playwright with Chromium, tools the skill needs)."),
}
SKILL_LINE = ("The `screenshot-to-qml` agent skill is installed at `{skill}`; read its `SKILL.md` first and\n"
              "follow it.")


def prompt(meta: dict, skill: Path | str | None, os_name: str = "linux") -> str:
    w, h = meta["designSize"]
    template = (HTML_TASK if meta.get("category") == "html"
                else QT5_TASK if str(meta.get("minQt", "6.8")).startswith("5.") else SCREENSHOT_TASK)
    task = template.format(
        dpr=meta["dpr"], profile=meta.get("profile", "desktop"), w=w, h=h)
    rules = RULES.format(skill_note=" (and read the skill folder below)" if skill else "", env=ENV[os_name])
    parts = [task, rules] + ([SKILL_LINE.format(skill=skill)] if skill else [])
    return "\n\n".join(parts) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("runs", type=Path)
    ap.add_argument("--cases", default="", help="comma-separated id prefixes (default: all)")
    ap.add_argument("--skill", type=Path, help="skill folder to install for the agents (omit for a baseline)")
    ap.add_argument("--force", action="store_true", help="reuse existing case folders (PROMPT.md and inputs are rewritten)")
    ap.add_argument("--os", choices=sorted(ENV), default="linux", help="machine the agent runs on (environment line)")
    ap.add_argument("--portable", action="store_true",
                    help="point the prompt at the skill with a relative path (../_skill/…), so RUNS_DIR can be moved")
    args = ap.parse_args(argv)

    prefixes = [c.strip() for c in args.cases.split(",") if c.strip()]
    cases = sorted(p for p in CASES.iterdir() if p.is_dir() and (not prefixes or p.name.startswith(tuple(prefixes))))
    if not cases:
        print("[error] no cases matched", file=sys.stderr)
        return 2
    unknown = [pre for pre in prefixes if not any(c.name.startswith(pre) for c in cases)]
    if unknown:
        print(f"[error] no case matches: {', '.join(unknown)}", file=sys.stderr)
        return 2
    busy = [args.runs / c.name for c in cases if (args.runs / c.name).exists() and any((args.runs / c.name).iterdir())]
    if busy and not args.force:      # checked before anything is written: agents may be using these folders
        print(f"[error] {busy[0]} exists (use --force)", file=sys.stderr)
        return 2
    skills = {}
    if args.skill:
        if not (args.skill / "SKILL.md").exists():
            print(f"[error] no SKILL.md in {args.skill}", file=sys.stderr)
            return 2
        need_no_example = any(c.name.startswith("01-") for c in cases)
        for variant in ("full", "no-example") if need_no_example else ("full",):
            dst = (args.runs / "_skill" / variant / "screenshot-to-qml").resolve()
            if dst.exists():
                shutil.rmtree(dst)
            shutil.copytree(args.skill, dst, ignore=shutil.ignore_patterns("__pycache__", ".check", "out", "build"))
            if variant == "no-example":
                shutil.rmtree(dst / "examples" / "hmi-dolum", ignore_errors=True)
            skills[variant] = dst
    for case in cases:
        meta = json.loads((case / "golden-spec.json").read_text())["meta"]
        d = args.runs / case.name
        d.mkdir(parents=True, exist_ok=True)
        if meta.get("category") == "html":
            if (d / "source").exists():
                shutil.rmtree(d / "source")
            shutil.copytree(case / "source", d / "source")
        else:
            shutil.copy2(case / "input.png", d / "input.png")
        skill = skills.get("no-example" if case.name.startswith("01-") else "full")
        if skill and args.portable:
            skill = "../" + skill.relative_to(args.runs.resolve()).as_posix()
        (d / "PROMPT.md").write_text(prompt(meta, skill, args.os))
        print(f"{d}  ({'html' if meta.get('category') == 'html' else 'png'}, {'skill' if skill else 'baseline'})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
