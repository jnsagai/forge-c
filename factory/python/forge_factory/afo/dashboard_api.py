"""AFO-T056/T058 (AFO-FR-061/062/063; AT-052..055) - Autonomy projections for the existing 002 dashboard.

Reads go through a READ-ONLY SQLite connection (`mode=ro` URI): a dashboard request can never migrate, write or lock
the Conductor store for writing. Projections expose ids, states, codes, hashes and refs - never prompts, tool output,
file contents or tokens. Operator identities and actions are auditor-only. The only write path is `control`, used by
the operator POST endpoints (bearer operator token, reason required) and audited like the CLI.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from ..common import state_dir, utc_now
from .queue import Store, default_path

OID = re.compile(r"^afo-[0-9a-f]{8,64}$")
STATES = {"SUBMITTED", "REJECTED_INTAKE", "QUEUED", "ADMITTED", "RUNNING", "WAITING_RECOVERY", "WAITING_EXTERNAL_CHANGE",
          "VALIDATING", "READY_FOR_OFFLINE_REVIEW", "BLOCKED", "PAUSED"}
ORDER_COLS = ("order_id", "request_id", "priority", "state", "version", "created_utc", "admitted_utc", "defer_count",
              "terminal_reason", "policy_sha256", "authorization_id")


@contextmanager
def ro():
    p = default_path()
    if not p.is_file():
        yield None
        return
    c = sqlite3.connect(f"file:{p}?mode=ro", uri=True, timeout=5)
    c.row_factory = sqlite3.Row
    try:
        yield c
    finally:
        c.close()


def _table(c, name: str) -> bool:
    return c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone() is not None


def summary() -> dict:
    from .policy import load

    eff = load(log=False)
    out = {"mode": eff.mode, "policy_sha256": (eff.sha256 or "")[:16], "issues": eff.issues[:5], "orders": {},
           "dead_letters_open": 0, "notifications_pending": 0, "proposals": {}, "control": {},
           "statement": "Queue bookkeeping only: READY needs a verified sealed archive; BLOCKED and dead-letter cases "
                        "are never counted as accepted engineering output."}
    with ro() as c:
        if c is None:
            return {**out, "store": "absent"}
        out["schema_version"] = c.execute("SELECT MAX(version) FROM afo_schema_version").fetchone()[0]
        out["orders"] = {r[0]: r[1] for r in c.execute("SELECT state, COUNT(*) FROM afo_work_orders GROUP BY state")}
        out["control"] = {r["key"]: r["value"] for r in c.execute("SELECT key, value FROM afo_control")}
        if _table(c, "afo_dead_letters"):
            out["dead_letters_open"] = c.execute("SELECT COUNT(*) FROM afo_dead_letters WHERE state!='CLOSED'").fetchone()[0]
            out["notifications_pending"] = c.execute(
                "SELECT COUNT(*) FROM afo_notifications WHERE delivery_state IN ('PENDING','RETRY')").fetchone()[0]
        if _table(c, "afo_maintainer_proposals"):
            out["proposals"] = {r[0]: r[1] for r in c.execute(
                "SELECT status, COUNT(*) FROM (SELECT proposal_id, status FROM afo_maintainer_proposals p WHERE seq="
                "(SELECT MAX(seq) FROM afo_maintainer_proposals q WHERE q.proposal_id=p.proposal_id)) GROUP BY status")}
    return out


def orders(state: str | None = None) -> list[dict]:
    if state and state not in STATES:
        raise ValueError("bad state")
    with ro() as c:
        if c is None:
            return []
        q = f"SELECT {', '.join(ORDER_COLS)} FROM afo_work_orders" + (" WHERE state=?" if state else "")  # noqa: S608 - fixed SQL text, values bound
        return [dict(r) for r in c.execute(q + " ORDER BY created_epoch DESC", (state,) if state else ())]


def order(oid: str, auditor: bool = False) -> dict:
    if not OID.match(oid):
        raise ValueError("bad order id")
    with ro() as c:
        if c is None:
            raise KeyError(oid)
        o = c.execute(f"SELECT {', '.join(ORDER_COLS)} FROM afo_work_orders WHERE order_id=?", (oid,)).fetchone()  # noqa: S608 - fixed SQL text, values bound
        if o is None:
            raise KeyError(oid)
        atts = []
        for r in c.execute("SELECT attempt_id, seq, state, record, created_utc, finished_utc FROM afo_attempts "
                           "WHERE order_id=? ORDER BY seq", (oid,)):
            rec = json.loads(r["record"])
            atts.append({"attempt_id": r["attempt_id"], "seq": r["seq"], "state": r["state"],
                         **{k: rec.get(k) for k in ("fabro_run_id", "factory_revision", "workspace_ref",
                                                    "recovery_plan_id", "exit_status", "terminal_package_status")},
                         "created_utc": r["created_utc"], "finished_utc": r["finished_utc"]})
        evs = [{k: e[k] for k in ("event_id", "occurred_utc", "type", "attempt_id", "severity", "payload_sha256")}
               for e in (json.loads(x["record"]) for x in c.execute(
                   "SELECT record FROM afo_lifecycle_events WHERE order_id=? ORDER BY seq", (oid,)))]
        cps = [dict(r) for r in c.execute("SELECT checkpoint_id, attempt_id, phase, baseline_hash, frozen_utc "
                                          "FROM afo_checkpoints WHERE order_id=? ORDER BY recorded_utc", (oid,))]
        plans = [{k: v for k, v in dict(r).items() if k != "record"} for r in c.execute(
            "SELECT * FROM afo_recovery_plans WHERE order_id=?", (oid,))] if _table(c, "afo_recovery_plans") else []
        dlq = [json.loads(r["record"]) | {"state": r["state"]} for r in c.execute(
            "SELECT record, state FROM afo_dead_letters WHERE order_id=?", (oid,))] if _table(c, "afo_dead_letters") else []
    return {"order": dict(o), "attempts": atts, "events": evs, "checkpoints": cps, "recovery_plans": plans,
            "dead_letters": dlq if auditor else [{k: d[k] for k in ("case_id", "reason_code", "required_action", "state")}
                                                 for d in dlq]}


def dead_letters(state: str | None = None) -> list[dict]:
    with ro() as c:
        if c is None or not _table(c, "afo_dead_letters"):
            return []
        rows = c.execute("SELECT record, state FROM afo_dead_letters ORDER BY recorded_utc DESC").fetchall()
    out = [{**{k: json.loads(r["record"])[k] for k in ("case_id", "order_id", "attempt_id", "reason_code",
                                                       "required_action", "artifact_refs", "created_utc")},
            "state": r["state"]} for r in rows]
    return [x for x in out if not state or x["state"] == state]


def proposals() -> list[dict]:
    with ro() as c:
        if c is None or not _table(c, "afo_maintainer_proposals"):
            return []
        rows = c.execute("SELECT proposal_id, status, record, recorded_utc FROM afo_maintainer_proposals ORDER BY seq").fetchall()
    last: dict[str, dict] = {}
    for r in rows:
        rec = json.loads(r["record"])
        last[r["proposal_id"]] = {"proposal_id": r["proposal_id"], "status": r["status"], "outcome": rec["outcome"],
                                  "capa_id": rec["capa_id"], "candidate_commit": rec["candidate_commit"][:12],
                                  "cre_promotion_id": rec["cre_promotion_id"], "branch_ref": rec["branch_ref"],
                                  "pr_url": rec["pr_url"], "recorded_utc": r["recorded_utc"],
                                  "auto_deployment_allowed": rec["auto_deployment_allowed"]}
    return sorted(last.values(), key=lambda x: x["recorded_utc"], reverse=True)


def operations(auditor: bool) -> dict:
    with ro() as c:
        if c is None:
            return {"leases": [], "control": {}, "operator_actions": []}
        leases = [{k: r[k] for k in ("scope", "epoch", "expires_epoch", "heartbeat_epoch")}
                  for r in c.execute("SELECT * FROM afo_leases")]
        control = {r["key"]: r["value"] for r in c.execute("SELECT key, value FROM afo_control")}
        acts = [dict(r) for r in c.execute("SELECT action, actor, reason, utc FROM afo_operator_actions ORDER BY seq DESC "
                                           "LIMIT 100")] if auditor else []
        outbox = {r[0]: r[1] for r in c.execute("SELECT state, COUNT(*) FROM afo_commands_outbox GROUP BY state")}
    return {"leases": leases, "control": control, "outbox": outbox, "operator_actions": acts,
            "operator_actions_visible": auditor}


def control(action: str, actor: str, reason: str, *, authentication=None) -> dict:
    """Operator pause / drain / resume (same semantics and audit as the CLI)."""
    if action not in ("pause", "drain", "resume", "shutdown") or not reason.strip():
        raise ValueError("action must be pause|drain|resume with a reason")
    s = Store()
    from .operations import configured, synchronize
    if configured():
        synchronize(s, action, actor, reason, authentication=authentication)
        return s.control()
    if action == 'shutdown':
        raise ValueError('durable operations intent required')
    if action == "pause":
        s.set_control("paused", "1", actor, reason)
    elif action == "drain":
        s.set_control("draining", "1", actor, reason)
    else:
        s.set_control("paused", "0", actor, reason)
        s.set_control("draining", "0", actor, reason)
    return s.control()


def audit_denied(action: str, who: str, why: str) -> None:
    s = Store()
    with s.tx() as c:
        c.execute("INSERT INTO afo_operator_actions (action, actor, reason, utc) VALUES (?,?,?,?)",
                  (f"denied:{action}"[:60], who[:60], why[:200], utc_now()))
        s._event(c, "operator_denied", "afo-control", None, {"action": action, "who": who[:60], "why": why[:120]}, "WARN")


def operator_token_path():
    return state_dir() / "dashboard" / "afo-operator-token"


def issue_operator_token() -> str:
    """CLI only (the account owning the state dir): a separate bearer token for the operator POST endpoints. The
    viewer/auditor dashboard tokens and the session cookie never authorize a control."""
    p = operator_token_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    tok = secrets.token_urlsafe(32)
    fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(tok)
    return tok


def operator_ok(authorization: str | None) -> bool:
    return operator_authentication(authorization) is not None


def operator_authentication(authorization: str | None) -> dict | None:
    """Bind the existing bearer decision to the same bytes, without storing a token."""
    p = operator_token_path()
    tok = (authorization or "").removeprefix("Bearer ").strip()
    if not tok or not p.is_file():
        return None
    stored = p.read_text().strip()
    if not secrets.compare_digest(tok, stored):
        return None
    try:
        source_sha = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    except OSError:
        source_sha = None
    return {"method": "DASHBOARD_OPERATOR_BEARER", "credential_sha256": hashlib.sha256(stored.encode()).hexdigest(),
            "source_sha256": source_sha}
