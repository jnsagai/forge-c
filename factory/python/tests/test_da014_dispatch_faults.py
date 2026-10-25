"""Signed dispatch/liveness interventions through the actual durable poll; typed native client, zero model calls."""
# ruff: noqa: F811

import hashlib
import json
import time
from types import SimpleNamespace

import pytest
from forge_factory.afo import authz
from forge_factory.afo import local_agent as L
from forge_factory.afo import protocol_faults as F
from forge_factory.afo import qualification as Q
from forge_factory.afo import qualification_state as R
from forge_factory.afo.durable import Refused
from forge_factory.afo.execution_lifecycle import Executions
from test_afo_local_autonomy import local  # noqa: F401
from test_afo_m4_recovery import order  # noqa: F401
from test_da014_protocol_faults import bind
from test_da014_qualification_reservations import signed  # noqa: F401


class Native:
    """Typed Fabro control-plane fixture: records every call, never runs inference."""

    def __init__(self, job, status="RUNNING", cancel_code=202, listed=()):
        self.job, self.status, self.cancel_code, self.listed = job, status, cancel_code, list(listed)
        self.cancels, self.launches = [], []

    def get_run(self, rid):
        return {"lifecycle": {"status": {"kind": self.status}}}

    def usage(self, rid):
        return {"stages": []}

    def cancel(self, rid):
        self.cancels.append(rid)
        return self.cancel_code

    def list_runs(self, **_):
        labels = {"afo_agent": self.job["job_id"], "afo_nonce": self.job["nonce"]}
        return [{"id": rid, "labels": labels} for rid in self.listed]

    def launch(self, job):
        self.launches.append(job["job_id"])
        return "RUN-" + job["job_id"][-6:]


def poll(p, job, native):
    return L.poll(p.store, p.store.order(job["order_id"]), job, p.eff, client=native, launch_fn=native.launch)


def evidence(p, job, kind):
    with p.store.tx() as c:
        row = c.execute("SELECT record FROM afo_execution_evidence WHERE job_id=? AND kind=?", (job["job_id"], kind)).fetchone()
    return json.loads(row[0]) if row else None


def row(p, name, job):
    return Q.protocol_observation(p.store, p.manifest, name + ":0", job)


def test_revocation_before_dispatch_is_job_scoped_and_never_contacts_native(signed):
    p = signed
    job, _, _ = bind(p, "revoked-before-dispatch", dispatch=False)
    native = Native(job)
    job = poll(p, job, native)
    assert job["state"] == "REVOKED" and native.launches == [] and native.cancels == []
    live = Executions(p.store).get(job["job_id"])
    assert (live["authorization_state"], live["execution_liveness"], live["resource_lease"]) == ("REVOKED", "NOT_STARTED", "RELEASED")
    assert live["admission_state"] == "RESERVED" and live["native_run_ids"] == []
    # The common grant and mission still authorize every other trial.
    grant = authz.find(p.eff.mode, p.eff.sha256, ref="AUTH-QUAL", action="recover_workorder", request={"model": job["model"]})
    assert grant.allow and p.ledger.snapshot("qualification-only")["limits"]["deadline"] > time.time()
    observed = row(p, "revoked-before-dispatch", job)
    assert observed["observed"] == "REVOKED" and F.observation_matches(p.manifest, observed)
    assert not F.observation_matches(p.manifest, {**observed, "fault_observation": None})
    assert poll(p, job, native)["state"] == "REVOKED" and native.launches == []


def test_expired_mission_uses_the_real_dispatch_deadline_check_without_editing_the_mission(signed):
    p = signed
    before = p.ledger.snapshot("qualification-only")
    job, _, _ = bind(p, "expired-mission", dispatch=False)
    native = Native(job)
    job = poll(p, job, native)
    assert (job["state"], job["error"]) == ("FAILED", "MISSION_DEADLINE_EXHAUSTED") and native.launches == []
    live = Executions(p.store).get(job["job_id"])
    assert (live["authorization_state"], live["execution_liveness"], live["resource_lease"]) == ("EXPIRED", "NOT_STARTED", "RELEASED")
    after = p.ledger.snapshot("qualification-only")
    assert after["limits"] == before["limits"] and after["limits"]["deadline"] > time.time()
    observed = row(p, "expired-mission", job)
    assert observed["observed"] == "EXHAUSTED" and F.observation_matches(p.manifest, observed)
    fact = evidence(p, job, "PROTOCOL_DISPATCH_FAULT")
    assert fact["effect"] == "JOB_SCOPED_MISSION_DEADLINE_ELAPSED"


def test_ordinary_dispatch_after_the_real_mission_deadline_is_refused(signed):
    p = signed
    job, _, _ = bind(p, "administrative-forgery", dispatch=False)
    with p.store.tx() as c:
        rec = json.loads(c.execute("SELECT record FROM afo_missions WHERE mission_id='qualification-only'").fetchone()[0])
        rec["limits"]["deadline"] = time.time() - 1
        c.execute("UPDATE afo_missions SET record=? WHERE mission_id='qualification-only'", (json.dumps(rec),))
    native = Native(job)
    job = poll(p, job, native)
    assert (job["state"], job["error"]) == ("FAILED", "MISSION_DEADLINE_EXHAUSTED") and native.launches == []
    assert evidence(p, job, "PROTOCOL_DISPATCH_FAULT") is None


