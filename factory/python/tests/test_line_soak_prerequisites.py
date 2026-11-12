"""CONTROL admission/replay fixtures only: no model, service, fault or live soak."""
# ruff: noqa: F811 - imported pytest fixtures are intentionally used by name
import copy
import json
import sqlite3
import time
from pathlib import Path
from types import SimpleNamespace

import pytest
from forge_factory.afo import line_soak as L
from forge_factory.afo import line_soak_prerequisites as P
from forge_factory.afo import operational_campaign as C
from forge_factory.afo import qualification as Q
from forge_factory.afo.durable import Refused, immutable_json
from forge_factory.afo.queue import ReadSnapshot, Store
from forge_factory.common import sha256_file
from test_da014_qualification import identity
from test_line_conductor_m3 import env  # noqa: F401
from test_line_soak import local_plan  # noqa: F401


def ref(path, value):
    immutable_json(path, value)
    return {"path": str(path), "sha256": sha256_file(path)}


def test_reference_is_bounded_hash_bound_and_rejects_symlink_parent(tmp_path):
    item = ref(tmp_path / "record.json", {"schema": "CONTROL"})
    assert P.reference(item) == {"schema": "CONTROL"}
    with pytest.raises(Refused, match="REFERENCE_CHANGED"):
        P.reference({**item, "sha256": "0" * 64})
    link = tmp_path / "link"
    link.symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(Refused, match="PATH_INVALID"):
        P.reference({**item, "path": str(link / "record.json")})
    with pytest.raises(Refused, match="REFERENCE_INVALID"):
        P.reference({**item, "ready": True})
    large = tmp_path / "large.json"
    large.write_bytes(b"x" * (P.LIMIT + 1))
    with pytest.raises(Refused, match="BOUNDED"):
        P.reference({"path": str(large), "sha256": sha256_file(large)})


def test_frozen_reference_cannot_be_added_only_to_plan(tmp_path):
    item = ref(tmp_path / "record.json", {"schema": "CONTROL"})
    with pytest.raises(Refused, match="NOT_FROZEN"):
        P.frozen_reference({"inputs": []}, item)
    assert P.frozen_reference({"inputs": [item]}, item)["schema"] == "CONTROL"


def capability(tmp_path, monkeypatch, role="swe3-author", work_class="PRODUCT"):
    from forge_factory.lrtx import role_capability as R

    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    ident = {**identity(role), "adapter_revision": "a" * 40, "model_digest": "model-digest", "precision": "Q8_0"}
    oracle = ref(tmp_path / (role + "-oracle.json"), {"scope": "CONTROL independent fixture"})
    report = ref(tmp_path / (role + "-report.json"), {
        "manifest_sha256": "m", "identity_sha256": R.key(ident), "status": "PASS", "execution_host": "omniverse2",
        "independent_oracle_refs": [{**oracle, "producer": "reference"}],
        "envelope": {"max_obligations": 2, "work_classes": [work_class]}})
    receipt = R.record(ident, report_path=report["path"], report_sha256=report["sha256"], expected_manifest_sha256="m")
    return {"identity": ident, "ref": receipt}, oracle


def test_real_role_validator_not_qualified_flag_or_source_eligibility(tmp_path, monkeypatch):
    entry, oracle = capability(tmp_path, monkeypatch)
    job = {"model": "model", "semantic_obligations": 2, "work_class": "PRODUCT"}
    ctl = {"source_revision": "a" * 40, "role_capabilities": {"swe3-author": entry}}
    prof = {"models": {"allowed": {"model": {"digest": "model-digest", "quantization": "Q8_0"}}}}
    out = P._roles(job, ctl, None, None, {"swe3-author": ["model"]}, prof)
    assert out[0]["qualification_only"] is False
    for changed in ({**job, "semantic_obligations": 3}, {k: v for k, v in job.items() if k != "semantic_obligations"}):
        with pytest.raises(Refused, match="CAPABILITY_LIMIT"):
            P._roles(changed, ctl, None, None, {"swe3-author": ["model"]}, prof)
    Path(oracle["path"]).chmod(0o600)  # deliberate external CONTROL tamper
    Path(oracle["path"]).write_text("changed")
    with pytest.raises(Refused, match="REFERENCE_CHANGED"):
        P._roles(job, ctl, None, None, {"swe3-author": ["model"]}, prof)


def test_prospective_planner_requires_class_receipt_without_inventing_future_objective(tmp_path, monkeypatch):
    role = "afo-recovery-planner"
    entry, _ = capability(tmp_path, monkeypatch, role, "PRODUCT_DIAGNOSIS")
    ctl = {"source_revision": "a" * 40, "role_capabilities": {role: entry}}
    prof = {"models": {"allowed": {"model": {"digest": "model-digest", "quantization": "Q8_0"}}},
            "runtime": {"ollama": {"OLLAMA_CONTEXT_LENGTH": 8192}}}
    assert P._roles({"model": "model"}, ctl, None, None, {role: ["model"]}, prof)[0]["envelope"]["max_obligations"] == 2
    ctl["role_capabilities"] = {}
    with pytest.raises(Refused, match="CAPABILITY_LIMIT"):
        P._roles({"model": "model"}, ctl, None, None, {role: ["model"]}, prof)


