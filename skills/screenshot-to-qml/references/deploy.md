# Deploy

`scripts/deploy.py PROJECT --target pyside6|cpp --platform desktop|device` writes the packaging
files for one host and one kind of machine; `--build` also builds the desktop bundle.

## Contents
- Choosing the path
- Desktop: PySide6 (pyside6-deploy)
- Desktop: C++ (cmake --install)
- Device: kiosk service on a Linux board
- Checking a package

## Choosing the path

| Machine | Host | Result |
| --- | --- | --- |
| Windows / macOS / Linux PC | pyside6 | `pyside6-deploy` (Nuitka) folder or single file; no Python needed on the PC |
| Windows / macOS / Linux PC | cpp | `cmake --install` folder with Qt bundled (Qt from the online installer or aqt) |
| Linux board (Pi OS, JetPack, Ubuntu) | pyside6 | `deploy/device/install.sh`: venv + pip (PySide6 6.8.0.2 on glibc < 2.39: Bookworm, JetPack 6) |
| Board with a system Qt 6.8+ (Debian 13 / Pi OS Trixie) | cpp | `install.sh` builds natively against the board's Qt |
| Board without Qt 6.8 (Bookworm, JetPack 6, Ubuntu 24.04) | cpp | a cross-compiled Qt (Yocto `meta-qt6`, Buildroot) or a Qt 6.8 build on the board; app built with `-DS2Q_DEPLOY_QT=OFF` |

Build for the platform you ship to: neither path cross-compiles Python, and a desktop bundle
made on Linux only runs on Linux.

## Desktop: PySide6 (pyside6-deploy)

```bash
python <skill>/scripts/deploy.py out --target pyside6 --platform desktop --name "Line 3 HMI" [--mode onefile] --build
```

- Writes `pysidedeploy.spec` (made by `pyside6-deploy --init`, then adjusted): title, `dist/`
  output, standalone (a folder, default) or onefile, and `--include-data-dir` for `qml/`,
  `assets/`, `i18n/`, `mock/` (the spec's own `qml_files` list has no `qmldir` files and no fonts).
- `excluded_qml_plugins` lists the heavy Qt modules the QML never imports (Qt 3D, Charts,
  WebEngine, Multimedia …).
- pyside6-deploy ships every project subfolder as data; the spec adds
  `--noinclude-data-files` for `src/`, `cmake/`, `build/`, `deploy/` and `dist/`, so the C++ host
  and earlier builds stay out (hidden folders such as `.check/` are skipped anyway).
- `--build` runs `pyside6-deploy -c pysidedeploy.spec -f` (downloads Nuitka on first use; several
  minutes). Result:
  `dist/<name>.dist/main.bin` (standalone) or `dist/<name>.bin`/`.exe` (onefile). Only output
  newer than the run counts: pyside6-deploy can exit 0 when Nuitka failed.
- Nuitka prints "Duplicate data file" warnings for QML files the spec lists twice; they are harmless.

## Desktop: C++ (cmake --install)

```bash
python <skill>/scripts/deploy.py out --target cpp --platform desktop --build [--qt ~/Qt/6.8.3/gcc_64]
# = build_cpp.py out --install out/dist
```

The executable already carries QML, fonts and translations. With Qt from an SDK, the install
step runs `qt_generate_deploy_qml_app_script`: Qt libraries, platform plugins and the QML
modules the app imports are copied next to it (`dist/bin`, `dist/lib`, `dist/plugins`,
`dist/qml`). A system Qt (prefix `/usr`) is never bundled: the target machine must have the same
Qt. Windows/macOS: build on that OS; the target is a GUI executable (`WIN32_EXECUTABLE`) and an
app bundle (`MACOSX_BUNDLE`), and the same script produces a `windeployqt`/`macdeployqt`-style
folder or `.app`.

## Device: kiosk service on a Linux board

```bash
python <skill>/scripts/deploy.py out --target cpp --platform device --name "Line 3 HMI" \
       [--profile embedded-gpu] [--display eglfs|linuxfb|wayland|xcb] [--gpu kms|jetson] [--user kiosk]
# copy the project to the board, then:  sudo sh deploy/device/install.sh
```

`deploy/device/`:

- `app.env` — `QT_QPA_PLATFORM`: `eglfs` (GPU, full screen, no compositor; the embedded-gpu
  default) with `eglfs_kms` (Raspberry Pi, Mesa) or `eglfs_kms_egldevice` (`--gpu jetson`),
  `linuxfb` + `QT_QUICK_BACKEND=software` for embedded-sw, or `wayland`/`xcb` under a compositor
  (set `XDG_RUNTIME_DIR` / `XAUTHORITY` for the compositor's user);
  hidden cursor; commented lines for evdev touch, rotation, language, and Qt platform logging.
- `kms.json` — eglfs_kms output (`HDMI1`, preferred mode); edit `name` for DSI panels (`DSI1`).
- `<slug>.service` — systemd unit: user `kiosk` in `video`, `render` and `input`; takes tty1 from
  getty (`TTYPath` + `StandardInput=tty`, reset and hung up on exit), restarts on crash, logs to
  the journal. `ExecStart` uses the executable name from `CMakeLists.txt` (`OUTPUT_NAME`).
- `install.sh` — creates the user, copies the app to `/opt/<slug>`, then either creates a venv
  and installs `requirements.txt` (pyside6) or builds with the board's Qt and installs
  (cpp), and enables the service.

On the board: `systemctl status <slug>`, `journalctl -u <slug> -f`. A black screen with eglfs is
usually the KMS device or connector name: run once with `QT_LOGGING_RULES=qt.qpa.*=true`.

## Checking a package

Both hosts grab a frame when `APP_GRAB=out.png` is set (`APP_GRAB_SIZE=WxH`, `QT_SCALE_FACTOR`
for the DPR), so a built package can be diffed like the project:

```bash
APP_GRAB=pkg.png APP_GRAB_SIZE=1920x1080 "dist/Line 3 HMI.dist/main.bin"
python <skill>/scripts/diff.py input.png pkg.png --spec design-spec.json
```

A blank or font-less frame means the package lost files (fonts, `qmldir`, translations).
