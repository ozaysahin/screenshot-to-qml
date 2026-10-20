---
name: screenshot-to-qml
description: Converts UI screenshots, mockups or HTML/CSS/Tailwind into native Qt Quick (QML) projects for PySide6 and/or C++ (CMake), with measured colors, spacing, fonts, icons and effects, a Theme singleton, QtQuick.Templates controls, a render-and-diff verification loop, and packaging for desktops or embedded boards (Raspberry Pi, Jetson). Use when the user shares a UI screenshot or HTML and wants a native Qt/QML desktop, kiosk, HMI or embedded interface without a web engine.
license: MIT (see LICENSE.txt)
compatibility: Python 3.10+, PySide6 6.8+; rendering checks need a display or Xvfb (Linux)
metadata:
  version: "1.0.1"
---

# Screenshot → Qt Quick (QML)

Rebuild the given screen as a native Qt Quick project that renders through Qt's own scene
graph — never a web engine or WebView. Three principles drive everything below:

1. **Measure, don't guess.** Colors, sizes and positions come from `scripts/probe.py`, not
   from reading the image by eye. Looking decides *what* something is; scripts decide *how
   big and which color*.
2. **Build from tokens.** Every value lives once in `Theme.qml`; components use tokens,
   Template-based controls and models.
3. **Prove it.** `scripts/check.py` renders the project, diffs it against the screenshot and
   runs quality gates. The work is done when it passes.

Not covered: Qt Widgets (`.ui`) output, wrapping HTML in a WebView, importing Figma files
(ask for a PNG export instead).

## Work budget

Every tool call re-sends the whole conversation, so a build's cost is set by how many calls
and images it takes, not by how hard each one is. Work in few, large steps:

| Effort | Use for | Tool calls | `check.py` runs |
| --- | --- | --- | --- |
| `quick` | simple screens (settings, forms, lists, one card grid), or a fast first version | ≤ 50 | ≤ 3 |
| `standard` | dashboards, HMIs, dense or mixed screens | ≤ 80 | ≤ 4 |
| `full` | the user asks for pixel-exact fidelity | as needed | ≤ 6 |

- Read summaries, not raw files: `spec_view.py` for a spec, `check.py`'s printout and
  `worst.png` for a check. Never open the JSON files to read them.
- Do not write ad hoc Python to read pixels, crop images, compare renders or inspect JSON.
  `probe.py` measures many points and boxes in one call; the sheets show many crops in one
  image.
- Open few images: the input once, `overlay.png` and `ocr_sheet.png` once, `worst.png` after
  each check. Do not open zoomed crops of single elements unless a measurement is ambiguous.
- Write each file whole in one call, fix everything a check lists before re-running it, and
  read a reference only when its step needs it.
- At the budget, stop: list what is left in the README's fidelity report instead of iterating.
  Spend the last round only on fixes you can name exactly ("padding 17 → 15.5 px").

## Setup (once per machine)

```bash
pip install -r <skill>/scripts/requirements.txt        # PySide6, numpy, opencv, scikit-image, scipy, Pillow, fonttools …
# OCR: apt install tesseract-ocr tesseract-ocr-tur (or brew install tesseract tesseract-lang)
# headless Linux only: apt install xvfb libxcb-cursor0
# Windows: set PYTHONUTF8=1 first (the scripts read and write UTF-8); renders open a window
python <skill>/scripts/font_match.py fetch             # candidate fonts, ~40 MB (google/fonts)
python <skill>/scripts/icon_match.py fetch             # icon sets + index, ~170 MB (needs npm)
# HTML input only: pip install playwright && python -m playwright install chromium
```

The two caches live in `~/.cache/screenshot-to-qml` (or `$S2Q_CACHE`); without them the font
and icon matchers are skipped, everything else works.

`<skill>` is this skill's directory. All scripts print `--help` and exit 0 (ok), 1 (below
threshold / gate failed) or 2 (could not run).

## Intake (ask at most 3 questions; otherwise use the defaults and say so)

| Decision | Options | Default |
| --- | --- | --- |
| Input | screenshot · HTML page (+ its CSS/fonts) | what the user gave; HTML → render it at the design size (step 1) |
| Target | `pyside6` · `cpp` · `both` (one qml/ tree, two hosts: references/target-cpp.md) | `pyside6` |
| Layout | `canvas` (fixed kiosk/HMI screen, scaled) · `responsive` (resizable desktop) | canvas for kiosk/HMI/panel screenshots, else responsive |
| Profile | `desktop` · `embedded-gpu` · `embedded-sw` (references/embedded.md) | `desktop` |
| Mode | `production` (Theme, models, controls, a11y) · `fidelity` (single static screen, quickest) | `production` |
| Effort | `quick` · `standard` · `full` (Work budget above) | what `analyze.py` suggests (quick for ≤ 70 text runs and ≤ 60 surfaces) |
| Screenshot DPR | 1 · 1.25 · 1.5 · 2 · 3 (references/analysis.md) | inferred from size; ask if ambiguous |
| Minimum Qt | 6.8 LTS or newer | 6.8 |

