"""Production recovery wiring: real role/MCP gates, durable dispatch, native receipts and budgets; no inference."""
import copy
import json
import os
import subprocess
import time
import tomllib
from types import SimpleNamespace

import pytest
from forge_factory.afo import local_agent as L
from forge_factory.afo import planner, policy, recovery, runtime, scheduler
from forge_factory.common import sha256_file
from forge_factory.policy.authz import Authorizer, Binding
from forge_factory.policy.governor import turn_limit
from test_afo_m4_recovery import order  # noqa: F401


@pytest.fixture
def local(order, tmp_path, monkeypatch):  # noqa: F811
    s, o, b, epoch, eff = order
    pol = copy.deepcopy(eff.policy)
    pol["engineering"]["enable_recovery_planner"] = True
    pol["engineering"]["allowed_model_profiles"] = ["qwen3.6:35b-a3b"]
    pol["maintenance"]["enable_factory_maintainer"] = True
    eff = policy.Effective("PILOT", "PILOT", "a" * 64, pol)
    ws = tmp_path / "failed-workspace"
    (ws / ".forge-run").mkdir(parents=True)
    (ws / ".forge-run/manifest.json").write_text(json.dumps({"local_profile": {"id": "local-rtx-v2-omniverse2"}}))
    (ws / ".forge-run/model-profile.json").write_text(json.dumps({"default": "qwen3.6:35b-a3b"}))
    case = planner.case(b, ws, {"attempts": 1})
    monkeypatch.setattr(L, "authorized", lambda *a, **k: True)
    from forge_factory import workorder

    monkeypatch.setattr(workorder, "factory_revision", lambda: {"commit": "1" * 40, "dirty": False})
    return s, o, b, eff, ws, case


def prepare(local, role="afo-recovery-planner"):
    s, o, b, eff, ws, case = local
    return L.prepare(s, o, b["attempt_id"], role, case, ws, eff)


def client(status="RUNNING", tokens=10, matches=None):
    return SimpleNamespace(get_run=lambda rid: {"lifecycle": {"status": {"kind": status}}},
                           usage=lambda rid: {"stages": [{"usage": {"tokens": {"input": tokens, "output": 1}}}]},
                           cancel=lambda rid: 200, list_runs=lambda **kw: matches or [])


def test_native_planner_role_has_only_its_registered_mcp_grants(tmp_path):
    a = Authorizer(Binding("job", str(tmp_path), {"agent": {"role": "afo-recovery-planner"}}))
    assert a.decide("agent", "mcp__forge_afo_mcp__read_failure_bundle", {}).allow
    assert a.decide("agent", "mcp__forge_afo_mcp__submit_recovery_plan", {}).allow
    for tool in ["shell", "spawn_agent", "read_file", "write_file", "mcp__forge_maintainer_mcp__write_source"]:
        assert not a.decide("agent", tool, {"path": "software/src/x.c"}).allow
    assert turn_limit("afo-recovery-planner") == 200
    assert turn_limit("afo-factory-maintainer") == 200


def test_overlay_mcp_preflight_really_checks_the_roles():
    from forge_factory.mcp.preflight import preflight

    assert preflight(["afo-recovery-planner"], live=False, include_afo=True)["servers"] == ["forge-afo-mcp"]
    assert preflight(["afo-factory-maintainer"], live=False, include_afo=True)["servers"] == ["forge-maintainer-mcp"]
    assert preflight(["afo-recovery-planner"], live=False)["status"] == "BLOCKED"


def test_local_admission_uses_the_selected_gateway_not_a_fixed_cloud_port(monkeypatch):
    monkeypatch.setattr(scheduler, "launch_manifest", lambda _: {"profile": "local-rtx-v2-omniverse2"})
    assert scheduler.gateway_health_url({}) == "http://127.0.0.1:11456/health"
    monkeypatch.setattr(scheduler, "launch_manifest", lambda _: {})
    assert scheduler.gateway_health_url({}) == "http://127.0.0.1:11437/health"


