"""The 2026-11-06 allowance is separate, finite and leaves the spent mission untouched."""

import inspect
import json
from types import SimpleNamespace

import pytest
from forge_factory.afo import owner_supervised_development as D
from forge_factory.afo.durable import Refused, digest
from forge_factory.afo.line_orders import Placer
from forge_factory.afo.mission_ledger import MissionLedger
from forge_factory.afo.owner_development_allowance import DIRECTIVE, open_allowance
from forge_factory.afo.queue import Store
from forge_factory.lrtx import stack
from test_owner_supervised_development import (
    CLOSED_ALLOWANCE_RECORD,
    PRIOR_RECORD,
    RAISED_ALLOWANCE_RECORD,
    seed_spent_original,
)


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    for key in (D.FILE, D.SHA, "FORGE_AGENT_ROLE", "FORGE_WORKSPACE", "FORGE_POLICY_BINDING"):
        monkeypatch.delenv(key, raising=False)
    value = Store(tmp_path / "state/supervisor/line-queue.sqlite3")
    seed_spent_original(value)
    return value


def row(store, mission):
    with store.tx() as c:
        return c.execute("SELECT record FROM afo_missions WHERE mission_id=?", (mission,)).fetchone()[0]


def close_first(store, state="BLOCKED"):
    with store.tx() as c:
        for i, order in enumerate(D.SPENT_ORDERS):
            c.execute(
                "INSERT INTO afo_work_orders (order_id,tenant_scope,request_id,manifest_sha256,input_manifest_ref,envelope,"
                "priority,state,version,created_utc,created_epoch,policy_sha256,fencing_epoch) VALUES "
                "(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                ("afo-spent-" + str(i), "line-local", order, "a" * 64, "ref", "{}", 40, state, 1,
                 "2026-11-06T00:00:00Z", 1.0, "b" * 64, 0),
            )


def test_opens_a_separate_finite_mission_without_touching_the_spent_one(store):
    close_first(store)
    before = MissionLedger(store).snapshot(D.PRIOR_MISSION)
    closed = MissionLedger(store).snapshot(D.CLOSED_ALLOWANCE)
    opened = open_allowance(store, directive=DIRECTIVE)
    assert opened["mission_id"] == D.MISSION != D.PRIOR_MISSION
    assert opened["lineage"] == D.LINEAGE
    assert opened["authorization_ref"] == D.ALLOWANCE_REF
    assert opened["limits"] == {**D.CAPS, "deadline": D.DEADLINE}
    assert MissionLedger(store).snapshot(D.PRIOR_MISSION) == before
    assert MissionLedger(store).snapshot(D.CLOSED_ALLOWANCE) == closed
    assert row(store, D.PRIOR_MISSION) == PRIOR_RECORD
    assert row(store, D.CLOSED_ALLOWANCE) == CLOSED_ALLOWANCE_RECORD
    assert row(store, D.RAISED_ALLOWANCE) == RAISED_ALLOWANCE_RECORD


def test_cannot_open_before_the_spent_orders_are_finished(store):
    close_first(store, state="WAITING_RECOVERY")
    with pytest.raises(Refused, match="SPENT_ORDER_NOT_CLOSED"):
        open_allowance(store, directive=DIRECTIVE)


def test_allowance_is_finite_and_covers_every_reservation():
    assert D.ATTEMPTS == 32 and len(D.ORDERS) == 32
    assert D.CAPS["max_attempts"] == 32 and D.CAPS["max_jobs"] == 64
    assert D.CAPS["max_requests"] == 32 * 256 and D.CAPS["max_tools"] == 32 * 512
    assert D.CAPS["max_tokens"] == 32 * 8388608 + 64 * 1048576
    assert D.DEADLINE == 1795057626.0