def test_finite_trial_is_explicit_not_role_competence_or_campaign_authority(tmp_path, monkeypatch):
    from forge_factory.afo import product_role_trial as T

    seen = []
    trial = {"authorization_ref": "CONTROL", "roles": {"swe3-author": ["CONTROL"]}}
    monkeypatch.setattr(T, "resolve", lambda ref: trial)
    monkeypatch.setattr(T, "authorized", lambda ref, job, eff, **kw: seen.append((job, kw)) or trial)
    ctl = {"product_role_trial": {"path": "CONTROL", "sha256": "1" * 64}, "role_capabilities": {}}
    reader = object()
    out = P._roles({"model": "model"}, ctl, None, reader, {"swe3-author": ["model"]},
                   {"models": {"allowed": {"model": {"digest": "d", "quantization": "Q8"}}}})
    assert out[0]["qualification_only"] is True and out[0]["qualified"] is False
    assert seen[0][1] == {"store": reader}
    with pytest.raises(Refused, match="TRIAL_ROLE_UNDECLARED"):
        P._roles({"model": "model"}, ctl, None, reader, {"swe3-inspector": ["model"]},
                 {"models": {"allowed": {"model": {"digest": "d", "quantization": "Q8"}}}})


def test_readonly_future_execution_needs_no_native_outcome_and_creates_nothing(tmp_path):
    path = tmp_path / "queue.sqlite3"
    Store(path)
    before = path.read_bytes()
    with ReadSnapshot(path, timeout_s=3) as reader:
        out = P._execution(reader, {"job_id": "CONTROL", "state": "PREPARED"})
        P._resources(reader, [{"job_id": "CONTROL", "execution": out}])
        with pytest.raises(sqlite3.OperationalError):
            with reader.tx() as c:
                c.execute("CREATE TABLE forbidden(value)")
    assert out["execution_liveness"] == "NOT_DISPATCHED"
    assert path.read_bytes() == before


def test_unknown_execution_lease_is_not_free_or_released(tmp_path):
    from forge_factory.afo.execution_lifecycle import Executions
    from forge_factory.afo.mission_ledger import MissionLedger

    path = tmp_path / "queue.sqlite3"
    store = Store(path)
    limits = dict(max_attempts=2, max_jobs=2, max_requests=4, max_tokens=1000, max_tools=4, max_corrections=1,
                  deadline=time.time() + 60)
    MissionLedger(store).register("fixture-mission", "CONTROL", limits, "CONTROL", authorize=lambda *a: True)
    MissionLedger(store).execution("fixture-mission", "CONTROL", "PRODUCT", reserved_tokens=100)
    ex = Executions(store)
    ex.reserve("CONTROL", "fixture-mission", "1" * 32)
    ex.dispatch_intent("CONTROL")
    before = ex.get("CONTROL")
    with ReadSnapshot(path, timeout_s=3) as reader:
        with pytest.raises(Refused, match="UNKNOWN|UNCERTAIN"):
            P._execution(reader, {"job_id": "CONTROL", "mission_id": "fixture-mission", "nonce": "1" * 32})
        with pytest.raises(Refused, match="FOREIGN_OR_UNKNOWN"):
            P._resources(reader, [])
    assert ex.get("CONTROL") == before and before["resource_lease"] == "HELD"


def test_missing_evidence_stays_blocked_no_start_or_dispatch(local_plan, monkeypatch):  # noqa: F811
    monkeypatch.setattr(Q, "preflight", lambda *a, **kw: {"status": "READY", "blockers": []})
    monkeypatch.setattr(C, "start", lambda *a, **kw: pytest.fail("must not start"))
    result = L.start(local_plan.manifest, "CONTROL", "CONTROL", local_plan.ref)
    assert result["blockers"] == ["LINE_AUTONOMY_PREREQUISITES_NOT_QUALIFIED"]
    assert result["prerequisites"]["effects_performed"] is False


def test_fault_refuses_exact_unit_mismatch_before_auth_or_systemctl(local_plan, monkeypatch):  # noqa: F811
    from forge_factory.afo import operations

    monkeypatch.setattr(Q, "preflight", lambda *a, **kw: {"blockers": []})
    monkeypatch.setattr(operations, "UNIT", "forge-conductor.service")
    with pytest.raises(Refused, match="FAULT_TARGET_MISMATCH"):
        C.fault(local_plan.manifest, "crash", "CONTROL", local_plan.tmp / "fault.json")
    assert local_plan.calls == []