def test_local_model_recovery_never_falls_back_to_cloud(monkeypatch):
    from forge_factory import workorder

    calls = []
    monkeypatch.setattr(workorder, "run", lambda *a, **k: calls.append(k) or {"fabro_run_id": "R"})
    runtime.launcher({"example": "examples/unused", "model_profile": "qwen3.6:35b-a3b",
                      "profile": "local-rtx-v2-omniverse2"}, "WO-test", {})
    assert calls[0]["model"] == "qwen3.6:35b-a3b" and calls[0]["provider"] == "ollama"
    with pytest.raises(ValueError, match="LOCAL_MODEL_PROFILE_UNKNOWN"):
        runtime.launcher({"example": "unused", "model_profile": "deepseek-flash", "profile": "local-rtx-v2-omniverse2"},
                         "WO-test", {})
    assert len(calls) == 1


def test_case_is_frozen_once_and_budget_refresh_does_not_rewrite_it(local):
    _, _, b, _, ws, case = local
    sha = sha256_file(case)
    assert planner.case(b, ws, {"attempts": 2}) == case
    assert sha256_file(case) == sha
    with pytest.raises(ValueError, match="FROZEN_RECOVERY_CASE_CHANGED"):
        planner.case({**b, "redacted_summary": "changed"}, ws, {})


def test_pending_planner_is_not_misreported_as_no_available_strategy(local):
    s, o, b, eff, ws, _ = local
    eff.policy["engineering"]["allowed_model_profiles"] = []  # no untried model rule before the planner
    calls = []

    def invoke(case):
        calls.append(case)
        raise planner.Pending("job-1")

    with pytest.raises(planner.Pending):
        recovery.decide(s, o, b, ws=ws, eff=eff, auth_models=None, planner=planner.make(invoke))
    assert len(calls) == 1 and recovery.plans(s, o["order_id"]) == []
    assert s.order(o["order_id"])["state"] == "RUNNING"


def test_reservations_survive_store_restart_and_duplicate_requests(local):
    from forge_factory.afo.queue import Store

    s, o, b, eff, ws, case = local
    first = prepare(local)
    second = L.prepare(Store(), o, b["attempt_id"], "afo-recovery-planner", case, ws, eff)
    assert first == second and len(L.records(s, o["order_id"])) == 1


def test_planner_dispatch_once_then_native_receipt_poll(local):
    s, o, _, eff, _, _ = local
    job = prepare(local)
    calls = []
    job = L.poll(s, o, job, eff, client=client(), launch_fn=lambda j: calls.append(j["nonce"]) or "R1")
    assert job["state"] == "RUNNING"
    reply = L.directory(job["job_id"]) / "reply.json"
    reply.parent.mkdir(parents=True, exist_ok=True)
    reply.write_text(json.dumps({"status": "BLOCKED", "artifacts": [], "issues": [], "next_action": "halt"}))
    job = L.poll(s, o, L.records(s, o["order_id"])[0], eff, client=client("SUCCEEDED"),
                 launch_fn=lambda _: pytest.fail("duplicate launch"))
    assert job["state"] == "SUCCEEDED" and job["reported_tokens"] == 11 and len(calls) == 1


@pytest.mark.parametrize("reply", [None, "not JSON", "x" * 2001])
def test_native_success_without_valid_recorded_output_is_failed_not_success(local, reply):
    s, o, _, eff, _, _ = local
    job = prepare(local)
    job.update(state="RUNNING", run_id="R1")
    if reply is not None:
        p = L.directory(job["job_id"]) / "reply.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(reply)
    job = L.poll(s, o, job, eff, client=client("SUCCEEDED"))
    assert job["state"] == "FAILED" and job["error"] == "LOCAL_AGENT_OUTPUT_MISSING_OR_INVALID"
    assert job["reported_tokens"] == 11 and job["reserved_tokens"] == 16000