def test_real_run_fits_and_policy_changed_only_two_budgets():
    from pathlib import Path

    import yaml

    raised = yaml.safe_load((Path(__file__).parent / "fixtures/owner-supervised-development/afo-policy.proposed.yaml").read_text())
    assert digest(raised) == D.RUNTIME_POLICY_SHA
    assert raised["budgets"]["max_inference_requests_per_order"] == 256
    assert raised["budgets"]["max_model_tokens_per_order"] == 8388608
    original = yaml.safe_load(yaml.safe_dump(raised))
    original["budgets"].update(max_model_tokens_per_order=1048576, max_inference_requests_per_order=32)
    assert digest(original) == D.ORIGINAL_RUNTIME_POLICY_SHA


def test_replay_returns_the_same_row_and_never_refills(store):
    close_first(store)
    first = open_allowance(store, directive=DIRECTIVE)
    ledger = MissionLedger(store)
    ledger.execution(D.MISSION, "spent", "PRODUCT", reserved_tokens=1)
    assert open_allowance(store, directive=DIRECTIVE) == first
    assert ledger.snapshot(D.MISSION)["attempts"] == 1


def test_changed_limits_cannot_reregister(store):
    close_first(store)
    open_allowance(store, directive=DIRECTIVE)
    with pytest.raises(Refused, match="MISSION_ALLOWANCE_RESET_FORBIDDEN"):
        MissionLedger(store).register(
            D.MISSION, D.LINEAGE, {**D.CAPS, "max_attempts": 3, "deadline": D.DEADLINE}, D.ALLOWANCE_REF,
            authorize=lambda *_: True,
        )


@pytest.mark.parametrize("directive", ["", "go", DIRECTIVE + " "])
def test_requires_the_exact_directive(store, directive):
    close_first(store)
    with pytest.raises(Refused, match="EXTERNAL_OPERATOR_REQUIRED"):
        open_allowance(store, directive=directive)
    with pytest.raises(Refused, match="MISSION_NOT_REGISTERED"):
        MissionLedger(store).snapshot(D.MISSION)


@pytest.mark.parametrize("key", ["FORGE_AGENT_ROLE", "FORGE_WORKSPACE", "FORGE_POLICY_BINDING", D.FILE, D.SHA])
def test_agent_or_issued_context_cannot_open(store, monkeypatch, key):
    close_first(store)
    monkeypatch.setenv(key, "x")
    with pytest.raises(Refused, match="EXTERNAL_OPERATOR_REQUIRED"):
        open_allowance(store, directive=DIRECTIVE)


def test_changed_prior_row_refuses(store):
    with store.tx() as c:
        c.execute(
            "UPDATE afo_missions SET record=? WHERE mission_id=?",
            (PRIOR_RECORD.replace('"max_attempts":4', '"max_attempts":5'), D.PRIOR_MISSION),
        )
    with pytest.raises(Refused, match="PRIOR_MISSION_NOT_CONSERVED"):
        open_allowance(store, directive=DIRECTIVE)


def test_changed_prior_spend_refuses(store):
    with store.tx() as c:
        c.execute("DELETE FROM afo_mission_executions WHERE identity='afo-product-spent-0'")
    with pytest.raises(Refused, match="PRIOR_MISSION_NOT_CONSERVED"):
        open_allowance(store, directive=DIRECTIVE)


def test_settled_prior_usage_refuses(store):
    with store.tx() as c:
        c.execute("DELETE FROM afo_mission_executions")
        for i in range(4):
            record = dict(charge=1048576, identity=str(i), kind="PRODUCT", reported_tokens=1048576, created_at="x")
            c.execute(
                "INSERT INTO afo_mission_executions VALUES (?,?,?,?)", (str(i), D.PRIOR_MISSION, "PRODUCT", json.dumps(record))
            )
    with pytest.raises(Refused, match="PRIOR_MISSION_NOT_CONSERVED"):
        open_allowance(store, directive=DIRECTIVE)


def test_pinned_prior_digest_matches_the_real_row():
    assert digest(json.loads(PRIOR_RECORD)) == D.PRIOR_RECORD_SHA256


def test_changed_closed_allowance_refuses(store):
    with store.tx() as c:
        c.execute(
            "UPDATE afo_missions SET record=? WHERE mission_id=?",
            (CLOSED_ALLOWANCE_RECORD.replace('"max_attempts":2', '"max_attempts":3'), D.CLOSED_ALLOWANCE),
        )
    with pytest.raises(Refused, match="PRIOR_MISSION_NOT_CONSERVED"):
        open_allowance(store, directive=DIRECTIVE)


