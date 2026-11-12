"""Real SQL/control/authentication boundaries; no host audit or model qualification."""

import hashlib
import json
import os
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from forge_factory.afo import cli
from forge_factory.afo import dashboard_api as D
from forge_factory.afo import operations as O
from forge_factory.afo.durable import Refused, digest
from forge_factory.afo.queue import Store


@pytest.fixture
def control(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("FORGE_EVENTS_DIR", str(tmp_path / "events"))
    monkeypatch.delenv("FORGE_DURABLE_AUTONOMY", raising=False)
    private = tmp_path / "operations"
    private.mkdir(mode=0o700)
    intent = O.Intent(private / "intent.json")
    monkeypatch.setenv("FORGE_OPERATIONS_INTENT", str(intent.path))
    intent.set("RUNNING", actor="fixture-owner", reason="initialize", initialize=True)
    return Store(), intent


def receipts(store):
    return [e["payload"] for e in store.events("afo-control") if e["type"] == "afo.operator_control"]


@pytest.mark.parametrize("action,mode,values", [
    ("pause", "PAUSED", {"paused": "1", "draining": "0"}),
    ("drain", "DRAINING", {"paused": "1", "draining": "1"}),
    ("resume", "RUNNING", {"paused": "0", "draining": "0"}),
    ("shutdown", "STOPPED", {"paused": "1", "draining": "1"}),
])
def test_control_receipt_binds_intent_and_exact_applied_action_rows(control, action, mode, values):
    store, intent = control
    rec = O.synchronize(store, action, "PRIVATE-ACTOR", "PRIVATE-REASON")
    assert rec["mode"] == mode and store.control() == values
    context = rec["control_context"]
    assert intent.read()["control_context"] == context
    assert context["control_id"] == "control-" + digest({k: v for k, v in context.items() if k != "control_id"})
    assert context["pid"] == os.getpid() and context["process"]["uid"] == os.getuid()
    assert context["process"]["start_ticks"].isdigit() and context["uid_map"]
    assert context["intent_epoch"] == rec["epoch"]
    receipt = receipts(store)[0]
    assert receipt["context"] == context
    assert "PRIVATE-ACTOR" not in json.dumps(receipt) and "PRIVATE-REASON" not in json.dumps(receipt)
    with store.tx() as c:
        actual = [dict(r) for r in c.execute("SELECT seq AS action_seq,action FROM afo_operator_actions ORDER BY seq")]
    assert receipt["applied"] == actual


def test_legacy_single_key_controls_keep_existing_rows_without_fabricated_authentication(control):
    store, _ = control
    store.set_control("legacy-custom-control", "value", "owner", "legacy caller")
    assert store.control() == {"legacy-custom-control": "value"} and receipts(store) == []


def test_multi_key_sql_failure_rolls_back_all_effects_while_stop_intent_stays_durable(control):
    store, intent = control
    store.set_controls({"paused": "0", "draining": "0"}, "owner", "initial")
    with store.tx() as c:
        c.execute("CREATE TRIGGER reject_second_control BEFORE UPDATE ON afo_control "
                  "WHEN NEW.key='draining' BEGIN SELECT RAISE(ABORT,'INJECTED_DB_FAILURE'); END")
    with pytest.raises(sqlite3.IntegrityError, match="INJECTED_DB_FAILURE"):
        O.synchronize(store, "shutdown", "owner", "stop despite store failure")
    assert intent.read()["mode"] == "STOPPED" and store.control() == {"paused": "0", "draining": "0"}
    assert receipts(store) == []
    with store.tx() as c:
        assert c.execute("SELECT COUNT(*) FROM afo_operator_actions").fetchone()[0] == 2
    # A failed provenance/database update must not revoke the durable stop fence.
    with pytest.raises(Refused, match="OPERATIONS_ADMISSION_FENCED"):
        O.fenced_call(intent.read()["epoch"], lambda: pytest.fail("must not start"))


def test_newer_stop_cannot_be_overwritten_by_old_resume_database_effects(control, monkeypatch):
    store, intent = control
    entered, release, stop_requested = threading.Event(), threading.Event(), threading.Event()
    stop_applied = threading.Event()
    original = store.set_controls

    def delayed(values, *args, **kwargs):
        if values["paused"] == "0":
            entered.set()
            assert release.wait(3)
        else:
            stop_applied.set()
        return original(values, *args, **kwargs)

    monkeypatch.setattr(store, "set_controls", delayed)

    def stop():
        stop_requested.set()
        return O.synchronize(store, "shutdown", "owner", "new stop")

    with ThreadPoolExecutor(max_workers=2) as executor:
        resume = executor.submit(O.synchronize, store, "resume", "owner", "older resume")
        assert entered.wait(3)
        stopped = executor.submit(stop)
        try:
            assert stop_requested.wait(3)
            assert not stop_applied.wait(0.1), "stop escaped intent serialization"
        finally:
            release.set()
        older, newer = resume.result(timeout=3), stopped.result(timeout=3)
    assert older["epoch"] < newer["epoch"]
    assert intent.read()["mode"] == "STOPPED" and store.control() == {"paused": "1", "draining": "1"}
    assert [r["context"]["intent_epoch"] for r in receipts(store)] == [older["epoch"], newer["epoch"]]


def test_missing_process_evidence_does_not_prevent_operator_stop(control, monkeypatch):
    from forge_factory.lrtx import provider_process

    store, intent = control
    monkeypatch.setattr(provider_process, "identity", lambda _: (_ for _ in ()).throw(Refused("FIXTURE_UNREADABLE_PROC")))
    rec = O.synchronize(store, "shutdown", "owner", "stop")
    assert rec["mode"] == intent.read()["mode"] == "STOPPED" and store.control()["paused"] == "1"
    assert rec["control_context"]["process"] is None


def test_arbitrary_authentication_metadata_never_exports_tokens_or_extra_fields(control):
    store, _ = control
    rec = O.synchronize(store, "pause", "owner", "reason", authentication={
        "method": "DASHBOARD_OPERATOR_BEARER", "credential_sha256": "a" * 64,
        "source_sha256": "bad-hash", "authorization": "Bearer PRIVATE-TOKEN", "extra": "PRIVATE-BODY",
    })
    auth = rec["control_context"]["authentication"]
    assert auth == {"method": "DASHBOARD_OPERATOR_BEARER", "credential_sha256": "a" * 64, "uid": os.getuid()}
    assert "PRIVATE-TOKEN" not in json.dumps(receipts(store)) and "PRIVATE-BODY" not in json.dumps(receipts(store))


def test_cli_records_existing_os_owner_authentication(control, capsys):
    store, _ = control
    assert cli.main(["pause", "--reason", "fixture pause"]) == 0
    assert json.loads(capsys.readouterr().out)["control"]["paused"] == "1"
    assert receipts(store)[0]["context"]["authentication"]["method"] == "OS_STATE_DIRECTORY_OWNER"


def test_existing_http_operator_decision_and_token_fingerprint_bind_one_receipt(control):
    from forge_factory.dashboard.app import create_app
    from forge_factory.events.store import EventStore

    store, _ = control
    client = TestClient(create_app(EventStore(), collect=False))
    token = D.issue_operator_token()
    body = {"reason": "fixture", "authentication": {"method": "FORGED", "credential_sha256": "a" * 64}}
    assert client.post("/api/v1/afo/operator/pause", json=body).status_code == 401
    assert receipts(store) == []
    result = client.post("/api/v1/afo/operator/pause", json=body, headers={"Authorization": "Bearer " + token})
    assert result.status_code == 200 and result.json()["control"]["paused"] == "1"
    auth = receipts(store)[0]["context"]["authentication"]
    assert auth["method"] == "DASHBOARD_OPERATOR_BEARER" and auth["credential_sha256"] == hashlib.sha256(token.encode()).hexdigest()
    assert token not in json.dumps(receipts(store)) and "FORGED" not in json.dumps(receipts(store))
    assert not D.operator_ok("Bearer wrong") and D.operator_ok("Bearer " + token)


def test_delayed_maintenance_resume_cannot_replace_newer_operator_stop(control):
    store, intent = control
    paused = O.synchronize(store, 'pause', 'maintenance', 'bounded deployment')
    stopped = O.synchronize(store, 'shutdown', 'owner', 'newer stop')
    before = receipts(store)
    with pytest.raises(Refused, match='OPERATIONS_INTENT_SUPERSEDED'):
        O.synchronize(store, 'resume', 'maintenance', 'finish deployment', expected_epoch=paused['epoch'])
    assert intent.read() == stopped
    assert store.control() == {'paused': '1', 'draining': '1'}
    assert receipts(store) == before


def test_current_maintenance_epoch_can_resume_through_existing_control_path(control):
    store, intent = control
    paused = O.synchronize(store, 'pause', 'maintenance', 'bounded deployment')
    resumed = O.synchronize(store, 'resume', 'maintenance', 'finish deployment', expected_epoch=paused['epoch'])
    assert resumed['epoch'] == paused['epoch'] + 1
    assert resumed['mode'] == 'RUNNING' and intent.read() == resumed
    assert store.control() == {'paused': '0', 'draining': '0'}
