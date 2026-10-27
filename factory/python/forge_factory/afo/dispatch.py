"""AFO M3 (T026-T029, T032; AFO-FR-027..030, 034; ADR-AFO-002) - launch protocol, crash reconciliation, run-state
reconciliation and the independent package check that alone may make an order READY.

All functions take a `view` (Fabro run listing: list[dict], or None when the server is unreachable) and, for
launches, a `launcher`; the real ones wrap fabro.client.FabroClient and workorder.run, tests inject fakes.
"""

from __future__ import annotations

import hashlib
import json
import secrets
import time
import zipfile
from pathlib import Path

from ..common import REPO_ROOT, sha256_file, utc_now
from .queue import QueueError, Store

GRACE_S = 180  # a launch younger than this may still appear in Fabro's listing
MAX_LAUNCH_TRIES = 2  # proven-not-submitted relaunches per attempt before quarantine
TERMINAL = {"SUCCEEDED": "SUCCEEDED", "FAILED": "FAILED", "CANCELLED": "CANCELLED", "CANCELED": "CANCELLED"}


def item_failure(store, order_id, exc, stage):
    """Contain typed item failures; SQLite/integrity failures deliberately remain uncaught."""
    from .durable import digest, canonical

    order = store.order(order_id)
    code = getattr(exc, "code", type(exc).__name__)
    record = {"order_id": order_id, "stage": stage, "code": code, "outcome": "ITEM_BLOCKED", "inference_release": False}
    key = "incident-" + digest(record)[:24]
    with store.tx() as c:
        changed = c.execute(
            "INSERT OR IGNORE INTO afo_recovery_incidents VALUES (?,?,?,?)", (key, order_id, code, canonical(record).decode())
        ).rowcount
        if changed:
            store._event(c, "item_failure", order_id, None, record, "WARN")
    if order and order["state"] in ("QUEUED", "ADMITTED", "RUNNING", "WAITING_RECOVERY", "VALIDATING", "WAITING_EXTERNAL_CHANGE"):
        store.transition(order_id, "BLOCKED", code, terminal_reason=code[:200])
    return {"order_id": order_id, "action": "item_blocked", "code": code, "incident_id": key}


def wo_name(order_id: str, seq: int) -> str:
    return f"WO-AFO-{order_id.removeprefix('afo-')}-a{seq}"


def run_kind(run: dict) -> str:
    return str((((run.get("lifecycle") or {}).get("status")) or {}).get("kind") or "UNKNOWN").upper()


def _attempt(store: Store, aid: str) -> dict:
    with store.tx() as c:
        r = c.execute("SELECT * FROM afo_attempts WHERE attempt_id=?", (aid,)).fetchone()
        return {**dict(r), "record": json.loads(r["record"])}


def _set_cmd(store: Store, cid: str, state: str, ack: str | None = None, count: bool = False) -> None:
    with store.tx() as c:
        c.execute(
            "UPDATE afo_commands_outbox SET state=?, ack_ref=COALESCE(?, ack_ref), attempts=attempts+? WHERE command_id=?",
            (state, ack, 1 if count else 0, cid),
        )


