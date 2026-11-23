"""Feature 020 port: the governance package (actors, use cases, scope) and its deterministic coverage gate."""
from __future__ import annotations

import json

from forge_hi import gates, governance, seal
from hi_helpers import SWR_ITEMS, SYS_ITEMS, governance_doc, make_project, req, with_use_case, write


def codes(root, stage="sys-req", **kw):
    return sorted(i["code"] for i in governance.check(root, stage, **kw))


def put(root, doc, stage="sys-req"):
    write(root / "hi" / stage / "governance.json", doc)


def test_package_from_the_helper_passes(tmp_project):
    make_project(tmp_project, sys_items=SYS_ITEMS)
    assert codes(tmp_project) == []
    assert governance.run(tmp_project, "sys-req")["verdict"] == "PASS"


def test_missing_and_unreadable(tmp_project):
    make_project(tmp_project, sys_items=SYS_ITEMS, governance=False)
    assert codes(tmp_project) == ["GOV-MISSING"]
    (tmp_project / "hi/sys-req/governance.json").write_text("{not json")
    assert codes(tmp_project) == ["GOV-UNREADABLE"]
    put(tmp_project, governance_doc(actors=[]))
    assert codes(tmp_project) == ["GOV-SCHEMA"]


def test_every_need_is_served_out_of_scope_or_open(tmp_project):
    make_project(tmp_project, sys_items=SYS_ITEMS)
    uc = governance_doc()["use_cases"][0]
    put(tmp_project, governance_doc(use_cases=[dict(uc, needs=["STK-SUP-001"])]))
    found = governance.check(tmp_project, "sys-req", realization=False)
    assert [(i["code"], i["target_id"]) for i in found] == [("GOV-NEED-UNCOVERED", "STK-SUP-002")]
    put(tmp_project, governance_doc(use_cases=[dict(uc, needs=["STK-SUP-001"])], out_of_scope=[
        {"ref": "STK-SUP-002", "reason": "Late tasks are the scheduler's job in this product."}]))
    assert codes(tmp_project, realization=False) == []
    put(tmp_project, governance_doc(use_cases=[dict(uc, needs=["STK-SUP-001"])], open_points=[
        {"id": "OP-GOV-001", "text": "Is lateness measured per task?", "concerns": ["STK-SUP-002"], "blocks": True}]))
    assert codes(tmp_project, realization=False) == []


def test_structure_errors(tmp_project):
    make_project(tmp_project, sys_items=SYS_ITEMS)
    uc = governance_doc()["use_cases"][0]
    put(tmp_project, governance_doc(
        use_cases=[uc, dict(uc, id="UC-SUP-002", actor="ACT-SUP-009", needs=["STK-SUP-404"]),
                   dict(uc, id="UC-SUP-001", needs=[])],
        out_of_scope=[{"ref": "STK-SUP-001", "reason": "Deliberately left to the hardware watchdog."}],
        open_points=[{"id": "OP-GOV-001", "text": "Which tasks are supervised?", "concerns": ["STK-SUP-001"],
                      "blocks": False}]))
    assert codes(tmp_project, realization=False) == [
        "GOV-ACTOR-UNKNOWN", "GOV-DUPLICATE-ID", "GOV-REF-UNKNOWN", "GOV-SCOPE-CONFLICT", "GOV-UC-EMPTY",
        "IQ-12.open-point-owner"]


def test_use_cases_are_realised_by_requirements(tmp_project):
    make_project(tmp_project, sys_items=SYS_ITEMS, governance=False)
    put(tmp_project, governance_doc())
    assert codes(tmp_project) == ["GOV-UC-UNREALIZED"]
    assert codes(tmp_project, realization=False) == []
    make_project(tmp_project, sys_items=with_use_case(SYS_ITEMS, "UC-SUP-404"), governance=False)
    assert codes(tmp_project) == ["GOV-UC-UNKNOWN", "GOV-UC-UNKNOWN", "GOV-UC-UNREALIZED"]


