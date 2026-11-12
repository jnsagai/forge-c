"""Control receipt source/SQL/privacy verification, not independent host proof."""
# ruff: noqa: F811

import copy
import hashlib
import json
from pathlib import Path

import pytest
from forge_factory.afo import cli
from forge_factory.afo import control_observation as C
from forge_factory.afo import dashboard_api as D
from forge_factory.afo import fault_observer as F
from forge_factory.afo import operations as O
from forge_factory.afo import qualification as Q
from forge_factory.afo.durable import Refused, digest, immutable_json
from forge_factory.common import sha256_file
from test_da014_fault_observer import setup  # noqa: F401
from test_da014_qualification import identity


def config():
    return {"reader_sha256": sha256_file(Path(C.__file__)), "intent_source_sha256": sha256_file(Path(O.__file__)),
            "authentication_sources": {"OS_STATE_DIRECTORY_OWNER": sha256_file(Path(cli.__file__)),
                                       "DASHBOARD_OPERATOR_BEARER": sha256_file(Path(D.__file__))}}


@pytest.fixture
def observed(setup, monkeypatch):
    p = setup
    private = p.tmp / "operations"
    private.mkdir(mode=0o700)
    intent = O.Intent(private / "intent.json")
    monkeypatch.setenv("FORGE_OPERATIONS_INTENT", str(intent.path))
    intent.set("RUNNING", actor="PRIVATE-OWNER", reason="PRIVATE-REASON", initialize=True)
    rec = O.synchronize(p.store, "pause", "PRIVATE-OWNER", "PRIVATE-REASON")
    raw = {**p.raw, "intent": str(intent.path), "control_sources": config()}
    path = p.tmp / "control-plan.json"
    immutable_json(path, raw)
    ref = {"path": str(path), "sha256": sha256_file(path)}
    manifest = Q.freeze("operation-24", p.tmp / "control-manifest.json", identity=identity(), inputs=[path])
    return p, intent, rec, raw, ref, manifest


def rehash(ctx):
    ctx["control_id"] = "control-" + digest({k: v for k, v in ctx.items() if k != "control_id"})
    return ctx


def event_row(store):
    with store.tx() as connection:
        row = dict(connection.execute("SELECT seq,event_id,occurred_utc,record FROM afo_lifecycle_events "
                                      "WHERE type='afo.operator_control'").fetchone())
        actions = {r["seq"]: r["action"] for r in connection.execute("SELECT seq,action FROM afo_operator_actions")}
    return row, actions


def test_frozen_capture_preserves_exact_safe_sources_actual_rows_and_private_fields(observed):
    p, intent, rec, raw, ref, manifest = observed
    before = sha256_file(p.db)
    captured = F.capture(manifest, ref, p.tmp / "captured.json")
    assert captured["complete"] and captured["ledger"]["control_source"]["events"]
    assert sha256_file(p.db) == before
    event = captured["ledger"]["control_source"]["events"][0]
    assert event["status"] == "APPLICATION_RECEIPT_CAPTURED"
    assert hashlib.sha256(event["record"].encode()).hexdigest() == event["record_sha256"]
    assert event["facts"]["producer_source_matches"] is True
    assert captured["intent_control_source"]["context"] == rec["control_context"]
    C.verify_sources(captured["ledger"], {**captured["intent"], "control_source": captured["intent_control_source"]}, config())
    assert "PRIVATE-OWNER" not in json.dumps(captured) and "PRIVATE-REASON" not in json.dumps(captured)
    assert "NOT_HOST_INTERVENTION" in captured["ledger"]["control_source"]["scope"]
    assert F.invariants([captured])["unexpected_interventions"] is None


@pytest.mark.parametrize("field", ["reader_sha256", "intent_source_sha256", "authentication_sources"])
def test_invalid_or_changed_reader_binding_is_refused(field):
    cfg = config()
    cfg[field] = "not-a-source-hash"
    with pytest.raises(Refused, match="CONFIGURATION"):
        C.configuration(cfg)


def test_historical_producer_is_retained_as_unmatched_not_reclassified_as_authenticated(observed):
    p, _, _, _, _, _ = observed
    cfg = config()
    cfg["intent_source_sha256"] = "0" * 64
    snap = F.ledger(p.db, 100, control_sources=cfg)
    row = snap["control_source"]["events"][0]
    assert row["status"] == "APPLICATION_RECEIPT_CAPTURED" and row["facts"]["producer_source_matches"] is False


@pytest.mark.parametrize("mutation", ["extra-context", "extra-auth", "extra-process", "wrong-source-type", "mode-type",
                                       "uid-map-overlap", "uid-map-zero", "uid-map-overflow", "uid-mismatch", "hash"])
