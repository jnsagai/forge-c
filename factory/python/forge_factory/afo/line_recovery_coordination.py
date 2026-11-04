"""M3 projections of existing REPLAN/product outbox state, never a second scheduler.

The healthy cycle performs bounded reads and spawns one external worker. All
packet preparation, model serving and native launch occur in that worker using
the exact immutable campaign run checkout. No configuration means legacy M3.
"""

from __future__ import annotations

import json
from pathlib import Path

from . import line_orders as O
from .durable import Refused, canonical, digest

REQUEST_SCHEMA = "forge-c/line-recovery-worker-request/1"


def reference(path):
    from .line_recovery_control import read
    from .operational_collection import reference as artifact_reference

    ref = artifact_reference(Path(path).resolve())
    read(ref)
    return ref


def origin(placer, campaign):
    value = {"campaign_path": str(campaign.path.resolve())}
    for key, path in (
        ("policy_path", placer.policy_path),
        ("auth_base", placer.auth_base),
        ("allowed_signers", placer.allowed_signers),
    ):
        if path is not None:
            value[key] = str(Path(path).resolve())
    return value


def command(store, command_id):
    found = [c for c in store.commands() if c["command_id"] == command_id]
    if len(found) != 1:
        raise Refused("LINE_RECOVERY_COMMAND_ABSENT")
    return found[0]


def _bind_command(store, cid, metadata):
    with store.tx() as c:
        row = c.execute("SELECT payload FROM afo_commands_outbox WHERE command_id=?", (cid,)).fetchone()
        payload = json.loads(row[0])
        if "line_worker" in payload and payload["line_worker"] != metadata:
            raise Refused("LINE_RECOVERY_COMMAND_REBOUND")
        if "line_worker" not in payload:
            payload["line_worker"] = metadata
            c.execute("UPDATE afo_commands_outbox SET payload=? WHERE command_id=?", (canonical(payload).decode(), cid))
            store._event(
                c,
                "line_worker_bound",
                metadata["order_id"],
                metadata["attempt_id"],
                {"command_id": cid, "metadata_sha256": digest(metadata)},
            )


def _metadata(placer, store, order_id, attempt_id, campaign, *, mode):
    from .operational_collection import reference as artifact_reference

    row = store.order(order_id)
    if row is None:
        raise Refused("LINE_RECOVERY_ORDER_ABSENT")
    spec_path = O.supervisor_dir() / "line-orders" / (row["request_id"] + ".json")
    return {
        "schema": REQUEST_SCHEMA,
        "mode": mode,
        "order_id": order_id,
        "attempt_id": attempt_id,
        "spec_ref": artifact_reference(spec_path),
        "control_ref": placer.durable_control,
        "line_origin": origin(placer, campaign),
    }


def _spawn(placer, store, cmd, wo, now, *, quiesce=False):
    cursor = O.supervisor_dir() / "launching" / (wo + ".json")
    previous = O._load(cursor) or {}
    if (
        previous.get("command_id") == cmd["command_id"]
        and previous.get("durable_worker")
        and placer.line.alive(int(previous.get("pid") or 0), previous.get("start"))
    ):
        return {"outcome": "DURABLE_WORKER_ACTIVE", "command_id": cmd["command_id"]}
    started = placer.line.spawn_recovery_worker(cmd["command_id"], wo, **({"quiesce": True} if quiesce else {}))
    O._atomic(
        cursor,
        {
            **started,
            "at": O._utc(now),
            "attempt_id": cmd["attempt_id"],
            "order_id": cmd["order_id"],
            "command_id": cmd["command_id"],
            "durable_worker": True,
        },
    )
    return {"outcome": "DURABLE_WORKER_STARTED", "command_id": cmd["command_id"], "pid": started.get("pid")}


def request_replan(placer, store, plan, att, attempt, campaigns, now):
    if not attempt:
        raise Refused("LINE_RECOVERY_SOURCE_ATTEMPT_ABSENT")
    from .mission_ledger import MissionLedger

    # Never onboard an unaccounted historical run as zero usage or a fresh budget.
    MissionLedger(store).for_order(attempt["order_id"])
    campaign = next(c for c in campaigns if c.campaign_id == plan.lineage.campaign_id)
    row = store.order(attempt["order_id"])
    with store.tx() as c:
        cid = store._enqueue(
            c,
            "REPLAN",
            "line-recovery:" + attempt["attempt_id"],
            row["order_id"],
            attempt["attempt_id"],
            row["fencing_epoch"],
            {"source_work_order": att.wo},
        )
    _bind_command(store, cid, _metadata(placer, store, row["order_id"], attempt["attempt_id"], campaign, mode="REPLAN"))
    return cid


