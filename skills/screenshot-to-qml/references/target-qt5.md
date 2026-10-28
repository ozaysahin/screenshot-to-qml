# Qt 5.15 target (automotive and industrial boards)

## Contents
- When to target Qt 5.15
- Setup and scaffold
- The Qt 5.15 dialect
- Effects, icons and shapes on 5.15
- How the check loop verifies 5.15
- Deploy

## When to target Qt 5.15

Many instrument clusters, IVI head units and industrial panels still ship Qt 5.15 LTS: a Yocto
image with meta-qt5, a vendor BSP, an older distro. Target it (`meta.minQt: "5.15"`) when the
user names Qt 5, a board image or SDK with Qt 5.15, or `qmake`/`Qt5::` code they must match.
Everything else defaults to Qt 6.8.

A Qt 5.15 project has the **C++ host only** (CMake, `find_package(Qt5)`). PySide2 has no
wheels for Python 3.11+; when a board must run Python, the distro's `python3-pyside2` can load
the same `qml/` tree with `engine.load()`, but the skill does not scaffold it.

## Setup and scaffold

Qt 5.15 for the C++ build: Debian/Ubuntu `apt install qtdeclarative5-dev qtquickcontrols2-5-dev
qml-module-qtquick-controls2 qml-module-qtquick-shapes qml-module-qtgraphicaleffects
libqt5svg5 cmake ninja-build g++`; Windows/macOS `aqt install-qt <os> desktop 5.15.2 <arch>`;
a board's SDK (`source environment-setup-*`). The check loop itself still runs on PySide6.

```bash
python <skill>/scripts/scaffold.py out/ --name "Cluster" --min-qt 5.15 --layout canvas --profile embedded-gpu
python <skill>/scripts/gen_theme.py design-spec.json out/qml/App/Style    # meta.minQt 5.15 → 5.15 imports
python <skill>/scripts/qt5.py check out/                                  # anything 5.15 cannot load
python <skill>/scripts/qt5.py port  out/                                  # an existing Qt 6 tree → 5.15 (mechanical part)
```

The scaffold writes the kit in the 5.15 dialect, adds `Controls/SvgIcon.qml`, and a host that
embeds `qml/`, `assets/`, `i18n/` and `mock/` as one resource (`qrc:/qml/App/Main.qml`, import
path `qrc:/qml`), compiled ahead of time when Qt5QuickCompiler is installed.

## The Qt 5.15 dialect

| Qt 6.8 | Qt 5.15 |
| --- | --- |
| `import QtQuick` | `import QtQuick 2.15`; a file that uses `Window` (or `Screen`) also `import QtQuick.Window 2.15` |
| `import QtQuick.Layouts` / `Shapes` / `Templates as T` | `… Layouts 1.15` / `Shapes 1.15` / `Templates 2.15 as T` |
| `import App.Style` (project modules) | `import App.Style 1.0`; qmldir entries need versions: `Main 1.0 Main.qml` |
| `pragma ComponentBehavior: Bound` | leave it out; keep `required property` in delegates |
| `MultiEffect` (shadow, blur, colorize, mask) | `QtGraphicalEffects 1.15`: `DropShadow`, `FastBlur`, `ColorOverlay`, `OpacityMask` |
| `RectangularShadow` | `DropShadow { source: card; cached: true }` |
| `VectorImage`, svgtoqml | `SvgIcon` (one color), `Image { source: "x.svg"; sourceSize }` (multi-color) |
| per-corner `radius` (`topLeftRadius` …) | `Shape` + `PathSvg` rounded-rect path, or a `radius` Rectangle plus square patches over the sharp corners |
| `Shape.CurveRenderer` | `layer.enabled: true; layer.samples: 4` on the Shape — group paths in one Shape, one layer each |
| `PathRectangle` | `PathSvg { path: "M … A …" }` |
| `Layout.horizontalStretchFactor` | `Layout.preferredWidth` in proportion + `Layout.fillWidth` |
| `font.variableAxes` | a static instance (match.py `--fonts-dir` writes them) |
| `QtCore` `Settings` | `import Qt.labs.settings 1.0` |
| `property list<string>` | `property var` |
| `Qt.alpha(c, a)` | `Theme.alpha(c, a)` |
| `a ??= b` | `a = a ?? b` |

Works the same on 5.15: `required property`, inline `component`, `?.` and `??`, arrow functions,
`Connections { function onX() {} }`, typed function parameters, Pointer Handlers, Layouts,
`QtQuick.Templates` (the whole kit), `Shape`/`PathAngleArc`/`PathSvg`, `Text` metrics.

`qt5.py port` does the import, pragma, qmldir and rendering-hint changes; the rest of the table
is hand work, and `qt5.py check` lists every place.

## Effects, icons and shapes on 5.15

- QtGraphicalEffects are shader effects: fine on `embedded-gpu`, never drawn by the software
  scene graph (`embedded-sw` → flat fallbacks, effects.md). Set `cached: true` on static
  shadows; `samples: 2 * radius + 1` for a smooth Gaussian.
- Icons: `SvgIcon { source: Qt.resolvedUrl("../../assets/icons/bell.svg"); width: 24; height: 24; color: Theme.muted }`.
  It rasterizes the SVG at its drawn size × DPR and tints it with `ColorOverlay`. Needs the SVG
  image plugin on the device (`libqt5svg5` / `qtsvg`). Icon fonts work as on Qt 6.
- Dials, rings, charts: one `Shape` per group of paths with a 4-sample layer for antialiasing
  (`examples/auto-cluster/project/qml/App/Dial.qml`); ticks as rotated `Rectangle`s with
  `antialiasing: true`.

## How the check loop verifies 5.15

- `render.py` renders the QML with PySide6; `assets/qt5-shim` maps `import QtGraphicalEffects
  1.15` to Qt 6's `Qt5Compat.GraphicalEffects`, so the diff and the gates run as usual.
- `lint` gate (`meta.minQt` 5.15): everything in `qt5.py check`, plus qmllint (Qt 6) on a copy
  with `pragma ComponentBehavior: Bound` added — code valid when bound is valid on 5.15.
- `cpp` gate: `check.py --qt <Qt 5.15 prefix>` (or a system Qt 5.15) builds the host, runs it
  headless and compares its frame with the PySide6 render by blurred 32-px tiles (limit 24): Qt
  5.15 lays text out up to ~1–2 px differently from Qt 6, so whole-frame SSIM is not the test.
  Its QML warnings fail the gate: this is the real 5.15 run. Without a Qt 5.15 SDK the gate is
  skipped with a note; say so in the README.

## Deploy

On a board the app links the image's Qt 5.15: `deploy.py out --target cpp --platform device`
writes the service and an `install.sh` that builds with it. A desktop bundle:
`deploy.py out --target cpp --platform desktop --build --qt <Qt 5.15>` installs to `dist/` and
runs `windeployqt` / `macdeployqt --qmldir qml` when the SDK has them.
