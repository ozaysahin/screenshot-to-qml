# screenshot-to-qml — eval set

Twenty-one original, synthetic UI screens used to measure the skill. Each case has a
screenshot input **and** a machine-extracted ground truth, so every score is a
number, not an opinion.

All designs, brands, names and data are fictional and were made for this repo.
No company screens are used.

## Cases

| Case | Size (design px) | DPR | Input px | Fonts | Tests |
| --- | --- | --- | --- | --- | --- |
| `01-hmi-dolum` | 1920×1080 | 1 | 1920×1080 | Barlow, JetBrains Mono, Font Awesome 7 | Industrial HMI, fixed canvas, gauges, alarms, slider, disabled state, icon font, line chart |
| `02-kiosk-kafe` | 1080×1920 | 1 | 1080×1920 | Manrope | Portrait kiosk, clipped horizontal tabs, product grid, stepper, gradient banner, ₺ glyph |
| `03-dashboard-dark` | 1440×900 | 2 | 2880×1800 | Inter, Space Grotesk | Retina input, sidebar nav, KPI sparklines, 2-series area chart, donut, table |
| `04-dashboard-light` | 1440×900 | 1.25 | 1800×1125 | DM Sans | Fractional (Windows 125%) scale, multi-layer shadows, bar charts, ring progress |
| `05-settings-form` | 1280×800 | 1 | 1280×800 | Plus Jakarta Sans | Every common control + focus / placeholder / error / disabled / checked states |
| `06-mobile-aliskanlik` | 390×844 | 3 | 1170×2532 | Nunito | 3× mobile input, week strip, ring, list under tab bar, filled vs outline icons |
| `07-data-table` | 1440×900 | 1 | 1440×900 | Inter, JetBrains Mono | Table: tri-state header checkbox, selected + hover rows, sort, badges, pagination |
| `08-glass-home` | 1280×800 | 2 | 2560×1600 | Outfit | **Hard case**: backdrop blur, gradient borders, blurred blobs, conic gradient, glow |
| `09-dashboard-sales` | 1440×900 | 1.5 | 2160×1350 | Onest | DPR 1.5, icon rail, dashed comparison series + hover tooltip, funnel, stacked bar |
| `10-dashboard-ops-dark` | 1920×1080 | 1 | 1920×1080 | Sora, DM Mono | NOC wall screen: semicircle gauges, 7×24 heatmap model, monospace log clipped at the edge |
| `11-hmi-boiler` | 1280×800 | 1 | 1280×800 | Rajdhani | ISA-101 gray HMI (embedded-gpu): vector mimic diagram, pump/valve states, steppers, soft keys |
| `12-ev-charger` | 1024×600 | 1 | 1024×600 | Titillium Web | 7" EV charger, **embedded-sw** (software renderer): flat only, segmented bar, ₺ as an icon |
| `13-form-wizard` | 1280×800 | 1.25 | 1600×1000 | Albert Sans | Stepper, open date-picker popup over the form, tag input, dashed drop zone, upload progress |
| `14-form-login-dark` | 1280×800 | 2 | 2560×1600 | Red Hat Display, Red Hat Text | Dark sign-in: radial gradients, password echo, busy button, toast, two families of one design |
| `15-mobile-wallet` | 393×852 | 3 | 1179×2556 | Mulish | Gradient card, transactions grouped by day (sections), row under a raised bottom nav |
| `16-mobile-chat` | 360×800 | 2 | 720×1600 | Be Vietnam Pro | Chat bubbles with per-corner radii, reply quote, voice waveform model, typing indicator |
| `17-data-table-stock` | 1366×768 | 1 | 1366×768 | Public Sans, IBM Plex Mono | Dense table: frozen column, horizontal scroll, group rows, inline edit, totals |
| `18-html-tailwind-billing` | 1280×800 | 1 | 1280×800 | Instrument Sans | **HTML input**: Tailwind v4 page (oklch palette, rings, real form elements) |
| `19-html-css-board` | 1366×768 | 2 | 2732×1536 | Karla | **HTML input**: hand-written CSS kanban with `<input>`, `<select>`, checkbox |
| `20-hard-weather` | 1280×800 | 2 | 2560×1600 | Bricolage Grotesque | **Hard case**: a font outside the skill's catalog, gradient text, rotated label, conic ring |
| `21-auto-cluster` | 1920×720 | 1 | 1920×720 | Rajdhani | **Qt 5.15 + C++** (`minQt` 5.15, target `cpp`): car instrument cluster, two 270° dials with generated ticks and a redline, telltales, navigation card |

