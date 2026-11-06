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
CURSOR_SCHEMA = "forge-c/controller-escalation-cursor/2"
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
    # Store.tx sets a ten-second busy timeout before BEGIN. Reporting uses a
    # bounded existing-only connection to the SAME pinned canonical Store,
    # with no constructor, migration, mkdir or journal conversion.
    store._check_existing()
    left = budget.until - time.monotonic()
    if left <= 0:
        raise Refused("CONTROLLER_EXPORT_TIME_BOUND")
    c = sqlite3.connect(store.path.absolute().as_uri() + "?mode=rw", uri=True, timeout=min(left, 0.1), isolation_level=None)
    c.row_factory = sqlite3.Row
    c.set_progress_handler(budget.progress, 1000)
    c.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, MAX_RECORD * 4)
    try:
        c.execute("PRAGMA busy_timeout=" + str(max(1, min(100, int(left * 1000)))))
        c.execute("PRAGMA synchronous=FULL")
        c.execute("PRAGMA foreign_keys=ON")
        if c.execute("PRAGMA journal_mode").fetchone()[0].lower() != "wal":
            raise Refused("CONTROLLER_EXPORT_EXISTING_WAL_REQUIRED")
        c.execute("BEGIN IMMEDIATE")
        store._check_existing()
        yield c
        if time.monotonic() > budget.until:
            raise Refused("CONTROLLER_EXPORT_TIME_BOUND")
        c.execute("COMMIT")
    except BaseException:
        c.set_progress_handler(None, 0)
        if c.in_transaction:
            c.execute("ROLLBACK")
        raise
    finally:
        c.close()


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
        return dict(through_seq=0, pending_delivery=None)
    if row["actor"] != "controller-escalation":
        raise Refused("CONTROLLER_EXPORT_CURSOR_REBOUND")
    value = _json(row["value"])
    if (
        not isinstance(value, dict)
        or set(value) != {"schema", "through_seq", "event_seq", "event_sha256", "pending_delivery"}
        or value["schema"] != CURSOR_SCHEMA
        or type(value["through_seq"]) is not int
        or value["through_seq"] < 1
        or type(value["event_seq"]) is not int
        or value["through_seq"] != value["event_seq"]
    ):
        raise Refused("CONTROLLER_EXPORT_CURSOR_INVALID")
    event = c.execute("SELECT record FROM afo_lifecycle_events WHERE seq=?", (value["event_seq"],)).fetchone()
    if not event or hashlib.sha256(event[0].encode()).hexdigest() != value["event_sha256"]:
        raise Refused("CONTROLLER_EXPORT_CURSOR_EVENT_CHANGED")
    _json(event[0])  # bounded authentic existing source/receipt event, not a new marker
    pending = value["pending_delivery"]
    if pending is not None:
        if (
            not isinstance(pending, dict)
            or set(pending) != {"notification_id", "receipt_seq", "receipt_sha256"}
            or type(pending["receipt_seq"]) is not int
            or pending["receipt_seq"] < 1
        ):
            raise Refused("CONTROLLER_EXPORT_DELIVERY_POINTER_INVALID")
        receipt = c.execute("SELECT record FROM afo_lifecycle_events WHERE seq=?", (pending["receipt_seq"],)).fetchone()
        if not receipt or hashlib.sha256(receipt[0].encode()).hexdigest() != pending["receipt_sha256"]:
            raise Refused("CONTROLLER_EXPORT_DELIVERY_RECEIPT_CHANGED")
        rec = _json(receipt[0])
        if (
            rec.get("type") != "afo.controller_exported"
            or rec.get("payload", {}).get("notification_id") != pending["notification_id"]
        ):
            raise Refused("CONTROLLER_EXPORT_DELIVERY_RECEIPT_CHANGED")
    return value


def _advance(store, c, through, pending_delivery=None):
    event = c.execute("SELECT record FROM afo_lifecycle_events WHERE seq=?", (through,)).fetchone()
    if not event:
        raise Refused("CONTROLLER_EXPORT_CURSOR_SOURCE_MISSING")
    # Directly bind the consumed existing append-only event. No self-generated
    # cursor markers can accumulate ahead of later settlements.
    value = dict(
        schema=CURSOR_SCHEMA,
        through_seq=through,
        event_seq=through,
        event_sha256=hashlib.sha256(event[0].encode()).hexdigest(),
        pending_delivery=pending_delivery,
    )
    c.execute(
        "INSERT INTO afo_control VALUES (?,?,?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value,"
        "updated_utc=excluded.updated_utc,actor=excluded.actor",
        (CURSOR, canonical(value).decode(), utc_now(), "controller-escalation"),
    )


