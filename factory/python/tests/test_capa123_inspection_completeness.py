"""CAPA-123 (run WO-F014-CMP-SWE3-IWDGHAL-20261102-10, cloud line, 2026-11-03): an inspection that did not examine its
evidence is INCOMPLETE (re-inspected, bounded), and an inspector visit that recorded nothing does not re-use the earlier
verdict; neither is a product finding or a rework cycle. Real defects still fail and reach the author."""
from __future__ import annotations

import contextlib
import io
import json

import pytest
from forge_factory.inspection import completeness as C
from forge_factory.inspection import gate
from forge_factory.inspection.engine import Store
from forge_factory.lrtx import reinspect
from forge_factory.mcp import sdk
from forge_factory.mcp.servers import evidence as E
from forge_factory.workflow import prompts

ITEMS = [f"SWE3-{i:02d}" for i in range(1, 11)]
DET = {"SWE3-07", "SWE3-08", "SWE3-09", "SWE3-10"}
UNEX = {"SWE3-01": "SWE.2 software_architecture.md interface section not examined (grep empty, budget reserved); API "
                   "match vs api_calls.json only",
        "SWE3-06": "matrix_3_code_to_unitspec and SWU-HAL-02.puml not examined (call budget reserved); trace provenance "
                   "unverified by inspector"}
REAL = {"SWE3-02": "HAL_IWDG_Refresh writes IWDG_KR without the start key the design requires"}


