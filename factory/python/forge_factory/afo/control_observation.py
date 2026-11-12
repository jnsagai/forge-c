"""Strict application-control source projection for the existing external observer.

Hash/source and SQL-row bindings are factual checks, not a new authentication
authority. Native actor/write correlation and complete host coverage are separate.
Only a validated fixed-shape record may leave the private application database.
"""
from __future__ import annotations

import hashlib
import math
import re
from datetime import datetime
from pathlib import Path

from .durable import Refused, digest, strict_json

SHA = re.compile(r"[0-9a-f]{64}")
MODES = {"RUNNING", "PAUSED", "DRAINING", "STOPPED"}
AUTH = {"OS_STATE_DIRECTORY_OWNER", "DASHBOARD_OPERATOR_BEARER"}
CONTEXT_KEYS = {
    "schema", "intent_epoch", "mode", "intent_path_sha256", "intent_request_sha256", "producer_source_sha256",
    "at", "mono", "pid", "process", "user_namespace", "uid_map", "authentication", "scope", "control_id",
}
EVENT_KEYS = {
    "schema_version", "event_id", "occurred_utc", "type", "order_id", "attempt_id", "producer_id", "correlation_id",
    "payload_sha256", "severity", "privacy", "evidence_refs", "payload",
}
SCOPE = "CALLER_AND_OS_SOURCE_FACTS_NOT_INDEPENDENT_HOST_AUDIT"


def _int(value, maximum=2**32 - 1, minimum=0):
    return type(value) is int and minimum <= value <= maximum


def _sha(value):
    return isinstance(value, str) and SHA.fullmatch(value) is not None


def timestamp(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9TZ:+.\-]{1,40}", value):
        raise Refused("CONTROL_SOURCE_CLOCK_INVALID")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.utcoffset() is None or parsed.utcoffset().total_seconds() != 0:
            raise ValueError
        return parsed.timestamp()
    except (ValueError, OverflowError, OSError) as exc:
        raise Refused("CONTROL_SOURCE_CLOCK_INVALID") from exc


def configuration(value):
    if (
        not isinstance(value, dict)
        or set(value) != {"reader_sha256", "intent_source_sha256", "authentication_sources"}
        or value.get("reader_sha256") != hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        or not _sha(value.get("intent_source_sha256"))
        or not isinstance(value.get("authentication_sources"), dict)
        or set(value["authentication_sources"]) != AUTH
        or not all(_sha(v) for v in value["authentication_sources"].values())
    ):
        raise Refused("CONTROL_SOURCE_CONFIGURATION_NOT_FROZEN_OR_INVALID")
    return value