Every case uses Turkish text (ç ğ ı İ ö ş ü) so OCR and font coverage are tested. By plan
category: dashboard 4 (03, 04, 09, 10), HMI/kiosk 4 (01, 02, 11, 12), form 3 (05, 13, 14),
mobile 3 (06, 15, 16), table 2 (07, 17), HTML input 2 (18, 19), hard 2 (08, 20), automotive 1 (21).
Case 21 (v1.1) asks for a Qt 5.15 project with a C++ host; `prepare_run.py` words its prompt
accordingly. It has no agent runs yet, so the results below cover cases 01–20.

**HTML-input cases** (category `html`) give the agent `source/` (the page and its fonts), not
`input.png`; the PNG is the reference the result is scored against. All other cases give only
`input.png`.

## Files per case

```
cases/<id>/
├── input.png          # the "screenshot": what the skill receives
├── golden-spec.json   # ground truth extracted from the live DOM
├── expected.json      # rubric: common + must-have + allowed approximations + forbidden
├── thresholds.json    # numeric gates, calibrated on the 2026-09-27 baseline (01–08; 09–21 reuse them)
└── source/index.html  # static HTML snapshot for the HTML-input path (no JS, no hint attributes)
                       # HTML-input cases: source/fonts/ too, so the folder is the agent's input as is
```

`golden-spec.json` follows the `design-spec.json` shape from the plan:

- `meta` — design size, DPR, capture size, fonts (CSS family, Qt family, files, weights)
- `tokens` — `color` (hex + alpha), `space`, `radius`, `shadow`, and `typeScale` derived from rendered text
- `nodes` — flat list, `parent` references; `bbox` in design px; `style` (fill, gradient, radius, border, parsed shadows, opacity, backdrop filter); `layout` (flex/grid, gap, padding); `state`; `model` for repeated items
- `text` — every visible text run: string after `text-transform`, bbox, first baseline, line count, color, font (family, px, weight, line height, letter spacing); `<input>`/`<select>`/`<textarea>` values and placeholders are runs too (`field`)
- `icons` — `match` (`lucide:gauge`, `tabler-filled:moon`, `fa:industry`), bbox, color, stroke width or glyph code point
- `colorsUsed` — every distinct color with usage count
- `data` — chart and list data behind the visuals

All coordinates are CSS px at 1× (design px). Multiply by `meta.dpr` to get `input.png` pixels.

## Rebuilding

Requirements: `pip install -r requirements-dev.txt` and `python -m playwright install chromium`.

```bash
cd evals/tools
python build_case.py                 # rebuild all cases (deterministic: identical PNGs)
python build_case.py --only 05       # rebuild one case
python expectations.py               # rewrite expected.json / thresholds.json
```

Adding a design: copy a template in `tools/designs/`, set `case-meta` (id, viewport, dpr, fonts),
declare tokens as `--color-* / --space-* / --radius-* / --shadow-*` on `:root`, mark semantic
elements with `data-node` (+ `data-role`, `data-state`, `data-model`, `data-value`), and use
`<i data-icon="set:name"></i>` for icons. New icons need `--pkg <dir with extracted npm packages>`
the first time (lucide-static, @tabler/icons, @fortawesome/fontawesome-free); they are then cached
in `assets/icons/`.

Fonts: `tools/build_fonts.py [--only "Onest,Sora"]` instances variable fonts from google/fonts
into static TTFs with clean family names, so Chromium and Qt rasterize the same outlines.
Families with an OFL Reserved Font Name are not instanced: Barlow, Rajdhani, Titillium Web,
Be Vietnam Pro, DM Mono and IBM Plex Mono are copied from their upstream static files.

