"""Signed qualification intake through the real AFO queue, scheduler and mission ledger; no native or model effect."""

import copy
import json
import shutil
import subprocess
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from forge_factory.afo import authz, host, policy, scheduler
from forge_factory.afo import local_agent as L
from forge_factory.afo import protocol_faults as F
from forge_factory.afo import qualification as Q
from forge_factory.afo import qualification_inputs as I
from forge_factory.afo import qualification_intake as N
from forge_factory.afo.durable import Refused, digest
from forge_factory.afo.mission_ledger import MissionLedger
from forge_factory.afo.queue import Store

REF = "AUTH-INTAKE"
FIRST, SECOND = "obligation-counterexample:0", "obligation-counterexample:1"
HEALTHY = {name: (lambda: True) for name in ("mount", "capacity", "fabro", "gateway", "mcp")}


def limits(**changes):
    out = dict(
        max_attempts=0,
        max_jobs=100,
        max_requests=100,
        max_tokens=3276800,
        max_tools=0,
        max_corrections=0,
        deadline=time.time() + 600,
    )
    return {**out, **changes}


def freeze(p, inputs_path, name="manifest.json", mission_limits=None):
    inputs = json.loads(Path(inputs_path).read_text())
    config = inputs["model_configuration"]
    identity = {
        "role": "afo-recovery-planner",
        "model_digest": config["model_digest"],
        "precision": config["precision"],
        "reasoning": config["reasoning_effort"],
        "schema_mode": "json_schema",
        "adapter_revision": Q.revision(),
        "context_tokens": 65536,
        "sampling": {"temperature": 0},
        "task_class": "single-obligation-protocol",
    }
    return Q.freeze(
        "protocol",
        p.tmp / name,
        identity=identity,
        inputs=[inputs_path],
        jobs=inputs["jobs"],
        model_profile=config["model"],
        job_token_reservations=inputs["requested_initial_reservations"],
        mission={
            "mission_id": inputs["mission_id"],
            "lineage": "explicit-distinct-protocol-intake",
            "limits": mission_limits or limits(),
        },
        protocol_faults={
            t["trial_id"]: t["prospective_fault"] for t in inputs["trials"] if t["trial_id"].rsplit(":", 1)[0] in F.SUPPORTED
        },
    )


def sign(p, manifest, actions=("submit_workorder", "launch_workorder", "recover_workorder")):
    now = datetime.now(UTC)
    grant = dict(
        schema_version="1.0",
        authorization_id=REF,
        approver="fixture-owner",
        approval_evidence_ref="fixture:explicit-qualification-intake",
        issued_utc=(now - timedelta(seconds=1)).isoformat(),
        expires_utc=(now + timedelta(minutes=20)).isoformat(),
        policy_sha256=p.eff.sha256,
        mode="PILOT",
        allowed_actions=list(actions),
        scope={"models": [manifest["model_profile"]]},
        signature_ref=REF + ".sig",
        signed_runbook_ref="qualification-014:" + digest(manifest),
    )
    path = p.authdir / (REF + ".json")
    path.write_text(json.dumps(grant))
    authz.sign(path, p.key)
    return grant


