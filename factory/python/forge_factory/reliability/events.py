"""CRE-T005/T006/T010 — typed CRE events: content-addressed, schema-validated, redacted, bounded, append-only.

* event_id = cre- + sha256(type | idempotency key)[:40]: duplicates, replays and reordered deliveries are no-ops.
* Stored in the CRE store (`cre_events`, append-only) and mirrored once into the 002 ledger as an envelope event
  (`payload_ref: cre-event:<id>`, derived id `fx-cre-...`), so the existing collector/dashboard/retention apply.
* Payload strings are redacted and capped (policy telemetry.max_tool_excerpt_bytes); keys that could carry model
  reasoning or raw prompts are refused (INV: no hidden reasoning, raw logs outside model context).
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from typing import Any

from ..common import REPO_ROOT, canonical_json, utc_now
from ..events.redact import redact_obj, redact_text
from .policy import CRE_CONTRACTS_DIR
from .store import CREStore

SCHEMA_VERSION = "cre-1.0"
FORBIDDEN_KEYS = {"reasoning", "chain_of_thought", "thoughts", "prompt", "raw_prompt", "raw_response", "messages"}
CHANNEL_OF = {"cre.failure_observed": "metrics", "cre.failure_classified": "metrics", "cre.retry_decided": "supervisor",
              "cre.circuit_opened": "supervisor", "cre.circuit_half_open": "supervisor",
              "cre.circuit_closed": "supervisor", "cre.recovery_transition": "supervisor",
              "cre.recovery_terminal": "supervisor", "cre.side_effect": "audit", "cre.capa_opened": "repair",
              "cre.capa_transition": "repair", "cre.reproducer_run": "repair", "cre.reproducer_verified": "repair",
              "cre.root_cause_verified": "repair", "cre.corrective_action_applied": "repair",
              "cre.preventive_test_registered": "repair", "cre.lesson_linked": "knowledge",
              "cre.lesson_retracted": "knowledge", "cre.benchmark_completed": "metrics",
              "cre.promotion_evaluated": "audit", "cre.candidate_rolled_back": "audit", "cre.spc_signal": "metrics",
              "cre.security_denial": "security", "cre.policy_decision": "audit"}
_FACTORY_VERSION: str | None = None


def factory_version() -> str:
    global _FACTORY_VERSION
    if _FACTORY_VERSION is None:
        try:
            head = subprocess.run(["git", "rev-parse", "--short=12", "HEAD"], cwd=REPO_ROOT, capture_output=True,
                                  text=True, timeout=10).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            head = ""
        _FACTORY_VERSION = f"forge-c@{head}" if head else "forge-c@UNKNOWN"
    return _FACTORY_VERSION


def _validator():
    from jsonschema import Draft202012Validator, FormatChecker

    schema = json.loads((CRE_CONTRACTS_DIR / "cre-event.schema.json").read_text())
    return Draft202012Validator(schema, format_checker=FormatChecker())


_V = None


def schema_errors(ev: dict) -> list[str]:
    global _V
    _V = _V or _validator()
    return [f"{'/'.join(map(str, e.path)) or '<root>'}: {e.message}"[:200] for e in _V.iter_errors(ev)]


def event_id(type_: str, key: str) -> str:
    return "cre-" + hashlib.sha256(f"{type_}|{key}".encode()).hexdigest()[:40]


def _bound(obj: Any, limit: int) -> Any:
    if isinstance(obj, dict):
        bad = FORBIDDEN_KEYS & {str(k).lower() for k in obj}
        if bad:
            raise ValueError(f"CRE_PAYLOAD_FORBIDDEN_KEY:{sorted(bad)[0]}")
        return {str(k)[:60]: _bound(v, limit) for k, v in list(obj.items())[:40]}
    if isinstance(obj, list):
        return [_bound(v, limit) for v in obj[:50]]
    if isinstance(obj, str):
        return redact_text(obj)[0][:limit]
    return obj


def build(type_: str, key: str, payload: dict, *, policy_sha256: str, correlation_id: str,
          source_type: str = "DETERMINISTIC_TOOL", data_status: str = "OBSERVED", ts_utc: str | None = None,
          evidence_refs: list[str] | None = None, evidence_sha256: str | None = None, excerpt_limit: int = 2048,
          **ids: Any) -> dict:
    pay, red = redact_obj(_bound(payload, excerpt_limit))
    ev = {"schema_version": SCHEMA_VERSION, "event_id": event_id(type_, key), "type": type_,
          "ts_utc": ts_utc or utc_now(), "source_type": source_type, "data_status": data_status,
          "correlation_id": redact_text(correlation_id)[0][:120] or "cre", "policy_sha256": policy_sha256,
          "factory_version": factory_version(), "evidence_refs": [r[:512] for r in (evidence_refs or [])][:20],
          "evidence_sha256": evidence_sha256, "redacted": bool(red), "payload": pay}
    for k in ("causation_id", "run_id", "work_order", "order_id", "incident_id", "capa_id", "fingerprint", "phase",
              "monotonic_elapsed_s"):
        if ids.get(k) is not None:
            ev[k] = ids[k]
    errs = schema_errors(ev)
    if errs:
        raise ValueError("CRE_EVENT_SCHEMA:" + "; ".join(errs[:3]))
    return ev


def record(store: CREStore, ev: dict, mirror: bool = True) -> bool:
    """Append once (idempotent). Returns True when the event is new; only then is it mirrored to the 002 ledger."""
    errs = schema_errors(ev)
    if errs:
        raise ValueError("CRE_EVENT_SCHEMA:" + "; ".join(errs[:3]))
    new = store.insert_event(ev)
    if new and mirror:
        from ..events.emit import append, build_event

        summary = " ".join(f"{k}={v}" for k, v in sorted(ev["payload"].items())
                           if isinstance(v, (str, int, float)) and k in ("error_code", "state", "decision", "class",
                                                                         "failure_class", "to", "verdict", "dependency"))
        env = build_event(CHANNEL_OF.get(ev["type"], "metrics"), "INFO", f"{ev['type']} {summary}"[:160],
                          correlation_id=ev["correlation_id"], run_id=ev.get("run_id"),
                          incident_id=ev.get("incident_id"), phase=ev.get("phase"),
                          payload_ref=f"cre-event:{ev['event_id']}")
        env["event_id"] = "fx-" + ev["event_id"]  # deterministic: the 002 store deduplicates replays as well
        env["ts_utc"] = ev["ts_utc"]
        append(env)
    return new


def canonical(ev: dict) -> bytes:
    return canonical_json(ev)
