"""CONTROL: real signed intake/admission/accounting; no native/model/live-soak qualification."""
# ruff: noqa: F811
import copy
import json
import time
from pathlib import Path

import pytest
from forge_factory.afo import line_orders as O
from forge_factory.afo import line_soak_intake as I
from forge_factory.afo import line_soak_prerequisites as P
from forge_factory.afo import qualification as Q
from forge_factory.afo.durable import Refused
from forge_factory.afo.queue import ReadSnapshot, Store, order_id_for
from test_da014_fault_observer import setup  # noqa: F401
from test_da014_operational_work import work  # noqa: F401
from test_da014_qualification import identity
from test_line_conductor_m3 import ORN, PROFILE, REV1, env, lineage, write_campaign  # noqa: F401
from test_line_soak_prerequisites import database_snapshot, pending, ref  # noqa: F401


@pytest.fixture
def planned(pending, monkeypatch):
    from forge_factory.afo import line_campaign as LC
    from forge_factory.afo.line_recovery_product import job_id

    p = pending
    path = write_campaign(p.env, [lineage("crc-later", "CRCL", "20261105-L100")], name="later.yaml", cid="CMP-LATER-1")
    camp = LC.parse(path, require_approval=True)
    lin = camp.lineages[0]
    origin = {**p.descriptor["line_origin"], "campaign_path": str(path)}
    ctlref = p.descriptor["control_ref"]
    policy = O.load_policy(Path(origin["policy_path"]))
    grant = O.verify_grant(policy, now=time.time(), base=Path(origin["auth_base"]), allowed_signers=Path(origin["allowed_signers"]))
    ok, how = O.quality_delivery(lin, p.env["line"])
    assert ok
    order = O.phase_order(lin, "SWE.1", "START", wo=lin.wo("SWE.1"), resume_from=None, provided_from=None,
                          quality_via=(how or None), durable_control=ctlref)
    spec = O.placed_spec(order, camp, grant)
    spec["digest"] = O._digest(spec)
    env = O.envelope_for(order, lin, camp, grant, time.time(), spec["digest"], line_id="local")
    desc = {"schema": I.SCHEMA, "state": "NOT_SUBMITTED", "lineage": lin.key,
            "spec_ref": ref(p.env["tmp"] / "planned-spec.json", spec), "control_ref": ctlref, "line_origin": origin}
    oid = order_id_for("line-local", spec["wo"])
    aid = oid + "-a1"
    binding = {"order_id": oid, "attempt_id": aid, "job_id": job_id(aid), "mission_id": p.control["mission"]["mission_id"],
               "line_intake_identity": I.identity(spec, env, ctlref)}
    doc = {**p.doc, "jobs": {"later": ref(p.env["tmp"] / "planned.json", desc)}}
    index = ref(p.env["tmp"] / "planned-index.json", doc)
    plan = {**p.plan, "prerequisites_ref": index}
    planref = ref(p.env["tmp"] / "planned-plan.json", plan)
    man = Q.freeze("operation-24", p.env["tmp"] / "planned-manifest.json", identity=identity(),
                   inputs=[Path(index["path"]), Path(doc["recovery_policy_ref"]["path"]), Path(planref["path"])],
                   jobs={"later": binding}, model_profile=ORN)
    monkeypatch.setattr(I, "line", lambda plan: p.env["line"])
    p.planned = desc
    p.future_binding, p.future_spec, p.future_env = binding, spec, env
    p.future_campaign, p.future_grant, p.future_policy = camp, grant, policy
    p.future_manifest, p.future_plan, p.future_planref = man, plan, planref
    return p


