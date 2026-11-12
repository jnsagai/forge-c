"""Feature 020 T008 (US1, FR-001..FR-003, FR-009..FR-012, SC-009): the deterministic governance inventory.

`prepare` of a functional-level order writes `inputs/governance-inventory.json` as a listed, fingerprinted input:
the input register (delivered code only as implementation under analysis), the delivered public API (HAL from the
delivery scope, LL inline functions from the delivered header) classified by the order's scope rule (exact names and
`prefix*` patterns), the in/out RM features and the not-delivered list. An unclassifiable function, a pattern that
matches nothing or a file no component owns is refused with INPUT_GAP naming it, before any workspace exists. The same
code prepares a second, different module (synthetic TMR) with only its own data."""
from __future__ import annotations

import json

import jsonschema
import pytest
from f020_fixtures import SER_HAL, SER_LL, SER_OUT, TMR_LL, example, ser_spec, tmr_spec
from forge_factory import workorder as WO
from forge_factory.common import REPO_ROOT, sha256_file, state_dir

INV = "inputs/governance-inventory.json"
SCHEMA = json.loads((REPO_ROOT / "specs/020-usart-benchmark-pilot/contracts/governance-inventory.schema.json")
                    .read_text())
DELIVERED = {"software/hal/ser_hal.c", "software/hal/ser_hal.h", "software/ll/ser_ll.h"}


@pytest.fixture(autouse=True)
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("FORGE_EVENTS_DIR", str(tmp_path / "state/events"))


def _inventory(tmp_path, spec=None, wo="WO-F020-I1"):
    ws, man = WO.prepare(example(tmp_path, spec), wo)
    return ws, man, json.loads((ws / INV).read_text())


def test_the_inventory_is_a_listed_fingerprinted_input_valid_against_the_contract(tmp_path):
    ws, man, inv = _inventory(tmp_path)
    jsonschema.Draft202012Validator(SCHEMA).validate(inv)
    rec = next(i for i in man["inputs"] if i["path"] == INV)
    assert rec["role"] == "governance_inventory" and rec["sha256"] == sha256_file(ws / INV)
    assert inv["module"] == "SER"


def test_the_input_register_lists_the_delivered_code_only_as_implementation_under_analysis(tmp_path):
    _ws, man, inv = _inventory(tmp_path)
    by_name = {i["name"]: i for i in inv["inputs"]}
    assert [i["input_id"] for i in inv["inputs"]] == [f"IN-{n:02d}" for n in range(1, len(inv["inputs"]) + 1)]
    delivered = {i["name"] for i in inv["inputs"] if i["role"] == "implementation_under_analysis"}
    assert delivered == DELIVERED
    sources = {i["name"] for i in inv["inputs"] if i["role"] == "requirement_source"}
    assert sources == {"DS9999-rev1-datasheet.md", "RM9999-rev2-ch42-ser.md", "RM9999-rev2-memory-map-ser.md",
                       "ser_device.h", "hal_guideline.md"}
    assert "inputs-manifest.json" not in by_name  # conversion provenance is no requirement source
    shas = {d["path"]: d["sha256"] for d in man["delivered"]}
    assert all(by_name[p]["sha256"] == shas[p] for p in DELIVERED)
    rm = by_name["RM9999-rev2-ch42-ser.md"]
    assert rm["revision"] == "Rev 2" and rm["bytes"] > 0
    assert {"section": "42.3.1", "title": "Transmitter", "page": 411} in rm["sections"]
    assert "sections" not in by_name["hal_guideline.md"]


def test_every_delivered_public_function_is_classified_by_the_scope_rule(tmp_path):
    _ws, _man, inv = _inventory(tmp_path)
    api = {a["function"]: a for a in inv["api"]}
    assert set(api) == set(SER_HAL) | set(SER_LL)  # the static helper SER_SetConfig is not public API
    assert {f for f, a in api.items() if a["scope_class"] == "out"} == set(SER_OUT)
    assert api["LL_SER_IsActiveFlag_TXE"]["scope_group"] == "ll data and flags"  # a prefix* pattern
    assert api["LL_SER_IsEnabledLoop"]["scope_group"] == "loopback"  # LL_SER_*Loop
    assert api["HAL_SER_Init"] == {"function": "HAL_SER_Init", "component": "HAL_SER", "file": "software/hal/ser_hal.c",
                                   "scope_class": "in", "scope_group": "initialisation"}
    assert api["LL_SER_SetBaud"]["component"] == "LL_SER" and api["LL_SER_SetBaud"]["file"] == "software/ll/ser_ll.h"
    assert inv["rm_features"] == [{"feature": "42.1", "scope_class": "in"}, {"feature": "42.3.1", "scope_class": "in"},
                                  {"feature": "42.3.2", "scope_class": "in"}, {"feature": "42.3.5", "scope_class": "out"}]
    assert inv["not_delivered"] == ser_spec()["scope_rule"]["not_delivered"]


