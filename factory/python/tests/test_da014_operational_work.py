"""Synthetic native/audit timelines test tooling, never live product acceptance."""

import json
import sqlite3
from pathlib import Path

import pytest
from forge_factory.afo import fault_observer as O
from forge_factory.afo import operational_work as W
from forge_factory.afo import qualification as Q
from forge_factory.afo import qualification_capture as C
from forge_factory.afo import queue
from forge_factory.afo.durable import Refused, digest, immutable_json
from forge_factory.common import sha256_file, state_dir
from test_da014_fault_observer import (
    sample,
    setup,  # noqa: F401
)
from test_da014_qualification import identity


def put(path, value):
    immutable_json(path, value)
    return {"path": str(path), "sha256": sha256_file(path)}


@pytest.fixture
def work(setup):  # noqa: F811
    p = setup
    p.binding = {
        "order_id": "order-fixture",
        "attempt_id": "attempt-fixture",
        "job_id": "job-fixture",
        "mission_id": "fixture-mission",
    }
    p.trial = "real-work:01"
    plan = put(
        p.tmp / "work-plan.json",
        {
            **p.raw,
            "work_verifier_sha256": sha256_file(Path(W.__file__)),
            "product_observer_sha256": sha256_file(Path(C.__file__)),
            "queue_reader_sha256": sha256_file(Path(queue.__file__)),
        },
    )
    p.ref = plan
    p.manifest = Q.freeze(
        "operation-24", p.tmp / "work-manifest.json", identity=identity(), inputs=[plan["path"]], jobs={p.trial: p.binding}
    )
    p.observation = {
        "trial_id": p.trial,
        "manifest_sha256": digest(p.manifest),
        "job_id": p.binding["job_id"],
        "attempt_id": p.binding["attempt_id"],
        "native_run_id": "native-fixture",
        "order_state": "READY_FOR_OFFLINE_REVIEW",
        "execution": {
            **p.binding,
            "launch_nonce": "nonce-fixture",
            "native_run_ids": ["native-fixture"],
            "execution_liveness": "QUIESCENT",
            "resource_lease": "RELEASED",
        },
        "package_sha256": "a" * 64,
        "package_verdict": {"verdict": "READY_FOR_OFFLINE_REVIEW", "archive_sha256": "b" * 64},
        "gates": {f"SWE.{i}": "PASS" for i in range(1, 7)},
        "request_ids": ["request-fixture"],
    }
    p.samples = []
    for n, wall in enumerate((100, 130)):
        ref = sample(p, "work-" + str(n), wall, "1000")
        row = O.bound_json(ref)
        ledger = row["ledger"]
        ledger["orders"] = [
            {"order_id": p.binding["order_id"], "state": p.observation["order_state"], "authorization_id": "fixture-auth"}
        ]
        ledger["attempts"] = [{**p.binding, "attempt_seq": 1, "fabro_run_id": "native-fixture", "state": "SUCCEEDED"}]
        ledger["afo_execution_liveness"] = [p.observation["execution"]]
        ledger["afo_request_ledger"] = [
            {
                "job_id": p.binding["job_id"],
                "mission_id": p.binding["mission_id"],
                "state": "QUIESCENT",
                "request_id": "request-fixture",
                "charge": 100,
            }
        ]
        p.samples.append(put(p.tmp / ("work-native-" + str(n) + ".json"), row))
    return p


def audited(p, name="audit", *, facts=None, observation=None, producer="REFERENCE_HARNESS"):
    observation = observation or p.observation
    oracle = put(
        p.tmp / (name + "-oracle.json"), {"scope": "SYNTHETIC_UNIT_TEST_NOT_REAL_PRODUCT", "gate_results": observation["gates"]}
    )
    audit = {
        "schema": "forge-c/independent-qualification-audit/1",
        "producer": producer,
        "manifest_sha256": digest(p.manifest),
        "source_revision": p.manifest["source_revision"],
        "trial_id": p.trial,
        "observation_sha256": digest(observation),
        "oracle_refs": [oracle],
        "observations": facts if facts is not None else {"false_ready": False, "required_evidence_complete": True},
    }
    ref = put(state_dir() / "lrtx/qualification-audits" / (name + ".json"), audit)
    row = C.audited_product_row(p.manifest, observation, ref)
    return put(p.tmp / (name + "-row.json"), row), ref, oracle


