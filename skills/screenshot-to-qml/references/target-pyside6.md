# Target: PySide6

## Project layout (scripts/scaffold.py creates it)

```
main.py                 loads assets/fonts/*, adds qml/ import path, loadFromModule("App", "Main")
requirements.txt        PySide6-Essentials>=6.8 (+ PySide6-Addons for Qt Graphs)
pyproject.toml          [tool.pyside6-project] for pyside6-project / pyside6-deploy
README.md               run instructions + fidelity report
qml/App/…               modules App, App.Controls, App.Style (tokens-theming.md)
assets/fonts/           bundled fonts
assets/icons/           SVG sources (when not using an icon font)
mock/                   sample data (JSON) used until a backend exists
```

`engine.loadFromModule("App", "Main")` (Qt 6.5+) resolves `qml/App/qmldir`; keep every QML file
listed in its module's `qmldir`.

## Data: mock first, backend later

Screens bind to a data API, not to literals. Start with a QML singleton (`MockData.qml`) that
exposes properties (`tanks`, `alarms`, `kpis` as JS arrays of objects). When the real data
arrives, replace it with a Python backend that exposes the same names:

```python
# backend.py
from PySide6.QtCore import QObject, Property, Signal
from PySide6.QtQml import QmlElement, QmlSingleton

QML_IMPORT_NAME = "App.Data"
QML_IMPORT_MAJOR_VERSION = 1

@QmlElement
@QmlSingleton
class LineData(QObject):
    tanksChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._tanks = [{"name": "Tank A", "level": 0.72}]

    @Property("QVariantList", notify=tanksChanged)
    def tanks(self):
        return self._tanks
```

Import `backend` in `main.py` before `loadFromModule`, and `import App.Data` in QML. For large
or frequently changing lists use a `QAbstractListModel` (or `QRangeModel`, Qt 6.10+) instead of
QVariantList. `render.py --backend backend.py` imports it for checks.

qmllint cannot see Python-registered types by default. Type info for them comes from
`pyside6-metaobjectdump` + `pyside6-qmltyperegistrar` (`pyside6-project` drives these for QML
module projects, see `pyside6-project --help`); until that is set up, lint against the mock
singleton, which exposes the same property names.

## Run, package, deploy

```bash
pip install -r requirements.txt
python main.py                               # windowed
QT_QUICK_BACKEND=software python main.py     # GPU-less machines (no shader effects)
pyside6-deploy main.py                       # Nuitka-based standalone build (see pyside6-deploy --help)
```

Resources: plain files next to `main.py` are fine for apps; for single-file deployment compile a
`.qrc` with `pyside6-rcc` and switch paths to `qrc:/`.

## Versions

Minimum Qt 6.8 LTS by default (VectorImage, PathRectangle, loadFromModule, CurveRenderer).
Newer features are used only when `PySide6.__version__` allows (see SKILL.md version table).
On Raspberry Pi OS the distro packages (`python3-pyside6.*`) may be older than 6.8 — check
before using 6.8+ types, or install from pip in a venv.
