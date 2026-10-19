# Target: C++ (CMake)

One project, two hosts: the `qml/` tree, `assets/`, `i18n/` and `mock/` are shared; `main.py`
runs them with PySide6, `CMakeLists.txt` + `src/main.cpp` compile them into one executable.
Build and check the QML with the PySide6 host as usual; the C++ host runs the same files,
within the limits under Pitfalls, and `check.py` proves it frame by frame.

## Contents
- Create
- What the CMake project does
- Build, run, check
- C++ backends
- Pitfalls

## Create

```bash
python <skill>/scripts/scaffold.py out/ --name "Line 3 HMI" --target cpp|both --profile embedded-gpu
python <skill>/scripts/scaffold.py out/ --add-host cpp --name "Line 3 HMI"   # a PySide6 project made earlier
```

Files: `CMakeLists.txt` (Qt 6.8+, `qt_standard_project_setup(REQUIRES 6.8)`), `src/main.cpp`,
`cmake/S2qQml.cmake`. Nothing in `qml/` changes.

## What the CMake project does

- **Every folder with a `qmldir` becomes a QML module** (`S2qQml.cmake`): a static library +
  plugin through `qt_add_qml_module`, URI and singletons read from the `qmldir`, so it stays
  the single source of truth. QML is compiled ahead of time (`qmlcachegen`: faster start,
  errors at build time). Local modules a file imports become `DEPENDENCIES`.
- **Resources keep the project's layout** under `:/qt/`: `qml/App/…` at `:/qt/qml/App/…`,
  `assets/` at `:/qt/assets/`, `i18n/*.qm` at `:/qt/i18n/`, `mock/` at `:/qt/mock/`. A relative URL
  in QML (`"../../assets/img/logo.svg"`) resolves the same way in both hosts. Files inside a
  module folder (images next to a component) are that module's `RESOURCES`.
- **`src/main.cpp` mirrors `main.py`**: registers the embedded fonts (plus a `fonts/` folder next to
  the executable), installs `app_<locale>.qm` (`APP_LANG` overrides), loads `App`/`Main`, exits 1
  when QML fails to load, and uses the software scene graph by default for `embedded-sw`
  (`S2Q_PROFILE`, set from `--profile`).
- **Both hosts grab frames the same way** for checks: `APP_GRAB=out.png`, `APP_GRAB_SIZE=WxH`,
  `APP_GRAB_WAIT_MS`, `QT_SCALE_FACTOR` for the DPR.
- **Install**: `cmake --install build --prefix dist`. With Qt from an SDK (online installer,
  `aqt`) this also bundles Qt's libraries, plugins and QML modules
  (`qt_generate_deploy_qml_app_script`). With a system Qt (`/usr`: a distro, Yocto, Buildroot)
  or when cross-compiling, only the app is installed (`S2Q_DEPLOY_QT=OFF`); the OS provides Qt.

## Build, run, check

```bash
cmake -S out -B build -G Ninja -DCMAKE_PREFIX_PATH=$HOME/Qt/6.8.3/gcc_64   # omit for a system Qt 6.8+
cmake --build build && ./build/line-3-hmi
python <skill>/scripts/build_cpp.py out --grab c.png --size 1920 1080 [--qt …]   # build + one frame
python <skill>/scripts/check.py out --source input.png --spec design-spec.json [--qt …]
```

`check.py` builds the C++ host when `CMakeLists.txt` exists, grabs it at the spec's size and DPR,
and compares it with the PySide6 render (gate `cpp`): build errors, QML warnings in the C++
run and SSIM < 0.98 fail it. The same QML gives the same pixels (the example: SSIM 1.000 between
Qt 6.8.3 C++ and PySide6 6.11), so a drop means a file did not make it into the binary. Without a
Qt 6 SDK the gate is skipped with a note; the PySide6 checks still run.

Qt 6.8 is the floor: Ubuntu 24.04 and Debian 12 ship older Qt, so use the Qt online installer,
`aqt install-qt linux desktop 6.8.3 linux_gcc_64`, or a newer distro.

## C++ backends

Keep the UI pure QML with `MockData.qml` until the data is real. Then add a module with C++
types next to the QML ones:

```cmake
qt_add_library(app_data STATIC)
qt_add_qml_module(app_data URI App.Data VERSION 1.0
    OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/qml/App/Data     # where the other modules are, for qmlcachegen
    SOURCES src/linestatus.h src/linestatus.cpp)
target_link_libraries(app PRIVATE app_dataplugin)
```

```cpp
class LineStatus : public QObject {
    Q_OBJECT
    QML_ELEMENT
    QML_SINGLETON
    Q_PROPERTY(double speed READ speed NOTIFY speedChanged)   // same names MockData used
    …
};
```

add `Q_IMPORT_QML_PLUGIN(App_DataPlugin)` in `main.cpp`, and replace `MockData` with
`LineStatus` in QML. The PySide6 host (and `render.py`) cannot load C++ types, so keep
`MockData.qml` for design checks, or register a Python twin with `render.py --backend
backend.py`. From then on the C++ binary's frame (`build_cpp.py --grab`) is the one to diff.

## Pitfalls

- A QML file outside every `qmldir` folder is not compiled into the binary; put components in
  a module folder. Plain subfolders of a module (`import "parts"`) are included.
- Absolute `file:` URLs and paths built from `Qt.resolvedUrl("../..")` beyond the project do not
  exist in the binary; keep files under `qml/`, `assets/`, `i18n/`, `mock/`.
- Translations are embedded as `.qm`: run `lrelease` before building.
- `qmlcachegen` warnings are build warnings (the `cpp` gate lists them): they usually mean a
  type it could not resolve (a missing import) and the function falls back to the interpreter.
