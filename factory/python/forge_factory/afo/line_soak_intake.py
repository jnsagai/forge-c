"""Read-only prospective intake for an approved independent first SWE.1 order.

This descriptor is neither a queue row nor an admission receipt. Proposed intake
UTC is not an observed future timestamp. Later intake/dispatch uses the ordinary
Store/Placer/worker path and rechecks authority, accounting and resource guards.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path

from ..common import state_dir
from .durable import Refused

SCHEMA = "forge-c/line-soak-planned-intake/1"


def line(plan):
    from . import line_launcher as LL
    from . import line_orders as O

    runtime = plan["line_runtime"]
    cfg = LL.LineConfig.from_env(launch_dir=runtime["launch_dir"], fabro_host_port=runtime["fabro_host_port"])
    if cfg.stack_root / "state" != state_dir():
        raise Refused("LINE_SOAK_INTAKE_LAYOUT_CHANGED")
    return O.RealLine(cfg)


def validate_identity(value):
    if (not isinstance(value, dict)
            or set(value) != {"payload_digest", "campaign_sha256", "profile", "control_sha256"}
            or not isinstance(value["profile"], str) or not re.fullmatch(r"[a-z0-9][a-z0-9.-]{0,120}", value["profile"])
            or any(not isinstance(value[k], str) or not re.fullmatch(r"[a-f0-9]{64}", value[k])
                   for k in ("payload_digest", "campaign_sha256", "control_sha256"))):
        raise Refused("LINE_SOAK_INTAKE_IDENTITY_INVALID")
    return value


def identity(spec, envelope, control_ref):
    from .line_orders import _digest

    result = {"payload_digest": _digest(spec), "campaign_sha256": spec.get("campaign_sha256"),
              "profile": spec.get("profile"), "control_sha256": control_ref.get("sha256")}
    if (spec.get("digest") != result["payload_digest"] or envelope.get("payload_digest") != result["payload_digest"]
            or envelope.get("manifest_sha256") != result["campaign_sha256"]
            or envelope.get("model_profile") != result["profile"] or spec.get("durable_control") != control_ref):
        raise Refused("LINE_SOAK_INTAKE_IDENTITY_CHANGED")
    return validate_identity(result)


def actual_identity(order, job):
    """Historical capture: immutable persisted inputs only, never current grant authorization."""
    from .line_soak_prerequisites import reference

    env = json.loads(order["envelope"])
    wo = env.get("request_id")
    if not isinstance(wo, str) or Path(wo).name != wo:
        raise Refused("LINE_SOAK_INTAKE_IDENTITY_CHANGED")
    path = state_dir() / "supervisor/line-orders" / (wo + ".json")
    from ..common import sha256_file

    spec = reference({"path": str(path), "sha256": sha256_file(path)})
    control_ref = job.get("line_role_authority_ref")
    reference(control_ref)
    if (order["manifest_sha256"] != env.get("manifest_sha256")
            or order["input_manifest_ref"] != env.get("input_manifest_ref")
            or spec.get("campaign_file") != env.get("input_manifest_ref")
            or job.get("profile") != spec.get("profile")):
        raise Refused("LINE_SOAK_INTAKE_IDENTITY_CHANGED")
    return identity(spec, env, control_ref)


def absent(store, predicted):
    """Reject actual intake AND orphan historical ownership; never synthesize zero state."""
    oid, aid, jid = (predicted[k] for k in ("order_id", "attempt_id", "job_id"))
    if store.order(oid) or store.attempts(oid):
        raise Refused("LINE_SOAK_PLANNED_INTAKE_ALREADY_EXISTS")
    for path in predicted.get("absence_paths", []):
        if Path(path).exists() or Path(path).is_symlink():
            raise Refused("LINE_SOAK_PLANNED_INTAKE_ARTIFACT_EXISTS")
    checks = (
        ("afo_work_orders", "order_id=? OR (tenant_scope='line-local' AND request_id=?)", (oid, predicted["work_order"])),
        ("afo_attempts", "order_id=? OR attempt_id=?", (oid, aid)),
        ("afo_commands_outbox", "order_id=? OR attempt_id=?", (oid, aid)),
        ("afo_lifecycle_events", "order_id=? OR attempt_id=?", (oid, aid)),
        ("afo_mission_orders", "order_id=?", (oid,)),
        ("afo_product_jobs", "job_id=?", (jid,)),
        ("afo_local_agent_jobs", "order_id=? OR attempt_id=? OR job_id=?", (oid, aid, jid)),
        ("afo_mission_executions", "identity=?", (jid,)),
        ("afo_request_ledger", "job_id=?", (jid,)),
        ("afo_execution_liveness", "job_id=?", (jid,)),
        ("afo_execution_evidence", "job_id=?", (jid,)),
        ("afo_resource_ownership", "holder=?", (jid,)),
        ("afo_mission_counters", "job_id=?", (jid,)),
        ("afo_semantic_proposals", "job_id=?", (jid,)),
        ("afo_durable_effects", "job_id=?", (jid,)),
        ("afo_completion_receipts", "json_extract(record,'$.job_id')=?", (jid,)),
    )
    with store.tx() as c:
        for table, where, args in checks:
            if c.execute(f"SELECT 1 FROM {table} WHERE {where} LIMIT 1", args).fetchone():  # noqa: S608 - fixed local table/SQL literals only
                raise Refused("LINE_SOAK_PLANNED_INTAKE_HISTORY_EXISTS")


def prepare_inputs(descriptor, plan):
    """Canonical pure normal spec/envelope intersection; no queue or accounting writes."""
    from . import line_campaign as LC
    from . import line_orders as O
    from . import line_recovery as R
    from .line_soak_prerequisites import _origin_inputs, _origin_snapshot, _shape, reference
    from .queue import QueueError, validate_intake

    _shape(descriptor, {"schema", "state", "lineage", "spec_ref", "control_ref", "line_origin"},
           "LINE_SOAK_PLANNED_INTAKE_INVALID")
    if descriptor["schema"] != SCHEMA or descriptor["state"] != "NOT_SUBMITTED":
        raise Refused("LINE_SOAK_PLANNED_INTAKE_INVALID")
    origin = descriptor["line_origin"]
    if not isinstance(origin, dict) or not set(origin) <= R.ORIGIN_KEYS or "campaign_path" not in origin:
        raise Refused("LINE_SOAK_PENDING_ORIGIN_INVALID")
    paths = {k: Path(v) for k, v in origin.items()}
    if any(not p.is_absolute() for p in paths.values()):
        raise Refused("LINE_SOAK_PENDING_ORIGIN_INVALID")
    _origin_inputs(paths)
    camp = LC.parse(paths["campaign_path"], require_approval=True)
    candidates = [a for a in camp.lineages if a.key == descriptor["lineage"]]
    if len(candidates) != 1:
        raise Refused("LINE_SOAK_PLANNED_LINEAGE_CHANGED")
    lin = candidates[0]
    # Unknown future dependencies/upstream evidence cannot be invented. Existing
    # registered/QUEUED phase1..6 paths remain supported by their original readers.
    if (lin.status != "ACTIVE" or not lin.phases or lin.phases[0] != "SWE.1"
            or lin.start or lin.provided_from or lin.depends_on or camp.line != "local"):
        raise Refused("LINE_SOAK_PLANNED_INTAKE_TYPE_UNSUPPORTED")
    policy = O.load_policy(paths.get("policy_path"))
    grant = O.verify_grant(policy, now=time.time(), base=paths.get("auth_base"),
                           allowed_signers=paths.get("allowed_signers"))
    if not grant.allow:
        raise Refused("LINE_SOAK_PLANNED_LINE_AUTHORITY_REFUSED")
    backend = line(plan)
    ok, how = O.quality_delivery(lin, backend)
    if not ok or not backend.resolve(lin.factory_revision):
        raise Refused("LINE_SOAK_PLANNED_SOURCE_OR_QUALITY_UNAVAILABLE")
    order = O.phase_order(lin, "SWE.1", "START", wo=lin.wo("SWE.1"), resume_from=None,
                          provided_from=None, quality_via=(how or None), durable_control=descriptor["control_ref"])
    expected = O.placed_spec(order, camp, grant)
    expected["digest"] = O._digest(expected)
    spec = reference(descriptor["spec_ref"])
    if spec != expected:
        raise Refused("LINE_SOAK_PLANNED_SPEC_CHANGED")
    env = O.envelope_for(order, lin, camp, grant, time.time(), expected["digest"], line_id="local")
    oid = validate_intake(env, repo=camp.root, approve=lambda e: (True, "CAMPAIGN_APPROVED"))
    bound = R.bind_inputs(spec, env, **paths)
    try:
        O.Placer._check_admission_scope(env, bound["grant"], submit=True)
    except QueueError as exc:
        raise Refused(exc.code) from exc
    _origin_snapshot(paths, bound)
    return spec, env, bound, oid


def check(manifest, plan, binding, descriptor, store, eff):
    from ..lrtx.profile import load
    from . import line_recovery_control as C
    from . import line_soak_prerequisites as P
    from .line_recovery_product import job_id
    from .line_soak_snapshot import authority

    spec, env, bound, oid = prepare_inputs(descriptor, plan)
    predicted = {"order_id": oid, "attempt_id": oid + "-a1", "job_id": job_id(oid + "-a1"),
                 "work_order": spec["wo"]}
    worktree = line(plan).run_worktree(spec["wo"])
    predicted["absence_paths"] = [str(state_dir() / "workorders" / spec["wo"]),
        str(state_dir() / "supervisor/line-orders" / (spec["wo"] + ".json")),
        str(worktree), str(worktree.parent / ".launch" / spec["wo"])]
    absent(store, predicted)
    P.reference(descriptor["control_ref"])
    authority(C.read(descriptor["control_ref"])["authorization_ref"])
    request = {"order_id": env["request_id"], "model": env["model_profile"], "driver_class": env["driver_class"]}
    ctl = C.configuration(descriptor["control_ref"], eff, request=request)
    authority(ctl["authorization_ref"])
    expected = {k: v for k, v in predicted.items() if k not in {"work_order", "absence_paths"}}
    expected["mission_id"] = ctl["mission"]["mission_id"]
    expected["line_intake_identity"] = identity(spec, env, descriptor["control_ref"])
    if binding != expected:
        raise Refused("LINE_SOAK_PLANNED_BINDING_CHANGED")
    if (ctl["operations_intent"] != plan["intent"] or ctl["source_revision"] != manifest["source_revision"]
            or ctl["source_revision"] != line(plan).resolve(spec["revision"])
            or ctl["profile"] != spec["profile"] or ctl["profile_sha256"] != plan["line_runtime"]["profile_sha256"]
            or spec["run_model"] != manifest["model_profile"]):
        raise Refused("LINE_SOAK_PLANNED_CONTROL_CHANGED")
    snap = P.bound_mission(store, ctl)
    tokens = int(eff.get("budgets.max_model_tokens_per_order"))
    if (time.time() >= snap["limits"]["deadline"] or snap["unbounded_historical_usage"]
            or snap["attempts"] >= snap["limits"]["max_attempts"]
            or snap["charged_tokens"] + tokens > snap["limits"]["max_tokens"]
            or snap["requests"] >= snap["limits"]["max_requests"]):
        raise Refused("LINE_SOAK_PENDING_MISSION_EXHAUSTED")
    profile = load(ctl["profile"])
    selected = profile["models"]["allowed"][spec["run_model"]]
    prospective = {**expected, "model": spec["run_model"], "profile": ctl["profile"], "factory_revision": C.revision(),
                   "profile_sha256": ctl["profile_sha256"], "model_digest": selected["digest"],
                   "precision": selected["quantization"], "reserved_tokens": tokens, "_prospective": True,
                   "line_origin": descriptor["line_origin"]}
    route = (profile.get("structured") or {}).get("role_models") or {}
    roles = {"swe1-" + r: [route.get(r, spec["run_model"])] for r in ("author", "inspector")}
    roles.update(P._auxiliary(prospective, eff, profile))
    measured = C.require_native_transport(prospective, control=ctl)
    verified = P._roles(prospective, ctl, eff, store, roles, profile,
                        native_output_cap=P._output_cap(measured), proposed_envelope=env)
    C.native_envelope_minimum(prospective)
    return {"job_id": predicted["job_id"], "roles": verified, "mission": snap, "planned_intake": predicted,
            "execution": {"execution_liveness": "NOT_SUBMITTED"}, "prospective": True,
            "reservation_performed": False, "outcome_required_before_start": False,
            "fresh_intake_and_admission_required": True}