def test_schema_length_feedback_survives_mcp_issue_limit_and_allows_corrected_plan(local, monkeypatch):
    from forge_factory.mcp import sdk
    from forge_factory.mcp.servers import afo

    _, _, b, _, ws, case = local
    monkeypatch.delenv("FORGE_MCP_TRUST", raising=False)
    monkeypatch.setenv("FORGE_AFO_CASE", str(case))
    monkeypatch.setenv("FORGE_BINDING_ID", "schema-feedback")
    tool = "mcp__forge_afo_mcp__submit_recovery_plan"
    op = next(o for o in afo.OPERATIONS if o.name == "submit_recovery_plan")
    plan = recovery._base(b, "REWORK_LOCAL", "SWE.3", "R" * 201, material_difference_ref="M" * 201)
    def submit(p):
        args = {"plan_json": json.dumps(p)}
        sdk.issue_ticket("schema-feedback", tool, args, "afo-recovery-planner", "agent", None, str(ws))
        return sdk.invoke("forge-afo-mcp", op, args)
    denied = submit(plan)
    assert denied["status"] == "BLOCKED"
    assert all("maxLength=200" in issue and "actual_length=201" in issue for issue in denied["issues"])
    assert not (case.parent / "proposed-plan.json").exists()
    plan.update(material_difference_ref="unit-map:repair-cross-unit-links", rationale_code="REPAIR_SPEC_ID_OWNERSHIP")
    assert submit(plan)["status"] == "PASS"
    assert json.loads((case.parent / "proposed-plan.json").read_text()) == plan


@pytest.mark.parametrize("invalid", [None, "string_budget", "numeric_schema", "both_inputs"])
def test_structured_plan_tool_exposes_and_enforces_the_existing_contract(local, monkeypatch, invalid):
    from forge_factory.mcp import sdk
    from forge_factory.mcp.servers import afo

    _, _, b, _, ws, case = local
    app = sdk.build_server("forge-afo-mcp", afo.OPERATIONS)
    wire = next(t.parameters for t in app._tool_manager.list_tools() if t.name == "submit_recovery_plan")
    assert wire["properties"]["plan"]["anyOf"][0]["$ref"] == "#/$defs/RecoveryPlan"
    schema = wire["$defs"]["RecoveryPlan"]
    assert schema == afo.PLAN_SCHEMA
    assert schema["required"] == afo.PLAN_SCHEMA["required"]
    assert schema["properties"]["schema_version"]["const"] == "1.0"
    assert schema["properties"]["material_difference_ref"]["maxLength"] == 200
    assert schema["properties"]["budget_estimate"]["properties"]["tokens_max"]["type"] == "integer"
    monkeypatch.delenv("FORGE_MCP_TRUST", raising=False)
    monkeypatch.setenv("FORGE_AFO_CASE", str(case))
    monkeypatch.setenv("FORGE_BINDING_ID", "typed-plan")
    plan = recovery._base(b, "REWORK_LOCAL", "SWE.3", "REPAIR_SPEC_ID_OWNERSHIP")
    if invalid == "string_budget":
        plan["budget_estimate"]["tokens_max"] = "5000"
    elif invalid == "numeric_schema":
        plan["schema_version"] = 1.0
    args = {"plan": plan}
    if invalid == "both_inputs":
        args["plan_json"] = json.dumps(plan)
    tool = "mcp__forge_afo_mcp__submit_recovery_plan"
    op = next(o for o in afo.OPERATIONS if o.name == "submit_recovery_plan")
    sdk.issue_ticket("typed-plan", tool, args, "afo-recovery-planner", "agent", None, str(ws))
    out = sdk.invoke("forge-afo-mcp", op, args)
    assert out["status"] == ("PASS" if invalid is None else "BLOCKED")
    assert (case.parent / "proposed-plan.json").exists() == (invalid is None)


