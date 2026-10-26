"""F015 (owner 2026-10-26: "enable_recovery_planner=true"): the afo-recovery-planner runs as an asynchronous Fabro
single-node run on the Claude login - least-privilege binding (forge-afo-mcp only), never blocking the Conductor
(PENDING while the run goes, the reply once stored, None on a run without reply or past the timeout), and the
recovery path that waits for it (WAITING_RECOVERY, polled) before validating and executing its plan."""
import dataclasses
import json
import tomllib

import pytest
from forge_factory.afo import planner, planner_run, recovery
from forge_factory.policy.authz import Authorizer, Binding
from test_afo_m2_queue import _env  # noqa: F401
from test_afo_m4_recovery import B, order  # noqa: F401


def _case(tmp_path):
    return planner.case({**B, "bundle_id": "afo-fb-test"}, tmp_path / "ws", {"attempts": 1})


def test_the_planner_run_is_bound_to_the_planner_role_and_forge_afo_mcp_only(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    cp = _case(tmp_path)
    ws, toml = planner_run.prepare(cp)
    run = tomllib.loads(toml.read_text())
    assert sorted(run["run"]["agent"]["mcps"]) == ["forge_afo_mcp"]
    assert run["run"]["agent"]["mcps"]["forge_afo_mcp"]["env"]["FORGE_AFO_CASE"] == str(cp.resolve())
    g = (ws / ".forge-run/workflow.fabro").read_text()
    assert "--node afo_planner --agent claude" in g and 'stdin_source="context.response.afo_planner"' in g
    assert "afo-fb-test" in g and "--agent codex" not in g and "qwen" not in g and "ollama" not in g
    assert (ws / ".fabro/skills/afo-recovery-planner/SKILL.md").read_text() == planner_run.SKILL.read_text()
    a = Authorizer(Binding.load(ws / ".forge-run/binding.json"))
    assert a.decide("afo_planner", "mcp__forge_afo_mcp__submit_recovery_plan", {}).allow
    assert a.decide("afo_planner", "use_skill", {"skill_name": "afo-recovery-planner"}).allow
    for tool, tin in (("mcp__forge_build_mcp__compile", {}), ("write_file", {"path": "x", "content": "y"}),
                      ("shell", {"command": "ls"}), ("use_skill", {"skill_name": "swe3-author"})):
        assert not a.decide("afo_planner", tool, tin).allow, tool
    swe = Authorizer(Binding("WO-x", str(ws), {"swe3_author": {"role": "swe3-author", "phase": "SWE.3"}}))
    assert not swe.decide("swe3_author", "mcp__forge_afo_mcp__read_failure_bundle", {}).allow  # base view unchanged


def test_invoke_never_blocks_pending_then_reply_or_nothing(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    cp = _case(tmp_path)
    launched = []
    states = {"R1": "running"}
    inv = lambda now=None: planner_run.invoke(cp, launcher=lambda p: launched.append(p) or "R1",  # noqa: E731
                                              state=lambda r: states[r], now=now)
    assert inv() == planner_run.PENDING and launched == [cp]
    assert inv() == planner_run.PENDING and len(launched) == 1                     # never launched twice
    planner_run.store_reply(cp.parent, '{"status":"PASS"}')
    assert inv() == '{"status":"PASS"}'
    (cp.parent / "reply.txt").unlink()
    states["R1"] = "failed"
    assert inv() is None                                                           # ended without a reply
    states["R1"] = "running"
    assert inv(now=planner_run.time.time() + planner_run.TIMEOUT_SECONDS + 1) is None   # bounded wait
    with pytest.raises(SystemExit):
        planner_run.store_reply(tmp_path, "x")                                      # only inside afo/cases


def test_recovery_waits_for_the_planner_then_executes_its_validated_plan(order, tmp_path, monkeypatch):  # noqa: F811
    s, o, b, epoch, eff = order
    eng = {**eff.policy["engineering"], "enable_recovery_planner": True,
           "allowed_model_profiles": []}                  # no untried model: no deterministic rule applies
    eff = dataclasses.replace(eff, policy={**eff.policy, "engineering": eng})
    replies = {"n": 0}

    def invoke(cp):
        replies["n"] += 1
        if replies["n"] == 1:
            return planner.PENDING
        plan = recovery._base(json.loads(cp.read_text())["bundle"], "REWORK_LOCAL", "SWE.3", "PLANNER_TECHNIQUE",
                              artifact_scope=["software/hal"], material_difference_ref="technique:split-unit-designs")
        (cp.parent / "proposed-plan.json").write_text(json.dumps(plan))
        return json.dumps({"status": "PASS", "artifacts": [], "issues": [], "next_action": "next",
                           "recovery_plan_ref": f"afo-plan:{plan['plan_id']}"})
    p = planner.make(invoke)
    d = recovery.decide(s, o, b, ws=tmp_path / "none", eff=eff, auth_models=None, planner=p)
    assert d["status"] == "PENDING" and recovery.plans(s, o["order_id"]) == []     # nothing recorded yet
    s.transition(o["order_id"], "WAITING_RECOVERY", "planner run")
    s.attempt_transition(b["attempt_id"], "FAILED")
    seen = []
    out = recovery.poll_waiting(s, lambda order, att: seen.append(att["attempt_id"]) or {"action": "x"})
    assert seen == [b["attempt_id"]] and out[0]["action"] == "x"
    d = recovery.decide(s, s.order(o["order_id"]), b, ws=tmp_path / "none", eff=eff, auth_models=None, planner=p)
    assert (d["status"], d["source"], d["plan"]["strategy"]) == ("VALIDATED", "PLANNER", "REWORK_LOCAL")
    r = recovery.execute(s, s.order(o["order_id"]), d, epoch=epoch, eff=eff, previous_wo="WO-AFO-x-a1")
    assert r["action"] == "new_attempt"
    assert recovery.poll_waiting(s, lambda *a: pytest.fail("a prepared attempt is not polled")) == []