@pytest.fixture
def intake(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("FORGE_EVENTS_DIR", str(tmp_path / "events"))
    monkeypatch.delenv("FORGE_DURABLE_AUTONOMY", raising=False)
    monkeypatch.delenv("FORGE_OPERATIONS_INTENT", raising=False)
    compiler = shutil.which("clang")
    if not compiler:
        pytest.skip("actual C compiler unavailable")
    real = subprocess.check_output

    def clean(cmd, *a, **k):  # generator cleanliness is its own preflight blocker (test_da014_qualification_scope)
        return "" if list(cmd[:2]) == ["git", "status"] else real(cmd, *a, **k)

    with monkeypatch.context() as m:
        m.setattr(subprocess, "check_output", clean)
        inputs = I.prepare(
            tmp_path / "inputs",
            compiler=compiler,
            campaign_id="intake-fixture",
            authorization_ref=REF,
            qualification_job_tokens=32768,
        )
    # The runtime never shares the preparer's private state directory (the Omniverse2 layout).
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "runtime-state"))
    authdir = tmp_path / "auth"
    authdir.mkdir()
    key = tmp_path / "fixture-owner-key"
    subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(key)], check=True, capture_output=True)
    signers = authdir / "allowed-signers"
    signers.write_text("fixture-owner " + key.with_suffix(".pub").read_text())
    monkeypatch.setattr(authz, "AUTH_DIR", authdir)
    monkeypatch.setattr(authz, "ALLOWED_SIGNERS", signers)
    pol = copy.deepcopy(policy.load().policy)
    pol["authorization_ref"] = REF
    pol["engineering"]["enable_recovery_planner"] = True
    pol["engineering"]["allowed_model_profiles"] = [inputs["model_configuration"]["model"]]
    eff = policy.Effective("PILOT", "PILOT", "a" * 64, pol)
    monkeypatch.setattr(policy, "load", lambda *a, **k: eff)
    monkeypatch.setattr(host, "preflight", lambda: {"ok": True})
    monkeypatch.setattr(Q.socket, "gethostname", lambda: "omniverse2")
    p = SimpleNamespace(tmp=tmp_path, inputs=inputs, authdir=authdir, key=key, eff=eff, store=Store(tmp_path / "afo.sqlite3"))
    p.inputs_path = Path(inputs["root"]) / "inputs.json"
    p.manifest = freeze(p, p.inputs_path)
    p.grant = sign(p, p.manifest)
    p.trial = {t["trial_id"]: t for t in inputs["trials"]}
    return p


def commands(store):
    with store.tx() as c:
        return c.execute("SELECT kind FROM afo_commands_outbox").fetchall()


def test_enrollment_links_mission_before_queue_and_scheduler_admits_wrapper_without_launch(intake):
    p = intake
    out = N.enroll(p.manifest, REF, store=p.store, trial_ids=[FIRST])
    assert out["status"] == "ENROLLED_WAITING_AFO_ADMISSION" and out["submitted"] == [FIRST]
    assert out["inference_requests"] == 0 and out["campaign_denominator"] == 100
    oid = p.trial[FIRST]["order_id"]
    order = p.store.order(oid)
    assert order["state"] == "QUEUED" and not p.store.attempts(oid)
    ledger = MissionLedger(p.store)
    assert ledger.for_order(oid) == p.manifest["mission"]["mission_id"]
    snap = ledger.snapshot(p.manifest["mission"]["mission_id"])
    assert snap["limits"] == p.manifest["mission"]["limits"] and snap["authorization_ref"] == REF
    assert (snap["attempts"], snap["jobs"], snap["requests"], snap["charged_tokens"]) == (0, 0, 0, 0)
    rec = N.context(p.store, order)
    assert rec["qualification_ref"] == "qualification-014:" + digest(p.manifest) and rec["trial_id"] == FIRST
    # The protocol-only mission (max_attempts=0) is not mistaken for an exhausted product budget.
    assert scheduler.preflight(order, p.eff, p.store, HEALTHY) == []
    cycle = scheduler.cycle(p.store, "fixture-controller", eff=p.eff, probes=HEALTHY)
    assert cycle["action"] == "admitted", cycle
    (att,) = p.store.attempts(oid)
    assert att["record"]["evidence_refs"] == [rec["qualification_ref"]] and att["record"]["fabro_run_id"] is None
    assert p.store.order(oid)["state"] == "ADMITTED" and not commands(p.store)
    assert [e["type"] for e in p.store.events(oid)].count("afo.qualification_admitted") == 1