def evaluate(p, ref):
    return W.evaluate(p.manifest, p.ref, ref, p.samples)


def test_native_ready_requires_existing_bound_independent_audit_and_quiescence(work):
    p = work
    row_ref, _, _ = audited(p)
    result = evaluate(p, row_ref)
    assert result["status"] == "VERIFIED" and result["product_success"] is True
    assert result["native_quiescence_captured"] is True and result["false_ready"] is False
    assert W.verify(p.manifest, result) == result
    assert O.invariants([O.bound_json(r) for r in p.samples])["false_ready"] is not False
    assert W.ready_verdict([O.bound_json(r) for r in p.samples], [result]) is False


def test_fault_observer_recomputes_the_ready_oracle_instead_of_assuming_it(work):
    p = work
    row, _, _ = audited(p)
    verified = evaluate(p, row)
    work_ref = put(p.tmp / "work-verdict.json", verified)
    receipt = put(
        p.tmp / "crash-receipt.json",
        {
            "schema": "forge-c/operational-fault/1",
            "manifest_sha256": digest(p.manifest),
            "fault": "crash",
            "unit": "forge-conductor.service",
            "host": "fixture-host",
            "at": 110,
            "returncode": 0,
            "command": ["systemctl", "--user", "kill", "--kill-who=main", "--signal=KILL", "forge-conductor.service"],
        },
    )
    without = O.evaluate(p.manifest, p.ref, receipt, p.samples, None)
    assert without["false_ready"] is None
    result = O.evaluate(p.manifest, p.ref, receipt, p.samples, None, work_refs=[work_ref])
    assert result["false_ready"] is False
    assert result["unexpected_interventions"] is None and result["independently_restored"] is False
    assert O.verify(p.manifest, result) == result


@pytest.mark.parametrize(
    "field,value",
    [("native_all_six_gates", False), ("false_ready", True), ("sealed_ready", False), ("required_evidence_complete", False)],
)
def test_product_success_flags_cannot_be_edited_after_audit(work, field, value):
    p = work
    ref, _, _ = audited(p)
    row = O.bound_json(ref)
    row[field] = value
    ref = put(p.tmp / "edited-product-row.json", row)
    with pytest.raises(Refused, match="PRODUCT_AUDIT_VERDICT_CHANGED"):
        evaluate(p, ref)


@pytest.mark.parametrize(
    "change",
    ["held", "running", "request-running", "request-absent", "mission", "native", "nonce", "older-attempt", "authorization"],
)
def test_terminal_task_outcome_does_not_substitute_for_captured_native_identity_and_liveness(work, change):
    p = work
    ref, _, _ = audited(p)
    samples = []
    for i, source in enumerate(p.samples):
        s = O.bound_json(source)
        ex = s["ledger"]["afo_execution_liveness"][0]
        if change == "held":
            ex["resource_lease"] = "HELD"
        if change == "running":
            ex["execution_liveness"] = "RUNNING"
        if change == "request-running":
            s["ledger"]["afo_request_ledger"][0]["state"] = "STREAMING"
        if change == "request-absent":
            s["ledger"]["afo_request_ledger"] = []
        if change == "mission":
            ex["mission_id"] = "other-mission"
        if change == "native":
            ex["native_run_ids"] = ["other-native"]
        if change == "nonce":
            ex["launch_nonce"] = "other-nonce"
        if change == "older-attempt":
            s["ledger"]["attempts"].append({**s["ledger"]["attempts"][0], "attempt_id": "newer-attempt", "attempt_seq": 2})
        if change == "authorization":
            s["ledger"]["orders"][0]["authorization_id"] = None
        samples.append(put(p.tmp / ("changed-" + str(i) + ".json"), s))
    p.samples = samples
    result = evaluate(p, ref)
    assert result["status"] == "INCOMPLETE" and result["native_quiescence_captured"] is False
    assert result["independently_verified"] is False


