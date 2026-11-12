"""Feature 020 T018 (US2, FR-020, FR-021): the SWE.1 author gate of a functional-level order.

`step_author` runs the functional checks (template attributes and fixed values, origin groups, links, the level rule,
no delivered code as a source, EARS, design constraints by inspection) and never the register contract; the presence
gate does not ask for `register_effects.json`. Rejections carry the requirement id, its key and the rule. A
register-level order runs exactly today's steps (register contract, no functional check; the full step list is the
T007 golden)."""
from __future__ import annotations

import io
import json
import sys

import pytest
from f020_fixtures import example, ser_spec
from f020_swe1 import author, prepared

ATTRS = "workproducts/SWE.1/requirement_attributes.json"
REQS = "workproducts/SWE.1/software_requirements.md"


def _gate(ws, monkeypatch) -> int:
    from forge_factory.inspection import gate

    monkeypatch.setattr(sys, "stdin", io.StringIO((ws / ".forge-run/lrtx/SWE.1/reply.json").read_text()))
    return gate.main(["--workspace", str(ws), "--phase", "SWE.1", "--step", "author"])


def _spy(monkeypatch, steps: list):
    from forge_factory.assurance import register_contract as RC
    from forge_factory.assurance import swe1_functional_checks as FC

    for mod, name, tag in ((RC, "check_effects", "RC.check_effects"), (FC, "findings", "FC.findings")):
        orig = getattr(mod, name)
        monkeypatch.setattr(mod, name, lambda *a, _o=orig, _t=tag, **k: (steps.append(_t), _o(*a, **k))[1])


def _last_gate(ws) -> dict:
    return json.loads((ws / ".forge-run/gates/gate-log.jsonl").read_text().splitlines()[-1])


@pytest.fixture()
def done(tmp_path, monkeypatch):
    ws = prepared(tmp_path, monkeypatch)
    rep, _ = author(ws, monkeypatch)
    assert rep["status"] == "PASS", rep
    return ws


def test_a_valid_functional_set_passes_the_gate_without_the_register_contract(done, monkeypatch):
    from forge_factory.assurance import swe1_functional_checks as FC
    from forge_factory.inspection.engine import Store

    assert FC.findings(done) == []
    assert not (done / "workproducts/SWE.1/register_effects.json").exists()
    steps: list = []
    _spy(monkeypatch, steps)
    assert _gate(done, monkeypatch) == 0
    assert steps == ["FC.findings"]
    assert _last_gate(done)["result"] == "FROZEN"
    assert Store(done).missing_outputs("SWE.1") == []  # the ReqIF the gate wrote; no register_effects.json asked


def _tamper(ws, swr: str, **change):
    doc = json.loads((ws / ATTRS).read_text())
    r = next(x for x in doc["requirements"] if x["id"] == swr)
    old = r["statement"]
    for k, v in change.items():
        if v is None:
            r.pop(k)
        else:
            r[k] = v
    (ws / ATTRS).write_text(json.dumps(doc, indent=1))
    if "statement" in change:
        md = (ws / REQS).read_text()
        (ws / REQS).write_text(md.replace(f"**{swr}** {old}", f"**{swr}** {change['statement']}"))
    return r["key"]


@pytest.mark.parametrize("swr, change, rule", [
    ("SWR-004", {"statement": "When HAL_SER_Transmit is called, the SER HAL driver shall write each item to SER_TDR."},
     "LEVEL_REGISTER_TERM"),
    ("SWR-004", {"statement": "When HAL_SER_Transmit is called, the SER HAL driver shall write to 0x40001010."},
     "LEVEL_HEX_VALUE"),
    ("SWR-004", {"test_level": None}, "TEMPLATE_ATTRIBUTE_MISSING"),
    ("SWR-004", {"asil": "ASIL B"}, "FIXED_ATTRIBUTE"),
    ("SWR-003", {"links": [{"kind": "trace", "input_id": "IN-02", "locator": "42.1"}]}, "LINKS_ON_AWAITING"),
    ("SWR-004", {"links": [{"kind": "trace", "input_id": "IN-06", "locator": "HAL_SER_Transmit"}]},
     "LINK_TO_DELIVERED_CODE"),
    ("SWR-004", {"use_cases": ["UC-77"]}, "USE_CASE_UNKNOWN"),
    ("SWR-019", {"verification_method": "test"}, "DESIGN_CONSTRAINT_NOT_BY_INSPECTION"),
    ("SWR-004", {"statement": "When HAL_SER_Transmit is called, the SER HAL driver should send the data."},
     "EARS_"),
])
def test_each_violation_is_rejected_with_the_requirement_id_and_rule(done, monkeypatch, swr, change, rule):
    from forge_factory.assurance import swe1_functional_checks as FC

    key = _tamper(done, swr, **change)
    assert any(f.startswith(f"SWE1_FUNCTIONAL:{swr} [{key}] {rule}") for f in FC.findings(done)), FC.findings(done)
    assert _gate(done, monkeypatch) != 0
    rec = _last_gate(done)
    assert rec["result"] == "REJECTED" and any(f"{swr} [{key}] {rule}" in i for i in rec["issues"]), rec


def test_the_markdown_must_match_the_attributes(done):
    from forge_factory.assurance import swe1_functional_checks as FC

    md = (done / REQS).read_text()
    (done / REQS).write_text(md.replace("shall send the data and return HAL_OK", "shall send the data"))
    assert any(f.startswith("SWE1_FUNCTIONAL:SWR-004 [transmit_blocking] MARKDOWN_MISMATCH") for f in FC.findings(done))


def test_a_missing_attributes_file_is_a_finding(done):
    from forge_factory.assurance import swe1_functional_checks as FC

    (done / ATTRS).unlink()
    assert FC.findings(done) == [f"SWE1_FUNCTIONAL:ATTRIBUTES_MISSING:{ATTRS}"]


def test_a_register_level_order_runs_todays_steps(tmp_path, monkeypatch):
    from forge_factory import workorder as WO
    from forge_factory.inspection.engine import Store

    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    ws, man = WO.prepare(example(tmp_path, ser_spec(functional=False), name="WO-F020-R"), "WO-F020-R")
    assert man["register_contract"] == "rc-v1" and "swe1_level" not in man
    assert "MISSING_REQUIRED_OUTPUT:workproducts/SWE.1/register_effects.json" in Store(ws).missing_outputs("SWE.1")
    (ws / ".forge-run/lrtx/SWE.1").mkdir(parents=True)
    (ws / ".forge-run/lrtx/SWE.1/reply.json").write_text(json.dumps(
        {"status": "PASS", "artifacts": [], "issues": [], "next_action": "next"}))
    (ws / "workproducts/SWE.1").mkdir(parents=True, exist_ok=True)
    (ws / REQS).write_text("# Software requirements\n\n- **SWR-001** The SER driver shall enable the interface.\n"
                           "  - Source: RM9999 p.413\n  - Verification: host unit test passes when it is enabled.\n")
    steps: list = []
    _spy(monkeypatch, steps)
    assert _gate(ws, monkeypatch) != 0  # no register contract written: rejected as today
    assert steps == ["RC.check_effects"]
