"""Factory event emitter: schema-validated, redacted-before-write, append-only JSONL segments.

All factory components (policy hook, MCP wrappers, supervisor, repair, packager) emit through here.
The collector (T034) ingests these segments and Fabro run events into the indexed store.
"""
from __future__ import annotations

import fcntl
import json
import os
import uuid
from pathlib import Path
from typing import Any

from ..common import canonical_json, state_dir, truncate, utc_now
from .redact import redact_obj, redact_text

CHANNELS = ("human", "workflow", "tools", "ai", "supervisor", "repair", "security", "audit", "metrics", "knowledge")
LEVELS = ("ERROR", "WARN", "INFO", "DEBUG", "TRACE")
OPTIONAL = ("trace_id", "span_id", "run_id", "workflow_id", "phase", "agent_id", "tool_id", "incident_id",
            "payload_ref", "duration_ms", "model", "input_tokens", "output_tokens", "token_count_provenance")


def events_dir() -> Path:
    return Path(os.environ.get("FORGE_EVENTS_DIR") or state_dir() / "events")


def build_event(channel: str, level: str, message: str, correlation_id: str | None = None,
                **fields: Any) -> dict:
    if channel not in CHANNELS or level not in LEVELS:
        raise ValueError(f"bad channel/level {channel}/{level}")
    msg, red1 = redact_text(message)
    ev: dict[str, Any] = {"schema_version": "0.4", "event_id": f"fx-{uuid.uuid4().hex}",
                          "ts_utc": utc_now(), "channel": channel, "level": level,
                          "message": truncate(msg.replace("\n", " ").strip() or "-", 160),
                          "correlation_id": truncate(correlation_id or fields.get("run_id") or "factory", 120)}
    red2 = False
    for k in OPTIONAL:
        v = fields.get(k)
        if v is None:
            continue
        if isinstance(v, str):
            v, r = redact_text(v)
            red2 |= r
            v = truncate(v, 512 if k == "payload_ref" else 120)
        ev[k] = v
    ev["redacted"] = bool(red1 or red2)
    return ev


def append(ev: dict, segment: str = "factory-events.jsonl") -> dict:
    ev, extra = redact_obj(ev)
    ev["redacted"] = bool(ev.get("redacted") or extra)
    d = events_dir()
    d.mkdir(parents=True, exist_ok=True)
    line = canonical_json(ev) + b"\n"
    with open(d / segment, "ab") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            f.write(line)
            f.flush()
            os.fsync(f.fileno())
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)
    return ev


def emit(channel: str, level: str, message: str, correlation_id: str | None = None, **fields: Any) -> dict:
    return append(build_event(channel, level, message, correlation_id, **fields))


def read_segment(segment: str = "factory-events.jsonl") -> list[dict]:
    p = events_dir() / segment
    if not p.is_file():
        return []
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]
