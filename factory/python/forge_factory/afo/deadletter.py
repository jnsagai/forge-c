"""AFO-T054 (AFO-FR-058/059; AT-037/038/039/040) - dead-letter cases after a safe BLOCKED finalization.

Exactly one immutable case per (order, reason): the case id is derived from both, inserted with INSERT OR IGNORE and
its alert is enqueued in the same transaction, so a repeated finalizer callback, a sweep or a restart creates nothing
new (AT-038). The record (who/what/why, required operator action, artifact refs with hashes) is immutable by a DB
trigger; only the operator state OPEN -> ACKNOWLEDGED -> CLOSED moves, audited. DEAD_LETTER is queue bookkeeping,
never a release state: the product archive stays BLOCKED and is never counted as READY (AT-037/057).
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from ..common import sha256_bytes, utc_now
from . import alerts, contracts
from .queue import QueueError, Store

ACTIONS = [  # reason prefix -> the operator action the case asks for (first match)
    ("WAITING_EXTERNAL_CHANGE_TTL", "Review the factory-source proposal/CAPA; re-submit after an approved, deployed change."),
    ("PACKAGE_MISSING", "Inspect the run: no sealed package before the deadline; re-submit only after the cause is known."),
    ("ORDER_ATTEMPT_BUDGET_EXHAUSTED", "Review the failure bundles; re-submit only with new inputs or an approved change."),
    ("MODEL_NOT_ALLOWED", "Re-submit with a pre-approved model profile (policy engineering.allowed_model_profiles)."),
    ("ARCHIVE_", "Package integrity failed: verify the archive and its recorded sha256 offline."),
    ("PACKAGE", "Review the BLOCKED package gaps offline (no READY claim)."),
]
STATE_EDGES = {"OPEN": {"ACKNOWLEDGED", "CLOSED"}, "ACKNOWLEDGED": {"CLOSED"}, "CLOSED": set()}


def reason_code(terminal_reason: str | None) -> str:
    head = (terminal_reason or "BLOCKED").split(":")[0].split(" ")[0]
    return (re.sub(r"[^A-Z0-9_]+", "_", head.upper()).strip("_") or "BLOCKED")[:60]


def required_action(code: str) -> str:
    return next((a for p, a in ACTIONS if code.startswith(p)), "Review the order events and the BLOCKED evidence offline.")


def artifact_refs(order_id: str, ws: Path | None) -> list[str]:
    refs = [f"afo-order:{order_id}"]
    pkg = ws / ".forge-run/package.json" if ws else None
    if pkg and pkg.is_file():
        refs.append(f"package-record:{pkg}@{hashlib.sha256(pkg.read_bytes()).hexdigest()[:16]}")
        try:
            rec = json.loads(pkg.read_text())
            if rec.get("archive"):
                refs.append(f"archive:{rec['archive']}@{str(rec.get('archive_sha256', ''))[:16]}")
        except ValueError:
            refs.append("package-record:UNREADABLE")
    return refs


def record_case(store: Store, order_id: str, *, ws: Path | None = None, window_s: float = 900) -> tuple[str, bool]:
    o = store.order(order_id)
    if o is None or o["state"] != "BLOCKED":
        raise QueueError("NOT_BLOCKED", f"{order_id}:{(o or {}).get('state')}")
    atts = store.attempts(order_id)
    aid = atts[-1]["attempt_id"] if atts else None
    code = reason_code(o["terminal_reason"])
    cid = "dlq-" + sha256_bytes(f"{order_id}|{code}".encode())[:20]
    rec = {"schema_version": "1.0", "case_id": cid, "order_id": order_id, "attempt_id": aid, "reason_code": code,
           "required_action": required_action(code), "incident_ref": f"afo-order:{order_id}",
           "artifact_refs": artifact_refs(order_id, ws), "created_utc": utc_now(),
           "notification_dedupe_key": f"dlq:{cid}", "state": "OPEN", "package_status": "BLOCKED", "owner": None,
           "last_notification_utc": None}
    contracts.require("dead-letter", rec)
    body = json.dumps(rec, sort_keys=True)
    with store.tx() as c:
        new = c.execute("INSERT OR IGNORE INTO afo_dead_letters (case_id, order_id, attempt_id, reason_code, record,"
                        " record_sha256, state, recorded_utc) VALUES (?,?,?,?,?,?,?,?)",
                        (cid, order_id, aid, code, body, sha256_bytes(body.encode()), "OPEN", rec["created_utc"])
                        ).rowcount == 1
        if new:
            store._event(c, "dead_letter", order_id, aid, {"case_id": cid, "reason_code": code}, "WARN")
            alerts.enqueue(c, rec["notification_dedupe_key"], "WARN",
                           {"case_id": cid, "order_id": order_id, "reason_code": code,
                            "required_action": rec["required_action"]}, window_s=window_s)
    return cid, new


def sweep(store: Store, workspace_of=None, window_s: float = 900) -> list[str]:
    """Every BLOCKED order gets its case (idempotent; safe to run every cycle and after a restart)."""
    out = []
    for o in store.orders(("BLOCKED",)):
        atts = store.attempts(o["order_id"])
        ws = workspace_of(atts[-1]) if (workspace_of and atts) else None
        cid, new = record_case(store, o["order_id"], ws=ws, window_s=window_s)
        if new:
            out.append(cid)
    return out


def cases(store: Store, state: str | None = None) -> list[dict]:
    with store.tx() as c:
        q = "SELECT * FROM afo_dead_letters" + (" WHERE state=?" if state else "") + " ORDER BY recorded_utc"  # noqa: S608 - fixed SQL text, values bound
        return [{**dict(r), "record": json.loads(r["record"])} for r in c.execute(q, (state,) if state else ())]


def set_state(store: Store, case_id: str, to: str, actor: str, reason: str) -> None:
    if not reason.strip():
        raise QueueError("REASON_REQUIRED", case_id)
    with store.tx() as c:
        r = c.execute("SELECT state, order_id FROM afo_dead_letters WHERE case_id=?", (case_id,)).fetchone()
        if r is None:
            raise QueueError("NO_SUCH_CASE", case_id)
        if to not in STATE_EDGES[r["state"]]:
            raise QueueError("CASE_TRANSITION_DENIED", f"{r['state']}->{to}")
        c.execute("UPDATE afo_dead_letters SET state=? WHERE case_id=?", (to, case_id))
        c.execute("INSERT INTO afo_operator_actions (action, actor, reason, utc) VALUES (?,?,?,?)",
                  (f"dead_letter_{to.lower()}", actor, f"{case_id}: {reason}"[:300], utc_now()))
        store._event(c, f"dead_letter_{to}", r["order_id"], None, {"case_id": case_id, "actor": actor})
