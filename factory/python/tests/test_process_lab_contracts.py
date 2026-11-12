"""Process lab increment 2 (design rev 4 §8-§9): the runtime loader validates the six lab contracts with the same
Draft 2020-12 + format checking as forge_factory.afo.contracts, and the spec fixtures behave as declared."""
from __future__ import annotations

import json

import pytest
from forge_factory.common import REPO_ROOT
from forge_factory.process_lab import contracts as C

FIXTURES = REPO_ROOT / "specs/014-durable-local-autonomy/contracts/examples"


def _lab_fixtures():
    manifest = json.loads((FIXTURES / "manifest.json").read_text())
    return [f for f in manifest["fixtures"] if f["schema"].startswith("runtime/")]


def test_every_runtime_contract_has_positive_and_negative_fixtures():
    by = {}
    for f in _lab_fixtures():
        by.setdefault(f["schema"].removeprefix("runtime/").removesuffix(".schema.json"), set()).add(f["expected_valid"])
    assert set(by) == set(C.NAMES)
    assert all(v == {True, False} for v in by.values())


@pytest.mark.parametrize("fixture", _lab_fixtures(), ids=lambda f: f["file"])
def test_fixture_result_matches_declaration(fixture):
    name = fixture["schema"].removeprefix("runtime/").removesuffix(".schema.json")
    doc = json.loads((FIXTURES / fixture["file"]).read_text())
    if fixture["expected_valid"]:
        assert C.require(name, doc) is doc
    else:
        with pytest.raises(C.ContractError) as exc:
            C.require(name, doc)
        assert str(exc.value).startswith(f"PROCESS_LAB_CONTRACT_INVALID:{name}:")


def test_unknown_contract_is_refused():
    with pytest.raises(C.ContractError, match="UNKNOWN_PROCESS_LAB_CONTRACT"):
        C.require("review-disposition", {})


def test_bad_date_time_is_rejected_by_format_checking():
    doc = json.loads((FIXTURES / "process-lab-disposition.valid.json").read_text())
    doc["decided_utc"] = "yesterday"
    with pytest.raises(C.ContractError):
        C.require("process-lab-disposition", doc)