def test_admitted_wrapper_provisions_once_after_a_crash_before_role_preparation(intake):
    p = intake
    N.enroll(p.manifest, REF, store=p.store, trial_ids=[FIRST])
    scheduler.cycle(p.store, "fixture-controller", eff=p.eff, probes=HEALTHY)
    oid = p.trial[FIRST]["order_id"]
    real = L.prepare
    calls = []

    def crash(*a, **k):
        calls.append(1)
        raise OSError("crash after wrapper start, before role preparation")

    L.prepare = crash
    try:
        with pytest.raises(OSError):
            Q.provision(p.manifest, REF, store=p.store, trial_ids=[FIRST])
    finally:
        L.prepare = real
    assert p.store.order(oid)["state"] == "RUNNING" and calls == [1]
    first = Q.provision(p.manifest, REF, store=p.store, trial_ids=[FIRST])
    again = Q.provision(p.manifest, REF, store=p.store, trial_ids=[FIRST])
    assert first["status"] == "PROVISIONED_NOT_RUN" and first["provisioned_this_call"] == 1
    assert again["provisioned_this_call"] == 0
    (job,) = L.records(p.store, oid)
    assert job["job_id"] == p.manifest["jobs"][FIRST]["job_id"] and job["state"] == "PREPARED"
    assert job["qualification_manifest_sha256"] == digest(p.manifest) and job["reserved_tokens"] == 32768
    assert len(p.store.attempts(oid)) == 1 and not commands(p.store)
    snap = MissionLedger(p.store).snapshot(p.manifest["mission"]["mission_id"])
    assert (snap["attempts"], snap["jobs"], snap["requests"], snap["charged_tokens"]) == (0, 1, 0, 32768)


def test_crash_between_link_and_submit_recovers_without_duplicate_order(intake, monkeypatch):
    p = intake
    real = Store.submit
    monkeypatch.setattr(Store, "submit", lambda *a, **k: (_ for _ in ()).throw(OSError("crash before intake commit")))
    with pytest.raises(OSError):
        N.enroll(p.manifest, REF, store=p.store, trial_ids=[FIRST])
    oid = p.trial[FIRST]["order_id"]
    assert p.store.order(oid) is None and MissionLedger(p.store).for_order(oid) == p.manifest["mission"]["mission_id"]
    monkeypatch.setattr(Store, "submit", real)
    assert N.enroll(p.manifest, REF, store=p.store, trial_ids=[FIRST])["submitted"] == [FIRST]
    replay = N.enroll(p.manifest, REF, store=p.store, trial_ids=[FIRST])
    assert replay["submitted"] == [] and replay["already_enrolled"] == [FIRST]
    assert len([o for o in p.store.orders() if o["order_id"] == oid]) == 1


def test_unbound_legacy_inputs_are_refused_before_any_durable_effect(intake):
    p = intake
    legacy = json.loads(p.inputs_path.read_text())
    for trial in legacy["trials"]:
        trial.pop("intake")
    path = p.tmp / "legacy-inputs.json"
    path.write_text(json.dumps(legacy))
    manifest = freeze(p, path, name="legacy-manifest.json")
    sign(p, manifest)
    with pytest.raises(Refused, match="QUALIFICATION_INTAKE_UNBOUND_LEGACY_INPUT"):
        N.enroll(manifest, REF, store=p.store, trial_ids=[FIRST])
    with p.store.tx() as c:
        assert not c.execute("SELECT 1 FROM afo_missions").fetchone()
    assert not p.store.orders()


@pytest.mark.parametrize("target", ["envelope", "launch_manifest", "run_manifest", "model_profile"])
def test_changed_bound_intake_bytes_refuse_enrollment(intake, target):
    p = intake
    path = Path(p.inputs["root"]) / p.trial[FIRST]["intake"][target]["path"]
    path.chmod(0o600)
    path.write_text(path.read_text().replace("}", ', "x": 1}', 1))
    with pytest.raises(Refused, match="QUALIFICATION_INTAKE_FILE_CHANGED"):
        N.enroll(p.manifest, REF, store=p.store, trial_ids=[FIRST])
    assert not p.store.orders()


