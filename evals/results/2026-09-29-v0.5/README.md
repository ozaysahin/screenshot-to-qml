# Skill v0.5 on the eval set — 2026-09-29

Skill v0.5 adds a production control kit, derived state tokens and three gates: `a11y`,
`states` and `i18n`. This run re-scores the baseline and skill v0.4 builds from 2026-09-27
with the v0.5 gates, and adds fresh skill v0.5 builds of the same eight screens.

## Setup

- **Same as the [2026-09-27 run](../2026-09-27/README.md).** The model is `claude-opus-5-5`;
  each build is a fresh agent session that sees only `input.png`, with the same prompt and
  one build per case.
- **Skill copy:** the skill v0.5 arm reads a copy of the skill as released in v0.5. For case
  01, the copy has `examples/hmi-dolum` removed, because that example is the answer to case 01.
- **Gates:** every arm is scored with the v0.5 gates:
  - `a11y`: real Tab presses; every enabled control reachable with a visible focus change and
    an accessible name; no `MouseArea` buttons;
  - `states`: pressing a control visibly changes it;
  - `i18n`: visible strings are wrapped in `qsTr()`.

## Results

| | baseline | skill v0.4 | skill v0.5 |
| --- | --- | --- | --- |
| **Full pass** (visual + all gates) | **0/8** | **0/8** | **5/8** |
| Visual checks pass | 6/8 | 6/8 | 5/8 |
| All quality gates pass | 0/8 | 0/8 | **8/8** |
| Mean global SSIM | 0.9953 | 0.9958 | 0.9965 |
| Mean worst-region SSIM | 0.939 | 0.959 | 0.963 |
| Real controls (Template-based, enabled) | 19 | 153 | 161 |
| … reachable with Tab, focus visible | 9/19 | 152/153 | **161/161** |
| MouseArea used as a button | 46 | 0 | 0 |
| Accessibility errors (total) | 64 | 1 | 0 |
| Controls without a visible pressed state | 0 * | 19 | 0 |
| Strings not wrapped in `qsTr()` | 142 | 4 | 0 |
| Lint / format / runtime / literal errors | 150 / 93 / 48 / 239 | 0 | 0 |

\* The baseline has almost no real controls to press: 46 of its "buttons" are `MouseArea`s,
which the probe does not press.

Per-case numbers are in [`comparison.md`](comparison.md). The capped error lists behind the
totals are in `*/gates.json`.

## What this shows

1. **The v0.5 exit criterion is met.** Every v0.5 build has zero hard-coded values, and every
   one of its 161 controls can be reached with the keyboard, shows focus, and has a pressed
   state and an accessible name. All eight builds pass all ten gates.
2. **Pixels stay the same.** Mean global SSIM is 0.9965 (v0.4: 0.9958), and the worst-region
   mean rose from 0.959 to 0.963. On 07 the dashed filter chips moved from 0.889 to 0.923, now
   above the gate.
3. **The three misses are single strings:**
   - 01: the batch clock is 2.1 px left.
   - 03: the donut's center number is 4 px high.
   - 07: the count next to the page title is 2.05 px right.

   Each is one string out of 95–112. Text on target is 99.6 %.

## Caveats

- **Sample size.** There is one build per case and arm, so SSIM differences of about ±0.002
  are noise.
- **Interrupted runs.** Rate limits interrupted six v0.5 builds; five were resumed with
  their context. The 03 build restarted from an empty folder after losing its session early.
- **The gates encode the skill's rules.** The baseline never saw the rules the gates check.
  Read those rows as "meets the production bar the skill teaches".
