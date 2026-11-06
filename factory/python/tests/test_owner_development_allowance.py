"""The 2026-11-06 allowance is separate, finite and leaves the spent mission untouched."""

import json

import pytest
from forge_factory.afo import owner_supervised_development as D
from forge_factory.afo.durable import Refused, digest
from forge_factory.afo.mission_ledger import MissionLedger
from forge_factory.afo.owner_development_allowance import DIRECTIVE, open_allowance
from forge_factory.afo.queue import Store
from test_owner_supervised_development import PRIOR_RECORD, seed_spent_original


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


def test_opens_a_separate_finite_mission_without_touching_the_spent_one(store):
    before = MissionLedger(store).snapshot(D.PRIOR_MISSION)
    opened = open_allowance(store, directive=DIRECTIVE)
    assert opened["mission_id"] == D.MISSION != D.PRIOR_MISSION
    assert opened["lineage"] == D.LINEAGE
    assert opened["authorization_ref"] == D.ALLOWANCE_REF
    assert opened["limits"] == {**D.CAPS, "deadline": D.DEADLINE}
    assert MissionLedger(store).snapshot(D.PRIOR_MISSION) == before
    assert row(store, D.PRIOR_MISSION) == PRIOR_RECORD


def test_allowance_is_within_the_original_caps_and_deadline():
    original = json.loads(PRIOR_RECORD)["limits"]
    assert all(D.CAPS[k] <= original[k] for k in D.CAPS)
    assert D.CAPS["max_attempts"] == 2 and D.CAPS["max_jobs"] == 2
    assert D.DEADLINE == 1795057626.0


def test_replay_returns_the_same_row_and_never_refills(store):
    first = open_allowance(store, directive=DIRECTIVE)
    ledger = MissionLedger(store)
    ledger.execution(D.MISSION, "spent", "PRODUCT", reserved_tokens=1)
    assert open_allowance(store, directive=DIRECTIVE) == first
    assert ledger.snapshot(D.MISSION)["attempts"] == 1


def test_changed_limits_cannot_reregister(store):
    open_allowance(store, directive=DIRECTIVE)
    with pytest.raises(Refused, match="MISSION_ALLOWANCE_RESET_FORBIDDEN"):
        MissionLedger(store).register(
            D.MISSION, D.LINEAGE, {**D.CAPS, "max_attempts": 3, "deadline": D.DEADLINE}, D.ALLOWANCE_REF,
            authorize=lambda *_: True,
        )


@pytest.mark.parametrize("directive", ["", "go", DIRECTIVE + " "])
def test_requires_the_exact_directive(store, directive):
    with pytest.raises(Refused, match="EXTERNAL_OPERATOR_REQUIRED"):
        open_allowance(store, directive=directive)
    with pytest.raises(Refused, match="MISSION_NOT_REGISTERED"):
        MissionLedger(store).snapshot(D.MISSION)


@pytest.mark.parametrize("key", ["FORGE_AGENT_ROLE", "FORGE_WORKSPACE", "FORGE_POLICY_BINDING", D.FILE, D.SHA])
def test_agent_or_issued_context_cannot_open(store, monkeypatch, key):
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


def test_expired_allowance_cannot_open(store, monkeypatch):
    monkeypatch.setattr("forge_factory.afo.owner_development_allowance.time.time", lambda: D.DEADLINE)
    with pytest.raises(Refused, match="ALLOWANCE_EXPIRED"):
        open_allowance(store, directive=DIRECTIVE)


def test_orders_are_only_the_next_two_in_the_series():
    assert D.ORDERS == ("WO-F014-SWE6-AFOQUAL-20261104-L90E", "WO-F014-SWE6-AFOQUAL-20261104-L90F")


