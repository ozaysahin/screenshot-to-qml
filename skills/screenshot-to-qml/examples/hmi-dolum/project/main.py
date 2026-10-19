"""Application entry point.

- Loads every font in assets/fonts (no hard-coded file list) and logs the family
  names Qt reports; QML must use those names (see Theme.qml).
- Installs the translation for the system locale from i18n/app_<locale>.qm when present
  (APP_LANG=en overrides; see the skill's references/a11y-i18n.md for lupdate/lrelease).
- Registers qml/ as an import path and loads the `App` module's Main.qml.
- Exits non-zero when QML fails to load, so CI and render checks catch it.

The C++ host (CMakeLists.txt + src/main.cpp, when present) runs the same qml/ tree.

Environment:
  APP_LOG=DEBUG         more logging
  APP_LANG=en           UI language (default: system locale)
  QT_QUICK_BACKEND=software   GPU-less rendering (the default for the embedded-sw profile)
  APP_GRAB=out.png      render one frame to a PNG and exit (checks a packaged build);
                        APP_GRAB_SIZE=1920x1080, APP_GRAB_WAIT_MS=500, QT_SCALE_FACTOR=2
"""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from PySide6.QtCore import QCoreApplication, QLocale, QTranslator
from PySide6.QtGui import QFontDatabase, QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickWindow  # noqa: F401  (makes the root a QQuickWindow for grabWindow)

BASE_DIR = Path(__file__).resolve().parent
FONT_DIR = BASE_DIR / "assets" / "fonts"
QML_DIR = BASE_DIR / "qml"
I18N_DIR = BASE_DIR / "i18n"
FONT_SUFFIXES = {".ttf", ".otf", ".ttc"}
APP_PROFILE = "embedded-gpu"   # desktop | embedded-gpu | embedded-sw (from the design spec)

log = logging.getLogger("app")


def load_fonts(folder: Path) -> dict[str, list[str]]:
    """Register every font file in `folder`; return {file name: [families]}."""
    loaded: dict[str, list[str]] = {}
    if not folder.is_dir():
        log.warning("font folder missing: %s", folder)
        return loaded
    for path in sorted(p for p in folder.iterdir() if p.suffix.lower() in FONT_SUFFIXES):
        font_id = QFontDatabase.addApplicationFont(str(path))
        if font_id == -1:
            log.warning("font not loaded: %s", path.name)
            continue
        loaded[path.name] = QFontDatabase.applicationFontFamilies(font_id)
    return loaded


def install_translation(app: QGuiApplication) -> QTranslator | None:
    """Load i18n/app_<locale>.qm for APP_LANG or the system locale; keep the source strings otherwise."""
    locale = QLocale(os.environ["APP_LANG"]) if os.environ.get("APP_LANG") else QLocale.system()
    translator = QTranslator(app)
    if translator.load(locale, "app", "_", str(I18N_DIR)):
        app.installTranslator(translator)
        log.debug("translation %s loaded", translator.filePath())
        return translator
    return None


def main() -> int:
    logging.basicConfig(level=os.environ.get("APP_LOG", "INFO").upper(), format="[%(levelname)s] %(message)s")
    if APP_PROFILE == "embedded-sw":
        os.environ.setdefault("QT_QUICK_BACKEND", "software")   # no GPU: software scene graph
    QCoreApplication.setOrganizationName("Nova Makine")
    QCoreApplication.setApplicationName("Hat 3 Dolum HMI")
    app = QGuiApplication(sys.argv)

    for file_name, families in load_fonts(FONT_DIR).items():
        log.debug("font %s -> %s", file_name, ", ".join(families))
    install_translation(app)

    engine = QQmlApplicationEngine()
    engine.addImportPath(str(QML_DIR))
    engine.loadFromModule("App", "Main")
    if not engine.rootObjects():
        log.error("QML failed to load; see warnings above")
        return 1
    if os.environ.get("APP_GRAB"):
        grab_frame(app, engine.rootObjects()[0], os.environ["APP_GRAB"])
    return app.exec()


def grab_frame(app: QGuiApplication, window, path: str) -> None:
    """APP_GRAB: show the window at APP_GRAB_SIZE, save one frame, quit (same contract as the C++ host)."""
    from PySide6.QtCore import QTimer
    size = os.environ.get("APP_GRAB_SIZE", "")
    if "x" in size:
        w, h = (int(v) for v in size.split("x", 1))
        window.resize(w, h)
        window.setWidth(w)
        window.setHeight(h)
    window.show()

    def save() -> None:
        img = window.grabWindow()
        ok = not img.isNull() and img.save(path)
        print(f"grabbed {path} ({img.width()}x{img.height()})")
        app.exit(0 if ok else 2)
    QTimer.singleShot(int(os.environ.get("APP_GRAB_WAIT_MS", "500")), save)


if __name__ == "__main__":
    sys.exit(main())
