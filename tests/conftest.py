import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SKILL = ROOT / "skills" / "screenshot-to-qml"
SCRIPTS = SKILL / "scripts"
EXAMPLE = SKILL / "examples" / "hmi-dolum"
EVALS = ROOT / "evals"
sys.path.insert(0, str(SCRIPTS))


def can_render() -> bool:
    import os
    import platform
    if platform.system() in ("Windows", "Darwin") or os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"):
        return True
    return shutil.which("xvfb-run") is not None


requires_render = pytest.mark.skipif(not can_render(), reason="needs a display or xvfb-run")


@pytest.fixture
def tiny_spec():
    return {
        "meta": {"designSize": [200, 120], "dpr": 1},
        "tokens": {"color": {}},
        "nodes": [
            {"id": "card", "role": "Panel", "parent": None, "bbox": [20, 20, 120, 80],
             "style": {"fill": {"hex": "#3366CC", "alpha": 1}, "radius": 0}},
        ],
        "text": [],
    }