def test_lost_launch_ack_is_adopted_once_by_nonce_listing(signed):
    p = signed
    job, _, _ = bind(p, "lost-launch-ack", dispatch=False)
    native = Native(job)
    job = poll(p, job, native)
    rid = "RUN-" + job["job_id"][-6:]
    assert job["state"] == "LAUNCHING" and job["run_id"] is None and native.launches == [job["job_id"]]
    live = Executions(p.store).get(job["job_id"])
    assert live["admission_state"] == "DISPATCH_INTENT_RECORDED" and live["resource_lease"] == "HELD"
    assert evidence(p, job, "PROTOCOL_DISPATCH_FAULT")["dropped_ack_sha256"] == hashlib.sha256(rid.encode()).hexdigest()
    # No listing yet: uncertainty is retained and nothing is relaunched.
    job = poll(p, job, native)
    assert native.launches == [job["job_id"]] and Executions(p.store).get(job["job_id"])["execution_liveness"] == "UNKNOWN"
    assert not F.observation_matches(p.manifest, row(p, "lost-launch-ack", job))
    native.listed = [rid]
    job = poll(p, job, native)
    assert job["run_id"] == rid and native.launches == [job["job_id"]]
    assert evidence(p, job, "NONCE_LIST_ADOPTION")["run_ids"] == [rid]
    assert F.observation_matches(p.manifest, row(p, "lost-launch-ack", job))


def test_cancel_ack_with_a_live_request_retains_inference_capacity(signed):
    p = signed
    job, _, _ = bind(p, "cancel-ack-still-live", dispatch=False)
    native = Native(job)
    job = poll(p, job, native)
    assert job["state"] == "RUNNING" and native.cancels == []
    # No live provider request: the declared intervention waits for a real exposure.
    job = poll(p, job, native)
    assert evidence(p, job, "PROTOCOL_DISPATCH_FAULT_INTENT") is None and native.cancels == []
    p.ledger.reserve_request(
        "qualification-only", job["job_id"], "typed-live-request", body_sha256="a" * 64, input_tokens=10, output_cap=30,
        authorize=lambda: True,
    )
    p.ledger.start_request("typed-live-request", authorize=lambda: True)
    job = poll(p, job, native)
    assert job["state"] == "FAILED" and native.cancels == [job["run_id"]]
    live = Executions(p.store).get(job["job_id"])
    assert live["cancellation_state"] == "ACKNOWLEDGED" and live["resource_lease"] == "HELD"
    assert live["task_outcome"] == "BLOCKED"
    fact = evidence(p, job, "PROTOCOL_DISPATCH_FAULT")
    assert fact["live_request_ids"] == ["typed-live-request"] and fact["cancel_acknowledged"] is True
    observed = row(p, "cancel-ack-still-live", job)
    assert observed["observed"] == "BLOCKED_LIVE_HELD" and F.observation_matches(p.manifest, observed)
    # Acknowledgment never released capacity; only native and provider quiescence do.
    native.status = "CANCELLED"
    p.ledger.reconcile_request("typed-live-request", input_tokens=10, output_tokens=5, quiescent=True, evidence_ref="typed")
    job = poll(p, job, native)
    assert Executions(p.store).get(job["job_id"])["resource_lease"] == "RELEASED"


def test_unacknowledged_cancel_is_not_counted_as_the_declared_exposure(signed):
    p = signed
    job, _, _ = bind(p, "cancel-ack-still-live", dispatch=False)
    native = Native(job, cancel_code=500)
    job = poll(p, job, native)
    p.ledger.reserve_request(
        "qualification-only", job["job_id"], "typed-live-request", body_sha256="a" * 64, input_tokens=10, output_cap=30,
        authorize=lambda: True,
    )
    p.ledger.start_request("typed-live-request", authorize=lambda: True)
    job = poll(p, job, native)
    fact = evidence(p, job, "PROTOCOL_DISPATCH_FAULT")
    assert fact["cancel_acknowledged"] is False and fact["last_cancel_error"] == "HTTP_500"
    assert not F.observation_matches(p.manifest, row(p, "cancel-ack-still-live", job))


def test_dispatch_fault_requires_the_current_signed_runbook(signed):
    p = signed
    job, _, _ = bind(p, "revoked-before-dispatch", dispatch=False)
    p.grant["signed_runbook_ref"] = "qualification-014:" + "0" * 64
    p.grant_path.write_text(json.dumps(p.grant))
    authz.sign(p.grant_path, p.key)
    native = Native(job)
    Executions(p.store).reserve(job["job_id"], job["mission_id"], job["nonce"])
    with pytest.raises(Refused, match="QUALIFICATION_FAULT_NOT_SIGNED"):
        F.apply_dispatch(p.store, job, p.eff)
    assert Executions(p.store).get(job["job_id"])["authorization_state"] == "VALID" and native.launches == []


def test_live_snapshot_is_recorded_but_wrapper_capacity_is_not_released(signed):
    p = signed
    job, _, _ = bind(p, "cancel-ack-still-live", dispatch=False)
    native = Native(job)
    job = poll(p, job, native)
    p.ledger.reserve_request(
        "qualification-only", job["job_id"], "typed-live-request", body_sha256="a" * 64, input_tokens=10, output_cap=30,
        authorize=lambda: True,
    )
    p.ledger.start_request("typed-live-request", authorize=lambda: True)
    job = poll(p, job, native)
    result = R.record_completed(p.store, job)
    assert result["row"]["observed"] == "BLOCKED_LIVE_HELD"
    assert p.store.order(job["order_id"])["state"] == "RUNNING"
    assert SimpleNamespace(**result).product_acceptance == "NOT_REQUESTED"
