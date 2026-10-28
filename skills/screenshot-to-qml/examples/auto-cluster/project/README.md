# Ayaz Cluster — instrument cluster (Qt 5.15)

Native Qt Quick rebuild of `../input.png` (1920×720, DPR 1), production mode, profile
`embedded-gpu`, minimum Qt 5.15 (C++ host).

## Run

```bash
cmake -S . -B build -G Ninja [-DCMAKE_PREFIX_PATH=~/Qt/5.15.2/gcc_64]   # omit for a system or Yocto SDK Qt
cmake --build build
./build/ayaz-cluster                                  # 1280×480 window, the canvas scales to fit
QT_QPA_PLATFORM=eglfs ./build/ayaz-cluster            # on the panel (set Window.FullScreen)
```

Needs Qt 5.15 with Qt Quick, Qt Quick Shapes, QtGraphicalEffects and the SVG image plugin
(Debian/Ubuntu: `qtdeclarative5-dev qml-module-qtquick-shapes qml-module-qtgraphicaleffects
libqt5svg5`). The QML, fonts and icons are compiled into the binary (`cmake/S2qQml5.cmake`,
qmlcachegen when Qt5QuickCompiler is installed). Board: `python <skill>/scripts/deploy.py .
--target cpp --platform device` writes the kiosk service (eglfs settings, systemd unit,
`install.sh`).

## Structure

| Path | Contents |
| --- | --- |
| `qml/App/Style/Theme.qml` | colors, spacing, radii, dial geometry (`tokens.size`), 20 font tokens named by role |
| `qml/App/Controls/SvgIcon.qml` | Theme-colored SVG icon for Qt 5.15 (Image + ColorOverlay) |
| `qml/App/` | `Main` (fixed 1920×720 canvas), `Dial`, `StatusRow`, `TelltaleRow`, `NavCard`, `TripTile`, `MediaCard`, `SegmentMeter`, `Card`, `MockData` |
| `assets/fonts/` | Rajdhani (OFL) |
| `assets/icons/` | Tabler icons (MIT) |

Data lives in `MockData.qml`; replace it with a C++ object registered as the `MockData`
singleton (or a context property) exposing the same names: `speed`, `rpm`, `gear`,
`telltales`, `turnLeft`, `fuel` …

## Fidelity report

Checked with `scripts/check.py` against the source screenshot and its spec:

| Metric | Result | Gate |
| --- | --- | --- |
| Global SSIM (text masked) | 0.999 | ≥ 0.98 |
| Worst region SSIM (aligned within 1 px) | 0.983 (`routeItem[1]`) | ≥ 0.90 |
| Color ΔE2000, max over surfaces | 0.0 | ≤ 2.0 |
| Geometry offset, max | 1.06 px | ≤ 2 px |
| Text strings found | 61 / 61 | 100 % |
| Text position offset, max | 1.05 px | ≤ 2 px |
| Quality gates (lint with the Qt 5.15 rules, format, runtime, literals, embedding, fonts, web engine, a11y, states, i18n, effects, perf, cpp) | all 13 pass | 0 errors |
| C++ host (Qt 5.15.13) frame vs PySide6 render | max tile difference 14.7, SSIM 0.996 | tile ≤ 24 |

Assumed (not visible in the screenshot): none of the values; the dial geometry comes from the
spec (`tokens.size`).

Approximations: Qt 5.15 has no curve renderer, so the dial arcs are antialiased with a
4-sample layer (one per dial). Text widths differ from the browser by ≤ 1 px per run.
