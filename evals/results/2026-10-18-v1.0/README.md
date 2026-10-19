# Skill v1.0 on the 20-case eval set — 2026-10-18

The v1.0 exit run. It covers all 20 cases (the eight from v0.3 and twelve new ones), three
Claude models, and the v1.0 scorer.

## Setup

- **Cases:** all 20 in `evals/cases`. The twelve new ones are:
  - two dashboards (DPR 1.5; 1920×1080);
  - an ISA-101 boiler HMI;
  - a 7" EV charger screen on the software renderer;
  - a wizard with an open date picker;
  - a dark login screen;
  - two phone screens (DPR 3 and DPR 2);
  - a dense stock table;
  - two **HTML-input** cases, where the agent gets `source/index.html` and no PNG: one Tailwind v4 page, one hand-written CSS page;
  - a **hard case** whose font is not in the skill's catalog (20).
- **Prompt:** the one `evals/prepare_run.py` writes to each case folder as `PROMPT.md`. It is
  identical for every skill arm and model. The baseline builds are from 2026-09-27 and had that
  run's prompt: the same task text, with slightly different environment notes. Each build
  started as a new session that sees only its case folder and the skill. One build per case
  and arm; most builds were interrupted by usage limits (see Interruptions).
- **Arms:**

  | Arm | Model | Cases |
  | --- | --- | --- |
  | skill v1.0 | `claude-opus-5-5` | all 20 |
  | skill v1.0 | `claude-sonnet-5-5` | 05, 09, 12, 18 |
  | skill v1.0 | `claude-haiku-5-5` | 05, 12, 18 |
  | baseline (no skill) | `claude-opus-5-5` | 01–08: the 2026-09-27 builds, re-scored |

  The skill copy is the v1.0 skill as of the run. For case 01 it has `examples/hmi-dolum`
  removed, because that example is the answer to case 01. The shipped v1.0 differs from that
  copy only in what this run found (see "Changes made after the builds").
- **Scoring:** `run_evals.py` with the golden spec and the calibrated thresholds:
  - global SSIM ≥ 0.98;
  - region SSIM ≥ 0.90, each region at its best alignment within 1 design px (an offset is
    scored by the geometry check, not twice). Unaligned, 11 of the 20 builds have every region
    ≥ 0.90;
  - ΔE ≤ 2;
  - geometry ≤ 2 px;
  - every string found and within 2 px;
  - plus all quality gates.

  Every arm was scored by the same v1.0 scorer.

## Against the v1.0 success criteria (plan summary)

| Criterion | Skill v1.0, opus, 20 cases |
| --- | --- |
| Global SSIM ≥ 0.95 | **20/20** (min 0.9873, mean 0.9949) |
| Region SSIM ≥ 0.90 | **18/20**. Misses: 01 alarm badge 0.878, 07 dashed filter chip 0.859 |
| ΔE2000 ≤ 2.0 on solid fills | **19/19 measured** (max 1.13). 08 has no opaque solid fill to measure |
| Position/size error ≤ 2 px | **18/20**. Misses: 08 clock 2.37 px, 12 cost tile 3.91 px |
| qmllint and runtime QML warnings: 0 | Runtime: **20/20 with 0 warnings**. Lint: **19/20**. 08 uses `RectangularShadow` (Qt 6.9) in a project whose floor is Qt 6.8 |
| Passes with Codex CLI (narrowed on 2026-10-19 from "≥ 2 agents other than Claude") | **Partly.** Two Codex runs on cases 05, 09, 12, 18: all gates pass in 4/4 both times, plan criteria 1/4 both times (the HTML case). See "Codex CLI" below |
| **All measured criteria per case** | **16/20** |

With the stricter calibrated thresholds plus all 13 gates, **12/20** pass outright. Each of
the eight misses comes down to one to three items:

| Case | Miss |
| --- | --- |
| 01 | Alarm count badge (28×24 px) region SSIM 0.878 |
| 02 | One price, "180 ₺", 2.03 px off |
| 07 | Dashed filter chip 0.859. QML has no dashed border; the approximation shows |
| 08 | Lint: `RectangularShadow` above the 6.8 floor. Also the clock is 2.37 px off |
| 10 | Three legend labels typed with "-" instead of "–" ("10–20") |
| 12 | "₺" drawn as a fallback-font glyph. The screen draws it as an icon of another width, so "293,40" moves 4.5 px |
| 17 | The pagination label typed with "-" instead of "–" ("1–14 / 326") |
| 20 | Three strings 2.3–3.5 px off. This is the case whose font is not in the catalog |

Two of the misses (10, 17) are the same slip: an en dash read as a hyphen. OCR cannot tell
them apart, so after this run SKILL.md lists `–` in ranges among the characters to check by
eye.