def test_crash_after_accept_is_adopted_by_nonce_without_repeat(local):
    s, o, _, eff, _, _ = local
    job = prepare(local)
    job = L.poll(s, o, job, eff, client=client(), launch_fn=lambda _: (_ for _ in ()).throw(OSError("lost receipt")))
    assert job["state"] == "LAUNCHING"
    hits = [{"id": "accepted", "labels": {"afo_agent": job["job_id"], "afo_nonce": job["nonce"]}}]
    job = L.poll(s, o, L.records(s, o["order_id"])[0], eff, client=client(matches=hits),
                 launch_fn=lambda _: pytest.fail("duplicate launch"))
    assert job["state"] == "RUNNING" and job["run_id"] == "accepted"


@pytest.mark.parametrize("multiple", [False, True])
def test_uncertain_launches_block_without_replay(local, multiple):
    s, o, _, eff, _, _ = local
    job = prepare(local)
    job.update(state="LAUNCHING", created_epoch=time.time() - 200)
    L.save(s, job)
    hits = [{"id": str(i), "labels": {"afo_agent": job["job_id"], "afo_nonce": job["nonce"]}} for i in range(2)]
    job = L.poll(s, o, job, eff, client=client(matches=hits if multiple else []),
                 launch_fn=lambda _: pytest.fail("duplicate launch"))
    assert job["state"] == "UNKNOWN" and len(L.records(s, o["order_id"])) == 1


@pytest.mark.parametrize("reason", ["wall", "policy", "case", "tokens"])
def test_limits_and_revocation_stop_existing_agent(local, reason):
    s, o, _, eff, _, case = local
    job = prepare(local)
    job.update(state="RUNNING", run_id="R1")
    if reason == "wall":
        job["deadline_epoch"] = time.time() - 1
    if reason == "policy":
        job["policy_sha256"] = "b" * 64
    if reason == "case":
        case.chmod(0o600)
        case.write_text("{}")
    cancelled = []
    c = client(tokens=100000 if reason == "tokens" else 10)
    c.cancel = lambda rid: cancelled.append(rid) or 200
    job = L.poll(s, o, job, eff, client=c)
    assert job["state"] in ("TIMED_OUT", "REVOKED", "FAILED")
    assert cancelled == ["R1"]


@pytest.mark.parametrize("mode", ["OBSERVE_ONLY", "DISABLED"])
def test_no_jobs_in_non_operating_modes(local, mode):
    s, o, b, eff, ws, case = local
    disabled = policy.Effective(mode, mode, eff.sha256, eff.policy)
    with pytest.raises(Exception, match="LOCAL_AGENT_NOT_AUTHORIZED"):
        L.prepare(s, o, b["attempt_id"], "afo-recovery-planner", case, ws, disabled)
    assert L.records(s, o["order_id"]) == []


def test_missing_usage_is_unknown_and_capacity_stays_reserved(local):
    s, o, _, eff, _, _ = local
    job = prepare(local)
    job.update(state="RUNNING", run_id="R1")
    c = client("SUCCEEDED")
    c.usage = lambda _: {"stages": []}
    job = L.poll(s, o, job, eff, client=c)
    assert job["reported_tokens"] is None and job["reserved_tokens"] == 16000


def test_call_budget_is_reserved_even_after_failure(local):
    s, o, b, eff, ws, case = local
    eff.policy["budgets"]["max_recovery_model_calls_per_order"] = 1
    job = prepare(local)
    job["state"] = "FAILED"
    L.save(s, job)
    with pytest.raises(Exception, match="RECOVERY_MODEL_CALL_BUDGET_EXHAUSTED"):
        L.prepare(s, o, b["attempt_id"] + "-next", "afo-recovery-planner", case, ws, eff)