## Workflow

Copy this checklist into your reply and tick it off:

```
- [ ] 0 Intake: target, layout, profile, mode, effort, DPR → design size
- [ ] 1 Measure: analyze.py draft → fix it from overlay + ocr_sheet → match.py → validate_spec.py
      (HTML input: html_to_spec.py → rename tokens/roles → validate_spec.py)
- [ ] 2 Plan: component tree, models, controls, states
- [ ] 3 Scaffold + gen_theme.py
- [ ] 4 Build components and screens
- [ ] 5 Check loop until PASS (rounds per effort: 3 / 4 / 6)
- [ ] 6 Deliver: README fidelity report + preview (+ deploy.py when asked to package)
```

### 1 · Measure → `design-spec.json`

**HTML input** (a page, a Tailwind build, an exported mockup): the DOM already holds the exact
values, so render and extract instead of measuring pixels:

```bash
python <skill>/scripts/html_to_spec.py page.html --size W H --dpr D --out-dir analysis [--lang tr-TR]
# -> analysis/input.png (the reference for check.py), analysis/design-spec.json (all src "truth"),
#    analysis/icons/*.svg (the page's own icon vectors), analysis/fonts/ (its @font-face files)
```

Ask for the viewport (design size) if the user did not give it. Keep the page's CSS, fonts and
images next to it (linked files are read). Then rename tokens by role, check roles and models,
validate, and continue at step 2; skip `analyze.py`, `probe.py` and `match.py` (nothing to
guess). Fonts the page names without an `@font-face` file are system fonts: find or
substitute them. Details: **references/css-to-qml.md**.

**Screenshot input**: start from the automatic draft, then correct it by looking and measuring:

```bash
python <skill>/scripts/analyze.py input.png --dpr D --out-dir analysis        # palette + surfaces + OCR
# -> analysis/design-spec.draft.json, overlay.png (s# surfaces, t# text, i# icons),
#    ocr_sheet.png (every text run's crop labelled with its id)
python <skill>/scripts/spec_view.py analysis/design-spec.draft.json             # the draft as a compact table
python <skill>/scripts/probe.py input.png --dpr D color X Y [X Y ...]       # only for values the draft lacks
python <skill>/scripts/probe.py input.png --dpr D edges X Y W H             # edges, borders, padding
```

Look at `overlay.png` and `ocr_sheet.png` once each, compare them with the `spec_view.py`
table, and fix the draft in one edit. Probe only what the draft is missing or flags as
`[verify]`.

On the 20 eval screens the draft recovers ~95 % of solid colors (ΔE ≤ 2) and ~94 % of solid
surfaces (box error mostly < 0.6 px) but misses most cells of dense grids such as heatmaps;
OCR gets ~73 % of strings exactly and font size within ~1.4 px. So:
**verify every string** against `ocr_sheet.png` (OCR confuses ı/i, 0/6/8 in monospace, `·` → `-`,
`–` in ranges ("10–20", "1–14") → `-`, `%` and `₺`), rename tokens by role, set roles and
models, delete false surfaces and add missed ones. Then let the matchers fill what the eye is
bad at:

```bash
python <skill>/scripts/match.py input.png design-spec.json --out design-spec.json --fonts-dir analysis/fonts
```

It writes font family/weight per text run (right family for 95 % of runs, also on fonts it
was not tuned on), icon `set:name` + stroke width (90 % top-1), `box-shadow` values and
`linear-gradient` fills, all as `src: "measured"`, and lists what to confirm in
`design-spec.match-report.json`. Check those entries, remove `meta.draft` and `verify` flags.
When the report flags the screen's font as **outside the catalog** (a proprietary or rare
face), do not trust the nearest family's metrics blindly: ask for the font file or name if the
user can give it, otherwise bundle the listed substitute, fit sizes so text widths match the
screenshot, and name the substitute in the README (**references/typography.md**).
All coordinates are design px (= screenshot px / DPR). Format and rules:
**references/design-spec.md**; method and limits: **references/analysis.md**.

```bash
python <skill>/scripts/validate_spec.py design-spec.json      # schema + consistency; fix every ERROR
```

The spec is also the test: `diff.py` scores every node box and looks for every text string.

### 2 · Plan

- Name components after what they are (`TankGauge`, `AlarmItem`, `KpiCard`).
- Anything that repeats (≥ 2 alike) is a delegate over a model — data goes to `MockData.qml`.
- Every interactive element maps to a kit control or a `QtQuick.Templates` control
  (**references/controls.md**).