def _deliver_pending(store, budget, root):
    with _tx(store, budget) as c:
        pointer = _cursor(c)
    pending = pointer["pending_delivery"]
    if pending is None:
        return []
    nid = pending["notification_id"]
    with _tx(store, budget) as c:
        receipt = c.execute("SELECT record FROM afo_lifecycle_events WHERE seq=?", (pending["receipt_seq"],)).fetchone()
        payload = _json(receipt[0])["payload"]
        row = c.execute("SELECT payload FROM afo_notifications WHERE notification_id=?", (nid,)).fetchone()
        if not row or digest(_json(row[0])) != digest(payload):
            raise Refused("CONTROLLER_EXPORT_NOTICE_PAYLOAD_CHANGED")
        _verify_receipt(root, payload)
    # Exact own notice only; never configure adapters or drain other tenants.
    alerts.deliver(
        store,
        adapters={},
        notification_ids=(nid,),
        limit=1,
        transaction=lambda: _tx(store, budget),
        expected_payload_sha256={nid: digest(payload)},
    )
    with _tx(store, budget) as c:
        row = c.execute("SELECT delivery_state FROM afo_notifications WHERE notification_id=?", (nid,)).fetchone()
        if not row:
            raise Refused("CONTROLLER_EXPORT_NOTIFICATION_MISSING")
        if row[0] not in ("DELIVERED", "DELIVERED_LOCAL_ONLY"):
            raise Refused("CONTROLLER_EXPORT_NOTICE_PENDING")
        from ..events.emit import events_dir

        notice = dict(
            notification_id=nid,
            status=row[0],
            notice_log=str(alerts.notice_log()),
            event_ledger=str(events_dir() / "factory-events.jsonl"),
            event_payload_ref=nid,
        )
        store._event(c, "controller_notice_delivered", "controller-escalation", payload=notice)
        _advance(store, c, pointer["through_seq"], None)
    return [notice]


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
        observed = {step["step"] for step in case["records"]["launcher"]["steps"] if "step" in step}
        phases = {"guard", "run_live", "revision", "worktree", "inputs", "stack_stop", "stack_start", "smoke", "workorder_launch"}
        case["records"]["steps_recorded"] = sorted(observed)
        case["records"]["steps_not_recorded"] = sorted(phases - observed)
        logdir = cfg.runs_root / ".launch" / wo / path.stem
        if rec.get("step_logs") != str(logdir):
            case["gaps"].append("STOP_LOG_TRANSCRIPT_PATH_UNCONFIRMED")
        else:
            _stop_log(case, logdir / "stack-stop.log", cfg.runs_root)
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


STOP_CODES = {
    "LINE_STACK_NATIVE_NOT_QUIESCENT",
    "LINE_STACK_NATIVE_OBSERVATION_UNKNOWN",
    "LINE_STACK_NATIVE_INVENTORY_UNKNOWN",
    "LINE_STACK_AUTHORITY_OR_EXECUTION_FENCED",
    "EFFECT_AUTHORITY_EXPIRED_OR_CHANGED",
    "PROVIDER_WORKER_PARENT_UNPROVEN",
    "PROVIDER_OWNER_VIEW_UNPROVEN",
    "OPERATIONS_ADMISSION_FENCED",
}


def _stop_log(case, path, runs_root):
    if path.resolve().is_relative_to(runs_root.resolve()) is not True or any(
        p.is_symlink() for p in [path, *path.parents] if p != runs_root and runs_root in p.parents
    ):
        case["gaps"].append("STOP_LOG_PATH_UNSAFE")
        return
    try:
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode):
            case["gaps"].append("STOP_LOG_TYPE_UNSAFE")
            return
        if info.st_size > MAX_RECORD:
            case["records"]["stop_log"] = dict(bytes=info.st_size, sha256=None, content="OVERSIZE_NOT_READ", observed_codes=[])
            case["gaps"].append("STOP_LOG_OVERSIZE")
            return
        raw = _read(path)
        words = set(re.findall(rb"\b[A-Z][A-Z0-9_]{1,127}\b", raw))
        codes = sorted(code for code in STOP_CODES if code.encode() in words)
        case["records"]["stop_log"] = dict(
            bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest(), content="KNOWN_TYPED_CODES_ONLY", observed_codes=codes
        )
        case["artifacts"].append(
            dict(kind="STACK_STOP_LOG", bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest(), content="KNOWN_TYPED_CODES_ONLY")
        )
        if not codes:
            case["gaps"].append("STOP_LOG_NO_RECOGNIZED_TYPED_CODE")
    except FileNotFoundError:
        case["gaps"].append("STOP_LOG_MISSING")
    except (OSError, Refused):
        case["gaps"].append("STOP_LOG_UNREADABLE")