def test_official_compact_artifact_reference_is_accepted(local):
    _, _, b, _, _, case = local
    plan = recovery._base(b, "REWORK_LOCAL", "SWE.3", "TECHNIQUE", artifact_scope=["software/hal"])
    (case.parent / "proposed-plan.json").write_text(json.dumps(plan))
    raw = json.dumps({"status": "PASS", "artifacts": [f"afo-plan:{plan['plan_id']}"], "issues": [], "next_action": "next"})
    assert planner.parse(raw, case.parent) == plan


def test_plan_for_another_fingerprint_is_rejected(local):
    s, o, b, eff, _, _ = local
    plan = recovery._base(b, "REWORK_LOCAL", "SWE.3", "TECHNIQUE")
    plan["failure_fingerprint"] = "another-failure"
    assert "PLAN_NOT_FOR_THIS_FAILURE" in recovery.validate(plan, b, store=s, order=o, eff=eff, auth_models=None)


def test_real_skill_mcp_preflight_and_native_workflow_validation(local, monkeypatch):
    from forge_factory.lrtx import profile

    job = prepare(local)
    real_run = subprocess.run
    real_fabro = os.environ["FORGE_FABRO_BIN"]
    launches = []
    monkeypatch.setattr(profile, "select", lambda *a, **k: {"id": job["profile"], "local_only": True})
    monkeypatch.setenv("FORGE_FABRO_BIN", "/unused/fake-fabro")

    def run(argv, **kw):
        if argv[0] == "/unused/fake-fabro":
            launches.append(argv)
            return SimpleNamespace(returncode=0, stdout="RUN-LOCAL-1\n")
        return real_run(argv, **kw)

    monkeypatch.setattr(subprocess, "run", run)
    assert L.launch(job) == "RUN-LOCAL-1"
    ws = L.directory(job["job_id"]) / "workspace"
    config = tomllib.loads((ws / ".forge-run/workflow.toml").read_text())
    assert config["run"]["model"] == {"name": job["model"], "provider": "ollama"}
    assert set(config["run"]["agent"]["mcps"]) == {"forge_afo_mcp"}
    assert config["run"]["agent"]["mcps"]["forge_afo_mcp"]["env"]["FORGE_AFO_CASE"] == job["case"]
    assert (ws / ".fabro/skills/afo-recovery-planner/SKILL.md").is_file()
    assert {p.name for p in (ws / ".fabro/skills").iterdir()} == {job["role"]}
    assert not real_run(["git", "-C", str(ws), "status", "--porcelain"], capture_output=True, text=True).stdout
    r = real_run([real_fabro, "validate", str(ws / ".forge-run/workflow.fabro")],
                 capture_output=True, text=True, timeout=30)
    assert r.returncode == 0, r.stderr + r.stdout
    assert len(launches) == 1


def test_case_data_crosses_the_real_mcp_ticket_boundary_without_120_char_truncation(local, monkeypatch):
    from forge_factory.mcp import sdk
    from forge_factory.mcp.servers import afo

    _, _, _, _, ws, case = local
    doc = json.loads(case.read_text())
    doc["bundle"]["redacted_summary"] = "finding-" * 5000 + " END_OF_FINDINGS"
    case.chmod(0o600)
    case.write_text(json.dumps(doc))
    monkeypatch.delenv("FORGE_MCP_TRUST", raising=False)
    monkeypatch.setenv("FORGE_AFO_CASE", str(case))
    monkeypatch.setenv("FORGE_BINDING_ID", "local-autonomy-test")
    tool = "mcp__forge_afo_mcp__read_failure_bundle"
    op = next(o for o in afo.OPERATIONS if o.name == "read_failure_bundle")
    chunks, offset = [], 0
    while True:
        sdk.issue_ticket("local-autonomy-test", tool, {"offset": offset}, "afo-recovery-planner", "agent", None, str(ws))
        out = sdk.invoke("forge-afo-mcp", op, {"offset": offset})
        assert out["status"] == "PASS" and len(json.dumps(out).encode()) <= 65536
        chunks.append(out["metrics"]["data"])
        offset = out["metrics"]["next_offset"]
        if offset is None:
            break
    body = json.loads("".join(chunks))
    assert body["redacted_summary"].endswith("END_OF_FINDINGS")
    assert body["order_id"] == doc["bundle"]["order_id"]
    assert len(chunks) > 1