# -- launch (T028) --------------------------------------------------------------------------------------------------
def dispatch_pending(store: Store, launcher, *, decide=None, now: float | None = None) -> list[dict]:
    """PENDING FABRO_LAUNCH commands: persist intent (IN_FLIGHT + nonce) BEFORE the launch, then record the receipt."""
    from . import authority

    decide = decide or (lambda req: authority.decide("launch_workorder", req))
    out = []
    for cmd in store.commands("PENDING"):
        if cmd["kind"] != "FABRO_LAUNCH":
            continue
        from .operations import configured, Intent

        payload = json.loads(cmd["payload"])
        if configured():
            intent = Intent().read()
            if intent["mode"] != "RUNNING":
                out.append({"command_id": cmd["command_id"], "action": "operations_wait"})
                continue
            if payload.get("operations_epoch") != intent["epoch"]:
                _set_cmd(store, cmd["command_id"], "QUARANTINED")
                out.append(item_failure(store, cmd["order_id"], ValueError("STALE_OPERATIONS_COMMAND"), "outbox_epoch"))
                continue
        if (cmd.get("retry_not_before_epoch") or 0) > (now or time.time()):  # a transient retry's backoff
            out.append({"command_id": cmd["command_id"], "action": "backoff"})
            continue
        order = store.order(cmd["order_id"])
        env = json.loads(order["envelope"])
        d = decide({"order_id": env["request_id"], "driver_class": env["driver_class"], "model": env["model_profile"]})
        if not d.allow:
            out.append({"command_id": cmd["command_id"], "action": "refused", "code": d.code})
            continue
        att = _attempt(store, cmd["attempt_id"])
        from .mission_ledger import MissionLedger
        from .durable import Refused

        try:
            mission = MissionLedger(store).for_order(order["order_id"])
        except Refused:
            mission = None
        seq, nonce = att["seq"], secrets.token_hex(16 if mission else 8)
        name = wo_name(order["order_id"], seq)
        labels = {"afo_attempt": cmd["attempt_id"], "afo_nonce": nonce}
        with store.tx() as c:
            claimed = c.execute(
                "UPDATE afo_commands_outbox SET state='IN_FLIGHT',attempts=attempts+1 WHERE command_id=? AND state='PENDING'",
                (cmd["command_id"],),
            ).rowcount
        if not claimed:
            continue
        store.attempt_transition(
            cmd["attempt_id"],
            "DISPATCH_PENDING",
            workspace_ref=f"workorder:{name}",
            evidence_refs=[f"nonce:{nonce}", f"dispatched_epoch:{now or time.time():.0f}"],
        )
        manifest_path = REPO_ROOT / order["input_manifest_ref"]
        if sha256_file(manifest_path) != order["manifest_sha256"]:
            _set_cmd(store, cmd["command_id"], "QUARANTINED")
            store.transition(
                order["order_id"],
                "BLOCKED",
                "launch manifest changed after approval",
                terminal_reason="LAUNCH_MANIFEST_HASH_CHANGED",
            )
            continue
        manifest = json.loads(manifest_path.read_text())
        if configured():
            manifest = {**manifest, "operations_epoch": payload["operations_epoch"]}
        payload = json.loads(cmd["payload"])
        if payload.get("resume_from"):  # recovery attempt: resume verified phases from the previous attempt
            manifest = {
                **manifest,
                **{
                    k: payload[k]
                    for k in ("resume_from", "resume_upto", "model_profile", "lesson_ids", "recovery_plan",
                              "recovery_exhausted")
                    if payload.get(k)
                },
            }
        from .mission_ledger import MissionLedger
        from .durable import Refused

        try:
            mission = MissionLedger(store).for_order(order["order_id"])
        except Refused:
            mission = None
        if mission:
            from . import product_job
            from .execution_lifecycle import Executions
            from .policy import load

            try:
                job = product_job.prepare(store, order, _attempt(store, att["attempt_id"]), nonce, manifest, load())
            except (Refused, ValueError, KeyError, TypeError) as exc:
                # The external launcher has not been called. Preserve its spent
                # reservation/history, quarantine this command and continue peers.
                _set_cmd(store, cmd["command_id"], "QUARANTINED")
                out.append(item_failure(store, order["order_id"], exc, "product_preparation"))
                continue
            labels.update(afo_agent=job["job_id"])
            manifest = {
                **manifest,
                "durable_binding": {
                    k: job[k] for k in ("job_id", "nonce", "mission_id", "order_id", "attempt_id", "operations_epoch") if k in job
                },
            }
            Executions(store).dispatch_intent(job["job_id"])
        try:
            receipt = launcher(manifest, name, labels)
        except Exception as exc:  # noqa: BLE001 - outcome unknown: reconciliation decides, never a blind retry
            out.append(
                {
                    "command_id": cmd["command_id"],
                    "action": "launch_outcome_unknown",
                    "error": f"{type(exc).__name__}: {exc}"[:200],
                }
            )
            continue
        if mission:
            Executions(store).adopt(job["job_id"], [receipt["fabro_run_id"]])
        adopt(store, cmd, receipt["fabro_run_id"], receipt.get("factory_revision", "unknown"))
        out.append({"command_id": cmd["command_id"], "action": "launched", "fabro_run_id": receipt["fabro_run_id"]})
    return out


