"""AFO M2 (T016-T019, T022, T025; AFO-FR-017..023, 036) - the Conductor's durable store.

$FORGE_STATE_DIR/conductor/conductor.sqlite3, SQLite WAL + synchronous=FULL + busy timeout, versioned additive
migrations. Authority for AFO queue state only: 002 incidents and 004 CRE records are referenced by id, never
mirrored.
  * Orders: id = afo-<sha256(tenant|request)>; immutable request/manifest hash; same request + same hash returns the
    same order (idempotent submit), a different hash is a CONFLICT (409). Initial state QUEUED after intake checks.
  * Transitions: only the edges of contracts/queue-fsm.yaml, compare-and-swap on `version`; a denied transition is
    an audited `transition_denied` event; a repeated transition to the current state is a no-op.
  * Leases: BEGIN IMMEDIATE compare-and-swap, monotonically increasing fencing epoch on takeover; commands carry the
    epoch and are refused when it is stale.
  * Outbox: commands unique by (kind, idempotency_key) - enqueue is idempotent; external delivery is at-least-once,
    state PENDING until an authoritative acknowledgement (never claimed exactly-once).
  * Events: append-only, event_id derived from content, INSERT OR IGNORE (replay-safe); forwarded once to the
    002 event ledger, channel `workflow`, correlated by order id (`forward_events`).
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path

from ..common import canonical_json, sha256_bytes, state_dir, utc_now
from . import contracts
from .durable import MIGRATION as DURABLE_MIGRATION

PRIORITY = {"LOW": 0, "NORMAL": 1, "HIGH": 2}
ACTIVE_STATES = ("ADMITTED", "RUNNING", "WAITING_RECOVERY", "VALIDATING")
MIGRATIONS = [
    # v1 - AFO-T016
    """
    CREATE TABLE afo_work_orders (
      order_id TEXT PRIMARY KEY, tenant_scope TEXT NOT NULL, request_id TEXT NOT NULL, manifest_sha256 TEXT NOT NULL,
      input_manifest_ref TEXT NOT NULL, envelope TEXT NOT NULL, priority TEXT NOT NULL, state TEXT NOT NULL,
      version INTEGER NOT NULL DEFAULT 1, created_utc TEXT NOT NULL, created_epoch REAL NOT NULL,
      admitted_utc TEXT, not_before_epoch REAL NOT NULL DEFAULT 0, defer_count INTEGER NOT NULL DEFAULT 0,
      policy_sha256 TEXT, authorization_id TEXT, fencing_epoch INTEGER, terminal_reason TEXT,
      UNIQUE (tenant_scope, request_id));
    CREATE TABLE afo_attempts (
      attempt_id TEXT PRIMARY KEY, order_id TEXT NOT NULL REFERENCES afo_work_orders(order_id), seq INTEGER NOT NULL,
      state TEXT NOT NULL, record TEXT NOT NULL, created_utc TEXT NOT NULL, finished_utc TEXT,
      UNIQUE (order_id, seq));
    CREATE TABLE afo_leases (scope TEXT PRIMARY KEY, owner_id TEXT NOT NULL, epoch INTEGER NOT NULL,
      expires_epoch REAL NOT NULL, heartbeat_epoch REAL NOT NULL);
    CREATE TABLE afo_commands_outbox (
      command_id TEXT PRIMARY KEY, kind TEXT NOT NULL, idempotency_key TEXT NOT NULL, order_id TEXT NOT NULL,
      attempt_id TEXT, fencing_epoch INTEGER NOT NULL, payload TEXT NOT NULL, state TEXT NOT NULL,
      created_utc TEXT NOT NULL, ack_ref TEXT, attempts INTEGER NOT NULL DEFAULT 0, retry_not_before_epoch REAL,
      UNIQUE (kind, idempotency_key));
    CREATE TABLE afo_lifecycle_events (
      seq INTEGER PRIMARY KEY AUTOINCREMENT, event_id TEXT UNIQUE NOT NULL, occurred_utc TEXT NOT NULL,
      type TEXT NOT NULL, order_id TEXT NOT NULL, attempt_id TEXT, record TEXT NOT NULL, forwarded INTEGER NOT NULL DEFAULT 0);
    CREATE TABLE afo_control (key TEXT PRIMARY KEY, value TEXT NOT NULL, updated_utc TEXT NOT NULL, actor TEXT NOT NULL);
    CREATE TABLE afo_operator_actions (
      seq INTEGER PRIMARY KEY AUTOINCREMENT, action TEXT NOT NULL, actor TEXT NOT NULL, reason TEXT NOT NULL,
      utc TEXT NOT NULL);
    """,
    # v2 - AFO-T030: immutable accepted-phase checkpoints with their upstream dependency hashes
    """
    CREATE TABLE afo_checkpoints (
      checkpoint_id TEXT PRIMARY KEY, order_id TEXT NOT NULL, attempt_id TEXT NOT NULL, phase TEXT NOT NULL,
      baseline_hash TEXT NOT NULL, upstream TEXT NOT NULL, inspection_ref TEXT NOT NULL, frozen_utc TEXT NOT NULL,
      recorded_utc TEXT NOT NULL, UNIQUE (attempt_id, phase, baseline_hash));
    """,
    # v3 - AFO-T048/T051: append-only Factory Maintainer proposal records (the database refuses UPDATE/DELETE) and
    # the moment an order started waiting for an external factory change (bounded TTL)
    """
    CREATE TABLE afo_maintainer_proposals (
      seq INTEGER PRIMARY KEY AUTOINCREMENT, proposal_id TEXT NOT NULL, order_id TEXT, status TEXT NOT NULL,
      record TEXT NOT NULL, record_sha256 TEXT NOT NULL, recorded_utc TEXT NOT NULL);
    CREATE TRIGGER afo_proposals_no_update BEFORE UPDATE ON afo_maintainer_proposals
      BEGIN SELECT RAISE(ABORT, 'APPEND_ONLY'); END;
    CREATE TRIGGER afo_proposals_no_delete BEFORE DELETE ON afo_maintainer_proposals
      BEGIN SELECT RAISE(ABORT, 'APPEND_ONLY'); END;
    ALTER TABLE afo_work_orders ADD COLUMN waiting_since_epoch REAL;
    """,
    # v4 - AFO-T054/T055: one immutable dead-letter case per (order, reason) and a deduplicated notification outbox
    """
    CREATE TABLE afo_dead_letters (
      case_id TEXT PRIMARY KEY, order_id TEXT NOT NULL, attempt_id TEXT, reason_code TEXT NOT NULL,
      record TEXT NOT NULL, record_sha256 TEXT NOT NULL, state TEXT NOT NULL, recorded_utc TEXT NOT NULL,
      UNIQUE (order_id, reason_code));
    CREATE TRIGGER afo_dlq_immutable BEFORE UPDATE OF case_id, order_id, attempt_id, reason_code, record, record_sha256,
      recorded_utc ON afo_dead_letters BEGIN SELECT RAISE(ABORT, 'IMMUTABLE_DEAD_LETTER'); END;
    CREATE TRIGGER afo_dlq_no_delete BEFORE DELETE ON afo_dead_letters
      BEGIN SELECT RAISE(ABORT, 'IMMUTABLE_DEAD_LETTER'); END;
    CREATE TABLE afo_notifications (
      notification_id TEXT PRIMARY KEY, dedupe_key TEXT UNIQUE NOT NULL, delivery_state TEXT NOT NULL,
      channel TEXT NOT NULL, severity TEXT NOT NULL, first_utc TEXT NOT NULL, last_utc TEXT NOT NULL,
      count INTEGER NOT NULL, payload TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0,
      next_epoch REAL NOT NULL DEFAULT 0, delivered_utc TEXT);
    """,
]
MIGRATIONS.append(DURABLE_MIGRATION)
MIGRATIONS.append("CREATE TABLE afo_product_jobs (job_id TEXT PRIMARY KEY,record TEXT NOT NULL);")
MIGRATIONS.append(
    "CREATE TABLE afo_mission_counters "
    "(event_id TEXT PRIMARY KEY,mission_id TEXT NOT NULL,job_id TEXT NOT NULL,kind TEXT NOT NULL);"
)
MIGRATIONS.append(
    "CREATE TABLE afo_execution_evidence "
    "(job_id TEXT NOT NULL,kind TEXT NOT NULL,record TEXT NOT NULL,sha256 TEXT NOT NULL,PRIMARY KEY(job_id,kind));"
)

# DISPATCH_PENDING/UNKNOWN -> PREPARED only when reconciliation PROVES the launch never reached Fabro (ADR-AFO-002)
ATTEMPT_EDGES = {
    "PREPARED": {"DISPATCH_PENDING", "CANCELLED"},
    "DISPATCH_PENDING": {"RUNNING", "UNKNOWN", "FAILED", "PREPARED"},
    "RUNNING": {"SUCCEEDED", "FAILED", "CANCELLED", "UNKNOWN"},
    "UNKNOWN": {"RUNNING", "SUCCEEDED", "FAILED", "CANCELLED", "PREPARED"},
}

# Local-agent storage was historically created lazily by prepare()/records().
# Continuous disabled/empty-queue supervision must be able to capture outcomes
# before any model job has ever been prepared. Preserve all legacy rows in place.
MIGRATIONS.append("""CREATE TABLE IF NOT EXISTS afo_local_agent_jobs (
 job_id TEXT PRIMARY KEY, order_id TEXT NOT NULL, attempt_id TEXT NOT NULL, role TEXT NOT NULL,
 state TEXT NOT NULL, record TEXT NOT NULL, UNIQUE(attempt_id, role));""")


class QueueError(ValueError):
    def __init__(self, code: str, detail: str = "", audit: tuple | None = None):
        super().__init__(f"{code}:{detail}" if detail else code)
        self.code, self.detail, self.audit = code, detail, audit  # audit: event to keep although the tx rolls back


def default_path() -> Path:
    return state_dir() / "conductor/conductor.sqlite3"


def order_id_for(tenant: str, request_id: str) -> str:
    return "afo-" + hashlib.sha256(f"{tenant}|{request_id}".encode()).hexdigest()[:16]


class Store:
    def __init__(self, path: Path | None = None, producer: str = "afo-conductor"):
        self.path = Path(path or default_path())
        import os

        if os.environ.get("FORGE_DURABLE_AUTONOMY") == "1":
            from .host import preflight

            if not preflight()["ok"]:
                raise QueueError("DURABLE_DATA_VOLUME_NOT_READY")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.producer = producer
        with self.tx() as c:
            c.execute("CREATE TABLE IF NOT EXISTS afo_schema_version (version INTEGER NOT NULL, applied_utc TEXT NOT NULL)")
            have = c.execute("SELECT COALESCE(MAX(version), 0) FROM afo_schema_version").fetchone()[0]
            for v, sql in enumerate(MIGRATIONS, 1):
                if v > have:
                    # one statement per line end ';' (trigger bodies keep their inner '; ' on one line)
                    for stmt in (s for s in re.split(r";[ \t]*\n", sql) if s.strip()):  # inside the IMMEDIATE tx
                        c.execute(stmt)
                    c.execute("INSERT INTO afo_schema_version VALUES (?, ?)", (v, utc_now()))
        self.path.chmod(0o600)

    def connect(self) -> sqlite3.Connection:
        import os

        if os.environ.get("FORGE_DURABLE_AUTONOMY") == "1":
            from ..common import data_root

            if hasattr(self, "_data_device") and data_root().stat().st_dev != self._data_device:
                raise QueueError("AUTHORITATIVE_DATA_DEVICE_CHANGED")
            self._data_device = data_root().stat().st_dev
        c = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA journal_mode=WAL")
        c.execute("PRAGMA synchronous=FULL")
        c.execute("PRAGMA busy_timeout=10000")
        c.execute("PRAGMA foreign_keys=ON")
        return c

    @contextmanager
    def tx(self):
        """BEGIN IMMEDIATE: one writer at a time, serialised across processes."""
        c = self.connect()
        try:  # AFO-T065 (DB lock): a BEGIN that fails holds no transaction - report the lock, not a failed ROLLBACK
            c.execute("BEGIN IMMEDIATE")
        except BaseException:
            c.close()
            raise
        try:
            yield c
            c.execute("COMMIT")
        except QueueError as e:
            c.execute("ROLLBACK")
            if e.audit:  # a refusal is evidence: record it in its own transaction after the rollback
                c.execute("BEGIN IMMEDIATE")
                self._event(c, *e.audit)
                c.execute("COMMIT")
            raise
        except BaseException:
            c.execute("ROLLBACK")
            raise
        finally:
            c.close()

    def schema_version(self) -> int:
        with self.tx() as c:
            return c.execute("SELECT MAX(version) FROM afo_schema_version").fetchone()[0]

    # -- events (T018) -------------------------------------------------------------------------------------------
    def _event(
        self, c, etype: str, order_id: str, attempt_id: str | None = None, payload: dict | None = None, severity: str = "INFO"
    ) -> str:
        payload = payload or {}
        etype = "afo." + re.sub(r"[^a-z0-9_]+", "_", etype.lower()).strip("_")  # contract: ^afo\.[a-z0-9_]+$
        psha = sha256_bytes(canonical_json(payload))
        n = c.execute("SELECT COUNT(*) FROM afo_lifecycle_events WHERE order_id=?", (order_id,)).fetchone()[0]
        eid = "afo-ev-" + sha256_bytes(canonical_json([etype, order_id, attempt_id, psha, n]))[:24]
        rec = {
            "schema_version": "1.0",
            "event_id": eid,
            "occurred_utc": utc_now(),
            "type": etype,
            "order_id": order_id,
            "attempt_id": attempt_id,
            "producer_id": self.producer,
            "correlation_id": order_id,
            "payload_sha256": psha,
            "severity": severity,
            "privacy": "INTERNAL",
            "evidence_refs": [],
        }
        contracts.require("queue-event", rec)
        c.execute(
            "INSERT OR IGNORE INTO afo_lifecycle_events (event_id, occurred_utc, type, order_id, attempt_id, record)"
            " VALUES (?,?,?,?,?,?)",
            (eid, rec["occurred_utc"], etype, order_id, attempt_id, json.dumps({**rec, "payload": payload})),
        )
        return eid

    def events(self, order_id: str | None = None) -> list[dict]:
        with self.tx() as c:
            q = "SELECT record FROM afo_lifecycle_events" + (" WHERE order_id=?" if order_id else "") + " ORDER BY seq"  # noqa: S608 - fixed SQL text, values bound
            return [json.loads(r["record"]) for r in c.execute(q, (order_id,) if order_id else ())]

    def forward_events(self, emit=None) -> int:
        """Bridge to the 002 event ledger, once per event (forwarded flag set in the same transaction)."""
        from ..events.emit import emit as emit_default

        emit = emit or emit_default
        n = 0
        with self.tx() as c:
            for r in c.execute("SELECT seq, record FROM afo_lifecycle_events WHERE forwarded=0 ORDER BY seq").fetchall():
                rec = json.loads(r["record"])
                emit(
                    "workflow",
                    "INFO" if rec["severity"] in ("DEBUG", "INFO") else "WARN",
                    f"afo {rec['type']} {rec['order_id']}",
                    correlation_id=rec["order_id"],
                    payload_ref=rec["event_id"],
                )
                c.execute("UPDATE afo_lifecycle_events SET forwarded=1 WHERE seq=?", (r["seq"],))
                n += 1
        return n

    # -- intake (T017, T022) -------------------------------------------------------------------------------------
    def submit(self, env: dict, *, repo: Path, max_queued: int, approve=None) -> tuple[str, bool]:
        """Returns (order_id, created). Raises QueueError(REJECTED_INTAKE codes / CONFLICT)."""
        errs = contracts.errors("work-order", env)
        if errs:
            raise QueueError("INTAKE_SCHEMA", errs[0])
        mpath = (repo / env["input_manifest_ref"]).resolve()
        if repo.resolve() not in mpath.parents or not mpath.is_file():
            raise QueueError("INTAKE_MANIFEST_MISSING", env["input_manifest_ref"])
        if hashlib.sha256(mpath.read_bytes()).hexdigest() != env["manifest_sha256"]:
            raise QueueError("INTAKE_MANIFEST_HASH_MISMATCH", env["input_manifest_ref"])
        if approve is not None:
            ok, code = approve(env)
            if not ok:
                raise QueueError("INTAKE_NOT_APPROVED", code)
        oid = order_id_for(env["tenant_scope"], env["request_id"])
        with self.tx() as c:
            row = c.execute("SELECT manifest_sha256 FROM afo_work_orders WHERE order_id=?", (oid,)).fetchone()
            if row is not None:
                if row["manifest_sha256"] != env["manifest_sha256"]:
                    raise QueueError(
                        "CONFLICT",
                        f"{env['request_id']} already submitted with another manifest",
                        ("intake_conflict", oid, None, {"manifest_sha256": env["manifest_sha256"]}, "WARN"),
                    )
                return oid, False
            queued = c.execute("SELECT COUNT(*) FROM afo_work_orders WHERE state IN ('QUEUED','PAUSED')").fetchone()[0]
            if queued >= max_queued:
                raise QueueError("INTAKE_BACKLOG_FULL", f"{queued} >= {max_queued}")
            now = time.time()
            c.execute(
                "INSERT INTO afo_work_orders (order_id, tenant_scope, request_id, manifest_sha256, input_manifest_ref,"
                " envelope, priority, state, created_utc, created_epoch) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    oid,
                    env["tenant_scope"],
                    env["request_id"],
                    env["manifest_sha256"],
                    env["input_manifest_ref"],
                    json.dumps(env, sort_keys=True),
                    env.get("priority", "NORMAL"),
                    "SUBMITTED",
                    utc_now(),
                    now,
                ),
            )
            self._event(c, "submitted", oid, payload={"request_id": env["request_id"]})
            self._transition(c, oid, "QUEUED", "intake checks passed")
        return oid, True

    # -- order transitions (T019) --------------------------------------------------------------------------------
    def _transition(self, c, oid: str, to: str, reason: str, expect_version: int | None = None, **fields) -> bool:
        row = c.execute("SELECT state, version FROM afo_work_orders WHERE order_id=?", (oid,)).fetchone()
        if row is None:
            raise QueueError("NO_SUCH_ORDER", oid)
        if row["state"] == to:
            return False  # idempotent no-op, no duplicate event
        allowed = contracts.fsm()["allowed_order_edges"].get(row["state"], [])
        if to not in allowed or (expect_version is not None and expect_version != row["version"]):
            raise QueueError(
                "TRANSITION_DENIED",
                f"{row['state']}->{to}",
                (
                    "transition_denied",
                    oid,
                    None,
                    {"from": row["state"], "to": to, "reason": reason, "version": row["version"]},
                    "WARN",
                ),
            )
        if to == "WAITING_EXTERNAL_CHANGE":  # AFO-T051: the TTL runs from here
            fields.setdefault("waiting_since_epoch", time.time())
        if to == "QUALIFICATION_RECORDED":
            from .qualification_state import can_close

            if not can_close(c, oid):
                raise QueueError("QUALIFICATION_RESULT_AND_QUIESCENCE_REQUIRED", oid)
        sets = ", ".join(["state=?", "version=version+1"] + [f"{k}=?" for k in fields])
        n = c.execute(
            f"UPDATE afo_work_orders SET {sets} WHERE order_id=? AND version=?",  # noqa: S608
            (to, *fields.values(), oid, row["version"]),
        ).rowcount
        if n != 1:
            raise QueueError("CAS_LOST", oid)
        self._event(c, f"state:{to}", oid, payload={"from": row["state"], "reason": reason})
        return True

    def transition(self, oid: str, to: str, reason: str, expect_version: int | None = None, **fields) -> bool:
        with self.tx() as c:
            return self._transition(c, oid, to, reason, expect_version, **fields)

    def order(self, oid: str) -> dict | None:
        with self.tx() as c:
            r = c.execute("SELECT * FROM afo_work_orders WHERE order_id=?", (oid,)).fetchone()
            return dict(r) if r else None

    def orders(self, states: tuple[str, ...] | None = None) -> list[dict]:
        with self.tx() as c:
            q = "SELECT * FROM afo_work_orders" + (f" WHERE state IN ({','.join('?' * len(states))})" if states else "")  # noqa: S608 - fixed SQL text, values bound
            return [dict(r) for r in c.execute(q + " ORDER BY created_epoch", states or ())]

    # -- leases and fencing (T019) -------------------------------------------------------------------------------
    def acquire_lease(self, scope: str, owner: str, ttl: float, now: float | None = None) -> int | None:
        now = now or time.time()
        with self.tx() as c:
            r = c.execute("SELECT * FROM afo_leases WHERE scope=?", (scope,)).fetchone()
            if r is None:
                c.execute("INSERT INTO afo_leases VALUES (?,?,?,?,?)", (scope, owner, 1, now + ttl, now))
                return 1
            if r["owner_id"] == owner and r["expires_epoch"] > now:
                c.execute("UPDATE afo_leases SET expires_epoch=?, heartbeat_epoch=? WHERE scope=?", (now + ttl, now, scope))
                return r["epoch"]
            if r["expires_epoch"] <= now:  # takeover after expiry: new epoch fences the old holder out
                c.execute(
                    "UPDATE afo_leases SET owner_id=?, epoch=epoch+1, expires_epoch=?, heartbeat_epoch=? WHERE scope=?",
                    (owner, now + ttl, now, scope),
                )
                return r["epoch"] + 1
            return None

    def fence_ok(self, c, scope: str, epoch: int) -> bool:
        r = c.execute("SELECT epoch FROM afo_leases WHERE scope=?", (scope,)).fetchone()
        return r is not None and r["epoch"] == epoch

    # -- outbox (T018) -------------------------------------------------------------------------------------------
    def _enqueue(self, c, kind: str, idem: str, oid: str, attempt_id: str | None, epoch: int, payload: dict) -> str:
        from .operations import Intent, configured

        if kind == "FABRO_LAUNCH" and configured():
            intent = Intent().read()
            if intent["mode"] != "RUNNING":
                raise QueueError("OPERATIONS_ADMISSION_FENCED")
            payload = {**payload, "operations_epoch": intent["epoch"]}
        cid = "afo-cmd-" + sha256_bytes(canonical_json([kind, idem]))[:20]
        rec = {
            "schema_version": "1.0",
            "command_id": cid,
            "idempotency_key": idem,
            "command_type": kind,
            "order_id": oid,
            "attempt_id": attempt_id,
            "fencing_epoch": epoch,
            "state": "PENDING",
            "created_utc": utc_now(),
            "payload_ref": f"inline:{sha256_bytes(canonical_json(payload))[:16]}",
            "ack_ref": None,
            "retry_not_before_utc": None,
            "attempts": 0,
        }
        contracts.require("outbox-command", rec)
        cur = c.execute(
            "INSERT OR IGNORE INTO afo_commands_outbox (command_id, kind, idempotency_key, order_id, attempt_id,"
            " fencing_epoch, payload, state, created_utc) VALUES (?,?,?,?,?,?,?,?,?)",
            (cid, kind, idem, oid, attempt_id, epoch, json.dumps(payload), "PENDING", rec["created_utc"]),
        )
        if cur.rowcount:
            self._event(c, f"command:{kind}", oid, attempt_id, {"command_id": cid, "idempotency_key": idem})
        return cid

    def commands(self, state: str | None = None) -> list[dict]:
        with self.tx() as c:
            q = "SELECT * FROM afo_commands_outbox" + (" WHERE state=?" if state else "") + " ORDER BY created_utc"  # noqa: S608 - fixed SQL text, values bound
            return [dict(r) for r in c.execute(q, (state,) if state else ())]

    def mark_command(self, cid: str, state: str, ack_ref: str | None = None) -> None:
        with self.tx() as c:
            c.execute(
                "UPDATE afo_commands_outbox SET state=?, ack_ref=COALESCE(?, ack_ref), attempts=attempts+1 WHERE command_id=?",
                (state, ack_ref, cid),
            )

    # -- control (pause/drain) and operator actions (T023) --------------------------------------------------------
    def set_control(self, key: str, value: str, actor: str, reason: str) -> None:
        with self.tx() as c:
            c.execute(
                "INSERT INTO afo_control VALUES (?,?,?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value,"
                " updated_utc=excluded.updated_utc, actor=excluded.actor",
                (key, value, utc_now(), actor),
            )
            c.execute(
                "INSERT INTO afo_operator_actions (action, actor, reason, utc) VALUES (?,?,?,?)",
                (f"{key}={value}", actor, reason, utc_now()),
            )

    def control(self) -> dict:
        with self.tx() as c:
            return {r["key"]: r["value"] for r in c.execute("SELECT key, value FROM afo_control")}

    # -- scheduler (T020) and admission (T021/T022) --------------------------------------------------------------
    def next_candidate(self, aging_s: float, now: float | None = None) -> dict | None:
        """FIFO with priority aging: effective = base priority + waited/aging_s; ties by submission time."""
        now = now or time.time()
        cands = [o for o in self.orders(("QUEUED",)) if o["not_before_epoch"] <= now]
        if not cands:
            return None
        return max(cands, key=lambda o: (PRIORITY[o["priority"]] + (now - o["created_epoch"]) / aging_s, -o["created_epoch"]))

    def admit(
        self,
        oid: str,
        *,
        epoch: int,
        scope: str,
        policy_sha256: str,
        authorization_id: str | None,
        max_concurrent: int,
        qualification_ref: str | None = None,
    ) -> str:
        """QUEUED -> ADMITTED and the FABRO_LAUNCH intent for attempt seq 1+, atomically, under the fencing epoch."""
        if qualification_ref is not None and (
            not isinstance(qualification_ref, str) or not re.fullmatch(r"qualification-014:[0-9a-f]{64}", qualification_ref)
        ):
            raise QueueError("QUALIFICATION_ADMISSION_REFERENCE_INVALID")
        with self.tx() as c:
            if not self.fence_ok(c, scope, epoch):
                raise QueueError("FENCED", f"epoch {epoch} is stale")
            busy = c.execute(
                f"SELECT COUNT(*) FROM afo_work_orders WHERE state IN ({','.join('?' * len(ACTIVE_STATES))})",  # noqa: S608 - fixed SQL text, values bound
                ACTIVE_STATES,
            ).fetchone()[0]
            if busy >= max_concurrent:
                raise QueueError("CAPACITY", f"{busy} active >= {max_concurrent}")
            if self.control_in(c).get("paused") == "1" or self.control_in(c).get("draining") == "1":
                raise QueueError("PAUSED")
            self._transition(
                c,
                oid,
                "ADMITTED",
                "scheduler admission",
                admitted_utc=utc_now(),
                fencing_epoch=epoch,
                policy_sha256=policy_sha256,
                authorization_id=authorization_id,
            )
            seq = c.execute("SELECT COALESCE(MAX(seq), 0) + 1 FROM afo_attempts WHERE order_id=?", (oid,)).fetchone()[0]
            aid = f"{oid}-a{seq}"
            rec = {
                "schema_version": "1.0",
                "order_id": oid,
                "attempt_id": aid,
                "attempt_seq": seq,
                "state": "PREPARED",
                "workspace_ref": f"pending:{aid}",
                "factory_revision": "pending",
                "created_utc": utc_now(),
                "fabro_run_id": None,
                "fabro_server": None,
                "recovery_plan_id": None,
                "exit_status": None,
                "terminal_package_status": None,
                "checkpoint_refs": [],
                "evidence_refs": [qualification_ref] if qualification_ref else [],
                "finished_utc": None,
            }
            contracts.require("attempt", rec)
            c.execute(
                "INSERT INTO afo_attempts (attempt_id, order_id, seq, state, record, created_utc) VALUES (?,?,?,?,?,?)",
                (aid, oid, seq, "PREPARED", json.dumps(rec), rec["created_utc"]),
            )
            if qualification_ref:
                self._event(
                    c,
                    "qualification_admitted",
                    oid,
                    aid,
                    {"qualification_ref": qualification_ref, "purpose": "ROLE_PROTOCOL_FIXTURE_NO_PRODUCT_LAUNCH"},
                )
            else:
                self._enqueue(c, "FABRO_LAUNCH", f"launch:{aid}", oid, aid, epoch, {"attempt_id": aid})
            return aid

    @staticmethod
    def control_in(c) -> dict:
        return {r["key"]: r["value"] for r in c.execute("SELECT key, value FROM afo_control")}

    def defer(self, oid: str, reason: str, base_s: float = 60, cap_s: float = 3600, now: float | None = None) -> float:
        """Unavailable dependency: keep QUEUED, back off exponentially (bounded), record why."""
        now = now or time.time()
        with self.tx() as c:
            n = c.execute("SELECT defer_count FROM afo_work_orders WHERE order_id=?", (oid,)).fetchone()[0]
            wait = min(cap_s, base_s * 2 ** min(n, 16))
            c.execute(
                "UPDATE afo_work_orders SET not_before_epoch=?, defer_count=defer_count+1 WHERE order_id=?", (now + wait, oid)
            )
            self._event(c, "deferred", oid, payload={"reason": reason[:200], "wait_s": wait}, severity="WARN")
        return wait

    def attempts(self, oid: str) -> list[dict]:
        with self.tx() as c:
            return [
                {**dict(r), "record": json.loads(r["record"])}
                for r in c.execute("SELECT * FROM afo_attempts WHERE order_id=? ORDER BY seq", (oid,))
            ]

    def attempt_transition(self, aid: str, to: str, **record_fields) -> None:
        with self.tx() as c:
            r = c.execute("SELECT * FROM afo_attempts WHERE attempt_id=?", (aid,)).fetchone()
            if r is None:
                raise QueueError("NO_SUCH_ATTEMPT", aid)
            if r["state"] == to:
                return
            if to not in ATTEMPT_EDGES.get(r["state"], set()):
                raise QueueError(
                    "ATTEMPT_TRANSITION_DENIED",
                    f"{r['state']}->{to}",
                    ("attempt_transition_denied", r["order_id"], aid, {"from": r["state"], "to": to}, "WARN"),
                )
            rec = {**json.loads(r["record"]), **record_fields, "state": to}
            contracts.require("attempt", rec)
            c.execute(
                "UPDATE afo_attempts SET state=?, record=?, finished_utc=? WHERE attempt_id=?",
                (to, json.dumps(rec), rec.get("finished_utc"), aid),
            )
            self._event(c, f"attempt:{to}", r["order_id"], aid, {"from": r["state"]})

    # -- external factory change (T051) and maintainer proposals (T048) ------------------------------------------
    def expire_waiting(self, ttl_s: float, now: float | None = None) -> list[str]:
        """WAITING_EXTERNAL_CHANGE is bounded: past the TTL the order is finalized BLOCKED (never waits forever)."""
        now = now or time.time()
        out = []
        for o in self.orders(("WAITING_EXTERNAL_CHANGE",)):
            if (o["waiting_since_epoch"] or 0) + ttl_s <= now:
                if self.transition(
                    o["order_id"],
                    "BLOCKED",
                    "WAITING_EXTERNAL_CHANGE_TTL",
                    terminal_reason=f"WAITING_EXTERNAL_CHANGE_TTL:{int(ttl_s)}s",
                ):
                    out.append(o["order_id"])
        return out

    def external_change_approved(self, oid: str, factory_revision: str, approval_ref: str, actor: str) -> None:
        """An externally approved and deployed factory change: the order re-enters the queue; admission then creates
        a NEW attempt on the deployed revision (the old attempt is never resumed in place)."""
        if not re.fullmatch(r"[0-9a-f]{7,40}", factory_revision) or not approval_ref.strip():
            raise QueueError("EXTERNAL_CHANGE_UNTRACEABLE", f"{factory_revision!r} {approval_ref!r}")
        with self.tx() as c:
            self._transition(
                c,
                oid,
                "QUEUED",
                f"external change {factory_revision[:12]} approved ({approval_ref[:80]})",
                waiting_since_epoch=None,
                not_before_epoch=0,
            )
            c.execute(
                "INSERT INTO afo_operator_actions (action, actor, reason, utc) VALUES (?,?,?,?)",
                ("external_change_approved", actor, f"{oid} {factory_revision} {approval_ref}"[:300], utc_now()),
            )
            self._event(
                c,
                "external_change_approved",
                oid,
                payload={"factory_revision": factory_revision, "approval_ref": approval_ref[:200]},
            )

    def record_proposal(self, rec: dict, status: str, order_id: str | None = None) -> int:
        contracts.require("maintenance-proposal", rec)
        if rec["auto_deployment_allowed"] is not False:  # schema const, repeated here: never relaxed by a schema edit
            raise QueueError("AUTO_DEPLOYMENT_FORBIDDEN", rec["proposal_id"])
        body = json.dumps(rec, sort_keys=True)
        with self.tx() as c:
            seq = c.execute(
                "INSERT INTO afo_maintainer_proposals (proposal_id, order_id, status, record, record_sha256,"
                " recorded_utc) VALUES (?,?,?,?,?,?)",
                (rec["proposal_id"], order_id, status, body, sha256_bytes(body.encode()), utc_now()),
            ).lastrowid
            self._event(
                c,
                f"proposal:{status}",
                order_id or rec["proposal_id"],
                payload={"proposal_id": rec["proposal_id"], "outcome": rec["outcome"]},
                severity="WARN" if status in ("QUARANTINED", "REJECTED") else "INFO",
            )
        return seq

    def proposal(self, pid: str) -> dict | None:
        with self.tx() as c:
            r = c.execute(
                "SELECT * FROM afo_maintainer_proposals WHERE proposal_id=? ORDER BY seq DESC LIMIT 1", (pid,)
            ).fetchone()
            return {**dict(r), "record": json.loads(r["record"])} if r else None

    def proposal_history(self, pid: str) -> list[dict]:
        with self.tx() as c:
            return [
                {**dict(r), "record": json.loads(r["record"])}
                for r in c.execute("SELECT * FROM afo_maintainer_proposals WHERE proposal_id=? ORDER BY seq", (pid,))
            ]

    # -- backup / restore (T025) ---------------------------------------------------------------------------------
    def backup(self, dest: Path) -> dict:
        dest.parent.mkdir(parents=True, exist_ok=True)
        src = self.connect()
        try:
            out = sqlite3.connect(dest)
            src.backup(out)
            ok = out.execute("PRAGMA integrity_check").fetchone()[0]
            out.close()
        finally:
            src.close()
        dest.chmod(0o600)
        return {"path": str(dest), "integrity": ok, "sha256": hashlib.sha256(dest.read_bytes()).hexdigest()}

    @staticmethod
    def restore(backup: Path, target: Path) -> dict:
        c = sqlite3.connect(backup)
        ok = c.execute("PRAGMA integrity_check").fetchone()[0]
        c.close()
        if ok != "ok":
            raise QueueError("BACKUP_CORRUPT", ok)
        if target.exists():
            raise QueueError("RESTORE_TARGET_EXISTS", str(target))  # never overwrite a live store
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(backup.read_bytes())
        target.chmod(0o600)
        return {"restored": str(target), "integrity": ok}


class ReadSnapshot(Store):
    """Bounded read-only view of the same Store for independent observation.

    Opens one consistent transaction, runs no migrations and creates no database.
    Existing read methods are reused; SQLite refuses every inherited mutation.
    """

    def __init__(self, path, *, max_rows=10000, max_bytes=16 * 1024 * 1024, timeout_s=120):
        import math

        self.path = Path(path)
        if self.path.is_symlink() or not self.path.is_file():
            raise QueueError("OBSERVATION_DATABASE_UNAVAILABLE")
        if (
            type(max_rows) is not int or not 1 <= max_rows <= 10000
            or type(max_bytes) is not int or not 1 <= max_bytes <= 16 * 1024 * 1024
            or type(timeout_s) not in (int, float) or not math.isfinite(timeout_s) or not 0 < timeout_s <= 120
        ):
            raise QueueError("OBSERVATION_BOUND_INVALID")
        self.remaining_rows, self.remaining_bytes = max_rows, max_bytes
        self.timeout_s = timeout_s
        self.reader = None

    def __enter__(self):
        if self.reader is not None:
            raise QueueError("OBSERVATION_SNAPSHOT_ALREADY_OPEN")
        self.deadline = time.monotonic() + self.timeout_s
        c = sqlite3.connect(self.path.resolve().as_uri() + "?mode=ro", uri=True, timeout=2, isolation_level=None)

        def bounded_row(cursor, row):
            self.remaining_rows -= 1
            self.remaining_bytes -= sum(
                len(v.encode("utf-8")) if isinstance(v, str) else len(v) if isinstance(v, bytes) else 32 for v in row
            )
            if self.remaining_rows < 0 or self.remaining_bytes < 0:
                raise QueueError("OBSERVATION_SNAPSHOT_BOUND_EXCEEDED")
            return sqlite3.Row(cursor, row)

        c.row_factory = bounded_row
        c.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, self.remaining_bytes)
        c.set_progress_handler(lambda: int(time.monotonic() > self.deadline), 1000)
        try:
            c.execute("PRAGMA query_only=ON")
            c.execute("BEGIN")
        except BaseException:
            c.close()
            raise
        self.reader = c
        return self

    def __exit__(self, *exc):
        self.reader.close()
        self.reader = None

    def connect(self):
        if self.reader is None or time.monotonic() > self.deadline:
            raise QueueError("OBSERVATION_SNAPSHOT_NOT_CURRENT")
        return self.reader

    @contextmanager
    def tx(self):
        yield self.connect()