def test_validated_strategy_reaches_only_its_author_and_keeps_packet_accounting(local):
    from forge_factory.afo import recovery_context as C
    from forge_factory.lrtx import runner
    from forge_factory.lrtx import structured as S
    from forge_factory.workflow.builder import build

    _, _, b, _, ws, _ = local
    plan = recovery._base(b, "REWORK_LOCAL", "SWE.3", "CHANGE_TECHNIQUE", artifact_scope=["software/hal"],
                          notes="use the named API from the accepted allocation")
    man = json.loads((ws / ".forge-run/manifest.json").read_text())
    C.install(ws, man, plan)
    graph, nodes = build("WO-local-test", recovery_plan=plan)
    assert "use the named API from the accepted allocation" in graph
    import re

    for name, role in nodes.items():
        match = re.search(rf'  {name} \[.*?prompt="((?:\\.|[^"\\])*)"', graph, re.S)
        if match and role["role"].endswith("-inspector"):
            assert "source_plan_sha256" not in match.group(1)
    args = dict(phase="SWE.3", task="repair", role="swe3-author", model="qwen", with_skill=False,
                instructions="fix", sources=[], criteria=[], output_schema={"type": "object"})
    before = S.packet(**args)
    after = runner._call(ws, S.packet, **args)
    assert after["sources"] == [{"path": C.PATH, "sha256": man["recovery_plan"]["sha256"]}]
    assert after["input_hash"] != before["input_hash"]
    assert after["accounting"]["serialized_chars"] > before["accounting"]["serialized_chars"]
    assert S.RECOVERY_WORKSPACE.get() is None


def test_return_to_requirements_does_not_disclose_downstream_code_in_diagnosis(local):
    from forge_factory.afo import recovery_context as C

    _, _, b, _, ws, _ = local
    plan = recovery._base(b, "RETURN_TO_OWNING_UPSTREAM_PHASE", "SWE.1", "DOWNSTREAM_CODE_SECRET",
                          notes="DOWNSTREAM_CODE_SECRET", material_difference_ref="DOWNSTREAM_CODE_SECRET")
    man = json.loads((ws / ".forge-run/manifest.json").read_text())
    C.install(ws, man, plan)
    assert "DOWNSTREAM_CODE_SECRET" not in (ws / C.PATH).read_text()
    assert C.source(ws, "SWE.1", "swe1-author") is not None
    assert C.source(ws, "SWE.1", "swe1-inspector") is None
    assert C.source(ws, "SWE.2", "swe2-author") is None


def test_supervisor_cancels_when_mode_is_revoked_and_never_dispatches(local, monkeypatch):
    s, o, _, eff, _, _ = local
    job = prepare(local)
    job.update(state="RUNNING", run_id="R1")
    L.save(s, job)
    cancelled = []
    c = client()
    c.cancel = lambda rid: cancelled.append(rid) or 200
    monkeypatch.setattr(L, "FabroClient", lambda **k: c)
    monkeypatch.setattr(L, "launch", lambda _: pytest.fail("supervision dispatched a model"))
    disabled = policy.Effective("DISABLED", "DISABLED", eff.sha256, eff.policy)
    assert L.supervise(s, disabled)[0]["state"] == "REVOKED"
    assert cancelled == ["R1"]


def test_healthy_supervisor_does_not_dispatch_a_prepared_job(local, monkeypatch):
    s, o, _, eff, _, _ = local
    prepare(local)
    monkeypatch.setattr(L, "launch", lambda _: pytest.fail("supervision dispatched a model"))
    assert L.supervise(s, eff) == []
    assert L.records(s, o["order_id"])[0]["state"] == "PREPARED"