Extraction (`tools/extract.js`) also reads `:root` custom properties inside `@layer`/`@media`
blocks (Tailwind v4's `@theme`) and converts `oklch()`/`lab()` colors to sRGB. Design 18 is
written with Tailwind v4 utilities; after editing its markup, recompile its CSS with
`tools/tailwind/build.py` (Node 18+, `npm install` there first). `_charts.js` names its SVG
gradients `g1`, `g2` …: do not give your own SVGs those ids.

## Scoring

```bash
python evals/run_evals.py runs/<label> [--jobs 2]   # scores runs/<label>/<case-id>/project for every case
```

For each case it runs `skills/screenshot-to-qml/scripts/check.py` with the case's
`golden-spec.json` and `thresholds.json` and writes `runs/<label>/results.{json,md}`.
The golden spec (not the agent's own spec) is used for scoring, so every run is measured the
same way. `expected.json` is graded separately (human or model reviewer).

## Analysis accuracy

```bash
python evals/score_analysis.py [--cases 01,03] [--verbose]      # writes evals/analysis-results.{json,md}
```

Runs `palette.py`, `geometry.py` and `text_ocr.py` on each `input.png` and compares with the
golden spec: palette recall (solid colors within ΔE 2), surface recall (solid-fill nodes matched
with IoU ≥ 0.85) and box error, OCR exact-string rate, character error rate and font-size error.

## Matching accuracy

```bash
python evals/score_matching.py [--cases 01,03] [--only fonts,icons,shadows,gradients] [--verbose]
python evals/synthetic_matching.py [--only fonts,outside,shadows,gradients] [--keep DIR] [--verbose]
```

`score_matching.py` runs the v0.6 matchers on each `input.png` with the golden geometry but
without the answers (fonts, icon names, shadows and gradients are stripped first) and writes
`matching-results.{json,md}`:

- fonts: family per run against all 63 catalog families, weight within ±100, size error;
- icons: top-1 / top-3 over all 11,869 indexed icons (an identical drawing under another
  name, such as Lucide `home`/`house`, counts as right);
- shadows: every painted surface is fitted (scene mode); on the surfaces with a CSS shadow,
  detection and the error of the dominant layer; on the others, false alarms;
- gradients: angle error and end-stop ΔE on opaque gradients; false gradients on opaque solid
  surfaces; translucent glass surfaces reported separately.

The matchers' constants were tuned on cases 01–08 (v0.6), before cases 09–20 existed, so
09–19 are unseen screens; case 20's font is outside the catalog on purpose. `synthetic_matching.py`
checks generalisation on images nothing was tuned on: 17 catalog families that no case uses (one
sheet each, dpr 1 or 2), 12 open families outside the catalog (the `outsideCatalog` flag), 24
cards with random shadows on flat or graded backgrounds, and 24 random 2- and 3-stop gradients
(any angle, some with a label inside). It writes `synthetic-results.{json,md}`.

Latest (2026-10-18, all 20 cases):

| Case | Font family (runs) | Weight ±100 | Icon top-1 / top-3 | Shadows found · false | Shadow blur / y error (found) | Gradient angle / end ΔE |
| --- | --- | --- | --- | --- | --- | --- |
| 01-hmi-dolum | 90% (40) | 100% | 86% / 95% | — | — | —° / — |
| 02-kiosk-kafe | 100% (32) | 88% | 96% / 96% | 3/5 · 0/15 | 1.8 / 0.1 px | 0.1° / 0.0 |
| 03-dashboard-dark | 78% (40) | 100% | 100% / 100% | 1/1 · 0/15 | 0.7 / 0.2 px | —° / — |
| 04-dashboard-light | 100% (32) | 84% | 87% / 93% | 5/5 · 0/8 | 3.7 / 1.3 px | 0.0° / 0.0 |
| 05-settings-form | 100% (30) | 100% | 76% / 82% | 6/7 · 0/12 | 1.5 / 0.1 px | —° / — |
| 06-mobile-aliskanlik | 100% (30) | 97% | 94% / 94% | 10/10 · 0/11 | 1.0 / 0.2 px | 0.0° / 0.5 |
| 07-data-table | 100% (40) | 100% | 85% / 95% | 2/3 · 0/12 | 1.7 / 0.4 px | —° / — |
| 08-glass-home | 100% (25) | 100% | 90% / 90% | 4/13 · 0/5 | 3.7 / 3.0 px | 1.8° / 1.9 |
| 09-dashboard-sales | 100% (40) | 100% | 89% / 89% | 10/11 · 0/25 | 0.9 / 0.2 px | 0.0° / 0.0 |
| 10-dashboard-ops-dark | 100% (40) | 98% | 86% / 93% | — | — | —° / — |
| 11-hmi-boiler | 100% (40) | 92% | 100% / 100% | — | — | —° / — |
| 12-ev-charger | 100% (34) | 65% | 67% / 67% | — | — | 0.0° / 0.0 |
| 13-form-wizard | 100% (33) | 97% | 95% / 100% | 8/10 · 3/17 | 0.1 / 0.3 px | —° / — |
| 14-form-login-dark | 70% (30) | 95% | 100% / 100% | 2/2 · 0/7 | 8.7 / 3.6 px | —° / — |
| 15-mobile-wallet | 100% (37) | 86% | 100% / 100% | 6/7 · 1/4 | 1.6 / 0.1 px | 0.0° / 3.7 |
| 16-mobile-chat | 100% (25) | 88% | 93% / 100% | 0/1 · 0/51 | — | —° / — |
| 17-data-table-stock | 68% (40) | 100% | 95% / 100% | 2/3 · 1/52 | 0.7 / 0.2 px | —° / — |
| 18-html-tailwind-billing | 100% (40) | 100% | 97% / 97% | 4/11 · 1/18 | 1.9 / 0.3 px | —° / — |
| 19-html-css-board | 80% (30) | 100% | 98% / 98% | 14/34 · 4/43 | 0.8 / 0.5 px | —° / — |
| 20-hard-weather | 0% (40) | — | 100% / 100% | 5/6 · 0/22 | 12.9 / 7.4 px | 7.3° / 35.5 |
| **pooled** | **88%** | 94% | **93%** / 95% | 82/129 · 10/317 | 1.4 / 0.3 px (median) | 0.9° / 3.8 |

Shadows: found = surfaces with a CSS shadow where the fit reports `hasShadow`; false = surfaces without one where it does. Errors are for the dominant layer on the found ones. Gradients: 12/14 opaque gradients accepted, 4/133 solid surfaces called gradients, 9/30 translucent glass surfaces read as gradients (a static stand-in for the blurred backdrop).

Tuned on vs unseen:

| Cases | Fonts (runs) | Weight ±100 | Icons top-1 / top-3 | Shadows found · false | Shadow blur (median) | Gradients accepted · false |
| --- | --- | --- | --- | --- | --- | --- |
| 01–08 (tuned on) | 95.2% (269) | 96.1% | 89.5% / 93.9% | 31/44 · 0/78 | 1.8 px | 7/8 · 0/49 |
| 09–19 (unseen) | 92.8% (389) | 92.8% | 94.4% / 96.1% | 46/79 · 10/217 | 0.9 px | 4/5 · 0/73 |
| 20 (font outside the catalog) | 0% (40), flagged | — | 100% / 100% | 5/6 · 0/22 | 12.9 px | 1/1 · 4/11 |

Case 20 is a font the catalog does not have, so every run names the nearest catalog face and
the screen is flagged `outsideCatalog` instead; its frosted, graded backdrop is also where the
four false gradients and the large shadow errors come from.

Unseen images:

| Test | Items | Result |
| --- | --- | --- |
| Fonts, hold-out families | 17 sheets / 170 runs | screen family 94%, run family 95%, weight ±100 100%, size error 0.71 px; flagged outside the catalog by mistake: 0/17 |
| Fonts outside the catalog | 12 sheets | flagged `outsideCatalog` 7/12 |
| Shadows, isolated card | 24 | detected 100%; mean error y 0.1 px, blur 1.1 px, spread 0.6 px, alpha 0.019 (90th pct: y 0.2, blur 2.3) |
| Gradients | 24 | angle error 0.04° (90th pct 0.1°), end ΔE 0.15 (90th pct 0.5), stop count 96% |

## Running agents (any agent, any model)

0. The machine: Ubuntu 24.04 (on Windows, a WSL2 Ubuntu). `bash evals/agents/setup_ubuntu.sh`
   installs what the agents had in the 2026-10-18 run (the skill's Python requirements in
   `~/s2q-venv`, Xvfb, tesseract, Playwright with Chromium, Node, the skill's font and icon
   caches, the Codex CLI) and runs the test suite as a check. Log the agent in once
   (`codex login`).
1. Prepare one folder per case with only what the agent may see, and the task:

   ```bash
   python evals/prepare_run.py runs/baseline                           # no skill
   python evals/prepare_run.py runs/skill-v1.0 --skill skills/screenshot-to-qml
   ```

   Each `runs/<label>/<case-id>/` gets `input.png` (or `source/` for HTML-input cases) and
   `PROMPT.md`. The prompt is the same for every agent:

   > Rebuild this screen (`input.png`) as a native PySide6 Qt Quick project in `./project`.
   > Screenshot DPR: {dpr}. Target: {profile}. Use a `Window` root in `qml/App/Main.qml`
   > (module `App`) and bundle fonts in `project/assets/fonts`.

   plus: work alone (assumptions go in the README), stay in this folder, the environment
   (headless Linux, `xvfb-run`, PySide6 6.8+, Playwright), and for the skill arm one line
   pointing at the skill copy. `--skill` copies the skill into `runs/<label>/_skill/`, and case
   01 gets a copy without `examples/hmi-dolum` (that example is the answer to case 01). For an
   agent on another machine, `--portable` points the prompt at the skill with a relative path,
   and `--os windows` swaps the environment line for a Windows one (the agent installs what is
   missing).
2. Run the agent on every folder, one fresh session per case:

   ```bash
   python evals/run_agent.py runs/skill-v1.0 --agent codex            # Codex CLI
   python evals/run_agent.py runs/skill-v1.0 --agent claude           # Claude Code
   python evals/run_agent.py runs/skill-v1.0 --cmd 'gemini -p "$(cat {prompt_file})" --yolo'
   python evals/run_agent.py runs/skill-v1.0 --status                 # progress and tokens
   ```

   A usage limit or crash stops the loop; run the same command again later. Finished cases
   are skipped, and the unfinished one restarts as a new session told to continue from the
   files already in its folder. Logs, prompts and token counts go to `<case>/.agent/`. Codex
   runs with `--sandbox danger-full-access` by default, because the skill renders under Xvfb,
   writes its caches under `~/.cache` and fetches fonts from GitHub: use a machine or WSL
   distribution meant for this.
3. Score and compare:

   ```bash
   python evals/run_evals.py runs/skill-v1.0 --jobs 2
   python evals/compare_runs.py runs/baseline runs/skill-v1.0 --labels baseline "skill v1.0"
   ```
4. A skill change ships only if it does not lower any case's global SSIM by more than 0.005
   and does not add gate errors.

## Results

| Run | What | Folder |
| --- | --- | --- |
| 2026-10-18 | v1.0 exit run: 20 cases, skill v1.0 with opus (20), sonnet (4), haiku (3); baseline 01–08 re-scored | [`results/2026-10-18-v1.0`](results/2026-10-18-v1.0/README.md) |
| 2026-09-29 | baseline, skill v0.4 and skill v0.5 under the v0.5 gates | [`results/2026-09-29-v0.5`](results/2026-09-29-v0.5/README.md) |
| 2026-09-27 | baseline vs skill v0.4; thresholds calibrated from it | [`results/2026-09-27`](results/2026-09-27/README.md) |

Latest: skill v1.0 with `claude-opus-5-5`, all 20 cases, one build each:

| Criterion | Result |
| --- | --- |
| Global SSIM ≥ 0.95 (plan) / ≥ 0.98 (calibrated) | 20/20 / 20/20 (min 0.9873, mean 0.9949) |
| Region SSIM ≥ 0.90 (each region aligned within 1 px) | 18/20 |
| ΔE2000 ≤ 2 on solid fills | 19/19 measured (max 1.13; 08 has no opaque fill) |
| Position/size ≤ 2 px | 18/20 |
| Runtime QML warnings 0 · lint clean | 20/20 · 19/20 |
| All plan criteria | 16/20 |
| Full pass with the calibrated thresholds + 13 gates | 12/20 |
| Controls reachable with Tab, focus visible · MouseArea buttons | 337/337 · 0 |
| Codex CLI (05, 09, 12, 18), two runs: all gates · plan criteria | 4/4 · 1/4 both times |

On cases 05, 12 and 18, built by all three models, every project passes all gates. Opus and
sonnet have the same visual scores; haiku stays above SSIM 0.987 but leaves more text 2–4 px
off (0/3 full passes). The baseline (no skill, cases 01–08) passes the visual checks more often (6/8 against
4/8) but no gate set: 46 `MouseArea` buttons, 48 runtime warnings, 239 hard-coded values.

## Licenses

Designs, data and tooling are original to this repo and ship under the skill's license. Fonts: SIL OFL 1.1 (`assets/licenses/OFL-*.txt`).
Font Awesome Free: fonts OFL 1.1, icons CC BY 4.0. Lucide: ISC. Tabler Icons: MIT.
