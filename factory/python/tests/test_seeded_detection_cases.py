"""lrtx-seeded-3 (owner 2026-11-02, cloud cross-inspection): the SWE.1 defect classes the local inspector missed, each a
generic synthetic mutation of one requirement on a copy, paired with a PROPOSED detection lesson. A baseline without a
site for a class raises NO_MUTATION_SITE (the harness reports NOT_APPLICABLE; nothing is forced)."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from forge_factory.assurance import owner_obligations as OO
from forge_factory.common import sha256_file
from forge_factory.knowledge import inspection as IL
from forge_factory.lrtx import seeded as SD

REQS = """# Software requirements

- **SWR-001** When the set function is called with a requested value in the 4-bit range 0U through 15U, the D driver shall write the requested value to PER_CR.LEN.
  - Source: RM p.10
  - Verification: Host unit test calls the set function for every value from 0U through 15U and passes when PER_CR.LEN equals each requested value.
  - Obligations: OBL-len-write
- **SWR-002** While write access is enabled, when the reload function is called, the D driver shall write the requested reload value to PER_RLR.RL, masking it to the field's 12-bit range.
  - Source: RM p.11
  - Verification: Host unit test passes when PER_RLR.RL equals 0x0ABC after a call with 0x0ABC.
- **SWR-003** When the mode function is called, the D driver shall write PER_CR.MODE and PER_CR.EN together.
  - Source: RM p.10
  - Verification: Host unit test passes when PER_CR.MODE is 1 and PER_CR.EN is 1.
- **SWR-004** While no LL function has been called after reset, the D driver shall not read or write any register.
  - Source: RM p.9
  - Verification: passes when unchanged.
  - Obligations: OBL-no-startup-accesses
- **SWR-005** When writing to a register, the D driver shall change only the named register field and leave the remaining bits of that register unchanged.
  - Source: RM p.9
  - Verification: passes when only the named field changes.

## Open points

- Target silicon revision: UNSPECIFIED.
"""
EFFECTS = {"effects": [
    {"case": "LEN", "swr": "SWR-001", "register": "PER_CR", "field": "LEN", "op": "write", "value": "0x5",
     "api_calls": [{"function": "set", "args": [5]}]},
    {"case": "RL", "swr": "SWR-002", "register": "PER_RLR", "field": "RL", "op": "write", "value": "0x0ABC"},
    {"case": "MODE", "swr": "SWR-003", "register": "PER_CR", "field": "MODE", "op": "set"},
    {"case": "EN", "swr": "SWR-003", "register": "PER_CR", "field": "EN", "op": "set"}]}
GAPS = """# Upstream coverage

## Upstream to software requirements

| Upstream ID | SWR IDs |
| --- | --- |
| RM-1.1 | SWR-001, SWR-003 |
| RM-1.2 | SWR-002 |
| RM-1.3 | SWR-004, SWR-005 |

## Software requirements to upstream