def test_tampered_launch_manifest_after_enrollment_blocks_only_that_wrapper(intake):
    p = intake
    N.enroll(p.manifest, REF, store=p.store, trial_ids=[FIRST])
    oid = p.trial[FIRST]["order_id"]
    path = Path(p.inputs["root"]) / p.trial[FIRST]["intake"]["launch_manifest"]["path"]
    path.chmod(0o600)
    path.write_text(path.read_text().replace("QUALIFICATION_PROTOCOL_FIXTURE", "PRODUCT"))
    cycle = scheduler.cycle(p.store, "fixture-controller", eff=p.eff, probes=HEALTHY)
    assert cycle["action"] == "blocked" and cycle["issues"] == ["QUALIFICATION_INTAKE_BINDING_CHANGED"]
    assert p.store.order(oid)["state"] == "BLOCKED" and not p.store.attempts(oid)


def test_changed_source_profile_after_admission_refuses_role_binding(intake):
    p = intake
    N.enroll(p.manifest, REF, store=p.store, trial_ids=[FIRST])
    scheduler.cycle(p.store, "fixture-controller", eff=p.eff, probes=HEALTHY)
    path = Path(p.inputs["root"]) / p.trial[FIRST]["intake"]["model_profile"]["path"]
    path.chmod(0o600)
    path.write_text(json.dumps({"default": "unqualified-model"}))
    with pytest.raises(Refused, match="QUALIFICATION_INTAKE_FILE_CHANGED"):
        Q.provision(p.manifest, REF, store=p.store, trial_ids=[FIRST])
    oid = p.trial[FIRST]["order_id"]
    assert p.store.order(oid)["state"] == "ADMITTED" and not L.records(p.store, oid)


def test_protocol_only_mission_stops_on_finite_job_limits_not_product_attempts(intake):
    p = intake
    manifest = freeze(p, p.inputs_path, name="one-job.json", mission_limits=limits(max_jobs=1, max_requests=1, max_tokens=32768))
    sign(p, manifest)
    N.enroll(manifest, REF, store=p.store, trial_ids=[FIRST, SECOND])
    assert scheduler.cycle(p.store, "fixture-controller", eff=p.eff, probes=HEALTHY)["action"] == "admitted"
    Q.provision(manifest, REF, store=p.store, trial_ids=[FIRST])
    second = p.store.order(p.trial[SECOND]["order_id"])
    assert "MISSION_ALLOWANCE_EXHAUSTED" in scheduler.preflight(second, p.eff, p.store, HEALTHY)
    snap = MissionLedger(p.store).snapshot(manifest["mission"]["mission_id"])
    assert snap["limits"]["max_attempts"] == 0 and snap["attempts"] == 0 and snap["jobs"] == 1


def test_existing_mission_with_other_limits_is_never_reset(intake):
    p = intake
    mission = p.manifest["mission"]
    MissionLedger(p.store).register(
        mission["mission_id"], mission["lineage"], limits(max_jobs=1), REF, authorize=lambda *a: True
    )
    with pytest.raises(Refused, match="MISSION_ALLOWANCE_RESET_FORBIDDEN"):
        N.enroll(p.manifest, REF, store=p.store, trial_ids=[FIRST])
    assert not p.store.orders()


@pytest.mark.parametrize("missing", ["submit_workorder", "launch_workorder", "recover_workorder"])
def test_every_intake_action_requires_the_current_owner_signature(intake, missing):
    p = intake
    sign(p, p.manifest, actions=[a for a in N.ACTIONS if a != missing])
    out = N.enroll(p.manifest, REF, store=p.store, trial_ids=[FIRST])
    assert out["status"] == "BLOCKED" and not p.store.orders()
    assert any(b.endswith(":" + missing) or b == "AUTH_ACTION_NOT_ALLOWED" for b in out["blockers"])