def test_expired_allowance_cannot_open(store, monkeypatch):
    monkeypatch.setattr("forge_factory.afo.owner_development_allowance.time.time", lambda: D.DEADLINE)
    with pytest.raises(Refused, match="ALLOWANCE_EXPIRED"):
        open_allowance(store, directive=DIRECTIVE)


def test_orders_continue_the_series_after_the_spent_ones():
    assert D.ORDERS[0].endswith("L90G") and D.ORDERS[19].endswith("L90Z") and D.ORDERS[20].endswith("L90AA")
    assert not set(D.ORDERS) & set(D.SPENT_ORDERS)


@pytest.mark.parametrize(
    ("request_id", "state", "expected"),
    [
        (D.SPENT_ORDERS[1], "BLOCKED", True),
        (D.ORDERS[0], "BLOCKED", True),
        (D.ORDERS[0], "WAITING_RECOVERY", False),
        (D.SERIES + "D", "BLOCKED", False),
    ],
)
def test_only_finished_orders_of_this_series_retry_from_the_seed(monkeypatch, request_id, state, expected):
    monkeypatch.setenv(D.FILE, "x")
    assert D.retries_from_seed(dict(request_id=request_id, state=state)) is expected


def test_outside_the_lane_nothing_retries_from_the_seed(monkeypatch):
    monkeypatch.delenv(D.FILE, raising=False)
    monkeypatch.delenv(D.SHA, raising=False)
    assert not D.retries_from_seed(dict(request_id=D.ORDERS[0], state="BLOCKED"))


def test_tool_hook_carries_the_queue_scope(tmp_path, monkeypatch):
    from forge_factory.fabro import runconfig

    monkeypatch.setenv("FORGE_AFO_QUEUE_SCOPE", "line-local")
    monkeypatch.setenv("FORGE_OPERATIONS_INTENT", "/private/intent.json")
    servers = dict(forge_tests_mcp=dict(module="forge_factory.mcp.servers.tests"))
    text = runconfig.render_run_toml("g.fabro", "goal", tmp_path / "b.json", servers)
    hooks = [line for line in text.splitlines() if line.startswith("script = ")]
    assert hooks and all("FORGE_AFO_QUEUE_SCOPE=line-local" in line for line in hooks)
    assert all("FORGE_OPERATIONS_INTENT=/private/intent.json" in line for line in hooks)
    assert 'FORGE_OPERATIONS_INTENT = "/private/intent.json"' in text
    assert 'FORGE_AFO_QUEUE_SCOPE = "line-local"' in text


def test_recovery_planner_uses_the_lane_grant_not_a_signed_file():
    from forge_factory.afo import line_recovery_runtime

    source = inspect.getsource(line_recovery_runtime.authorize)
    assert "development.DevelopmentGrant(policy)" in source and "eff.mode == development.MODE" in source


@pytest.mark.parametrize(("served", "ok"), [("model-a", True), ("model-b", False)])
def test_managed_serve_is_a_no_op_only_for_the_served_model(tmp_path, monkeypatch, served, ok):
    from forge_factory.afo import line_stack_lifecycle

    monkeypatch.setattr(line_stack_lifecycle, "selected", lambda: False)
    monkeypatch.setattr(stack, "managed_serving", lambda: True)
    monkeypatch.setattr(stack, "_serve_model", lambda *a, **k: pytest.fail("NO_SWAP_ALLOWED"))
    (tmp_path / "run").mkdir()
    (tmp_path / "run/services.json").write_text(json.dumps(dict(processes=dict(llama_server=dict(model=served)))))
    if ok:
        assert stack.serve(dict(root=tmp_path), "model-a")["model_swap"] == "NOT_NEEDED"
    else:
        with pytest.raises(RuntimeError, match="MODEL_SWAP_REFUSED_MANAGED_SERVING"):
            stack.serve(dict(root=tmp_path), "model-a")


def test_api_bridge_waits_past_a_cold_integrity_check():
    assert stack.API_READY_SECONDS >= 120


