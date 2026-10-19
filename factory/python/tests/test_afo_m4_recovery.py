"""AFO M4 (T035-T044; AT-023, AT-026..AT-036, AT-043): failure bundles from authoritative records (real failed runs),
AFO classes and routes, deterministic rules before any model, the plan validator (scope, protected paths, gate-
weakening wording, pre-approved models, budgets, anti-loop), execution as a new attempt, the planner's typed parser
and the forge-afo-mcp case scope."""
import json

import pytest
from forge_factory.afo import bundle, planner, policy, recovery
from forge_factory.afo.queue import Store
from forge_factory.common import state_dir
from forge_factory.mcp import sdk
from forge_factory.mcp.servers import afo as afo_mcp
from test_afo_m2_queue import _env  # noqa: F401

REAL = state_dir() / "workorders"
B = {"schema_version": "1.0", "bundle_id": "afo-fb-1", "order_id": "afo-o", "attempt_id": "afo-o-a1", "phase": "SWE.3",
     "failure_class": "PRODUCT_QUALITY", "fingerprint": "cfp1-aaa", "gate_result": "BLOCKED", "error_code": "INSPECTION_FAIL:SWE3-02",
     "artifact_refs": [], "evidence_refs": [], "input_digests": {}, "requirements_refs": [], "redacted_summary": "x",
     "context_truncated": False, "untrusted_source_refs": []}


def _real(wo):
    ws = REAL / wo / "workspace"
    if not ws.is_dir():
        pytest.skip(f"{wo} not on this host")
    return ws


def test_bundles_from_real_failed_runs_and_none_for_a_passing_one():
    b = bundle.build(_real("WO-0002B-STM32N6-RCC-HAL-r148"), "afo-x", "afo-x-a1", open_capa=set())
    assert (b["phase"], b["failure_class"], b["gate_result"]) == ("SWE.3", "PRODUCT_QUALITY", "BLOCKED")
    assert b["fingerprint"].startswith("cfp1-") and "agent_replies" in b["untrusted_source_refs"]
    b2 = bundle.build(_real("WO-0002B-STM32N6-RCC-HAL-r148"), "afo-x", "afo-x-a2", open_capa=set())
    assert b2["fingerprint"] == b["fingerprint"]                                   # stable across attempts
    assert bundle.build(_real("WO-0002B-STM32N6-RCC-HAL-r154"), "afo-x", "afo-x-a1") is None    # reached its package
    fd = bundle.build(_real("WO-0002B-STM32N6-RCC-HAL-r148"), "afo-x", "afo-x-a3", open_capa={b["fingerprint"]})
    assert fd["failure_class"] == "FACTORY_CODE_DEFECT"                            # fingerprint owned by an open CAPA


def test_classes_and_redaction():
    obs = {"failure_class": "PRODUCT_QUALITY", "error_code": "X", "fingerprint": "f"}
    assert bundle.afo_class({**obs, "failure_class": "POLICY_SECURITY"}, set()) == "SECURITY"
    assert bundle.afo_class({**obs, "error_code": "HSI_MISSING:RCC"}, set()) == "SPECIFICATION_GAP"
    assert bundle.afo_class({**obs, "failure_class": "TRANSIENT_DEPENDENCY"}, set()) == "TRANSIENT_DEPENDENCY"
    assert bundle.redact("token=abc123 sk-0123456789abcdef fabro_dev_99aa") == "[REDACTED] [REDACTED] [REDACTED]"