def admit_planned(p, monkeypatch):
    from forge_factory import workorder
    from forge_factory.afo import line_recovery_product as RP
    from forge_factory.afo import product_job
    from forge_factory.afo.mission_ledger import MissionLedger

    # Normal controller publication + normal submit/admit. No synthetic queued rows.
    specpath = O.supervisor_dir() / "line-orders" / (p.future_spec["wo"] + ".json")
    O._atomic(specpath, O.placed_spec(p.future_spec, p.future_campaign, p.future_grant, placed_at=O._utc(time.time())))
    monkeypatch.setattr(Store, "admit", p.real_admit)
    from test_line_conductor_m3 import placer
    controller = placer(p.env)
    aid, oid = controller._admit(p.store, p.future_env, p.future_campaign, p.future_policy, p.future_grant, None)
    assert (oid, aid) == (p.future_binding["order_id"], p.future_binding["attempt_id"])
    row = p.store.order(oid)
    RP.link_mission(p.store, row, p.control, p.future_spec)
    attempt = next(a for a in p.store.attempts(oid) if a["attempt_id"] == aid)
    before_charge = MissionLedger(p.store).snapshot(p.future_binding["mission_id"])
    monkeypatch.setattr(workorder, "factory_revision", lambda: {"commit": REV1, "dirty": False})
    monkeypatch.setenv("FORGE_AFO_QUEUE_SCOPE", "line-local")
    manifest = {"model": ORN, "profile": PROFILE, "operations_epoch": 1,
                "line_role_authority_ref": p.planned["control_ref"], "line_origin": p.planned["line_origin"]}
    job = product_job.prepare(p.store, row, attempt, "a" * 32, manifest, p.eff)
    assert job["job_id"] == p.future_binding["job_id"]
    return job, row, before_charge


@pytest.mark.parametrize("pending", [{}, {"max_jobs": 0}], indirect=True)
def test_not_submitted_preview_is_pure_and_actual_normal_intake_uses_exact_predicted_identity(planned, monkeypatch):
    from forge_factory.afo import line_recovery as R
    from forge_factory.afo.mission_ledger import MissionLedger

    p = planned
    before = database_snapshot(p.store)
    observed = P.check(p.future_manifest, p.future_plan)
    assert observed["blockers"] == [], observed
    assert observed["jobs"][0]["execution"]["execution_liveness"] == "NOT_SUBMITTED"
    assert observed["jobs"][0]["reservation_performed"] is False
    assert database_snapshot(p.store) == before
    assert p.store.order(p.future_binding["order_id"]) is None  # independently observed baseline absence
    assert P.admission_boundary(p.future_manifest, p.future_plan, observed)["blockers"] == []
    from forge_factory.afo import operational_campaign as campaign
    from forge_factory.afo import soak

    monkeypatch.setattr(Q, "preflight", lambda *a, **kw: {"status": "READY", "blockers": []})
    starts = []
    def append_control(*args):
        import fcntl
        with p.intent.with_suffix(".lock").open("r+") as stream:
            with pytest.raises(BlockingIOError):
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        assert p.store.order(p.future_binding["order_id"]) is None
        starts.append(args)
        return {"scope": "CONTROL append leaf only; no live elapsed-duration evidence"}
    monkeypatch.setattr(soak, "start", append_control)
    started = campaign.start(p.future_manifest, "soak-control-unsubmitted-start", "AUTH-CONTROL")
    assert started["status"] == "STARTED_OBSERVATION_ONLY" and len(starts) == 1
    assert database_snapshot(p.store) == before
    origin = {k: Path(v) for k, v in p.planned["line_origin"].items()}
    with pytest.raises(R.BindingRefused, match="ORDER_ABSENT"):
        R.bind_order(p.store, p.future_binding["order_id"], p.future_binding["attempt_id"], **origin)
    job, row, before_charge = admit_planned(p, monkeypatch)
    assert I.actual_identity(row, job) == p.future_binding["line_intake_identity"]
    actual = MissionLedger(p.store).snapshot(job["mission_id"])
    assert actual["authorization_ref"] == before_charge["authorization_ref"]
    assert actual["limits"] == before_charge["limits"]
    assert actual["attempts"] == before_charge["attempts"] + 1
    assert actual["charged_tokens"] == before_charge["charged_tokens"] + job["reserved_tokens"]
    assert actual["requests"] == 0
    assert actual["jobs"] == before_charge["jobs"] == 0
    # Preview cannot be replayed after actual intake, even if no native request exists.
    assert P.check(p.future_manifest, p.future_plan)["blockers"] == ["LINE_SOAK_PLANNED_INTAKE_ALREADY_EXISTS"]
    assert P.admission_boundary(p.future_manifest, p.future_plan, observed)["blockers"] == ["LINE_SOAK_PLANNED_INTAKE_ALREADY_EXISTS"]