def test_recovery_journal_accepts_the_real_launch_guard(tmp_path):
    from types import SimpleNamespace as NS

    from forge_factory.afo import line_launcher as LL
    from forge_factory.afo.line_recovery_runtime import Journal

    log = tmp_path / "steps.jsonl"
    cfg = NS(guard=True, stack_root=tmp_path, uid=1000)
    procs = NS()
    real = LL.survey
    LL.survey = lambda *_: ([], None)
    try:
        LL._guard(Journal(log), NS(guard=lambda own: "OK"), procs, cfg, lambda _: None)
    finally:
        LL.survey = real
    row = json.loads(log.read_text())
    assert (row["step"], row["outcome"], row["result"]) == ("guard", "OK", "OK")


def test_tool_charge_reaches_the_line_queue_under_the_hook_scope(store, tmp_path, monkeypatch):
    from forge_factory.afo.tool_accounting import charge

    close_first(store)
    open_allowance(store, directive=DIRECTIVE)
    MissionLedger(store).execution(D.MISSION, "job", "PRODUCT", reserved_tokens=1)
    binding = tmp_path / ".forge-run/durable-binding.json"
    binding.parent.mkdir()
    binding.write_text(json.dumps(dict(mission_id=D.MISSION, job_id="job")))
    monkeypatch.delenv("FORGE_AFO_QUEUE_SCOPE", raising=False)
    with pytest.raises(Refused, match="MISSION_NOT_REGISTERED"):
        charge(tmp_path, "event-before")
    monkeypatch.setenv("FORGE_AFO_QUEUE_SCOPE", "line-local")
    assert charge(tmp_path, "event-after")["job_id"] == "job"
    assert MissionLedger(store).snapshot(D.MISSION)["tools"] == 1


def execute_with(monkeypatch, failure):
    def refuse(order):
        raise failure

    monkeypatch.setattr(D, "validate_order", refuse)
    plan = SimpleNamespace(order=dict(wo="WO-X", kind="RETRY"), action="PLACE")
    return Placer._execute(SimpleNamespace(owner_supervised_development=True), plan, None, None, None, 0.0, execute=True)


def test_order_outside_the_envelope_is_refused_without_ending_the_guardian(monkeypatch):
    result = execute_with(monkeypatch, Refused(D.ENVELOPE_REFUSED))
    assert result["outcome"] == "REFUSED" and result["wo"] == "WO-X" and result["detail"] == D.ENVELOPE_REFUSED


def test_authority_failures_still_stop_the_guardian(monkeypatch):
    with pytest.raises(Refused, match="GUARDIAN_ATTESTATION_CHANGED"):
        execute_with(monkeypatch, Refused("OWNER_DEVELOPMENT_GUARDIAN_ATTESTATION_CHANGED"))


@pytest.mark.parametrize("text", [None, "stale"])
def test_stale_or_missing_fabro_settings_refuse_start(tmp_path, monkeypatch, text):
    monkeypatch.setattr(stack, "fabro_config", lambda s: "current")
    (tmp_path / "fabro").mkdir()
    if text:
        (tmp_path / "fabro/settings.toml").write_text(text)
    with pytest.raises(ValueError, match="FABRO_SETTINGS_STALE"):
        stack.require_current_fabro_settings(dict(root=tmp_path))


def test_current_fabro_settings_pass(tmp_path, monkeypatch):
    monkeypatch.setattr(stack, "fabro_config", lambda s: "current")
    (tmp_path / "fabro").mkdir()
    (tmp_path / "fabro/settings.toml").write_text("current")
    stack.require_current_fabro_settings(dict(root=tmp_path))


def test_every_profile_model_gets_an_output_limit():
    settings = stack.settings(D.PROFILE)
    text = stack.fabro_config(settings)
    for model in settings["profile"]["models"]["allowed"]:
        section = text.split(f'[llm.providers.ollama.models."{model}"]', 1)[1].split("[", 1)[0]
        assert "max_output_tokens" in text.split(f'[llm.providers.ollama.models."{model}"]', 1)[1][:400], section
