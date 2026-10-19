"""CAPA-044 (r144-r152): ASIL B work products stated "QM development scope" (stale example manifest field). The SWE
author gate and the EASA pilot check now reject a QM claim, or another ASIL, inside an owner ASIL scope."""
import json

import pytest
from forge_factory.assurance import scope
from forge_factory.inspection import gate as G
from forge_factory.inspection.engine import Store

B = {"scope_id": "SC-1", "target_asil": "B"}
PENDING = ("Target ASIL B (SC-1): software safety allocation PENDING owner allocation review - no software safety "
           "requirement is allocated yet; this is an open gap, not a QM claim")


@pytest.mark.parametrize("text", [
    "QM development scope: no software safety requirements are allocated (work-order owner decision)",
    "| Safety allocation | OUT_OF_SCOPE: QM development, no safety allocation |",
    "The driver is developed as QM with no safety allocation.",
])
def test_qm_claims_in_an_asil_b_scope_are_found(text):
    assert any(f.startswith("QM_CLAIM_IN_ASIL_SCOPE") for f in scope.scope_level_findings(B, text))


def test_the_pending_statement_and_a_qm_scope_are_accepted():
    assert scope.scope_level_findings(B, PENDING) == []
    assert scope.scope_level_findings(B, "Target ASIL B; ASIL D is not claimed") == ["ASIL_MISMATCH_TEXT:ASIL D!=B"]
    assert scope.scope_level_findings({"target_asil": "QM"}, "QM development scope: nothing allocated") == []


def test_allocation_status_is_pending_until_an_allocation_review_is_recorded():
    rec = {"scope": {**B, "allocation_review_ref": None}, "approved_by": "Jefferson Nascimento", "approved_at": "2026-10-18"}
    s = scope.allocation_status(rec)
    assert s == "ASIL B (SC-1, approved by Jefferson Nascimento on 2026-10-18); software safety allocation PENDING owner allocation review"
    rec["scope"]["allocation_review_ref"] = "AR-7"
    assert scope.allocation_status(rec).endswith("allocation review AR-7")


def test_swe1_author_gate_rejects_a_qm_claim_in_an_asil_scope(tmp_path):
    ws = tmp_path / "ws"
    (ws / ".forge-run/gates").mkdir(parents=True)
    (ws / ".forge-run/manifest.json").write_text(json.dumps({"layer": "LL", "created_at": "2026-10-19T00:00:00Z"}))
    (ws / scope.SCOPE_FILE).write_text(json.dumps({"scope": B}))
    (ws / "safety").mkdir()
    (ws / "safety/software_safety_requirements.md").write_text("# Software safety requirements\n\nQM development scope.\n")
    f = scope.workspace_scope_findings(ws, "SWE.1")
    assert f == ["SAFETY_SCOPE:QM_CLAIM_IN_ASIL_SCOPE:QM development!=ASIL B:safety/software_safety_requirements.md"]
    G.step_author(Store(ws), "SWE.1", json.dumps({"status": "DONE", "issues": []}))
    last = json.loads((ws / ".forge-run/gates/gate-log.jsonl").read_text().splitlines()[-1])
    assert last["result"] == "REJECTED" and any(str(i).startswith("SAFETY_SCOPE:QM_CLAIM") for i in last["issues"])
    (ws / "safety/software_safety_requirements.md").write_text("# Software safety requirements\n\n" + PENDING + "\n")
    assert scope.workspace_scope_findings(ws, "SWE.1") == []
    (ws / scope.SCOPE_FILE).unlink()
    (ws / "safety/software_safety_requirements.md").write_text("QM development scope.\n")
    assert scope.workspace_scope_findings(ws, "SWE.1") == []               # no owner scope: not judged here


def test_pilot_check_reports_a_qm_claim_in_an_asil_package(tmp_path):
    import zipfile

    from forge_factory.assurance import pilot

    z = tmp_path / "pkg-review.zip"
    with zipfile.ZipFile(z, "w") as f:
        f.writestr("manifest.json", json.dumps({"status": "BLOCKED", "gap_count": 2}))
        f.writestr("evidence/configuration/safety_scope.json", json.dumps({"scope": B}))
        f.writestr("evidence/safety/software_safety_requirements.md", "QM development scope: nothing allocated\n")
        f.writestr("evidence/workproducts/SWE.6/report.md", PENDING + "\n")
    r = pilot.check(z)
    assert r["status"] == "FAIL" and r["archive_unchanged"]
    assert [x for x in r["failing_relations"] if x.startswith("SAFETY_SCOPE_TEXT")] == [
        "SAFETY_SCOPE_TEXT:QM_CLAIM_IN_ASIL_SCOPE:QM development!=ASIL B:evidence/safety/software_safety_requirements.md"]