def test_generic_fault_target_and_no_historical_claims_do_not_require_completed_cohorts():
    assert P.fault_target({"inputs": []}) is None
    assert P._claims([], {"source_revision": "a" * 40}) == []


@pytest.fixture
def pending(env, monkeypatch, request):
    """Real signed TEST-key M3 queue/campaign; no attempt, native run or lease."""
    import yaml
    from forge_factory.afo import authz, policy
    from forge_factory.afo import line_orders as O
    from forge_factory.afo import line_recovery_control as K
    from forge_factory.afo.durable import digest
    from forge_factory.afo.mission_ledger import MissionLedger
    from forge_factory.afo.queue import QueueError
    from forge_factory.common import REPO_ROOT
    from forge_factory.lrtx import profile as profiles
    from forge_factory.lrtx import role_capability as R
    from test_line_conductor_m3 import ORN, PROFILE, REV1, grant, lineage, placer, write_campaign

    data = env["tmp"] / "application"
    launch = data / "line"
    monkeypatch.setenv("FORGE_STATE_DIR", str(launch / "lrtx/state"))
    monkeypatch.setenv("FORGE_DATA_ROOT", str(data))
    path = write_campaign(env, [lineage("crc-hal", "CRCHAL", "20261104-L38")])
    grant(env)
    from forge_factory.common import canonical_json, sha256_bytes
    afo = yaml.safe_load((REPO_ROOT / "config/factory/afo-policy.yaml").read_text())
    afo["authorization_ref"] = "AUTH-CONTROL"
    afo["budgets"]["max_model_tokens_per_order"] = 1048576
    afo["engineering"]["enable_recovery_planner"] = False
    afo["engineering"]["allowed_model_profiles"] = [PROFILE]
    afo_path = env["tmp"] / "afo-policy.yaml"
    afo_path.write_text(yaml.safe_dump(afo))
    monkeypatch.setenv("FORGE_AFO_POLICY", str(afo_path))
    eff_sha = sha256_bytes(canonical_json(afo))
    monkeypatch.setattr(K, "revision", lambda: {"commit": REV1, "dirty": False})
    monkeypatch.setattr(L, "_revision", lambda: {"commit": REV1, "dirty": False})
    monkeypatch.setattr(Q, "revision", lambda: REV1)
    monkeypatch.setattr(P, "current_source", lambda: {"commit": REV1, "dirty": False})
    monkeypatch.setattr(authz, "AUTH_DIR", env["tmp"] / "auth")
    monkeypatch.setattr(authz, "ALLOWED_SIGNERS", env["signers"])
    profile = profiles.load(PROFILE)
    intent = env["tmp"] / "intent.json"
    immutable_json(intent, {"mode": "RUNNING", "epoch": 1})
    monkeypatch.setenv("FORGE_OPERATIONS_INTENT", str(intent))
    entries = {}
    route = profile["structured"]["role_models"]
    for suffix in ("author", "inspector"):
        role = "swe1-" + suffix
        model = profile["models"]["allowed"][route[suffix]]
        ident = {**identity(role), "adapter_revision": REV1, "model_digest": model["digest"], "precision": model["quantization"],
                 "context_tokens": 262144}
        oracle = ref(env["tmp"] / (role + "-oracle.json"), {"scope": "CONTROL only"})
        report = ref(env["tmp"] / (role + "-report.json"), {"manifest_sha256": "CONTROL", "identity_sha256": R.key(ident),
                    "status": "PASS", "execution_host": "omniverse2", "independent_oracle_refs": [{**oracle, "producer": "reference"}],
                    "envelope": {"max_obligations": 2, "work_classes": ["PRODUCT"]}})
        entries[role] = {"identity": ident, "ref": R.record(ident, report_path=report["path"], report_sha256=report["sha256"],
                                                         expected_manifest_sha256="CONTROL")}
    ctl = {"schema": K.SCHEMA, "source_revision": REV1, "policy_sha256": eff_sha, "authorization_ref": "AUTH-CONTROL",
           "profile": PROFILE, "profile_sha256": profile["_sha256"], "operations_intent": str(intent),
           "mission": {"mission_id": "CONTROL-mission", "lineage": "CONTROL-future-work", "limits": {
               "max_attempts": 3, "max_jobs": getattr(request, "param", {}).get("max_jobs", 2), "max_requests": 8, "max_tokens": 4194304,
               "max_tools": 24, "max_corrections": 2, "deadline": time.time() + 600}},
           "role_capabilities": entries, "product_role_trial": None}
    ctl_ref = ref(env["tmp"] / "control.json", ctl)
    grant_path = env["tmp"] / "auth/AUTH-CONTROL.json"
    signed = json.loads((env["tmp"] / "auth/AUTH-T.json").read_text())
    signed.update(authorization_id="AUTH-CONTROL", signature_ref="AUTH-CONTROL.sig", policy_sha256=eff_sha)
    signed["scope"]["models"].append(ORN)
    signed["signed_runbook_ref"] = "line-recovery-014:" + digest(ctl)
    grant_path.write_text(json.dumps(signed))
    grant_path.with_suffix(".json.sig").unlink(missing_ok=True)
    (grant_path.parent / "AUTH-CONTROL.sig").unlink(missing_ok=True)
    authz.sign(grant_path, env["key"])
    eff = policy.load()
    assert eff.mode == "PILOT", eff.issues

    def busy(*args, **kwargs):
        raise QueueError("CAPACITY", "CONTROL no admission")
    real_admit = Store.admit
    monkeypatch.setattr(Store, "admit", busy)
    # A durable recovery configuration never initializes authority: the queue must already exist.
    Store(O.supervisor_dir() / "line-queue.sqlite3")
    result = placer(env, recovery_config=Path(ctl_ref["path"])).cycle()
    store = Store(O.supervisor_dir() / "line-queue.sqlite3")
    assert len(store.orders()) == 1, result
    row = store.orders()[0]
    assert row["state"] == "QUEUED" and store.attempts(row["order_id"]) == []
    MissionLedger(store).register(**ctl["mission"], authorization_ref="AUTH-CONTROL", authorize=lambda *a: True)
    spec_path = O.supervisor_dir() / "line-orders" / (row["request_id"] + ".json")
    descriptor = {"schema": "forge-c/line-soak-pending-order/1", "order_id": row["order_id"], "attempt_seq": 1,
                  "spec_ref": {"path": str(spec_path), "sha256": sha256_file(spec_path)}, "control_ref": ctl_ref,
                  "line_origin": {"campaign_path": str(path), "policy_path": str(env["tmp"] / "line-policy.yaml"),
                                  "auth_base": str(env["tmp"] / "auth"), "allowed_signers": str(env["signers"])}}
    from forge_factory.afo.line_recovery_product import job_id
    aid = row["order_id"] + "-a1"
    binding = {"order_id": row["order_id"], "attempt_id": aid, "job_id": job_id(aid), "mission_id": ctl["mission"]["mission_id"]}
    desc_ref = ref(env["tmp"] / "pending.json", descriptor)
    cre = yaml.safe_load((REPO_ROOT / "config/factory/reliability-policy.yaml").read_text())
    cre.update(mode="ACTIVE", authorization={"runbook_ref": "CONTROL-only", "approved_by": "CONTROL-owner", "approved_on": "2026-11-05"})
    cre["promotion"]["allowed_automatic_operational_actions"] = ["restart_conductor"]
    cre_path = env["tmp"] / "cre-policy.yaml"
    cre_path.write_text(yaml.safe_dump(cre))
    monkeypatch.setenv("FORGE_CRE_POLICY", str(cre_path))
    cre_ref = {"path": str(cre_path), "sha256": sha256_file(cre_path)}
    doc = {"schema": P.SCHEMA, "source_revision": REV1, "profile_sha256": profile["_sha256"], "intent_epoch": 1,
           "jobs": {"future": desc_ref}, "recovery_policy_ref": cre_ref, "claims": []}
    index = ref(env["tmp"] / "prerequisites.json", doc)
    evidence = env["tmp"] / "external-evidence"
    evidence.mkdir()
    plan = L.observer_plan(data_root=data, launch_dir=launch, intent=intent, evidence_root=evidence,
                           mount_uuid="12345678-abcd", profile=PROFILE, prerequisites_ref=index)
    assert plan["database"] == str(store.path)
    plan_ref = ref(env["tmp"] / "plan.json", plan)
    manifest = Q.freeze("operation-24", env["tmp"] / "manifest.json", identity=identity(),
                        inputs=[Path(index["path"]), cre_path, Path(plan_ref["path"])], jobs={"future": binding}, model_profile=ORN)
    monkeypatch.setattr(K, "require_native_transport", lambda *a, **kw: {"scope": "CONTROL transport substitution, NOT qualification", "max_tokens": 16384})
    return SimpleNamespace(env=env, store=store, descriptor=descriptor, binding=binding, manifest=manifest, plan=plan, plan_ref=plan_ref,
                           control=ctl, intent=intent, eff=eff, doc=doc, index=index, real_admit=real_admit)


