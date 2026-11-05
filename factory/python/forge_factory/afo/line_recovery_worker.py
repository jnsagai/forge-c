"""One persisted M3 outbox step outside the healthy conductor cycle.

Bootstrap prepares/reuses the exact immutable campaign run checkout, then execs
that checkout. The existing outbox, role jobs, receipts and mission ledger own
progress; this process adds no scheduler or independent accounting database.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import re
from contextlib import contextmanager
from pathlib import Path

from ..common import state_dir
from . import line_launcher as LL
from . import line_recovery as R
from . import line_recovery_control as C
from . import line_recovery_coordination as K
from .durable import Refused, digest
from .queue import Store


def metadata(store, cid):
    cmd = K.command(store, cid)
    value = json.loads(cmd["payload"]).get("line_worker")
    required = {"schema", "mode", "order_id", "attempt_id", "spec_ref", "control_ref", "line_origin"}
    if (
        not isinstance(value, dict)
        or set(value) != required
        or value.get("schema") != K.REQUEST_SCHEMA
        or value.get("mode") not in ("PRODUCT", "REPLAN")
        or value["order_id"] != cmd["order_id"]
        or value["attempt_id"] != cmd["attempt_id"]
        or cmd["kind"] != ("FABRO_LAUNCH" if value["mode"] == "PRODUCT" else "REPLAN")
    ):
        raise Refused("LINE_RECOVERY_WORKER_COMMAND_INVALID")
    from .fault_observer import bound_json

    spec = bound_json(value["spec_ref"])
    row = store.order(value["order_id"])
    expected = state_dir() / "supervisor/line-orders" / ((row or {}).get("request_id", "") + ".json")
    if (
        not row
        or Path(value["spec_ref"]["path"]).resolve() != expected.resolve()
        or not _work_order(spec.get("wo"))
        or spec.get("wo") != row["request_id"]
        or spec.get("durable_control") != value["control_ref"]
    ):
        raise Refused("LINE_RECOVERY_WORKER_SPEC_CHANGED")
    from .line_orders import ORDER_SCHEMA, _digest

    envelope = json.loads(row["envelope"])
    if (
        spec.get("schema") != ORDER_SCHEMA
        or spec.get("digest") != _digest(spec)
        or spec["digest"] != envelope.get("payload_digest")
    ):
        raise Refused("LINE_RECOVERY_WORKER_SPEC_CHANGED")
    if not isinstance(value["line_origin"], dict) or not set(value["line_origin"]) <= R.ORIGIN_KEYS:
        raise Refused("LINE_RECOVERY_WORKER_ORIGIN_INVALID")
    return cmd, value, spec, row


def _work_order(value):
    from .line_campaign import RX

    return isinstance(value, str) and RX["wo"].fullmatch(value)


def existing_job(store, value):
    """Only the registered job belonging to this exact frozen worker request."""
    with store.tx() as c:
        if value["mode"] == "PRODUCT":
            jid = "afo-product-" + digest(value["attempt_id"])[:24]
            rows = c.execute("SELECT record FROM afo_product_jobs WHERE job_id=?", (jid,)).fetchall()
        else:
            rows = c.execute(
                "SELECT record FROM afo_local_agent_jobs WHERE order_id=? AND attempt_id=?",
                (value["order_id"], value["attempt_id"]),
            ).fetchall()
    jobs = [json.loads(r[0]) for r in rows]
    if len(jobs) > 1:
        from .execution_lifecycle import Executions

        held = [j for j in jobs if (Executions(store).get(j["job_id"]) or {}).get("resource_lease") == "HELD"]
        if len(held) > 1:
            raise Refused("LINE_RECOVERY_REGISTERED_JOBS_AMBIGUOUS")
        jobs = held or [j for j in jobs if j["state"] in ("PREPARED", "LAUNCHING", "RUNNING")]
    if len(jobs) != 1:
        return None
    job = jobs[0]
    if (
        job.get("order_id") != value["order_id"]
        or job.get("attempt_id") != value["attempt_id"]
        or job.get("line_role_authority_ref") != value["control_ref"]
        or job.get("line_origin") != value["line_origin"]
    ):
        raise Refused("LINE_RECOVERY_REGISTERED_JOB_CHANGED")
    return job


def config_environment(cfg):
    fields = {
        "LAUNCH_DIR": cfg.launch_dir,
        "REPO": cfg.repo,
        "STACK_ROOT": cfg.stack_root,
        "RUNS_ROOT": cfg.runs_root,
        "GPU_LOCK": cfg.gpu_lock,
        "PYTHON": cfg.python,
        "FABRO_BIN": cfg.fabro_bin,
        "FABRO_PORT": cfg.fabro_host_port,
        "INPUTS_CACHE": cfg.inputs_cache or "",
        "REFERENCES": ":".join(map(str, cfg.references)),
        "GUARD": "",
    }
    # The existing LineConfig guard input is a path, never a command string.
    if cfg.guard and (len(cfg.guard) != 2 or cfg.guard[0] != "bash"):
        raise Refused("LINE_RECOVERY_GUARD_CONFIGURATION_UNSUPPORTED")
    fields["GUARD"] = str(cfg.guard[1]) if cfg.guard else ""
    return {"FORGE_LINE_" + key: str(value) for key, value in fields.items()}


def bound_order(store, value):
    paths = {key: Path(path) for key, path in value["line_origin"].items()}
    if not all(path.is_absolute() for path in paths.values()):
        raise Refused("LINE_RECOVERY_WORKER_ORIGIN_INVALID")
    return R.bind_order(store, value["order_id"], value["attempt_id"], **paths)


def bootstrap(cid, *, cfg=None, execute=None, quiesce=False):
    """No GPU/service/model operation; only existing worktree preparation and exact-source exec."""
    cfg = cfg or LL.LineConfig.from_env()
    if state_dir().resolve() != (cfg.stack_root / "state").resolve():
        raise Refused("LINE_RECOVERY_WORKER_STATE_MISMATCH")
    store = Store(state_dir() / "supervisor/line-queue.sqlite3", must_exist=True)
    cmd, value, spec, row = metadata(store, cid)
    revision = LL.resolve_rev(cfg.repo, spec["revision"])
    from .local_agent import request_for
    from .policy import load

    supervision_only = quiesce
    if quiesce and existing_job(store, value) is None:
        raise Refused("LINE_RECOVERY_NO_EXISTING_JOB_TO_QUIESCE")
    try:
        bound_order(store, value)
        control = C.controller_configuration(value["control_ref"], load(), target_revision=revision, request=request_for(row))
    except (Refused, R.BindingRefused, OSError, ValueError, KeyError):
        registered = existing_job(store, value)
        if (
            not registered
            or registered.get("factory_revision", {}).get("commit") != revision
            or registered.get("profile") != spec["profile"]
        ):
            raise
        # No worktree creation or new admission on this path. The exact existing
        # worker must still cancel/reconcile a revoked/expired owned job safely.
        intent = registered.get("native_context", {}).get("FORGE_OPERATIONS_INTENT")
        if not intent or not Path(intent).is_absolute():
            raise Refused("LINE_RECOVERY_REGISTERED_INTENT_ABSENT") from None
        control = {"profile": registered["profile"], "operations_intent": intent}
        supervision_only = True
    if control["profile"] != spec["profile"]:
        raise Refused("LINE_RECOVERY_WORKER_PROFILE_CHANGED")
    order = LL.Order(
        wo=spec["wo"],
        rev=revision,
        example=spec["example"],
        profile=spec["profile"],
        model=spec["run_model"],
        stop_after=spec["stop_after"],
        purpose=spec["purpose"],
    )
    wt = cfg.runs_root / spec["wo"]
    if value["mode"] == "PRODUCT" and not wt.exists() and not supervision_only:
        wt, _ = LL.ensure_worktree(cfg, order, revision)
    else:
        if LL.resolve_rev(wt, "HEAD") != revision or LL.worktree_clean(wt):
            raise Refused("LINE_RECOVERY_WORKER_SOURCE_CHANGED")
    if not (wt / "factory/python/forge_factory/afo/line_recovery_worker.py").is_file():
        raise Refused("LINE_RECOVERY_WORKER_NOT_IN_RUN_REVISION")
    env = LL.run_env(cfg, wt, spec["profile"])
    env.update(config_environment(cfg))
    env.update(
        FORGE_STATE_DIR=str(cfg.stack_root / "state"),
        FORGE_DATA_ROOT=str(cfg.stack_root),
        FORGE_ARCHIVE_DIR=str(cfg.stack_root / "archives"),
        FORGE_AFO_QUEUE_SCOPE="line-local",
        FORGE_DURABLE_AUTONOMY="1",
        FORGE_OPERATIONS_INTENT=control["operations_intent"],
        FORGE_FABRO_STORAGE=str(cfg.stack_root / "fabro/storage"),
        FORGE_FABRO_URL=f"http://127.0.0.1:{cfg.fabro_host_port}/api/v1",
    )
    argv = [
        str(cfg.python),
        "-m",
        "forge_factory.afo.line_recovery_worker",
        "step",
        "--command",
        cid,
        *(["--quiesce"] if quiesce else []),
    ]
    return (execute or os.execve)(str(cfg.python), argv, env)


@contextmanager
def worker_lock(cid):
    if not isinstance(cid, str) or not re.fullmatch(r"afo-cmd-[0-9a-f]{20}", cid):
        raise Refused("LINE_RECOVERY_COMMAND_ID_INVALID")
    root = state_dir() / "supervisor/line-recovery-locks"
    root.mkdir(parents=True, exist_ok=True)
    with (root / (cid + ".lock")).open("a") as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise Refused("LINE_RECOVERY_WORKER_LOCK_HELD") from None
        try:
            yield
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


def _replan(store, cmd, value, spec, row, eff, client):
    from . import bundle, checkpoints, local_agent, planner, recovery
    from . import line_recovery_product as product
    from .completion_receipt import Receipts, for_plan
    from .mission_ledger import MissionLedger

    attempt = next((a for a in store.attempts(row["order_id"]) if a["attempt_id"] == cmd["attempt_id"]), None)
    if not attempt or row["state"] != "WAITING_RECOVERY" or attempt["state"] not in ("FAILED", "SUCCEEDED"):
        raise Refused("LINE_RECOVERY_SOURCE_NOT_TERMINAL_ACTIVE_ORDER")
    mission = MissionLedger(store).for_order(row["order_id"])
    control = C.configuration(value["control_ref"], eff, request=local_agent.request_for(row))
    if mission != control["mission"]["mission_id"]:
        raise Refused("LINE_RECOVERY_MISSION_CHANGED")
    settled = product.synchronize(store, row, attempt, eff, client)
    if not settled:
        return {"status": "WAITING_FOR_NATIVE_PROVIDER_QUIESCENCE", "order_id": row["order_id"]}
    ws = state_dir() / "workorders" / spec["wo"] / "workspace"
    R.context(store, row["order_id"], attempt["attempt_id"], ws, value["line_origin"])
    checkpoints.capture(store, row["order_id"], attempt["attempt_id"], ws)
    failure = bundle.build(ws, row["order_id"], attempt["attempt_id"], run_failed=attempt["state"] == "FAILED")
    if failure is None:
        raise Refused("LINE_RECOVERY_FAILURE_BUNDLE_REQUIRED")
    if failure["failure_class"] == "FACTORY_CODE_DEFECT":
        try:
            from .line_maintenance_coordinator import step as maintenance_step
        except ModuleNotFoundError:
            raise Refused("LINE_MAINTENANCE_COORDINATOR_NOT_INSTALLED") from None
        result = maintenance_step(
            store,
            row,
            attempt,
            failure,
            ws,
            eff,
            line_origin=value["line_origin"],
            line_role_authority_ref=value["control_ref"],
            client=client,
        )
        if result["status"] == "MAINTENANCE_PENDING":
            store.mark_command(cmd["command_id"], "PENDING")
        elif result["status"] == "WAITING_EXTERNAL_CHANGE":
            store.transition(row["order_id"], "WAITING_EXTERNAL_CHANGE", "isolated maintenance result awaits approved source")
            store.mark_command(cmd["command_id"], "ACKED", ack_ref="maintenance:" + str(result.get("case_id", "offline")))
        elif result["status"] == "BLOCKED":
            store.transition(row["order_id"], "BLOCKED", "maintenance blocked", terminal_reason="MAINTENANCE_BLOCKED")
            store.mark_command(cmd["command_id"], "ACKED", ack_ref="maintenance:blocked")
        else:
            raise Refused("LINE_MAINTENANCE_RESULT_INVALID")
        return result
    invoke = R.make_planner(store, eff, origin=value["line_origin"], line_role_authority_ref=value["control_ref"])
    try:
        decision = recovery.decide(
            store, row, failure, ws=ws, eff=eff, auth_models=None, planner=invoke, line_origin=value["line_origin"]
        )
    except planner.Pending as pending:
        store.mark_command(cmd["command_id"], "PENDING")
        return {"status": "PLANNER_PENDING", "job_id": str(pending)}
    if decision["status"] == "PENDING":
        store.mark_command(cmd["command_id"], "PENDING")
        return {"status": "PLANNER_PENDING"}
    plan = decision["plan"]
    if decision["status"] != "VALIDATED":
        raise Refused("LINE_RECOVERY_PLAN_NOT_VALIDATED")
    if plan["strategy"] == "CLOSE_BLOCKED":
        store.transition(row["order_id"], "BLOCKED", plan["rationale_code"], terminal_reason=plan["rationale_code"][:200])
        store.mark_command(cmd["command_id"], "ACKED", ack_ref="blocked:" + plan["rationale_code"])
        return {"status": "BLOCKED", "issues": [plan["rationale_code"]]}
    receipt = for_plan(store, plan["plan_id"])
    if decision["source"] == "PLANNER" and (not receipt or Receipts(store).bound_plan(receipt) != plan):
        raise Refused("LINE_RECOVERY_SEMANTIC_RECEIPT_REQUIRED")
    # Park owner input/model/safety/policy changes; deterministic validation remains authoritative.
    if (
        plan.get("model_profile")
        or plan["strategy"] == "SWITCH_PREAPPROVED_MODEL_PROFILE"
        or (plan.get("owner_phase") or plan["affected_phase"]) == "SWE.1"
    ):
        raise Refused("LINE_RECOVERY_OWNER_CHANGE_REQUIRED")
    store.mark_command(cmd["command_id"], "ACKED", ack_ref="afo-plan:" + plan["plan_id"])
    return {"status": "PLAN_VALIDATED", "plan_id": plan["plan_id"], "receipt_id": receipt["receipt_id"] if receipt else None}


def step(cid, *, client=None, quiesce=False):
    from ..fabro.client import FabroClient, load_token
    from . import line_recovery_product as product
    from .local_agent import request_for
    from .policy import load

    store = Store(state_dir() / "supervisor/line-queue.sqlite3", must_exist=True)
    with worker_lock(cid):
        cmd, value, spec, row = metadata(store, cid)
        eff = load()
        own = client is None
        client = client or FabroClient(token=load_token(), timeout=3)
        try:
            # Existing jobs must still be reconciled when a grant/config/intent is
            # revoked. Supervision never creates a replacement job or frees UNKNOWN.
            product.supervise_existing(store, cmd, value, eff, client, quiesce=quiesce)
            if quiesce:
                return {"status": "QUIESCING_EXISTING_EXECUTION"}
            if value["mode"] == "PRODUCT" and cmd["state"] == "ACKED":
                return {"status": "SUPERVISED_EXISTING_PRODUCT"}
            C.configuration(value["control_ref"], eff, request=request_for(row))
            bound_order(store, value)
            from .operations import Intent

            control = C.read(value["control_ref"])
            if Intent(control["operations_intent"]).read()["mode"] != "RUNNING":
                return {"status": "WAITING_FOR_AUTHENTICATED_OPERATIONS_INTENT"}
            if value["mode"] == "PRODUCT":
                return product.dispatch(store, cmd, value, spec, eff, client)
            return _replan(store, cmd, value, spec, row, eff, client)
        finally:
            if own:
                client.close()


def record_refusal(cid, exc):
    """Project hard configuration refusals onto the existing outbox/order.

    A registered execution is never declared not-started here: unknown native or
    provider liveness remains held and is supervised on later conductor cycles.
    """
    from .dispatch import item_failure
    from .execution_lifecycle import Executions

    if getattr(exc, "code", "") == "LINE_RECOVERY_WORKER_LOCK_HELD":
        return {"action": "existing_worker_owns_command", "inference_release": False}
    store = Store(state_dir() / "supervisor/line-queue.sqlite3", must_exist=True)
    cmd, value, _, row = metadata(store, cid)
    job = existing_job(store, value)
    if job:
        execution = Executions(store).get(job["job_id"])
        if execution and execution["resource_lease"] == "HELD":
            Executions(store).revoke(job["job_id"])
            if execution["task_outcome"] == "ACTIVE":
                Executions(store).outcome(job["job_id"], "BLOCKED", "LINE_WORKER_REFUSED")
    # Block this immutable request instead of allocating fresh names/nonces for
    # an unchanged configuration. Existing execution leases are left untouched.
    store.mark_command(cid, "QUARANTINED")
    return item_failure(store, row["order_id"], exc, "line_worker")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["bootstrap", "step"])
    parser.add_argument("--command", dest="command_id", required=True)
    parser.add_argument("--quiesce", action="store_true", help="reconcile/cancel only an already registered execution")
    args = parser.parse_args(argv)
    try:
        result = (
            bootstrap(args.command_id, quiesce=args.quiesce)
            if args.command == "bootstrap"
            else step(args.command_id, quiesce=args.quiesce)
        )
    except (Refused, R.BindingRefused, LL.LaunchError, OSError, ValueError, KeyError) as exc:
        result = {"status": "REFUSED", "issues": [getattr(exc, "code", type(exc).__name__)]}
        try:
            result["projection"] = record_refusal(args.command_id, exc)
        except (Refused, R.BindingRefused, OSError, ValueError, KeyError):
            result["projection"] = "IDENTITY_UNAVAILABLE_NO_MUTATION"
    print(json.dumps(result, sort_keys=True))
    return 2 if result.get("status") in ("BLOCKED", "REFUSED") else 0


if __name__ == "__main__":
    raise SystemExit(main())
