---
name: screenshot-to-qml
description: Converts UI screenshots, mockups or HTML/CSS/Tailwind into native Qt Quick (QML) projects for PySide6 and/or C++ (CMake) on Qt 6.8+ or Qt 5.15 (automotive and industrial boards), with measured colors, spacing, fonts, icons and effects, a Theme singleton, QtQuick.Templates controls, a render-and-diff verification loop, and packaging for desktops or embedded boards (Raspberry Pi, Jetson, Yocto). Use when the user shares a UI screenshot or HTML and wants a native Qt/QML desktop, kiosk, HMI, instrument cluster or embedded interface without a web engine.
license: MIT (see LICENSE.txt)
compatibility: Python 3.10+, PySide6 6.8+ (the check loop, also for Qt 5.15 targets); rendering checks need a display or Xvfb (Linux)
effort: medium
metadata:
  version: "1.1.1"
---

# Screenshot → Qt Quick (QML)

Rebuild the screen as a native Qt Quick project (Qt's own scene graph, never a web engine).

1. **Measure, don't guess.** Colors, sizes and positions come from the scripts, not from
   reading the image by eye. Looking decides *what* something is; scripts decide *how big
   and which color*.
2. **Build from tokens.** Every value lives once in `Theme.qml`; components use tokens,
   Template-based controls and models.
3. **Prove it.** `check.py` renders the project, diffs it against the screenshot and runs 13
   quality gates. The work is done when it passes. It is only as strict as the spec: boxes
   come from the draft and `probe.py`, never typed in by eye (the check fails a spec whose
   text boxes stray from the measured ones).

Not covered: Qt Widgets (`.ui`), HTML in a WebView, Figma files (ask for a PNG export).

## Work budget

Every tool call re-sends the whole conversation: cost = number of turns × context size.

| Effort | Use for | Tool calls | `check.py` runs |
| --- | --- | --- | --- |
| `quick` | simple screens (settings, forms, lists, one card grid), or a fast first version | ≤ 40 | ≤ 3 |
| `standard` | dashboards, HMIs, clusters, dense or mixed screens | ≤ 60 | ≤ 4 |
| `full` | the user asks for pixel-exact fidelity | as needed | ≤ 6 |

- **Batch.** Independent calls go in one turn: probes for many boxes in one `probe.py` call,
  exports in one shell loop. Write the spec fixes in one edit and all QML files in one call (a
  heredoc or a small generator script that writes every file is fine).
- **Think briefly.** The measurements decide: act on the printouts instead of reasoning about
  pixel values in prose, and do not narrate between calls.
- **Read printouts, not files.** The commands in this file and the scripts' printouts are
  complete: do not read script sources, `--help`, JSON files or the match report, and read a
  reference only when its step says so.
- **No ad hoc scripts** to read pixels, crop images, compare renders or inspect JSON.
- **Few images:** the input once, `overlay.png` and `ocr_sheet.png` once, `worst.png` after
  each check.
- Write each file whole, fix everything a check lists before re-running it. At the budget,
  stop and list what is left in the README; spend the last round only on fixes you can name
  exactly ("padding 17 → 15.5 px").

## Setup (once per machine)

```bash
pip install -r <skill>/scripts/requirements.txt        # PySide6, numpy, opencv, scikit-image, scipy, Pillow, fonttools …
# OCR: apt install tesseract-ocr tesseract-ocr-tur (or brew install tesseract tesseract-lang)
# headless Linux: apt install xvfb libxcb-cursor0 · Windows: set PYTHONUTF8=1 first
python <skill>/scripts/font_match.py fetch             # candidate fonts, ~40 MB (google/fonts)
python <skill>/scripts/icon_match.py fetch             # icon sets + index, ~170 MB (needs npm)
# HTML input only: pip install playwright && python -m playwright install chromium
```

Caches live in `~/.cache/screenshot-to-qml` (`$S2Q_CACHE`); without them the font and icon
matchers are skipped. `<skill>` is this folder. Scripts exit 0 ok, 1 below threshold, 2 error.

## Intake (ask at most 3 questions; otherwise use the defaults and say so)

| Decision | Options | Default |
| --- | --- | --- |
| Input | screenshot · HTML page (+ its CSS/fonts) | what the user gave |
| Target | `pyside6` · `cpp` · `both` (one qml/ tree, two hosts: references/target-cpp.md) | `pyside6` (`cpp` for Qt 5.15) |
| Layout | `canvas` (fixed kiosk/HMI screen, scaled) · `responsive` (resizable desktop) | canvas for kiosk/HMI/panel screenshots, else responsive |
| Profile | `desktop` · `embedded-gpu` · `embedded-sw` (references/embedded.md) | `desktop` |
| Mode | `production` (Theme, models, controls, a11y) · `fidelity` (single static screen) | `production` |
| Effort | `quick` · `standard` · `full` | what `analyze.py` suggests |
| Screenshot DPR | 1 · 1.25 · 1.5 · 2 · 3 (references/analysis.md) | inferred from size; ask if ambiguous |
| Minimum Qt | 6.8 or newer · 5.15 (Qt 5 boards: clusters, IVI, industrial BSPs; references/target-qt5.md) | 6.8 |

## Workflow

```
- [ ] 0 Intake → design size
- [ ] 1 Measure: analyze.py --match → fix the draft from overlay + ocr_sheet → match.py → validate_spec.py
- [ ] 2 Plan: component tree, models, controls, states
- [ ] 3 Scaffold + gen_theme.py
- [ ] 4 Build all components and screens (one turn)
- [ ] 5 Check loop until PASS (rounds per effort: 3 / 4 / 6)
- [ ] 6 Deliver: README fidelity report + preview (+ deploy.py when asked)
```

### 1 · Measure → `design-spec.json`

**Screenshot input:**

```bash
python <skill>/scripts/analyze.py input.png --dpr D --out-dir analysis --match
# palette + surfaces + OCR + a first font/icon match; prints the draft as a table and what to confirm
# -> analysis/design-spec.draft.json, overlay.png (s# surfaces, t# text, i# icons), ocr_sheet.png
python <skill>/scripts/probe.py input.png --dpr D color X Y [X Y …]        # values the draft lacks
python <skill>/scripts/probe.py input.png --dpr D edges X Y W H [X Y W H …]   # edges, borders, padding
```

Look at `overlay.png` and `ocr_sheet.png` once, compare with the printed table and fix the
draft in one edit into `design-spec.json`: **verify every string** (OCR confuses ı/i, 0/6/8 in
monospace, `·` → `-`, `–` in ranges → `-`, `%`, `₺`), rename tokens by role, set roles and
models (`model` on repeats), delete false surfaces, add missed ones (`probe.py` for their
boxes), give typeScale entries role names and snap near-duplicate sizes (39/40 px) to one.
Probe only what is missing or flagged `[verify]`. Then:

```bash
python <skill>/scripts/match.py input.png design-spec.json --out design-spec.json --fonts-dir analysis/fonts
python <skill>/scripts/validate_spec.py design-spec.json      # fix every ERROR
```

`match.py` writes font family/weight per run, icon `set:name` + stroke, shadows and
gradients (`src: "measured"`), and prints what to confirm: settle those, remove `meta.draft`
and `verify` flags. A font **outside the catalog**: ask for the file or name, else bundle the
listed substitute and name it in the README (references/typography.md). Coordinates are design
px (screenshot px / DPR). Text boxes from OCR are ink boxes; keep them (the check compares
them by baseline and the font's own bearings); node boxes are outer edges, border included.
Format: references/design-spec.md.

**HTML input:** `html_to_spec.py page.html --size W H --dpr D --out-dir analysis [--lang tr-TR]`
renders the page and writes `analysis/input.png` (the check's reference), a truth spec, the
page's icon SVGs and fonts. Ask for the viewport if not given; rename tokens and roles,
validate, go to step 2 (no analyze/probe/match). Mapping: references/css-to-qml.md.

### 2 · Plan

Components named for what they are (`TankGauge`, `AlarmItem`); anything that repeats is a
delegate over a model (data in `MockData.qml`); every interactive element is a kit or
`QtQuick.Templates` control (references/controls.md); positioning per region
(references/layout.md); list visible and assumed states (hover, pressed, focus, disabled).

### 3 · Scaffold and Theme

```bash
python <skill>/scripts/scaffold.py out/ --name "App Name" --layout canvas|responsive --fonts analysis/fonts/* \
       --target pyside6|cpp|both --profile desktop|embedded-gpu|embedded-sw \
       --controls Button,TextField,Switch [--min-qt 5.15]     # controls: all (default) / none / a list
python <skill>/scripts/gen_theme.py design-spec.json out/qml/App/Style        # Theme.qml + Icons.qml
```

It prints the token names it wrote (no need to open Theme.qml). You get the host(s) (`main.py`; `CMakeLists.txt` + `src/main.cpp` with QML, fonts and
translations compiled in), `qml/App/Main.qml`, `qml/App/Style` (Theme, Icons) and the control
kit `qml/App/Controls` (14 Template controls with hover, pressed, focus, checked, error and
disabled states, Theme roles only; `SvgIcon` on Qt 5.15). `gen_theme.py` ends Theme with the
roles the kit needs (`accentHover`, `focusRing`, `controlHeight` …), aliased, derived or
assumed; measured sizes in `tokens.size` (`{"controlHeight": 40}`) replace assumed ones. Fix
names and sizes in the spec and re-run, not in the QML (references/tokens-theming.md).

### 4 · Build

Write every component and screen in one turn, then format them all in one command.

- Only Theme tokens for colors, fonts, spacing and radii; no literals in components.
- Kit/Template controls restyled to the screenshot; `enabled: false` for disabled; a visible
  ring on `visualFocus`; every enabled control reachable with Tab.
- Models + delegates for repeats; `required property` in delegates (and `pragma
  ComponentBehavior: Bound` on Qt 6).
- Text: a fixed-height `Text` with `AlignVCenter` per CSS line box; verbatim strings (Turkish
  ı/İ, decimal commas, real uppercase), in `qsTr()` (not data in models and mock files).
- Icons are vectors from the matched set, never redrawn:
  `icon_match.py export tabler:bell tabler:route … --stroke 2 --color "#64748B" --out assets/icons`
  (all icons of one stroke in one call), then `VectorImage`, svgtoqml for Theme colors
  (references/icons-vectors.md), or `SvgIcon` on Qt 5.15.
- Effects per profile (references/effects.md, which also has the Qt version gates: use only
  what `meta.minQt` has); `Accessible.name` on icon-only buttons, sliders, combos, progress
  bars and informative custom items (references/a11y-i18n.md).
- `pyside6-qmlformat -i` on every QML file.

C++ host: references/target-cpp.md. Embedded: references/embedded.md. Qt 5.15:
references/target-qt5.md (write the 5.15 dialect from the start; `qt5.py check` lists the rest).

### 5 · Check loop

```bash
python <skill>/scripts/check.py out/ --source input.png --spec design-spec.json [--qt <Qt 6.8+ or 5.15 prefix>]
```

It renders at designSize × DPR (Xvfb on headless Linux), diffs (global and per-node SSIM,
ΔE2000, geometry, every string's position; it prints how to read each kind), drives Tab,
hover and press, builds and compares the C++ host, and runs the 13 gates (lint, format,
runtime warnings, literals, screenshot embedding, fonts, web engine, a11y, states, i18n,
effects, perf, cpp). After a failed diff, open `out/.check/worst.png` (source | render of the
worst items, labelled), fix every listed item in one pass, re-run. Stop at PASS, at the round
limit, or when improvement stalls (< 0.005 SSIM over two rounds). Causes of typical failures:
references/verification.md.

Never put the screenshot or crops of it into the UI; never edit thresholds or the spec to pass.

### 6 · Deliver

README fidelity report: metrics from `out/.check/summary.json` and the gate result; values
`assumed` or `conf < 0.7` ("please verify"); approximations and why; how to run; the preview
`out/.check/render.png`. Packaging (references/deploy.md): `deploy.py out --target pyside6|cpp
--platform desktop --build` (bundle) or `--platform device` (kiosk service for a board). Keep
the chat reply short: what was built, the check result, what needs the user's eyes.

## Scripts and examples

All scripts: references/scripts.md. Reference projects (read a file when you need a pattern):

- `examples/hmi-dolum/` — 1920×1080 industrial HMI, both hosts, Shape line chart, Font
  Awesome glyphs; SSIM 0.994, 95/95 strings, 13 gates clean, C++ frame = PySide6 frame.
- `examples/auto-cluster/` — 1920×720 car instrument cluster on Qt 5.15 (C++ host): a reusable
  `Dial` (one Shape, generated ticks and labels, a needle bound to `value`), telltales from a
  model, `SvgIcon`; SSIM 0.999, 61/61 strings, 13 gates clean on Qt 5.15.13.
- `examples/controls-gallery/` — every kit control in its states, English with a Turkish
  translation, both hosts; 13 gates clean.