def launch_product(placer, store, order, aid, oid, campaign, now):
    cmds = [c for c in store.commands("PENDING") if c["kind"] == "FABRO_LAUNCH" and c["attempt_id"] == aid]
    if len(cmds) != 1:
        raise Refused("LINE_RECOVERY_PRODUCT_COMMAND_AMBIGUOUS")
    _bind_command(store, cmds[0]["command_id"], _metadata(placer, store, oid, aid, campaign, mode="PRODUCT"))
    return {"attempt_id": aid, **_spawn(placer, store, command(store, cmds[0]["command_id"]), order["wo"], now)}


def _decision(store, cmd):
    from . import recovery
    from .completion_receipt import Receipts, for_plan

    plan_id = str(cmd.get("ack_ref") or "").removeprefix("afo-plan:")
    candidates = [p for p in recovery.plans(store, cmd["order_id"]) if p["plan_id"] == plan_id]
    if len(candidates) != 1 or candidates[0]["status"] not in ("VALIDATED", "EXECUTED"):
        raise Refused("LINE_RECOVERY_VALIDATED_PLAN_ABSENT")
    record = candidates[0]
    plan = record["record"]
    receipt = for_plan(store, plan_id)
    if record["source"] == "PLANNER":
        if not receipt or Receipts(store).bound_plan(receipt) != plan:
            raise Refused("LINE_RECOVERY_SEMANTIC_RECEIPT_REQUIRED")
    if (
        plan["strategy"] in ("SWITCH_PREAPPROVED_MODEL_PROFILE", "CLOSE_BLOCKED")
        or (plan.get("owner_phase") or plan["affected_phase"]) == "SWE.1"
        or plan.get("model_profile")
    ):
        raise Refused("LINE_RECOVERY_OWNER_CHANGE_REQUIRED")
    return plan, receipt


def continuation(store, spec):
    """Resolve the accepted plan, never trust a phase name or model-authored CLI field."""
    from . import recovery
    from .completion_receipt import Receipts, for_plan
    from .execution_lifecycle import Executions
    from .line_recovery_product import job_id

    value = spec.get("durable_recovery")
    keys = {"source_order_id", "source_attempt_id", "source_work_order", "plan_id", "plan_sha256", "receipt_id"}
    if not isinstance(value, dict) or set(value) != keys:
        raise Refused("LINE_RECOVERY_CONTINUATION_INVALID")
    source = store.order(value["source_order_id"])
    attempts = store.attempts(value["source_order_id"])
    attempt = next((a for a in attempts if a["attempt_id"] == value["source_attempt_id"]), None)
    if (
        not source
        or source["request_id"] != value["source_work_order"]
        or not attempt
        or attempt["state"] not in ("FAILED", "SUCCEEDED")
    ):
        raise Refused("LINE_RECOVERY_CONTINUATION_SOURCE_CHANGED")
    candidates = [p for p in recovery.plans(store, source["order_id"]) if p["plan_id"] == value["plan_id"]]
    if len(candidates) != 1 or candidates[0]["status"] not in ("VALIDATED", "EXECUTED"):
        raise Refused("LINE_RECOVERY_VALIDATED_PLAN_ABSENT")
    selected = candidates[0]["record"]
    if digest(selected) != value["plan_sha256"]:
        raise Refused("LINE_RECOVERY_PLAN_CHANGED")
    receipt = for_plan(store, selected["plan_id"])
    if candidates[0]["source"] == "PLANNER":
        if not receipt or receipt["receipt_id"] != value["receipt_id"] or Receipts(store).bound_plan(receipt) != selected:
            raise Refused("LINE_RECOVERY_SEMANTIC_RECEIPT_REQUIRED")
    elif value["receipt_id"] is not None:
        raise Refused("LINE_RECOVERY_RECEIPT_CHANGED")
    execution = Executions(store).get(job_id(attempt["attempt_id"]))
    if not execution or execution["resource_lease"] != "RELEASED" or execution["execution_liveness"] != "QUIESCENT":
        raise Refused("LINE_RECOVERY_SOURCE_NOT_QUIESCENT")
    from .checkpoints import PHASES

    owner = selected.get("owner_phase") or selected["affected_phase"]
    if (
        owner == "SWE.1"
        or selected.get("model_profile")
        or selected["strategy"] in ("CLOSE_BLOCKED", "SWITCH_PREAPPROVED_MODEL_PROFILE")
        or spec["phase"] not in PHASES
        or PHASES.index(spec["phase"]) < PHASES.index(owner)
    ):
        raise Refused("LINE_RECOVERY_OWNER_CHANGE_REQUIRED")
    return selected, receipt