Every opus build is lint- and format-clean (except 08's minimum-Qt error), has zero runtime
warnings and zero hard-coded colors or fonts, and wraps every visible string in `qsTr()`.
All **337/337** enabled controls are reachable with Tab and show focus. No `MouseArea` is used
as a button.

## By model

Cases 05, 12 and 18 were built by all three models. Sonnet also built 09. Details are in
[`comparison-models.md`](comparison-models.md).

| | opus | sonnet | haiku |
| --- | --- | --- | --- |
| Full pass (calibrated + gates) | 2/3 | 2/3 (2/4 with 09) | 0/3 |
| All quality gates pass | 3/3 | 4/4 | 3/3 |
| Meets the plan criteria | 2/3 | 4/4 | 1/3 |
| Mean global SSIM | 0.9977 | 0.9979 | 0.9890 |
| Mean worst region | 0.954 | 0.961 | 0.910 |
| Text within 2 px | 98.6 % | 98.6 % | 91.9 % |
| Controls with Tab + visible focus | 52/52 | 52/52 | 51/51 |

The plan criteria do not include text position, so sonnet's 12 meets them with one string
6.0 px off (the same "₺" icon-width slip as opus); opus's and haiku's 12 miss on a 3.9–4.0 px
geometry offset.

The production rules carry over to the smallest model: every haiku project passes all gates.
The models differ in measurement discipline. Haiku's projects are visually close (SSIM ≥ 0.987)
but leave more text 2–4 px off, and its regions sit at the 0.90 line.

## Codex CLI (two runs, 2026-10-19)

The user ran Codex CLI (`gpt-6-astra`, reasoning medium, as named in Codex) on Windows, on the
four cases sonnet built. Each case was a new session started in its folder with "Read PROMPT.md
in this folder and do the task it describes." `PROMPT.md` came from
`prepare_run.py --os windows --portable`: the same task, with a Windows environment line. The
projects were scored here with the same scorer as every other arm
([`comparison-codex.md`](comparison-codex.md), [`codex-run1/`](codex-run1/results.md),
[`codex-run2/`](codex-run2/results.md)).

- **Run 1:** nothing prepared. The skill's font catalog never arrived (05: "the font matcher had
  no candidate catalog"; 12: only eight families in its cache) and Tesseract was missing.
- **Run 2:** before the sessions, the user installed Tesseract (tur + eng) and ran the skill's
  `font_match.py fetch` and `icon_match.py fetch`, as the Claude arms had them.

| | opus | sonnet | codex run 1 | codex run 2 |
| --- | --- | --- | --- | --- |
| Full pass (calibrated + gates), 05/09/12/18 | 3/4 | 2/4 | 1/4 | 1/4 |
| All quality gates pass | 4/4 | 4/4 | **4/4** | **4/4** |
| Meets the plan criteria | 3/4 | 4/4 | 1/4 | 1/4 |
| Mean global SSIM | 0.9954 | 0.9948 | 0.9828 | 0.9798 |
| Mean worst region | 0.954 | 0.954 | 0.881 | 0.888 |
| Text within 2 px | 98.9 % | 97.4 % | 90.8 % | 89.7 % |
| Controls with Tab + visible focus · MouseArea buttons | 65/65 · 0 | 64/64 · 0 | 65/65 · 0 | 65/65 · 0 |

**The production half carries over.** In both runs every Codex project is lint-, format- and
runtime-clean, uses only Theme tokens, wraps every string in `qsTr()`, and builds every control
on `QtQuick.Templates` with keyboard focus.

**The visual half does not.** Case 18, the HTML input whose fonts come with it, passes outright
in both runs. The three screenshot cases fail both times:

- **Fonts.** Run 1 built 05, 09 and 12 in substitute fonts. In run 2, 05 got the right family
  (Plus Jakarta Sans) but 09 and 12 did not: Codex's matcher picked Inter for 09. The same
  screenshot and the same spec of Codex's own, matched here with the full catalog, give Onest,
  the right family. So the catalog on that machine was most likely still incomplete. GitHub
  rate-limits bursts of downloads, and `fetch` used to report a refused download as "not
  found". For 12, Codex's draft text runs were too rough for any family to win clearly.
- **Text and geometry.** Wrong widths move buttons and labels: 09's date-range label is 14 px
  off in both runs. 05, even in the right font, stays 2.4 px off in geometry and 3.2 px in text.
- **Not fonts.** 09's avatar fill is wrong in both runs (ΔE 7.4–7.7), and 12's connector icon
  is drawn differently (region 0.75–0.83).

So the skill's production rules work with Codex as well as with Claude, but its measurement
loop did not get Codex to the same fidelity: 1/4 against opus's 3/4 on the same cases. With
one build per case and the catalog doubt in run 2, this run cannot split the gap between the
agent and that machine's setup.

Fixes from these runs:

- `font_match.py fetch` retries rate-limited and failed downloads, then says plainly that the
  catalog is incomplete and why (it used to report every refused download as "not found");
- `icon_match.py fetch` finds `npm.cmd` on Windows, and SKILL.md says to set `PYTHONUTF8=1` there;
- one Codex project (run 2, case 12) crashed PySide during `render.py`'s scan for idle
  animations, which wraps every child QObject. `check.py` now renders such a project again
  with `--no-idle-scan`, and the perf gate warns that the scan was skipped.

## Baseline vs skill (cases 01–08)

From [`comparison-baseline.md`](comparison-baseline.md). The baseline builds are the 2026-09-27
ones, re-scored with the v1.0 gates.

| | baseline | skill v1.0 |
| --- | --- | --- |
| Full pass | 0/8 | 4/8 |
| Visual checks pass (no gates) | **6/8** | 4/8 |
| All quality gates pass | 0/8 | 7/8 |
| Mean global SSIM | 0.9953 | 0.9951 |
| Mean worst region | 0.939 | 0.947 |
| Controls with Tab + visible focus | 9/19 | 153/153 |
| MouseArea buttons · runtime warnings · hard-coded values · strings without qsTr | 46 · 48 · 239 · 142 | 0 · 0 · 0 · 0 |

On pixels alone the baseline did better here: 6 of 8 baseline builds pass every visual check,
against 4 of 8 skill builds (the skill misses are 01's badge, 02's one price, 07's dashed chip
and 08's clock). Mean scores are a tie, as in every earlier run. The skill's value is a project
that ships: no baseline build passes the gates.

Since the probe fix, the interaction probe visits every control in all eight baseline
projects. Before it, baseline 03 and 08 stopped at a control that quit the app, so the earlier
counts (9/18 controls, 27 `MouseArea` buttons) were lower bounds.

Against skill v0.5 (2026-09-29), two v1.0 builds score a lower global SSIM by more than the
0.005 the ship rule allows: 04 (0.9873 vs 0.9946) and 07 (0.9922 vs 0.9983). Skill v0.4 had
scored 04 at 0.9875 too, and there is one build per case, so this reads as build-to-build
noise (about ±1 case) rather than a regression in the skill, but it was not re-run to confirm.
Skill v0.5 passed 5/8 of these cases under its own gates. Under the v1.0 gates its builds fail
the minimum-Qt lint (`RectangularShadow`) in 7 of 8, which is why v1.0 rewrote the shadow
guidance.

## Changes made after the builds

The agents built with the skill copy as of the run. What the run found was fixed afterwards,
in two groups.

**Scorer.** Every arm above was re-scored with the fixed version; the agents' own checks
during their builds used the earlier copy.

- **Text areas:** `render.py` now reads `TextArea`/`TextEdit` content line by line, from the
  text document's layout and its vertical alignment. Before, a real multi-line `TextArea` (13)
  counted as "missing text".
- **Fill colors:** fills (ΔE) are measured on the pixels where the screenshot shows the node's
  dominant color. Before, a status dot or a CSS `::before` switch knob that is not its own node
  moved the median: up to ΔE 18 for identical fills (17, 18).
- **Wrapped spans:** a text run that starts inside one line and wraps onto the next (a tinted
  second half of a headline) now matches across the line break (14, 20).
- **Separators:** separators drawn as shapes (`•••• 4821`) are matched on the edge that was not
  cut, instead of the run's left edge (15).
- **Vertical labels:** rotated or vertical text is compared by box centers; a baseline means
  nothing there (20).
- **Probe crash:** a control that quits or closes the window when pressed no longer ends the
  interaction probe (baseline 03 and 08 called `Qt.quit()`). Quit and close are held off while
  the probe runs, so every control is still visited; a probe that fails anyway is an `a11y`
  error instead of a crashed check.

**Skill.** These change what an agent does, so their effect is not in this run's numbers:

- `shadow_fit.py`, `gradient_fit.py`: nodes with per-corner radii (`[12, 12, 0, 0]`) crashed
  the fitter; they now use the largest corner.
- SKILL.md: `–` in ranges joins the characters to check by eye (10, 17); the checklist has an
  HTML-input line; system fonts named in CSS are called out.
- `html_to_spec.py` / `html_extract.js`, from a review after the run: linked stylesheets read
  from `file://`, `data:` fonts saved as files, elements hidden by an `opacity: 0` ancestor
  skipped, invalid `lang` values no longer crash, `<textarea>` text wrapped into one run per
  line, unreadable stylesheets reported.

## Interruptions

Usage limits interrupted most builds. Of 27 builds:

- 6 ran in one go: opus 06, 14, 18, 19 and haiku 12, 18.
- 9 were resumed with their own context: opus 02, 03, 05, 08, 10, 13, 16; sonnet 05; haiku 05.
- 12 were finished by a second session of the same model and skill, which continued from the
  first one's files: opus 01, 04, 07, 09, 11, 12, 15, 17, 20; sonnet 09, 12, 18. Four of the
  opus ones were then resumed again.

The continuing session got the same prompt plus one paragraph saying the folder holds an
interrupted session's work.

## Files

- `skill-v1.0-opus/`, `skill-v1.0-sonnet/`, `skill-v1.0-haiku/`, `baseline/` each hold
  `results.{json,md}` and `gates.json`, with gate errors capped at 20 per gate.
- `codex-run1/`, `codex-run2/` hold the Codex projects' scores in the same format.
- `comparison-models.md` (opus, sonnet, haiku, codex on 05/12/18), `comparison-codex.md`
  (opus, sonnet, both Codex runs on 05/09/12/18) and `comparison-baseline.md` are from `compare_runs.py`.
