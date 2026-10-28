# Example: automotive instrument cluster on Qt 5.15 (auto-cluster)

| File | What it is |
| --- | --- |
| `input.png` | the screenshot the skill receives (1920×720, DPR 1: a 12.3-inch cluster panel) |
| `analysis/` | what `analyze.py` drafts from the screenshot alone: `design-spec.draft.json`, `overlay.png`, `ocr_sheet.png`, raw palette/geometry/OCR |
| `design-spec.json` | the reviewed spec used for the build and the check (here: the eval ground truth for case `21-auto-cluster`, with role names for the font tokens and the dial geometry in `tokens.size`); `meta.minQt` is `5.15` |
| `project/` | the generated project: Qt 5.15 QML and a C++ host (CMake, Qt5) |
| `check/` | output of `scripts/check.py`: `render.png` (PySide6), `cpp.png` (the Qt 5.15.13 binary's own frame), `diff.png`, `report.json`, `gate.json`, `cpp.json`, `summary.json` |

Reproduce the check (Qt 5.15 from the distro, e.g. `apt install qtdeclarative5-dev
qtquickcontrols2-5-dev qml-module-qtquick-shapes qml-module-qtgraphicaleffects`, or `--qt` for an SDK):

```bash
python ../../scripts/check.py project --source input.png --spec design-spec.json --out-dir check [--qt ~/Qt/5.15.2/gcc_64]
```

Result: global SSIM 0.999, worst region 0.983, ΔE 0.0, geometry ≤ 1.1 px, 61/61 strings, all
13 gates pass. The C++ host built against Qt 5.15.13 runs with no QML warnings and draws the
same frame as the PySide6 (Qt 6) render: max tile difference 14.7 (limit 24; text lays out up
to ~1 px differently in Qt 5), SSIM 0.996.

How it was built (the skill's steps, `--min-qt 5.15`):

```bash
python ../../scripts/scaffold.py project --name "Ayaz Cluster" --min-qt 5.15 --layout canvas \
       --profile embedded-gpu --controls none --fonts Rajdhani-*.ttf
python ../../scripts/gen_theme.py design-spec.json project/qml/App/Style
# icons: tabler SVGs in project/assets/icons, drawn with the kit's SvgIcon (Image + ColorOverlay)
python ../../scripts/qt5.py check project          # nothing Qt 5.15 cannot load
```

Patterns worth copying:

- `Dial.qml` — a reusable round gauge: one `Shape` with three `PathAngleArc`s (track, redline,
  value) antialiased by a single multisampled layer, ticks and scale labels generated from
  `maximum` / `minorStep` / `majorStep`, a needle bound to `value`. The speedometer and the
  tachometer are two instances.
- `Controls/SvgIcon.qml` — Theme-colored SVG icons on Qt 5.15 (no `VectorImage`, no
  `MultiEffect`): the SVG rasterized at its drawn size × DPR, tinted by `ColorOverlay`.
- `TelltaleRow.qml` — warning lights from a model (on: their tone; off: dim).
- `MockData.qml` — the vehicle state in one singleton with writable `speed`, `rpm`, `gear`,
  `turnLeft` …; on the car a C++ object fed by the CAN gateway exposes the same names.
- `NavCard.qml` — CSS `justify-content: space-between` for a row of three items.

`docs/tools/demo_gif.py` drives `MockData.speed` / `rpm` on the running app to make the
README's demo GIF.
