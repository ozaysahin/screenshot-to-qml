# Controls gallery

Every control of the kit (`assets/templates/project/qml/App/Controls`) in its default, checked,
error and disabled states, themed from `design-spec.json` with `gen_theme.py`. The source
strings are English; `project/i18n/app_tr.qm` is the Turkish translation.

```bash
cd project
python main.py                 # English (or your system locale when a translation exists)
APP_LANG=tr python main.py     # Turkish
```

Checked with `render.py --interact`, `build_cpp.py` and `quality_gate.py`: all 13 gates pass. The
project has both hosts; the C++ build (Qt 6.8.3) draws the same frame as PySide6, in English and
with the embedded Turkish translation (`APP_LANG=tr`): SSIM 1.000.

- Tab reaches all 27 enabled controls, and each one visibly changes on focus, hover and press.
- Every control has an accessible name.
- Every string goes through `qsTr()`.

`docs/tools/controls_image.py` builds `docs/img/controls.png` from this project.
