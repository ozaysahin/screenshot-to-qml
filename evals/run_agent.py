#!/usr/bin/env python3
"""Run a coding agent on every prepared case folder, one fresh session per case.

Usage:
  python evals/run_agent.py RUNS_DIR --agent codex|claude [--model M] [--cases 05,09]
  python evals/run_agent.py RUNS_DIR --cmd 'my-agent --prompt-file {prompt_file}'
  python evals/run_agent.py RUNS_DIR --status

RUNS_DIR comes from `evals/prepare_run.py` (each case folder holds PROMPT.md and its input).
For each case the agent starts in that folder with PROMPT.md as the prompt. Everything the
runner writes goes to <case>/.agent/: status.json, one log per attempt, the prompt sent.

Interruptions (usage limits, a crash, a timeout) are expected. A non-zero exit stops the
loop, so the remaining cases do not burn through a limit that is already spent; run the same
command again later. Finished cases are skipped, and an unfinished one restarts as a new session
whose prompt is PROMPT.md plus one paragraph saying the folder holds an interrupted session's
work (the same rule the 2026-10-18 run used). `--keep-going` moves on to the next case instead.

Agents:
  codex   codex exec --sandbox SANDBOX --skip-git-repo-check --json -o … PROMPT  (in CASE)
          (default sandbox danger-full-access: the skill writes its caches under ~/.cache,
          renders with Xvfb and fetches fonts from GitHub; run it on a machine or WSL distro
          meant for this)
  claude  claude -p PROMPT --dangerously-skip-permissions --output-format stream-json --verbose
  --cmd   any shell command; {prompt_file} and {dir} are filled in

DISPLAY and WAYLAND_DISPLAY are removed from the agent's environment, so renders go through
Xvfb as on the headless machine the prompt describes (WSLg would otherwise give Qt a desktop).

Exit codes: 0 every selected case finished, 1 stopped or some case unfinished, 2 error.
"""
from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
import time
from pathlib import Path

CONTINUE = (
    "An earlier session on this task was cut off before it finished. Its work is in this folder "
    "(`project/` and any analysis files). Continue from those files: check what is done, finish "
    "the rest, and run the checks again. Do not start over."
)


def load_status(case: Path) -> dict:
    f = case / ".agent" / "status.json"
    return json.loads(f.read_text()) if f.exists() else {"done": False, "attempts": []}


def save_status(case: Path, status: dict) -> None:
    (case / ".agent").mkdir(exist_ok=True)
    (case / ".agent" / "status.json").write_text(json.dumps(status, indent=1, ensure_ascii=False))


def usage_from_log(log: Path) -> dict:
    """Token totals from a JSON-lines log (Codex `turn.completed`, Claude `result` events)."""
    tot: dict[str, int] = {}
    if not log.exists():
        return tot
    for line in log.read_text(errors="replace").splitlines():
        try:
            ev = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            continue
        if not isinstance(ev, dict):
            continue
        u = ev.get("usage") if ev.get("type") in ("turn.completed", "result") else None
        if isinstance(u, dict):
            for k, v in u.items():
                if isinstance(v, int):
                    tot[k] = tot.get(k, 0) + v
    return tot


def command(args, case: Path, prompt: str, prompt_file: Path, n: int) -> tuple[list[str] | str, bool]:
    if args.cmd:
        cmd = args.cmd.replace("{prompt_file}", shlex.quote(str(prompt_file))).replace("{dir}", shlex.quote(str(case)))
        return cmd, True
    if args.agent == "codex":
        cmd = ["codex", "exec", "--sandbox", args.sandbox, "--skip-git-repo-check", "--json",
               "-o", str(case / ".agent" / f"last-message-{n}.md")]
        return cmd + (["-m", args.model] if args.model else []) + [prompt], False
    cmd = ["claude", "-p", prompt, "--dangerously-skip-permissions", "--output-format", "stream-json", "--verbose"]
    return cmd + (["--model", args.model] if args.model else []), False


def agent_version(args) -> str | None:
    if args.cmd:
        return None
    try:
        res = subprocess.run([args.agent, "--version"], capture_output=True, text=True, timeout=30)
        return (res.stdout or res.stderr).strip()[:100]
    except (OSError, subprocess.TimeoutExpired):
        return None


