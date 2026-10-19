# Controls Gallery

Native Qt Quick UI generated with screenshot-to-qml.

## Run

```bash
pip install -r requirements.txt
python main.py                          # APP_LANG=tr for Turkish
```

C++ (Qt 6.8+):

```bash
cmake -S . -B build -G Ninja && cmake --build build && ./build/controls-gallery
```

Headless check: `python <skill>/scripts/render.py . --size 1200 760` and
`python <skill>/scripts/build_cpp.py . --grab cpp.png --size 1200 760 --compare render.png`

## Structure

- `qml/App/Style` — Theme (all tokens) and Icons
- `qml/App/Controls` — reusable controls built on QtQuick.Templates
- `qml/App` — screens and screen-specific components
- `assets/fonts` — bundled fonts, loaded by `main.py` from the folder (embedded in the C++ binary)
- `main.py` — PySide6 host; `CMakeLists.txt`, `src/main.cpp`, `cmake/` — C++ host

## Fidelity report

<!-- filled in by the agent: measured metrics, assumed values, approximations -->
