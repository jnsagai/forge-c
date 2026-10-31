"""Historical SWE.1 refusal/advisory resume route, separate from the M1 success fixture.

Native terminal status, model admission refusal and advisory profile are explicit
fixtures. Preparation, failed inspection, queue/outbox, budgets and brownfield
resume validation/copy are real. No model or live recovery qualification claim.
"""
import json
import time

import pytest
from forge_factory import workorder as WO
from forge_factory.afo import planner, recovery
from forge_factory.afo import product_role_trial as role_trial
from forge_factory.afo.diagnosis_packet import measure_request
from forge_factory.afo.durable import Refused, immutable_json
from forge_factory.afo.mission_ledger import MissionLedger
from forge_factory.brownfield import resume as R
from forge_factory.inspection import gate
from forge_factory.inspection.engine import PHASES, Store
from forge_factory.lrtx import role_capability
from test_afo_m4_recovery import order  # noqa: F401
from test_brownfield_resume import pair  # noqa: F401
from test_da014_product_role_trial import trial  # noqa: F401
from test_resume_from import _all_pass


@pytest.mark.parametrize("pair", ["ASPICE_ONLY"], indirect=True)
def test_failed_swe1_admission_refusal_advisory_resumes_swe1_without_erasing_history(
        order, pair, trial, monkeypatch):  # noqa: F811
    s, o, b, epoch, eff = order
    src, old, dst, new, prepare, _ = pair
    # Both reused fixtures own private stores; retain the brownfield workspace namespace.
    monkeypatch.setenv("FORGE_STATE_DIR", str(src.parents[2]))
    st = Store(src)
    verdicts = _all_pass("SWE.1")
    verdicts["SWE1-05"] = {"verdict": "FAIL", "evidence_refs": ["workproducts/SWE.1/software_requirements.md"],
                              "detail": "Unresolved requirements semantics in the recorded incident fixture."}
    failed = st.record_inspection("SWE.1", "swe1-inspector", st.latest_baseline("SWE.1")["baseline_id"], verdicts)
    assert failed["verdict"] == "FAIL" and st.gate("SWE.1")["decision"] != "PASS"
    original = R.files(src, ".")
    aid = b["attempt_id"]
    s.attempt_transition(aid, "FAILED", exit_status="SWE.1 inspection failed")
    s.transition(o["order_id"], "WAITING_RECOVERY", "recorded SWE.1 failure")
    o = s.order(o["order_id"])
    b = {**b, "phase": "SWE.1", "error_code": "INSPECTION_FAIL:SWE1-05"}
    monkeypatch.setattr(recovery, "rule_plan", lambda *a, **kw: None)
    monkeypatch.setattr(gate, "advisory_enabled", lambda _: True)  # Explicit historical profile fixture.
    calls = []
    # Separately declared qualification-only identity, with explicit fake signer/auth fixtures.
    # This permits testing the context boundary rather than failing on a missing receipt.
    identity = {**trial.doc["roles"]["swe1-author"][0], "role": "afo-recovery-planner",
                "context_tokens": 65536, "reasoning": "xhigh"}
    trial.doc["roles"] = {"afo-recovery-planner": [identity]}
    ref = trial.publish(trial.doc)
    immutable_json(src.parents[2] / ref["path"], trial.doc)
    role_trial.bind(ref, trial.job, trial.eff)
    body = {"model": "local", "messages": [{"role": "user", "content": "administrative fixture " + "x" * 69000}],
            "response_format": {"type": "json_schema"}, "reasoning_effort": "xhigh", "temperature": 0,
            "max_tokens": 32768 + 2048}
    measured = measure_request(body)
    assert measured["input_tokens"] + body["max_tokens"] > identity["context_tokens"]

    def refused_diagnosis(bundle, budget, ws):
        calls.append(bundle["phase"])
        # Complete administrative bytes plus reasoning/output exceed the scoped context.
        # This is never an HTTP call or a semantic finding that no repair strategy exists.
        try:
            role_capability.admit_job(trial.job, "afo-recovery-planner", input_tokens=measured["input_tokens"],
                                      output_tokens=body["max_tokens"], body=body)
        except Refused as exc:
            raise planner.Failed(exc.code) from exc
        pytest.fail("an unqualified diagnosis request must not be generated")

    before = recovery.budget_snapshot(s, o, eff)
    decision = recovery.decide(s, o, b, ws=src, eff=eff, auth_models=None, planner=refused_diagnosis)
    assert calls == ["SWE.1"] and decision["status"] == "VALIDATED"
    assert decision["plan"]["rationale_code"] == "LOCAL_DIAGNOSIS_FAILED:CAPABILITY_LIMIT"
    assert recovery.advisory_final(decision, b, src)
    ledger = MissionLedger(s)
    limits = dict(max_attempts=3, max_jobs=1, max_requests=2, max_tokens=38000,
                  max_tools=10, max_corrections=1, deadline=time.time() + 600)
    ledger.register("incident-mission", "incident:SWE1", limits, "AUTH-fixture", authorize=lambda *args: True)
    ledger.link("incident-mission", o["order_id"])
    ledger.execution("incident-mission", aid, "PRODUCT", reserved_tokens=38000)
    spent = ledger.snapshot("incident-mission")
    result = recovery.execute_advisory(s, o, decision, epoch=epoch, eff=eff,
                                       previous_wo=old["work_order"], bundle=b, ws=src)
    assert result["action"] == "advisory_attempt"
    command = next(c for c in s.commands("PENDING") if c["attempt_id"] == result["attempt_id"])
    payload = json.loads(command["payload"])
    assert payload["resume_from"] == "WO-SRC" and payload["resume_upto"] == "SWE.1"
    assert payload["recovery_exhausted"]["SWE.1"]["rationale_code"] == decision["plan"]["rationale_code"]
    assert WO.resume_from(dst, new, payload["resume_from"], upto=payload["resume_upto"]) == PHASES
    assert Store(dst).latest_baseline("SWE.1") is None and Store(dst).gate("SWE.1")["decision"] != "PASS"
    assert new["resume_lineage"]["attempt_seq"] == 2
    assert R.files(src, ".") == original and st.inspections("SWE.1")[-1] == failed
    after = recovery.budget_snapshot(s, s.order(o["order_id"]), eff)
    assert after["attempts"] == before["attempts"] + 1
    assert after["max_attempts"] == before["max_attempts"] and after["tokens"] == before["tokens"]
    historical = s.attempts(o["order_id"])[0]
    assert historical["state"] == "FAILED" and historical["record"]["exit_status"] == "SWE.1 inspection failed"
    assert ledger.snapshot("incident-mission") == spent and spent["usage_unknown"]
    with pytest.raises(Refused, match="MISSION_ALLOWANCE_EXHAUSTED"):
        ledger.execution("incident-mission", result["attempt_id"], "PRODUCT", reserved_tokens=1)
    # Changed destination identity refuses before a further lineage reservation or artifact copy.
    wrong, man = prepare("WO-INCOMPATIBLE")
    man["scope"] = ["changed objective"]
    snapshot = R.files(wrong, ".")
    with pytest.raises(R.ResumeRefused, match="CONTRACT_OR_RUNTIME_CHANGED"):
        WO.resume_from(wrong, man, "WO-SRC", upto="SWE.1")
    assert R.files(wrong, ".") == snapshot
