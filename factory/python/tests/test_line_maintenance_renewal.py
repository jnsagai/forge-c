"""Renewed signed-control binding preserves original authority, limits and job wall.

Crypto/source-origin leaves are fixtures here; the independent frozen RPR174
uses real TEST signatures for the same raw-versus-effective authorization path.
"""
import copy
import json
import time
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from forge_factory import workorder
from forge_factory.afo import authz
from forge_factory.afo import line_maintenance_coordinator as C
from forge_factory.afo import line_recovery_control as CONTROL
from forge_factory.afo import mission_deadline as D
from forge_factory.afo.durable import Refused, digest
from forge_factory.afo.mission_ledger import MissionLedger
from forge_factory.afo.operations import Intent
from forge_factory.afo.queue import Store
from forge_factory.common import sha256_file


@pytest.mark.parametrize("fault", [None, "stale", "extra_cap", "lineage", "authority", "job_deadline"])
def test_review_uses_effective_mission_but_keeps_base_authority_and_job_wall(tmp_path, monkeypatch, fault):
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    store = Store(tmp_path / "state/queue.sqlite3")
    inputs = tmp_path / "inputs"
    (inputs / "afo-manifests").mkdir(parents=True)
    manifest = inputs / "afo-manifests/fixture.json"
    manifest.write_text('{"example":"isolated-maintenance-control"}')
    envelope = dict(schema_version="1.0", request_id="NEXT-RENEWED", tenant_scope="line-local",
        manifest_sha256=sha256_file(manifest), input_manifest_ref="afo-manifests/fixture.json", approved_by="TEST",
        authorization_ref="INITIAL", driver_class="LL", target="fixture", safety_scope="TEST_ONLY",
        model_profile="fixture-local", submitted_utc="2026-11-05T00:00:00Z", priority="NORMAL")
    oid, _ = store.submit(envelope, repo=inputs, max_queued=4)
    limits = dict(max_attempts=4, max_jobs=4, max_requests=32, max_tokens=8388608,
                  max_tools=256, max_corrections=4, deadline=time.time()+600)
    ledger = MissionLedger(store)
    ledger.register("m1", "original-lineage", limits, "INITIAL", authorize=lambda *_: True)
    ledger.link("m1", oid)
    ledger.execution("m1", "retained-product", "PRODUCT", reserved_tokens=1048576, imported=True)
    before = ledger.snapshot("m1")
    with store.tx() as connection:
        original = connection.execute("SELECT record FROM afo_missions").fetchone()[0]
    private = tmp_path / "private"
    private.mkdir(mode=0o700)
    intent = Intent(private / "intent.json")
    epoch = intent.set("RUNNING", actor="TEST", reason="private renewal test", initialize=True)["epoch"]
    case = tmp_path / "case.json"
    case.write_text('{"scope":"TEST_ONLY"}')
    revision = dict(commit="b"*40, dirty=False)
    monkeypatch.setattr(workorder, "factory_revision", lambda: revision)
    monkeypatch.setattr(C.L, "authorized_job", lambda *_: True)
    monkeypatch.setattr(C.line_recovery, "valid_job", lambda *_: True)
    eff = SimpleNamespace(mode="PILOT", sha256="c"*64, get=lambda key, default=None: {
        "maintenance.enable_factory_maintainer": True, "budgets.max_order_wall_seconds": 1800}.get(key, default))
    job = dict(job_id="afo-agent-"+"1"*24, order_id=oid, attempt_id="a1", role=C.ROLE, state="SUCCEEDED",
        durable_native="maintenance-1", line_origin={"fixture": True}, policy_sha256=eff.sha256,
        factory_revision=revision, case=str(case), case_sha256=sha256_file(case), operations_epoch=epoch,
        native_context={"FORGE_OPERATIONS_INTENT": str(intent.path), "FORGE_AFO_QUEUE_SCOPE": "line-local"},
        mission_id="m1", profile="fixture-local", profile_sha256="d"*64, deadline_epoch=time.time()+400,
        line_role_authority_ref={"path": str(tmp_path / "control.json"), "sha256": "e"*64})
    control = dict(operations_intent=str(intent.path), profile=job["profile"], profile_sha256=job["profile_sha256"],
        source_revision=revision["commit"], policy_sha256=eff.sha256, authorization_ref="INITIAL",
        mission=dict(mission_id="m1", lineage="original-lineage", limits=copy.deepcopy(limits)))
    monkeypatch.setattr(CONTROL, "configuration", lambda *_a, **_kw: control)
    with store.tx() as connection:
        connection.execute("INSERT INTO afo_local_agent_jobs VALUES (?,?,?,?,?,?)",
            (job["job_id"], oid, job["attempt_id"], C.ROLE, job["state"], json.dumps(job)))
    assert C._authorized(store, job, eff) == store.order(oid)
    auth = tmp_path / "test-auth"
    auth.mkdir()
    monkeypatch.setattr(authz, "AUTH_DIR", auth)
    monkeypatch.setattr(authz, "verify", lambda *_a, **_kw: SimpleNamespace(allow=True))
    document = dict(schema=D.SCHEMA, mission_id="m1", snapshot_sha256=digest(before),
        deadline_epoch=time.time()+1200, authorization_ref="TIME-ONLY", request=C.L.request_for(store.order(oid)),
        reason="Private operator time-only amendment, no new exposure")
    (auth / "TIME-ONLY.json").write_text(json.dumps(dict(authorization_id="TIME-ONLY",
        expires_utc=datetime.fromtimestamp(time.time()+1800, UTC).isoformat(),
        signed_runbook_ref="mission-deadline-extension-014:"+digest(document))))
    D.extend(store, document, eff)
    effective = ledger.snapshot("m1")
    control["mission"]["limits"] = copy.deepcopy(effective["limits"])
    assert CONTROL.require_job_binding(job, control, store=store)
    if fault == "stale":
        control["mission"]["limits"] = limits
    elif fault == "extra_cap":
        control["mission"]["limits"]["max_attempts"] += 1
    elif fault == "lineage":
        control["mission"]["lineage"] = "renamed"
    elif fault == "authority":
        control["authorization_ref"] = "FOREIGN"
    elif fault == "job_deadline":
        job["deadline_epoch"] = time.time()-1
        C.L.save(store, job)
    if fault:
        with pytest.raises(Refused, match="LINE_MAINTENANCE_" + (
                "DEADLINE" if fault == "job_deadline" else "CONTROL_MISSION_OR_INTENT_CHANGED")):
            C._authorized(store, job, eff)
    else:
        assert C._authorized(store, job, eff) == store.order(oid)
        assert C._review_deadline(store, job) == job["deadline_epoch"]
    assert ledger.snapshot("m1") == effective
    assert effective["charged_tokens"] == before["charged_tokens"] == 1048576
    assert effective["attempts"] == before["attempts"] == 1 and effective["usage_unknown"] is True
    with store.tx() as connection:
        assert connection.execute("SELECT record FROM afo_missions").fetchone()[0] == original