| SWR ID | Upstream ID |
| --- | --- |
| SWR-001 | RM-1.1 |
| SWR-002 | RM-1.2 |
| SWR-003 | RM-1.1 |
| SWR-004 | RM-1.3 |
| SWR-005 | RM-1.3 |
"""
OBLIGATIONS = {"schema": "forge-c/owner-obligations/1", "status": "OWNER_APPROVED", "owner": "test owner",
               "source_inputs": [], "obligations": [
                   {"id": "OBL-len-write", "statement": "Write the requested length.", "critical": False},
                   {"id": "OBL-no-startup-accesses", "statement": "No startup accesses occur.", "critical": True}]}
NEW = ("S1-DOMAIN", "S1-OBLDECLINE", "S1-OBLNARROW", "S1-PRECOND", "S1-VERIFRESET", "S1-XCUT", "S1-TRACESEC")


@pytest.fixture
def base(tmp_path) -> Path:
    ws = tmp_path / "base"
    (ws / "workproducts/SWE.1").mkdir(parents=True)
    (ws / "traceability").mkdir()
    (ws / "inputs").mkdir()
    (ws / ".forge-run").mkdir()
    (ws / "workproducts/SWE.1/software_requirements.md").write_text(REQS)
    (ws / "workproducts/SWE.1/register_effects.json").write_text(json.dumps(EFFECTS))
    (ws / "traceability/upstream_gaps.md").write_text(GAPS)
    (ws / "traceability/obligations_to_requirements.csv").write_text(
        "obligation_id,requirement_id,gap_reason\nOBL-len-write,SWR-001,\nOBL-no-startup-accesses,SWR-004,\n")
    p = ws / "inputs/owner-obligations.json"
    p.write_text(json.dumps(OBLIGATIONS))
    (ws / ".forge-run/manifest.json").write_text(json.dumps({"inputs": [
        {"path": "inputs/owner-obligations.json", "role": OO.ROLE, "sha256": sha256_file(p)}]}))
    return ws


def _copy(base: Path, n: str) -> Path:
    ws = base.parent / n
    shutil.copytree(base, ws)
    return ws


def _md(ws):
    return (ws / "workproducts/SWE.1/software_requirements.md").read_text()


def _swr(ws, swr):
    return next(line for line in _md(ws).splitlines() if line.startswith(f"- **{swr}**"))


def _eff(ws):
    return json.loads((ws / "workproducts/SWE.1/register_effects.json").read_text())["effects"]


def test_the_catalogue_has_the_detection_cases_and_a_new_version():
    ids = [c["id"] for c in SD.CATALOGUE]
    assert SD.CATALOGUE_VERSION == "lrtx-seeded-3" and all(i in ids for i in NEW) and len(ids) == len(set(ids))
    assert all(c["phase"] == "SWE.1" for c in SD.CATALOGUE if c["id"] in NEW)


def test_domain_clause_removed_and_the_choice_left_open(base):
    ws = _copy(base, "w")
    assert SD.undecided_domain(ws) == "SWR-001"
    assert "range" not in _swr(ws, "SWR-001") and "requested value" in _swr(ws, "SWR-001")
    assert "(input scope: SWR-001): It is undecided whether a requested value outside the field range" in _md(ws)
    assert _md(ws).index("## Open points") < _md(ws).index("(input scope: SWR-001)")


def test_obligation_declined_as_a_gap(base):
    ws = _copy(base, "w")
    assert SD.decline_obligation(ws) == "OBL-len-write"  # the non-critical implemented obligation first
    mapping, gaps = OO.parse(_md(ws))
    assert "SWR-001" not in mapping and "OBL-len-write" in gaps and "forbid inventing" in gaps["OBL-len-write"]
    assert all(e["swr"] != "SWR-001" for e in _eff(ws))
    csv = (ws / "traceability/obligations_to_requirements.csv").read_text()
    assert "OBL-len-write,SWR-001" not in csv and "OBL-len-write,," in csv


def test_obligation_requirement_narrowed_from_accesses_to_writes(base):
    ws = _copy(base, "w")
    assert SD.narrow_obligation(ws) == "SWR-004"
    assert "shall not write any register" in _swr(ws, "SWR-004")
    assert OO.parse(_md(ws))[0]["SWR-004"] == ["OBL-no-startup-accesses"]  # the mapping stays, no gap reason


def test_caller_precondition_dropped(base):
    ws = _copy(base, "w")
    assert SD.drop_precondition(ws) == "SWR-002"
    assert _swr(ws, "SWR-002").startswith("- **SWR-002** When the reload function is called")
    assert "SWR-004** While no LL function" in _md(ws)  # the startup rule is never a precondition site


def test_verification_reduced_to_the_reset_value(base):
    ws = _copy(base, "w")
    assert SD.reset_value_verification(ws) == "SWR-001"
    ver = _md(ws).split("- **SWR-001**")[1].split("\n")[2]
    assert "once with the value 0x0 " in ver and "every value" not in ver
    e = next(x for x in _eff(ws) if x["swr"] == "SWR-001")
    assert e["value"] == "0x0" and e["api_calls"][0]["args"] == [0]


def test_cross_cutting_rule_made_to_contradict_a_two_field_requirement(base):
    ws = _copy(base, "w")
    assert SD.exactly_one_field(ws) == "SWR-005"
    assert "change exactly one named field of that register per call" in _swr(ws, "SWR-005")
    single = _copy(base, "s")
    (single / "workproducts/SWE.1/register_effects.json").write_text(json.dumps({"effects": EFFECTS["effects"][:2]}))
    (single / "workproducts/SWE.1/software_requirements.md").write_text(REQS.replace(" and PER_CR.EN together", ""))
    with pytest.raises(ValueError, match="NO_MUTATION_SITE:exactly_one_field"):
        SD.exactly_one_field(single)


def test_trace_row_moved_to_a_neighbour_section_in_both_tables(base):
    ws = _copy(base, "w")
    assert SD.neighbour_trace_section(ws) == "SWR-001"
    t = (ws / "traceability/upstream_gaps.md").read_text()
    assert "| SWR-001 | RM-1.2 |" in t and "| RM-1.1 | SWR-003 |" in t and "| RM-1.2 | SWR-001, SWR-002 |" in t


def test_a_baseline_without_sites_is_not_applicable(tmp_path):
    ws = tmp_path / "w"
    (ws / "workproducts/SWE.1").mkdir(parents=True)
    (ws / "workproducts/SWE.1/software_requirements.md").write_text(
        "# Software requirements\n\n- **SWR-001** The D driver shall write 0x1 to PER_CR.KEY.\n"
        "  - Verification: passes when PER_CR.KEY is 0x1.\n")
    (ws / "workproducts/SWE.1/register_effects.json").write_text(json.dumps({"effects": [
        {"case": "K", "swr": "SWR-001", "register": "PER_CR", "field": "KEY", "op": "write", "value": "0x1"}]}))
    for fn in (SD.undecided_domain, SD.decline_obligation, SD.narrow_obligation, SD.drop_precondition,
               SD.reset_value_verification, SD.exactly_one_field, SD.neighbour_trace_section):
        with pytest.raises(ValueError, match="NO_MUTATION_SITE"):
            fn(ws)


def test_every_paired_case_of_a_repository_lesson_exists():
    known = {c["id"] for c in SD.CATALOGUE}
    for r in IL.load():
        assert set(r.get("must_still_detect") or []) <= known, r["id"]