@pytest.mark.parametrize("kind", ["row", "outbox", "mission-link", "job", "execution", "resource", "lifecycle"])
def test_planned_absence_rejects_orphan_history_without_reset(planned, kind):
    p = planned
    b = p.future_binding
    with p.store.tx() as c:
        if kind == "row":
            pass
        elif kind == "outbox":
            c.execute("INSERT INTO afo_commands_outbox(command_id,kind,idempotency_key,order_id,attempt_id,fencing_epoch,payload,state,created_utc) VALUES (?,?,?,?,?,1,'{}','PENDING','CONTROL')", ("x", "DISPATCH", "x", b["order_id"], b["attempt_id"]))
        elif kind == "mission-link":
            c.execute("INSERT INTO afo_mission_orders VALUES (?,?)", (b["order_id"], b["mission_id"]))
        elif kind == "job":
            c.execute("INSERT INTO afo_product_jobs VALUES (?,'{}')", (b["job_id"],))
        elif kind == "execution":
            c.execute("INSERT INTO afo_mission_executions VALUES (?,?, 'PRODUCT','{}')", (b["job_id"], b["mission_id"]))
        elif kind == "resource":
            c.execute("INSERT INTO afo_resource_ownership VALUES ('inference',?,1,'{}')", (b["job_id"],))
        else:
            c.execute("INSERT INTO afo_lifecycle_events(event_id,occurred_utc,type,order_id,attempt_id,record) VALUES ('x','CONTROL','CONTROL',?,?,'{}')", (b["order_id"], b["attempt_id"]))
    if kind == "row":
        p.store.submit(p.future_env, repo=p.future_campaign.root, max_queued=100, approve=lambda e: (True, "CONTROL"))
    before = database_snapshot(p.store)
    result = P.check(p.future_manifest, p.future_plan)
    assert any("INTAKE" in s for s in result["blockers"]), result
    assert database_snapshot(p.store) == before


@pytest.mark.parametrize("field", ["payload_digest", "campaign_sha256", "profile", "control_sha256"])
def test_frozen_binding_cannot_change_same_order_workload(planned, field):
    p = planned
    manifest = copy.deepcopy(p.future_manifest)
    manifest["jobs"]["later"]["line_intake_identity"][field] = "changed"
    before = database_snapshot(p.store)
    assert P.check(manifest, p.future_plan)["blockers"] == ["LINE_SOAK_PLANNED_BINDING_CHANGED"]
    assert database_snapshot(p.store) == before


@pytest.mark.parametrize("action", ["submit_workorder", "launch_workorder"])
def test_planned_missing_submit_scope_refuses_despite_recover_and_launch(planned, action):
    from forge_factory.afo import authz
    p = planned
    path = p.env["tmp"] / "auth/AUTH-T.json"
    value = json.loads(path.read_text())
    value["allowed_actions"].remove(action)
    path.write_text(json.dumps(value))
    authz.sign(path, p.env["key"])
    assert P.check(p.future_manifest, p.future_plan)["blockers"] == ["ORDER_ADMISSION_NOT_AUTHORIZED"]


def test_real_trial_default_requires_actual_row_even_if_proposed_bindings_exist(planned):
    from forge_factory.afo import product_role_trial as T
    p = planned
    # A descriptor is not a runtime admission. No trial resolution shortcut exists.
    with pytest.raises(Refused):
        T.authorized({"path": "not-a-trial", "sha256": "0" * 64},
                     {**p.future_binding, "profile": PROFILE}, p.eff, store=p.store)


