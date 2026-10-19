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

from ..common import REPO_ROOT, utc_now
from .queue import QueueError, Store

GRACE_S = 180          # a launch younger than this may still appear in Fabro's listing
MAX_LAUNCH_TRIES = 2   # proven-not-submitted relaunches per attempt before quarantine
TERMINAL = {"SUCCEEDED": "SUCCEEDED", "FAILED": "FAILED", "CANCELLED": "CANCELLED", "CANCELED": "CANCELLED"}


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
        c.execute("UPDATE afo_commands_outbox SET state=?, ack_ref=COALESCE(?, ack_ref), attempts=attempts+? "
                  "WHERE command_id=?", (state, ack, 1 if count else 0, cid))


# -- launch (T028) --------------------------------------------------------------------------------------------------
def dispatch_pending(store: Store, launcher, *, decide=None, now: float | None = None) -> list[dict]:
    """PENDING FABRO_LAUNCH commands: persist intent (IN_FLIGHT + nonce) BEFORE the launch, then record the receipt."""
    from . import authority

    decide = decide or (lambda req: authority.decide("launch_workorder", req))
    out = []
    for cmd in store.commands("PENDING"):
        if cmd["kind"] != "FABRO_LAUNCH":
            continue
        order = store.order(cmd["order_id"])
        env = json.loads(order["envelope"])
        d = decide({"order_id": env["request_id"], "driver_class": env["driver_class"], "model": env["model_profile"]})
        if not d.allow:
            out.append({"command_id": cmd["command_id"], "action": "refused", "code": d.code})
            continue
        att = _attempt(store, cmd["attempt_id"])
        seq, nonce = att["seq"], secrets.token_hex(8)
        name = wo_name(order["order_id"], seq)
        labels = {"afo_attempt": cmd["attempt_id"], "afo_nonce": nonce}
        _set_cmd(store, cmd["command_id"], "IN_FLIGHT", count=True)
        store.attempt_transition(cmd["attempt_id"], "DISPATCH_PENDING", workspace_ref=f"workorder:{name}",
                                 evidence_refs=[f"nonce:{nonce}", f"dispatched_epoch:{now or time.time():.0f}"])
        manifest = json.loads((REPO_ROOT / order["input_manifest_ref"]).read_text())
        payload = json.loads(cmd["payload"])
        if payload.get("resume_from"):  # recovery attempt: resume verified phases from the previous attempt
            manifest = {**manifest, "resume_from": payload["resume_from"]}
        try:
            receipt = launcher(manifest, name, labels)
        except Exception as exc:  # noqa: BLE001 - outcome unknown: reconciliation decides, never a blind retry
            out.append({"command_id": cmd["command_id"], "action": "launch_outcome_unknown",
                        "error": f"{type(exc).__name__}: {exc}"[:200]})
            continue
        adopt(store, cmd, receipt["fabro_run_id"], receipt.get("factory_revision", "unknown"))
        out.append({"command_id": cmd["command_id"], "action": "launched", "fabro_run_id": receipt["fabro_run_id"]})
    return out


