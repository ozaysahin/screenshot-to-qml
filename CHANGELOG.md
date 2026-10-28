# Changelog

All notable changes to this project. Versions follow the roadmap in README.md.

## [1.1.0] — 2026-10-28

Qt 5.15 and automotive. Many instrument clusters, head units and industrial panels still ship
Qt 5.15 LTS, so the skill now targets it end to end, with a car instrument cluster as the new
reference example.

### Added
- **Qt 5.15 target** (`meta.minQt: "5.15"`, `scaffold.py --min-qt 5.15`): the kit and the
  generated Theme in the Qt 5.15 dialect (versioned imports, no `ComponentBehavior` pragma, no
  Qt 6-only types or properties) and a Qt 5 C++ host (CMake, `find_package(Qt5)`, one embedded
  resource, qmlcachegen when Qt5QuickCompiler is installed). `references/target-qt5.md` maps
  every Qt 6 construct the skill uses to its 5.15 form.
- `qt5.py`: `check` lists everything Qt 5.15 cannot load (MultiEffect, VectorImage,
  RectangularShadow, per-corner radius, stretch factors, versionless imports, value-type lists,
  `??=` …) with the replacement; `port` rewrites a Qt 6 tree's imports, pragmas, qmldirs and
  rendering hints (a Shape's curve renderer becomes a 4-sample layer).
- `SvgIcon` (Qt 5.15 kit): Theme-colored SVG icons with `Image` + `ColorOverlay`.
- Verification of Qt 5.15 projects: the check loop renders them with PySide6 through
  `assets/qt5-shim` (`QtGraphicalEffects` → Qt 6's `Qt5Compat`); the `lint` gate applies the
  5.15 rules and lints a copy with the Bound pragma added; the `cpp` gate builds the host
  against Qt 5.15, runs it and compares its frame by blurred 32-px tiles, since Qt 5 lays text
  out up to ~1–2 px differently from Qt 6.
- `examples/auto-cluster`: a 1920×720 car instrument cluster rebuilt for Qt 5.15 with the C++
  host — a reusable `Dial` (one Shape, ticks and labels generated from the scale, a needle
  bound to `value`), telltales from a model, navigation, trip and media cards. Global SSIM
  0.999, 61/61 strings, geometry ≤ 1.1 px, all 13 gates; the Qt 5.15.13 binary runs without QML
  warnings and matches the reference render.
- Eval case `21-auto-cluster` (category `automotive`, `minQt` 5.15, target `cpp`);
  `prepare_run.py` asks for a Qt 5.15 C++ project for it.
- `docs/img/demo.gif` (`docs/tools/demo_gif.py`): the cluster screenshot wiping into the running
  app, whose dials are then driven through `MockData`.
- CI job `qt5-host`: Ubuntu's Qt 5.15 builds and runs the cluster's host; the full check runs
  with it.

### Changed
- `deploy.py`: Qt 5.15 projects get an `install.sh` that builds with the board's Qt 5.15, and a
  desktop bundle runs `windeployqt` / `macdeployqt --qmldir qml` when the SDK has them.
- The design-spec schema accepts `minQt` `5.15`.

### Fixed
- `build_cpp.py` dropped the grab when `cv2` had been imported in the same process (opencv-python
  points `QT_QPA_PLATFORM_PLUGIN_PATH` at its own Qt); the variable is now removed for the
  binary's run.

## [1.0.1] — 2026-10-20

Token diet. The build transcripts of the v1.0 eval showed where the cost was: about 200 model
turns per screen, 63 % of the tool calls before the first check, mostly ad hoc Python to read pixels and
JSON and about 20 image crops opened one by one. Each call re-sends the whole conversation, so
the number of calls is what made a screen expensive.

### Added
- **Work budget** in SKILL.md: `quick` / `standard` / `full` effort with call and check-run
  limits, and rules: read summaries not raw files, no ad hoc pixel or JSON scripts, few images,
  whole-file writes, stop at the budget and report what is left. `analyze.py` suggests the
  effort from the screen's size.
- `sheet.py`: contact sheets. `check.py` writes `worst.png` after a failed diff (source and
  render crops of the worst items side by side, labelled with what failed); `analyze.py`
  writes `ocr_sheet.png` (every text run's crop with its id), so all strings are checked in
  one look.
- `spec_view.py`: a design-spec as a compact table (about a quarter of the JSON's size), with
  `--verify` and `--ids` filters.

### Changed
- `probe.py region` and `edges` take several boxes per call; output is compact JSON, and
  `edges` keeps the first and last 4 runs (`--all` for every run).
- `gen_theme.py` and SKILL.md say how measured control sizes override the assumed roles
  (`tokens.size`), and SKILL.md gives the icon export command; both used to cost agents
  several calls reading source code.

### Fixed
- `diff.py` compared an OCR'd ink box with Qt's line box by their centers when the spec had no
  baseline, so every string with a descender (y, g, p, ş …) read as 2–3 px off. It now
  estimates the ink box's baseline from the string's deepest descender. Agents had been
  spending check rounds on this false alarm.

### Results (case 05, a settings form, claude-opus-5-5)
| | v1.0 (6 builds) | v1.0.1, first run | v1.0.1, final |
| --- | --- | --- | --- |
| Tool calls | 82–151 | 79 | 61 |
| Tokens processed (cumulative context) | 32–61 M, median ~45 M | 23.7 M | 14.7 M |
| Images opened | 11–35 | 5 | 5 |
| Golden-spec result | pass | pass (SSIM 0.9946) | fail: one button 3 px wide, stopped at the 2-check limit |

The final run's miss was a fix the agent had already named when the budget stopped it, so the
quick budget now allows 3 check runs and asks to spend the last one on exactly named fixes.

## [1.0.0] — 2026-10-18

### Added
- **Eval set: 20 cases** (12 new, all original and fictional, Turkish UI). The new ones are:
  - a DPR 1.5 sales dashboard;
  - a 1080p network-operations wall (gauges, a 7×24 heatmap, a monospace log);
  - an ISA-101 boiler HMI (embedded-gpu);
  - a 7" EV charger on the software renderer (embedded-sw);
  - a wizard with an open date picker;
  - a dark login;
  - two phone screens (DPR 3 and 2);
  - a dense stock table (frozen column, groups, inline edit);
  - **two HTML-input cases**: Tailwind v4, and hand-written CSS with real form elements;
  - a **hard case whose font is not in the skill's catalog**.

  Together they cover every category in the plan: dashboard 4, HMI/kiosk 4, form 3, mobile 3,
  table 2, HTML 2, hard 2.
- **`html_to_spec.py` + `html_extract.js`** (HTML input path). The page is rendered in Chromium
  at the design size and DPR, giving a reference `input.png` and a design-spec with every value
  `src: "truth"`:
  - tokens from `:root` custom properties, including Tailwind v4's `@theme` inside `@layer`,
    with oklch/lab converted to sRGB;
  - nodes for painted boxes, controls, landmarks, and repeated children as models;
  - text runs with baselines, plus form-field values and placeholders;
  - inline SVG icons saved as files, and the page's `@font-face` files copied.

  With the same Chromium build, its render is pixel-identical to the eval's ground truth.
- **Fonts outside the catalog are flagged.** `font_match` reports each family's `agreement`
  (how its runs compare with their best alternative) and `outsideCatalog` when the voted face
  loses on the median run by more than 0.08. Results:
  - no false alarms on 36 catalog screens (19 eval cases + 17 hold-out sheets);
  - catches 7 of 12 open faces outside the catalog, and the eval's hard case;
  - the five it misses have a near twin in the catalog.

  The 0.08 threshold was chosen on these same sheets, so treat 7 of 12 as an in-sample number.

  `match.py` surfaces the flag. `typography.md` has the steps: ask for the font, or fit sizes
  to the screenshot and name the substitute. `font_match.py fetch/match --families` accepts
  any google/fonts family, and `font_match.py bundle` writes its static TTFs.
- **Gradient text** recipe (`effects.md`: MultiEffect mask over a gradient, software fallback).
- **Eval harness for any agent**:
  - `evals/prepare_run.py` writes per-case input folders and one `PROMPT.md` for Claude Code,
    Codex CLI, Gemini CLI or any other agent;
  - `evals/run_agent.py` runs Codex CLI, Claude Code or any command on every case folder: one
    session per case, logs and token counts in `<case>/.agent/`, stops at a usage limit and
    continues the unfinished case on the next run;
  - `evals/agents/setup_ubuntu.sh` sets up an Ubuntu 24.04 / WSL2 machine like the run's;
  - `run_evals.py --jobs` scores in parallel;
  - `evals/tools/tailwind/` rebuilds the Tailwind case;
  - `docs/tools/evals_image.py` draws the case sheet.
- **Claude Code plugin marketplace** (`.claude-plugin/marketplace.json`): `/plugin marketplace add
  ozaysahin/screenshot-to-qml`, then `/plugin install screenshot-to-qml@screenshot-to-qml`.
- README rewritten: install per agent, usage, results, platform support, limitations.
- `synthetic_matching.py --only outside`: open faces outside the catalog, to check the flag.

### Results
- **Skill v1.0, opus, all 20 cases**, against the plan's success criteria:
  - global SSIM ≥ 0.95: 20/20 (min 0.987);
  - region ≥ 0.90 (each region aligned within 1 px): 18/20;
  - ΔE ≤ 2: 19/19 measured (08 has no opaque fill);
  - geometry ≤ 2 px: 18/20;
  - zero runtime warnings: 20/20;
  - lint clean: 19/20;
  - all criteria at once: **16/20**.

  With the stricter calibrated thresholds and all 13 gates, 12/20 pass outright. 337/337
  controls are keyboard-reachable with visible focus. Both HTML cases pass at SSIM 0.998/0.999.
- **Multi-model:** on three shared cases every sonnet and haiku project passes all gates.
  Sonnet matches opus visually; haiku scores SSIM ≥ 0.987 but leaves more text 2–4 px off.
- **Baseline (no skill, cases 01–08), re-scored:** 0/8 full passes against 4/8 with the skill,
  with 46 `MouseArea` buttons, 48 runtime warnings and 239 hard-coded values. On pixels alone
  the baseline passes the visual checks in 6/8 against the skill's 4/8.
- **Codex CLI** (`gpt-6-astra`, medium; cases 05, 09, 12, 18, on Windows; two runs, the second
  with OCR and the caches fetched first): all gates pass in 4/4 with every control
  keyboard-reachable; plan criteria 1/4 (the HTML case) both times. The screenshot cases miss
  on fonts and text position; the machine's font catalog was most likely incomplete.
- Not done: Codex on more cases with a verified font catalog,
  and baselines for the 12 new cases.

### Fixed
- `render.py` reads `TextArea`/`TextEdit` content (line by line from the text document, plain
  or rich text). Before, multi-line text areas counted as missing text.
- `render.py`, interaction probe: a control that calls `Qt.quit()` or closes the window when
  pressed no longer ends the probe or crashes the check (quit and close are held off while it
  runs; the window wrapper is re-fetched after the scene walk). A probe that still fails is an
  `a11y` error.
- `render.py` places `TextEdit` lines with the item's vertical alignment.
- `shadow_fit.py`, `gradient_fit.py`: nodes with per-corner radii no longer crash the fitter.
- Windows: `icon_match.py fetch` finds `npm.cmd`; SKILL.md's setup says to set `PYTHONUTF8=1`.
- PySide6 6.12: the `lint` gate passes absolute paths to qmllint (6.12 misses a file's own qmldir
  singleton entry for relative paths), and the HMI example no longer has an id that shadows
  `Item.scale` (a new 6.12 warning).
- `font_match.py fetch` retries rate-limited and failed downloads, says when the catalog stays
  incomplete and why (it used to report a refused download as "not found"), and downloads
  families in parallel.
- `check.py` renders again with `render.py --no-idle-scan` when the scan for idle animations
  crashes PySide (seen on one Codex-built project); the perf gate warns that it was skipped.
- `diff.py`, fill colors: measured on the pixels showing the node's dominant color, so a
  status dot or `::before` knob that is not a node no longer counts as fill (up to ΔE 18 for
  identical fills before).
- `diff.py`, text runs:
  - a run that wraps from mid-line onto the next line matches across the break;
  - separators drawn as shapes are matched on the uncut edge;
  - vertical or rotated labels are compared by box centers.
- Eval builder:
  - rem and `calc(infinity*1px)` radii no longer crash it;
  - transparent placeholder shadow layers are dropped;
  - input, select and textarea text is recorded;
  - `style=""` left by the screenshot step is stripped;
  - HTML-input cases get a self-contained `source/` with their fonts.

### Changed
- SKILL.md: an HTML-input intake row and step; the `fonts.outsideCatalog` step; `–` in ranges
  added to the characters OCR confuses (two eval misses were en dashes typed as hyphens);
  `metadata.version: 1.0.0`.
- `css-to-qml.md` rewritten around `html_to_spec.py`:
  - what the extraction cannot see (`::before`, other states);
  - Tailwind v4 oklch palette and `in oklab` gradients;
  - transparent ring and shadow slots.
- The eval rubric for case 02 no longer suggests `RectangularShadow` on a Qt 6.8 floor.
- Analysis and matcher accuracy re-measured on all 20 cases, split into the cases they were
  tuned on (01–08) and unseen ones (09–20); SKILL.md and `analysis.md` quote the 20-case
  numbers (see `README.md`, Evaluation).

## [0.7.0] — 2026-09-29

### Added
- **C++ host** (`assets/templates/cpp`): `CMakeLists.txt` (Qt 6.8+), `src/main.cpp` and
  `cmake/S2qQml.cmake`. Every `qml/**/qmldir` folder becomes a static QML module + plugin
  (`qt_add_qml_module`, URI and singletons read from the qmldir, local imports as
  dependencies), so QML is compiled ahead of time. `assets/`, `i18n/*.qm` and `mock/` are
  embedded under `:/qt/` with the project's layout, so relative URLs resolve as in PySide6.
  `main.cpp` mirrors `main.py`: embedded fonts, translation (`APP_LANG`), `App`/`Main`, exit 1
  on load errors, software scene graph for `embedded-sw`.
- **One QML tree, two hosts**: the template is split into `project/` (shared) and `pyside6/`,
  `cpp/` hosts. `scaffold.py --target pyside6|cpp|both --profile …`, and `--add-host` adds a
  host to an existing project. Both examples now carry both hosts.
- **Frame grab in both hosts** (`APP_GRAB`, `APP_GRAB_SIZE`, `APP_GRAB_WAIT_MS`), so builds and
  packages can be diffed like the project.
- **`build_cpp.py`**: configure (Ninja when available), build (warnings counted), run and grab
  under Xvfb, SSIM against the PySide6 render, `--install`. `check.py` runs it for projects
  with a `CMakeLists.txt` (`--qt`, `--no-cpp`).
- **Gates `effects`, `perf`, `cpp`** (13 in all):
  - `effects`: shader effects are errors on `embedded-sw`; blur and many layers are warnings on
    `embedded-gpu`; Qt5Compat effects are warnings on desktop;
  - `perf`, from the render's new `perf` block: oversized decoded images (errors on embedded
    profiles), infinite animations and fast timers running while idle, layers, item count,
    time to first frame;
  - `cpp`: build or run failures, QML warnings in the C++ run, and parity with the PySide6 render.
- **`render.py --scenegraph software`**; `check.py` uses it for `embedded-sw`, so the diff scores
  what a GPU-less board draws. `scene.json` gains `perf`.
- **`deploy.py`**:
  - desktop: a `pysidedeploy.spec` for pyside6-deploy (Nuitka). It ships `qml/`, `assets/`,
    `i18n/` and `mock/` as data, and excludes the heavy QML modules the UI never imports;
  - desktop C++: `cmake --install`, which bundles Qt when it comes from an SDK;
  - device: `app.env` (eglfs with `eglfs_kms` or Jetson's `eglfs_kms_egldevice`, or linuxfb with
    the software scene graph), `kms.json`, a systemd kiosk unit and `install.sh` (a venv +
    pip, or a native CMake build against the board's Qt).
- References: `target-cpp.md` rewritten (the host is generated now), `deploy.md` (new),
  `embedded.md` (profiles enforced by gates; which host fits which board OS: PySide6 aarch64
  wheels need glibc 2.39+).
- CI job `cpp-host`: Qt 6.8.3 from install-qt-action. It builds both examples, runs check.py with
  the `cpp` gate, and bundles with `cmake --install`. The bundle's frame is compared with the
  render. `tests/test_targets.py`: scaffold, gates, deploy files, and a C++ build of the gallery
  when a Qt 6.8+ SDK is present.

### Results
- Both examples build as C++ against Qt 6.8.3 without warnings. Their frames equal the
  PySide6 6.11 renders (SSIM 1.000), and the gallery also matches in Turkish from the embedded
  translation. All 13 gates pass.
- The HMI example's pyside6-deploy standalone build (Nuitka) starts and draws the same frame
  as the render (SSIM 1.000). Its device install, simulated in a Qt 6.8 root filesystem,
  builds and runs with the software scene graph.
- On the glassmorphism eval build, the `embedded-sw` profile flags 9 shader effects the
  software scene graph would drop (global SSIM 0.986 with the software render).

### Changed
- The template moved to `assets/templates/project` (shared) + `pyside6/` and `cpp/` hosts.
- The effects rules that lived only in `embedded.md` are now gates.
- Gate `lint` also fails QML types newer than the project's minimum Qt (`meta.minQt`, default
  6.8; `RectangularShadow` needs 6.9). Seven of the eight v0.5 eval builds used it and would not
  load on a Qt 6.8 board. effects.md now leads with the `MultiEffect` shadow for 6.8, with a
  `blurMax` table measured with `shadow_fit.py`.
- The examples' `main.py` files follow the current template (translation loading, profile
  default, `APP_GRAB`).
- File and target names are transliterated (`Hat 3 Dolum Çay` → `hat-3-dolum-cay`), not stripped.
- `.gitignore`: `build/`.

## [0.6.0] — 2026-09-29

### Added
- **`match.py`**: fills a corrected spec with measured fonts, icons, shadows and gradients
  (`src: "measured"`), keeps existing values unless `--overwrite`, and writes
  `*.match-report.json` with scores, alternatives and the entries to confirm by eye.
  `--fonts-dir` writes static TTFs of the matched weights plus the license.
- **Font matching** (`font_match.py`, `fontlib.py`, `assets/catalog/fonts.json`): 63 open UI
  families (52 sans, 11 mono) fetched from google/fonts into a cache. Each text run is
  rendered in every family at its weights (variable axes set like CSS, `opsz` = px), scaled
  to the run's ink height and scored on shape, width and ink mass. Runs vote for the screen's
  families (a sans plus a monospace family when numeric runs want one).
  `fontlib.bundle()` instances variable fonts per weight with Qt-friendly names and copies
  families with a Reserved Font Name unmodified.
- **Icon matching** (`icon_match.py`, `assets/catalog/icons.json`): Lucide, Tabler (outline,
  filled), Font Awesome (solid, regular, brands) and Heroicons (outline, solid), 11,869 icons
  fetched with `npm pack` and indexed at 32×32. A coarse pass over the index, then the best 40
  are re-rendered at the box size and 7 stroke widths; the screen's dominant sets break ties.
  `export` writes the SVG with the matched stroke and color.
- **Shadow fitting** (`shadow_fit.py`): CSS `box-shadow` from the ring of pixels around a
  surface. Gaussian-blurred box (closed-form erf for rectangles, rasterised for circles and
  pills) + a quadratic background per surface underneath, with the color term solved in
  closed form; bounded Nelder–Mead over x, y, blur, spread with a weak prior; outlier trimming.
  Scene mode fits every painted node, fits equal-sized siblings as one shared shadow, and
  back-fits twice with the neighbours' shadows subtracted. Reports `hasShadow` and `atBound`.
- **Gradient fitting** (`gradient_fit.py`): CSS `linear-gradient` angle and 2–4 stops. Angle
  from the direction of steepest color change (plus an angle scan for multi-stop gradients),
  colors piecewise-linear along the CSS gradient line, consensus fitting that ignores
  undeclared content (a switch knob, decorative circles), and checks that reject shape edges
  posing as stops. Reports the angle in (0°, 180°] and Qt hints (`Gradient.Vertical` /
  `Horizontal`, or `LinearGradient` x1 y1 x2 y2).
- `evals/score_matching.py` scores the four matchers against the golden specs →
  `evals/matching-results.{json,md}`; `evals/synthetic_matching.py` runs controlled and
  hold-out tests rendered by Chromium → `evals/synthetic-results.{json,md}`.
- `tests/test_matching.py`: gradients, shadows and match.py on synthetic images; font and icon
  tests run when their caches exist.

### Results
- Eval cases (`evals/matching-results.md`): font family 95 % of runs, weight ±100 96 %;
  icon top-1 90 %, top-3 94 %; shadows found on 31 of 44 surfaces with no false alarm on 78
  (median error blur 1.8 px, y 0.25 px); gradients 0.7° and ΔE 0.9, no solid fill misread.
- Unseen images (`evals/synthetic-results.md`): 17 font families outside the eval set 95 % of
  runs and 16 of 17 screens; isolated shadows blur 1.1 px, y 0.1 px; random gradients 0.04°,
  ΔE 0.15.
- Plan targets met: font family ≥ 70 %, icon top-1 ≥ 80 %.

### Changed
- analysis.md, typography.md, icons-vectors.md, effects.md and SKILL.md start from the matchers
  and keep the by-eye methods for checking and for what the matchers cannot do.
- Requirements: `scipy`, `Pillow`, `fonttools` (and `threadpoolctl`, optional: the fitters run
  with single-threaded BLAS, 7× faster on busy machines).

## [0.5.0] — 2026-09-29

### Added
- **Control kit** in the PySide6 template (`qml/App/Controls`, 14 controls on
  `QtQuick.Templates`):
  - controls: Button (primary / secondary / ghost / danger, glyph, compact), IconButton,
    TextField (error, glyph), CheckBox (tristate), RadioButton, Switch, Slider (centered
    handle), ComboBox (with popup), SpinBox, SegmentedControl, TabBar + TabButton,
    ProgressBar, ToolTip, and a shared FocusRing;
  - hover, pressed, keyboard focus, checked, error and disabled states;
  - Theme roles only, lint/format/literal clean.
- `scaffold.py --controls Button,TextField,…` keeps only the controls a screen needs.
- **Control roles in `gen_theme.py`**: the Theme always ends with the contract the kit reads
  (`accentHover`, `accentPressed`, `surfaceHover`, `surfacePressed`, `danger*`, `focusRing`,
  `track`, `knob`, control sizes, `fontControl`, `fontInput`, `fontIcon`). Each role is taken
  from the spec, aliased to a synonym (`accent: primary`), derived (`Qt.darker/lighter/tint`,
  depending on light or dark UI), or assumed and marked. Touch profiles get 48 px controls.
- **`render.py --interact`** (`interact.py`) drives the rendered window:
  - Tab until focus cycles: which controls are reached, and whether focus visibly changes them;
  - pointer hover and press on every enabled control (drag-off release, so no clicks fire);
  - accessible names and roles;
  - `MouseArea`s that act as buttons.

  The results go to `interaction.json`.
- **Gates `a11y`, `states`, `i18n`** in `quality_gate.py` (check.py runs them):
  - `a11y`: Tab reach, visible focus, accessible names, `MouseArea` buttons, touch targets on
    embedded profiles;
  - `states`: visible pressed state, and hover on desktop;
  - `i18n`: `qsTr()` on visible strings; mock data and `ListElement`s are exempt.
- **Translations:** the template's `main.py` loads `i18n/app_<locale>.qm` (`APP_LANG`
  override); `render.py --lang xx` renders a translated layout.
- `examples/controls-gallery`: every control in its states, English UI plus a Turkish
  translation, all ten gates clean; `docs/img/controls.png` and the script that builds it.
- `evals/compare_runs.py` compares any number of run sets and reports keyboard and
  accessibility counts.
- Eval: skill v0.5 builds of the 8 cases, in `evals/results/2026-09-29-v0.5/`:
  - all gates pass in 8/8, full pass in 5/8 (v0.4: 0/8 under the same gates);
  - 161/161 controls keyboard-reachable with visible focus;
  - 0 `MouseArea` buttons, 0 unwrapped strings, 0 missing pressed states.

### Changed
- `references/controls.md` is rewritten around the kit (token contract, restyling rules,
  what the gates check); `a11y-i18n.md`, `tokens-theming.md`, `verification.md` and
  `SKILL.md` are updated.
- The reference HMI example is fixed for the new gates: its outline button got a focus ring
  and its segment buttons got pressed colors.

## [0.4.1] — 2026-09-27

### Added
- Baseline run: 8 cases × (no skill, skill v0.4) with `claude-opus-5-5`, results in
  `evals/results/2026-09-27/` — full pass 0/8 → 6/8; visual fidelity equal (global SSIM
  0.9953 vs 0.9958); qmllint errors 150 → 0, runtime warnings 48 → 0, hard-coded
  colors/fonts 239 → 0.
- `evals/compare_runs.py`: side-by-side report of two scored run sets.
- `diff.py`: `textOnTargetRate` (share of runs within `textPositionPx`); region results carry
  `ssimUnaligned` and `alignShift` when alignment helped.
- Golden specs record each text run's baseline.
- References, from the two failures the baseline found: `typography.md` checks every numeric run
  for monospace (≈ 0.6 em per character); `effects.md` gets a dashed/dotted border recipe
  (`ShapePath.DashLine` + `PathRectangle`).

### Changed
- Thresholds calibrated and no longer provisional: global SSIM ≥ 0.98 (was 0.95); region SSIM
  measured at the best alignment within 1 px; chart overrides and the relaxed glass-case gates
  removed (every case reached the standard gates).
- Text matching: a spec run may match a whole item, one line, or part of a line (split, merged
  or re-wrapped runs); separators and `…`/`...` tolerated; vertical offset between baselines;
  global nearest-first assignment for repeated strings.
- Golden specs: text boxes exclude leading/trailing whitespace; text hidden under opaque
  elements is dropped (input screenshots unchanged).
- `quality_gate.py` embed gate: a preview image the UI does not use is a warning, not an error.

### Fixed
- Scene dump missed text in components wrapping `Text`, Controls `Label`, and `TextField` /
  `TextInput` values; text boxes ignored `leftPadding`; PySide enum-converter crash on
  `QQuickText` enums; `check.py` could report a previous run's numbers after a crash;
  `render.py` now loads projects without a `qmldir`; parallel renders no longer race for the
  same Xvfb display.

## [0.4.0] — 2026-09-25

### Added
- `analyze.py`: draft `design-spec.json` from a screenshot plus `overlay.png` (surfaces, text runs,
  icon candidates with ids), marked `draft` / `verify` for review.
- `palette.py`: solid colors (fills, borders, text stems, icon strokes) with coverage and samples.
- `geometry.py`: surfaces with box, fill, radius, border, parent, repeat hints; gradients drawn as
  flat steps are merged into gradient candidates; glyph bowls and same-color regions are pruned.
- `text_ocr.py`: tesseract (tur+eng) in three detection passes (local-contrast map + both
  polarities), each run re-read as one line at ~44 px ink height; ink-box font size estimate
  with Turkish accent/descender handling; text color snapped to the palette; icon candidates.
- `validate_spec.py`: schema + consistency (parents, duplicates, model counts, fills vs tokens,
  `on…` token names, leftover draft markers, low-confidence list).
- `gen_theme.py`: Theme.qml + Icons.qml from spec tokens with QML-safe names, qmlformat-ed.
- `evals/score_analysis.py` — measured on the 8 cases: palette recall 95.8 % (ΔE ≤ 2),
  surface recall 97.3 % (IoU ≥ 0.85, box error < 0.6 px), OCR 76 % exact strings, CER 12 %,
  font size MAE 1.2 px.

## [0.3.0] — 2026-09-25

### Added
- `render.py`: headless render at design size × DPR; re-runs under Xvfb on displayless Linux so
  shader effects render; `scene.json` with every visible text (string, painted box, font),
  images and QML warnings.
- `diff.py`: global SSIM with text masked, per-node region SSIM, CIEDE2000 per solid surface,
  sub-pixel template-matched geometry offsets, text match rate and positions; heatmap.
- `quality_gate.py`: qmllint, qmlformat drift, runtime QML warnings, color/font literals outside
  Style, screenshot-embedding detection, bundled-font verification, web-engine ban.
- `check.py`: render + diff + gates in one command.
- Eval set: 8 original screens (HMI, kiosk, dark/light dashboards at 2× and 1.25×, settings
  form, 3× mobile, data table, glassmorphism) with DOM-extracted ground truth, rubrics and
  thresholds; deterministic builder; `run_evals.py`.
- pytest suite (35 tests incl. end-to-end render of the example) and GitHub Actions CI.

### Changed
- Eval screenshots are rendered with `--font-render-hinting=none` (fractional glyph advances)
  so text metrics match Qt and non-Linux browsers.

## [0.2.0] — 2026-09-25

### Changed
- Renamed `html-to-pyside6` → `screenshot-to-qml`; screenshot input is the primary path.
- `SKILL.md` is now a < 200-line router; details moved to 14 reference files loaded on demand.
- Agent-agnostic wording; no tool names specific to one agent.
- Font loader scans `assets/fonts/` instead of a hard-coded list and logs Qt family names.
- Icon-font glyphs are written as escaped code points via an `Icons` singleton.

### Added
- `probe.py` for measuring colors, regions, edges, crops and rulers in design px.
- `scaffold.py` and a PySide6 template with `App`, `App.Style`, `App.Controls` modules.
- `design-spec.json` schema.
- Reference example `examples/hmi-dolum` (replaces the previous company-owned example).

### Removed
- "One DOM node = one QML item" rule and "write every row by hand" rule (replaced by semantic
  components and models).

## [0.1.0]

- Initial `html-to-pyside6` skill: HTML/screenshot → PySide6 QML with an offscreen preview.
