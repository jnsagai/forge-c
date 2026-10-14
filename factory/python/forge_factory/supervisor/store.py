"""T019 — durable incident ledger (SQLite WAL) with guarded state transitions and fingerprint dedup.

States (data-model.md): DETECTED -> TRIAGED -> REPAIRING -> VERIFYING -> RESOLVED
                         REPAIRING|VERIFYING -> ROLLED_BACK -> TRIAGED (retry budget) | REQUIRES_OFFLINE_ATTENTION
* At most one ACTIVE (non-terminal) incident per fingerprint (UNIQUE partial index) -> dedup.
* Every transition is one transaction appending to `incident_history` (append-only audit trail).
* Terminal incidents are immutable; a recurrence opens a new incident linking the previous one.
* Leases (owner + expiry) ensure a single repair dispatcher per incident across process restarts.
"""
from __future__ import annotations

import json
import sqlite3
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from ..common import schema_errors, state_dir, utc_now

TERMINAL = {"RESOLVED", "REQUIRES_OFFLINE_ATTENTION"}
TRANSITIONS = {
    "DETECTED": {"TRIAGED", "REQUIRES_OFFLINE_ATTENTION", "RESOLVED"},
    "TRIAGED": {"REPAIRING", "REQUIRES_OFFLINE_ATTENTION", "RESOLVED"},
    "REPAIRING": {"VERIFYING", "ROLLED_BACK", "REQUIRES_OFFLINE_ATTENTION"},
    "VERIFYING": {"RESOLVED", "ROLLED_BACK", "REQUIRES_OFFLINE_ATTENTION"},
    "ROLLED_BACK": {"TRIAGED", "REQUIRES_OFFLINE_ATTENTION"},
    "RESOLVED": set(),
    "REQUIRES_OFFLINE_ATTENTION": set(),
}

SCHEMA = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS incidents (
  incident_id TEXT PRIMARY KEY, fingerprint TEXT NOT NULL, component TEXT NOT NULL, fault_type TEXT NOT NULL,
  state TEXT NOT NULL, severity TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
  attempts INTEGER NOT NULL DEFAULT 0, correlation_id TEXT NOT NULL, run_id TEXT, last_error TEXT,
  evidence_refs TEXT NOT NULL DEFAULT '[]', patch_hash TEXT, recoverable INTEGER NOT NULL DEFAULT 1,
  previous_incident_id TEXT, lease_owner TEXT, lease_expires REAL, occurrences INTEGER NOT NULL DEFAULT 1,
  active INTEGER NOT NULL DEFAULT 1);
CREATE UNIQUE INDEX IF NOT EXISTS one_active_per_fingerprint ON incidents(fingerprint) WHERE active = 1;
CREATE TABLE IF NOT EXISTS incident_history (
  seq INTEGER PRIMARY KEY AUTOINCREMENT, incident_id TEXT NOT NULL, from_state TEXT, to_state TEXT NOT NULL,
  at TEXT NOT NULL, reason TEXT);
CREATE TRIGGER IF NOT EXISTS history_append_only BEFORE UPDATE ON incident_history
  BEGIN SELECT RAISE(ABORT, 'incident_history is append-only'); END;
CREATE TRIGGER IF NOT EXISTS history_no_delete BEFORE DELETE ON incident_history
  BEGIN SELECT RAISE(ABORT, 'incident_history is append-only'); END;
CREATE TABLE IF NOT EXISTS repair_attempts (
  attempt_id TEXT PRIMARY KEY, incident_id TEXT NOT NULL, record TEXT NOT NULL, started_at TEXT NOT NULL,
  started_epoch REAL NOT NULL);
