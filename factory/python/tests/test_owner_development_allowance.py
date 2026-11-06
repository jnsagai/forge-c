"""The 2026-11-06 allowance is separate, finite and leaves the spent mission untouched."""

import json
from types import SimpleNamespace

import pytest
from forge_factory.afo import owner_supervised_development as D
from forge_factory.afo.durable import Refused, digest
from forge_factory.afo.line_orders import Placer
from forge_factory.afo.mission_ledger import MissionLedger
from forge_factory.afo.owner_development_allowance import CLOSE_DIRECTIVE, DIRECTIVE, close_for_source_fix, open_allowance
from forge_factory.afo.queue import Store
from forge_factory.lrtx import stack
from test_owner_supervised_development import CLOSED_ALLOWANCE_RECORD, PRIOR_RECORD, seed_spent_original


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


def close_first(store):
    oid = waiting_order(store)
    close_for_source_fix(store, directive=CLOSE_DIRECTIVE)
    return oid


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


def test_cannot_open_before_the_spent_order_is_closed(store):
    waiting_order(store)
    with pytest.raises(Refused, match="SPENT_ORDER_NOT_CLOSED"):
        open_allowance(store, directive=DIRECTIVE)


def test_allowance_is_the_owner_decision_and_no_more():
    assert D.CAPS == dict(
        max_attempts=1, max_jobs=2, max_requests=256, max_tokens=16777216, max_tools=512, max_corrections=4
    )
    assert D.DEADLINE == 1795057626.0


def test_real_run_fits_and_policy_changed_only_two_budgets():
    from pathlib import Path

    import yaml

    raised = yaml.safe_load((Path(__file__).parent / "fixtures/owner-supervised-development/afo-policy.proposed.yaml").read_text())
    assert digest(raised) == D.RUNTIME_POLICY_SHA
    assert D.CAPS["max_requests"] >= 218 and raised["budgets"]["max_inference_requests_per_order"] == D.CAPS["max_requests"]
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


def test_only_the_last_order_is_in_scope():
    assert D.ORDERS == ("WO-F014-SWE6-AFOQUAL-20261104-L90F",)




def waiting_order(store, *, state="WAITING_RECOVERY", attempt="FAILED", run="native-run"):
    oid = "afo-spent-order"
    with store.tx() as c:
        c.execute(
            "INSERT INTO afo_work_orders (order_id,tenant_scope,request_id,manifest_sha256,input_manifest_ref,envelope,"
            "priority,state,version,created_utc,created_epoch,policy_sha256,fencing_epoch) VALUES "
            "(?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (oid, "line-local", D.SPENT_ORDER, "a" * 64, "ref", "{}", 40, state, 1, "2026-11-06T00:00:00Z", 1.0, "b" * 64, 0),
        )
        c.execute(
            "INSERT INTO afo_attempts (attempt_id,order_id,seq,state,record,created_utc) VALUES (?,?,1,?,?,?)",
            (oid + "-a1", oid, attempt, json.dumps(dict(state=attempt, fabro_run_id=run)), "2026-11-06T00:00:00Z"),
        )
    MissionLedger(store).link(D.CLOSED_ALLOWANCE, oid)
    return oid


def test_closes_only_the_spent_first_order_and_keeps_its_charge(store):
    oid = waiting_order(store)
    before = MissionLedger(store).snapshot(D.CLOSED_ALLOWANCE)
    closed = close_for_source_fix(store, directive=CLOSE_DIRECTIVE)
    assert (closed["order_id"], closed["state"], closed["terminal_reason"]) == (oid, "BLOCKED", D.SOURCE_FIX_CLOSED)
    assert MissionLedger(store).snapshot(D.CLOSED_ALLOWANCE) == before
    assert close_for_source_fix(store, directive=CLOSE_DIRECTIVE)["version"] == closed["version"]


@pytest.mark.parametrize("change", [dict(state="RUNNING"), dict(attempt="RUNNING"), dict(run=None)])
def test_refuses_any_other_order_state(store, change):
    oid = waiting_order(store, **change)
    with pytest.raises(Refused, match="SPENT_ORDER_NOT_CLOSABLE"):
        close_for_source_fix(store, directive=CLOSE_DIRECTIVE)
    assert store.order(oid)["state"] == change.get("state", "WAITING_RECOVERY")


@pytest.mark.parametrize("key", ["FORGE_AGENT_ROLE", D.FILE])
def test_agent_or_issued_context_cannot_close(store, monkeypatch, key):
    waiting_order(store)
    monkeypatch.setenv(key, "x")
    with pytest.raises(Refused, match="EXTERNAL_OPERATOR_REQUIRED"):
        close_for_source_fix(store, directive=CLOSE_DIRECTIVE)


def test_close_requires_the_exact_directive(store):
    waiting_order(store)
    with pytest.raises(Refused, match="EXTERNAL_OPERATOR_REQUIRED"):
        close_for_source_fix(store, directive=DIRECTIVE)


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
