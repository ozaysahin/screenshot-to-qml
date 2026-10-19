import json

import jsonschema
import pytest

from conftest import EVALS, EXAMPLE, SKILL

SCHEMA = json.loads((SKILL / "assets" / "schema" / "design-spec.schema.json").read_text())
SPECS = sorted(EVALS.glob("cases/*/golden-spec.json")) + [EXAMPLE / "design-spec.json"]


def test_schema_is_valid():
    jsonschema.Draft202012Validator.check_schema(SCHEMA)


@pytest.mark.parametrize("path", SPECS, ids=lambda p: p.parent.name)
def test_specs_validate(path):
    jsonschema.validate(json.loads(path.read_text()), SCHEMA)


@pytest.mark.parametrize("path", sorted(EVALS.glob("cases/*")), ids=lambda p: p.name)
def test_case_files_complete(path):
    for name in ("input.png", "golden-spec.json", "expected.json", "thresholds.json", "source/index.html"):
        assert (path / name).exists(), f"{path.name} is missing {name}"
    meta = json.loads((path / "golden-spec.json").read_text())["meta"]
    import cv2
    img = cv2.imread(str(path / "input.png"))
    assert [img.shape[1], img.shape[0]] == meta["captureSize"]
