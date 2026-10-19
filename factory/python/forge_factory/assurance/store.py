"""EASA records in the EXISTING 002 incident database (same file as CRE), via additive versioned migrations.

Every assurance record (policy activation, applicability decision, oracle provenance, verification run, gate
decision, claim, audit finding) is appended once, content-addressed and never updated or deleted (trigger
enforced). A correction is a NEW record that names the record it supersedes; the first-pass record stays readable
(EASA-FR-021/064). 002/003/004 tables are not touched.
"""
from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from ..common import canonical_json, sha256_bytes, state_dir, utc_now
from ..reliability.store import _append_only, _statements

KINDS = ("policy", "scope", "applicability", "reconciliation", "oracle", "verification", "coverage", "mutation",
         "fidelity", "independence", "claim", "gate", "finding", "audit", "impact", "mode")

MIGRATIONS: list[tuple[int, str, str]] = [
    (1, "EASA append-only assurance records with supersession", """
CREATE TABLE IF NOT EXISTS easa_records (seq INTEGER PRIMARY KEY AUTOINCREMENT, record_id TEXT UNIQUE NOT NULL,
  kind TEXT NOT NULL, subject TEXT NOT NULL, work_order_id TEXT, ts_utc TEXT NOT NULL, sha256 TEXT NOT NULL,
  supersedes TEXT, actor TEXT NOT NULL, record TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS easa_records_subject ON easa_records(kind, subject);
""" + _append_only("easa_records")),
]
SCHEMA_VERSION = max(v for v, _, _ in MIGRATIONS)


class AssuranceStore:
    def __init__(self, path: Path | None = None):
        self.path = path or state_dir() / "supervisor" / "incidents.sqlite3"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.migrate()

    @contextmanager
    def conn(self):
        t = float(os.environ.get("FORGE_CRE_DB_TIMEOUT_S", "30"))
        c = sqlite3.connect(self.path, timeout=t, isolation_level=None)
        c.row_factory = sqlite3.Row
        c.execute(f"PRAGMA busy_timeout={int(t * 1000)}")
        c.execute("PRAGMA synchronous=FULL")
        try:
            yield c
        finally:
            c.close()

    def migrate(self) -> list[int]:
        applied = []
        with self.conn() as c:
            c.execute("PRAGMA journal_mode=WAL")
            c.execute("CREATE TABLE IF NOT EXISTS easa_schema_version (version INTEGER PRIMARY KEY, description TEXT "
                      "NOT NULL, applied_at TEXT NOT NULL)")
            have = {r[0] for r in c.execute("SELECT version FROM easa_schema_version")}
            for v, desc, sql in MIGRATIONS:
                if v in have:
                    continue
                c.execute("BEGIN IMMEDIATE")
                try:
                    for stmt in _statements(sql):
                        c.execute(stmt)
                    c.execute("INSERT INTO easa_schema_version VALUES (?,?,?)", (v, desc, utc_now()))
                    c.execute("COMMIT")
                except Exception:
                    c.execute("ROLLBACK")
                    raise
                applied.append(v)
        return applied

    def version(self) -> int:
        with self.conn() as c:
            return int(c.execute("SELECT max(version) FROM easa_schema_version").fetchone()[0] or 0)

    def append(self, kind: str, subject: str, record: dict, *, actor: str, work_order_id: str | None = None,
               supersedes: str | None = None) -> str:
        """Append one record; identical content is a no-op returning the same id (replay-safe)."""
        if kind not in KINDS:
            raise ValueError(f"unknown record kind {kind}")
        body = canonical_json({"kind": kind, "subject": subject, "record": record, "supersedes": supersedes})
        digest = sha256_bytes(body)
        rid = f"easa-{kind}-{digest[:20]}"
        with self.conn() as c:
            if supersedes and not c.execute("SELECT 1 FROM easa_records WHERE record_id=?", (supersedes,)).fetchone():
                raise KeyError(f"superseded record {supersedes} does not exist")
            c.execute("INSERT OR IGNORE INTO easa_records (record_id, kind, subject, work_order_id, ts_utc, sha256, "
                      "supersedes, actor, record) VALUES (?,?,?,?,?,?,?,?,?)",
                      (rid, kind, subject, work_order_id, utc_now(), digest, supersedes, actor,
                       json.dumps(record, sort_keys=True)))
        return rid

    def _rows(self, sql: str, args: tuple) -> list[dict]:
        with self.conn() as c:
            return [{**dict(r), "record": json.loads(r["record"])} for r in c.execute(sql, args)]

    def history(self, kind: str, subject: str | None = None) -> list[dict]:
        if subject is None:
            return self._rows("SELECT * FROM easa_records WHERE kind=? ORDER BY seq", (kind,))
        return self._rows("SELECT * FROM easa_records WHERE kind=? AND subject=? ORDER BY seq", (kind, subject))

    def get(self, record_id: str) -> dict | None:
        rows = self._rows("SELECT * FROM easa_records WHERE record_id=?", (record_id,))
        return rows[0] if rows else None

    def current(self, kind: str, subject: str) -> dict | None:
        """Newest record of a subject that no later record supersedes."""
        rows = self.history(kind, subject)
        superseded = {r["supersedes"] for r in rows if r["supersedes"]}
        live = [r for r in rows if r["record_id"] not in superseded]
        return live[-1] if live else None

    def first_pass(self, kind: str, subject: str) -> dict | None:
        rows = self.history(kind, subject)
        return rows[0] if rows else None
