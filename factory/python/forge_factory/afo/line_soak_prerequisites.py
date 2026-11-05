"""Read-only, stage-scoped admission replay for the existing line soak collector.

A successful replay is a current admission observation, never role competence,
completed fault coverage, or a 24/72/168-hour result. Every eventual effect still
passes its original live guards. Missing/unsupported evidence is not a PASS.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path

from .durable import Refused, digest

SCHEMA = "forge-c/line-soak-prerequisites/1"
LIMIT = 1024 * 1024


def reference(ref, *, decode=True):
    """Bounded, absolute, no symlink components, hash-bound ordinary file."""
    from .durable import strict_json
    from .fault_observer import read_bytes

    if (not isinstance(ref, dict) or set(ref) != {"path", "sha256"}
            or not isinstance(ref["path"], str) or len(ref["path"]) > 4096
            or not re.fullmatch(r"[a-f0-9]{64}", str(ref["sha256"]))):
        raise Refused("LINE_SOAK_REFERENCE_INVALID")
    path = Path(ref["path"])
    if not path.is_absolute() or ".." in path.parts or any(p.is_symlink() for p in (path, *path.parents)):
        raise Refused("LINE_SOAK_REFERENCE_PATH_INVALID")
    raw = read_bytes(path, LIMIT)
    if hashlib.sha256(raw).hexdigest() != ref["sha256"]:
        raise Refused("LINE_SOAK_REFERENCE_CHANGED")
    from .line_soak_snapshot import CURRENT

    if (snapshot := CURRENT.get()) is not None:
        snapshot.observe(ref, raw)
    return strict_json(raw, LIMIT) if decode else raw


def frozen_reference(manifest, ref, *, decode=True):
    if ref not in manifest.get("inputs", []):
        raise Refused("LINE_SOAK_PREREQUISITE_NOT_FROZEN")
    return reference(ref, decode=decode)


def _shape(value, required, code):
    if not isinstance(value, dict) or set(value) != set(required):
        raise Refused(code)


def _roles(job, control, eff, store, required, profile, *, native_output_cap=None, proposed_envelope=None):
    """Actual pinned role/model inventory; no guessed semantic objective or request."""
    from ..lrtx import role_capability as R
    from ..mcp.preflight import preflight as mcp_preflight
    from ..registry.agents import preflight as agents_preflight
    from . import product_role_trial as T

    if (agents_preflight(list(required), include_afo=True)["status"] != "PASS"
            or mcp_preflight(list(required), live=False, include_afo=True)["status"] != "PASS"):
        raise Refused("LINE_SOAK_SKILL_OR_MCP_PREFLIGHT_FAILED")
    rows = []
    for role, models in sorted(required.items()):
        for model in models:
            identity = profile["models"]["allowed"].get(model)
            if not identity:
                raise Refused("LINE_SOAK_ROLE_MODEL_UNDECLARED")
            selected = {**job, "model": model, "model_digest": identity["digest"], "precision": identity["quantization"]}
            if role in ("afo-recovery-planner", "afo-factory-maintainer"):
                from ..lrtx.profile import role_job_tokens
                from ..registry.agents import load_agents

                definition = next(a for a in load_agents(include_afo=True)[0] if a.id == role)
                selected["reserved_tokens"] = role_job_tokens(profile, role, definition.max_stage_tokens)
            minimum = None
            if native_output_cap is not None and role != "afo-recovery-planner":
                from ..llm_gateway import sanitize_request

                effective = sanitize_request({"model": model, "max_tokens": native_output_cap, "messages": []},
                                             policy=(profile.get("gateway") or {}).get("reasoning") or {}, role=role)
                minimum = effective["max_tokens"] + 1  # necessary lower bound, never a full request measurement
                if selected["reserved_tokens"] < minimum:
                    raise Refused("LINE_SOAK_NATIVE_RESERVATION_TOO_SMALL")
            trial_ref = (control.get("product_role_trials") or {}).get(model)
            if not trial_ref and model == job["model"]:
                trial_ref = control.get("product_role_trial")
            if trial_ref:
                from ..common import state_dir
                from .line_soak_snapshot import CURRENT, authority

                trial = T.resolve(trial_ref)
                authority(trial["authorization_ref"])
                if (snapshot := CURRENT.get()) is not None:
                    snapshot.file(state_dir() / trial_ref["path"])
                    snapshot.follow(trial)
                    snapshot.grants.append({"issued_utc": "1970-01-01T00:00:00Z", "expires_utc":
                        datetime.fromtimestamp(trial["deadline_epoch"], UTC).isoformat()})
                trial = T.authorized(trial_ref, selected, eff, store=store,
                                     **({"proposed_envelope": proposed_envelope} if proposed_envelope is not None else {}))
                if not trial["roles"].get(role):
                    raise Refused("LINE_SOAK_TRIAL_ROLE_UNDECLARED")
                if minimum is not None and not any(i["context_tokens"] >= minimum for i in trial["roles"][role]):
                    raise Refused("LINE_SOAK_NATIVE_CONTEXT_TOO_SMALL")
                rows.append({"role": role, "model": model, "qualification_only": True, "qualified": False,
                             "authority_sha256": trial_ref["sha256"]})
                continue
            entry = (control["role_capabilities"] or {}).get(role)
            if not entry or entry.get("identity", {}).get("model_digest") != identity["digest"]:
                alternatives = [a for a in control.get("qualified_local_alternatives", []) if a.get("model_profile") == model]
                entry = ((alternatives[0].get("role_capabilities") or {}).get(role) if len(alternatives) == 1 else None)
            if not entry:
                raise Refused("CAPABILITY_LIMIT", role)
            ident = entry["identity"]
            R.key(ident)
            if minimum is not None and ident["context_tokens"] < minimum:
                raise Refused("LINE_SOAK_NATIVE_CONTEXT_TOO_SMALL")
            if (ident["role"] != role or ident["adapter_revision"] != control["source_revision"]
                    or ident["model_digest"] != identity["digest"] or ident["precision"] != identity["quantization"]):
                raise Refused("LINE_SOAK_ROLE_IDENTITY_CHANGED")
            # A future planner/maintainer case has no semantic objective yet.
            # Check measured class now; dispatch still checks that actual objective.
            if role in ("afo-recovery-planner", "afo-factory-maintainer"):
                size, work_class = None, "PRODUCT_DIAGNOSIS" if role.endswith("planner") else "MAINTENANCE"
            elif job.get("_prospective") is True:
                size, work_class = None, "PRODUCT"
            else:
                size, work_class = R.measured_objective(job, role)
            capability = reference(entry["ref"])
            report = reference(capability["report"])
            for oracle in report["independent_oracle_refs"]:
                reference({k: oracle[k] for k in ("path", "sha256")}, decode=False)
            receipt = R.require(entry["ref"], ident, semantic_obligations=size, work_class=work_class)
            rows.append({"role": role, "model": model, "qualification_only": False,
                         "receipt_sha256": entry["ref"]["sha256"], "envelope": receipt["envelope"]})
    return rows


def _output_cap(measured):
    cap = measured.get("max_tokens") if isinstance(measured, dict) else None
    if type(cap) is not int or not 1 <= cap <= 1048576:
        raise Refused("LINE_SOAK_NATIVE_OUTPUT_MEASUREMENT_REQUIRED")
    return cap


def _auxiliary(job, eff, profile):
    from ..lrtx.profile import role_job_tokens
    from ..registry.agents import load_agents
    from .line_recovery_control import native_envelope_minimum
    from .local_agent import ROLES, enabled

    definitions = {a.id: a for a in load_agents(include_afo=True)[0]}
    roles = {}
    for role in ROLES:
        if not enabled(role, eff):
            continue
        tokens = role_job_tokens(profile, role, definitions[role].max_stage_tokens)
        if tokens > int(eff.get("budgets.max_model_tokens_per_order")):
            raise Refused("RECOVERY_PROFILE_ENVELOPE_EXCEEDS_POLICY")
        native_envelope_minimum({**job, "role": role, "reserved_tokens": tokens})
        if role == "afo-factory-maintainer":
            from ..reliability.isolation import available
            from .line_verifier_guard import require_backend

            require_backend()
            if not available():
                raise Refused("MAINTAINER_SANDBOX_UNAVAILABLE")
        roles[role] = [job["model"]]
    return roles


def _job(manifest, plan, binding, ref, store, eff):
    from ..lrtx.profile import load
    from . import line_recovery_control as C
    from . import local_agent
    from .line_recovery_product import registered
    from .mission_ledger import MissionLedger

    job = reference(ref)
    if not isinstance(job, dict):
        raise Refused("LINE_SOAK_JOB_REFERENCE_INVALID")
    if job.get("schema") == "forge-c/line-soak-planned-intake/1":
        from .line_soak_intake import check

        return check(manifest, plan, binding, job, store, eff)
    if job.get("schema") == "forge-c/line-soak-pending-order/1":
        return _pending(manifest, plan, binding, job, store, eff)
    if any(job.get(k) != binding.get(k) for k in ("job_id", "mission_id", "order_id", "attempt_id")):
        raise Refused("LINE_SOAK_JOB_BINDING_CHANGED")
    # A prepared job is a prospective execution, not a future outcome receipt.
    # Never manufacture registration or import historical consumption at zero.
    if job.get("model") != manifest["model_profile"]:
        raise Refused("LINE_SOAK_JOB_MODEL_CHANGED")
    if registered(store, job["job_id"]) != job:
        raise Refused("LINE_SOAK_JOB_RECORD_CHANGED")
    order = store.order(job["order_id"])
    if not order or not any(a["attempt_id"] == job["attempt_id"] for a in store.attempts(job["order_id"])):
        raise Refused("LINE_SOAK_JOB_ATTEMPT_UNREGISTERED")
    reference(job.get("line_role_authority_ref"))
    from .line_soak_snapshot import authority

    authority(C.read(job.get("line_role_authority_ref"))["authorization_ref"])
    control = C.configuration(job.get("line_role_authority_ref"), eff, request=local_agent.request_for(order))
    if (control["operations_intent"] != plan["intent"] or control["profile"] != plan["line_runtime"]["profile"]
            or control["source_revision"] != manifest["source_revision"]):
        raise Refused("LINE_SOAK_JOB_RUNTIME_CHANGED")
    from .line_soak_snapshot import authority

    authority(control["authorization_ref"])
    C.require_job_binding(job, control, store=store)
    from . import line_recovery

    origin = {k: Path(v) for k, v in job["line_origin"].items()}
    _origin_inputs(origin)
    bound = line_recovery.bind_order(store, job["order_id"], job["attempt_id"], **origin)
    _origin_snapshot(origin, bound)
    if "line_intake_identity" in binding:
        from .line_soak_intake import actual_identity

        if actual_identity(order, job) != binding["line_intake_identity"]:
            raise Refused("LINE_SOAK_INTAKE_IDENTITY_CHANGED")
    if job.get("operations_epoch") != plan["_intent_epoch"]:
        raise Refused("LINE_SOAK_JOB_INTENT_CHANGED")
    mission = MissionLedger(store).snapshot(job["mission_id"])
    if mission["authorization_ref"] != control["authorization_ref"]:
        raise Refused("LINE_SOAK_JOB_MISSION_AUTHORITY_CHANGED")
    if time.time() >= min(mission["limits"]["deadline"], job["deadline_epoch"]):
        raise Refused("LINE_SOAK_JOB_AUTHORITY_EXPIRED")
    spent = {"max_attempts": "attempts", "max_jobs": "jobs", "max_requests": "requests", "max_tokens": "charged_tokens",
             "max_tools": "tools", "max_corrections": "corrections"}
    if mission["unbounded_historical_usage"] or any(mission[v] > mission["limits"][k] for k, v in spent.items()):
        raise Refused("LINE_SOAK_MISSION_ACCOUNTING_UNBOUNDED")
    if mission["requests"] >= mission["limits"]["max_requests"]:
        raise Refused("LINE_SOAK_MISSION_EXHAUSTED")
    with store.tx() as c:
        charge = c.execute("SELECT record FROM afo_mission_executions WHERE mission_id=? AND identity=?",
                           (job["mission_id"], job["job_id"])).fetchone()
    charged = json.loads(charge[0]) if charge else {}
    if charged.get("reserved_tokens") != job["reserved_tokens"] or charged.get("imported"):
        raise Refused("LINE_SOAK_JOB_ACCOUNTING_UNBOUND")
    execution = _execution(store, job)
    phase = bound["spec"]["phase"]
    if phase not in {f"SWE.{n}" for n in range(1, 7)}:
        raise Refused("LINE_SOAK_UNSUPPORTED_PHASE_SCOPE")
    selected_profile = load(job["profile"])
    route = (selected_profile.get("structured") or {}).get("role_models") or {}
    required = {"swe" + phase[-1] + "-" + role: [route.get(role, job["model"])] for role in ("author", "inspector")}
    if phase == "SWE.6":
        required["release-manager"] = [route.get("author", job["model"])]
    # Prospective jobs need the signed immutable phase/model binding, not an
    # execution or future work receipt. When an actual graph exists, replay it;
    # actual native admission independently enforces every graph node at launch.
    if job.get("line_product_context"):
        from .line_product_context import resolve

        context, _ = resolve(job)
        if any(context["role_models"].get(role) != models for role, models in required.items()):
            raise Refused("LINE_SOAK_PRODUCT_ROLE_CONTEXT_CHANGED")
    selected_profile = load(job["profile"])
    required.update(_auxiliary(job, eff, selected_profile))
    measured = C.require_native_transport(job, control=control)
    roles = _roles(job, control, eff, store, required, selected_profile, native_output_cap=_output_cap(measured))
    C.native_envelope_minimum(job)
    return {"job_id": job["job_id"], "roles": roles, "execution": execution,
            "mission": mission, "deadline_epoch": job["deadline_epoch"], "outcome_required_before_start": False}


def _policy_snapshot():
    import os

    import yaml

    from . import policy
    from .line_soak_snapshot import CURRENT

    if (snapshot := CURRENT.get()) is not None:
        raw = snapshot.file(os.environ.get("FORGE_AFO_POLICY") or policy.POLICY_PATH)
        value = yaml.safe_load(raw)
        if isinstance(value, dict) and value.get("authorization_ref"):
            snapshot.authority(value["authorization_ref"])


def _origin_inputs(origin):
    """Capture bounded origin authority BEFORE normal approval/binding validation."""
    from . import authz
    from .line_orders import POLICY_PATH, load_policy
    from .line_soak_snapshot import CURRENT

    if (snapshot := CURRENT.get()) is not None:
        snapshot.file(origin["campaign_path"])
        selected = origin.get("policy_path") or POLICY_PATH
        snapshot.file(selected)
        pol = load_policy(selected)
        snapshot.authority(pol.get("authorization_ref"), base=origin.get("auth_base") or authz.AUTH_DIR,
                           signers=origin.get("allowed_signers") or authz.ALLOWED_SIGNERS)


def _origin_snapshot(origin, bound):
    from . import authz
    from .line_soak_snapshot import CURRENT

    if (snapshot := CURRENT.get()) is not None:
        reference({"path": str(origin["campaign_path"]), "sha256": bound["campaign"].sha256}, decode=False)
        if origin.get("policy_path"):
            snapshot.file(origin["policy_path"])
        snapshot.authority(bound["grant"].authorization_id, base=origin.get("auth_base") or authz.AUTH_DIR,
                           signers=origin.get("allowed_signers") or authz.ALLOWED_SIGNERS)


def _pending(manifest, plan, binding, descriptor, store, eff):
    """A normal queued immutable M3 order, checked without admitting its next attempt.

    No fabricated job row, mission execution, nonce, native ID or outcome is
    inserted. Predicted IDs use Store.admit and product_job's existing identities.
    Actual admission/role request checks remain mandatory after this observation.
    """
    from ..lrtx.profile import load
    from . import line_recovery as R
    from . import line_recovery_control as C
    from . import local_agent as L
    from .line_recovery_product import job_id
    from .mission_ledger import MissionLedger

    _shape(descriptor, {"schema", "order_id", "attempt_seq", "spec_ref", "control_ref", "line_origin"},
           "LINE_SOAK_PENDING_ORDER_INVALID")
    oid, seq = descriptor["order_id"], descriptor["attempt_seq"]
    if type(seq) is not int or not 1 <= seq <= 10000:
        raise Refused("LINE_SOAK_PENDING_SEQUENCE_INVALID")
    aid = f"{oid}-a{seq}"
    row = store.order(oid)
    if not row:
        raise Refused("LINE_SOAK_PENDING_QUEUE_REQUIRED")
    origin = descriptor["line_origin"]
    if not isinstance(origin, dict) or not set(origin) <= R.ORIGIN_KEYS or "campaign_path" not in origin:
        raise Refused("LINE_SOAK_PENDING_ORIGIN_INVALID")
    paths = {k: Path(v) for k, v in origin.items()}
    if any(not p.is_absolute() for p in paths.values()):
        raise Refused("LINE_SOAK_PENDING_ORIGIN_INVALID")
    _origin_inputs(paths)
    bound = R.bind_order(store, oid, aid, prospective_attempt_seq=seq, **paths)
    _origin_snapshot(paths, bound)
    from ..common import state_dir

    spec = reference(descriptor["spec_ref"])
    if (Path(descriptor["spec_ref"]["path"]) != state_dir() / "supervisor/line-orders" / (row["request_id"] + ".json")
            or spec != bound["spec"]):
        raise Refused("LINE_SOAK_PENDING_SPEC_CHANGED")
    if "line_intake_identity" in binding:
        from .line_soak_intake import actual_identity

        observed = actual_identity(row, {"line_role_authority_ref": descriptor["control_ref"], "profile": spec["profile"]})
        if observed != binding["line_intake_identity"]:
            raise Refused("LINE_SOAK_INTAKE_IDENTITY_CHANGED")
    reference(descriptor["control_ref"])
    from .line_soak_snapshot import authority

    authority(C.read(descriptor["control_ref"])["authorization_ref"])
    ctl = C.configuration(descriptor["control_ref"], eff, request=L.request_for(row))

    authority(ctl["authorization_ref"])
    if (spec.get("durable_control") != descriptor["control_ref"] or ctl["operations_intent"] != plan["intent"]
            or ctl["source_revision"] != manifest["source_revision"]
            or ctl["profile_sha256"] != plan["line_runtime"]["profile_sha256"]
            or ctl["profile"] != spec["profile"]):
        raise Refused("LINE_SOAK_PENDING_CONTROL_CHANGED")
    expected = {"job_id": job_id(aid), "order_id": oid, "attempt_id": aid, "mission_id": ctl["mission"]["mission_id"]}
    if {k: v for k, v in binding.items() if k != "line_intake_identity"} != expected:
        raise Refused("LINE_SOAK_PENDING_BINDING_CHANGED")
    ledger = MissionLedger(store)
    snap = ledger.snapshot(expected["mission_id"])
    if (snap["authorization_ref"] != ctl["authorization_ref"]
            or any(snap[k] != ctl["mission"][k] for k in ("mission_id", "lineage", "limits"))):
        raise Refused("LINE_SOAK_PENDING_MISSION_CHANGED")
    # A retry must retain the actual original mission/history, never a new lineage.
    with store.tx() as c:
        link = c.execute("SELECT mission_id FROM afo_mission_orders WHERE order_id=?", (oid,)).fetchone()
        old = c.execute("SELECT 1 FROM afo_product_jobs WHERE job_id=?", (expected["job_id"],)).fetchone()
    if old or (link and link[0] != expected["mission_id"]) or (store.attempts(oid) and not link):
        raise Refused("LINE_SOAK_PENDING_HISTORY_UNBOUND")
    tokens = int(eff.get("budgets.max_model_tokens_per_order"))
    if (time.time() >= snap["limits"]["deadline"] or snap["unbounded_historical_usage"]
            or snap["attempts"] >= snap["limits"]["max_attempts"]
            or snap["charged_tokens"] + tokens > snap["limits"]["max_tokens"]
            or snap["requests"] >= snap["limits"]["max_requests"]):
        raise Refused("LINE_SOAK_PENDING_MISSION_EXHAUSTED")
    profile = load(ctl["profile"])
    model = spec["run_model"]
    if model != manifest["model_profile"]:
        raise Refused("LINE_SOAK_JOB_MODEL_CHANGED")
    selected = profile["models"]["allowed"][model]
    prospective = {**expected, "model": model, "profile": ctl["profile"], "factory_revision": C.revision(),
                   "profile_sha256": ctl["profile_sha256"], "model_digest": selected["digest"],
                   "precision": selected["quantization"], "reserved_tokens": tokens, "_prospective": True,
                   "line_origin": origin}
    phase = spec["phase"]
    if phase not in {f"SWE.{n}" for n in range(1, 7)}:
        raise Refused("LINE_SOAK_UNSUPPORTED_PHASE_SCOPE")
    route = (profile.get("structured") or {}).get("role_models") or {}
    roles = {"swe" + phase[-1] + "-" + role: [route.get(role, model)] for role in ("author", "inspector")}
    if phase == "SWE.6":
        roles["release-manager"] = [route.get("author", model)]
    roles.update(_auxiliary(prospective, eff, profile))
    measured = C.require_native_transport(prospective, control=ctl)
    verified = _roles(prospective, ctl, eff, store, roles, profile, native_output_cap=_output_cap(measured))
    C.native_envelope_minimum(prospective)
    return {"job_id": expected["job_id"], "roles": verified, "mission": snap,
            "execution": {"execution_liveness": "NOT_ADMITTED"}, "prospective": True,
            "reservation_performed": False, "outcome_required_before_start": False,
            "fresh_admission_required": True}


def _execution(store, job):
    from ..fabro.client import FabroClient, load_token
    from .execution_lifecycle import Executions
    from .local_agent import endpoint_for

    ledger = Executions(store)
    execution = ledger.get(job["job_id"])
    if not execution:
        # Explicitly prospective registration must have no observed effects.
        with store.tx() as c:
            requests = c.execute("SELECT 1 FROM afo_request_ledger WHERE job_id=? LIMIT 1", (job["job_id"],)).fetchone()
        if requests or job.get("fabro_run_id") or job.get("state") not in (None, "PREPARED", "LAUNCHING"):
            raise Refused("LINE_SOAK_UNREGISTERED_EXECUTION_HISTORY")
        return {"execution_liveness": "NOT_DISPATCHED", "outcome_required_before_start": False}
    if (execution["mission_id"] != job["mission_id"] or execution["launch_nonce"] != job["nonce"]
            or execution["authorization_state"] != "VALID"
            or execution["execution_liveness"] not in ("NOT_STARTED", "QUIESCENT", "LIVE")
            or execution["identity_state"] in ("UNCONFIRMED", "AMBIGUOUS")):
        raise Refused("LINE_SOAK_EXECUTION_UNKNOWN_OR_UNAUTHORIZED")
    if execution["execution_liveness"] == "NOT_STARTED":
        if (execution["admission_state"] != "RESERVED" or execution["native_run_ids"]
                or ledger._evidence(job["job_id"], "PRODUCT_NATIVE_SUBMIT_INTENT")
                or ledger._evidence(job["job_id"], "LINE_LOCAL_LAUNCH_CLAIM")):
            raise Refused("LINE_SOAK_LAUNCH_OUTCOME_UNCERTAIN")
    elif execution["execution_liveness"] == "QUIESCENT":
        if execution["resource_lease"] != "RELEASED" or not ledger._evidence(job["job_id"], "QUIESCENCE"):
            raise Refused("LINE_SOAK_QUIESCENCE_UNPROVEN")
    else:
        if execution["identity_state"] != "CONFIRMED" or len(execution["native_run_ids"]) != 1:
            raise Refused("LINE_SOAK_NATIVE_IDENTITY_UNCONFIRMED")
        # GET only, not reconcile(): that API writes observations/releases leases.
        try:
            with FabroClient(base_url=endpoint_for(job), token=load_token(job.get("fabro_storage")), timeout=3) as client:
                observation = ledger._observe_native(client, execution["native_run_ids"][0])
            if observation.get("status") != "RUNNING":
                raise Refused("LINE_SOAK_NATIVE_LIVENESS_NOT_CURRENT")
        except (OSError, RuntimeError) as exc:
            raise Refused("LINE_SOAK_NATIVE_LIVENESS_UNKNOWN") from exc
    return execution


def _resources(store, jobs):
    """No listing gap, provider UNKNOWN, or foreign held lease becomes free capacity."""
    known = {j["job_id"] for j in jobs}
    with store.tx() as c:
        requests = c.execute("SELECT job_id,state FROM afo_request_ledger WHERE state!='QUIESCENT'").fetchall()
        held = [json.loads(r[0]) for r in c.execute(
            "SELECT record FROM afo_execution_liveness WHERE json_extract(record,'$.resource_lease')='HELD'")]
        owner = c.execute("SELECT holder,epoch FROM afo_resource_ownership WHERE resource='inference'").fetchone()
    if (len(held) > 1 or (held and (not owner or tuple(owner) != (held[0]["job_id"], held[0]["lease_epoch"])))
            or (owner and owner[0] and not held)):
        raise Refused("LINE_SOAK_INFERENCE_OWNERSHIP_UNKNOWN")
    for record in held:
        previous = next((j["execution"] for j in jobs if j["job_id"] == record["job_id"]), None)
        if not previous:
            raise Refused("LINE_SOAK_FOREIGN_OR_UNKNOWN_EXECUTION")
        keys = ("execution_liveness", "authorization_state", "launch_nonce", "lease_epoch", "identity_state", "admission_state")
        if (record.get("execution_liveness") in ("UNKNOWN", "POSSIBLY_LIVE")
                or any(record.get(key) != previous.get(key) for key in keys)):
            raise Refused("LINE_SOAK_EXECUTION_SNAPSHOT_CHANGED_OR_UNKNOWN")
    live = {j["job_id"] for j in jobs if j["execution"]["execution_liveness"] == "LIVE"}
    if any(r["job_id"] not in known or r["state"] not in ("RESERVED", "ACTIVE")
           or (r["state"] == "ACTIVE" and r["job_id"] not in live) for r in requests):
        raise Refused("LINE_SOAK_PROVIDER_LIVENESS_UNKNOWN")


def _sha(path):
    from ..common import sha256_file

    return sha256_file(path)


def _claims(claims, manifest, store=None):
    """Replay historical claims only when supplied. Stage outcomes are NOT prerequisites."""
    from . import fault_observer as O
    from . import operational_work as W
    from . import qualification as Q

    if not isinstance(claims, list) or len(claims) > 128:
        raise Refused("LINE_SOAK_CLAIMS_UNBOUNDED")
    rows = []
    for claim in claims:
        if not isinstance(claim, dict):
            raise Refused("LINE_SOAK_CLAIM_INVALID")
        if claim.get("kind") == "lesson":
            _shape(claim, {"kind", "record_ref"}, "LINE_SOAK_CLAIM_INVALID")
            from .line_soak_claims import lesson

            rows.append(lesson(claim))
            continue
        if claim.get("kind") == "maintenance":
            _shape(claim, {"kind", "job_id", "proposal_id", "decision_ref"}, "LINE_SOAK_CLAIM_INVALID")
            if store is None:
                raise Refused("LINE_SOAK_CLAIM_STORE_REQUIRED")
            from .line_soak_claims import maintenance

            rows.append(maintenance(claim, manifest, store))
            continue
        _shape(claim, {"kind", "manifest_ref", "record_ref"}, "LINE_SOAK_CLAIM_INVALID")
        source = reference(claim["manifest_ref"])
        Q.validate(source)
        if source["source_revision"] != manifest["source_revision"] or source["model_profile"] != manifest["model_profile"]:
            raise Refused("LINE_SOAK_CLAIM_SCOPE_CHANGED")
        record = reference(claim["record_ref"])
        if claim["kind"] == "fault":
            actual = O.verify(source, record)
        elif claim["kind"] == "work":
            actual = W.verify(source, record)
        else:
            raise Refused("LINE_SOAK_UNSUPPORTED_CLAIM")
        rows.append({"kind": claim["kind"], "record_sha256": digest(actual)})
    return rows


def require(manifest, plan, *, purpose="admission"):
    from ..reliability import policy as cre_policy
    from . import policy
    from .operations import Intent
    from .queue import ReadSnapshot

    ref = plan.get("prerequisites_ref")
    if not ref:
        raise Refused("LINE_AUTONOMY_PREREQUISITES_NOT_QUALIFIED")
    doc = frozen_reference(manifest, ref)
    _shape(doc, {"schema", "source_revision", "profile_sha256", "intent_epoch", "jobs", "recovery_policy_ref", "claims"},
           "LINE_SOAK_PREREQUISITES_INVALID")
    if (doc["schema"] != SCHEMA or doc["source_revision"] != manifest["source_revision"]
            or doc["profile_sha256"] != plan["line_runtime"]["profile_sha256"]
            or type(doc["intent_epoch"]) is not int):
        raise Refused("LINE_SOAK_PREREQUISITE_SCOPE_CHANGED")
    intent = Intent(plan["intent"]).read()
    if purpose not in ("admission", "fault"):
        raise Refused("LINE_SOAK_REPLAY_PURPOSE_INVALID")
    if intent["mode"] != "RUNNING" or (purpose == "admission" and intent["epoch"] != doc["intent_epoch"]):
        raise Refused("LINE_SOAK_INTENT_CHANGED_OR_NOT_RUNNING")
    # A real existing CRE operational recipe, not a flag claiming M5 completion.
    policy_ref = doc["recovery_policy_ref"]
    frozen_reference(manifest, policy_ref, decode=False)  # normal YAML policy validation below
    selected = cre_policy.selected_path()
    if Path(policy_ref["path"]) != selected or _sha(selected) != policy_ref["sha256"]:
        raise Refused("LINE_SOAK_OPERATIONAL_POLICY_CHANGED")
    if not cre_policy.load().automatic_action_allowed("restart_conductor"):
        raise Refused("LINE_SOAK_RESTART_RECIPE_NOT_AUTHORIZED")
    if purpose == "fault":
        import os

        from .line_soak_snapshot import CURRENT

        _policy_snapshot()
        eff = policy.load()
        if (snapshot := CURRENT.get()) is not None:
            snapshot.epoch = intent["epoch"]
            snapshot.policy = (eff.mode, eff.sha256, eff.get("authorization_ref"))
            snapshot.file(os.environ.get("FORGE_AFO_POLICY") or policy.POLICY_PATH)
            snapshot.authority(eff.get("authorization_ref"))
        return {"status": "CURRENT_OPERATIONAL_RECIPE_REPLAYED", "intent_epoch": intent["epoch"],
                "effects_performed": False, "role_qualification_inferred": False}
    if (not isinstance(doc["jobs"], dict) or not doc["jobs"] or len(doc["jobs"]) > 32
            or set(doc["jobs"]) != set(manifest["jobs"])):
        raise Refused("LINE_SOAK_JOB_INVENTORY_CHANGED")
    _policy_snapshot()
    eff = policy.load()
    import os

    from .line_soak_snapshot import CURRENT

    if (snapshot := CURRENT.get()) is not None:
        snapshot.epoch = intent["epoch"]
        snapshot.policy = (eff.mode, eff.sha256, eff.get("authorization_ref"))
        snapshot.file(os.environ.get("FORGE_AFO_POLICY") or policy.POLICY_PATH)
        snapshot.authority(eff.get("authorization_ref"))
        snapshot.follow(doc)
        snapshot.follow(manifest["inputs"])
    plan = {**plan, "_intent_epoch": doc["intent_epoch"]}
    jobs = []
    with ReadSnapshot(plan["database"], max_rows=plan["max_rows"], timeout_s=3) as store:
        for key, binding in sorted(manifest["jobs"].items()):
            jobs.append(_job(manifest, plan, binding, doc["jobs"][key], store, eff))
        _resources(store, jobs)
        claims = _claims(doc["claims"], manifest, store)
    from ..common import utc_now

    return {"status": "CURRENT_STAGE_PREREQUISITES_REPLAYED", "jobs": jobs, "claims": claims,
            "claims_scope": "REPLAY_TIME_OBSERVATIONS_NOT_CURRENT_AUTHORITY", "claims_replayed_utc": utc_now(),
            "live_campaign": "NOT_RUN", "role_qualification_inferred": False, "effects_performed": False,
            "completed_cohorts_required": False}


def check(manifest, plan, *, purpose="admission"):
    """Public projection is JSON; only the internal Replay instance can fence an effect."""
    from .line_soak_snapshot import CURRENT, Replay
    from .maintainer import MaintainerDenied

    replay = Replay(manifest, plan)
    token = CURRENT.set(replay)
    try:
        replay.update({"blockers": [], **require(manifest, plan, purpose=purpose)})
        return replay
    except (OSError, ValueError, KeyError, TypeError, sqlite3.Error, subprocess.SubprocessError, MaintainerDenied) as exc:
        code = exc.code if isinstance(exc, (Refused, MaintainerDenied)) else "LINE_SOAK_EVIDENCE_UNAVAILABLE"
        return {"status": "BLOCKED", "blockers": [code],
                "live_campaign": "NOT_RUN", "effects_performed": False}
    finally:
        CURRENT.reset(token)


def admission_boundary(manifest, plan, snapshot, *, fault=False):
    """Small current fence only. All expensive proof verification ran BEFORE Intent.lock."""
    from .line_soak_snapshot import Replay
    from .mission_ledger import MissionLedger
    from .operations import Intent
    from .queue import ReadSnapshot

    try:
        if not isinstance(snapshot, Replay) or snapshot.get("blockers"):
            raise Refused("LINE_SOAK_INTERNAL_REPLAY_SNAPSHOT_REQUIRED")
        snapshot.fence(manifest, plan)
        if current_source() != {"commit": manifest["source_revision"], "dirty": False}:
            raise Refused("LINE_SOAK_BOUNDARY_SOURCE_CHANGED")
        from .operations import path

        if str(path()) != plan["intent"]:
            raise Refused("LINE_SOAK_BOUNDARY_INTENT_CONTEXT_CHANGED")
        current = Intent(plan["intent"]).read()
        if current["mode"] != "RUNNING" or current["epoch"] != snapshot.epoch:
            raise Refused("LINE_SOAK_INTENT_CHANGED_OR_NOT_RUNNING")
        deadlines = []
        if not fault:
            with ReadSnapshot(plan["database"], max_rows=plan["max_rows"], timeout_s=3) as reader:
                for job in snapshot["jobs"]:
                    if job.get("planned_intake"):
                        from .line_soak_intake import absent

                        absent(reader, job["planned_intake"])
                    prior = job["mission"]
                    mission = MissionLedger(reader).snapshot(prior["mission_id"])
                    if any(mission[k] != prior[k] for k in ("authorization_ref", "limits", "lineage")):
                        raise Refused("LINE_SOAK_BOUNDARY_MISSION_CHANGED")
                    if mission["unbounded_historical_usage"]:
                        raise Refused("HISTORICAL_USAGE_REQUIRES_INDEPENDENT_BOUND")
                    deadline = min(mission["limits"]["deadline"], job.get("deadline_epoch", mission["limits"]["deadline"]))
                    deadlines.append(deadline)
                    if time.time() >= deadline:
                        raise Refused("LINE_SOAK_START_AUTHORITY_EXPIRED")
                    maxima = {"attempts": "max_attempts", "jobs": "max_jobs", "requests": "max_requests", "tools": "max_tools",
                              "corrections": "max_corrections", "charged_tokens": "max_tokens"}
                    for field, limit in maxima.items():
                        if mission[field] < prior[field] or mission[field] > mission["limits"][limit]:
                            raise Refused("LINE_SOAK_MISSION_HISTORY_RESET_OR_EXHAUSTED")
                _resources(reader, snapshot["jobs"])
        snapshot.time_fence(deadlines)
        return {"blockers": [], "status": "CURRENT_START_AUTHORITY", "effects_performed": False}
    except (OSError, ValueError, KeyError, TypeError, sqlite3.Error, subprocess.SubprocessError) as exc:
        return {"status": "BLOCKED", "blockers": [exc.code if isinstance(exc, Refused) else "LINE_SOAK_EVIDENCE_UNAVAILABLE"]}


def current_source():
    from ..common import REPO_ROOT

    def git(*args):
        return subprocess.run(["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, check=True, timeout=2).stdout.strip()
    return {"commit": git("rev-parse", "HEAD"), "dirty": bool(git("status", "--porcelain", "--untracked-files=no"))}


def line_plan_reference(manifest, requested=None):
    """Recognize existing frozen typed inputs, including callers omitting --observer-plan.

    Unrelated generic primary inputs retain their existing interpretation. A
    recognized line descriptor can never silently choose a generic effect route.
    """
    from . import fault_observer as O

    plans, typed = [], False
    for ref in manifest.get("inputs", []):
        if Path(ref.get("path", "")).suffix != ".json":
            continue
        try:
            candidate = O.bound_json(ref)
        except Refused as exc:
            if exc.code in ("INVALID_JSON", "OBSERVER_ARTIFACT_NOT_BOUNDED_REGULAR_FILE"):
                continue
            raise
        if isinstance(candidate, dict) and candidate.get("schema") == SCHEMA:
            typed = True
        if (isinstance(candidate, dict) and candidate.get("schema") == "forge-c/operational-observer-plan/1"
                and "line_runtime" in candidate):
            plans.append(ref)
    if len(plans) > 1:
        raise Refused("LINE_SOAK_FAULT_PLAN_AMBIGUOUS")
    if not plans:
        if typed:
            raise Refused("LINE_SOAK_FROZEN_RUNTIME_REQUIRED")
        return requested
    if requested is not None and requested != plans[0]:
        raise Refused("LINE_SOAK_OBSERVER_PLAN_MISMATCH")
    return plans[0]


def fault_target(manifest, observer_plan_ref=None):
    """Infer only an already frozen line observer; never accept a caller-selected unit."""
    from . import fault_observer as O
    from .operations import UNIT, path

    selected = line_plan_reference(manifest, observer_plan_ref)
    if selected is None:
        return None
    plan = O.plan(manifest, selected)
    if "line_runtime" not in plan:
        return None
    if UNIT != plan["unit"] or str(path()) != plan["intent"]:
        raise Refused("LINE_SOAK_FAULT_TARGET_MISMATCH")
    require(manifest, plan, purpose="fault")
    return plan