def prepare_continuation(placer, store, spec, grant):
    """Bounded controller check, then close the terminal source to free M3 capacity.

    The external worker independently revalidates source checkpoints and authority
    before execution. Old specs, queue envelopes and workproducts are immutable.
    """
    if not spec.get("durable_control"):
        return
    from .line_recovery_control import controller_configuration
    from .policy import load

    value = spec.get("durable_recovery")
    request = {"driver_class": spec["driver_class"], "model": spec["profile"]}
    controller_configuration(
        spec["durable_control"], load(), target_revision=placer.line.resolve(spec["revision"]), request=request
    )
    if not value:
        return
    selected, receipt = continuation(store, spec)
    source = store.order(value["source_order_id"])
    permitted = grant.permit("recover_workorder", request).allow
    if not permitted:
        raise Refused("LINE_RECOVERY_CONTINUATION_NOT_AUTHORIZED")
    if receipt:
        from .completion_receipt import Receipts

        Receipts(store).request_dispatch(receipt["receipt_id"], authorize=lambda: permitted)
    if source["state"] == "WAITING_RECOVERY":
        store.transition(
            source["order_id"],
            "BLOCKED",
            "continued by immutable order " + spec["wo"],
            terminal_reason="CONTINUED_AS:" + spec["wo"],
        )
    elif source["state"] != "BLOCKED" or not str(source["terminal_reason"]).startswith("CONTINUED_AS:"):
        raise Refused("LINE_RECOVERY_SOURCE_NOT_CONTINUABLE")


def bind_continuation(store, spec, order_id, attempt_id):
    if not spec.get("durable_recovery"):
        return
    _, receipt = continuation(store, spec)
    if receipt:
        from .completion_receipt import applying

        applying(store, receipt["receipt_id"], attempt_id)
    with store.tx() as c:
        c.execute(
            "UPDATE afo_recovery_plans SET status='EXECUTED' WHERE plan_id=? AND status='VALIDATED'",
            (spec["durable_recovery"]["plan_id"],),
        )