- Pick the positioning tool per region (**references/layout.md**).
- List states you can see and states you must assume (hover, pressed, focus, disabled).

### 3 · Scaffold and Theme

```bash
python <skill>/scripts/scaffold.py out/ --name "App Name" --layout canvas|responsive --fonts analysis/fonts/* \
       --target pyside6|cpp|both --profile desktop|embedded-gpu|embedded-sw \
       --controls Button,TextField,Switch        # or all (default) / none
python <skill>/scripts/gen_theme.py design-spec.json out/qml/App/Style        # Theme.qml + Icons.qml
```

The scaffold creates:

- the host: `main.py` (PySide6) and/or `CMakeLists.txt` + `src/main.cpp` (C++: every `qmldir`
  folder is compiled into the binary with fonts and translations). Both load `assets/fonts`
  and the `i18n/` translation, and use the software scene graph for `embedded-sw`;
  `--add-host cpp` adds the C++ host to an existing project;
- `qml/App` (Main);
- `qml/App/Style` (Theme, Icons);
- `qml/App/Controls`: the **control kit**. It has 14 QtQuick.Templates controls with hover,
  pressed, focus-ring, checked, error and disabled states, and they read only Theme roles.

`gen_theme.py` writes every token: flat QML-safe names, `#AARRGGBB` alphas and `Qt.font`
tokens. It ends with the control roles the kit needs (`accentHover`, `surfacePressed`,
`focusRing`, `controlHeight` …): aliased to spec tokens, derived from them, or assumed. Give
typeScale entries role names (`title`, `body`, `button`, `caption` …) in the spec and re-run
rather than editing the QML. Measured control sizes go in `tokens.size`
(`{"controlHeight": 40, "controlPadding": 14}`): an entry with a role's name replaces the
assumed value.

More detail: conventions in **references/tokens-theming.md**, fonts in
**references/typography.md**, icons in **references/icons-vectors.md**.

### 4 · Build

Rules that apply to every file:

- Only Theme tokens for colors, fonts, spacing and radii; no literals in components.
- Kit/Template controls restyled to the screenshot; `enabled: false` for disabled; a
  visible ring on `visualFocus`; every enabled control reachable with Tab.
- Models + delegates for repeats; `pragma ComponentBehavior: Bound` and `required property`
  in delegates.
- Layouts inside the canvas; mind the layout gotchas (nested `fillWidth`, equal columns,
  borders inside boxes, rounded corners do not clip).
- Text verbatim (Turkish ı/İ, decimal commas, real uppercase strings), wrapped in `qsTr()`
  (data in models and mock files is not).
- Effects per profile (**references/effects.md**); vector icons, never redrawn by hand:
  `icon_match.py export lucide:bell --stroke 2 --color "#64748B" --out assets/icons/bell.svg`
  per matched icon (one shell loop for all), then `VectorImage` for a fixed color or
  `svgtoqml` when the color must follow Theme tokens (**references/icons-vectors.md**).
- `Accessible.name` on icon-only buttons, sliders, combos, spin boxes, progress bars and
  informative custom items (**references/a11y-i18n.md**).
- Run `qmlformat -i` (or `pyside6-qmlformat -i`) on every QML file you write.

HTML input: **references/css-to-qml.md** (map the extracted CSS, not the markup, to QML).
C++ host: **references/target-cpp.md** (build and
check the QML with the PySide6 host; the C++ host runs the same files). Embedded devices:
**references/embedded.md**.

### 5 · Check loop

```bash
python <skill>/scripts/check.py out/ --source input.png --spec design-spec.json [--qt ~/Qt/6.8.3/gcc_64]
```

Renders at designSize × DPR (headless Linux: under Xvfb automatically; the software scene
graph for `embedded-sw`), then:

- `diff.py` — global SSIM (text masked), per-node region SSIM, ΔE2000 per solid fill,
  sub-pixel geometry offsets, text strings and positions (via the scene dump);
- `render.py --interact`: presses Tab through the window and hovers and presses every
  control, writing `interaction.json`;
- `build_cpp.py` (projects with a C++ host): builds, runs and grabs the binary, and compares it
  with the PySide6 render;
- `quality_gate.py`: qmllint, qmlformat, runtime QML warnings, color/font literals, screenshot
  embedding, bundled fonts, web engine use, **a11y** (Tab reach, visible focus, accessible
  names), **states** (visible pressed/hover), **i18n** (`qsTr` on visible strings), **effects**
  and **perf** (what the profile's renderer and hardware can afford) and **cpp** (the C++ host
  builds, runs clean and matches).

After a failed diff, `check.py` writes `out/.check/worst.png`: source and render crops of the
worst items side by side, labelled with what failed. Open it (not the full render, not crops
of your own), fix every listed item in one pass, and re-run. Stop at PASS, at the effort's
round limit, or when improvement stalls (< 0.005 SSIM over two rounds); list what is left in
the README.
How to read failures and what usually causes them: **references/verification.md**.