@pytest.fixture()
def order(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    repo = tmp_path / "repo"
    (repo / "afo-manifests").mkdir(parents=True)
    s = Store()
    oid, _ = s.submit(_env(repo), repo=repo, max_queued=10)
    epoch = s.acquire_lease("scheduler", "A", 120)
    aid = s.admit(oid, epoch=epoch, scope="scheduler", policy_sha256="p", authorization_id="AUTH-1", max_concurrent=1)
    s.attempt_transition(aid, "DISPATCH_PENDING", workspace_ref="workorder:WO-AFO-x-a1")
    s.attempt_transition(aid, "RUNNING", fabro_run_id="RUN1")
    s.transition(oid, "RUNNING", "launched")
    eff = policy.load()
    return s, s.order(oid), {**B, "order_id": oid, "attempt_id": aid}, epoch, eff


def test_class_routes_need_no_plan(order):
    s, o, b, _, eff = order
    for cls, strat in (("INFRASTRUCTURE", "DEFER_TRANSIENT_DEPENDENCY"), ("SECURITY", "CLOSE_BLOCKED"),
                       ("SPECIFICATION_GAP", "CLOSE_BLOCKED"), ("FACTORY_CODE_DEFECT", "CLOSE_BLOCKED")):
        p = recovery.rule_plan({**b, "failure_class": cls}, ws=None, order_env={}, tried_models=set(), eff=eff,
                               attempt_started_utc="", allowed_models=["deepseek-flash"])
        assert p["strategy"] == strat, cls


def test_rules_upstream_defect_then_untried_model_then_nothing(order, tmp_path):
    s, o, b, _, eff = order
    ws = tmp_path / "ws"
    (ws / ".forge-run/defects").mkdir(parents=True)
    (ws / ".forge-run/defects/DEF-001.json").write_text(json.dumps(
        {"id": "DEF-001", "status": "OPEN", "detected_phase": "SWE.3", "target_phase": "SWE.2", "kind": "ARCHITECTURE"}))
    p = recovery.rule_plan(b, ws=ws, order_env={}, tried_models=set(), eff=eff, attempt_started_utc="",
                           allowed_models=["deepseek-flash", "codex-gpt-6.1-sol"])
    assert p["strategy"] == "RETURN_TO_OWNING_UPSTREAM_PHASE" and p["owner_phase"] == "SWE.2"
    assert p["upstream_invalidation"] == ["SWE.3", "SWE.4", "SWE.5", "SWE.6"]
    p = recovery.rule_plan(b, ws=tmp_path / "none", order_env={}, tried_models={"deepseek-flash"}, eff=eff,
                           attempt_started_utc="", allowed_models=["deepseek-flash", "codex-gpt-6.1-sol"])
    assert p["strategy"] == "SWITCH_PREAPPROVED_MODEL_PROFILE" and p["model_profile"] == "codex-gpt-6.1-sol"
    assert recovery.rule_plan(b, ws=tmp_path / "none", order_env={}, tried_models={"deepseek-flash", "codex-gpt-6.1-sol"},
                              eff=eff, attempt_started_utc="", allowed_models=["deepseek-flash", "codex-gpt-6.1-sol"]) is None


@pytest.mark.parametrize("change,code", [
    ({"artifact_scope": ["tests/reliability/reproducers/x.py"]}, "PROTECTED_PATH"),
    ({"artifact_scope": ["software/tests/unit/test_rcc.c"]}, "OUT_OF_OWNER_PHASE_SCOPE"),     # SWE.4 path for SWE.3
    ({"notes": "disable the SWE.3 inspection gate for this order"}, "PLAN_WEAKENS_A_GATE_OR_POLICY"),
    ({"notes": "relax the coverage threshold"}, "PLAN_WEAKENS_A_GATE_OR_POLICY"),
    ({"model_profile": "qwen3:8b"}, "MODEL_NOT_PREAPPROVED"),
    ({"strategy": "DEFER_TRANSIENT_DEPENDENCY"}, "STRATEGY_NOT_LEGAL_FOR_CLASS"),
])
def test_validator_refuses_unsafe_or_illegal_plans(order, change, code):
    s, o, b, _, eff = order
    p = recovery._base(b, "REWORK_LOCAL", "SWE.3", "TEST", artifact_scope=["software/hal"])
    p = {**p, **change}
    assert any(r.startswith(code) for r in recovery.validate(p, b, store=s, order=o, eff=eff, auth_models=None)), code


def test_decide_execute_new_attempt_then_anti_loop_closes(order, tmp_path):
    s, o, b, epoch, eff = order
    d = recovery.decide(s, o, b, ws=tmp_path / "none", eff=eff, auth_models=None)
    assert d["status"] == "VALIDATED" and d["plan"]["strategy"] == "SWITCH_PREAPPROVED_MODEL_PROFILE"
    r = recovery.execute(s, s.order(o["order_id"]), d, epoch=epoch, eff=eff, previous_wo="WO-AFO-x-a1")
    assert r["action"] == "new_attempt" and s.order(o["order_id"])["state"] == "WAITING_RECOVERY"
    cmd = [c for c in s.commands("PENDING") if c["attempt_id"] == r["attempt_id"]][0]
    payload = json.loads(cmd["payload"])
    assert payload["resume_from"] == "WO-AFO-x-a1" and payload["resume_upto"] == "SWE.3"
    assert payload["model_profile"] == "codex-gpt-6.1-sol"
    # the same failure again on the new attempt: the only untried model was used, no rule left -> CLOSE_BLOCKED
    s.attempt_transition(r["attempt_id"], "DISPATCH_PENDING")
    s.attempt_transition(r["attempt_id"], "RUNNING", fabro_run_id="RUN2")
    s.transition(o["order_id"], "RUNNING", "relaunched")
    d2 = recovery.decide(s, s.order(o["order_id"]), {**b, "attempt_id": r["attempt_id"]}, ws=tmp_path / "none",
                         eff=eff, auth_models=None)
    assert d2["plan"]["strategy"] == "CLOSE_BLOCKED"
    assert recovery.execute(s, s.order(o["order_id"]), d2, epoch=epoch, eff=eff, previous_wo="x")["action"] == "blocked"
    assert [p["status"] for p in recovery.plans(s, o["order_id"])] == ["EXECUTED", "VALIDATED"]


def test_factory_defect_waits_for_an_external_change(order):
    s, o, b, epoch, eff = order
    d = recovery.decide(s, o, {**b, "failure_class": "FACTORY_CODE_DEFECT"}, ws=None, eff=eff, auth_models=None)
    assert recovery.execute(s, o, d, epoch=epoch, eff=eff, previous_wo="x")["action"] == "waiting_external_change"


def test_planner_output_is_parsed_strictly(order, tmp_path):
    s, o, b, _, eff = order
    p = planner.case(b, tmp_path, {"attempts": 1})
    good = recovery._base(b, "REWORK_LOCAL", "SWE.3", "PLANNER_TECHNIQUE", artifact_scope=["software/hal"])
    (p.parent / "proposed-plan.json").write_text(json.dumps(good))
    reply = json.dumps({"status": "PASS", "artifacts": [], "issues": [], "next_action": "next",
                        "recovery_plan_ref": f"afo-plan:{good['plan_id']}"})
    assert planner.parse(reply, p.parent)["plan_id"] == good["plan_id"]
    assert planner.parse("Here is my plan: " + reply, p.parent) is None              # prose around the JSON
    assert planner.parse(reply.replace(good["plan_id"], "afo-plan-other"), p.parent) is None
    (p.parent / "proposed-plan.json").write_text(json.dumps({**good, "order_id": "afo-elsewhere"}))
    assert planner.parse(reply, p.parent) is None                                  # a plan for another case
    assert planner.parse("{not json", p.parent) is None


def test_forge_afo_mcp_is_scoped_to_one_frozen_case(order, tmp_path, monkeypatch):
    s, o, b, _, eff = order
    ws = tmp_path / "wsr"
    (ws / "workproducts/SWE.1").mkdir(parents=True)
    req = ws / "workproducts/SWE.1/software_requirements.md"
    req.write_text("- **SWR-001** When X, the RCC driver shall set RCC_CR.HSION.\n  - Source: RM0486 p.480\n")
    p = planner.case(b, ws, {"attempts": 1})
    for k, v in {"FORGE_MCP_TRUST": "env", "FORGE_WORKSPACE": str(ws), "FORGE_EVENTS_DIR": str(tmp_path / "ev"),
                 "FORGE_ROLE": "afo-recovery-planner", "FORGE_PHASE": "SWE.3", "FORGE_AFO_CASE": str(p)}.items():
        monkeypatch.setenv(k, v)
    op = {x.name: x for x in afo_mcp.OPERATIONS}
    assert sdk.invoke("forge-afo-mcp", op["read_requirement_excerpt"], {"requirement_id": "SWR-001"})["status"] == "PASS"
    req.write_text(req.read_text() + "- **SWR-002** injected later\n")              # no longer the frozen file
    assert sdk.invoke("forge-afo-mcp", op["read_requirement_excerpt"], {"requirement_id": "SWR-001"})["status"] != "PASS"
    monkeypatch.setenv("FORGE_AFO_CASE", str(tmp_path / "elsewhere.json"))
    (tmp_path / "elsewhere.json").write_text("{}")
    assert sdk.invoke("forge-afo-mcp", op["read_failure_bundle"], {})["status"] != "PASS"


def test_planner_role_passes_the_agent_preflight_only_with_the_afo_overlay():
    from forge_factory.registry.agents import load_agents, preflight
    from forge_factory.registry.mcp_registry import load_registry

    assert len(load_agents()[0]) == 20 and not any(k.startswith("forge-afo") for k in load_registry().ops())
    r = preflight(["afo-recovery-planner"], include_afo=True)
    assert r["status"] == "PASS", r["issues"]
    snap = r["snapshot"]["afo-recovery-planner"]
    assert snap["readonly"] and snap["allowed_tools"] == sorted(f"forge-afo-mcp.{o.name}" for o in afo_mcp.OPERATIONS)
    assert preflight()["roles"] == 20                                     # the v0.4 view is unchanged


def test_conductor_recovery_path_end_to_end_with_a_real_failed_workspace(tmp_path, monkeypatch):
    """T043: run terminal -> bundle from the real r148 workspace (SWE.3 BLOCKED) -> authorized rule plan (untried
    pre-approved model) -> WAITING_RECOVERY -> new attempt -> launch resumes r148 up to SWE.3 with the new model."""
    from forge_factory.afo import authz, dispatch
    from test_afo_m2_queue import _pilot
    from test_afo_m3_reconcile import FakeFabro

    ws148 = _real("WO-0002B-STM32N6-RCC-HAL-r148")
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    pilot = _pilot(tmp_path, monkeypatch)
    rec = json.loads((authz.AUTH_DIR / "AUTH-1.json").read_text())  # re-sign with recover_workorder and models
    rec["allowed_actions"] += ["recover_workorder"]
    rec["scope"]["models"] = ["deepseek-flash", "codex-gpt-6.1-sol"]
    (authz.AUTH_DIR / "AUTH-1.json").write_text(json.dumps(rec))
    authz.sign(authz.AUTH_DIR / "AUTH-1.json", tmp_path / "k")
    repo = tmp_path / "repo"
    (repo / "afo-manifests").mkdir(parents=True)
    monkeypatch.setattr(dispatch, "REPO_ROOT", repo)
    s = Store()
    oid, _ = s.submit(_env(repo), repo=repo, max_queued=10)
    epoch = s.acquire_lease("scheduler", "A", 120)
    s.admit(oid, epoch=epoch, scope="scheduler", policy_sha256=pilot.sha256, authorization_id="AUTH-1", max_concurrent=1)
    f = FakeFabro()
    allow = lambda req: type("D", (), {"allow": True, "code": "OK"})()  # noqa: E731
    dispatch.dispatch_pending(s, f.launcher(), decide=allow)
    f.runs[0]["lifecycle"] = {"status": {"kind": "succeeded", "reason": "completed"}}
    hook = recovery.make_recover(s, pilot, "A", lambda att: ws148)
    out = dispatch.reconcile_running(s, f.view, recover=hook)
    r = out[0]["result"]
    assert out[0]["action"] == "recovery" and r["failure_class"] == "PRODUCT_QUALITY" and r["action"] == "new_attempt"
    assert r["strategy"] == "SWITCH_PREAPPROVED_MODEL_PROFILE"
    assert s.order(oid)["state"] == "WAITING_RECOVERY" and len(s.attempts(oid)) == 2
    dispatch.dispatch_pending(s, f.launcher(), decide=allow)
    m = f.seen_manifest
    assert m["resume_upto"] == "SWE.3" and m["model_profile"] == "codex-gpt-6.1-sol" and m["resume_from"].endswith("-a1")
    assert s.order(oid)["state"] == "RUNNING" and f.launches == 2