def show_status(cases: list[Path]) -> int:
    print(f"{'case':26s} {'state':10s} attempts  tokens (input / cached / output)")
    for c in cases:
        st = load_status(c)
        tot: dict[str, int] = {}
        for a in st["attempts"]:
            for k, v in (a.get("usage") or {}).items():
                tot[k] = tot.get(k, 0) + v
        state = "done" if st["done"] else ("stopped" if st["attempts"] else "new")
        tok = " / ".join(str(tot.get(k, "—")) for k in ("input_tokens", "cached_input_tokens", "output_tokens"))
        print(f"{c.name:26s} {state:10s} {len(st['attempts']):8d}  {tok}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("runs", type=Path)
    ap.add_argument("--agent", choices=["codex", "claude"], default="codex")
    ap.add_argument("--cmd", help="custom shell command instead of --agent ({prompt_file}, {dir})")
    ap.add_argument("--model", help="model name passed to the agent (default: the agent's own default)")
    ap.add_argument("--cases", default="", help="comma-separated id prefixes (default: every prepared folder)")
    ap.add_argument("--sandbox", default="danger-full-access",
                    choices=["read-only", "workspace-write", "danger-full-access"], help="codex only")
    ap.add_argument("--timeout", type=int, default=3 * 3600, help="seconds per attempt (default 3 h)")
    ap.add_argument("--keep-going", action="store_true", help="after a failed attempt, go on to the next case")
    ap.add_argument("--status", action="store_true", help="print the state of every case and exit")
    args = ap.parse_args(argv)

    if not args.runs.is_dir():
        print(f"[error] {args.runs} is not a folder (run evals/prepare_run.py first)", file=sys.stderr)
        return 2
    prefixes = [c.strip() for c in args.cases.split(",") if c.strip()]
    cases = sorted(p for p in args.runs.iterdir() if (p / "PROMPT.md").exists()
                   and (not prefixes or p.name.startswith(tuple(prefixes))))
    if not cases:
        print("[error] no prepared case folders matched", file=sys.stderr)
        return 2
    if args.status:
        return show_status(cases)
    if not args.cmd and not shutil.which(args.agent):
        print(f"[error] `{args.agent}` is not on PATH", file=sys.stderr)
        return 2

    env = {k: v for k, v in os.environ.items() if k not in ("DISPLAY", "WAYLAND_DISPLAY")}
    version = agent_version(args)
    unfinished = 0
    for case in cases:
        st = load_status(case)
        if st["done"]:
            print(f"{case.name:26s} done (skipped)")
            continue
        n = len(st["attempts"]) + 1
        prompt = (case / "PROMPT.md").read_text()
        if st["attempts"]:
            prompt = prompt.rstrip("\n") + "\n\n" + CONTINUE + "\n"
        (case / ".agent").mkdir(exist_ok=True)
        prompt_file = case / ".agent" / f"prompt-{n}.md"
        prompt_file.write_text(prompt)
        log = case / ".agent" / f"attempt-{n}.log"
        cmd, shell = command(args, case, prompt, prompt_file, n)
        attempt = {"n": n, "agent": args.cmd or args.agent, "version": version, "model": args.model,
                   "continued": n > 1, "start": time.strftime("%Y-%m-%dT%H:%M:%S")}
        print(f"{case.name:26s} attempt {n} …", flush=True)
        t0 = time.time()
        try:
            with log.open("w") as out:
                res = subprocess.run(cmd, cwd=case, env=env, shell=shell, stdin=subprocess.DEVNULL,
                                     stdout=out, stderr=subprocess.STDOUT, timeout=args.timeout)
            code = res.returncode
        except subprocess.TimeoutExpired:
            code = "timeout"
        attempt.update(end=time.strftime("%Y-%m-%dT%H:%M:%S"), minutes=round((time.time() - t0) / 60, 1),
                       exit=code, usage=usage_from_log(log))
        st["attempts"].append(attempt)
        st["done"] = code == 0 and (case / "project").is_dir()
        save_status(case, st)
        if st["done"]:
            print(f"{case.name:26s} finished in {attempt['minutes']} min")
            continue
        unfinished += 1
        tail = log.read_text(errors="replace").strip().splitlines()[-3:]
        why = "no project/ folder" if code == 0 else f"exit {code}"
        print(f"{case.name:26s} stopped ({why}). Last lines of {log}:")
        for line in tail:
            print("    " + line[:200])
        if not args.keep_going:
            print("Run the same command again later to continue (finished cases are skipped).")
            return 1
    return 1 if unfinished else 0


if __name__ == "__main__":
    sys.exit(main())