"""


class TransitionError(ValueError):
    pass


class IncidentStore:
    def __init__(self, path: Path | None = None):
        self.path = path or state_dir() / "supervisor" / "incidents.sqlite3"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as c:
            c.executescript(SCHEMA)

    @contextmanager
    def _conn(self):
        c = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA busy_timeout=30000")
        c.execute("PRAGMA synchronous=FULL")
        try:
            yield c
        finally:
            c.close()

    @staticmethod
    def _row(r: sqlite3.Row | None) -> dict | None:
        if r is None:
            return None
        d = dict(r)
        d["evidence_refs"] = json.loads(d["evidence_refs"])
        d["recoverable"] = bool(d["recoverable"])
        return d

    def to_contract(self, inc: dict) -> dict:
        keys = ["incident_id", "fingerprint", "component", "fault_type", "state", "severity", "created_at",
                "updated_at", "attempts", "correlation_id", "run_id", "last_error", "evidence_refs", "patch_hash",
                "recoverable"]
        out = {k: inc[k] for k in keys if inc.get(k) not in (None, [])}
        out["attempts"] = min(100, inc["attempts"])
        return out

    def open_or_dedup(self, fingerprint: str, component: str, fault_type: str, severity: str = "HIGH",
                      run_id: str | None = None, last_error: str | None = None, recoverable: bool = True,
                      evidence_refs: list[str] | None = None) -> tuple[dict, bool]:
        """Return (incident, created). An active incident with the same fingerprint is reused (dedup)."""
        now = utc_now()
        with self._conn() as c:
            c.execute("BEGIN IMMEDIATE")
            try:
                cur = c.execute("SELECT * FROM incidents WHERE fingerprint=? AND active=1", (fingerprint,)).fetchone()
                if cur:
                    c.execute("UPDATE incidents SET occurrences=occurrences+1, updated_at=?, last_error=COALESCE(?,"
                              " last_error) WHERE incident_id=?", (now, (last_error or "")[:160] or None,
                                                                    cur["incident_id"]))
                    c.execute("COMMIT")
                    return self.must(cur["incident_id"]), False
                prev = c.execute("SELECT incident_id FROM incidents WHERE fingerprint=? ORDER BY created_at DESC "
                                 "LIMIT 1", (fingerprint,)).fetchone()
                iid = f"inc-{uuid.uuid4().hex[:12]}"
                c.execute("INSERT INTO incidents(incident_id,fingerprint,component,fault_type,state,severity,created_at,"
                          "updated_at,correlation_id,run_id,last_error,recoverable,evidence_refs,previous_incident_id) "
                          "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                          (iid, fingerprint[:512], component[:128], fault_type[:128], "DETECTED", severity, now, now,
                           f"corr-{iid}", run_id, (last_error or "")[:160] or None, int(recoverable),
                           json.dumps(evidence_refs or []), prev["incident_id"] if prev else None))
                c.execute("INSERT INTO incident_history(incident_id,from_state,to_state,at,reason) VALUES(?,?,?,?,?)",
                          (iid, None, "DETECTED", now, (last_error or "detected")[:200]))
                c.execute("COMMIT")
            except Exception:
                c.execute("ROLLBACK")
                raise
        inc = self.must(iid)
        errs = schema_errors("incident.schema.json", self.to_contract(inc))
        if errs:
            raise ValueError(f"incident contract violation: {errs[:2]}")
        return inc, True

    def must(self, incident_id: str) -> dict:
        inc = self.get(incident_id)
        if inc is None:
            raise KeyError(incident_id)
        return inc

    def get(self, incident_id: str) -> dict | None:
        with self._conn() as c:
            return self._row(c.execute("SELECT * FROM incidents WHERE incident_id=?", (incident_id,)).fetchone())

    def transition(self, incident_id: str, to_state: str, reason: str = "", **fields: Any) -> dict:
        now = utc_now()
        with self._conn() as c:
            c.execute("BEGIN IMMEDIATE")
            try:
                cur = c.execute("SELECT state FROM incidents WHERE incident_id=?", (incident_id,)).fetchone()
                if cur is None:
                    raise TransitionError(f"unknown incident {incident_id}")
                if to_state not in TRANSITIONS[cur["state"]]:
                    raise TransitionError(f"{cur['state']}->{to_state} not allowed")
                sets, vals = ["state=?", "updated_at=?", "active=?"], [to_state, now, 0 if to_state in TERMINAL else 1]
                for k in ("attempts", "patch_hash", "last_error", "recoverable"):
                    if k in fields:
                        sets.append(f"{k}=?")
                        vals.append(fields[k] if k != "last_error" else str(fields[k])[:160])
                if "evidence_ref" in fields:
                    row = c.execute("SELECT evidence_refs FROM incidents WHERE incident_id=?", (incident_id,)).fetchone()
                    refs = json.loads(row["evidence_refs"]) + [fields["evidence_ref"]]
                    sets.append("evidence_refs=?")
                    vals.append(json.dumps(refs))
                if to_state in TERMINAL:
                    sets += ["lease_owner=NULL", "lease_expires=NULL"]
                c.execute(f"UPDATE incidents SET {', '.join(sets)} WHERE incident_id=?", (*vals, incident_id))  # noqa: S608
                c.execute("INSERT INTO incident_history(incident_id,from_state,to_state,at,reason) VALUES(?,?,?,?,?)",
                          (incident_id, cur["state"], to_state, now, reason[:200]))
                c.execute("COMMIT")
            except Exception:
                c.execute("ROLLBACK")
                raise
        return self.must(incident_id)

    def acquire_lease(self, incident_id: str, owner: str, ttl_s: float = 600) -> bool:
        now = time.time()
        with self._conn() as c:
            cur = c.execute("UPDATE incidents SET lease_owner=?, lease_expires=? WHERE incident_id=? AND active=1 AND "
                            "(lease_owner IS NULL OR lease_expires < ? OR lease_owner=?)",
                            (owner, now + ttl_s, incident_id, now, owner))
            return cur.rowcount == 1

    def release_lease(self, incident_id: str, owner: str) -> None:
        with self._conn() as c:
            c.execute("UPDATE incidents SET lease_owner=NULL, lease_expires=NULL WHERE incident_id=? AND lease_owner=?",
                      (incident_id, owner))

    def active(self) -> list[dict]:
        with self._conn() as c:
            return [dict(self._row(r) or {}) for r in c.execute("SELECT * FROM incidents WHERE active=1 ORDER BY created_at")]

    def all(self, limit: int = 200) -> list[dict]:
        with self._conn() as c:
            return [dict(self._row(r) or {}) for r in c.execute("SELECT * FROM incidents ORDER BY created_at DESC LIMIT ?",
                                                    (limit,))]

    def history(self, incident_id: str) -> list[dict]:
        with self._conn() as c:
            return [dict(r) for r in c.execute("SELECT * FROM incident_history WHERE incident_id=? ORDER BY seq",
                                               (incident_id,))]

    # repair attempts --------------------------------------------------------------------------
    def record_attempt(self, record: dict) -> None:
        errs = schema_errors("repair-attempt.schema.json", record)
        if errs:
            raise ValueError(f"repair-attempt contract violation: {errs[:2]}")
        with self._conn() as c:
            c.execute("INSERT OR REPLACE INTO repair_attempts(attempt_id,incident_id,record,started_at,started_epoch) "
                      "VALUES(?,?,?,?,COALESCE((SELECT started_epoch FROM repair_attempts WHERE attempt_id=?),?))",
                      (record["attempt_id"], record["incident_id"], json.dumps(record, sort_keys=True),
                       record["started_at"], record["attempt_id"], time.time()))

    def attempts(self, incident_id: str | None = None) -> list[dict]:
        q, args = "SELECT record FROM repair_attempts", tuple[str, ...]()
        if incident_id:
            q, args = q + " WHERE incident_id=?", (incident_id,)
        with self._conn() as c:
            return [json.loads(r["record"]) for r in c.execute(q + " ORDER BY started_epoch", args)]

    def attempts_since(self, epoch: float) -> int:
        with self._conn() as c:
            return c.execute("SELECT COUNT(*) FROM repair_attempts WHERE started_epoch >= ?", (epoch,)).fetchone()[0]