def adopt(store: Store, cmd: dict, run_id: str, revision: str = "unknown") -> None:
    if _durable_order(store, cmd["order_id"]):
        from .execution_lifecycle import Executions

        with store.tx() as c:
            jobs = [json.loads(r[0]) for r in c.execute("SELECT record FROM afo_product_jobs")]
        job = next((j for j in jobs if j["attempt_id"] == cmd["attempt_id"]), None)
        if job:
            rec = Executions(store).get(job["job_id"])
            if rec and run_id not in rec["native_run_ids"]:
                Executions(store).adopt(job["job_id"], [run_id])
    store.attempt_transition(cmd["attempt_id"], "RUNNING", fabro_run_id=run_id, factory_revision=revision)
    _set_cmd(store, cmd["command_id"], "ACKED", ack=f"fabro_run:{run_id}")
    if store.order(cmd["order_id"])["state"] in ("ADMITTED", "WAITING_RECOVERY"):
        store.transition(cmd["order_id"], "RUNNING", f"Fabro run {run_id} receipted")


def _durable_order(store, order_id):
    with store.tx() as c:
        return c.execute("SELECT 1 FROM afo_mission_orders WHERE order_id=?", (order_id,)).fetchone() is not None


def _nonce(att: dict) -> tuple[str | None, float]:
    refs = att["record"].get("evidence_refs") or []
    n = next((r.split(":", 1)[1] for r in refs if r.startswith("nonce:")), None)
    t = next((float(r.split(":", 1)[1]) for r in refs if r.startswith("dispatched_epoch:")), 0.0)
    return n, t


# -- crash reconciliation of in-flight launches (T028) ---------------------------------------------------------------
def reconcile_inflight(store: Store, view, *, now: float | None = None) -> list[dict]:
    now = now or time.time()
    out = []
    for cmd in store.commands("IN_FLIGHT") + store.commands("UNKNOWN"):
        if cmd["kind"] != "FABRO_LAUNCH":
            continue
        att = _attempt(store, cmd["attempt_id"])
        nonce, t0 = _nonce(att)
        runs = view()
        if runs is None:  # Fabro unreachable: outcome stays unknown, nothing is relaunched
            if att["state"] == "DISPATCH_PENDING":
                store.attempt_transition(cmd["attempt_id"], "UNKNOWN")
            _set_cmd(store, cmd["command_id"], "UNKNOWN")
            out.append({"command_id": cmd["command_id"], "action": "unknown_fabro_unreachable"})
            continue
        hits = [
            r
            for r in runs
            if (r.get("labels") or {}).get("afo_attempt") == cmd["attempt_id"]
            and (r.get("labels") or {}).get("afo_nonce") == nonce
        ]
        if len(hits) == 1:
            adopt(store, cmd, hits[0]["id"])
            out.append({"command_id": cmd["command_id"], "action": "adopted", "fabro_run_id": hits[0]["id"]})
        elif len(hits) > 1:
            _set_cmd(store, cmd["command_id"], "QUARANTINED")
            if att["state"] != "UNKNOWN":
                store.attempt_transition(cmd["attempt_id"], "UNKNOWN")
            store.transition(
                cmd["order_id"], "BLOCKED", f"{len(hits)} Fabro runs carry one attempt nonce", terminal_reason="LAUNCH_AMBIGUOUS"
            )
            out.append({"command_id": cmd["command_id"], "action": "quarantined", "matches": len(hits)})
        elif now - t0 < GRACE_S:
            out.append({"command_id": cmd["command_id"], "action": "wait_grace"})
        elif _durable_order(store, cmd["order_id"]):
            _set_cmd(store, cmd["command_id"], "UNKNOWN")
            out.append({"command_id": cmd["command_id"], "action": "durable_native_identity_unknown"})
        elif cmd["attempts"] >= MAX_LAUNCH_TRIES:
            _set_cmd(store, cmd["command_id"], "QUARANTINED")
            store.transition(
                cmd["order_id"],
                "BLOCKED",
                "launch never appeared in Fabro after bounded retries",
                terminal_reason="LAUNCH_NOT_RECEIPTED",
            )
            out.append({"command_id": cmd["command_id"], "action": "quarantined_retries"})
        else:  # reachable, past grace, no run with this nonce: proven not submitted -> one more bounded launch
            store.attempt_transition(cmd["attempt_id"], "PREPARED")
            _set_cmd(store, cmd["command_id"], "PENDING")
            out.append({"command_id": cmd["command_id"], "action": "proven_not_submitted_requeued"})
    return out


