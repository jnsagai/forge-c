"""CAPA-191: mission E's qwen trial declared a sampling the stepwise inspector never sends; the refusal looped unbounded.

Omniverse2 owner lane 2026-11-07, WO-F014-SWE1-SPIL-20261107-L41C (V21.3, f283dbae): SWE.1 authoring froze BL-SWE.1-001,
then every inspector call was refused CALL_REFUSED:PRODUCT_ROLE_TRIAL_CONFIGURATION_UNDECLARED (the trial declared the
json_schema inspectors at the profile default temperature 0.2/seed 1; inspector_stepwise sends temperature 0/seed 1).
The visit counted the refused calls (calls 18), so CAPA-085's zero-call breaker never fired: 160 re-inspections in 47
minutes, the run ended PHASE_VERDICT:NO with no route BLOCKED, and the bundle called it INFRASTRUCTURE/transient.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from forge_factory.afo import bundle, recovery
from forge_factory.afo import owner_supervised_development as D
from forge_factory.afo import product_role_trial as T
from forge_factory.afo.durable import digest
from forge_factory.inspection import gate
from forge_factory.inspection.engine import Store
from forge_factory.lrtx.profile import load
from forge_factory.lrtx.review_semantic import inspector_options
from test_lrtx_swe1 import pytestmark, ws  # noqa: F401 - fixture and owner-input precondition
from test_lrtx_swe2 import ws1  # noqa: F401 - fixture

FIX = Path(__file__).parent / "fixtures/owner-supervised-development"
QWEN = "qwen3.8:27b-q8_0"
REFUSED = "CALL_REFUSED:PRODUCT_ROLE_TRIAL_CONFIGURATION_UNDECLARED"


def _profile_ws(tmp_path):
    w = tmp_path / "ws"
    (w / ".forge-run").mkdir(parents=True)
    (w / ".forge-run/manifest.json").write_text(json.dumps({"local_profile": {"id": D.PROFILE}}))
    return w


def test_capa191_every_e_inspector_request_matches_exactly_one_declared_configuration(tmp_path):
    opts = inspector_options(_profile_ws(tmp_path), QWEN)
    assert opts["stepwise"] is True and opts["sampling"] == {"temperature": 0, "seed": 1}
    effort = load(D.PROFILE)["gateway"]["reasoning"][QWEN]["effort"]
    trial = json.loads((FIX / "qwen-trial-e.json").read_text())
    body = {"response_format": {"type": "json_schema"}, "reasoning_effort": effort, **opts["sampling"]}
    for n in range(1, 7):
        role = f"swe{n}-inspector"
        candidates = [i for i in trial["roles"][role] if i["schema_mode"] == "json_schema"
                      and i["reasoning"] == body["reasoning_effort"]
                      and all(body.get(k) == v for k, v in i["sampling"].items())]
        assert len(candidates) == 1, role  # product_role_trial.identity's own selection rule


def test_capa191_the_corrected_envelope_is_pinned_and_the_first_one_is_history_only():
    trial = json.loads((FIX / "qwen-trial-e.json").read_text())
    norm = {r: [{k: v for k, v in i.items() if k != "adapter_revision"} for i in ids] for r, ids in trial["roles"].items()}
    assert digest(norm) == D.ROLE_ENVELOPES_E[QWEN]
    assert D.ROLE_ENVELOPES_E[QWEN] not in D.ROLE_ENVELOPES_E_HISTORY[QWEN]


def _control(monkeypatch, qwen_trial):
    trials = {"hf.co/ornith-ai/Ornith-1.5-35B-A3B-GGUF:Q8_0": json.loads((FIX / "ornith-trial-e.json").read_text()),
              QWEN: qwen_trial}
    rev, deadline = "f" * 40, 1_900_000_000
    for t in trials.values():
        t.update(source_revision=rev, deadline_epoch=deadline, profile=D.PROFILE)
        for ids in t["roles"].values():
            for i in ids:
                i["adapter_revision"] = rev
    refs = {m: {"path": f"afo/product-role-trials/{m}.json", "sha256": m} for m in trials}
    monkeypatch.setattr(T, "resolve", lambda ref: trials[ref["sha256"]])
    return {"mission": {"mission_id": D.MISSION, "limits": {"deadline": deadline}}, "product_role_trials": refs,
            "product_role_trial": refs[D.RUN_MODEL], "source_revision": rev}


def test_capa191_historical_e_controls_still_validate_but_new_issuance_needs_the_fix(monkeypatch):
    old = json.loads((FIX / "qwen-trial-e.json").read_text())
    for ids in old["roles"].values():
        for i in ids:
            if i["schema_mode"] == "json_schema":
                i["sampling"] = {"temperature": 0.2, "seed": 1}
    control = _control(monkeypatch, old)
    D._trial_envelopes(control)  # reconciliation of an issuance made before the fix
    with pytest.raises(Exception, match="ORIGINAL_ROLE_ENVELOPES_REQUIRED"):
        D._trial_envelopes(control, envelopes=D.ROLE_ENVELOPES_E)  # create(): only the corrected envelope
    D._trial_envelopes(_control(monkeypatch, json.loads((FIX / "qwen-trial-e.json").read_text())),
                       envelopes=D.ROLE_ENVELOPES_E)


def _rows(ws_, rows):
    p = ws_ / ".forge-run/lrtx/SWE.1/inspections.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("".join(json.dumps(r) + "\n" for r in rows))


AT = "9999-01-01T00:00:00Z"
ISSUES = [f"SWE1-0{i}: {REFUSED}" for i in range(1, 7)]


def test_capa191_counted_gateway_refusals_block_the_route(ws1):  # noqa: F811
    _rows(ws1, [{"at": AT, "status": "FAILED", "calls": 18, "issues": ISSUES}] * 2)
    assert Store(ws1).gate("SWE.1")["decision"] == "REINSPECT"
    _rows(ws1, [{"at": AT, "status": "FAILED", "calls": 18, "issues": ISSUES}] * 3)
    g = Store(ws1).gate("SWE.1")
    assert g["decision"] == "BLOCKED" and g["reason"] == f"INSPECTOR_REFUSED_REPEATEDLY:SWE1-01: {REFUSED}"
    assert gate.step_route(Store(ws1), "SWE.1") == 1


@pytest.mark.parametrize("issues", [[f"SWE1-0{i}: CALL_REFUSED:server_error" for i in range(1, 4)],
                                    [f"SWE1-01: {REFUSED}", "SWE1-02: LRTX_TIMEOUT"],
                                    ["SWE1-01: INFRA_UNAVAILABLE:MODEL_CALLS_REFUSED (waited 600 s)"]])
def test_capa191_outages_and_answered_calls_keep_reinspection(ws1, issues):  # noqa: F811
    _rows(ws1, [{"at": AT, "status": "FAILED", "calls": 18, "issues": issues}] * 4)
    assert Store(ws1).gate("SWE.1")["decision"] == "REINSPECT"


def _route_ws(tmp_path, reason):
    w = tmp_path / "WO-F014-SWE1-SPIL-20261107-L41C" / "workspace"
    (w / ".forge-run/gates").mkdir(parents=True)
    (w / ".forge-run/manifest.json").write_text(json.dumps(
        {"work_order": "WO-F014-SWE1-SPIL-20261107-L41C", "created_at": "2026-11-07T18:46:17Z",
         "factory_revision": {"commit": "f283dbaeb2d83407e426dd099853d436224c0a88", "basis": "manifest"},
         "driver": "STM32N6_SPI_LL_ST", "target": {"core": "cortex-m55"}}))
    rows = [{"baseline_id": "BL-SWE.1-001", "phase": "SWE.1", "result": "FROZEN", "step": "author",
             "ts": "2026-11-07T20:21:14.911740Z"},
            {"gate": {"decision": "BLOCKED", "phase": "SWE.1", "reason": reason}, "phase": "SWE.1", "step": "route",
             "ts": "2026-11-07T20:22:41.320390Z"}]
    (w / ".forge-run/gates/gate-log.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    return w


def test_capa191_the_blocked_route_goes_to_maintenance(tmp_path):
    reason = f"STUCK: INSPECTOR_REFUSED_REPEATEDLY:SWE1-01: {REFUSED}; external diagnosis required"
    b = bundle.build(_route_ws(tmp_path, reason), "afo-o", "afo-o-a1", open_capa=set(), run_failed=True)
    assert (b["phase"], b["failure_class"], b["error_code"]) == ("SWE.1", "FACTORY_CODE_DEFECT",
                                                                  "PRODUCT_ROLE_TRIAL_CONFIGURATION_UNDECLARED")
    plan = recovery.rule_plan(b, ws=None, order_env={}, tried_models=set(), eff=None,
                              attempt_started_utc="2026-11-07T18:46:17Z", allowed_models=[])
    assert plan["rationale_code"] == "FACTORY_DEFECT_NEEDS_EXTERNAL_CHANGE"


def test_capa191_budget_refusals_and_other_stuck_routes_are_unchanged(tmp_path):
    for i, reason in enumerate(("STUCK: INSPECTOR_REFUSED_REPEATEDLY:SWE1-01: CALL_REFUSED:MISSION_TOKEN_CAPACITY_EXHAUSTED;"
                                " external diagnosis required",
                                "STUCK: repeated rejection without changed evidence; external diagnosis required")):
        b = bundle.build(_route_ws(tmp_path / str(i), reason), "afo-o", "afo-o-a1", open_capa=set(), run_failed=True)
        assert b["failure_class"] != "FACTORY_CODE_DEFECT"