def test_untrusted_contexts_never_export_arbitrary_data_or_become_valid(observed, mutation):
    p, _, _, _, _, _ = observed
    row, actions = event_row(p.store)
    record = json.loads(row["record"])
    ctx = record["payload"]["context"]
    if mutation == "extra-context":
        ctx["private"] = "DO-NOT-EXPORT"
    elif mutation == "extra-auth":
        ctx["authentication"]["token"] = "DO-NOT-EXPORT"
    elif mutation == "extra-process":
        ctx["process"]["cmdline"] = "DO-NOT-EXPORT"
    elif mutation == "wrong-source-type":
        ctx["producer_source_sha256"] = {"private": "DO-NOT-EXPORT"}
    elif mutation == "mode-type":
        ctx["mode"] = ["DO-NOT-EXPORT"]
    elif mutation == "uid-map-overlap":
        ctx["uid_map"] = [[0, 1000, 2], [1, 2000, 2]]
    elif mutation == "uid-map-zero":
        ctx["uid_map"] = [[0, 1000, 0]]
    elif mutation == "uid-map-overflow":
        ctx["uid_map"] = [[0, 2**32 - 1, 2]]
    elif mutation == "uid-mismatch":
        ctx["authentication"]["uid"] += 1
    elif mutation == "hash":
        ctx["control_id"] = "control-" + "0" * 64
    if mutation != "hash":
        rehash(ctx)
    record["payload_sha256"] = digest(record["payload"])
    row["record"] = json.dumps(record)
    result = C.event(row, actions, config())
    assert result["status"] == "UNKNOWN" and "record" not in result
    assert "DO-NOT-EXPORT" not in json.dumps(result)


@pytest.mark.parametrize("mutation", ["missing-action", "changed-action", "duplicate-seq", "payload", "wrapper", "producer"])
def test_actual_sql_and_event_carrier_bindings_are_required(observed, mutation):
    p, _, _, _, _, _ = observed
    row, actions = event_row(p.store)
    record = json.loads(row["record"])
    if mutation == "missing-action":
        actions.pop(next(iter(actions)))
    elif mutation == "changed-action":
        actions[next(iter(actions))] = "paused=0"
    elif mutation == "duplicate-seq":
        record["payload"]["applied"][1]["action_seq"] = record["payload"]["applied"][0]["action_seq"]
        record["payload_sha256"] = digest(record["payload"])
    elif mutation == "payload":
        record["payload_sha256"] = "0" * 64
    elif mutation == "wrapper":
        row["event_id"] = "afo-ev-" + "0" * 24
    elif mutation == "producer":
        record["producer_id"] = "PRIVATE-PRODUCER"
    row["record"] = json.dumps(record)
    result = C.event(row, actions, config())
    assert result["status"] == "UNKNOWN" and "PRIVATE-PRODUCER" not in json.dumps(result)


def test_uid_map_is_relative_to_parent_namespace_not_implicitly_host_authority(observed):
    _, _, rec, _, _, _ = observed
    ctx = copy.deepcopy(rec["control_context"])
    ctx["process"]["uid"] = ctx["authentication"]["uid"] = 0
    ctx["uid_map"] = [[0, 1000, 1]]
    facts = C.context(rehash(ctx), config())
    assert facts["parent_namespace_uid"] == 1000 and "host_uid" not in facts and "authenticated" not in facts


def test_optional_context_and_unknown_process_are_not_invented(observed):
    p, _, rec, _, _, _ = observed
    ctx = copy.deepcopy(rec["control_context"])
    ctx.update(process=None, user_namespace=None, uid_map=None)
    facts = C.context(rehash(ctx), config())
    assert not facts["process_identity_known"] and facts["parent_namespace_uid"] is None
    assert "control_source" not in F.ledger(p.db, 100)


def test_legacy_or_custom_actions_are_sanitized_without_erasing_their_identity(observed):
    p, _, _, _, _, _ = observed
    p.store.set_control("custom", "PRIVATE-VALUE", "owner", "fixture")
    snapshot = F.ledger(p.db, 100, control_sources=config())
    assert snapshot["actions"][-1]["action"] is None and snapshot["actions"][-1]["action_sha256"]
    assert "PRIVATE-VALUE" not in json.dumps(snapshot)


def test_private_invalid_control_value_and_intent_boolean_are_never_exported(observed):
    p, intent, _, _, _, _ = observed
    p.store.set_control("paused", "PRIVATE-VALUE", "owner", "fixture")
    with pytest.raises(Refused, match="CONTROL_VALUE"):
        F.ledger(p.db, 100, control_sources=config())
    with intent.lock():
        record = intent.read()
        record["effective_stop"] = {"private": "PRIVATE-VALUE"}
        intent._write(record)
    with pytest.raises(Refused, match="INTENT_UNKNOWN"):
        F._intent(intent.path, control_sources=config())


def test_replay_recomputes_flags_and_rejects_rebinding_to_unrelated_intent(observed):
    p, intent, _, _, _, _ = observed
    ledger, recorded = F.ledger(p.db, 100, control_sources=config()), F._intent(intent.path, control_sources=config())
    ledger["control_source"]["events"][0]["facts"]["producer_source_matches"] = False
    with pytest.raises(Refused, match="REPLAY_MISMATCH"):
        C.verify_sources(ledger, recorded, config())
    ledger = F.ledger(p.db, 100, control_sources=config())
    recorded["epoch"] += 1
    with pytest.raises(Refused, match="REPLAY_MISMATCH"):
        C.verify_sources(ledger, recorded, config())