def _gap(tmp_path, mutate, wo="WO-F020-I2"):
    spec = ser_spec()
    mutate(spec)
    with pytest.raises(ValueError) as exc:
        WO.prepare(example(tmp_path, spec), wo)
    assert not (state_dir() / "workorders" / wo / "workspace").exists()
    return str(exc.value)


def test_an_unclassified_function_is_an_input_gap_naming_it(tmp_path):
    msg = _gap(tmp_path, lambda s: s["scope_rule"]["in"].pop(2))  # the "state" group: HAL_SER_GetState
    assert msg.startswith("INPUT_GAP:") and "GOVERNANCE_FUNCTION_UNCLASSIFIED:HAL_SER_GetState" in msg


@pytest.mark.parametrize("entry", ["LL_SER_Frobnicate*", "HAL_SER_Abort"])
def test_a_scope_entry_that_matches_nothing_is_an_input_gap_naming_it(tmp_path, entry):
    msg = _gap(tmp_path, lambda s: s["scope_rule"]["in"][0]["functions"].append(entry))
    assert f"INPUT_GAP:GOVERNANCE_SCOPE_ENTRY_MATCHES_NOTHING:{entry}" in msg


def test_a_function_in_two_groups_is_an_input_gap(tmp_path):
    msg = _gap(tmp_path, lambda s: s["scope_rule"]["in"][2]["functions"].append("HAL_SER_EnableLoop"))
    assert "GOVERNANCE_FUNCTION_AMBIGUOUS:HAL_SER_EnableLoop" in msg


def test_components_must_cover_exactly_the_delivered_files(tmp_path):
    msg = _gap(tmp_path, lambda s: s["module"]["components"][0]["files"].remove("software/hal/ser_hal.h"))
    assert "GOVERNANCE_FILE_WITHOUT_COMPONENT:software/hal/ser_hal.h" in msg
    msg = _gap(tmp_path, lambda s: s["module"]["components"][1]["files"].append("software/ll/ser_ll_ex.h"),
               wo="WO-F020-I3")
    assert "GOVERNANCE_COMPONENT_FILE_NOT_DELIVERED:software/ll/ser_ll_ex.h" in msg


def test_an_rm_feature_the_inputs_do_not_have_is_an_input_gap(tmp_path):
    msg = _gap(tmp_path, lambda s: s["scope_rule"]["in"][0]["rm_features"].append("42.9"))
    assert "GOVERNANCE_RM_FEATURE_UNKNOWN:42.9" in msg


def test_the_same_code_prepares_a_second_different_module(tmp_path):
    ws, man, inv = _inventory(tmp_path, tmr_spec(), wo="WO-F020-I4")
    jsonschema.Draft202012Validator(SCHEMA).validate(inv)
    api = {a["function"]: a for a in inv["api"]}
    assert inv["module"] == "TMR" and set(api) == set(TMR_LL)
    assert api["LL_TMR_ClearFlag_UPD"]["scope_group"] == "flags" and api["LL_TMR_EnableOnePulse"]["scope_class"] == "out"
    assert {i["name"] for i in inv["inputs"] if i["role"] == "implementation_under_analysis"} == {"software/ll/tmr_ll.h"}
    assert man["swe1_level"] == "functional"


def test_a_register_level_order_gets_no_inventory(tmp_path):
    ws, man = WO.prepare(example(tmp_path, ser_spec(functional=False)), "WO-F020-I5")
    assert not (ws / INV).exists() and all(i["path"] != INV for i in man["inputs"])


def test_classification_is_a_pure_function_of_names_and_rule():
    from forge_factory.governance.inventory import classify

    rule = {"in": [{"group": "a", "functions": ["X_Init", "X_Get*"]}], "out": [{"group": "b", "functions": ["X_*"]}]}
    got, gaps = classify(["X_Init", "X_GetA", "X_Other"], rule)
    assert gaps == [] and got == {"X_Init": ("in", "a"), "X_GetA": ("in", "a"), "X_Other": ("out", "b")}