def test_missing_audit_is_unknown_and_same_model_producer_is_refused(work):
    p = work
    row = C.audited_product_row(p.manifest, p.observation)
    result = evaluate(p, put(p.tmp / "no-audit-row.json", row))
    assert result["false_ready"] is None and result["status"] == "INCOMPLETE"
    with pytest.raises(Refused, match="INDEPENDENT_QUALIFICATION_AUDIT_MISMATCH"):
        audited(p, "model", producer="QWEN")


def test_oracle_tampering_is_rejected_on_replay(work):
    p = work
    ref, _, oracle = audited(p)
    Path(oracle["path"]).chmod(0o600)
    Path(oracle["path"]).write_text("{}")
    with pytest.raises(Refused, match="INDEPENDENT_ORACLE_CHANGED"):
        evaluate(p, ref)


@pytest.mark.parametrize("gates", [{}, {"SWE.1": "PASS"}, {**dict.fromkeys(W.PHASES, "PASS"), "SWE.7": "PASS"}])
def test_ready_with_missing_or_extra_phase_gates_is_false_ready(work, gates):
    p = work
    observation = {**p.observation, "gates": gates}
    ref, _, _ = audited(p, observation=observation)
    result = evaluate(p, ref)
    assert result["false_ready"] is True and result["status"] == "FAIL"


def test_independent_counterexample_is_preserved(work):
    p = work
    ref, _, _ = audited(p, facts={"false_ready": True, "required_evidence_complete": True})
    result = evaluate(p, ref)
    assert not result["independently_verified"] and result["false_ready"] is True
    assert W.ready_verdict([O.bound_json(r) for r in p.samples], [result]) is True


def test_blocked_real_work_is_evidence_without_product_success(work):
    p = work
    p.observation.update(order_state="BLOCKED", package_verdict={"verdict": "BLOCKED"}, gates=dict.fromkeys(W.PHASES, "BLOCKED"))
    sources = []
    for i, ref in enumerate(p.samples):
        row = O.bound_json(ref)
        row["ledger"]["orders"][0]["state"] = "BLOCKED"
        row["ledger"]["attempts"][0]["state"] = "FAILED"
        sources.append(put(p.tmp / ("blocked-" + str(i) + ".json"), row))
    p.samples = sources
    ref, _, _ = audited(p, facts={"false_ready": False, "required_evidence_complete": False, "native_outcome_verified": True})
    result = evaluate(p, ref)
    assert result["independently_verified"] and not result["product_success"]


def test_incomplete_product_without_an_independent_outcome_verdict_cannot_count(work):
    p = work
    ref, _, _ = audited(p, facts={"false_ready": False, "required_evidence_complete": False})
    result = evaluate(p, ref)
    assert result["status"] == "INCOMPLETE" and not result["independently_verified"]


def test_work_record_verdict_and_observation_identity_cannot_be_rebound(work):
    p = work
    ref, _, _ = audited(p)
    result = evaluate(p, ref)
    with pytest.raises(Refused, match="OPERATIONAL_WORK_VERDICT_CHANGED"):
        W.verify(p.manifest, {**result, "product_success": False})
    row = O.bound_json(ref)
    row["native_run_id"] = "other-native"
    with pytest.raises(Refused, match="PRODUCT_OBSERVATION_CHANGED"):
        evaluate(p, put(p.tmp / "rebound-row.json", row))


def test_a_verified_older_attempt_cannot_clear_a_later_ready_claim(work):
    p = work
    ref, _, _ = audited(p)
    verified = evaluate(p, ref)
    samples = [O.bound_json(r) for r in p.samples]
    samples[-1]["ledger"]["attempts"].append(
        {**samples[-1]["ledger"]["attempts"][0], "attempt_id": "later-attempt", "attempt_seq": 2}
    )
    assert W.ready_verdict(samples, [verified]) is None