def test_reference_document_sections_are_covered_and_cited(tmp_project):
    drv = [req("DRV-WDG-001", "The driver shall refresh the watchdog counter with the reload key.",
               [{"kind": "document", "doc_id": "RM0486", "section": "34.4.2", "page": 1201}],
               attributes={"use_cases": ["UC-WDG-001"]})]
    make_project(tmp_project, swr_items=drv, stages=("sw-req",), input_class="reference_document", inputs=[
        {"path": "docs/rm.pdf", "kind": "reference_document", "doc_id": "RM0486"}])
    scope = [{"ref": "RM0486#34.4", "title": "Functional description", "scope": "in"},
             {"ref": "RM0486#34.5", "title": "Window option", "scope": "in"},
             {"ref": "RM0486#34.6", "title": "Debug", "scope": "out", "reason": "Not used."}]
    uc = {"id": "UC-WDG-001", "title": "Refresh", "actor": "ACT-SUP-001", "goal": "Keep the watchdog refreshed.",
          "needs": [], "sections": ["RM0486#34.4"]}
    put(tmp_project, governance_doc("sw-req", document_scope=scope, use_cases=[uc]), "sw-req")
    assert codes(tmp_project, "sw-req") == ["GOV-SECTION-UNCOVERED"]   # 34.5 is in scope but in no use case
    uc2 = dict(uc, id="UC-WDG-002", title="Window", sections=["RM0486#34.5"])
    put(tmp_project, governance_doc("sw-req", document_scope=scope, use_cases=[uc, uc2]), "sw-req")
    found = governance.check(tmp_project, "sw-req")
    assert sorted((i["code"], i["target_id"]) for i in found) == [
        ("GOV-SECTION-UNREALIZED", "RM0486#34.5"), ("GOV-UC-UNREALIZED", "UC-WDG-002")]


def test_gate_belongs_to_the_entry_stage_only(tmp_project):
    make_project(tmp_project, sys_items=SYS_ITEMS, swr_items=SWR_ITEMS)
    proj = json.loads((tmp_project / ".hi/project.json").read_text())
    assert "governance" in gates.required_gates(proj, "sys-req")
    assert "governance" not in gates.required_gates(proj, "sw-req")
    assert governance.run(tmp_project, "sw-req")["verdict"] == "NOT_RUN"
    assert "governance" not in gates.required_gates(dict(proj, integrity_level="HI-0"), "sys-req")


def test_blocking_governance_open_point_is_a_seal_gap(tmp_project):
    from test_seal import accept, gap_codes
    make_project(tmp_project, sys_items=SYS_ITEMS, swr_items=SWR_ITEMS, level="HI-1")
    put(tmp_project, governance_doc(open_points=[
        {"id": "OP-GOV-001", "text": "Who owns the supervision configuration?", "concerns": ["STK-SUP-001"],
         "blocks": True}]))
    accept(tmp_project, "sys-req")
    accept(tmp_project, "sw-req")
    res = seal.seal(tmp_project)
    assert "OPEN-POINT-BLOCKING" in gap_codes(res)
    st = {s["stage"]: s for s in gates.status(tmp_project)["stages"]}
    assert st["sys-req"]["blocking_open_points"] == 1


def test_cli_before_and_after_requirements(tmp_project):
    import subprocess
    import sys
    from conftest import SKILLS
    hi = SKILLS / "hi-gates" / "scripts" / "hi.py"
    make_project(tmp_project, governance=False)
    put(tmp_project, governance_doc())

    def run(*a):
        r = subprocess.run([sys.executable, str(hi), "governance", "sys-req", *a], cwd=tmp_project,
                           capture_output=True, text=True)
        return r.returncode, json.loads(r.stdout)

    code, out = run("--before-requirements")
    assert code == 0 and out["verdict"] == "PASS" and "written" not in out
    write(tmp_project / "hi/sys-req/requirements.json",
          json.loads(json.dumps(__import__("hi_helpers").reqset("sys-req", SYS_ITEMS))))
    code, out = run()
    assert code == 1 and out["top"][0]["code"] == "GOV-UC-UNREALIZED"
    assert out["written"] == "hi/sys-req/gates/governance.json"


def test_constraints_may_be_named_but_need_no_use_case(tmp_project):
    # driver demo T052: the scope of a driver project is stated as constraints (CON-IWDG-002 lists the services)
    make_project(tmp_project, sys_items=SYS_ITEMS)
    uc = dict(governance_doc()["use_cases"][0], needs=["STK-SUP-001", "STK-SUP-002", "CON-SUP-001"])
    op = {"id": "OP-GOV-001", "text": "Which core clock applies to the timing?", "concerns": ["CON-SUP-001"],
          "blocks": False, "deferred_to": "sw-req"}
    put(tmp_project, governance_doc(use_cases=[uc], open_points=[op]))
    assert codes(tmp_project) == []
    put(tmp_project, governance_doc())                     # CON-SUP-001 in no use case: not a coverage gap
    assert codes(tmp_project) == []