def database_snapshot(store):
    with store.tx() as c:
        return {name: [tuple(row) for row in c.execute('SELECT * FROM "' + name + '" ORDER BY rowid')]
                for (name,) in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}


def test_normal_pending_order_replays_without_future_receipt_charge_or_lease(pending):
    p = pending
    before = database_snapshot(p.store)
    result = P.check(p.manifest, p.plan)
    if result["blockers"]:
        from forge_factory.afo.line_soak_snapshot import CURRENT, Replay
        token = CURRENT.set(Replay(p.manifest, p.plan))
        try:
            P.require(p.manifest, p.plan)
        finally:
            CURRENT.reset(token)
    assert result["blockers"] == [], result
    assert result["jobs"][0]["execution"]["execution_liveness"] == "NOT_ADMITTED"
    assert result["jobs"][0]["reservation_performed"] is False
    assert result["jobs"][0]["fresh_admission_required"] is True
    assert result["claims"] == [] and result["live_campaign"] == "NOT_RUN"
    assert database_snapshot(p.store) == before
    assert p.store.attempts(p.binding["order_id"]) == []
    with p.store.tx() as c:
        assert c.execute("SELECT COUNT(*) FROM afo_mission_executions").fetchone()[0] == 0
        assert not c.execute("SELECT holder FROM afo_resource_ownership WHERE holder IS NOT NULL").fetchone()
    from forge_factory.afo import line_recovery as R
    # A preview never satisfies the normal actual-admitted API.
    origin = {k: Path(v) for k, v in p.descriptor["line_origin"].items()}
    with pytest.raises(R.BindingRefused, match="ATTEMPT_MISMATCH"):
        R.bind_order(p.store, p.binding["order_id"], p.binding["attempt_id"], **origin)