def test_mission_cannot_outlive_its_signed_authority(intake):
    p = intake
    manifest = freeze(p, p.inputs_path, name="long.json", mission_limits=limits(deadline=time.time() + 7200))
    sign(p, manifest)
    with pytest.raises(Refused, match="QUALIFICATION_MISSION_OUTLIVES_AUTHORITY"):
        N.enroll(manifest, REF, store=p.store, trial_ids=[FIRST])
    assert not p.store.orders()


def test_operator_pause_and_runbook_change_hold_enrolled_wrappers(intake):
    p = intake
    N.enroll(p.manifest, REF, store=p.store, trial_ids=[FIRST])
    oid = p.trial[FIRST]["order_id"]
    p.store.set_control("paused", "1", "fixture-operator", "hold qualification")
    assert scheduler.cycle(p.store, "fixture-controller", eff=p.eff, probes=HEALTHY)["code"] == "PAUSED"
    p.store.set_control("paused", "0", "fixture-operator", "resume")
    other = copy.deepcopy(p.manifest)
    other["bounds"]["batch_items"] = 31
    sign(p, other)  # the grant now signs another runbook
    assert "SIGNED_CAMPAIGN_RUNBOOK_MISMATCH" in scheduler.preflight(p.store.order(oid), p.eff, p.store, HEALTHY)
    assert p.store.order(oid)["state"] == "QUEUED" and not p.store.attempts(oid)


def test_ordinary_orders_keep_repository_launch_manifests(intake, tmp_path):
    p = intake
    order = {"order_id": "ordinary", "manifest_sha256": "0" * 64, "input_manifest_ref": "x", "envelope": "{}"}
    assert N.context(p.store, order) is None


def test_sealed_packets_are_imported_into_the_runtime_state_only_when_hashes_match(intake):
    p = intake
    case = json.loads(Path(p.manifest["jobs"][FIRST]["case"]).read_text())
    copy_path = Path(p.inputs["root"]) / "packets" / case["packet_ref"]["path"]
    runtime = p.tmp / "runtime-state" / case["packet_ref"]["path"]
    assert copy_path.is_file() and not runtime.exists()
    copy_path.chmod(0o600)
    copy_path.write_text(copy_path.read_text().replace("SWR-001", "SWR-999", 1))
    with pytest.raises(Refused, match="QUALIFICATION_INTAKE_PACKET_CHANGED"):
        N.enroll(p.manifest, REF, store=p.store, trial_ids=[FIRST])
    with p.store.tx() as c:
        assert not c.execute("SELECT 1 FROM afo_missions").fetchone()
    assert not p.store.orders() and not runtime.exists()


def test_deterministic_role_refusal_closes_only_that_wrapper_and_frees_capacity(intake, monkeypatch):
    p = intake
    N.enroll(p.manifest, REF, store=p.store, trial_ids=[FIRST, SECOND])
    scheduler.cycle(p.store, "fixture-controller", eff=p.eff, probes=HEALTHY)
    monkeypatch.setattr(L, "prepare", lambda *a, **k: (_ for _ in ()).throw(Refused("PACKET_REFERENCE_INVALID")))
    out = Q.provision(p.manifest, REF, store=p.store, trial_ids=[FIRST])
    assert out["status"] == "ROLE_JOB_REFUSED_WRAPPER_CLOSED"
    assert out["refused_trials"] == [{"trial": FIRST, "code": "QUALIFICATION_PROVISION_REFUSED:PACKET_REFERENCE_INVALID"}]
    first = p.store.order(p.trial[FIRST]["order_id"])
    assert first["state"] == "BLOCKED" and first["terminal_reason"].endswith("PACKET_REFERENCE_INVALID")
    assert [a["state"] for a in p.store.attempts(first["order_id"])] == ["CANCELLED"]
    assert MissionLedger(p.store).snapshot(p.manifest["mission"]["mission_id"])["jobs"] == 0
    assert scheduler.cycle(p.store, "fixture-controller", eff=p.eff, probes=HEALTHY)["action"] == "admitted"