def adopt(store: Store, cmd: dict, run_id: str, revision: str = "unknown") -> None:
    store.attempt_transition(cmd["attempt_id"], "RUNNING", fabro_run_id=run_id, factory_revision=revision)
    _set_cmd(store, cmd["command_id"], "ACKED", ack=f"fabro_run:{run_id}")
    if store.order(cmd["order_id"])["state"] in ("ADMITTED", "WAITING_RECOVERY"):
        store.transition(cmd["order_id"], "RUNNING", f"Fabro run {run_id} receipted")


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
        hits = [r for r in runs if (r.get("labels") or {}).get("afo_attempt") == cmd["attempt_id"]
                and (r.get("labels") or {}).get("afo_nonce") == nonce]
        if len(hits) == 1:
            adopt(store, cmd, hits[0]["id"])
            out.append({"command_id": cmd["command_id"], "action": "adopted", "fabro_run_id": hits[0]["id"]})
        elif len(hits) > 1:
            _set_cmd(store, cmd["command_id"], "QUARANTINED")
            if att["state"] != "UNKNOWN":
                store.attempt_transition(cmd["attempt_id"], "UNKNOWN")
            store.transition(cmd["order_id"], "BLOCKED", f"{len(hits)} Fabro runs carry one attempt nonce",
                             terminal_reason="LAUNCH_AMBIGUOUS")
            out.append({"command_id": cmd["command_id"], "action": "quarantined", "matches": len(hits)})
        elif now - t0 < GRACE_S:
            out.append({"command_id": cmd["command_id"], "action": "wait_grace"})
        elif cmd["attempts"] >= MAX_LAUNCH_TRIES:
            _set_cmd(store, cmd["command_id"], "QUARANTINED")
            store.transition(cmd["order_id"], "BLOCKED", "launch never appeared in Fabro after bounded retries",
                             terminal_reason="LAUNCH_NOT_RECEIPTED")
            out.append({"command_id": cmd["command_id"], "action": "quarantined_retries"})
        else:  # reachable, past grace, no run with this nonce: proven not submitted -> one more bounded launch
            store.attempt_transition(cmd["attempt_id"], "PREPARED")
            _set_cmd(store, cmd["command_id"], "PENDING")
            out.append({"command_id": cmd["command_id"], "action": "proven_not_submitted_requeued"})
    return out


# -- run-state reconciliation (T029) ---------------------------------------------------------------------------------
def reconcile_running(store: Store, view) -> list[dict]:
    out = []
    runs = view()
    for order in store.orders(("RUNNING",)):
        att = store.attempts(order["order_id"])[-1]
        rid = att["record"].get("fabro_run_id")
        if runs is None or not rid:
            out.append({"order_id": order["order_id"], "action": "no_change"})
            continue
        run = next((r for r in runs if r.get("id") == rid), None)
        if run is None:
            store.attempt_transition(att["attempt_id"], "UNKNOWN")
            store.transition(order["order_id"], "BLOCKED", f"Fabro run {rid} absent on a reachable server",
                             terminal_reason="RUN_ABSENT")
            out.append({"order_id": order["order_id"], "action": "blocked_run_absent"})
            continue
        kind = run_kind(run)
        if kind in TERMINAL:
            store.attempt_transition(att["attempt_id"], TERMINAL[kind], exit_status=kind.lower(), finished_utc=utc_now())
            store.transition(order["order_id"], "VALIDATING", f"Fabro run {rid} {kind.lower()}")
            out.append({"order_id": order["order_id"], "action": "validating", "run": kind})
        else:
            out.append({"order_id": order["order_id"], "action": "still_active", "run": kind})
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
    ready = (rec.get("package_status") == "READY_FOR_OFFLINE_REVIEW" and man.get("status") == "READY_FOR_OFFLINE_REVIEW"
             and not rec.get("gaps") and not man.get("gaps"))
    return {"verdict": "READY_FOR_OFFLINE_REVIEW" if ready else "BLOCKED", "archive_sha256": sha,
            "reason": "all package gates" if ready else f"package {rec.get('package_status')} / {man.get('status')}, "
                                                         f"{len(rec.get('gaps') or [])} gaps"}


def validate(store: Store, workspace_of, *, deadline_s: float = 6 * 3600, now: float | None = None) -> list[dict]:
    now = now or time.time()
    out = []
    for order in store.orders(("VALIDATING",)):
        att = store.attempts(order["order_id"])[-1]
        v = package_verdict(workspace_of(att) / ".forge-run/package.json")
        if v["verdict"] == "PENDING":
            if now - order["created_epoch"] > deadline_s:
                store.transition(order["order_id"], "BLOCKED", "no sealed package before the deadline",
                                 terminal_reason="PACKAGE_MISSING")
                out.append({"order_id": order["order_id"], "action": "blocked_no_package"})
            continue
        try:
            store.transition(order["order_id"], v["verdict"], v["reason"], terminal_reason=v["reason"][:200])
        except QueueError:
            continue
        out.append({"order_id": order["order_id"], "action": v["verdict"], "archive_sha256": v.get("archive_sha256")})
    return out