@pytest.mark.parametrize("changed", ["sequence", "state", "spec", "mission", "expiry", "signature", "epoch"])
def test_pending_context_changes_refuse_with_no_new_accounting(pending, changed):
    p = pending
    if changed == "state":
        p.store.transition(p.binding["order_id"], "PAUSED", "CONTROL operator pause")
    elif changed == "spec":
        path = Path(p.descriptor["spec_ref"]["path"])
        value = json.loads(path.read_text())
        value["revision"] = "b" * 40
        path.write_text(json.dumps(value))
    elif changed == "signature":
        (p.env["tmp"] / "auth/AUTH-CONTROL.sig").write_text("CONTROL revoked signature")
    elif changed == "epoch":
        p.intent.chmod(0o600)
        p.intent.write_text(json.dumps({"mode": "RUNNING", "epoch": 2}))
    elif changed == "expiry":
        p.control["mission"]["limits"]["deadline"] = 0  # unchanged signed/frozen bytes cannot authorize new content
        p.index = {**p.index, "sha256": "0" * 64}
        p.plan["prerequisites_ref"] = p.index
    else:
        descriptor = copy.deepcopy(p.descriptor)
        if changed == "sequence":
            descriptor["attempt_seq"] = 2
        else:
            p.manifest["jobs"]["future"]["mission_id"] = "foreign"
        if changed == "sequence":
            newref = ref(p.env["tmp"] / "changed-pending.json", descriptor)
            p.doc["jobs"]["future"] = newref
            newindex = ref(p.env["tmp"] / "changed-index.json", p.doc)
            p.manifest["inputs"].append(newindex)
            p.plan["prerequisites_ref"] = newindex
    before = database_snapshot(p.store)
    assert P.check(p.manifest, p.plan)["status"] == "BLOCKED"
    assert database_snapshot(p.store) == before


def test_public_preflight_replays_current_stage_without_circular_cohort_or_fault_outcomes(pending, monkeypatch):
    monkeypatch.setattr(Q, "preflight", lambda *a, **kw: {"status": "READY", "blockers": []})  # CONTROL host/campaign boundary
    before = database_snapshot(pending.store)
    out = L.preflight(pending.manifest, pending.plan_ref, live=True, authorization_ref="CONTROL")
    assert out["blockers"] == [], out
    assert out["prerequisite_status"] == "CURRENT_STAGE_PREREQUISITES_REPLAYED"
    assert out["live_campaign"] == "NOT_RUN" and out["service_stop_at_end"] is False
    assert database_snapshot(pending.store) == before