def _verify_receipt(root, payload):
    if not isinstance(payload, dict) or not re.fullmatch(r"case-[0-9a-f]{24}", str(payload.get("case_id", ""))):
        raise Refused("CONTROLLER_EXPORT_RECEIPT_INVALID")
    directory = root / payload["case_id"]
    _private(directory)
    for key, name, sha in (
        ("case_json", "case.json", "case_sha256"),
        ("bundle", "export.zip", "sha256"),
        ("report", "REPORT.md", "report_sha256"),
    ):
        if payload.get(key) != str(directory / name):
            raise Refused("CONTROLLER_EXPORT_RECEIPT_PATH_CHANGED")
        raw = _read(directory / name, controller_export.MAX_BYTES)
        if hashlib.sha256(raw).hexdigest() != payload.get(sha):
            raise Refused("CONTROLLER_EXPORT_RECEIPT_ARTIFACT_CHANGED")
        if key == "bundle" and controller_export.verify(raw):
            raise Refused("CONTROLLER_EXPORT_RECEIPT_ARCHIVE_INVALID")


def observe(store, cfg, *, store_identity):
    """Reporting failures remain explicit telemetry, never kill a healthy owner.

    Normal current()/Store/Intent/admission guards remain unconditional on every
    production cycle; this does not permit placement on unavailable storage.
    """
    try:
        return cycle(store, cfg, store_identity=store_identity)
    except Exception as exc:  # noqa: BLE001 - telemetry containment, not manufacturing authority
        code = getattr(exc, "code", type(exc).__name__)
        if not isinstance(code, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,127}", code):
            code = "CONTROLLER_EXPORT_FAILED"
        return dict(status="CAPTURE_FAILED", code=code, exports=[], model_calls=0)


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
    if archive != archive.resolve() or not archive.parent.is_dir():
        raise Refused("CONTROLLER_EXPORT_ARCHIVE_ROOT_UNSAFE")
    parent = archive.parent.stat()
    if parent.st_dev != store.path.stat().st_dev:
        raise Refused("CONTROLLER_EXPORT_ARCHIVE_DEVICE_CHANGED")
    try:
        archive.mkdir(mode=0o700)
    except FileExistsError:
        pass
    anchor = archive.stat()
    if (
        not stat.S_ISDIR(anchor.st_mode)
        or anchor.st_uid != os.getuid()
        or anchor.st_mode & 0o022
        or anchor.st_dev != store.path.stat().st_dev
    ):
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
        deliveries = _deliver_pending(store, budget, root)
        with _tx(store, budget) as c:
            pointer = _cursor(c)
            through = pointer["through_seq"]
            rows = c.execute(
                "SELECT seq,CASE WHEN length(record)<=? THEN record END AS record "
                "FROM afo_lifecycle_events WHERE seq>? ORDER BY seq LIMIT ?",
                (MAX_RECORD, through, MAX_EVENTS),
            ).fetchall()
        advanced = through
        for row in rows:
            event = _json(row["record"])
            examined += 1
            # Every existing event (including inert legacy telemetry) advances
            # the bounded source cursor; we never append cursor markers.
            if event.get("type") == "afo.controller_exported":
                _verify_receipt(root, event.get("payload"))
                advanced = row["seq"]
                break  # one bounded artifact verification/output per cycle
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
                if (
                    record.get("sha256") != digest(old)
                    or record.get("case_json") != str(sealed)
                    or record.get("bundle") != str(directory / "export.zip")
                    or record.get("report") != str(directory / "REPORT.md")
                ):
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
                record = dict(
                    case=case,
                    sha256=digest(case),
                    case_json=str(sealed),
                    bundle=str(directory / "export.zip"),
                    report=str(directory / "REPORT.md"),
                )
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
                    notification_id="afo-ntf-"
                    + hashlib.sha256(("controller-export:" + case["case_id"]).encode()).hexdigest()[:20],
                )
                # artifact-before-ack, receipt and local notification share tx;
                # no new product command, admission or inference allocation.
                receipt_id = store._event(c, "controller_exported", case["order_id"], case["attempt_id"], payload, "WARN")
                receipt = c.execute("SELECT seq,record FROM afo_lifecycle_events WHERE event_id=?", (receipt_id,)).fetchone()
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
                nid, _ = alerts.enqueue(c, "controller-export:" + case["case_id"], "WARN", payload)
                if nid != payload["notification_id"]:
                    raise Refused("CONTROLLER_EXPORT_NOTIFICATION_REBOUND")
                pending = dict(
                    notification_id=nid,
                    receipt_seq=receipt["seq"],
                    receipt_sha256=hashlib.sha256(receipt["record"].encode()).hexdigest(),
                )
                _advance(store, c, advanced, pending)
            _checkpoint("receipt_committed")
            deliveries += _deliver_pending(store, budget, root)
            exports.append(dict(**payload, case=str(sealed)))
            through = advanced
            break
        if advanced > through:
            _store(store, store_identity)
            with _tx(store, budget) as c:
                _advance(store, c, advanced)
        return dict(status="OBSERVED", exports=exports, deliveries=deliveries, examined_events=examined, model_calls=0)
    finally:
        os.close(lockfd)