def test_load_samples_calls_source_replay_instead_of_accepting_supplied_flags(observed):
    p, _, _, _, ref, manifest = observed
    one = F.capture(manifest, ref, p.tmp / "one.json")
    two = F.capture(manifest, ref, p.tmp / "two.json")
    two["ledger"]["control_source"]["events"][0]["facts"]["producer_source_matches"] = False
    forged = p.tmp / "forged.json"
    immutable_json(forged, two)
    references = [{"path": str(p.tmp / "one.json"), "sha256": sha256_file(p.tmp / "one.json")},
                  {"path": str(forged), "sha256": sha256_file(forged)}]
    assert one["complete"]
    with pytest.raises(Refused, match="REPLAY_MISMATCH"):
        F.load_samples(manifest, ref, references)


def test_recovery_accounting_changes_source_bytes_without_changing_operator_intent(observed):
    p, intent, _, _, ref, manifest = observed
    before = F.capture(manifest, ref, p.tmp / "before-counters.json")
    with intent.lock():
        record = intent.read()
        record["recoveries"] += 1
        record["pending_start"] = True
        intent._write(record)
    after = F.capture(manifest, ref, p.tmp / "after-counters.json")
    assert before["intent"] == after["intent"]
    assert before["intent_control_source"]["record_sha256"] != after["intent_control_source"]["record_sha256"]


def test_expanded_observation_cannot_publish_an_oversized_snapshot(observed, monkeypatch):
    p, _, _, _, ref, manifest = observed
    monkeypatch.setattr(F, "MAX_BYTES", 4096)
    monkeypatch.setattr(F, "ledger", lambda *a, **k: {"unexpected": "x" * 5000})
    out = p.tmp / "bounded-output.json"
    result = F.capture(manifest, ref, out)
    assert len(out.read_bytes()) <= 4096 and not result["complete"] and result["ledger"] is None
    assert result["errors"]["ledger"] == "OBSERVER_OUTPUT_BYTE_BOUND_EXCEEDED"


def test_actual_bearer_decision_source_is_bound_but_never_promoted_to_host_authority(observed):
    p, _, _, _, _, _ = observed
    token = D.issue_operator_token()
    auth = D.operator_authentication("Bearer " + token)
    O.synchronize(p.store, "resume", "PRIVATE-OWNER", "PRIVATE-REASON", authentication=auth)
    snapshot = F.ledger(p.db, 100, control_sources=config())
    row = snapshot["control_source"]["events"][-1]
    assert row["facts"]["authentication_source_matches"] is True
    assert token not in json.dumps(snapshot) and "authenticated" not in row["facts"]


def test_legacy_intent_without_context_stays_explicitly_unknown(setup):
    projected = F._intent(setup.raw["intent"], control_sources=config())
    assert projected["control_source"]["status"] == "UNKNOWN"
    assert projected["control_source"]["reason"] == "LEGACY_CONTROL_CONTEXT_ABSENT"


def test_action_and_event_reads_share_a_snapshot_during_real_concurrent_commit(observed, monkeypatch):
    p, _, _, _, _, _ = observed
    original = F.sqlite3.connect
    committed, errors = [], []

    def connect(*args, **kwargs):
        connection = original(*args, **kwargs)

        def trace(sql):
            if sql.startswith("SELECT seq,action FROM afo_operator_actions") and not committed:
                committed.append(True)
                try:
                    O.synchronize(p.store, "resume", "owner", "concurrent source write")
                except Exception as exc:
                    errors.append(type(exc).__name__)

        connection.set_trace_callback(trace)
        return connection

    monkeypatch.setattr(F.sqlite3, "connect", connect)
    before = F.ledger(p.db, 100, control_sources=config())
    after = F.ledger(p.db, 100, control_sources=config())
    assert committed and not errors
    assert len(before["actions"]) == 2 and len(before["control_source"]["events"]) == 1
    assert len(after["actions"]) == 4 and len(after["control_source"]["events"]) == 2
    assert all(r["status"] == "APPLICATION_RECEIPT_CAPTURED" for r in after["control_source"]["events"])


@pytest.mark.parametrize("mutation", ["duplicate-action", "duplicate-event", "unknown-extra", "intent-extra"])
def test_replay_refuses_duplicated_or_unreviewed_source_shapes(observed, mutation):
    p, intent, _, _, _, _ = observed
    ledger, desired = F.ledger(p.db, 100, control_sources=config()), F._intent(intent.path, control_sources=config())
    if mutation == "duplicate-action":
        ledger["actions"].append(ledger["actions"][0])
    elif mutation == "duplicate-event":
        event = copy.deepcopy(ledger["control_source"]["events"][0])
        event["seq"] += 1
        ledger["control_source"]["events"].append(event)
    elif mutation == "unknown-extra":
        ledger["control_source"]["events"][0] = {"seq": 1, "record_sha256": "a" * 64, "status": "UNKNOWN",
                                                  "reason": "FIXTURE", "extra": "DO-NOT-EXPORT"}
    else:
        desired["control_source"]["extra"] = "DO-NOT-EXPORT"
    with pytest.raises(Refused):
        C.verify_sources(ledger, desired, config())
