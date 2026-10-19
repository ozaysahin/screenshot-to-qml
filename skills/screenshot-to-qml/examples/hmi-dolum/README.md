# Example: industrial HMI (hmi-dolum)

| File | What it is |
| --- | --- |
| `input.png` | the screenshot the skill receives (1920×1080, DPR 1) |
| `analysis/` | what `analyze.py` drafts from the screenshot alone: `design-spec.draft.json`, `overlay.png`, raw palette/geometry/OCR |
| `design-spec.json` | the reviewed spec used for the build and the check (here: the eval ground truth for case `01-hmi-dolum`) |
| `project/` | the generated project with both hosts: `python project/main.py` (PySide6), or CMake (C++, below) |
| `check/` | output of `scripts/check.py`: `render.png`, `diff.png`, `report.json`, `gate.json`, `summary.json`, and the C++ host's frame `cpp.png` + `cpp.json` |

Reproduce the check:

```bash
python ../../scripts/check.py project --source input.png --spec design-spec.json --out-dir check [--qt ~/Qt/6.8.3/gcc_64]
```

Result: global SSIM 0.994, worst region 0.943, ΔE 0.43, geometry ≤ 1.9 px, 95/95 strings; all
13 gates pass. The C++ host (Qt 6.8.3, compiled QML) draws the same frame as the PySide6 host
(Qt 6.11): SSIM 1.000.

C++ host (profile `embedded-gpu`; see `references/target-cpp.md`):

```bash
cmake -S project -B build -G Ninja && cmake --build build && ./build/hat-3-dolum-hmi
python ../../scripts/deploy.py project --target cpp --platform device    # kiosk service for a board
```

Patterns worth copying: `Controls/TouchButton.qml` (variants + inset press edge),
`Controls/SegmentedControl.qml` (ButtonGroup + Repeater), `Controls/ValueSlider.qml`
(CSS-style centered handle), `AlarmItem.qml` (rounded severity bar without clipping),
`LineChart.qml` (Shape chart with smoothed path, area gradient, dashed setpoint),
`TankGauge.qml` (per-corner radius fill), `ControlPanel.qml` (space-between scale labels).

`qml/App/Style/Theme.qml` started as `gen_theme.py` output; font tokens were then given role
names (`kpiValue`, `heading`, `caption` …) and component-level sizes added — the same review step
the skill asks for.