Never put the screenshot or crops of it into the UI, and never edit thresholds or the spec to
pass — the gates detect the first and reviewers catch the second.

### 6 · Deliver

Put a fidelity report in the project README:

- metrics from `out/.check/summary.json` (global SSIM, worst regions, ΔE max, geometry max,
  text match) and the gate result;
- values that are `assumed` or have `conf < 0.7` ("please verify");
- approximations and why (proprietary font substitute, blur dropped on embedded, …);
- how to run (`python main.py`, or the CMake build) and the preview (`out/.check/render.png`).

Packaging (**references/deploy.md**): `deploy.py out --target pyside6|cpp --platform desktop
--build` makes a desktop bundle (pyside6-deploy, or `cmake --install` with Qt bundled);
`--platform device` writes a kiosk service for a Linux board (`app.env` for eglfs/linuxfb,
systemd unit, `install.sh`).

Keep the chat reply short: what was built, the check result, what needs the user's eyes.

## Qt version gates

| Feature | Min Qt | Fallback |
| --- | --- | --- |
| `loadFromModule`, `MultiEffect` | 6.5 | `engine.load(url)`, layered rects |
| per-corner `Rectangle` radius | 6.7 | Shape `PathRectangle`/`PathSvg` |
| `VectorImage`, `svgtoqml`, `PathRectangle` | 6.8 | `Image` + `sourceSize` |
| `RectangularShadow` | 6.9 | `MultiEffect` shadow |
| `FlexboxLayout` (tech preview) | 6.10 | `Flow` / `RowLayout` |

Check `python -c "import PySide6; print(PySide6.__version__)"` and use only what the target has:
the `lint` gate fails types newer than `meta.minQt` even when the local PySide6 accepts them.

## Scripts

| Script | Purpose |
| --- | --- |
| `analyze.py` | draft spec from a screenshot: palette + surfaces + OCR, with an overlay |
| `html_to_spec.py` | HTML input: render the page (Chromium) → `input.png` + a truth spec, icon SVGs, font files |
| `palette.py` · `geometry.py` · `text_ocr.py` | the three analyzers on their own |
| `match.py` | fonts, icons, shadows, gradients measured into the spec + a report; `--fonts-dir` bundles static TTFs |
| `font_match.py` · `icon_match.py` | font family/weight/size per run; icon set:name + stroke; `fetch` the caches, `export` an SVG |
| `shadow_fit.py` · `gradient_fit.py` | CSS box-shadow / linear-gradient of one box (`--box`) or a whole spec |
| `probe.py` | measure colors, regions, edges; zoomed crops; coordinate ruler |
| `spec_view.py` | a spec as a compact table (tokens, nodes, text, icons; `--verify`, `--ids`) |
| `sheet.py` | contact sheets: `compare` (worst items, source \| render) and `ocr` (all text runs) |
| `validate_spec.py` | schema + consistency checks for design-spec.json |
| `scaffold.py` | new project (shared `assets/templates/project` + a `pyside6` and/or `cpp` host); `--add-host` |
| `gen_theme.py` | Theme.qml + Icons.qml from the spec tokens |
| `render.py` | headless render at size × DPR + `scene.json` (texts, images, QML warnings, perf); `--interact` → `interaction.json`; `--lang xx` loads a translation; `--scenegraph software` |
| `diff.py` | source vs render metrics → `report.json`, `diff.png` |
| `quality_gate.py` | 13 gates (static, runtime, a11y, states, i18n, effects, perf, cpp) → `gate.json` |
| `check.py` | render + diff + C++ build + gates in one command |
| `build_cpp.py` | CMake configure/build, run with `APP_GRAB`, parity with the PySide6 render, `--install` |
| `deploy.py` | desktop bundle (pyside6-deploy / cmake --install) or a board's kiosk service files |

## Reference implementation

`examples/hmi-dolum/` — a 1920×1080 industrial HMI screenshot rebuilt in production mode:
three QML modules, a Theme with 79 tokens, Template controls, models, a Shape line chart,
Font Awesome glyphs by code point, both hosts (PySide6 and C++). `check.py` passes it with
global SSIM 0.994, worst region 0.943, ΔE 0.43, geometry ≤ 1.9 px, 95/95 strings matched, all
13 gates clean; the C++ binary's frame equals the PySide6 render (SSIM 1.000). Read its files
when you need a concrete pattern.

`examples/controls-gallery/` — every kit control in its states, English UI with a Turkish
translation (`i18n/app_tr.qm`), both hosts; all 13 gates clean (Tab reaches all 27 enabled
controls, every one shows focus, hover and press).