def test_stage_initial_epoch_cannot_authorize_old_start_but_fault_checks_current_resume_epoch(pending, monkeypatch):
    from forge_factory.afo import authz, operations
    p = pending
    operator = operations.Intent(p.intent)
    operator.set("STOPPED", actor="CONTROL", reason="CONTROL normal stop")
    operator.set("RUNNING", actor="CONTROL", reason="CONTROL normal resume")
    assert operator.read()["epoch"] == 3
    monkeypatch.setattr(Q, "preflight", lambda *a, **kw: {"status": "READY", "blockers": []})
    out = L.preflight(p.manifest, p.plan_ref, live=True, authorization_ref="CONTROL")
    assert out["blockers"] == ["LINE_SOAK_INTENT_CHANGED_OR_NOT_RUNNING"]
    grant_path = p.env["tmp"] / "auth/AUTH-CONTROL.json"
    record = json.loads(grant_path.read_text())
    record["allowed_actions"].append("operate_service")
    record["scope"]["service_actions"].append("qualification-fault:crash:forge-line-conductor-local.service")
    grant_path.write_text(json.dumps(record))
    (grant_path.parent / "AUTH-CONTROL.sig").unlink()
    authz.sign(grant_path, p.env["key"])
    monkeypatch.setattr(operations, "UNIT", "forge-line-conductor-local.service")
    monkeypatch.setenv("FORGE_OPERATIONS_INTENT", str(p.intent))
    effects = []
    original_run = C.subprocess.run
    def effect(command, **kwargs):
        if command[0] != "systemctl":
            return original_run(command, **kwargs)
        # Test the actual existing lock rather than replacing it with a boolean.
        import fcntl
        with p.intent.with_suffix(".lock").open("r+") as stream:
            with pytest.raises(BlockingIOError):
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        effects.append(command)
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(C.subprocess, "run", effect)
    # Q host/campaign authority is substituted above; this remains CONTROL only.
    # Actual source validation uses the frozen fake revision, no service is called.
    out = C.fault(p.manifest, "crash", "AUTH-CONTROL", p.env["tmp"] / "fault-control.json", observer_plan_ref=p.plan_ref)
    assert out["operations_epoch"] == 3
    assert effects == [["systemctl", "--user", "kill", "--kill-who=main", "--signal=KILL", "forge-line-conductor-local.service"]]


def test_public_generic_start_discovers_line_plan_and_rejects_forged_json_replay(pending, monkeypatch):
    from forge_factory.afo import soak
    p = pending
    monkeypatch.setattr(Q, "preflight", lambda *a, **kw: {"status": "READY", "blockers": []})
    calls = []
    def begin(*args):
        import fcntl
        with p.intent.with_suffix(".lock").open("r+") as stream:
            with pytest.raises(BlockingIOError):
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        calls.append(args)
        return {"scope": "CONTROL substituted append; NOT live evidence"}
    monkeypatch.setattr(soak, "start", begin)
    out = C.start(p.manifest, "soak-control-public-start", "AUTH-CONTROL")
    assert out["status"] == "STARTED_OBSERVATION_ONLY" and len(calls) == 1
    replay = P.check(p.manifest, p.plan)
    copied = json.loads(json.dumps(replay))
    assert P.admission_boundary(p.manifest, p.plan, copied)["blockers"] == ["LINE_SOAK_INTERNAL_REPLAY_SNAPSHOT_REQUIRED"]


@pytest.mark.parametrize("race", ["stop-resume", "deadline"])
def test_heavy_claim_replay_does_not_hold_stop_lock_and_cannot_leave_stale_start_authority(pending, monkeypatch, race):
    from forge_factory.afo import operations, soak
    p = pending
    monkeypatch.setattr(Q, "preflight", lambda *a, **kw: {"status": "READY", "blockers": []})
    monkeypatch.setattr(soak, "start", lambda *a: pytest.fail("stale admission must not append a head"))
    original = P._claims
    def replay(*args, **kwargs):
        # An operator can take the real lock while this potentially heavy replay
        # executes. No timing thresholds or accelerated duration become evidence.
        import fcntl
        lock = p.intent.with_suffix(".lock")
        with lock.open("a+") as stream:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            fcntl.flock(stream, fcntl.LOCK_UN)
        result = original(*args, **kwargs)
        if race == "stop-resume":
            operator = operations.Intent(p.intent)
            operator.set("STOPPED", actor="CONTROL", reason="CONTROL race")
            operator.set("RUNNING", actor="CONTROL", reason="CONTROL resume")
        else:
            now = time.time()
            monkeypatch.setattr(time, "time", lambda: now + 3600)  # CONTROL deadline refusal only
        return result
    monkeypatch.setattr(P, "_claims", replay)
    out = C.start(p.manifest, "soak-control-raced-start", "AUTH-CONTROL", observer_plan_ref=p.plan_ref)
    assert out["status"] == "BLOCKED", out


def test_same_stat_byte_tampering_is_rejected_by_boundary_hashes(pending):
    import os
    p = pending
    replay = P.check(p.manifest, p.plan)
    assert replay["blockers"] == []
    path = Path(p.control["role_capabilities"]["swe1-author"]["ref"]["path"])
    raw = path.read_bytes()
    stat = path.stat()
    altered = raw.replace(b'"qualified":true', b'"qualified":null')
    assert len(raw) == len(altered) and raw != altered
    path.chmod(0o600)
    path.write_bytes(altered)
    path.chmod(stat.st_mode & 0o777)
    os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns))
    assert path.stat().st_size == stat.st_size and path.stat().st_mtime_ns == stat.st_mtime_ns
    assert P.admission_boundary(p.manifest, p.plan, replay)["blockers"] == ["LINE_SOAK_REFERENCE_CHANGED"]


