# Contributing

## Setup

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
python -m playwright install chromium          # only for building eval cases
sudo apt install xvfb libxcb-cursor0           # headless Linux
```

## Before a pull request

```bash
ruff check .
pytest -q
python skills/screenshot-to-qml/scripts/check.py skills/screenshot-to-qml/examples/hmi-dolum/project \
  --source skills/screenshot-to-qml/examples/hmi-dolum/input.png \
  --spec skills/screenshot-to-qml/examples/hmi-dolum/design-spec.json
```

QML in the repository must be `qmlformat`-clean and `qmllint`-clean (`-I qml --max-warnings 0`).

## Changing the skill

- Keep `SKILL.md` under 500 lines; put details in `references/` (one level deep, a table of
  contents for files over 100 lines).
- Scripts: `--help`, JSON or one-line summaries on stdout, exit codes 0/1/2, actionable errors
  (say what to do), no unexplained constants.
- Any change to scripts or references is measured: run the eval cases before and after and
  paste `run_evals.py` tables into the PR.

## Adding an eval case

1. Copy a template in `evals/tools/designs/`, set `case-meta` (id, viewport, dpr, fonts), use
   `:root` tokens (`--color-*`, `--space-*`, `--radius-*`, `--shadow-*`), mark elements with
   `data-node` / `data-role` / `data-state` / `data-model`, and icons with `<i data-icon="set:name"></i>`.
2. Designs must be original: fictional brands, names and data; no copied product UIs.
3. `python evals/tools/build_case.py --only <prefix> --pkg <dir with extracted icon npm packages>`
4. Add the rubric to `evals/tools/expectations.py` and run it.
5. Commit the template, the built case folder and any new cached icons.