def test_failed_diagnosis_is_an_explicit_reason_not_an_exhausted_strategy(local):
    s, o, b, eff, ws, _ = local
    eff.policy["engineering"]["allowed_model_profiles"] = []

    def invoke(case):
        raise planner.Failed("UNKNOWN:receipt-not-found")

    d = recovery.decide(s, o, b, ws=ws, eff=eff, auth_models=None, planner=planner.make(invoke))
    assert d["source"] == "RULE" and d["plan"]["strategy"] == "CLOSE_BLOCKED"
    assert d["plan"]["rationale_code"] == "LOCAL_DIAGNOSIS_FAILED:UNKNOWN:receipt-not-found"


def test_dirty_factory_source_is_refused_before_any_local_model_connection(local, monkeypatch):
    from forge_factory import workorder
    from forge_factory.lrtx import profile

    job = prepare(local)
    monkeypatch.setattr(workorder, "factory_revision", lambda: {"commit": "1" * 40, "dirty": True})
    monkeypatch.setattr(profile, "select", lambda *a, **k: pytest.fail("profile contacted before source refusal"))
    with pytest.raises(RuntimeError, match="REVISION_CHANGED_OR_DIRTY"):
        L.launch(job)


def test_maintainer_submission_dispatches_one_independent_review_without_blocking_conductor(local, monkeypatch):
    from forge_factory.afo import maintainer

    s, o, b, eff, ws, _ = local
    d = recovery.decide(s, o, {**b, "failure_class": "FACTORY_CODE_DEFECT"}, ws=ws, eff=eff, auth_models=None)
    epoch = s.acquire_lease("scheduler", "A", 120)
    recovery.execute(s, o, d, epoch=epoch, eff=eff, previous_wo="original")
    pid = f"mnt-{o['order_id'].removeprefix('afo-')[:16]}-a1"
    case = maintainer.case_dir(pid) / "case.json"
    case.parent.mkdir(parents=True)
    case.write_text(json.dumps({"proposal_id": pid, "incident": {}}))
    (case.parent / "submission.json").write_text("{}")
    monkeypatch.setattr(runtime, "workspace_of", lambda _: ws)
    calls = []

    def submitted(store, current_order, job, eff):
        job["state"] = "SUCCEEDED"
        L.directory(job["job_id"]).mkdir(parents=True, exist_ok=True)
        L.save(store, job)
        return job

    monkeypatch.setattr(L, "poll", submitted)
    monkeypatch.setattr(subprocess, "Popen", lambda argv, **kw: calls.append(argv))
    assert L.sweep_maintenance(s, eff)[0]["state"] == "SUCCEEDED"
    assert L.sweep_maintenance(s, eff)[0]["state"] == "SUCCEEDED"
    assert len(calls) == 1 and calls[0][2:4] == ["forge_factory.afo.local_agent", "review"]
    assert L.records(s, o["order_id"])[0]["review_state"] == "DISPATCHED"


def test_external_deployment_policy_still_requires_a_real_owner_signature(tmp_path, monkeypatch):
    from forge_factory.common import REPO_ROOT, load_yaml

    pol = load_yaml(REPO_ROOT / "config/factory/afo-policy.yaml")
    pol.update(mode="PILOT", authorization_ref="unsigned-autonomy")
    import yaml

    p = tmp_path / "deployment-policy.yaml"
    p.write_text(yaml.safe_dump(pol))
    monkeypatch.setenv("FORGE_AFO_POLICY", str(p))
    eff = policy.load()
    assert eff.requested_mode == "PILOT" and eff.mode == "OBSERVE_ONLY"
    assert "NOT_AUTHORIZED" in eff.issues[0]


