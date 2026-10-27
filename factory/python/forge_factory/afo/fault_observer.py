"""Read-only, model-free evidence capture outside the Conductor (DA-AT-052).

The observer never injects a fault, repairs storage, admits work or grants authority.
Missing observations remain unknown. Its plan is an input of the frozen campaign;
artifacts belong to the existing qualification evidence tree, not another database.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import socket
import sqlite3
import subprocess
import time
import urllib.error
import urllib.request
from contextlib import closing
from pathlib import Path
from urllib.parse import urlsplit

from ..common import sha256_file
from . import qualification, soak
from .durable import Refused, canonical, digest, immutable_json, strict_json

SCHEMA = "forge-c/independent-operational-observation/1"
FIELDS = {
    "afo_missions": ("mission_id", "lineage", "limits", "authorization_ref"),
    "afo_mission_executions": ("identity", "mission_id", "kind", "reserved_tokens", "charge", "reported_tokens"),
    "afo_request_ledger": ("request_id", "mission_id", "job_id", "charge", "state"),
    "afo_execution_liveness": (
        "job_id", "mission_id", "launch_nonce", "native_run_ids", "resource_lease", "execution_liveness", "last_reconciled_at"
    ),
}
MAX_BYTES = 16 * 1024 * 1024
MAX_TRACE_BYTES = 128 * 1024 * 1024


def read_bytes(path, limit=MAX_BYTES):
    # Single regular-file read supplies BOTH parsing and the reference digest.
    import stat

    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as f:
        mode = os.fstat(f.fileno())
        if not stat.S_ISREG(mode.st_mode) or mode.st_size > limit:
            raise Refused("OBSERVER_ARTIFACT_NOT_BOUNDED_REGULAR_FILE")
        raw = f.read(limit + 1)
        if len(raw) > limit:
            raise Refused("OBSERVER_ARTIFACT_NOT_BOUNDED_REGULAR_FILE")
        return raw


def read_json(path, limit=MAX_BYTES):
    return strict_json(read_bytes(path, limit), limit)


def bound_json(ref, *, path=None):
    raw = read_bytes(path or ref["path"])
    if hashlib.sha256(raw).hexdigest() != ref["sha256"]:
        raise Refused("OBSERVER_ARTIFACT_HASH_CHANGED")
    return strict_json(raw, MAX_BYTES)


def plan(manifest, ref):
    qualification.validate(manifest)
    if not manifest["stage"].startswith("operation-") or ref not in manifest["inputs"]:
        raise Refused("OBSERVER_PLAN_NOT_FROZEN")
    d = bound_json(ref)
    from . import operational_facts

    if (
        d.get("schema") != "forge-c/operational-observer-plan/1"
        or not re.fullmatch(r"[A-Za-z0-9_.@-]+\.service", d.get("unit", ""))
        or d.get("observer_source_sha256") != sha256_file(Path(__file__))
        or d.get("fact_evaluator_sha256") != sha256_file(Path(operational_facts.__file__))
        or type(d.get("max_rows")) is not int
        or not 1 <= d["max_rows"] <= 10000
        or not all(
            isinstance(d.get(k), str) and Path(d[k]).is_absolute()
            for k in ("database", "intent", "data_root", "heartbeat", "evidence_root")
        )
    ):
        raise Refused("OBSERVER_PLAN_INVALID")
    if "control_sources" in d:
        from .control_observation import configuration

        configuration(d["control_sources"])
    if any(Path(d["data_root"]).resolve() not in Path(d[k]).resolve().parents for k in ("database", "heartbeat")):
        raise Refused("OBSERVER_DATABASE_OUTSIDE_DATA_ROOT")
    if not isinstance(d.get("mount_uuid"), str) or not re.fullmatch(r"[0-9a-fA-F-]{8,64}", d["mount_uuid"]):
        raise Refused("OBSERVER_MOUNT_IDENTITY_REQUIRED")
    if Path(d["data_root"]).resolve() in (Path(d["evidence_root"]).resolve(), *Path(d["evidence_root"]).resolve().parents):
        raise Refused("OBSERVER_EVIDENCE_MUST_BE_OUTSIDE_FACTORY_STATE")
    urls = d.get("health_urls")
    if not isinstance(urls, dict) or set(urls) != {"fabro", "gateway"}:
        raise Refused("OBSERVER_LOCAL_PROBES_REQUIRED")
    for raw in urls.values():
        parsed = urlsplit(raw)
        if (
            parsed.scheme != "http"
            or parsed.hostname not in ("127.0.0.1", "::1")
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
            or parsed.path != "/health"
            or not parsed.port
        ):
            raise Refused("OBSERVER_PROBE_MUST_BE_LOOPBACK")
    return d


def artifact(frozen, path):
    from .diagnosis_packet import scoped_path

    root = Path(frozen["evidence_root"]).resolve()
    try:
        relative = Path(path).absolute().relative_to(root)
    except ValueError:
        raise Refused("OBSERVER_EVIDENCE_OUTSIDE_APPROVED_ROOT") from None
    return scoped_path(root, str(relative))


def _action(row):
    value = row["action"]
    if type(row["seq"]) is not int or not 1 <= row["seq"] <= 2**63 - 1 or not isinstance(value, str):
        raise Refused("CONTROL_SOURCE_ACTION_INVALID")
    known = re.fullmatch(r"(?:paused|draining)=[01]|denied:(?:pause|drain|resume|shutdown)", value) is not None
    return {"seq": row["seq"], "action": value if known else None,
            **({"action_sha256": hashlib.sha256(value.encode()).hexdigest()} if not known else {})}


def ledger(path, limit, *, control_sources=None):
    """Snapshot authoritative tables in one read transaction; never call Store/migrate."""
    p = Path(path)
    if p.is_symlink() or not p.is_file():
        raise Refused("OBSERVER_DATABASE_UNAVAILABLE")
    with closing(sqlite3.connect(p.resolve().as_uri() + "?mode=ro", uri=True, timeout=2)) as c:
        c.row_factory = sqlite3.Row
        c.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, MAX_BYTES)
        budget = MAX_BYTES

        def take(sql, params=()):
            nonlocal budget
            rows = []
            for row in c.execute(sql, params):
                budget -= sum(
                    len(value.encode("utf-8")) if isinstance(value, str) else len(value) if isinstance(value, bytes) else 32
                    for value in row
                )
                if budget < 0:
                    raise Refused("OBSERVER_LEDGER_BYTE_BOUND_EXCEEDED")
                rows.append(row)
            return rows

        def project(raw, fields):
            record = strict_json(raw, MAX_BYTES)
            if not isinstance(record, dict):
                raise Refused("OBSERVER_LEDGER_RECORD_INVALID")
            if "charge" in fields and (type(record.get("charge")) is not int or record["charge"] < 0):
                raise Refused("OBSERVER_LEDGER_ACCOUNTING_INVALID")
            if "limits" in fields:
                from .mission_ledger import validate_limits

                validate_limits(record.get("limits"))
            if "execution_liveness" in fields:
                from .durable import validate

                validate("execution-lifecycle", record)
            return {k: record.get(k) for k in fields}

        c.execute("PRAGMA query_only=ON")
        c.execute("BEGIN")
        result = {}
        for table, fields in FIELDS.items():
            rows = take("SELECT record FROM " + table + " LIMIT ?", (limit + 1,))  # noqa: S608
            if len(rows) > limit:
                raise Refused("OBSERVER_LEDGER_ROW_BOUND_EXCEEDED")
            result[table] = [project(r[0], fields) for r in rows]
        orders = take(
            "SELECT order_id,state,authorization_id,created_epoch,terminal_reason,envelope FROM afo_work_orders "
            "ORDER BY order_id LIMIT ?",
            (limit + 1,),
        )
        attempts = take("SELECT record FROM afo_attempts ORDER BY attempt_id LIMIT ?", (limit + 1,))
        controls = take("SELECT key,value FROM afo_control WHERE key IN ('paused','draining')")
        commands = take(
            "SELECT command_id,kind,idempotency_key,ack_ref FROM afo_commands_outbox ORDER BY command_id LIMIT ?", (limit + 1,)
        )
        actions = take("SELECT seq,action FROM afo_operator_actions ORDER BY seq LIMIT ?", (limit + 1,))
        if max(len(orders), len(commands), len(actions), len(attempts)) > limit:
            raise Refused("OBSERVER_LEDGER_ROW_BOUND_EXCEEDED")
        from . import contracts
        source = None
        if control_sources is not None:
            from . import control_observation as control

            control.configuration(control_sources)
            event_rows = take(
                "SELECT seq,event_id,occurred_utc,record FROM afo_lifecycle_events "
                "WHERE type='afo.operator_control' ORDER BY seq LIMIT ?", (limit + 1,),
            )
            if len(event_rows) > limit:
                raise Refused("OBSERVER_CONTROL_ROW_BOUND_EXCEEDED")
            action_map = {r["seq"]: r["action"] for r in actions}
            source = {
                "reader_sha256": control_sources["reader_sha256"],
                "events": [control.event(dict(row), action_map, control_sources) for row in event_rows],
                "scope": "APPLICATION_CONTROL_SOURCES_NOT_HOST_INTERVENTION_VERIFICATION",
            }
        if any(row["value"] not in ("0", "1") for row in controls):
            raise Refused("OBSERVER_CONTROL_VALUE_INVALID")

        clean_orders = []
        for r in orders:
            row = dict(r)
            if row["state"] not in contracts.fsm()["order_states"]:
                raise Refused("OBSERVER_QUEUE_STATE_INVALID")
            envelope = row.pop("envelope")
            try:
                row["envelope_valid"] = not contracts.errors("work-order", strict_json(envelope, 65536))
            except (ValueError, TypeError):
                row["envelope_valid"] = False
            # The untrusted/private envelope itself never leaves the database.
            clean_orders.append(row)
        result.update(
            orders=clean_orders,
            commands=[dict(r) for r in commands],
            actions=[_action(dict(r)) for r in actions],
            controls={r["key"]: r["value"] for r in controls},
            attempts=[
                project(
                    r[0],
                    ("attempt_id", "attempt_seq", "order_id", "state", "fabro_run_id", "exit_status",
                     "terminal_package_status", "created_utc"),
                )
                for r in attempts
            ],
        )
        if control_sources is not None:
            result["control_source"] = source
        return result


def unit_status(unit):
    result = subprocess.run(
        ["systemctl", "--user", "show", unit, "--property=ActiveState,SubState,Result,MainPID,ControlGroup,NRestarts"],
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )
    if result.returncode:
        raise Refused("OBSERVER_UNIT_UNAVAILABLE")
    props = dict(line.split("=", 1) for line in result.stdout.splitlines() if "=" in line)
    return {k: props.get(k) for k in ("ActiveState", "SubState", "Result", "MainPID", "ControlGroup", "NRestarts")}


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def _healthy(url):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())
    try:
        with opener.open(url, timeout=2) as response:
            return 200 <= response.status < 300
    except (OSError, urllib.error.URLError):
        return False


def health(frozen, bound):
    checks = {key: _healthy(url) for key, url in frozen["health_urls"].items()}
    try:
        heartbeat = read_json(frozen["heartbeat"], 65536)
        checks["conductor"] = heartbeat.get("ok") is True and 0 <= time.time() - heartbeat["epoch"] <= bound
    except (OSError, ValueError, KeyError, TypeError):
        checks["conductor"] = False
    result = subprocess.run(
        ["findmnt", "--noheadings", "--output", "UUID", "--target", frozen["data_root"]],
        capture_output=True,
        text=True,
        timeout=3,
        check=False,
    )
    checks["data_volume"] = result.returncode == 0 and result.stdout.strip() == frozen["mount_uuid"]
    return checks


def _intent(path, *, control_sources=None):
    raw = read_bytes(path, 65536)
    record = strict_json(raw, 65536)
    if (
        not isinstance(record, dict)
        or record.get("mode") not in ("RUNNING", "PAUSED", "DRAINING", "STOPPED")
        or type(record.get("epoch")) is not int
        or record["epoch"] < 0
        or ("effective_stop" in record and type(record["effective_stop"]) is not bool)
    ):
        raise Refused("OBSERVER_OPERATIONS_INTENT_UNKNOWN")
    result = {k: record.get(k) for k in ("mode", "epoch", "effective_stop")}
    if control_sources is not None:
        from . import control_observation as control

        control.configuration(control_sources)
        result["control_source"] = control.intent(record, raw, control_sources)
    return result


def heartbeat(path):
    record = read_json(path, 65536)
    if (
        any(type(record.get(k)) is not int or record[k] < 0 for k in ("pid", "cycle"))
        or type(record.get("epoch")) not in (int, float)
        or not math.isfinite(record["epoch"])
    ):
        raise Refused("OBSERVER_HEARTBEAT_INVALID")
    return {k: record.get(k) for k in ("pid", "cycle", "epoch", "mode", "ok")}


def independent(sample):
    unit = sample.get("unit") or {}
    own = sample.get("observer_cgroups")
    pid = unit.get("MainPID")
    if not own or not isinstance(pid, str) or not pid.isdecimal() or pid == str(sample["observer_pid"]):
        return False
    group = unit.get("ControlGroup")
    if group:
        return all(g != group and not g.startswith(group + "/") for g in own)
    # systemd legitimately releases an empty stopped cgroup. Unknown/missing unit
    # properties are different from the explicit inactive/failed + PID 0 state.
    return pid == "0" and unit.get("ActiveState") in ("inactive", "failed") and unit.get("SubState") in ("dead", "failed")


def capture(manifest, plan_ref, destination):
    """One bounded external sample; safe while the controller or engineering grant is down."""
    frozen = plan(manifest, plan_ref)
    started = time.monotonic()
    out = {
        "schema": SCHEMA,
        "manifest_sha256": digest(manifest),
        "plan_ref": plan_ref,
        "observer_source_sha256": sha256_file(Path(__file__)),
        "host": socket.gethostname(),
        "observer_pid": os.getpid(),
        "wall": time.time(),
        "mono": started,
        "boot_id": soak._boot_id(),
        "errors": {},
    }
    probes = {
        "ledger": lambda: ledger(frozen["database"], frozen["max_rows"], control_sources=frozen.get("control_sources")),
        "intent": lambda: _intent(frozen["intent"], control_sources=frozen.get("control_sources")),
        "unit": lambda: unit_status(frozen["unit"]),
        "health": lambda: health(frozen, manifest["bounds"]["control_cycle_seconds"]),
        "heartbeat": lambda: heartbeat(frozen["heartbeat"]),
        "free_bytes": lambda: os.statvfs(frozen["data_root"]).f_bavail * os.statvfs(frozen["data_root"]).f_frsize,
        "observer_cgroups": lambda: [s.split(":", 2)[-1] for s in Path("/proc/self/cgroup").read_text().splitlines()],
    }
    for name, probe in probes.items():
        try:
            out[name] = probe()
        except (OSError, ValueError, sqlite3.Error, subprocess.SubprocessError) as exc:
            # No exception messages (which can contain private data), no artificial healthy defaults.
            out[name] = None
            out["errors"][name] = getattr(exc, "code", type(exc).__name__)
    if frozen.get("control_sources") and out.get("intent") is not None:
        # Provenance may change when recovery counters change; that is not new
        # operator intent. Preserve the existing mode/epoch/stop comparison API.
        out["intent_control_source"] = out["intent"].pop("control_source")
    if out.get("health") is not None:
        hb, unit = out.get("heartbeat") or {}, out.get("unit") or {}
        out["health"]["conductor"] = (
            out["health"].get("conductor") is True
            and unit.get("ActiveState") == "active"
            and str(hb.get("pid")) == unit.get("MainPID")
            and unit.get("MainPID") != "0"
        )
    out["independent_process"] = independent(out)
    out["completed_wall"] = time.time()
    out["capture_seconds"] = time.monotonic() - started
    out["complete"] = (
        not out["errors"] and out["independent_process"] and out["capture_seconds"] <= manifest["bounds"]["control_cycle_seconds"]
    )
    if len(canonical(out)) > MAX_BYTES:
        out["ledger"] = None
        out["errors"]["ledger"] = "OBSERVER_OUTPUT_BYTE_BOUND_EXCEEDED"
        out["complete"] = False
    immutable_json(artifact(frozen, destination), out)
    return out


def _rows(snapshot, table, key):
    rows = snapshot["ledger"][table]
    out = {r[key]: r for r in rows}
    if len(rows) != len(out):
        raise Refused("OBSERVER_DUPLICATE_LEDGER_IDENTITY")
    return out


def invariants(samples):
    """Unknown or truncated accounting cannot be converted into zero loss/duplicates."""
    if not samples or any(not s.get("complete") or not s.get("ledger") for s in samples):
        return {"ledger_reset": None, "duplicate_effects": None, "false_ready": None, "unexpected_interventions": None}
    reset, duplicates = False, 0
    for a, b in zip(samples, samples[1:], strict=False):
        for table, key in (
            ("afo_missions", "mission_id"),
            ("afo_mission_executions", "identity"),
            ("afo_request_ledger", "request_id"),
        ):
            before, after = _rows(a, table, key), _rows(b, table, key)
            reset |= not set(before) <= set(after)
            for ident in set(before) & set(after):
                old, new = before[ident], after[ident]
                if table == "afo_missions":
                    reset |= old != new  # even higher limits require a separately audited amendment, not replacement
                else:
                    reset |= old["mission_id"] != new["mission_id"] or new["charge"] < old["charge"]
                    if table == "afo_mission_executions":
                        reset |= old["reserved_tokens"] != new["reserved_tokens"]
                        reset |= old["reported_tokens"] is not None and (
                            new["reported_tokens"] is None or new["reported_tokens"] < old["reported_tokens"]
                        )
                    else:
                        reset |= old["job_id"] != new["job_id"]
        old_commands = {r["command_id"]: r for r in a["ledger"]["commands"]}
        new_commands = {r["command_id"]: r for r in b["ledger"]["commands"]}
        reset |= not set(old_commands) <= set(new_commands)
        for ident in set(old_commands) & set(new_commands):
            old, new = old_commands[ident], new_commands[ident]
            reset |= old["idempotency_key"] != new["idempotency_key"] or bool(old["ack_ref"] and old["ack_ref"] != new["ack_ref"])
    for sample in samples:
        for ex in sample["ledger"]["afo_execution_liveness"]:
            duplicates = max(duplicates, max(0, len(set(ex["native_run_ids"])) - 1))
        keys = [(r["kind"], r["idempotency_key"]) for r in sample["ledger"]["commands"]]
        duplicates = max(duplicates, len(keys) - len(set(keys)))
    ready = any(r["state"] == "READY_FOR_OFFLINE_REVIEW" for s in samples for r in s["ledger"]["orders"])
    return {
        "ledger_reset": bool(reset),
        "duplicate_effects": duplicates,
        "false_ready": None if ready else False,  # READY requires the separate independent package oracle
        "unexpected_interventions": None,  # authenticated actions alone cannot exclude host-level manual intervention
    }


def load_samples(manifest, plan_ref, refs):
    frozen = plan(manifest, plan_ref)
    rows = []
    if not 2 <= len(refs) <= 50000:
        raise Refused("OBSERVER_SAMPLE_COUNT_INVALID")
    byte_budget = MAX_TRACE_BYTES
    for ref in refs:
        p = artifact(frozen, ref["path"])
        if byte_budget <= 0:
            raise Refused("OBSERVER_TRACE_BYTE_BOUND_EXCEEDED")
        raw = read_bytes(p, min(MAX_BYTES, byte_budget))
        byte_budget -= len(raw)
        if byte_budget < 0:
            raise Refused("OBSERVER_TRACE_BYTE_BOUND_EXCEEDED")
        if hashlib.sha256(raw).hexdigest() != ref["sha256"]:
            raise Refused("OBSERVER_SAMPLE_UNBOUND")
        row = strict_json(raw, MAX_BYTES)
        if row.get("schema") != SCHEMA or row.get("manifest_sha256") != digest(manifest) or row.get("plan_ref") != plan_ref:
            raise Refused("OBSERVER_SAMPLE_UNBOUND")
        if any(type(row.get(k)) not in (float, int) or not math.isfinite(row[k]) for k in ("wall", "mono")):
            raise Refused("OBSERVER_SAMPLE_CLOCK_INVALID")
        if frozen.get("control_sources") and row.get("ledger") is not None and row.get("intent") is not None:
            from .control_observation import verify_sources

            if not isinstance(row["intent"], dict):
                raise Refused("CONTROL_SOURCE_SNAPSHOT_INVALID")
            verify_sources(row["ledger"], {**row["intent"], "control_source": row.get("intent_control_source")},
                           frozen["control_sources"])
        rows.append(row)
    if len({r["host"] for r in rows}) != 1 or any(r.get("observer_source_sha256") != sha256_file(Path(__file__)) for r in rows):
        raise Refused("OBSERVER_SAMPLE_SOURCE_CHANGED")
    if any(
        b["wall"] <= a["wall"] or (a["boot_id"] == b["boot_id"] and b["mono"] <= a["mono"])
        for a, b in zip(rows, rows[1:], strict=False)
    ):
        raise Refused("OBSERVER_SAMPLE_ORDER_INVALID")
    return rows


def evaluate(manifest, plan_ref, injection_ref, sample_refs, destination, *, work_refs=()):
    """Correlate objective signal-fault restoration; no hand-entered success flags."""
    frozen = plan(manifest, plan_ref)
    receipt = bound_json(injection_ref, path=artifact(frozen, injection_ref["path"]))
    if receipt.get("manifest_sha256") != digest(manifest):
        raise Refused("OBSERVER_FAULT_RECEIPT_UNBOUND")
    fault = receipt.get("fault")
    if fault not in manifest["faults"]:
        raise Refused("OBSERVER_FAULT_NOT_FROZEN")
    rows = load_samples(manifest, plan_ref, sample_refs)
    if type(receipt.get("at")) not in (int, float) or not math.isfinite(receipt["at"]):
        raise Refused("OBSERVER_FAULT_CLOCK_INVALID")
    before = [s for s in rows if s["wall"] <= receipt["at"]]
    after = [s for s in rows if s["wall"] > receipt["at"]]
    from . import operational_facts
    from .operational_campaign import SIGNALS

    exposure = bool(
        fault in SIGNALS
        and receipt.get("schema") == "forge-c/operational-fault/1"
        and receipt.get("unit") == frozen["unit"]
        and receipt.get("returncode") == 0
        and receipt.get("command")
        == ["systemctl", "--user", "kill", "--kill-who=main", "--signal=" + SIGNALS[fault], frozen["unit"]]
        and before
        and before[-1].get("complete")
        and before[-1]["unit"]["ActiveState"] == "active"
        and before[-1]["intent"]["mode"] == "RUNNING"
        and receipt.get("host") == before[-1]["host"]
        and 0 <= receipt["at"] - before[-1]["wall"] <= manifest["bounds"]["probe_gap_seconds"]
    )
    affected = (
        [
            s
            for s in after
            if s.get("unit") and (s["unit"]["ActiveState"] != "active" or s["unit"]["MainPID"] != before[-1]["unit"]["MainPID"])
        ]
        if before
        else []
    )
    restored = next(
        (
            s
            for s in affected
            if operational_facts.healthy(s, manifest["bounds"]["control_cycle_seconds"])
            and s.get("intent") == before[-1]["intent"]
            and s["unit"]["ActiveState"] == "active"
            and s["unit"]["MainPID"] != before[-1]["unit"]["MainPID"]
        ),
        None,
    )
    if fault not in SIGNALS:
        fixture_ref = receipt.get("fixture_ref")
        if (
            receipt.get("schema") != "forge-c/operational-exposure/1"
            or receipt.get("unit") != frozen["unit"]
            or not rows
            or receipt.get("host") != rows[0]["host"]
            or not isinstance(fixture_ref, dict)
            or fixture_ref not in manifest["inputs"]
        ):
            raise Refused("OBSERVER_EXTERNAL_EXPOSURE_NOT_FROZEN")
        fixture = bound_json(fixture_ref)
        parameters = operational_facts.validate_fixture(fixture, fault, plan_ref, frozen["unit"])
        exposure, restored = operational_facts.external(manifest, fault, parameters, receipt, rows)
    gaps = any(
        b["wall"] - a["wall"] > manifest["bounds"]["probe_gap_seconds"]
        or (a["boot_id"] == b["boot_id"] and abs((b["wall"] - a["wall"]) - (b["mono"] - a["mono"])) > soak.CLOCK_SKEW_S)
        for a, b in zip(rows, rows[1:], strict=False)
    )
    facts = invariants(rows)
    from . import operational_work

    work = []
    if len(work_refs) > frozen["max_rows"]:
        raise Refused("OBSERVER_WORK_COUNT_BOUND_EXCEEDED")
    for ref in work_refs:
        record = bound_json(ref, path=artifact(frozen, ref["path"]))
        work.append(operational_work.verify(manifest, record))
    if all(s.get("complete") is True for s in rows):
        facts["false_ready"] = operational_work.ready_verdict(rows, work)
    record = {
        "schema": "forge-c/independent-operational-fault/1",
        "producer": "INDEPENDENT_OPERATIONAL_OBSERVER",
        "manifest_sha256": digest(manifest),
        "plan_ref": plan_ref,
        "fault": fault,
        "injection_ref": injection_ref,
        "sample_refs": sample_refs,
        "work_refs": list(work_refs),
        "fault_exposed": exposure,
        "independently_restored": bool(exposure and restored and not gaps),
        "restoration_seconds": (0 if fault == "post-campaign-continuity" else restored["wall"] - receipt["at"])
        if restored and exposure
        else None,
        "observation_seconds": rows[-1]["wall"] - rows[0]["wall"],
        "observation_gaps": gaps,
        **facts,
        "status": "OBSERVED_REQUIRES_HOST_AUDIT" if exposure and restored and not gaps else "INCOMPLETE",
        "limitations": [
            "HOST_INTERVENTION_AUDIT_REQUIRED",
            *(["INDEPENDENT_READY_ORACLE_REQUIRED"] if facts["false_ready"] is None else []),
            *(["FAULT_EXPOSURE_NOT_OBSERVED"] if not exposure else []),
        ],
    }
    if destination is not None:
        immutable_json(artifact(frozen, destination), record)
    return record


def verify(manifest, record):
    if record.get("schema") != "forge-c/independent-operational-fault/1":
        raise Refused("INDEPENDENT_OPERATIONAL_OBSERVER_REQUIRED")
    actual = evaluate(
        manifest, record["plan_ref"], record["injection_ref"], record["sample_refs"], None,
        work_refs=record.get("work_refs", ()),
    )
    if actual != record:
        raise Refused("OPERATIONAL_OBSERVER_VERDICT_CHANGED")
    return actual


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("command", choices=("capture", "evaluate", "work", "product"))
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--plan-ref", type=Path, required=True, help="JSON path+sha256 reference already frozen in manifest inputs")
    ap.add_argument("--evidence", type=Path, help="JSON with injection_ref and sample_refs")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args(argv)
    m, ref = read_json(args.manifest), read_json(args.plan_ref)
    if args.command == "capture":
        result = capture(m, ref, args.out)
    else:
        if not args.evidence:
            ap.error("--evidence required for evaluate")
        if args.command == "product":
            from .operational_work import capture_product

            result = capture_product(m, ref, **read_json(args.evidence), destination=args.out)
        elif args.command == "work":
            from .operational_work import evaluate as evaluate_work

            result = evaluate_work(m, ref, **read_json(args.evidence), destination=args.out)
        else:
            result = evaluate(m, ref, **read_json(args.evidence), destination=args.out)
    print(json.dumps({"schema": result.get("schema", "forge-c/product-qualification-row/1"),
                      "manifest_sha256": result["manifest_sha256"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