def context(value, config):
    """Validate before export; do not leak untrusted extra fields or exception text."""
    if (
        not isinstance(value, dict) or set(value) != CONTEXT_KEYS
        or value.get("schema") != "forge-c/control-source-context/1" or value.get("scope") != SCOPE
        or not isinstance(value.get("mode"), str) or value["mode"] not in MODES
        or not _int(value.get("intent_epoch"), minimum=1)
        or not _int(value.get("pid"), 2**31 - 1, 1)
        or any(type(value.get(k)) not in (int, float) or not math.isfinite(value[k]) or value[k] < 0 for k in ("at", "mono"))
        or not all(_sha(value.get(k)) for k in ("intent_path_sha256", "intent_request_sha256"))
        or (value.get("producer_source_sha256") is not None and not _sha(value["producer_source_sha256"]))
    ):
        raise Refused("CONTROL_SOURCE_CONTEXT_INVALID")
    if value["control_id"] != "control-" + digest({k: v for k, v in value.items() if k != "control_id"}):
        raise Refused("CONTROL_SOURCE_CONTEXT_HASH_INVALID")
    process = value["process"]
    if process is not None:
        basic = {"boot_id", "start_ticks", "state", "uid"}
        if (
            not isinstance(process, dict) or not basic <= set(process)
            or not set(process) <= basic | {"pid_namespace", "namespace_pid"}
            or not isinstance(process["boot_id"], str)
            or not re.fullmatch(r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}", process["boot_id"])
            or not isinstance(process["start_ticks"], str) or not re.fullmatch(r"[0-9]{1,20}", process["start_ticks"])
            or not isinstance(process["state"], str) or process["state"] not in set("RSDZTtXxKWPI")
            or not _int(process["uid"])
            or ("pid_namespace" in process and not re.fullmatch(r"pid:\[[0-9]{1,20}\]", str(process["pid_namespace"])))
            or ("namespace_pid" in process and not _int(process["namespace_pid"], 2**31 - 1, 1))
        ):
            raise Refused("CONTROL_SOURCE_PROCESS_INVALID")
    ns, mapping = value["user_namespace"], value["uid_map"]
    if ns is not None and (not isinstance(ns, str) or not re.fullmatch(r"user:\[[0-9]{1,20}\]", ns)):
        raise Refused("CONTROL_SOURCE_NAMESPACE_INVALID")
    if mapping is not None:
        if not isinstance(mapping, list) or not 1 <= len(mapping) <= 340:
            raise Refused("CONTROL_SOURCE_UID_MAP_INVALID")
        for row in mapping:
            if (
                not isinstance(row, list) or len(row) != 3 or not all(_int(x) for x in row) or row[2] == 0
                or row[0] + row[2] > 2**32 or row[1] + row[2] > 2**32
            ):
                raise Refused("CONTROL_SOURCE_UID_MAP_INVALID")
        for column in (0, 1):
            ordered = sorted(mapping, key=lambda r: r[column])
            if any(a[column] + a[2] > b[column] for a, b in zip(ordered, ordered[1:], strict=False)):
                raise Refused("CONTROL_SOURCE_UID_MAP_AMBIGUOUS")
    auth = value["authentication"]
    if not isinstance(auth, dict) or not _int(auth.get("uid")):
        raise Refused("CONTROL_SOURCE_AUTHENTICATION_INVALID")
    method = auth.get("method")
    if not isinstance(method, str):
        raise Refused("CONTROL_SOURCE_AUTHENTICATION_INVALID")
    required = {"method", "uid"} | ({"credential_sha256"} if method == "DASHBOARD_OPERATOR_BEARER" else set())
    allowed = required | ({"source_sha256"} if method in AUTH else set())
    if (
        not isinstance(method, str) or method not in AUTH | {"PRIVATE_INTENT_DIRECTORY_OWNER"}
        or not required <= set(auth) <= allowed
        or any(not _sha(auth[k]) for k in ("credential_sha256", "source_sha256") if k in auth)
        or (process is not None and process["uid"] != auth["uid"])
    ):
        raise Refused("CONTROL_SOURCE_AUTHENTICATION_INVALID")
    parents = [outside + auth["uid"] - inside for inside, outside, count in mapping or []
               if inside <= auth["uid"] < inside + count]
    return {
        "control_id": value["control_id"], "intent_epoch": value["intent_epoch"], "mode": value["mode"],
        "producer_source_matches": value["producer_source_sha256"] == config["intent_source_sha256"],
        "authentication_source_matches": auth.get("source_sha256") == config["authentication_sources"].get(method)
        if method in AUTH else None,
        # A UID map is relative to its parent namespace, not necessarily the host.
        "parent_namespace_uid": parents[0] if len(parents) == 1 else None,
        "process_identity_known": process is not None and process["state"] not in {"Z", "X", "x"}
        and {"pid_namespace", "namespace_pid"} <= set(process),
        "scope": "APPLICATION_SOURCE_BINDINGS_NOT_INDEPENDENT_AUTHENTICATION",
    }


def event(row, actions, config):
    if not _int(row.get("seq"), 2**63 - 1, 1) or not isinstance(row.get("record"), (str, bytes)):
        raise Refused("CONTROL_SOURCE_EVENT_ROW_INVALID")
    raw = row["record"].encode() if isinstance(row["record"], str) else row["record"]
    result = {"seq": row["seq"], "record_sha256": hashlib.sha256(raw).hexdigest()}
    try:
        record = strict_json(raw, 16384)
        if (
            not isinstance(record, dict) or set(record) != EVENT_KEYS
            or record["schema_version"] != "1.0" or record["type"] != "afo.operator_control"
            or record["order_id"] != "afo-control" or record["correlation_id"] != "afo-control"
            or record["producer_id"] != "afo-conductor" or record["attempt_id"] is not None
            or record["privacy"] != "INTERNAL" or record["severity"] != "INFO" or record["evidence_refs"] != []
            or not re.fullmatch(r"afo-ev-[0-9a-f]{24}", str(record["event_id"]))
            or record["event_id"] != row["event_id"] or record["occurred_utc"] != row["occurred_utc"]
        ):
            raise Refused("CONTROL_SOURCE_EVENT_INVALID")
        timestamp(record["occurred_utc"])
        payload = record["payload"]
        if not isinstance(payload, dict) or set(payload) != {"context", "applied"} or digest(payload) != record["payload_sha256"]:
            raise Refused("CONTROL_SOURCE_PAYLOAD_INVALID")
        facts = context(payload["context"], config)
        applied = payload["applied"]
        expected = {"paused": "0" if facts["mode"] == "RUNNING" else "1",
                    "draining": "1" if facts["mode"] in ("DRAINING", "STOPPED") else "0"}
        if (
            not isinstance(applied, list) or len(applied) != 2
            or any(not isinstance(a, dict) or set(a) != {"action_seq", "action"}
                   or not _int(a.get("action_seq"), 2**63 - 1, 1) or not isinstance(a.get("action"), str) for a in applied)
            or len({a["action_seq"] for a in applied}) != 2
            or {a["action"] for a in applied} != {k + "=" + v for k, v in expected.items()}
            or any(actions.get(a["action_seq"]) != a["action"] for a in applied)
        ):
            raise Refused("CONTROL_SOURCE_APPLIED_ROWS_UNBOUND")
        result.update(status="APPLICATION_RECEIPT_CAPTURED", event_id=row["event_id"], occurred_utc=row["occurred_utc"],
                      record=raw.decode(), facts=facts)
    except (Refused, TypeError, KeyError, UnicodeError, ValueError) as exc:
        result.update(status="UNKNOWN", reason=getattr(exc, "code", "CONTROL_SOURCE_INVALID"))
    return result


