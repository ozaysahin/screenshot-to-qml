# Hat 3 · Dolum İstasyonu — HMI

Native Qt Quick rebuild of `../input.png` (1920×1080, DPR 1), production mode, profile
`embedded-gpu`.

## Run

PySide6:

```bash
pip install -r requirements.txt
python main.py                                   # 1280×720 window, canvas scales to fit
QT_QPA_PLATFORM=eglfs python3 main.py            # Raspberry Pi / Jetson kiosk (set Window.FullScreen)
```

C++ (Qt 6.8+; the same `qml/`, compiled into the binary with the fonts):

```bash
cmake -S . -B build -G Ninja [-DCMAKE_PREFIX_PATH=~/Qt/6.8.3/gcc_64] && cmake --build build
./build/hat-3-dolum-hmi
```

Board: `python <skill>/scripts/deploy.py . --target cpp --platform device` writes the kiosk
service (`deploy/device/`: eglfs settings, systemd unit, `install.sh`).

## Structure

| Path | Contents |
| --- | --- |
| `qml/App/Style/Theme.qml` | 79 tokens: colors, spacing, radii, sizes, 28 font tokens, `alpha()` helper |
| `qml/App/Style/Icons.qml` | Font Awesome 7 Free Solid code points |
| `qml/App/Controls/` | `TouchButton`, `SegmentedControl`, `ValueSlider` (QtQuick.Templates), `Panel`, `Icon`, `CountBadge`, `StatusTag` |
| `qml/App/` | `Main` (fixed 1920×1080 canvas + Layouts), screen components, `MockData` |
| `assets/fonts/` | Barlow, JetBrains Mono, Font Awesome 7 Free Solid |

Data lives in `MockData.qml`; replace it with a Python backend exposing the same property
names (tanks, kpis, alarms, pressure, …) — see the skill's `references/target-pyside6.md`.

## Fidelity report

Checked with `scripts/check.py` against the source screenshot and its spec:

| Metric | Result | Gate |
| --- | --- | --- |
| Global SSIM (text masked) | 0.9944 | ≥ 0.98 |
| Worst region SSIM (aligned within 1 px) | 0.943 (`shift` chip) | ≥ 0.90 |
| Color ΔE2000, max over surfaces | 0.43 | ≤ 2.0 |
| Geometry offset, max | 1.93 px | ≤ 2 px |
| Text strings found | 95 / 95 | 100 % |
| Text position offset, max | 1.79 px | ≤ 2 px |
| Quality gates (lint, format, runtime, literals, embedding, fonts, web engine, a11y, states, i18n, effects, perf, cpp) | all 13 pass; 1 warning: the speed slider is 36 px tall (< 44 px touch target) | 0 errors |
| C++ host (Qt 6.8.3) frame vs PySide6 render | SSIM 1.000 | ≥ 0.98 |

Assumed (not visible in the screenshot): pressed colors (`Qt.darker(fill, 1.15)`), focus rings
(`visualFocus` border), slider step size (50).

Approximations: none required for this screen. Text widths differ from the browser by < 1 px
per run (fractional advances on both sides).