def test_qualified_lesson_claim_replays_normal_source_but_infers_no_application_or_benefit(tmp_path, monkeypatch):
    from forge_factory.knowledge import experience
    from forge_factory.knowledge.store import LessonStore
    from test_da014_learning import candidate

    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    memory = LessonStore()
    lesson = candidate(memory, tmp_path)
    validated = memory.validate(memory.propose(lesson, phase="SWE.3")["lesson_id"])
    assert validated["state"] == "VALIDATED"
    with memory._conn() as c:
        actual = json.loads(c.execute("SELECT record FROM lessons WHERE lesson_id=?", (validated["lesson_id"],)).fetchone()[0])
    claim = {"kind": "lesson", "record_ref": ref(tmp_path / "lesson-claim.json", actual)}
    before = experience.report(memory)
    rows = P._claims([claim], {"source_revision": "a" * 40})
    assert rows[0]["scope"] == "VALIDATED_MEMORY_RECORD_ONLY"
    assert rows[0]["applicability"]["phases"] == ["SWE.3"]
    assert rows[0]["application_inferred"] is False and rows[0]["benefit_inferred"] is False
    assert experience.report(memory) == before
    with memory._conn() as c:
        c.execute("UPDATE lessons SET state='RETRACTED' WHERE lesson_id=?", (actual["lesson_id"],))
    with pytest.raises(Refused, match="NOT_CURRENT_VALIDATED"):
        P._claims([claim], {"source_revision": "a" * 40})


def test_native_output_lower_bound_cannot_exceed_measured_role_context(tmp_path, monkeypatch):
    entry, _ = capability(tmp_path, monkeypatch)
    ctl = {"source_revision": "a" * 40, "role_capabilities": {"swe3-author": entry}}
    profile = {"models": {"allowed": {"model": {"digest": "model-digest", "quantization": "Q8_0"}}}}
    with pytest.raises(Refused, match="NATIVE_CONTEXT_TOO_SMALL"):
        P._roles({"model": "model", "reserved_tokens": 65536, "semantic_obligations": 1, "work_class": "PRODUCT"},
                 ctl, None, None, {"swe3-author": ["model"]}, profile, native_output_cap=16384)


def test_real_profile_maintainer_envelope_refusal_is_not_clamped(monkeypatch):
    from forge_factory.lrtx.profile import load
    from test_line_conductor_m3 import ORN, PROFILE
    profile = load(PROFILE)
    eff = SimpleNamespace(mode="PILOT", get=lambda key, default=None: {
        "maintenance.enable_factory_maintainer": True, "budgets.max_model_tokens_per_order": 1048576}.get(key, default))
    with pytest.raises(Refused, match="RECOVERY_NATIVE_ENVELOPE_EXCEEDS_RESERVATION"):
        P._auxiliary({"model": ORN, "profile": PROFILE}, eff, profile)
    assert profile["afo"]["role_job_tokens"]["afo-factory-maintainer"] == 131072


def test_auxiliary_measured_native_cap_uses_helper_reservation_not_product_capacity():
    from forge_factory.lrtx.profile import load
    from test_line_conductor_m3 import ORN, PROFILE
    profile = copy.deepcopy(load(PROFILE))
    # CONTROL prospective profile: enough for max_tokens=1 + thinking,
    # insufficient for the measured SDK output=16384 + thinking.
    profile["afo"]["role_job_tokens"]["afo-factory-maintainer"] = 140000
    identity = profile["models"]["allowed"][ORN]
    job = {"model": ORN, "profile": PROFILE, "reserved_tokens": 1048576}
    with pytest.raises(Refused, match="LINE_SOAK_NATIVE_RESERVATION_TOO_SMALL"):
        P._roles(job, {"role_capabilities": {}}, None, None, {"afo-factory-maintainer": [ORN]}, profile, native_output_cap=16384)
    assert job["reserved_tokens"] == 1048576 and identity["quantization"] == "Q8_0"


def test_late_unknown_historical_import_cannot_pass_start_boundary(pending):
    from forge_factory.afo.mission_ledger import MissionLedger
    p = pending
    replay = P.check(p.manifest, p.plan)
    assert replay["blockers"] == []
    ledger = MissionLedger(p.store)
    ledger.execution(p.binding["mission_id"], "CONTROL-historical-native", "PRODUCT", reserved_tokens=0,
                     imported=True, evidence_refs=["CONTROL-known-execution-unknown-consumption"])
    before = ledger.snapshot(p.binding["mission_id"])
    assert before["unbounded_historical_usage"] is True
    assert P.admission_boundary(p.manifest, p.plan, replay)["blockers"] == ["HISTORICAL_USAGE_REQUIRES_INDEPENDENT_BOUND"]
    assert ledger.snapshot(p.binding["mission_id"]) == before