@pytest.fixture()
def st(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("FORGE_EVENTS_DIR", str(tmp_path / "events"))
    ws = tmp_path / "ws"
    (ws / ".forge-run").mkdir(parents=True)
    (ws / ".forge-run/manifest.json").write_text(json.dumps({"work_order": "WO-T-123", "layer": "HAL", "scope": [],
                                                             "created_at": "2026-11-03T00:00:00Z", "target": {},
                                                             "budgets": {}}))
    for rel, text in {"workproducts/SWE.1/software_requirements.md": "- **SWR-001** x\n",
                      "workproducts/SWE.2/software_architecture.md": "# a\n",
                      "workproducts/SWE.3/detailed_design.md": "# d\n", "software/hal/x.c": "int x;\n"}.items():
        (ws / rel).parent.mkdir(parents=True, exist_ok=True)
        (ws / rel).write_text(text)
    monkeypatch.setattr(Store, "deterministic_items", lambda self, phase, checklist: {
        i: {"verdict": "PASS", "evidence_refs": ["d.json"], "findings": [], "source": "deterministic"} for i in DET})
    s = Store(ws)
    for ph in ("SWE.1", "SWE.2", "SWE.3"):
        bl = s.freeze(ph, f"swe{ph[-1]}-author")
    gate._state(ws, "SWE.3", {"step": "author", "result": "FROZEN", "baseline_id": bl["baseline_id"]})
    return s


def _submit(st, fails):
    text = "; ".join(f"{i}=FAIL:{fails[i]}" if i in fails else f"{i}=PASS" for i in ITEMS)
    ctx = sdk.ToolContext("forge-evidence-mcp", "check_inspection", "swe3-inspector", "SWE.3", st.workspace, "r")
    return E.check_inspection(ctx, E.InspectIn(phase="SWE.3", baseline_id=st.latest_baseline("SWE.3")["baseline_id"],
                                               verdicts=text))


def _gates(st, text='{"status":"REWORK","artifacts":[],"issues":[],"next_action":"rework"}'):
    with contextlib.redirect_stdout(io.StringIO()):
        gate.step_inspect(st, "SWE.3", text)
        rc = gate.step_route(st, "SWE.3")
    rows = [json.loads(x) for x in (st.workspace / ".forge-run/gates/gate-log.jsonl").read_text().splitlines()]
    return [r for r in rows if r["step"] == "inspect"][-1]["gate"], rows[-1], rc


@pytest.mark.parametrize("text", [*UNEX.values(), "NOT_EXAMINED: workproducts/SWE.2/api_calls.json",
                                  "could not inspect SWU-HAL-02.puml", "out of tool calls before the matrix"])
def test_statements_of_unexamined_evidence(text):
    assert C.not_examined_text(text)


@pytest.mark.parametrize("text", ["the return value of LL_IWDG_IsReady is not checked", "SWR-003 is not verified by "
                                  "any unit test", "the loop exceeds the 64-instruction per-call budget",
                                  "IWDG_SR is not read before the write", "the timeout path cannot return HAL_TIMEOUT"])
def test_real_defect_wording_stays_a_product_finding(text):
    assert not C.not_examined_text(text)


def test_unexamined_evidence_is_an_incomplete_inspection_not_an_author_finding(st):
    assert _submit(st, {})["status"] == "PASS"  # the incident: first a PASS given without the evidence ...
    out = _submit(st, UNEX)  # ... then the not-examined FAILs
    assert out["status"] == "FAIL" and out["issues"] == ["SWE3-01:NOT_EXAMINED", "SWE3-06:NOT_EXAMINED"]
    assert [i["verdict"] for i in st.inspections("SWE.3")] == ["PASS"]  # no FAIL record with product findings
    inc = C.records(st.workspace, "SWE.3")[0]
    assert sorted(inc["not_examined"]) == ["SWE3-01", "SWE3-06"] and out["artifact_refs"] == [inc["record_ref"]]
    g = st.gate("SWE.3")
    assert g["decision"] == "REINSPECT" and g["reason"].startswith("INSPECTION_INCOMPLETE:INC-SWE.3-001")  # PASS voided
    ig, route, rc = _gates(st)
    assert rc == 0 and route["inspection_outcome"] and route["gate"]["decision"] == "REINSPECT"
    assert gate._count(st.workspace, "SWE.3", "route") == 0 and g["failed_inspections"] == 0
    assert reinspect.decide(st.workspace, "SWE.3")[0] is True  # straight back to the inspector, not the author


def test_a_complete_inspection_after_an_incomplete_one_decides(st):
    _submit(st, UNEX)
    assert _submit(st, {})["status"] == "PASS" and st.gate("SWE.3")["decision"] == "PASS"


def test_repeated_incomplete_inspections_block_without_a_product_finding(st):
    for _ in range(C.INCOMPLETE_LIMIT):
        _submit(st, UNEX)
    g = st.gate("SWE.3")
    assert g["decision"] == "BLOCKED" and g["reason"].startswith("INSPECTION_INCOMPLETE_REPEATEDLY")
    _ig, route, rc = _gates(st)
    assert rc == 1 and route["gate"]["decision"] == "BLOCKED"


def test_a_real_defect_beside_unexamined_items_reaches_the_author_alone(st):
    out = _submit(st, {**REAL, **UNEX})
    rec = st.inspections("SWE.3")[-1]
    assert out["status"] == "FAIL" and rec["verdict"] == "FAIL" and [f["id"] for f in rec["findings"]] == ["SWE3-02"]
    assert rec["items"]["SWE3-01"]["not_examined"] is True and rec["items"]["SWE3-01"]["verdict"] == "FAIL"
    assert gate._failed_items(rec) == {"SWE3-02"}
    ig, route, rc = _gates(st)
    assert ig["decision"] == "REWORK" and rc == 0 and "inspection_outcome" not in route


def test_a_real_defect_alone_is_unchanged(st):
    _submit(st, REAL)
    ig, route, _rc = _gates(st)
    assert ig == st.gate("SWE.3") and ig["decision"] == "REWORK" and "inspection_outcome" not in route


def test_an_inspector_visit_that_recorded_nothing_does_not_reuse_the_verdict(st):
    _submit(st, REAL)
    _gates(st)
    for n in range(1, C.NOT_PERFORMED_LIMIT + 1):
        gate._state(st.workspace, "SWE.3", {"step": "author", "result": "FROZEN_BY_EVIDENCE",
                                            "baseline_id": st.latest_baseline("SWE.3")["baseline_id"]})
        ig, route, rc = _gates(st, "")  # the session failed before any call
        if n < C.NOT_PERFORMED_LIMIT:
            assert ig["decision"] == "REINSPECT" and ig["reason"].startswith("INSPECTION_NOT_PERFORMED:") and rc == 0
            assert reinspect.decide(st.workspace, "SWE.3")[0] is True
    assert ig["decision"] == "BLOCKED" and ig["reason"].startswith("INSPECTION_NOT_PERFORMED_REPEATEDLY") and rc == 1
    assert gate._count(st.workspace, "SWE.3", "route") == 1  # only the real inspection's route was a cycle


def test_the_native_inspector_prompt_asks_for_not_examined_never_a_finding():
    p = prompts.inspector_prompt("SWE.3")
    assert "retain an explicit finding for evidence you could not examine" not in p
    assert "ID=FAIL:NOT_EXAMINED:" in p and "never FAIL or PASS an item on evidence you did not examine" in p
    assert "{{" not in p