def intent(record, raw, config):
    result = {"record_sha256": hashlib.sha256(raw).hexdigest()}
    value = record.get("control_context")
    if value is None:
        return {**result, "status": "UNKNOWN", "reason": "LEGACY_CONTROL_CONTEXT_ABSENT"}
    try:
        facts = context(value, config)
        expected = digest({k: record[k] for k in ("epoch", "mode", "actor", "reason", "changed_at")})
        if (
            value["mode"] != record["mode"] or value["intent_epoch"] != record["epoch"]
            or value["intent_request_sha256"] != expected
        ):
            raise Refused("CONTROL_SOURCE_INTENT_CONTEXT_UNBOUND")
        timestamp(record["changed_at"])
        return {**result, "status": "APPLICATION_INTENT_CAPTURED", "context": value, "facts": facts}
    except (Refused, TypeError, KeyError, ValueError):
        return {**result, "status": "UNKNOWN", "reason": "CONTROL_SOURCE_INTENT_INVALID"}


def verify_sources(ledger, intent_record, config):
    """Replay exported safe sources; supplied source-match flags are not trusted."""
    if not isinstance(ledger, dict) or not isinstance(intent_record, dict):
        raise Refused("CONTROL_SOURCE_SNAPSHOT_INVALID")
    source = ledger.get("control_source")
    if (
        not isinstance(source, dict) or set(source) != {"reader_sha256", "events", "scope"}
        or source["reader_sha256"] != config["reader_sha256"]
        or source["scope"] != "APPLICATION_CONTROL_SOURCES_NOT_HOST_INTERVENTION_VERIFICATION"
        or not isinstance(source["events"], list) or len(source["events"]) > 10000
    ):
        raise Refused("CONTROL_SOURCE_SNAPSHOT_INVALID")
    action_rows = ledger.get("actions")
    if not isinstance(action_rows, list) or any(
        not isinstance(a, dict) or not _int(a.get("seq"), 2**63 - 1, 1)
        or a.get("action") not in ("paused=0", "paused=1", "draining=0", "draining=1", None,
                                   "denied:pause", "denied:drain", "denied:resume", "denied:shutdown")
        for a in action_rows
    ):
        raise Refused("CONTROL_SOURCE_ACTION_SNAPSHOT_INVALID")
    actions = {a["seq"]: a["action"] for a in action_rows}
    if len(actions) != len(action_rows):
        raise Refused("CONTROL_SOURCE_ACTION_IDENTITY_INVALID")
    seen = set()
    event_ids = set()
    for row in source["events"]:
        if not isinstance(row, dict) or not _int(row.get("seq"), 2**63 - 1, 1) or row["seq"] in seen:
            raise Refused("CONTROL_SOURCE_EVENT_IDENTITY_INVALID")
        seen.add(row["seq"])
        if row.get("status") == "UNKNOWN":
            if set(row) != {"seq", "record_sha256", "status", "reason"} or not _sha(row["record_sha256"]):
                raise Refused("CONTROL_SOURCE_UNKNOWN_EVENT_INVALID")
        elif row.get("status") != "APPLICATION_RECEIPT_CAPTURED" or event(row, actions, config) != row:
            raise Refused("CONTROL_SOURCE_EVENT_REPLAY_MISMATCH")
        else:
            if row["event_id"] in event_ids:
                raise Refused("CONTROL_SOURCE_EVENT_IDENTITY_INVALID")
            event_ids.add(row["event_id"])
    projected = intent_record.get("control_source")
    if not isinstance(projected, dict) or not _sha(projected.get("record_sha256")):
        raise Refused("CONTROL_SOURCE_INTENT_SNAPSHOT_INVALID")
    if projected.get("status") == "APPLICATION_INTENT_CAPTURED":
        ctx = projected.get("context")
        facts = context(ctx, config)
        if (
            set(projected) != {"record_sha256", "status", "context", "facts"} or facts != projected["facts"]
            or facts["mode"] != intent_record["mode"] or facts["intent_epoch"] != intent_record["epoch"]
        ):
            raise Refused("CONTROL_SOURCE_INTENT_REPLAY_MISMATCH")
    elif projected.get("status") != "UNKNOWN" or set(projected) != {"record_sha256", "status", "reason"}:
        raise Refused("CONTROL_SOURCE_UNKNOWN_INTENT_INVALID")
