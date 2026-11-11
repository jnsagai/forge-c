"""Existing durable product lifecycle adapted to immutable M3 phase orders.

One finite mission owns product/planner/maintainer calls. The existing native
execution/request ledger proves quiescence; phase transport is never a repair
verification authority. All runtime actions remain in the external worker.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from ..common import sha256_file, state_dir
from . import line_recovery as R
from . import line_recovery_control as C
from .durable import Refused, canonical, digest, immutable_json
from .execution_lifecycle import Executions
from .mission_ledger import MissionLedger

SCHEMA = "forge-c/line-product-launch/1"


def job_id(attempt_id):
    return "afo-product-" + digest(attempt_id)[:24]


def registered(store, jid):
    with store.tx() as c:
        row = c.execute("SELECT record FROM afo_product_jobs WHERE job_id=?", (jid,)).fetchone()
    if not row:
        raise Refused("LINE_PRODUCT_JOB_UNREGISTERED")
    return json.loads(row[0])


ACTIVE_PARENT = ("SUBMITTED", "QUEUED", "ADMITTED", "RUNNING", "WAITING_RECOVERY", "VALIDATING", "PAUSED",
                 "WAITING_EXTERNAL_CHANGE")


def continuation_parent(store, spec, ledger, control, *, development_mode):
    """The continued order whose mission consumption this order joins, or None for an independently validated frozen
    input. CAPA-223 (SWE2-WWDGL-L44, 2026-11-09): every owner-lane deploy issues a new development control, so a phase
    continuation of an order passed under an earlier deploy was refused CONTROL_CHANGED and no SWE.2 could ever start.
    On the development lane such a parent, once no longer active, is a frozen input like one without a recorded control
    (no continuation link, its historical consumption is never relabelled); an active parent or any other mode refuses."""
    from .line_orders import _load, supervisor_dir

    continuation = spec.get("resume_from")
    parents = [r for r in store.orders() if r["request_id"] == continuation] if continuation else []
    parent = parents[0] if len(parents) == 1 else None
    if parent:
        previous = _load(supervisor_dir() / "line-orders" / (continuation + ".json")) or {}
        if previous.get("durable_control"):
            if previous["durable_control"] != spec["durable_control"]:
                if development_mode and parent.get("state") not in ACTIVE_PARENT:
                    return None
                raise Refused("LINE_PRODUCT_CONTINUATION_CONTROL_CHANGED")
            if ledger.for_order(parent["order_id"]) != control["mission"]["mission_id"]:
                raise Refused("LINE_PRODUCT_CONTINUATION_MISSION_CHANGED")
        else:
            parent = None  # independently validated frozen input, never relabel its historical consumption
    return parent


def _development_mode():
    from . import owner_supervised_development as development
    from .policy import load

    try:
        return load().mode == development.MODE
    except Exception:  # noqa: BLE001 - an unreadable policy is never the development lane
        return False


def link_mission(store, row, control, spec):
    """Register finite authority before the first inference, never import old work as zero usage."""
    from . import owner_supervised_development as development

    ledger = MissionLedger(store)
    parent = continuation_parent(store, spec, ledger, control, development_mode=_development_mode())
    try:
        existing = ledger.for_order(row["order_id"])
    except Refused:
        existing = None
    if existing and existing != control["mission"]["mission_id"]:
        raise Refused("LINE_PRODUCT_MISSION_REBOUND")
    if not existing:
        attempts = store.attempts(row["order_id"])
        if any(a["record"].get("fabro_run_id") or a["state"] not in ("PREPARED", "DISPATCH_PENDING") for a in attempts):
            raise Refused("LINE_PRODUCT_HISTORICAL_ACCOUNTING_REQUIRED")
    # An owner-signed deadline/capacity amendment changes the effective envelope,
    # never the initial registration. Re-registering that envelope would either
    # refuse a valid continuation or rewrite/reset its original authority.
    with store.tx() as c:
        base_row = c.execute("SELECT record FROM afo_missions WHERE mission_id=?",
                             (control["mission"]["mission_id"],)).fetchone()
        if base_row:
            base = json.loads(base_row[0])
            snapshot = MissionLedger._snapshot(c, control["mission"]["mission_id"])
            if base["authorization_ref"] != development.mission_authority(control):
                raise Refused("LINE_PRODUCT_MISSION_AUTHORITY_CHANGED")
            if any(snapshot[k] != control["mission"][k] for k in ("mission_id", "lineage", "limits")):
                raise Refused("LINE_ROLE_SIGNED_MISSION_LIMITS_MISMATCH")
    if not base_row:
        if existing:
            raise Refused("MISSION_NOT_REGISTERED")
        ledger.register(
            **control["mission"],
            authorization_ref=control["authorization_ref"],
            authorize=lambda authority, limits: (
                authority == control["authorization_ref"] and limits == control["mission"]["limits"]
            ),
        )
    if not existing:
        ledger.link(control["mission"]["mission_id"], row["order_id"], continuation_of=parent["order_id"] if parent else None)
    # Effective amendments are checked; initial registration cannot refill a ledger.
    snapshot = ledger.snapshot(control["mission"]["mission_id"])
    if any(snapshot[k] != control["mission"][k] for k in ("mission_id", "lineage", "limits")):
        raise Refused("LINE_ROLE_SIGNED_MISSION_LIMITS_MISMATCH")
    return snapshot


def manifest(store, cmd, worker, spec, eff):
    from .line_recovery_worker import bound_order
    from .local_agent import request_for

    row = store.order(cmd["order_id"])
    bound_order(store, worker)
    control = C.configuration(worker["control_ref"], eff, request=request_for(row))
    if spec["profile"] != control["profile"]:
        raise Refused("LINE_PRODUCT_PROFILE_CHANGED")
    link_mission(store, row, control, spec)
    recovery = spec.get("durable_recovery")
    plan = None
    if recovery:
        from .checkpoints import PHASES, capture, checkpoints, reusable
        from .line_recovery_coordination import continuation

        plan, _ = continuation(store, spec)
        source_ws = state_dir() / "workorders" / recovery["source_work_order"] / "workspace"
        R.context(store, recovery["source_order_id"], recovery["source_attempt_id"], source_ws, worker["line_origin"])
        capture(store, recovery["source_order_id"], recovery["source_attempt_id"], source_ws)
        owner = plan.get("owner_phase") or plan["affected_phase"]
        required = list(PHASES[: PHASES.index(owner)])
        if reusable(checkpoints(store, recovery["source_attempt_id"]))[: len(required)] != required:
            raise Refused("LINE_PRODUCT_REQUIRED_CHECKPOINT_PREFIX_UNAVAILABLE")
        from ..inspection.engine import Store as InspectionStore

        phases = InspectionStore(source_ws)
        current = {p: phases.latest_baseline(p) for p in required}
        recorded = {c["phase"]: c for c in checkpoints(store, recovery["source_attempt_id"])}
        if any(
            phases.gate(p)["decision"] != "PASS" or not current[p] or current[p]["baseline_hash"] != recorded[p]["baseline_hash"]
            for p in required
        ):
            raise Refused("LINE_PRODUCT_CHECKPOINT_CHANGED")
    return {
        "model": spec["run_model"],
        "profile": spec["profile"],
        "line_role_authority_ref": worker["control_ref"],
        "line_origin": worker["line_origin"],
        "recovery_plan": plan,
    }


def launcher(store, cmd, spec, *, cfg=None, launch=None):
    """Existing M2 host launcher, carrying one immutable product execution/nonce."""
    from . import line_launcher as LL
    from .local_agent import LaunchNotStarted

    cfg = cfg or LL.LineConfig.from_env()

    def invoke(man, name, labels):
        job = registered(store, man["durable_binding"]["job_id"])
        if name != spec["wo"]:
            raise LaunchNotStarted(job, Refused("LINE_PRODUCT_WORK_ORDER_CHANGED"))
        root = state_dir() / "supervisor/line-product-launches"
        root.mkdir(parents=True, exist_ok=True)
        value = {
            "schema": SCHEMA,
            "command_id": cmd["command_id"],
            "job_id": job["job_id"],
            "nonce": job["nonce"],
            "binding": man["durable_binding"],
            "labels": labels,
            "source_revision": job["factory_revision"]["commit"],
            "recovery_plan": man.get("recovery_plan"),
            "order": {
                "wo": spec["wo"],
                "model": spec["run_model"],
                "profile": spec["profile"],
                **{k: spec.get(k) for k in ("purpose", "stop_after", "resume_from", "provided_from", "resume_upto")},
                "quality": spec.get("quality") if spec.get("quality_via") == "FLAG" else None,
                **({"rework_context": spec["rework_context"]} if spec.get("rework_context") is not None else {}),
                **({"retry_of": spec["retry_of"]} if spec.get("retry_of") else {}),  # CAPA-209
            },
        }
        path = root / (job["job_id"] + ".json")
        immutable_json(path, value)
        quality = None
        if value["order"]["quality"] is not None:
            quality = str(root / (job["job_id"] + ".quality.json"))
            immutable_json(Path(quality), value["order"]["quality"])
        order = LL.Order(
            rev=job["factory_revision"]["commit"],
            example=spec["example"],
            **{k: value["order"][k] for k in value["order"] if k != "quality"},
            quality_file=quality,
            durable_file=str(path),
            durable_sha256=sha256_file(path),
        )
        result = (launch or LL.launch)(order, cfg)
        if result["outcome"] == "LAUNCHED":
            return {"fabro_run_id": result["fabro_run_id"], "factory_revision": job["factory_revision"]["commit"]}
        # A completed M2 step prior to workorder submission, or the callback's
        # durable refusal, proves no native invocation. Transport/unknown process
        # failures never supply this proof merely because the API is empty.
        ex = Executions(store)
        submit = ex._evidence(job["job_id"], "PRODUCT_NATIVE_SUBMIT_INTENT")
        refusal = ex._evidence(job["job_id"], "PRODUCT_NATIVE_ADMISSION_REFUSAL")
        early = {
            "GPU_LOCK_HELD",
            "RUN_LIVE",
            "STACK_LOCK_HELD",
            "GUARD_FAIL",
            "ORDER_ARGS_INVALID",
            "REV_UNKNOWN",
            "EXAMPLE_UNKNOWN",
            "PROFILE_UNKNOWN",
            "WO_ALREADY_RUN",
            "WORKTREE_PATH_OCCUPIED",
            "WORKTREE_REV_MISMATCH",
            "WORKTREE_ALREADY_LAUNCHED",
            "WORKTREE_NOT_CLEAN",
            "INPUT_OUTSIDE_REPO",
            "INPUT_MISSING",
            "INPUT_HASH_UNKNOWN",
            "INPUT_UNAVAILABLE",
            "WORKTREE_ADD_FAILED",
            "FABRO_API_UNREACHABLE",
            "STACK_STOP_INCOMPLETE",
            "STACK_START_FAILED",
            "STACK_STOP_FAILED",
            "STACK_NOT_HEALTHY",
            "EXPOSE_FAILED",
            "SMOKE_FAIL",
            "QUALITY_FLAG_UNSUPPORTED",
            "DURABLE_EXECUTION_BUSY",
        }
        if not submit and (result["outcome"] in early or (refusal and result["outcome"] == "WORKORDER_LAUNCH_FAILED")):
            raise LaunchNotStarted(job, Refused(result["outcome"]))
        raise RuntimeError("LINE_PRODUCT_NATIVE_OUTCOME_UNKNOWN:" + result["outcome"])

    return invoke


def dispatch(store, cmd, worker, spec, eff, client, *, cfg=None, launch=None):
    from ..fabro.client import FabroUnavailable
    from . import dispatch as D
    from .line_recovery_worker import bound_order

    # Restart adopts only this attempt's original nonce. An unreachable native
    # control plane or an empty listing cannot authorize a replacement execution.
    def view():
        try:
            return client.list_runs(limit=1000)
        except (FabroUnavailable, OSError, ValueError):
            return None

    if cmd["state"] in ("IN_FLIGHT", "UNKNOWN"):
        actions = D.reconcile_inflight(store, view, commands=[cmd])
        return {"status": "RECONCILING_PRODUCT", "actions": actions}
    if cmd["state"] != "PENDING":
        return {"status": "PRODUCT_" + cmd["state"]}
    grant = bound_order(store, worker)["grant"]
    actions = D.dispatch_pending(
        store,
        launcher(store, cmd, spec, cfg=cfg, launch=launch),
        commands=[cmd],
        manifest_loader=lambda row, payload: manifest(store, cmd, worker, spec, eff),
        name_for=lambda row, attempt: spec["wo"],
        decide=lambda request: grant.permit("launch_workorder", request),
    )
    return {"status": "PRODUCT_DISPATCH_STEP", "actions": actions}


def synchronize(store, order, attempt, eff, client):
    from . import checkpoints, product_job

    job = registered(store, job_id(attempt["attempt_id"]))
    product_job.reconcile(store, eff, client, job_ids=[job["job_id"]])
    execution = Executions(store).get(job["job_id"])
    if not execution or execution["resource_lease"] != "RELEASED" or execution["execution_liveness"] != "QUIESCENT":
        return False
    if attempt["state"] in ("SUCCEEDED", "FAILED", "CANCELLED"):
        workspace = Path(job["workspace"])
        checkpoints.capture(store, order["order_id"], attempt["attempt_id"], workspace)
        from .line_orders import _load, supervisor_dir

        spec = _load(supervisor_dir() / "line-orders" / (order["request_id"] + ".json")) or {}
        if spec.get("stop_after") == "SWE.6" and attempt["record"].get("recovery_plan_id"):
            from .completion_receipt import for_plan, verified_attempt

            receipt = for_plan(store, attempt["record"]["recovery_plan_id"])
            if not receipt or receipt["mission_id"] != job["mission_id"]:
                raise Refused("LINE_PRODUCT_VERIFICATION_MISSION_CHANGED")
            verified_attempt(store, attempt, workspace)
    return True


def supervise_existing(store, cmd, value, eff, client, *, quiesce=False):
    from . import local_agent, product_job

    if value["mode"] == "PRODUCT":
        try:
            job = registered(store, job_id(cmd["attempt_id"]))
        except Refused:
            return
        if job.get("line_role_authority_ref") != value["control_ref"] or job.get("line_origin") != value["line_origin"]:
            raise Refused("LINE_PRODUCT_SUPERVISION_BINDING_CHANGED")
        execution = Executions(store).get(job["job_id"])
        if quiesce and execution and execution["resource_lease"] == "HELD":
            Executions(store).revoke(job["job_id"])
            if execution["task_outcome"] == "ACTIVE":
                Executions(store).outcome(job["job_id"], "BLOCKED", "LINE_ADMISSION_CLOSED")
            Executions(store).reconcile(job["job_id"], client, cancel=True)
        product_job.reconcile(store, eff, client, job_ids=[job["job_id"]])
        row = store.order(job["order_id"])
        attempt = next(a for a in store.attempts(job["order_id"]) if a["attempt_id"] == job["attempt_id"])
        synchronize(store, row, attempt, eff, client)
        return
    for job in local_agent.records(store, cmd["order_id"]):
        if job["attempt_id"] != cmd["attempt_id"] or job.get("line_role_authority_ref") != value["control_ref"]:
            continue
        row = store.order(job["order_id"])
        if quiesce or row["state"] not in ("RUNNING", "WAITING_RECOVERY", "WAITING_EXTERNAL_CHANGE"):
            job["deadline_epoch"] = min(job["deadline_epoch"], time.time())
            local_agent.save(store, job)
        if job["state"] in ("PREPARED", "LAUNCHING", "RUNNING"):
            local_agent.poll(store, row, job, eff, client=client)


def bind_native(store, jid):
    """Called after workorder preparation, immediately before native Fabro submission."""
    from ..lrtx.profile import load as load_profile
    from ..lrtx.role_capability import measured_objective, require
    from . import local_agent
    from .line_product_context import capture, request_job
    from .operations import Intent
    from .policy import load
    from .product_role_trial import authorized as authorized_trial

    job = registered(store, jid)
    order = store.order(job["order_id"])
    eff = load()
    control = C.configuration(job["line_role_authority_ref"], eff, request=local_agent.request_for(order))
    C.require_native_transport(job, control=control)
    intent = Intent(control["operations_intent"]).read()
    execution = Executions(store).get(jid)
    if (
        not order
        or order["state"] not in ("ADMITTED", "RUNNING")
        or intent["mode"] != "RUNNING"
        or intent["epoch"] != job.get("operations_epoch")
        or not local_agent.authorized(order, eff, job["model"])
        or eff.sha256 != job["policy_sha256"]
        or not time.time() < job["deadline_epoch"]
        or job["factory_revision"].get("commit") != control["source_revision"]
        or job["factory_revision"].get("dirty") is not False
        or not execution
        or execution["launch_nonce"] != job["nonce"]
        or execution["resource_lease"] != "HELD"
        or execution["admission_state"] != "DISPATCH_INTENT_RECORDED"
        or execution["authorization_state"] != "VALID"
        or execution["task_outcome"] != "ACTIVE"
    ):
        raise Refused("LINE_PRODUCT_NATIVE_ADMISSION_FENCED")
    context = R.context(store, order["order_id"], job["attempt_id"], Path(job["workspace"]), job["line_origin"])
    profile = load_profile(job["profile"])
    # The graph holds every phase; a resumed order acts only in its bound phase.
    reference = capture(Path(job["workspace"]), job, profile, phase=context["phase"])
    candidate = {**job, "line_context_sha256": digest(context), "line_product_context": reference}
    # Every actual role/model needs measured objective proof, or its separately
    # signed finite experiment. No semantic complexity is invented for a phase.
    from .line_product_context import resolve

    frozen, _ = resolve(candidate)
    for role, models in frozen["role_models"].items():
        for model in models:
            selected = request_job(candidate, role, model, eff)
            C.native_envelope_minimum({**selected, "role": role})
            if selected.get("product_role_trial"):
                trial = authorized_trial(selected["product_role_trial"], selected, eff)
                if not any(
                    identity.get("role") == role
                    and identity.get("model_digest") == selected["model_digest"]
                    and identity.get("precision") == selected["precision"]
                    and identity.get("adapter_revision") == job["factory_revision"]["commit"]
                    for identity in trial["roles"].get(role, [])
                ):
                    raise Refused("LINE_PRODUCT_ROLE_TRIAL_UNDECLARED")
            else:
                entry = selected["role_capabilities"].get(role)
                if not entry:
                    raise Refused("CAPABILITY_LIMIT", "product role has no independent capability receipt")
                identity = entry["identity"]
                if (
                    identity["role"] != role
                    or identity["model_digest"] != selected["model_digest"]
                    or identity["precision"] != selected["precision"]
                    or identity["adapter_revision"] != job["factory_revision"]["commit"]
                ):
                    raise Refused("LINE_PRODUCT_ROLE_CAPABILITY_IDENTITY_CHANGED")
                size, work_class = measured_objective(selected, role)
                require(entry["ref"], entry["identity"], semantic_obligations=size, work_class=work_class)
    with store.tx() as c:
        current = json.loads(c.execute("SELECT record FROM afo_product_jobs WHERE job_id=?", (jid,)).fetchone()[0])
        for key in ("line_context_sha256", "line_product_context"):
            if key in current and current[key] != candidate[key]:
                raise Refused("LINE_PRODUCT_NATIVE_CONTEXT_REBOUND")
        current.update({key: candidate[key] for key in ("line_context_sha256", "line_product_context")})
        c.execute("UPDATE afo_product_jobs SET record=? WHERE job_id=?", (canonical(current).decode(), jid))
    if not local_agent.authorized_job(order, eff, current):
        raise Refused("LINE_PRODUCT_NATIVE_AUTHORITY_CHANGED")
    # Actual namespace gateway must advertise the same scope and startup source.
    import urllib.request

    url = f"http://127.0.0.1:{profile['deployment']['ports']['gateway']}/health"
    with urllib.request.urlopen(url, timeout=3) as response:
        health = json.loads(response.read(65537))
    if (
        health.get("afo_queue_scope") != "line-local"
        or (health.get("factory_revision") or {}).get("commit") != job["factory_revision"]["commit"]
        or (health.get("factory_revision") or {}).get("dirty") is not False
    ):
        raise Refused("LINE_PRODUCT_GATEWAY_SCOPE_OR_REVISION_CHANGED")
    if health.get("durable_native_header") is not True:
        raise Refused("LINE_NATIVE_TRANSPORT_GATEWAY_NOT_ENABLED")
    Executions(store)._save_evidence(
        jid,
        "PRODUCT_NATIVE_SUBMIT_INTENT",
        {"job_id": jid, "nonce": job["nonce"], "role_context": reference, "source_revision": control["source_revision"]},
    )
    return current


def payload(path, sha256):
    import re

    from .fault_observer import bound_json

    if (
        not isinstance(path, (str, Path))
        or not Path(path).is_absolute()
        or not isinstance(sha256, str)
        or not re.fullmatch(r"[0-9a-f]{64}", sha256)
    ):
        raise Refused("LINE_PRODUCT_LAUNCH_PAYLOAD_INVALID")
    try:
        value = bound_json({"path": str(path), "sha256": sha256})
    except OSError:
        raise Refused("LINE_PRODUCT_LAUNCH_PAYLOAD_UNAVAILABLE") from None
    required = {"schema", "command_id", "order", "job_id", "nonce", "binding", "labels", "recovery_plan", "source_revision"}
    if not isinstance(value, dict) or set(value) != required or value.get("schema") != SCHEMA:
        raise Refused("LINE_PRODUCT_LAUNCH_PAYLOAD_INVALID")
    if (
        not isinstance(value["binding"], dict)
        or value["binding"].get("job_id") != value["job_id"]
        or value["binding"].get("nonce") != value["nonce"]
        or value["labels"]
        != {"afo_agent": value["job_id"], "afo_nonce": value["nonce"], "afo_attempt": value["binding"].get("attempt_id")}
    ):
        raise Refused("LINE_PRODUCT_LAUNCH_BINDING_CHANGED")
    return value


def order_arguments(order):
    value = {
        key: getattr(order, key)
        for key in ("wo", "model", "profile", "purpose", "stop_after", "resume_from", "provided_from", "resume_upto")
    }
    if getattr(order, "rework_context", None) is not None:
        value["rework_context"] = order.rework_context
    if getattr(order, "retry_of", None):  # CAPA-209
        value["retry_of"] = order.retry_of
    return value


def validate_launch_order(order):
    value = payload(order.durable_file, order.durable_sha256)
    expected = order_arguments(order)
    expected["quality"] = json.loads(Path(order.quality_file).read_text()) if order.quality_file else None
    if value["order"] != expected:
        raise Refused("LINE_PRODUCT_LAUNCH_ARGUMENTS_CHANGED")
    return value


def _job_for_payload(store, value):
    from .line_recovery_worker import bound_order, metadata

    job = registered(store, value["job_id"])
    if (
        job["nonce"] != value["nonce"]
        or job["factory_revision"]["commit"] != value["source_revision"]
        or value["binding"]
        != {
            key: job[key] for key in ("job_id", "nonce", "mission_id", "order_id", "attempt_id", "operations_epoch") if key in job
        }
    ):
        raise Refused("LINE_PRODUCT_REGISTERED_BINDING_CHANGED")
    cmd, worker, spec, row = metadata(store, value["command_id"])
    if value["order"].get("rework_context") != spec.get("rework_context"):
        raise Refused("LINE_PRODUCT_REWORK_CONTEXT_CHANGED")
    if (
        worker["mode"] != "PRODUCT"
        or cmd["attempt_id"] != job["attempt_id"]
        or cmd["order_id"] != job["order_id"]
        or worker["control_ref"] != job["line_role_authority_ref"]
    ):
        raise Refused("LINE_PRODUCT_COMMAND_BINDING_CHANGED")
    bound_order(store, worker)
    return job, row, spec


def claim_for_launch(cfg, order):
    """Exact fresh product dispatch exclusion, before any stack/model preparation."""
    from .line_liveness import KIND, ClaimUncertain, claim
    from .local_agent import LaunchNotStarted, authorized, request_for
    from .operations import Intent
    from .policy import load
    from .queue import Store

    value = validate_launch_order(order)
    store = Store(cfg.stack_root / "state/supervisor/line-queue.sqlite3", must_exist=True)
    job = registered(store, value["job_id"])
    if Executions(store)._evidence(job["job_id"], KIND):
        raise ClaimUncertain("LINE_LOCAL_LAUNCH_ALREADY_CLAIMED")
    try:
        job, row, spec = _job_for_payload(store, value)
        eff = load()
        control = C.configuration(job["line_role_authority_ref"], eff, request=request_for(row))
        C.require_job_binding(job, control, store=store)
        C.require_native_transport(job, cfg=cfg, control=control)
        intent = Intent(control["operations_intent"]).read()
        if (
            row["state"] not in ("ADMITTED", "RUNNING")
            or intent["mode"] != "RUNNING"
            or intent["epoch"] != job.get("operations_epoch")
            or not time.time() < job["deadline_epoch"]
            or not authorized(row, eff, job["model"])
        ):
            raise Refused("LINE_PRODUCT_LAUNCH_AUTHORITY_REFUSED")
        from .line_recovery_worker import bound_order, metadata

        _, worker, _, _ = metadata(store, value["command_id"])
        grant = bound_order(store, worker)["grant"]
        if not grant.permit(
            "launch_workorder",
            {"order_id": spec["wo"], "driver_class": spec["driver_class"], "model": spec["profile"],
             "service_action": "line_stack_restart"},
        ).allow:
            raise Refused("LINE_PRODUCT_STACK_LAUNCH_NOT_AUTHORIZED")
        return claim(cfg, job)
    except ClaimUncertain:
        raise
    except Exception as exc:
        if Executions(store)._evidence(job["job_id"], KIND):
            raise ClaimUncertain("LINE_PRODUCT_LAUNCH_CLAIM_OUTCOME_UNCERTAIN") from exc
        raise LaunchNotStarted(job, exc) from exc


def execution_context(order):
    """Retain the already-signed private intent/policy context; legacy M2 still drops it."""
    from .local_agent import execution_context as role_context
    from .queue import Store

    value = validate_launch_order(order)
    store = Store(state_dir() / "supervisor/line-queue.sqlite3", must_exist=True)
    job, _, _ = _job_for_payload(store, value)
    return {**role_context(job), "FORGE_DURABLE_AUTONOMY": "1", "FORGE_AFO_QUEUE_SCOPE": "line-local",
            "FORGE_OPERATIONS_PROFILE": job["profile"], "FORGE_LINE_STACK_PAYLOAD": str(order.durable_file),
            "FORGE_LINE_STACK_PAYLOAD_SHA256": order.durable_sha256}


def _native_prepare_claim(store, job):
    import os

    from .line_liveness import KIND, ClaimUncertain
    from .line_orders import _proc_start

    claim = Executions(store)._evidence(job["job_id"], KIND)
    if not claim or claim["nonce"] != job["nonce"] or claim["start"] is None or _proc_start(claim["pid"]) != claim["start"]:
        raise Refused("LINE_PRODUCT_LOCAL_LAUNCH_OWNER_NOT_ALIVE")
    value = {"job_id": job["job_id"], "nonce": job["nonce"], "pid": os.getpid(), "start": _proc_start(os.getpid())}
    with store.tx() as c:
        created = c.execute(
            "INSERT OR IGNORE INTO afo_execution_evidence VALUES (?,?,?,?)",
            (job["job_id"], "PRODUCT_NATIVE_PREPARE_CLAIM", canonical(value).decode(), digest(value)),
        ).rowcount
        if not created:
            raise ClaimUncertain("LINE_PRODUCT_NATIVE_PREPARATION_ALREADY_CLAIMED")
    return value


def native_parameters(path, sha256, expected):
    """The workorder CLI's only optional durable input; no model-supplied CLI kwargs."""
    from .queue import Store

    value = payload(path, sha256)
    if value["order"] != expected:
        raise Refused("LINE_PRODUCT_NATIVE_ARGUMENTS_CHANGED")
    if expected.get("rework_context") is not None:
        from ..rework_context import request

        try:
            request(expected["rework_context"], expected.get("stop_after"), expected.get("resume_from"))
        except ValueError:
            raise Refused("LINE_PRODUCT_REWORK_CONTEXT_INVALID") from None
    store = Store(state_dir() / "supervisor/line-queue.sqlite3", must_exist=True)
    job, row, spec = _job_for_payload(store, value)
    _native_prepare_claim(store, job)

    def before_native():
        try:
            bind_native(store, job["job_id"])
        except Exception as exc:
            if not Executions(store)._evidence(job["job_id"], "PRODUCT_NATIVE_SUBMIT_INTENT"):
                Executions(store)._save_evidence(
                    job["job_id"],
                    "PRODUCT_NATIVE_ADMISSION_REFUSAL",
                    {"job_id": job["job_id"], "nonce": job["nonce"],
                     "failure_type": getattr(exc, "code", None) or (str(exc)[:96] if isinstance(exc, R.BindingRefused)
                                                                    else type(exc).__name__)},
                )
            if isinstance(exc, Refused):
                raise
            raise Refused("LINE_PRODUCT_NATIVE_ADMISSION_FAILED", type(exc).__name__) from exc

    return {
        "recovery_plan": value["recovery_plan"],
        "durable_binding": value["binding"],
        "labels": value["labels"],
        "before_native_launch": before_native,
    }