@pytest.mark.parametrize("field", [None, "payload_digest", "campaign_sha256", "profile", "control_sha256"])
def test_actual_capture_binds_immutable_intake_not_current_grant(planned, monkeypatch, field):
    from forge_factory.afo import qualification_capture as C

    p = planned
    job, row, _ = admit_planned(p, monkeypatch)
    # Historical capture remains available after current-grant expiry/revocation.
    (p.env["tmp"] / "auth/AUTH-CONTROL.sig").write_text("CONTROL no current authority")
    binding = copy.deepcopy(p.future_binding)
    if field is not None:
        binding["line_intake_identity"][field] = "different-workload-same-oid"
        with pytest.raises(Refused, match="QUALIFICATION_LINE_INTAKE_CHANGED"):
            C.product_observation(p.store, p.future_manifest, "later", binding)
    else:
        observation, _ = C.product_observation(p.store, p.future_manifest, "later", binding)
        assert observation["line_intake_identity"] == binding["line_intake_identity"]
        legacy = {k: v for k, v in binding.items() if k != "line_intake_identity"}
        monkeypatch.setattr(I, "actual_identity", lambda *a: pytest.fail("legacy cannot invoke optional adapter"))
        old, _ = C.product_observation(p.store, p.future_manifest, "later", legacy)
        assert old == {k: v for k, v in observation.items() if k != "line_intake_identity"}


@pytest.mark.parametrize("field", [None, "payload_digest", "campaign_sha256", "profile", "control_sha256"])
def test_independent_work_replay_binds_optional_intake_provenance(work, field):
    from forge_factory.afo import qualification_capture as C
    from forge_factory.afo.durable import digest
    from test_da014_operational_work import audited

    p = work
    ident = {"payload_digest": "a" * 64, "campaign_sha256": "b" * 64, "profile": PROFILE, "control_sha256": "c" * 64}
    p.manifest["jobs"][p.trial]["line_intake_identity"] = ident
    p.observation["manifest_sha256"] = digest(p.manifest)
    p.observation["line_intake_identity"] = copy.deepcopy(ident)
    if field is not None:
        p.observation["line_intake_identity"][field] = "foreign"
    rowref, _, _ = audited(p)
    row = json.loads(Path(rowref["path"]).read_text())
    if field is None:
        assert C.replay_product_row(p.manifest, row)[1] == p.manifest["jobs"][p.trial]
    else:
        with pytest.raises(Refused, match="QUALIFICATION_LINE_INTAKE_CHANGED"):
            C.replay_product_row(p.manifest, row)


@pytest.mark.parametrize("change", ["state", "lineage", "control", "spec", "model"])
def test_planned_descriptor_cannot_invent_approval_or_phase(planned, change):
    p = planned
    descriptor = copy.deepcopy(p.planned)
    if change == "state":
        descriptor["state"] = "QUEUED"
    elif change == "lineage":
        descriptor["lineage"] = "foreign/unsupported"
    elif change == "control":
        descriptor["control_ref"]["sha256"] = "0" * 64
    elif change == "spec":
        descriptor["spec_ref"]["sha256"] = "0" * 64
    else:
        p.future_manifest["model_profile"] = PROFILE  # capture contract is actual model alias, not profile id
    before = database_snapshot(p.store)
    with ReadSnapshot(p.store.path) as reader, pytest.raises((Refused, ValueError)):
        I.check(p.future_manifest, p.future_plan, p.future_binding, descriptor, reader, p.eff)
    assert database_snapshot(p.store) == before


