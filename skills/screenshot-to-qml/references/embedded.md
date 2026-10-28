# Embedded targets (Raspberry Pi, Jetson, i.MX, kiosks)

## Contents
- Profiles
- What the checks enforce
- Running on the board
- Performance budget

## Profiles

Set `meta.profile` in the spec and pass `--profile` to `scaffold.py`; both hosts then default to
the right scene graph and `check.py` checks the rules below. A board whose image ships Qt 5.15
(many automotive and industrial BSPs) also needs `--min-qt 5.15` (**target-qt5.md**).

| Profile | Hardware | Rendering | Rules |
| --- | --- | --- | --- |
| `desktop` | PCs, laptops | RHI (OpenGL, Vulkan, Metal, D3D) | anything in effects.md |
| `embedded-gpu` | RPi 4/5, Jetson Nano/Orin, i.MX8 | RHI / OpenGL ES via `eglfs` | shadows (`RectangularShadow` from Qt 6.9, `MultiEffect` shadow on 6.8) and gradients fine; no blur; ≤ 4 layers; touch targets ≥ 44 px |
| `embedded-sw` | no GPU, or a broken GPU driver | software scene graph (`QT_QUICK_BACKEND=software`), `linuxfb` | no shader effects at all: flat colors, borders and gradients only |

## What the checks enforce

`check.py` reads the profile from the spec:

- `embedded-sw` renders with the software scene graph (`render.py --scenegraph software`), so the
  diff scores what the device will draw, not what a desktop GPU draws.
- gate `effects`: `MultiEffect`, `RectangularShadow`, `ShaderEffect`, `layer.effect` and
  `Qt5Compat.GraphicalEffects` are errors on `embedded-sw` (the software scene graph skips
  them); blur and more than four `layer.enabled` items are warnings on `embedded-gpu`.
- gate `perf` (from the render): images decoded ≥ 4× the pixels they are drawn with (missing
  `sourceSize`) are errors on embedded profiles; infinite animations and timers faster than
  250 ms running while nothing happens, many layers, > 3000 items and a first frame later than
  1.5 s are warnings.
- gate `a11y`: touch targets under 44 px are warnings; hover is not required.

Flat fallbacks for `embedded-sw`: a shadow becomes a 1 px darker border or a second rect
offset by 1–2 px; glass becomes an opaque tint; a glow becomes nothing. List them in the README.

## Running on the board

`deploy.py PROJECT --target pyside6|cpp --platform device` writes `deploy/device/`: `app.env`,
`kms.json`, a systemd unit and `install.sh` (see deploy.md). By hand:

```bash
export QT_QPA_PLATFORM=eglfs          # GPU, full screen, no desktop (embedded-gpu)
export QT_QPA_EGLFS_INTEGRATION=eglfs_kms   # Jetson: eglfs_kms_egldevice
export QT_QPA_EGLFS_HIDECURSOR=1
# embedded-sw: QT_QPA_PLATFORM=linuxfb QT_QUICK_BACKEND=software
python3 main.py        # or ./build/<app>
```

- Full screen: `visibility: Window.FullScreen` in `Main.qml`; the canvas layout scales to the panel.
- Rotated panels: rotate in QML. `QT_QPA_EGLFS_ROTATION` only rotates QWidget content, not Qt
  Quick. In the canvas `Main.qml`, give the stage `rotation: 90` and swap the fit calculation's
  width and height. Rotate touch with
  `QT_QPA_EVDEV_TOUCHSCREEN_PARAMETERS=/dev/input/eventX:rotate=90` when libinput does not.
- Qt versions decide the host. PySide6's aarch64 wheels need glibc 2.31 up to 6.8.0.2 and 2.39
  from 6.8.1, so pip installs 6.8.0.2 on older boards (the project asks for `>=6.8`):

  | Board OS | System Qt | PySide6 host (pip) | C++ host |
  | --- | --- | --- | --- |
  | Raspberry Pi OS / Debian 12 (Bookworm) | 6.4 | 6.8.0.2 (glibc 2.36) | cross-compiled or self-built Qt 6.8 |
  | Raspberry Pi OS / Debian 13 (Trixie) | 6.8 | current | the system Qt |
  | Jetson JetPack 6 (Ubuntu 22.04) | 6.2 | 6.8.0.2 (glibc 2.35) | cross-compiled or self-built Qt 6.8 |
  | Ubuntu 24.04 | 6.4 | current | Qt from the online installer or aqt |

  Cross-compiled Qt: Yocto `meta-qt6` or Buildroot; build the app with `-DS2Q_DEPLOY_QT=OFF`.
- GPU driver problems: `QT_QUICK_BACKEND=software` for a quick test, then fix the driver
  (vc4-kms-v3d overlay on a Pi, JetPack's EGL on a Jetson).

## Performance budget

- Keep the scene small: prefer `Rectangle`/`Text`/`Image` over `Shape` for boxes.
- `clip: true` and `layer.enabled` each add a render pass; use them only where the design needs them.
- Long lists: `ListView` with `reuseItems: true` and fixed-height delegates.
- Load secondary screens with `Loader { asynchronous: true }`.
- Animate `opacity`, `x/y`, `scale` (cheap); avoid animating sizes that relayout. Stop
  decorative animations when the screen is idle.
- Images: `sourceSize` = displayed size × DPR; `asynchronous: true` for large ones.
- Measure on the device: `QSG_RENDER_TIMING=1` prints frame times; aim for < 16 ms. The C++
  host starts faster (compiled QML, no Python start-up), which matters on a Pi.
