"""Feature 020 T004: the SWE.1 level setting of a work order (research R2, data model "SWE.1 level setting").

A work order with `swe1: {level: functional, template: swe1-functional-v1}` yields the manifest keys `swe1_level` /
`swe1_template`, no `register_contract`, and refuses every run beyond SWE.1 (SWE1_FUNCTIONAL_LATER_PHASES_NOT_YET).
A work order without the block prepares a manifest byte-identical to the base commit: the golden
`fixtures/f020/manifest_register_ser.json` was produced on forge-c-020-base (303b46ea) with FORGE_GOLDEN_WRITE=1.
An invalid block is refused before any workspace exists (contracts/workorder-swe1-block.schema.json; the work order
carries the contract's `scope` block as `scope_rule`, decision log D14)."""
from __future__ import annotations

import copy
import json
import os

import pytest
from f020_fixtures import FIX, example, normalized_manifest, ser_spec
from forge_factory import workorder as WO
from forge_factory.common import REPO_ROOT, pretty_json, state_dir

GOLDEN = FIX / "manifest_register_ser.json"


@pytest.fixture(autouse=True)
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("FORGE_EVENTS_DIR", str(tmp_path / "state/events"))


def _normalized(ws) -> str:
    return pretty_json(normalized_manifest(json.loads((ws / ".forge-run/manifest.json").read_text())))


def test_functional_order_stamps_the_level_and_no_register_contract(tmp_path):
    ws, man = WO.prepare(example(tmp_path), "WO-F020-L1")
    assert man["swe1_level"] == "functional" and man["swe1_template"] == "swe1-functional-v1"
    assert "register_contract" not in man
    written = json.loads((ws / ".forge-run/manifest.json").read_text())
    assert written["swe1_level"] == "functional" and "register_contract" not in written
    assert man["scope"] == ser_spec()["scope"]  # the declared scope text stays what agents read


def test_register_order_manifest_is_byte_identical_to_the_base(tmp_path):
    ws, man = WO.prepare(example(tmp_path, ser_spec(functional=False)), "WO-F020-L2")
    got = _normalized(ws)
    if os.environ.get("FORGE_GOLDEN_WRITE") == "1":
        GOLDEN.write_text(got)
        pytest.skip("golden recorded")
    assert got == GOLDEN.read_text()
    assert "swe1_level" not in man and "swe1_template" not in man and man["register_contract"] == "rc-v1"


def test_explicit_register_level_keeps_the_register_manifest(tmp_path):
    spec = ser_spec()
    spec["swe1"]["level"] = "register"
    ws, man = WO.prepare(example(tmp_path, spec), "WO-F020-L2R")
    assert _normalized(ws).replace("WO-F020-L2R", "WO-F020-L2") == GOLDEN.read_text()
    assert man["register_contract"] == "rc-v1" and "swe1_level" not in man


def _no_prepare(monkeypatch):
    def boom(*_a, **_k):
        raise RuntimeError("PREPARE_REACHED")
    monkeypatch.setattr(WO, "prepare", boom)  # never a workspace or a launch from this test
    monkeypatch.setattr(WO, "suspension", lambda *_a, **_k: None)


@pytest.mark.parametrize("stop_after", ["SWE.2", "SWE.3", "SWE.4", "SWE.5", "SWE.6", None])
def test_functional_order_refuses_every_phase_after_swe1(tmp_path, monkeypatch, stop_after):
    _no_prepare(monkeypatch)
    with pytest.raises(ValueError, match="SWE1_FUNCTIONAL_LATER_PHASES_NOT_YET"):
        WO.run(example(tmp_path), "WO-F020-L3", stop_after=stop_after)
    assert not (state_dir() / "workorders/WO-F020-L3").exists()


def test_functional_swe1_only_and_register_orders_reach_prepare(tmp_path, monkeypatch):
    _no_prepare(monkeypatch)
    with pytest.raises(RuntimeError, match="PREPARE_REACHED"):
        WO.run(example(tmp_path), "WO-F020-L4", stop_after="SWE.1")
    with pytest.raises(RuntimeError, match="PREPARE_REACHED"):
        WO.run(example(tmp_path, ser_spec(functional=False), name="reg"), "WO-F020-L5", stop_after="SWE.2")


def _drop(key):
    return lambda s: s.pop(key)


@pytest.mark.parametrize("mutate, issue", [
    (lambda s: s["swe1"].update(level="behavioural"), "SWE1_BLOCK_INVALID:swe1/level"),
    (lambda s: s["swe1"].update(extra=True), "SWE1_BLOCK_INVALID:swe1"),
    (lambda s: s["swe1"].pop("template"), "SWE1_BLOCK_INVALID:swe1"),
    (_drop("module"), "SWE1_BLOCK_INVALID:-"),
    (_drop("scope_rule"), "SWE1_BLOCK_INVALID:-"),
    (lambda s: s["scope_rule"].update({"in": []}), "SWE1_BLOCK_INVALID:scope/in"),
    (lambda s: s["module"]["components"][0].update(layer="MIDDLE"), "SWE1_BLOCK_INVALID:module/components/0/layer"),
    (lambda s: s["module"]["components"][0].pop("uses"), "SWE1_BLOCK_INVALID:module/components/0"),
    (lambda s: s["swe1"].update(template="swe1-functional-v9"), "SWE1_TEMPLATE_UNKNOWN:swe1-functional-v9"),
])
def test_an_invalid_block_is_refused_before_any_workspace(tmp_path, mutate, issue):
    with pytest.raises(ValueError, match=issue):
        WO.prepare(example(tmp_path, mutate=mutate), "WO-F020-L6")
    assert not (state_dir() / "workorders/WO-F020-L6").exists()


def test_the_config_schema_is_the_contract_with_the_use_case_inlined():
    contract = json.loads((REPO_ROOT / "specs/020-usart-benchmark-pilot/contracts/workorder-swe1-block.schema.json")
                          .read_text())
    package = json.loads((REPO_ROOT / "specs/020-usart-benchmark-pilot/contracts/governance-package.schema.json")
                         .read_text())
    copy_ = json.loads((REPO_ROOT / "config/schemas/workorder/swe1-block.schema.json").read_text())
    expected = copy.deepcopy(contract)
    expected["properties"]["use_cases_owner"]["items"] = {"$ref": "#/$defs/use_case"}
    expected["$defs"]["use_case"] = package["$defs"]["use_case"]
    assert copy_ == expected


def test_resume_contract_carries_the_level_only_when_present(tmp_path):
    from forge_factory.brownfield.resume import contract

    _ws, man = WO.prepare(example(tmp_path), "WO-F020-L7")
    got = contract(man)
    assert got["swe1_level"] == "functional" and got["swe1_template"] == "swe1-functional-v1"
    _ws2, reg = WO.prepare(example(tmp_path, ser_spec(functional=False), name="reg"), "WO-F020-L8")
    assert not {"swe1_level", "swe1_template", "swe1_use_cases_owner"} & set(contract(reg))
