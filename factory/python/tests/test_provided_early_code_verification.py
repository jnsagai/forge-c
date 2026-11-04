"""CAPA167 actual public verification CONTROL, dependent on qualified166; no model competence claim."""
import json
from types import SimpleNamespace

import pytest
import test_unit_target_carry as F
from forge_factory import workorder as W
from forge_factory.inspection import defects as D
from forge_factory.inspection import provided_changes as PC
from forge_factory.inspection import provided_early_code as E
from forge_factory.inspection.engine import Store
from forge_factory.mcp.servers import sim
from forge_factory.mcp.servers import tests as U
from forge_factory.workflow import provided_input_identity as I
from forge_factory.workflow import unit_target_carry as C
from forge_factory.workflow import unit_target_observation as O
from test_provided_effective_identity import execute, files
from test_unit_target_observation import actual, write

LL = "software/ll/stm32n6xx_ll_wwdg.h"


@actual
@pytest.mark.parametrize("pathway", ["direct", "restored"])
def test_normal_early2_claim3_reviewed_fix_real_unit4_verified_and_resume5_6(tmp_path, monkeypatch, pathway):
    origin, normal_pass = F.observation_ws, F.pass_control

    def original(ws):
        origin.__wrapped__(ws)
        path = ws / LL
        path.write_text(path.read_text().replace("x->SR = 0U", "x->SR = ~WWDG_SR_EWIF"))
        man = json.loads((ws / ".forge-run/manifest.json").read_text())
        man.update(unit_verification="uspec-gtest-v1", hal_unit_isolation="ll-fake-v1")
        write(ws, ".forge-run/manifest.json", man)

    class AtOwner3(Exception):
        pass

    def pass_prefix(store, phase):
        if phase == "SWE.3":
            raise AtOwner3
        normal_pass(store, phase)

    with monkeypatch.context() as bootstrap:
        bootstrap.setattr(F, "observation_ws", SimpleNamespace(__wrapped__=original))
        bootstrap.setattr(F, "pass_control", pass_prefix)
        with pytest.raises(AtOwner3):
            F.passed.__wrapped__(tmp_path, monkeypatch)
    ws = tmp_path / "state/workorders/WO-CONTROL-SOURCE/workspace"
    PC.save_original(ws, LL, (ws / LL).read_bytes())
    cited = [O.DECLARATION] if pathway == "restored" else []
    if cited:
        D.integrity(ws, [ws / O.DECLARATION], [])  # protected byte snapshot, no execution result
    row = D.report(ws, detected_phase="SWE.2", reported_by="swe2-author", kind="CODE",
        summary="CONTROL supplied flag-clear implementation contradicts the reserved-write SWR.",
        requirement_ids=["SWR-034"], requirement_quote=O.SWR, test_files=cited, evidence_refs=[LL + ":3"])
    assert Store(ws).gate("SWE.2")["decision"] == "PASS"
    assert row["status"] == "OPEN" and D.open_from(ws, "SWE.2") == []
    assert E.claim(ws) == [row["id"]] and D.loops_used(ws) == 0
    path = ws / LL
    path.write_text(path.read_text().replace("x->SR = ~WWDG_SR_EWIF", "x->SR = 0U"))
    assert PC.findings(ws) == []
    normal_pass(Store(ws), "SWE.3")
    baseline = Store(ws).latest_baseline("SWE.3")
    assert D.mark_fixed(ws, "SWE.3", baseline["baseline_id"]) == [row["id"]]
    identity = I.effective_identity(ws, LL)
    result = execute(ws, monkeypatch)
    assert result["status"] == "PASS", result
    assert O.verify(ws, result)[0]["observed"]["sr_reserved_write_values_valid"] is True
    assert D.verify_on_freeze(ws, "SWE.2") == []
    assert D.all_defects(ws)[0]["status"] == "FIXED"
    if pathway == "restored":
        (ws / O.DECLARATION).write_text(json.dumps(O.CASE, sort_keys=True, indent=4))
    assert D.verify_on_freeze(ws, "SWE.4") == []
    defect = D.all_defects(ws)[0]
    assert defect["status"] == "VERIFIED" and D.verification_phase(ws, defect) == "SWE.4"
    assert I.effective_identity(ws, LL) == identity
    if pathway == "restored":
        assert defect["history"][-1]["tools"] == ["gate-reverify"]
        assert defect["history"][-1]["reverify_receipt"]
        assert execute(ws, monkeypatch)["status"] == "PASS"  # fresh normal evidence for current declaration
    else:
        # The actual phase4 ledger is indispensable; an invented phase2 PASS cannot replace it.
        ledger = ws / "evidence/tool-results.jsonl"
        original_ledger = ledger.read_text()
        rows = [json.loads(line) for line in original_ledger.splitlines()]
        for rec in rows:
            if rec.get("phase") == "SWE.4":
                rec["phase"] = "SWE.2"
        ledger.write_text("".join(json.dumps(rec) + "\n" for rec in rows))
        with pytest.raises(ValueError, match="CODE_VERIFICATION_TOOL_MISSING"):
            I.effective_identity(ws, LL)
        ledger.write_text(original_ledger)
    normal_pass(Store(ws), "SWE.4")
    before = files(ws)
    phase5, manifest = F.destination(ws, "WO-CONTROL-EARLY5")
    assert W.resume_from(phase5, manifest, "WO-CONTROL-SOURCE") == ["SWE.5", "SWE.6"]
    assert I.effective_identity(phase5, LL) == identity
    assert C.trace(phase5, O)[1:] == ({"UT-021": "PASS"}, [])
    write(phase5, "software/tests/integration/test_control.c", "int main(void) { return 0; }\n")
    write(phase5, "software/tests/target/test_control.c", O.harness())
    write(phase5, "workproducts/SWE.5/integration_verification_report.md", "# CONTROL\nActual host and target tools.\n")
    assert execute(phase5, monkeypatch, phase="SWE.5", operation=U.OPERATIONS[1])["status"] == "PASS"
    assert execute(phase5, monkeypatch, phase="SWE.5", operation=sim.OPERATIONS[0],
                   server="forge-sim-mcp", args={})["status"] == "PASS"
    normal_pass(Store(phase5), "SWE.5")
    phase6, final = F.destination(phase5, "WO-CONTROL-EARLY6")
    assert W.resume_from(phase6, final, "WO-CONTROL-EARLY5") == ["SWE.6"]
    assert I.effective_identity(phase6, LL) == identity
    assert C.trace(phase6, O)[1:] == ({"UT-021": "PASS"}, [])
    assert files(ws) == before