# -- run-state reconciliation (T029) ---------------------------------------------------------------------------------
def reconcile_running(store: Store, view, recover=None) -> list[dict]:
    """`recover(order, attempt)` handles a terminal run whose SWE phase failed (AFO M4) and returns True when it
    took the order; otherwise the order goes to VALIDATING (the package decides READY or BLOCKED)."""
    out = []
    runs = view()
    for order in store.orders(("RUNNING",)):
        try:
            att = store.attempts(order["order_id"])[-1]
            rid = att["record"].get("fabro_run_id")
            if runs is None or not rid:
                out.append({"order_id": order["order_id"], "action": "no_change"})
                continue
            run = next((r for r in runs if r.get("id") == rid), None)
            if run is None:
                store.attempt_transition(att["attempt_id"], "UNKNOWN")
                store.transition(
                    order["order_id"], "BLOCKED", f"Fabro run {rid} absent on a reachable server", terminal_reason="RUN_ABSENT"
                )
                out.append({"order_id": order["order_id"], "action": "blocked_run_absent"})
                continue
            kind = run_kind(run)
            if kind in TERMINAL:
                from .execution_lifecycle import Executions
                from ..fabro.client import FabroClient, load_token

                with store.tx() as c:
                    pending = [json.loads(r[0]) for r in c.execute("SELECT record FROM afo_execution_liveness")]
                for rec in pending:
                    if rid in rec["native_run_ids"] and rec["resource_lease"] == "HELD":
                        with FabroClient(token=load_token(), timeout=5) as client:
                            Executions(store).reconcile(rec["job_id"], client)
                store.attempt_transition(att["attempt_id"], TERMINAL[kind], exit_status=kind.lower(), finished_utc=utc_now())
                r = recover(store.order(order["order_id"]), store.attempts(order["order_id"])[-1]) if recover else None
                if r:
                    out.append({"order_id": order["order_id"], "action": "recovery", "result": r})
                    continue
                store.transition(order["order_id"], "VALIDATING", f"Fabro run {rid} {kind.lower()}")
                out.append({"order_id": order["order_id"], "action": "validating", "run": kind})
            else:
                out.append({"order_id": order["order_id"], "action": "still_active", "run": kind})
        except (KeyError, ValueError, TypeError, FileNotFoundError) as exc:
            out.append(item_failure(store, order["order_id"], exc, "reconcile_running"))
    return out