def test_start_rechecks_earliest_job_deadline_after_final_database_observation(pending, monkeypatch):
    p = pending
    replay = P.check(p.manifest, p.plan)
    assert replay["blockers"] == []
    original = P._resources
    def final_read(reader, jobs):
        original(reader, jobs)
        now = time.time()
        monkeypatch.setattr(time, "time", lambda: now + 3600)  # CONTROL expiry during final read, not a live clock
    monkeypatch.setattr(P, "_resources", final_read)
    assert P.admission_boundary(p.manifest, p.plan, replay)["blockers"] == ["LINE_SOAK_START_AUTHORITY_EXPIRED"]


def test_fault_rechecks_grant_expiry_after_source_observation_before_kernel_call(pending, monkeypatch):
    from forge_factory.afo import authz, operations
    p = pending
    grant = p.env["tmp"] / "auth/AUTH-CONTROL.json"
    record = json.loads(grant.read_text())
    record["allowed_actions"].append("operate_service")
    record["scope"]["service_actions"].append("qualification-fault:crash:forge-line-conductor-local.service")
    grant.write_text(json.dumps(record))
    grant.with_suffix(".sig").unlink()
    authz.sign(grant, p.env["key"])
    monkeypatch.setattr(operations, "UNIT", "forge-line-conductor-local.service")
    monkeypatch.setattr(Q, "preflight", lambda *a, **kw: {"blockers": [], "status": "READY"})
    original_source = P.current_source
    def source():
        current = original_source()
        now = time.time()
        monkeypatch.setattr(time, "time", lambda: now + 15 * 86400)  # CONTROL: existing signed grant is now expired
        return current
    monkeypatch.setattr(P, "current_source", source)
    original_run = C.subprocess.run
    def kernel(command, **kwargs):
        if command[0] == "systemctl":
            pytest.fail("expired authority cannot reach kernel effect")
        return original_run(command, **kwargs)
    monkeypatch.setattr(C.subprocess, "run", kernel)
    out = C.fault(p.manifest, "crash", "AUTH-CONTROL", p.env["tmp"] / "no-fault.json", observer_plan_ref=p.plan_ref)
    assert out["blockers"] == ["LINE_SOAK_AUTHORITY_NOT_CURRENT"]
    assert not (p.env["tmp"] / "no-fault.json").exists()


@pytest.mark.parametrize("value", [[], 7, None, "not-an-object"])
def test_hash_valid_non_object_job_projection_is_typed_blocked(pending, value):
    p = pending
    from forge_factory.afo.durable import immutable_json
    from forge_factory.common import sha256_file
    path = p.env["tmp"] / "scalar-job.json"
    immutable_json(path, value)
    descriptor = {"path": str(path), "sha256": sha256_file(path)}
    with ReadSnapshot(p.store.path) as reader, pytest.raises(Refused, match="JOB_REFERENCE_INVALID"):
        P._job(p.manifest, p.plan, p.binding, descriptor, reader, p.eff)


@pytest.mark.parametrize("changed", ["campaign", "policy", "grant", "signature", "signers"])
def test_origin_inputs_changed_during_normal_binding_cannot_be_sealed_as_verified(pending, monkeypatch, changed):
    from forge_factory.afo import line_recovery as R
    p = pending
    original = R.bind_order
    paths = p.descriptor["line_origin"]
    selected = {"campaign": Path(paths["campaign_path"]), "policy": Path(paths["policy_path"]),
                "grant": p.env["tmp"] / "auth/AUTH-T.json", "signature": p.env["tmp"] / "auth/AUTH-T.sig",
                "signers": Path(paths["allowed_signers"])}[changed]
    def bind(*args, **kwargs):
        bound = original(*args, **kwargs)
        selected.write_bytes(selected.read_bytes() + b" ")
        return bound
    monkeypatch.setattr(R, "bind_order", bind)
    before = database_snapshot(p.store)
    result = P.check(p.manifest, p.plan)
    assert result["status"] == "BLOCKED" and result["blockers"][0] in {
        "LINE_SOAK_REFERENCE_CHANGED", "LINE_SOAK_REPLAY_INPUT_CHANGED"}
    assert database_snapshot(p.store) == before


@pytest.mark.parametrize("bad", ["/tmp/private-key", "../owner.sig", "owner_ed25519", "nested/../../owner.sig"])
def test_unvalidated_signature_path_never_reads_outside_signature_input(pending, monkeypatch, bad):
    from forge_factory.afo.line_soak_snapshot import Replay
    p = pending
    grant = p.env["tmp"] / "auth/AUTH-T.json"
    record = json.loads(grant.read_text())
    record["signature_ref"] = bad
    grant.write_text(json.dumps(record))
    snap = Replay(p.manifest, p.plan)
    original = snap.file
    reads = []
    def read(path, **kwargs):
        reads.append(Path(path))
        return original(path, **kwargs)
    monkeypatch.setattr(snap, "file", read)
    with pytest.raises(Refused, match="SIGNATURE_REFERENCE_INVALID"):
        snap.authority("AUTH-T", base=grant.parent, signers=p.env["signers"])
    assert reads == [grant]