def test_finite_trial_preview_never_satisfies_default_actual_binding(planned):
    from forge_factory.afo import authz
    from forge_factory.afo import product_role_trial as T
    from forge_factory.afo.durable import digest, immutable_json
    from forge_factory.common import state_dir
    from forge_factory.lrtx.profile import load

    p = planned
    prof = load(PROFILE)
    selected = prof["models"]["allowed"][ORN]
    job = {**p.future_binding, "profile": PROFILE, "model": ORN, "factory_revision": {"commit": REV1},
           "model_digest": selected["digest"], "precision": selected["quantization"]}
    ident = p.control["role_capabilities"]["swe1-author"]["identity"]
    # Keep this CONTROL within the base context ceiling; no allocation assertion.
    ident = {**ident, "context_tokens": 32768}
    trial = {"schema": "forge-c/product-role-trial/1", "qualification_only": True,
             "order_ids": [job["order_id"]], "source_revision": REV1, "profile": PROFILE, "model": ORN,
             "deadline_epoch": time.time() + 120, "roles": {"swe1-author": [ident]}, "authorization_ref": "AUTH-TRIAL"}
    sha = digest(trial)
    trialref = {"path": f"afo/product-role-trials/{sha}.json", "sha256": sha}
    immutable_json(state_dir() / trialref["path"], trial)
    signed = json.loads((p.env["tmp"] / "auth/AUTH-CONTROL.json").read_text())
    signed.update(authorization_id="AUTH-TRIAL", signature_ref="AUTH-TRIAL.sig", signed_runbook_ref="qualification-product-014:" + sha)
    path = p.env["tmp"] / "auth/AUTH-TRIAL.json"
    path.write_text(json.dumps(signed))
    authz.sign(path, p.env["key"])
    result = T.authorized(trialref, job, p.eff, store=p.store, proposed_envelope=p.future_env)
    assert result["qualification_only"] is True
    with pytest.raises(Refused, match="TRIAL_BINDING_CHANGED"):
        T.authorized(trialref, job, p.eff, store=p.store)
    with pytest.raises(Refused, match="PROPOSED_INTAKE_CHANGED"):
        T.authorized(trialref, job, p.eff, store=p.store, proposed_envelope={**p.future_env, "request_id": "foreign"})


def test_queued_optional_identity_is_checked_before_stage_start(pending):
    p = pending
    p.manifest["jobs"]["future"]["line_intake_identity"] = {
        "payload_digest": "0" * 64, "campaign_sha256": "0" * 64, "profile": PROFILE, "control_sha256": "0" * 64}
    assert P.check(p.manifest, p.plan)["blockers"] == ["LINE_SOAK_INTAKE_IDENTITY_CHANGED"]


def test_proposed_order_equals_normal_planner_identity(planned):
    from types import SimpleNamespace
    p = planned
    lin = p.future_campaign.lineages[0]
    normal = O.Planner([p.future_campaign], SimpleNamespace(phase_attempts=lambda *a: []), p.env["line"],
                       p.future_policy, time.time(), durable_control=p.planned["control_ref"])
    plan = O.Plan(lin)
    normal.plans[lin.key] = plan
    actual = normal._order(plan, "SWE.1", "START", resume_from=None)
    assert actual == {key: value for key, value in p.future_spec.items()
                      if key not in {"campaign_sha256", "campaign_commit", "campaign_file", "authorization_id", "digest"}}
    assert O._digest(actual) == p.future_spec["digest"]


@pytest.mark.parametrize("artifact", ["workspace", "spec", "run", "launch"])
def test_unsubmitted_preview_refuses_existing_legacy_artifacts_even_without_queue_row(planned, artifact):
    from forge_factory.common import state_dir
    p = planned
    before = database_snapshot(p.store)
    replay = P.check(p.future_manifest, p.future_plan)
    assert replay["blockers"] == []
    wo = p.future_spec["wo"]
    run = p.env["line"].run_worktree(wo)
    path = {"workspace": state_dir() / "workorders" / wo,
            "spec": state_dir() / "supervisor/line-orders" / (wo + ".json"),
            "run": run, "launch": run.parent / ".launch" / wo}[artifact]
    if artifact == "spec":
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("CONTROL old orphan spec")
    else:
        path.mkdir(parents=True)
    assert P.check(p.future_manifest, p.future_plan)["blockers"] == ["LINE_SOAK_PLANNED_INTAKE_ARTIFACT_EXISTS"]
    assert P.admission_boundary(p.future_manifest, p.future_plan, replay)["blockers"] == ["LINE_SOAK_PLANNED_INTAKE_ARTIFACT_EXISTS"]
    assert database_snapshot(p.store) == before
