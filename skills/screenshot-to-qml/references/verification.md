# Verification

A project is done when `scripts/check.py` passes, not when it "looks right".

## Contents
- The loop
- What the metrics mean
- Fixing by failure type
- Rules that keep the numbers honest
- Rendering environments

## The loop

```bash
python scripts/check.py PROJECT --source input.png --spec design-spec.json [--thresholds t.json]
```

It renders at `meta.designSize × meta.dpr`, compares with the source, runs the quality gates,
and writes `PROJECT/.check/{render.png, diff.png, report.json, gate.json, summary.json}`.

1. Read the one-line summary and `worstRegions`.
2. Open `diff.png` (hot colors = differences; boxes = worst regions) and the same crop of the
   source and render (`probe.py … crop`).
3. Fix the worst 1–3 regions with targeted edits. Do not rewrite files wholesale.
4. Re-run. Stop at PASS, or after 5 iterations, or when two iterations improve global SSIM by
   less than 0.005 — then report what is left.

## What the metrics mean

| Metric | Measures | Default gate |
| --- | --- | --- |
| globalSSIM | structure of the whole frame, text boxes masked | ≥ 0.98 |
| regionSSIM | structure inside each spec node > 24×24, best alignment within 1 px | ≥ 0.90 (per-node overrides) |
| colorDeltaE2000 | median color of each solid-fill node, source vs render | ≤ 2.0 |
| geometryPx | shift of each node found by template matching (sub-pixel) | ≤ 2 px |
| textStringMatch | spec strings found in the rendered scene | 100 % |
| textPositionPx | offset of each string: aligned edge horizontally, baseline vertically | ≤ 2 px |
| quality gates | lint, format, runtime warnings, literals, embedding, fonts, web engine, a11y, states, i18n, effects, perf, cpp | 0 errors |
| cpp parity | SSIM of the C++ host's frame against the PySide6 render (same QML) | ≥ 0.98 (warning < 0.995) |

The gates were calibrated on 16 eval runs: good rebuilds score global SSIM 0.987–0.999, so
0.98 separates "missing or wrong element" from rasterizer noise.

Text is masked out of SSIM because no two rasterizers produce identical glyph pixels; text is
checked by string and position through the scene dump instead. The scene dump sees `Text`,
`Label`, custom components that wrap them, `TextField`/`TextInput` values and `TextArea`/`TextEdit`
content (line by line, plain or rich text). A spec run may match a whole item, one line of a
multi-line item, part of a line, or a span that wraps from one line onto the next, so splitting
or merging runs differently from the design is fine. Separators drawn as their own shapes
(`•••• 4821` with dots as circles) are matched without them, on the edge that was not cut.
Vertical or rotated labels are compared by the centers of their boxes.

Fill colors (ΔE) are measured on the pixels where the screenshot shows the node's dominant
color, so a status dot or a switch knob that is not its own node does not count as the fill.

## Fixing by failure type

| Failure | Usual cause | Fix |
| --- | --- | --- |
| Many geometry offsets with the same dx | a parent is shifted/wider (padding, border, fillWidth) | fix the parent; children follow |
| One column too wide/narrow | nested layout `fillWidth` inheritance, unequal "equal" columns | layout.md gotchas 1–2 |
| Text offsets growing along a line | letter spacing, wrong weight or family, rounded advances | typography.md |
| Text dy ≈ ±2–4 | line box height/alignment | `height: lineHeight; verticalAlignment: AlignVCenter` |
| ΔE > 2 on a surface | wrong token, missing alpha, `#RRGGBBAA` order | tokens-theming.md |
| Region SSIM low, colors right | missing border/shadow/gradient, radius off | crop both images at zoom 4 and compare |
| Missing strings | text in an Image/Canvas, `Font.AllUppercase` on Turkish text (gives I, not İ), a live clock or date instead of the screenshot's value, typo | write real text; show the screenshot's values from mock data |
| Region SSIM low but geometry fine | border style (dashed), radius or antialiasing of a small control | crop both images at zoom 4 and compare |
| runtime gate | QML warnings (binding loops, undefined properties) | fix every warning |
| format gate | not qmlformat-clean | `qmlformat -i` (or `pyside6-qmlformat -i`) on the files |
| a11y: "Tab never reaches it" | `focusPolicy: Qt.NoFocus` (template default for some), a `MouseArea` instead of a control | `focusPolicy: Qt.StrongFocus`; use a kit/Template control |
| a11y: "keyboard focus is not visible" | no ring, or the ring only on some variants | `FocusRing { visible: control.visualFocus }` in the background |
| a11y: "no accessible name" | icon-only button, slider, combo, spin box, progress bar | `Accessible.name: qsTr("…")` |
| a11y: duplicate Tab stop | an inner `TextInput` is also a Tab stop | give the outer control `focusPolicy: Qt.NoFocus` and let the inner item take focus (kit SpinBox) |
| states: "no visible pressed state" | background ignores `control.down` | a `down` color (`Theme.accentPressed`, `surfacePressed`) |
| i18n: "string without qsTr()" | literal `text: "…"` or `model: ["…"]` | `qsTr("…")`; data belongs in models/mock files |
| effects: "not drawn by the software scene graph" | a shadow, glow or blur in an `embedded-sw` project | the flat fallback (embedded.md); say so in the README |
| perf: "decoded at … set sourceSize" | a large PNG/JPG shown small | `sourceSize.width/height` = drawn size × DPR |
| perf: infinite animation / fast timer | a spinner or clock animating while idle | stop it when hidden or idle; a clock needs a 1 s timer, not 16 ms |
| cpp: "Qt 6.8+ CMake package not found or incomplete" | no Qt 6.8+ SDK where check.py runs | `--qt ~/Qt/6.8.3/gcc_64` or `QT_DIR`; the gate is skipped, not failed |
| cpp: SSIM < 0.98 against the PySide6 render | a file the binary does not contain (image outside `qml/`/`assets/`, a folder without `qmldir`), or C++-only code | keep files in module folders or `assets/`; open `cpp.png` next to `render.png` |
| cpp: "QML: …" in the C++ run | a type the compiled module cannot resolve (import missing in that file) | add the import; qmlcachegen warnings in the build log point at it |

## Rules that keep the numbers honest

- Never place the screenshot (or crops of it) in the UI. The `embed` gate checks raster size and
  similarity to the source.
- Never edit `thresholds.json` or the spec to make a check pass. If a threshold is unreachable
  for a real reason (backdrop blur on an embedded profile), say so in the README.
- Assumed values stay marked as assumed even if the check passes.

## Rendering environments

- Linux without a display: `render.py` re-runs itself under `xvfb-run` (GPU path through Mesa, shader effects work).
  Needs `xvfb` and `libxcb-cursor0`.
- `--scenegraph software`: the software scene graph an `embedded-sw` device uses (no shader
  effects); `check.py` picks it from the profile. `--platform offscreen` also falls back to it.
- Windows/macOS/Linux desktop: renders with the native platform, window moved off-screen.
- Render size must equal the source pixel size; `diff.py` refuses mismatched sizes.
