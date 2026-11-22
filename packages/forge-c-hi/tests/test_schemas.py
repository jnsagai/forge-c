"""T005 + T010: contract schemas are well-formed, identical to the feature contracts, and discriminate samples."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from conftest import FIXTURES, PKG, REFS
from forge_hi.jsonschema_lite import validate

import sys

sys.path.insert(0, str(FIXTURES))
from contract_samples import INVALID, VALID  # noqa: E402

SCHEMAS = REFS / "schemas"
FEAT_CONTRACTS = PKG.parents[1] / "specs" / "023-high-integrity-vmodel-skills" / "contracts"


def load(name: str) -> dict:
    return json.loads((SCHEMAS / f"{name}.schema.json").read_text())


def test_runtime_schemas_match_feature_contracts():
    if not FEAT_CONTRACTS.is_dir():
        pytest.skip("feature contracts not present (installed package)")
    for f in sorted(FEAT_CONTRACTS.glob("*.schema.json")):
        assert (SCHEMAS / f.name).read_bytes() == f.read_bytes(), f.name


def test_schemas_pass_metaschema_when_jsonschema_available():
    jsonschema = pytest.importorskip("jsonschema")
    for f in SCHEMAS.glob("*.schema.json"):
        jsonschema.Draft202012Validator.check_schema(json.loads(f.read_text()))


@pytest.mark.parametrize("name", sorted(VALID))
def test_valid_samples(name):
    assert validate(VALID[name], load(name)) == []


@pytest.mark.parametrize("name,doc,why", INVALID, ids=[w for _, _, w in INVALID])
def test_invalid_samples(name, doc, why):
    assert validate(doc, load(name)) != [], why
