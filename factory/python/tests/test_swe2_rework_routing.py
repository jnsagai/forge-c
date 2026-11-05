"""CAPA-109 (run WO-F014-CMP-SWE2-IWDG-20261102-03): SWE.2 rework findings reach the task that owns the architecture
section they name; the design packet carries the register field bit positions and the component-level constraints it
justifies; the interface packet says where the unlisted component-level constraints are allocated."""
from __future__ import annotations

from forge_factory.lrtx import structured as S
from forge_factory.lrtx import swe2
from test_lrtx_swe1 import _scripted, pytestmark, ws  # noqa: F401 - fixture and owner-input precondition
from test_lrtx_swe2 import DESIGN, IFACE, ws1  # noqa: F401

ALLOC = ("SWE2-06: Minor - workproducts/SWE.2/software_architecture.md, Requirement allocation table, SWR-012: states "
         "SWR-019/SWR-020 are outside the task requirement list, contradicting their inclusion in frozen SWE.1.")
SAFETY = ("SWE2-06: Minor - workproducts/SWE.2/software_architecture.md, Safety mechanisms, degraded states and "
          "dependencies: lists the PR field width and mask as undecidable, although its Interfaces and Register table "
          "fix bits 3:0 and mask 0xFU consistently with SWE.1 SWR-005.")
BUDGET = ("SWE2-05: workproducts/SWE.2/software_architecture.md, 'Timing and error handling' and SWR-012/SWR-019/SWR-020 "
          "allocation rows: the per-call budgets are allocated to SWC_LL, but their justification remains open.")


def test_a_design_section_finding_citing_an_swr_reaches_the_design_task():
    r = swe2.route([ALLOC, SAFETY, BUDGET])
    assert r["design"] == [SAFETY, BUDGET]  # SAFETY cites the Interfaces table only as evidence
    assert r["interfaces"] == [ALLOC, BUDGET]  # its location names sections of both tasks: both
    unlocated = ("SWE2-06: Minor: workproducts/SWE.2/software_architecture.md, 'Safety mechanisms', lists the PR width as "
                 "unresolved, while its Interfaces and Requirement allocation fix bits 3:0 (SWR-005).")
    assert swe2.route([unlocated]) == {"design": [unlocated]}  # no location clause: the first section named


def test_sectionless_findings_keep_the_earlier_rule_and_a_visit_failure_keeps_its_task():
    r = swe2.route(["SWR-009 is not allocated", "the dynamic texts lack a rationale", "CONTRACT_CALL_MISSING: START",
                    "interfaces: function LL_IWDG_X: IWDG_PR.Q is not a field", "design: register_access must state"])
    assert r["interfaces"] == ["SWR-009 is not allocated", "CONTRACT_CALL_MISSING: START",
                               "interfaces: function LL_IWDG_X: IWDG_PR.Q is not a field"]
    assert r["design"] == ["the dynamic texts lack a rationale", "design: register_access must state"]


def test_design_packet_carries_field_bits_and_component_constraints(ws1):
    p = swe2.design_packet(ws1, "m", IFACE)
    text = "\n".join(m["content"] for m in p["_messages"])
    assert "IWDG_PR.PR (bits 3:0)" in text and "IWDG_KR.KEY (bits 15:0)" in text
    cl = sorted(swe2.component_level(ws1))
    assert cl and all(f"{s}: " in text for s in cl)
    assert any(a["path"].endswith("#component-level") for a in p["artifacts"])
    q = swe2.interfaces_packet(ws1, "m")
    assert f"component-level constraints {', '.join(cl)}" in q["instructions"]


def test_rework_repairs_the_design_text_the_safety_finding_names(ws1, monkeypatch):
    calls = []
    monkeypatch.setattr(S, "call", _scripted({"interfaces": IFACE, "design": DESIGN}, calls))
    assert swe2.visit(ws1, "m")["status"] == "PASS"
    fixed = {**DESIGN, "safety_and_dependencies": DESIGN["safety_and_dependencies"] + " The PR field is bits 3:0."}
    later = []
    monkeypatch.setattr(S, "call", _scripted({"interfaces": IFACE, "design": lambda p: fixed if p["findings"] else
                                              DESIGN}, later))
    rep = swe2._visit(ws1, "m", {"calls": 0, "max_calls": 8}, [SAFETY])
    design = [p for p in later if p["task"] == "design"]
    assert design and SAFETY in design[0]["findings"], [p["task"] for p in later]
    assert rep["status"] in ("PASS", "FAILED")
    assert "The PR field is bits 3:0." in (ws1 / swe2.ARCH).read_text()