def coordinate(placer, plans, policy, grant, campaigns, now, *, execute):
    from .queue import Store

    if not execute:
        return []  # dry-run never creates a queue, worker cursor, outbox intent or job
    store = Store(placer.queue_path, producer="line-recovery-coordination")
    actions = []
    spawned = False
    # Supervise existing resource holders even after expiry, campaign hold, or a
    # terminal phase. This is reconciliation of the same nonce, never admission.
    # UNKNOWN provider/native liveness keeps the existing lease and blocks M2.
    with store.tx() as c:
        holders = [
            r[0]
            for r in c.execute(
                "SELECT job_id FROM afo_execution_liveness WHERE json_extract(record,'$.resource_lease')='HELD' LIMIT 2"
            )
        ]
    if holders:
        jobs = []
        with store.tx() as c:
            for jid in holders:
                raw = c.execute(
                    "SELECT record FROM afo_product_jobs WHERE job_id=? UNION ALL "
                    "SELECT record FROM afo_local_agent_jobs WHERE job_id=?",
                    (jid, jid),
                ).fetchall()
                if len(raw) == 1:
                    jobs.append((jid, json.loads(raw[0][0])))
        for jid, job in jobs:
            cmds = [
                cmd
                for cmd in store.commands()
                if cmd["attempt_id"] == job["attempt_id"]
                and (json.loads(cmd["payload"]).get("line_worker") or {}).get("control_ref") == job.get("line_role_authority_ref")
                and cmd["kind"] == ("FABRO_LAUNCH" if jid.startswith("afo-product-") else "REPLAN")
            ]
            if len(cmds) != 1:
                continue
            row = store.order(job["order_id"])
            spec = O._load(O.supervisor_dir() / "line-orders" / (row["request_id"] + ".json")) or {}
            plan = next((p for p in plans if p.lineage.key == spec.get("lineage")), None)
            quiesce = not grant.allow or plan is None or plan.lineage.status == "ON_HOLD"
            actions.append(
                {
                    "action": "DURABLE_SUPERVISION",
                    "wo": row["request_id"],
                    **_spawn(placer, store, cmds[0], row["request_id"], now, quiesce=quiesce),
                }
            )
            spawned = True
            break
        # Never place a new phase beside a held/unknown inference execution.
        for p in plans:
            if p.order:
                p.action = None
    if holders or not grant.allow:
        return actions
    for p in plans:
        closed = [
            a
            for attempts in p.atts.values()
            for a in attempts
            if a.status == "CLOSED"
            and (a.spec or {}).get("durable_control") == placer.durable_control
            and (a.spec or {}).get("lineage_sha") == p.lineage.sha256
            and (a.queue or {}).get("terminal_reason") != "SUPERSEDED_BY_CAMPAIGN_CHANGE"
        ]
        if closed:
            p.state, p.reason, p.order, p.action = "WAITING", "DURABLE_SOURCE_CLOSED_REQUIRES_OWNER_CHANGE", None, None
            continue
        if p.state in ("ESCALATED", "PARKED", "ON_HOLD", "DONE"):
            continue
        a = p.current
        if not a or a.status != "ENDED" or a.verdict == "PASS":
            continue
        rows = [r for r in store.orders() if r["request_id"] == a.wo]
        if len(rows) != 1 or (a.spec or {}).get("durable_control") != placer.durable_control:
            p.state, p.reason, p.order = "WAITING", "DURABLE_SOURCE_ACCOUNTING_REQUIRED", None
            continue
        row = rows[0]
        if row["state"] in ("BLOCKED", "WAITING_EXTERNAL_CHANGE") and not str(row.get("terminal_reason")).startswith(
            "CONTINUED_AS:"
        ):
            p.state, p.reason, p.order, p.action = "WAITING", "DURABLE_SOURCE_" + row["state"], None, None
            continue
        cmds = [c for c in store.commands() if c["kind"] == "REPLAN" and c["order_id"] == row["order_id"]]
        if not cmds:
            p.state, p.reason, p.order = "WAITING", "DURABLE_REPLAN_NOT_RECORDED", None
            continue
        cmd = cmds[-1]
        if cmd["state"] != "ACKED":
            p.state, p.reason, p.order = "WAITING", "DURABLE_PLANNER_" + cmd["state"], None
            if not spawned and cmd["state"] in ("PENDING", "IN_FLIGHT"):
                actions.append({"action": "DURABLE_RECOVERY", "wo": a.wo, **_spawn(placer, store, cmd, a.wo, now)})
                spawned = True
            continue
        try:
            selected, receipt = _decision(store, cmd)
            owner = selected.get("owner_phase") or selected["affected_phase"]
            n = max([x.n for x in p.atts.get(owner, [])] + [0]) + 1
            new = dict(p.order or a.spec)
            new.update(
                wo=p.lineage.wo(owner, n),
                phase=owner,
                stop_after=owner,
                kind="RETRY",
                resume_from=a.wo,
                resume_upto=owner,
                durable_control=placer.durable_control,
                durable_recovery={
                    "source_order_id": row["order_id"],
                    "source_attempt_id": cmd["attempt_id"],
                    "source_work_order": a.wo,
                    "plan_id": selected["plan_id"],
                    "plan_sha256": digest(selected),
                    "receipt_id": receipt["receipt_id"] if receipt else None,
                },
            )
            p.order, p.action, p.kind, p.phase, p.state, p.reason = (
                new,
                "PLACE",
                "RETRY",
                owner,
                "QUEUED",
                "VALIDATED_DURABLE_RECOVERY",
            )
        except (Refused, KeyError, ValueError) as exc:
            p.state, p.reason, p.order = "WAITING", getattr(exc, "code", "DURABLE_DECISION_INVALID"), None
    return actions
