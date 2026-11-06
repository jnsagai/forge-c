"""Bounded local-only controller evidence escalation; never repair authority.

Consume the existing append-only lifecycle stream, not terminal-order scans or
creation timestamps. Existing pinned Store only. An artifact is sealed before
its local outbox acknowledgment. All observations retain charges and uncertainty.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import math
import os
import re
import sqlite3
import stat
import time
from contextlib import contextmanager

from ..common import state_dir, utc_now
from ..offline import controller_export
from ..release.finalize import archive_root
from . import alerts
from .durable import Refused, canonical, digest
from .line_recovery_product import job_id
from .mission_ledger import MissionLedger

CURSOR = "controller_escalation_event_cursor"
CURSOR_SCHEMA = "forge-c/controller-escalation-cursor/1"
MAX_EVENTS, MAX_RECORD = 32, 65536
MAX_SQL_STEPS, MAX_SECONDS = 500000, 3.0


class _Budget:
    def __init__(self):
        self.steps, self.until = 0, time.monotonic() + MAX_SECONDS

    def progress(self):
        self.steps += 1000
        return int(self.steps > MAX_SQL_STEPS or time.monotonic() > self.until)


@contextmanager
def _tx(store, budget):
    with store.tx() as c:
        c.set_progress_handler(budget.progress, 1000)
        c.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, MAX_RECORD * 4)
        try:
            yield c
        finally:
            c.set_progress_handler(None, 0)


def _store(store, identity):
    if (
        getattr(store, "_existing_only", False) is not True
        or store.path.absolute() != (state_dir() / "supervisor/line-queue.sqlite3").absolute()
        or type(identity) is not dict
        or set(identity) != {"device", "inode"}
        or any(type(x) is not int for x in identity.values())
    ):
        raise Refused("CONTROLLER_EXPORT_STORE_SCOPE")
    store._check_existing()
    s = store.path.stat()
    if dict(device=s.st_dev, inode=s.st_ino) != identity:
        raise Refused("CONTROLLER_EXPORT_STORE_REBOUND")


def _private(path, *, create=False):
    if create:
        try:
            path.mkdir(mode=0o700)
        except FileExistsError:
            pass
    s = path.lstat()
    if not stat.S_ISDIR(s.st_mode) or s.st_uid != os.getuid() or stat.S_IMODE(s.st_mode) != 0o700:
        raise Refused("CONTROLLER_EXPORT_DIRECTORY_UNSAFE")


def _read(path, limit=MAX_RECORD):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        s = os.fstat(fd)
        if not stat.S_ISREG(s.st_mode) or s.st_uid != os.getuid() or s.st_size > limit:
            raise Refused("CONTROLLER_EXPORT_FILE_BOUND_OR_TYPE")
        raw = os.read(fd, limit + 1)
        if len(raw) > limit or len(raw) != s.st_size or path.lstat().st_ino != s.st_ino:
            raise Refused("CONTROLLER_EXPORT_FILE_CHANGED")
        return raw
    finally:
        os.close(fd)


def _immutable(path, raw):
    # A crash during write leaves a divergent file and refuses; it never causes
    # a reporting callback to overwrite a possibly consumed artifact.
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    except FileExistsError:
        if _read(path, controller_export.MAX_BYTES) != raw:
            raise Refused("CONTROLLER_EXPORT_ARTIFACT_REBOUND") from None
        return
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        parent_fd = os.open(path.parent, os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(parent_fd)
        finally:
            os.close(parent_fd)
    except BaseException:
        # Preserve partial evidence, never truncate/reset it.
        raise


def _json(raw):
    if raw is None or len(raw.encode()) > MAX_RECORD:
        raise Refused("CONTROLLER_EXPORT_RECORD_BOUND")
    return json.loads(raw)


def _cursor(c):
    row = c.execute("SELECT value,actor FROM afo_control WHERE key=?", (CURSOR,)).fetchone()
    if not row:
        return 0
    if row["actor"] != "controller-escalation":
        raise Refused("CONTROLLER_EXPORT_CURSOR_REBOUND")
    value = _json(row["value"])
    if (
        not isinstance(value, dict)
        or set(value) != {"schema", "through_seq", "event_seq", "event_sha256"}
        or value["schema"] != CURSOR_SCHEMA
        or any(type(value[k]) is not int or value[k] < 1 for k in ("through_seq", "event_seq"))
    ):
        raise Refused("CONTROLLER_EXPORT_CURSOR_INVALID")
    event = c.execute("SELECT record FROM afo_lifecycle_events WHERE seq=?", (value["event_seq"],)).fetchone()
    if not event or hashlib.sha256(event[0].encode()).hexdigest() != value["event_sha256"]:
        raise Refused("CONTROLLER_EXPORT_CURSOR_EVENT_CHANGED")
    rec = _json(event[0])
    if rec.get("type") != "afo.controller_escalation_cursor" or rec.get("payload") != {"through_seq": value["through_seq"]}:
        raise Refused("CONTROLLER_EXPORT_CURSOR_INVALID")
    return value["through_seq"]


def _advance(store, c, through):
    store._event(c, "controller_escalation_cursor", "controller-escalation", payload=dict(through_seq=through))
    event = c.execute("SELECT seq,record FROM afo_lifecycle_events ORDER BY seq DESC LIMIT 1").fetchone()
    value = dict(
        schema=CURSOR_SCHEMA,
        through_seq=through,
        event_seq=event["seq"],
        event_sha256=hashlib.sha256(event["record"].encode()).hexdigest(),
    )
    c.execute(
        "INSERT INTO afo_control VALUES (?,?,?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value,"
        "updated_utc=excluded.updated_utc,actor=excluded.actor",
        (CURSOR, canonical(value).decode(), utc_now(), "controller-escalation"),
    )


def _case(c, event):
    if event.get("type") != "afo.attempt_failed" or not event.get("attempt_id"):
        return None
    aid, oid = event["attempt_id"], event["order_id"]
    jid = job_id(aid)
    evidence = c.execute(
        "SELECT record,sha256 FROM afo_execution_evidence WHERE job_id=? AND kind='LAUNCH_NOT_STARTED'", (jid,)
    ).fetchone()
    if not evidence:
        return None  # ordinary native terminal event, not a fabricated unsent launch
    proof = _json(evidence["record"])
    if digest(proof) != evidence["sha256"]:
        raise Refused("CONTROLLER_EXPORT_PROOF_CHANGED")
    row = c.execute("SELECT * FROM afo_work_orders WHERE order_id=?", (oid,)).fetchone()
    attempt = c.execute("SELECT * FROM afo_attempts WHERE attempt_id=?", (aid,)).fetchone()
    jrow = c.execute("SELECT record FROM afo_product_jobs WHERE job_id=?", (jid,)).fetchone()
    xrow = c.execute("SELECT record FROM afo_execution_liveness WHERE job_id=?", (jid,)).fetchone()
    if not all((row, attempt, jrow, xrow)):
        raise Refused("CONTROLLER_EXPORT_BINDING_MISSING")
    job, execution = _json(jrow[0]), _json(xrow[0])
    if row["state"] != "BLOCKED":
        return "PENDING_SETTLEMENT"  # never skip a late settlement after its FAILED event
    cmds = c.execute(
        "SELECT command_id,state FROM afo_commands_outbox WHERE order_id=? AND attempt_id=? AND kind='FABRO_LAUNCH' LIMIT 2",
        (oid, aid),
    ).fetchall()
    if (
        row["tenant_scope"] != "line-local"
        or attempt["order_id"] != oid
        or attempt["state"] != "FAILED"
        or job.get("order_id") != oid
        or job.get("attempt_id") != aid
        or job.get("job_id") != jid
        or proof.get("job_id") != jid
        or proof.get("kind") != "LOCAL_LAUNCH_NOT_STARTED"
        or proof.get("launch_nonce") != execution.get("launch_nonce")
        or job.get("nonce") != execution.get("launch_nonce")
        or proof.get("lease_epoch") != execution.get("lease_epoch")
        or execution.get("task_outcome") != "BLOCKED"
        or execution.get("resource_lease") != "RELEASED"
        or execution.get("native_run_ids") != []
        or execution.get("execution_liveness") != "NOT_STARTED"
        or len(cmds) != 1
        or cmds[0]["state"] != "QUARANTINED"
        or not re.fullmatch(r"[A-Z][A-Z0-9_]{0,127}", str(proof.get("failure_type", "")))
    ):
        raise Refused("CONTROLLER_EXPORT_LOCAL_PROOF_UNCONFIRMED")
    mission = c.execute("SELECT mission_id FROM afo_mission_orders WHERE order_id=?", (oid,)).fetchone()
    if not mission or mission[0] != job.get("mission_id") or execution.get("mission_id") != mission[0]:
        raise Refused("CONTROLLER_EXPORT_MISSION_REBOUND")
    gaps = []
    # Pre-count complete rows under the same VM/time budget before legacy
    # MissionLedger projection (which materializes rows). This is an export
    # snapshot limit, never a different mission cap.
    queries = (
        "SELECT COUNT(*) FROM afo_mission_executions WHERE mission_id=?",
        "SELECT COUNT(*) FROM afo_request_ledger WHERE mission_id=?",
        "SELECT COUNT(*) FROM afo_mission_counters WHERE mission_id=?",
    )
    bounded = all(c.execute(q, (mission[0],)).fetchone()[0] <= 1024 for q in queries)
    if bounded:
        full = MissionLedger._snapshot(c, mission[0])
        snapshot = {
            k: full[k]
            for k in (
                "mission_id",
                "lineage",
                "limits",
                "attempts",
                "jobs",
                "requests",
                "charged_tokens",
                "tools",
                "corrections",
                "usage_unknown",
            )
        }
    else:
        snapshot = dict(mission_id=mission[0], status="NOT_CAPTURED_BOUND")
        gaps.append("MISSION_SNAPSHOT_ROW_BOUND")
    execution_view = {
        k: execution[k] for k in ("task_outcome", "resource_lease", "execution_liveness", "native_run_ids", "authorization_state")
    }
    case = dict(
        schema="forge-c/controller-case/1",
        case_id="case-" + digest([jid, evidence["sha256"]])[:24],
        classification="CONTROLLER_FAILURE_UNDIAGNOSED",
        native_run="NOT_RECORDED",
        order_id=oid,
        attempt_id=aid,
        job_id=jid,
        failure_type=proof["failure_type"],
        source_revision=(job.get("factory_revision") or {}).get("commit") or "UNKNOWN",
        gaps=gaps,
        execution=execution_view,
        artifacts=[],
        records=dict(
            request_id=row["request_id"],
            execution_scope=job.get("execution_scope", "UNSPECIFIED"),
            acceptance="UNACCEPTED",
            profile=job.get("profile"),
            profile_sha256=job.get("profile_sha256"),
            model=job.get("model"),
            model_digest=job.get("model_digest"),
            precision=job.get("precision"),
            policy_sha256=job.get("policy_sha256"),
            operations_epoch=job.get("operations_epoch"),
            mission=snapshot,
            local_proof=dict(kind=proof["kind"], sha256=evidence["sha256"], failure_type=proof["failure_type"]),
            command=dict(command_id=cmds[0]["command_id"], state=cmds[0]["state"]),
            boundaries=dict(native_submit="NOT_RECORDED", model_inference="NOT_ASSERTED", replay="FORBIDDEN"),
            required_action=(
                "External engineering review of recorded controller failure; protected repair gates remain mandatory."
            ),
            auto_merge_source=False,
            auto_promote_factory_code=False,
        ),
    )
    return case


def _transcript(case, cfg):
    wo = case["records"]["request_id"]
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,128}", wo):
        raise Refused("CONTROLLER_EXPORT_WORKORDER_PATH")
    roots = [cfg.runs_root / wo / ".forge-run/launch", cfg.runs_root / ".launch" / wo]
    found = []
    for root in roots:
        if not root.exists():
            continue
        # Never traverse symlinks, including ancestors in this configured tree.
        if not root.resolve().is_relative_to(cfg.runs_root.resolve()) or any(
            p.is_symlink() for p in [root, *root.parents] if p != cfg.runs_root and cfg.runs_root in p.parents
        ):
            case["gaps"].append("LAUNCH_TRANSCRIPT_PATH_UNSAFE")
            continue
        for i, path in enumerate(root.iterdir()):
            if i >= 32:
                case["gaps"].append("LAUNCH_TRANSCRIPT_ENTRY_BOUND")
                break
            if re.fullmatch(r"attempt-[1-9][0-9]{0,5}\.json", path.name):
                found.append(path)
    if not found:
        case["gaps"].append("LAUNCH_TRANSCRIPT_MISSING")
        return
    # Ambiguous multiple launcher attempts are not silently attributed to the
    # queue attempt. A single exact workorder/source transcript is sufficient.
    if len(found) != 1:
        case["gaps"].append("LAUNCH_TRANSCRIPT_AMBIGUOUS")
        return
    path = found[0]
    try:
        raw = _read(path)
        rec = json.loads(raw)
        if (
            not isinstance(rec, dict)
            or rec.get("work_order") != wo
            or rec.get("revision") != case["source_revision"]
            or rec.get("fabro_run_id") is not None
        ):
            raise Refused("TRANSCRIPT_BINDING_CHANGED")
        steps = rec.get("steps", [])
        if not isinstance(steps, list) or len(steps) > 64:
            raise Refused("TRANSCRIPT_STEP_BOUND")

        def metadata(value):
            out = {}
            for key in ("step", "outcome", "code", "rc", "t_s", "at", "started_at", "ended_at", "class"):
                if key not in value or value[key] is None:
                    continue
                item = value[key]
                if key == "rc":
                    valid = type(item) is int and -(2**31) <= item < 2**31
                elif key == "t_s":
                    valid = type(item) in (int, float) and math.isfinite(item) and 0 <= item < 1e9
                else:
                    pattern = r"[0-9TtZz:+.\-]{1,64}" if key in ("at", "started_at", "ended_at") else r"[A-Za-z0-9_:.-]{1,128}"
                    valid = isinstance(item, str) and re.fullmatch(pattern, item) is not None
                if not valid:
                    raise Refused("LAUNCH_TRANSCRIPT_METADATA_INVALID")
                out[key] = item
            return out

        case["records"]["launcher"] = metadata(rec)
        if any(not isinstance(step, dict) for step in steps):
            raise Refused("LAUNCH_TRANSCRIPT_METADATA_INVALID")
        case["records"]["launcher"]["steps"] = [metadata(step) for step in steps]
        case["artifacts"].append(
            dict(
                kind="LAUNCH_TRANSCRIPT",
                sha256=hashlib.sha256(raw).hexdigest(),
                bytes=len(raw),
                content="WHITELISTED_METADATA_ONLY",
            )
        )
    except (OSError, ValueError, Refused) as exc:
        case["gaps"].append(getattr(exc, "code", "LAUNCH_TRANSCRIPT_UNREADABLE"))


def cycle(store, cfg, *, store_identity, max_cases=1, _checkpoint=lambda phase: None):
    """At most32 stream events/one1MiB export/finite SQL VM budget per cycle.

    `_checkpoint` is a private fault-injection leaf; no permission or authority
    predicate is replaced. Healthy empty polls make no model or network call.
    """
    if type(max_cases) is not int or max_cases != 1:
        raise Refused("CONTROLLER_EXPORT_BOUND_REQUIRED")
    _store(store, store_identity)
    budget = _Budget()
    archive = archive_root().absolute()
    # Existing configured archive location, outside every reclaimable input/job
    # tree. No arbitrary export destination or reference to live source paths.
    for forbidden in (cfg.runs_root.absolute(), state_dir() / "workorders"):
        if archive.resolve().is_relative_to(forbidden.resolve()) or forbidden.resolve().is_relative_to(archive.resolve()):
            raise Refused("CONTROLLER_EXPORT_ARCHIVE_IN_RECLAIMABLE_TREE")
    if archive.is_symlink() or not archive.parent.is_dir():
        raise Refused("CONTROLLER_EXPORT_ARCHIVE_ROOT_UNSAFE")
    try:
        archive.mkdir(mode=0o700)
    except FileExistsError:
        pass
    anchor = archive.stat()
    if not stat.S_ISDIR(anchor.st_mode) or anchor.st_uid != os.getuid() or anchor.st_mode & 0o022:
        raise Refused("CONTROLLER_EXPORT_ARCHIVE_ROOT_UNSAFE")
    root = archive / "controller-exports"
    _private(root, create=True)
    lockfd = os.open(root / ".lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
    exports, examined = [], 0
    try:
        try:
            fcntl.flock(lockfd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return dict(status="REPORTER_BUSY", exports=[], model_calls=0)
        with _tx(store, budget) as c:
            through = _cursor(c)
            rows = c.execute(
                "SELECT seq,CASE WHEN length(record)<=? THEN record END AS record "
                "FROM afo_lifecycle_events WHERE seq>? ORDER BY seq LIMIT ?",
                (MAX_RECORD, through, MAX_EVENTS),
            ).fetchall()
        advanced = through
        for row in rows:
            event = _json(row["record"])
            examined += 1
            if event.get("type") in ("afo.controller_escalation_cursor", "afo.controller_exported", "afo.dead_letter"):
                continue
            with _tx(store, budget) as c:
                case = _case(c, event)
            if case == "PENDING_SETTLEMENT":
                break
            advanced = row["seq"]
            if case is None:
                continue
            directory = root / case["case_id"]
            _private(directory, create=True)
            sealed = directory / "case.json"
            seal_id = "controller-export-seal:" + case["case_id"]
            with _tx(store, budget) as c:
                known = c.execute("SELECT record FROM afo_recovery_incidents WHERE incident_id=?", (seal_id,)).fetchone()
            if known:
                record = _json(known[0])
                old = record["case"]
                if record.get("sha256") != digest(old):
                    raise Refused("CONTROLLER_EXPORT_SEAL_CHANGED")
                if any(old.get(k) != case[k] for k in ("case_id", "job_id", "order_id", "attempt_id", "source_revision")):
                    raise Refused("CONTROLLER_EXPORT_CASE_REBOUND")
                case = old  # immutable point-in-time accounting, never re-aged
            else:
                _transcript(case, cfg)
                # Existing incident table holds the bounded immutable publisher
                # intent before artifact creation. It is not a new work queue.
                if len(canonical(case)) > MAX_RECORD // 2:
                    raise Refused("CONTROLLER_EXPORT_CASE_BOUND")
                record = dict(case=case, sha256=digest(case))
                with _tx(store, budget) as c:
                    c.execute(
                        "INSERT INTO afo_recovery_incidents VALUES (?,?,?,?)",
                        (seal_id, case["order_id"], "CONTROLLER_EXPORT_SEALED", canonical(record).decode()),
                    )
            _immutable(sealed, canonical(case))
            _checkpoint("case_sealed")
            rendered = controller_export.render(case)
            _immutable(directory / "export.zip", rendered["archive"])
            _immutable(directory / "REPORT.md", rendered["report"])
            _checkpoint("bundle_written")
            _store(store, store_identity)
            with _tx(store, budget) as c:
                # Recheck exact still-blocked local proof before acknowledgment.
                actual = _case(c, event)
                if not isinstance(actual, dict) or actual["case_id"] != case["case_id"]:
                    raise Refused("CONTROLLER_EXPORT_SETTLEMENT_CHANGED")
                payload = dict(
                    case_id=case["case_id"],
                    case_json=str(sealed),
                    case_sha256=hashlib.sha256(_read(sealed, controller_export.MAX_BYTES)).hexdigest(),
                    report_sha256=hashlib.sha256(rendered["report"]).hexdigest(),
                    bundle=str(directory / "export.zip"),
                    sha256=rendered["sha256"],
                    report=str(directory / "REPORT.md"),
                    status="NEEDS_EXTERNAL_ENGINEERING",
                    classification=case["classification"],
                )
                # artifact-before-ack, receipt and local notification share tx;
                # no new product command, admission or inference allocation.
                store._event(c, "controller_exported", case["order_id"], case["attempt_id"], payload, "WARN")
                # Existing immutable BLOCKED case + local alert outbox contract.
                from .deadletter import reason_code, required_action

                code = reason_code("PRODUCT_LAUNCH_NOT_STARTED")
                cid = "dlq-" + hashlib.sha256(f"{case['order_id']}|{code}".encode()).hexdigest()[:20]
                rec = dict(
                    schema_version="1.0",
                    case_id=cid,
                    order_id=case["order_id"],
                    attempt_id=case["attempt_id"],
                    reason_code=code,
                    required_action=required_action(code),
                    incident_ref="afo-order:" + case["order_id"],
                    artifact_refs=[
                        str(sealed),
                        str(directory / "export.zip"),
                        str(directory / "REPORT.md"),
                        "controller-export:sha256:" + rendered["sha256"],
                    ],
                    created_utc=utc_now(),
                    notification_dedupe_key="dlq:" + cid,
                    state="OPEN",
                    package_status="BLOCKED",
                    owner=None,
                    last_notification_utc=None,
                )
                from . import contracts

                contracts.require("dead-letter", rec)
                body = json.dumps(rec, sort_keys=True)
                c.execute(
                    "INSERT OR IGNORE INTO afo_dead_letters "
                    "(case_id,order_id,attempt_id,reason_code,record,record_sha256,state,recorded_utc) "
                    "VALUES (?,?,?,?,?,?,?,?)",
                    (
                        cid,
                        case["order_id"],
                        case["attempt_id"],
                        code,
                        body,
                        hashlib.sha256(body.encode()).hexdigest(),
                        "OPEN",
                        rec["created_utc"],
                    ),
                )
                # Existing earlier deadletter remains immutable; a single
                # controller-case notice carries its new exact evidence ref.
                alerts.enqueue(c, "controller-export:" + case["case_id"], "WARN", payload)
                _advance(store, c, advanced)
            _checkpoint("receipt_committed")
            exports.append(dict(**payload, case=str(sealed)))
            through = advanced
            break
        if advanced > through:
            _store(store, store_identity)
            with _tx(store, budget) as c:
                _advance(store, c, advanced)
        return dict(status="OBSERVED", exports=exports, examined_events=examined, model_calls=0)
    finally:
        os.close(lockfd)