def enforce_deadlines(store: Store, eff, client=None, now: float | None = None) -> list[dict]:
    """Bound adopted and ordinary work orders as well as diagnosis jobs; revocation never starts more work."""
    from ..fabro.client import FabroClient, load_token
    from . import authority
    from .local_agent import request_for

    now = time.time() if now is None else now
    out = []
    for order in store.orders(("RUNNING",)):
        expired = now >= order["created_epoch"] + float(eff.get("budgets.max_order_wall_seconds", 0))
        allowed = authority.decide("launch_workorder", request_for(order), afo=eff, log=False).allow
        if not expired and allowed:
            continue
        attempt = store.attempts(order["order_id"])[-1]
        rid = attempt["record"].get("fabro_run_id")
        if not rid:
            continue
        try:
            c = client or FabroClient(token=load_token(), timeout=5)
            code = c.cancel(rid)
        except Exception:  # noqa: BLE001 - unknown cancellation is recorded, never claimed as stopped
            code = None
        with store.tx() as db:
            store._event(
                db,
                "order_cancel_requested",
                order["order_id"],
                attempt["attempt_id"],
                {
                    "reason": "ORDER_WALL_BUDGET_EXHAUSTED" if expired else "AUTHORIZATION_REVOKED_OR_EXPIRED",
                    "http_status": code,
                    "cancellation_confirmed": False,
                },
            )
        out.append({"order_id": order["order_id"], "cancellation_requested": code in (200, 202, 204)})
    return out


# -- independent package check (T032) --------------------------------------------------------------------------------
def package_verdict(package_json: Path) -> dict:
    """READY only if the sealed archive exists, its sha256 matches the record, and both the record and the manifest
    inside the archive say READY_FOR_OFFLINE_REVIEW with no gaps. Anything else is BLOCKED (never Fabro status)."""
    try:
        rec = json.loads(Path(package_json).read_text())
    except (OSError, ValueError):
        return {"verdict": "PENDING", "reason": "no package record yet"}
    arc = Path(rec.get("archive", ""))
    if not arc.is_file():
        return {"verdict": "BLOCKED", "reason": "ARCHIVE_MISSING"}
    sha = hashlib.sha256(arc.read_bytes()).hexdigest()
    if sha != rec.get("archive_sha256"):
        return {"verdict": "BLOCKED", "reason": "ARCHIVE_HASH_MISMATCH", "archive_sha256": sha}
    try:
        with zipfile.ZipFile(arc) as z:
            man = json.loads(z.read("manifest.json"))
    except (KeyError, ValueError, zipfile.BadZipFile):
        return {"verdict": "BLOCKED", "reason": "ARCHIVE_MANIFEST_UNREADABLE", "archive_sha256": sha}
    ready = (
        rec.get("package_status") == "READY_FOR_OFFLINE_REVIEW"
        and man.get("status") == "READY_FOR_OFFLINE_REVIEW"
        and not rec.get("gaps")
        and not man.get("gaps")
    )
    return {
        "verdict": "READY_FOR_OFFLINE_REVIEW" if ready else "BLOCKED",
        "archive_sha256": sha,
        "reason": "all package gates"
        if ready
        else f"package {rec.get('package_status')} / {man.get('status')}, {len(rec.get('gaps') or [])} gaps",
    }


def validate(store: Store, workspace_of, *, deadline_s: float = 6 * 3600, now: float | None = None) -> list[dict]:
    now = now or time.time()
    out = []
    for order in store.orders(("VALIDATING",)):
        try:
            att = store.attempts(order["order_id"])[-1]
            v = package_verdict(workspace_of(att) / ".forge-run/package.json")
            if v["verdict"] == "PENDING":
                if now - order["created_epoch"] > deadline_s:
                    store.transition(
                        order["order_id"], "BLOCKED", "no sealed package before the deadline", terminal_reason="PACKAGE_MISSING"
                    )
                    out.append({"order_id": order["order_id"], "action": "blocked_no_package"})
                continue
            from .completion_receipt import verified_attempt

            verified_attempt(store, att, workspace_of(att))
            try:
                store.transition(order["order_id"], v["verdict"], v["reason"], terminal_reason=v["reason"][:200])
            except QueueError:
                continue
            out.append({"order_id": order["order_id"], "action": v["verdict"], "archive_sha256": v.get("archive_sha256")})
        except (KeyError, ValueError, TypeError, FileNotFoundError) as exc:
            out.append(item_failure(store, order["order_id"], exc, "validate"))
    return out
