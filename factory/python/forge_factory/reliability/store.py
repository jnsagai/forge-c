"""CRE-T005/T006/T009 — CRE tables in the EXISTING 002 incident database, created by versioned additive migrations.

ADR-CRE-001/003. The 002 tables (incidents, incident_history, repair_attempts) are never altered. Every history
table is append-only by trigger; current-state tables are projections that can be rebuilt from history. IDs are
content-addressed, so duplicate/replayed writes are no-ops (INSERT OR IGNORE).
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from ..common import canonical_json, state_dir, utc_now


def _append_only(table: str) -> str:
    return (f"CREATE TRIGGER IF NOT EXISTS {table}_no_update BEFORE UPDATE ON {table} "
            f"BEGIN SELECT RAISE(ABORT, '{table} is append-only'); END;\n"
            f"CREATE TRIGGER IF NOT EXISTS {table}_no_delete BEFORE DELETE ON {table} "
            f"BEGIN SELECT RAISE(ABORT, '{table} is append-only'); END;\n")


MIGRATIONS: list[tuple[int, str, str]] = [
    (1, "D1 events, failure observations, failure modes, fingerprint aliases", """
CREATE TABLE IF NOT EXISTS cre_events (seq INTEGER PRIMARY KEY AUTOINCREMENT, event_id TEXT UNIQUE NOT NULL,
  type TEXT NOT NULL, ts_utc TEXT NOT NULL, record TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS cre_failure_observations (obs_id TEXT PRIMARY KEY, fingerprint TEXT NOT NULL,
  failure_class TEXT NOT NULL, category TEXT NOT NULL, component TEXT NOT NULL, error_code TEXT NOT NULL,
  operation TEXT NOT NULL, order_id TEXT, attempt_id TEXT, run_id TEXT, phase TEXT, ts_utc TEXT NOT NULL,
  disposition TEXT NOT NULL, outcome TEXT NOT NULL, cohort TEXT NOT NULL, factory_version TEXT NOT NULL,
  source_ref TEXT NOT NULL, evidence_sha256 TEXT, excerpt TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS cre_obs_fp ON cre_failure_observations(fingerprint);
CREATE TABLE IF NOT EXISTS cre_failure_modes (fingerprint TEXT PRIMARY KEY, failure_class TEXT NOT NULL,
  category TEXT NOT NULL, component TEXT NOT NULL, error_code TEXT NOT NULL, operation TEXT NOT NULL,
  first_seen TEXT NOT NULL, last_seen TEXT NOT NULL, occurrences INTEGER NOT NULL, distinct_attempts INTEGER NOT NULL,
  distinct_orders INTEGER NOT NULL, recurring INTEGER NOT NULL, significant INTEGER NOT NULL,
  root_cause_status TEXT NOT NULL DEFAULT 'UNKNOWN', root_cause_hypothesis TEXT, verified_root_cause TEXT,
  capa_id TEXT, data_quality TEXT NOT NULL DEFAULT 'OBSERVED');
CREATE TABLE IF NOT EXISTS cre_fingerprint_aliases (seq INTEGER PRIMARY KEY AUTOINCREMENT, from_fp TEXT NOT NULL,
  to_fp TEXT NOT NULL, kind TEXT NOT NULL CHECK (kind IN ('MERGE','SPLIT')), reason TEXT NOT NULL, actor TEXT NOT NULL,
  at TEXT NOT NULL);
""" + _append_only("cre_events") + _append_only("cre_failure_observations") + _append_only("cre_fingerprint_aliases")),
    (2, "D2 retry ledger, breakers, recovery FSM, side-effect journal, scope leases", """
CREATE TABLE IF NOT EXISTS cre_retry_attempts (seq INTEGER PRIMARY KEY AUTOINCREMENT, op_key TEXT NOT NULL,
  attempt INTEGER NOT NULL, decided_at TEXT NOT NULL, not_before_epoch REAL NOT NULL, outcome TEXT NOT NULL,
  detail TEXT, UNIQUE(op_key, attempt));
CREATE TABLE IF NOT EXISTS cre_breakers (dependency TEXT PRIMARY KEY, state TEXT NOT NULL, failures INTEGER NOT NULL,
  opened_at_epoch REAL, half_open_probes INTEGER NOT NULL DEFAULT 0, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS cre_breaker_history (seq INTEGER PRIMARY KEY AUTOINCREMENT, dependency TEXT NOT NULL,
  from_state TEXT, to_state TEXT NOT NULL, at TEXT NOT NULL, reason TEXT);
CREATE TABLE IF NOT EXISTS cre_recovery (scope TEXT PRIMARY KEY, fingerprint TEXT, failure_class TEXT NOT NULL,
  state TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0, opened_at TEXT NOT NULL, updated_at TEXT NOT NULL,
  terminal_reason TEXT);
CREATE TABLE IF NOT EXISTS cre_recovery_history (seq INTEGER PRIMARY KEY AUTOINCREMENT, scope TEXT NOT NULL,
  from_state TEXT, to_state TEXT NOT NULL, at TEXT NOT NULL, reason TEXT);
CREATE TABLE IF NOT EXISTS cre_side_effects (seq INTEGER PRIMARY KEY AUTOINCREMENT, idem_key TEXT NOT NULL,
  op_class TEXT NOT NULL, replay_class TEXT NOT NULL, status TEXT NOT NULL, at TEXT NOT NULL, receipt TEXT);
CREATE INDEX IF NOT EXISTS cre_side_effects_key ON cre_side_effects(idem_key);
CREATE TABLE IF NOT EXISTS cre_scope_leases (scope TEXT PRIMARY KEY, owner TEXT NOT NULL, expires_epoch REAL NOT NULL);
""" + _append_only("cre_retry_attempts") + _append_only("cre_breaker_history") + _append_only("cre_recovery_history")
        + _append_only("cre_side_effects")),
    (3, "D3 CAPA, reproducer runs, prevention tests, lesson links", """
CREATE TABLE IF NOT EXISTS cre_capa (capa_id TEXT PRIMARY KEY, record TEXT NOT NULL, state TEXT NOT NULL,
  root_cause_status TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS cre_capa_history (seq INTEGER PRIMARY KEY AUTOINCREMENT, capa_id TEXT NOT NULL,
  from_state TEXT, to_state TEXT NOT NULL, at TEXT NOT NULL, reason TEXT NOT NULL, evidence TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS cre_reproducer_runs (run_id TEXT PRIMARY KEY, reproducer_id TEXT NOT NULL,
  revision TEXT NOT NULL, role TEXT NOT NULL, exit_code INTEGER NOT NULL, verdict TEXT NOT NULL, signature TEXT,
  log_sha256 TEXT NOT NULL, at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS cre_prevention_tests (test_id TEXT PRIMARY KEY, capa_id TEXT NOT NULL,
  reproducer_id TEXT NOT NULL, registered_at TEXT NOT NULL, registered_revision TEXT NOT NULL);
""" + _append_only("cre_capa_history") + _append_only("cre_reproducer_runs") + _append_only("cre_prevention_tests")),
    (4, "D4 benchmark runs, promotion decisions, rollbacks", """
CREATE TABLE IF NOT EXISTS cre_benchmark_runs (run_id TEXT PRIMARY KEY, suite_sha256 TEXT NOT NULL,
  revision TEXT NOT NULL, record TEXT NOT NULL, at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS cre_promotion_decisions (decision_id TEXT PRIMARY KEY, candidate TEXT NOT NULL,
  baseline TEXT NOT NULL, decision TEXT NOT NULL, record TEXT NOT NULL, at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS cre_rollbacks (seq INTEGER PRIMARY KEY AUTOINCREMENT, subject TEXT NOT NULL,
  from_ref TEXT NOT NULL, to_ref TEXT NOT NULL, reason TEXT NOT NULL, retracted_lessons TEXT NOT NULL, at TEXT NOT NULL);
""" + _append_only("cre_benchmark_runs") + _append_only("cre_promotion_decisions") + _append_only("cre_rollbacks")),
    (5, "D1 auditable retraction of observations superseded by a newer classifier version", """
CREATE TABLE IF NOT EXISTS cre_observation_retractions (obs_id TEXT PRIMARY KEY, reason TEXT NOT NULL,
  classifier_version TEXT NOT NULL, at TEXT NOT NULL);
""" + _append_only("cre_observation_retractions")),
    (6, "D3 CAPA links (fingerprints, revisions, observations, lessons) and lesson links", """
CREATE TABLE IF NOT EXISTS cre_capa_links (seq INTEGER PRIMARY KEY AUTOINCREMENT, capa_id TEXT NOT NULL,
  kind TEXT NOT NULL, ref TEXT NOT NULL, at TEXT NOT NULL, UNIQUE(capa_id, kind, ref));
""" + _append_only("cre_capa_links")),
]
SCHEMA_VERSION = max(v for v, _, _ in MIGRATIONS)


class CREStore:
    """CRE state inside the 002 incident database (default state/supervisor/incidents.sqlite3)."""

    def __init__(self, path: Path | None = None):
        self.path = path or state_dir() / "supervisor" / "incidents.sqlite3"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.migrate()

    @contextmanager
    def conn(self):
        c = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA busy_timeout=30000")
        c.execute("PRAGMA synchronous=FULL")
        try:
            yield c
        finally:
            c.close()

    def migrate(self) -> list[int]:
        applied = []
        with self.conn() as c:
            c.execute("PRAGMA journal_mode=WAL")
            c.execute("CREATE TABLE IF NOT EXISTS cre_schema_version (version INTEGER PRIMARY KEY, description TEXT "
                      "NOT NULL, applied_at TEXT NOT NULL)")
            have = {r[0] for r in c.execute("SELECT version FROM cre_schema_version")}
            for v, desc, sql in MIGRATIONS:
                if v in have:
                    continue
                c.execute("BEGIN IMMEDIATE")
                try:
                    for stmt in _statements(sql):
                        c.execute(stmt)
                    c.execute("INSERT INTO cre_schema_version VALUES (?,?,?)", (v, desc, utc_now()))
                    c.execute("COMMIT")
                except Exception:
                    c.execute("ROLLBACK")
                    raise
                applied.append(v)
        return applied

    def version(self) -> int:
        with self.conn() as c:
            r = c.execute("SELECT max(version) FROM cre_schema_version").fetchone()
        return int(r[0] or 0)

    # -- events ---------------------------------------------------------------------------
    def insert_event(self, ev: dict) -> bool:
        with self.conn() as c:
            cur = c.execute("INSERT OR IGNORE INTO cre_events(event_id,type,ts_utc,record) VALUES (?,?,?,?)",
                            (ev["event_id"], ev["type"], ev["ts_utc"], canonical_json(ev).decode()))
            return cur.rowcount == 1

    def events(self, type_: str | None = None) -> list[dict]:
        q, a = "SELECT record FROM cre_events", ()
        if type_:
            q, a = q + " WHERE type=?", (type_,)
        with self.conn() as c:
            return [json.loads(r[0]) for r in c.execute(q + " ORDER BY ts_utc, event_id", a)]

    def get_event(self, event_id: str) -> dict | None:
        with self.conn() as c:
            r = c.execute("SELECT record FROM cre_events WHERE event_id=?", (event_id,)).fetchone()
        return json.loads(r[0]) if r else None

    # -- observations ---------------------------------------------------------------------
    OBS_COLS = ("obs_id", "fingerprint", "failure_class", "category", "component", "error_code", "operation",
                "order_id", "attempt_id", "run_id", "phase", "ts_utc", "disposition", "outcome", "cohort",
                "factory_version", "source_ref", "evidence_sha256", "excerpt")

    def insert_observation(self, o: dict) -> bool:
        with self.conn() as c:
            cur = c.execute(f"INSERT OR IGNORE INTO cre_failure_observations({','.join(self.OBS_COLS)}) "  # noqa: S608
                            f"VALUES ({','.join('?' * len(self.OBS_COLS))})", tuple(o.get(k) for k in self.OBS_COLS))
            return cur.rowcount == 1

    def observations(self, fingerprint: str | None = None, include_retracted: bool = False) -> list[dict]:
        q, a = "SELECT * FROM cre_failure_observations o WHERE 1=1", ()
        if not include_retracted:
            q += " AND obs_id NOT IN (SELECT obs_id FROM cre_observation_retractions)"
        if fingerprint:
            q, a = q + " AND fingerprint=?", (fingerprint,)
        with self.conn() as c:
            return [dict(r) for r in c.execute(q + " ORDER BY ts_utc, obs_id", a)]

    def retract_observation(self, obs_id: str, reason: str, classifier_version: str) -> bool:
        """Observations are immutable; a superseded one is retracted by an append-only record (never deleted)."""
        with self.conn() as c:
            return c.execute("INSERT OR IGNORE INTO cre_observation_retractions VALUES (?,?,?,?)",
                             (obs_id, reason[:300], classifier_version, utc_now())).rowcount == 1

    def retractions(self) -> list[dict]:
        with self.conn() as c:
            return [dict(r) for r in c.execute("SELECT * FROM cre_observation_retractions ORDER BY at, obs_id")]

    MODE_COLS = ("fingerprint", "failure_class", "category", "component", "error_code", "operation", "first_seen",
                 "last_seen", "occurrences", "distinct_attempts", "distinct_orders", "recurring", "significant",
                 "root_cause_status", "root_cause_hypothesis", "verified_root_cause", "capa_id", "data_quality")

    def failure_modes(self) -> list[dict]:
        with self.conn() as c:
            return [dict(r) for r in c.execute("SELECT * FROM cre_failure_modes ORDER BY occurrences DESC, fingerprint")]

    def replace_failure_modes(self, rows: list[dict]) -> None:
        """Projection rebuild (failure modes are derived from the append-only observations; ADR-CRE-003)."""
        with self.conn() as c:
            keep = {r["fingerprint"]: r for r in c.execute(
                "SELECT fingerprint, root_cause_status, root_cause_hypothesis, verified_root_cause, capa_id "
                "FROM cre_failure_modes")}
            c.execute("BEGIN IMMEDIATE")
            c.execute("DELETE FROM cre_failure_modes")
            for r in rows:
                k = keep.get(r["fingerprint"])
                if k is not None:  # analysis results are not observations: preserve them across rebuilds
                    r = {**r, "root_cause_status": k["root_cause_status"],
                         "root_cause_hypothesis": k["root_cause_hypothesis"],
                         "verified_root_cause": k["verified_root_cause"], "capa_id": k["capa_id"]}
                cols = [k2 for k2 in self.MODE_COLS if k2 in r]  # fixed column whitelist, never caller-chosen names
                c.execute(f"INSERT INTO cre_failure_modes({','.join(cols)}) VALUES ({','.join('?' * len(cols))})",  # noqa: S608
                          tuple(r[k2] for k2 in cols))
            c.execute("COMMIT")

    def set_root_cause(self, fingerprint: str, status: str, hypothesis: str | None = None,
                       verified: str | None = None, capa_id: str | None = None) -> None:
        if status not in ("UNKNOWN", "HYPOTHESIS", "VERIFIED"):
            raise ValueError(status)
        with self.conn() as c:
            c.execute("UPDATE cre_failure_modes SET root_cause_status=?, root_cause_hypothesis=coalesce(?, "
                      "root_cause_hypothesis), verified_root_cause=coalesce(?, verified_root_cause), "
                      "capa_id=coalesce(?, capa_id) WHERE fingerprint=?", (status, hypothesis, verified, capa_id,
                                                                            fingerprint))

    def add_alias(self, from_fp: str, to_fp: str, kind: str, reason: str, actor: str) -> None:
        with self.conn() as c:
            c.execute("INSERT INTO cre_fingerprint_aliases(from_fp,to_fp,kind,reason,actor,at) VALUES (?,?,?,?,?,?)",
                      (from_fp, to_fp, kind, reason, actor, utc_now()))

    def aliases(self) -> list[dict]:
        with self.conn() as c:
            return [dict(r) for r in c.execute("SELECT * FROM cre_fingerprint_aliases ORDER BY seq")]


def _statements(sql: str) -> list[str]:
    """Split a migration script into statements (triggers contain ';' inside BEGIN..END)."""
    out, buf, depth = [], [], 0
    for line in sql.splitlines():
        if not line.strip():
            continue
        buf.append(line)
        depth += line.upper().count(" BEGIN ") + line.upper().rstrip().endswith(" BEGIN")
        if line.rstrip().endswith("END;"):
            depth = 0
        if line.rstrip().endswith(";") and depth == 0:
            out.append("\n".join(buf))
            buf = []
    if buf:
        out.append("\n".join(buf))
    return out