def install_capture_fixture(p):
    with p.store.tx() as c:
        c.execute(
            "INSERT INTO afo_work_orders(order_id,tenant_scope,request_id,manifest_sha256,input_manifest_ref,envelope,priority,state,created_utc,created_epoch) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (p.binding["order_id"], "test", "capture", "a" * 64, "fixture", "{}", "NORMAL", "BLOCKED", "fixture", 100),
        )
        c.execute(
            "INSERT INTO afo_attempts(attempt_id,order_id,seq,state,record,created_utc) VALUES (?,?,?,?,?,?)",
            (
                p.binding["attempt_id"],
                p.binding["order_id"],
                1,
                "FAILED",
                json.dumps({"workspace_ref": "workorder:capture"}),
                "fixture",
            ),
        )
        c.execute(
            "INSERT INTO afo_execution_liveness VALUES (?,?,?,?)",
            ("execution-fixture", p.binding["job_id"], p.binding["mission_id"], json.dumps(p.observation["execution"])),
        )
    ws = state_dir() / "workorders/capture/workspace"
    ws.mkdir(parents=True)
    return ws


def test_product_capture_uses_read_only_store_without_a_native_or_service_effect(work, monkeypatch):
    p = work
    install_capture_fixture(p)
    before = sha256_file(p.db)

    def observe(store, manifest, trial, binding):
        assert isinstance(store, queue.ReadSnapshot)
        assert trial == p.trial and binding == p.binding
        assert store.order(binding["order_id"])["state"] == "BLOCKED"
        with store.tx() as c, pytest.raises(sqlite3.OperationalError, match="readonly"):
            c.execute("DELETE FROM afo_attempts")
        return C.audited_product_row(manifest, p.observation)

    monkeypatch.setattr(C, "product_row", observe)
    output = p.tmp / "captured-product-row.json"
    result = W.capture_product(p.manifest, p.ref, p.trial, output)
    assert O.read_json(output) == result
    assert result["qualification_status"] == "INCOMPLETE_INDEPENDENT_AUDIT"
    assert sha256_file(p.db) == before


def test_model_free_native_outcome_requires_bound_zero_requests_not_missing_capture(work):
    p = work
    p.observation["request_ids"] = []
    ref, _, _ = audited(p)
    samples = []
    for i, source in enumerate(p.samples):
        row = O.bound_json(source)
        row["ledger"]["afo_request_ledger"] = []
        samples.append(put(p.tmp / ("zero-request-" + str(i) + ".json"), row))
    p.samples = samples
    result = evaluate(p, ref)
    assert result["status"] == "VERIFIED" and result["model_request_count"] == 0


def test_product_capture_cannot_publish_after_its_read_deadline(work, monkeypatch):
    p = work
    install_capture_fixture(p)

    def late(store, *args):
        store.deadline = 0
        return C.audited_product_row(p.manifest, p.observation)

    monkeypatch.setattr(C, "product_row", late)
    with pytest.raises(queue.QueueError, match="NOT_CURRENT"):
        W.capture_product(p.manifest, p.ref, p.trial, p.tmp / "late-result.json")
    assert not (p.tmp / "late-result.json").exists()


@pytest.mark.parametrize("change", ["held", "running", "fifo", "symlink", "outside-archive"])
def test_product_capture_refuses_live_execution_and_unbounded_or_out_of_scope_inputs(work, change):
    import os

    p = work
    ws = install_capture_fixture(p)
    if change in ("held", "running"):
        execution = {
            **p.observation["execution"],
            **({"resource_lease": "HELD"} if change == "held" else {"execution_liveness": "RUNNING"}),
        }
        with p.store.tx() as c:
            c.execute("UPDATE afo_execution_liveness SET record=?", (json.dumps(execution),))
    if change == "fifo":
        os.mkfifo(ws / "fifo")
    if change == "symlink":
        (ws / "escape").symlink_to(p.tmp)
    if change == "outside-archive":
        put(ws / ".forge-run/package.json", {"archive": str(p.tmp / "outside.zip")})
    with pytest.raises(Refused, match="NOT_QUIESCENT|BOUND_EXCEEDED|OUTSIDE_DATA_ROOT"):
        W.capture_product(p.manifest, p.ref, p.trial, p.tmp / "refused-capture.json")
    assert not (p.tmp / "refused-capture.json").exists()