@pytest.mark.parametrize("approved", [True, False])
def test_legacy_fresh_revalidation_requires_the_owner_approved_exact_revision(local, monkeypatch, approved):
    from forge_factory import workorder
    from forge_factory.afo import authz
    from forge_factory.common import state_dir

    s, o, b, eff, ws, _ = local
    previous = state_dir() / "workorders/WO-legacy/workspace/.forge-run"
    previous.mkdir(parents=True)
    (previous / "manifest.json").write_text(json.dumps({"factory_revision": {"commit": "0" * 40}}))
    eff.policy["authorization_ref"] = "OWNER-1"
    auth = ws / "auth"
    auth.mkdir()
    (auth / "OWNER-1.json").write_text(json.dumps({"signed_runbook_ref": "factory-revision:" + ("1" if approved else "2") * 40}))
    monkeypatch.setattr(authz, "AUTH_DIR", auth)
    monkeypatch.setattr(authz, "find", lambda *a, **k: SimpleNamespace(allow=True))
    monkeypatch.setattr(policy, "load", lambda: eff)
    calls = []
    monkeypatch.setattr(workorder, "run", lambda *a, **kw: calls.append(kw) or {"fabro_run_id": "NEW-RUN"})
    man = {"example": "unused", "profile": "local-rtx-v2-omniverse2", "model": "qwen3.6:35b-a3b",
           "resume_from": "WO-legacy", "approved_factory_revision": "1" * 40,
           "resume_upto": "SWE.1", "revalidate_author_tasks": True}
    if approved:
        runtime.launcher(man, "WO-new", {"afo_attempt": b["attempt_id"]})
        assert calls[0]["resume"] is None and calls[0]["fresh_recovery_from"] == "WO-legacy"
        assert calls[0]["resume_upto"] is None and calls[0]["revalidate_author_tasks"] is True
    else:
        with pytest.raises(RuntimeError, match="NOT_OWNER_AUTHORIZED"):
            runtime.launcher(man, "WO-new", {"afo_attempt": b["attempt_id"]})
        assert not calls


def test_fresh_recovery_never_reads_a_live_source_as_terminal(local, monkeypatch):
    from forge_factory import workorder
    from forge_factory.common import state_dir
    from forge_factory.fabro import client as F

    _, _, _, _, ws, _ = local
    old = state_dir() / "workorders/WO-live/workspace/.forge-run"
    old.mkdir(parents=True)
    (old / "fabro_run_id").write_text("LIVE")
    (old / "manifest.json").write_text(json.dumps({"work_order": "WO-live"}))
    example = ws / "example"
    example.mkdir()
    (example / "workorder.json").write_text("{}")
    monkeypatch.setattr(F, "client_for_workspace", lambda _: client("RUNNING"))
    monkeypatch.setattr(workorder, "prepare", lambda *a, **k: pytest.fail("prepared from a live source"))
    with pytest.raises(ValueError, match="SOURCE_NOT_TERMINAL"):
        workorder.run(example, "WO-new", fresh_recovery_from="WO-live")


def test_order_deadline_cancels_only_the_managed_parent_without_claiming_terminal(local, monkeypatch):
    from forge_factory.afo import authority, dispatch

    s, o, _, eff, _, _ = local
    monkeypatch.setattr(authority, "decide", lambda *a, **k: SimpleNamespace(allow=True))
    cancelled = []
    c = client()
    c.cancel = lambda rid: cancelled.append(rid) or 202
    end = o["created_epoch"] + eff.get("budgets.max_order_wall_seconds")
    assert dispatch.enforce_deadlines(s, eff, client=c, now=end - 1) == []
    assert dispatch.enforce_deadlines(s, eff, client=c, now=end + 1)[0]["cancellation_requested"]
    assert cancelled == ["RUN1"]
    assert s.order(o["order_id"])["state"] == "RUNNING"  # authoritative Fabro reconciliation still decides
