# Baseline vs skill — 2026-09-27

The same model rebuilt each of the eight eval screens twice: once without the skill
(**baseline**) and once with `screenshot-to-qml` v0.4 installed (**skill**). Both sets were
scored the same way, by `run_evals.py` against the golden specs.

## Setup

- **Model:** `claude-opus-5-5` in both arms. A general-purpose coding agent ran one build per
  case per arm, 16 in total.
- **Isolation:** each run started as a fresh agent session in an empty folder that held only
  `input.png`. The agent never saw the HTML source or the golden spec.
- **Prompt:** the task text in [`evals/README.md`](../../README.md#running-agents-any-agent-any-model)
  (the screenshot task; `prepare_run.py` did not exist yet), plus the same
  environment notes for both arms:
  - headless Linux with PySide6 6.11 and `xvfb-run`;
  - network access to pip, npm and GitHub only;
  - no one answers questions, so the agent makes assumptions and lists them in the README.
- **Skill arm only:** one extra line: *"The `screenshot-to-qml` agent skill is installed at …;
  read its `SKILL.md` first and follow it."*
- **Case 01 exception:** this case is also the skill's reference example, so its skill run used
  a copy of the skill with `examples/` removed.
- **Scoring:** `run_evals.py` with the calibrated thresholds (global SSIM ≥ 0.98, region SSIM
  ≥ 0.90 aligned within 1 px, ΔE ≤ 2, geometry ≤ 2 px, 100 % of strings found and each within
  2 px), plus the seven quality gates.

## Results

| | baseline | skill v0.4 |
| --- | --- | --- |
| **Full pass (visual + quality gates)** | **0/8** | **6/8** |
| Visual checks pass | 6/8 | 6/8 |
| Quality gates pass | 0/8 | 8/8 |
| Mean global SSIM | 0.9953 | 0.9958 |
| Mean worst-region SSIM | 0.939 | 0.959 |
| Text on target (≤ 2 px) | 99.5 % | 99.6 % |
| Lint errors (qmllint), total | 150 | 0 |
| Files not qmlformat-clean, total | 93 | 0 |
| Runtime QML warnings, total | 48 | 0 |
| Hard-coded colors/fonts outside Theme, total | 239 | 0 |
| QML files / lines per project | 16 / 1309 | 31 / 2168 |

Per-case numbers are in [`comparison.md`](comparison.md), [`baseline/results.md`](baseline/results.md)
and [`skill-v0.4/results.md`](skill-v0.4/results.md). The gate errors behind the totals, capped at
20 per gate, are in `*/gates.json`.

## What this shows

1. **Visual fidelity is a tie.** Without the skill the model already reproduces these
   screens at global SSIM 0.991–0.998 and puts 99.5 % of strings within 2 px. The skill barely
   moves the pixels.
2. **The difference is whether the project can ship.** Every skill project is lint-clean,
   formatted, free of runtime warnings, and keeps colors and fonts in a Theme. No baseline
   project passes those gates. Skill projects have more files because tokens, controls and
   components are split into the `App`, `App.Style` and `App.Controls` modules.
3. **Two skill runs still fail, both on visuals:**
   - **01:** the tank percentages use JetBrains Mono Bold, but both arms picked Barlow. That
     puts the text 2 px low and 1.5 px wide. Font identification is on the v0.6 roadmap.
   - **07:** the filter chips have dashed borders, and QML has no dashed border. Both arms
     approximated it, scoring region SSIM 0.889 (skill) and 0.784 (baseline). A dashed-border
     recipe is on the v0.6 roadmap.

## Caveats

- **Sample size:** one run per case and arm. Differences of about ±0.002 in SSIM are noise.
- **Interrupted runs:** API rate limits interrupted 11 of the 16 runs.
  - 9 were resumed with their full context.
  - 2 (baseline 08, skill 06) lost their session. A fresh agent finished each one from the
    partial work already on disk.
- **Scorer version:** skill runs 01–02 used the v0.4.0 scripts. The later skill runs used the
  v0.4.1 scorer fixes that came out of runs 01–02 (below). `SKILL.md` and the references were
  the same for every run.
- **The gates encode the skill's rules:** the quality gates check the skill's production rules
  (Theme tokens, qmlformat, no runtime warnings), and the baseline agent was never told those
  rules. Teaching them is the skill's job, but read the gate rows as "follows the house rules",
  not as "bad code".

## Scorer fixes found by this run (v0.4.1)

Each of these made a correct build score as wrong:

- **Hidden text:** text inside a QML component that wraps `Text` (`AppText { }`), and Controls
  `Label`, was invisible to the scene dump. It now uses `inherits()`.
- **Text-field values:** `TextField` and `TextInput` values were not dumped. They are now,
  with a position computed from padding and vertical alignment.
- **Padding:** text boxes ignored `leftPadding` (`QQuickText::boundingRect` does not include
  it). Boxes are now computed from padding, alignment and glyph advances.
- **Text runs:** a design's runs may be merged, split or wrapped differently in QML. A run can
  now match a whole item, one line, or part of a line. Separators such as ` ·` and `…` versus
  `...` are tolerated.
- **Vertical position:** this is now measured between baselines, recorded in the golden spec
  from the browser's font metrics. Comparing box centres moved whenever two fonts had
  different ascent and descent.
- **Repeated strings:** a string that appears twice ("1" in a footer and in a pager) was
  assigned first-come. Matching is now global and nearest-first.
- **Region SSIM:** this is now taken at the best alignment within 1 px. A control drawn 1 px
  to the side is a position error, which the geometry check measures separately.
- **Golden specs:**
  - Text boxes no longer include leading and trailing whitespace.
  - Text hidden under an opaque element (a list row under the tab bar) is dropped.
  - The input screenshots are byte-identical to before.
- **Embed gate:** an agent's own preview render left in the project folder was reported as
  an embedded screenshot. It is now a warning unless the UI uses the file.
- **Crashes and stale results:**
  - A PySide enum-converter crash is fixed.
  - `check.py` now clears stale results, so a crashed diff can no longer report the previous
    run's numbers.
  - `render.py` loads projects that have no `qmldir`.

The full projects, renders and diffs are in `evalruns-2026-09-27-baseline.zip` and `evalruns-2026-09-27-skill-v0.4.zip` on the GitHub release.

## Reproduce

```bash
# after placing each run's project in runs/<label>/<case-id>/project/
python evals/run_evals.py runs/baseline
python evals/run_evals.py runs/skill-v0.4
python evals/compare_runs.py runs/baseline runs/skill-v0.4 --labels baseline "skill v0.4"
```
