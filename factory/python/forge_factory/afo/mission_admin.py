"""Authenticated operator provisioning of bounded mission lineage; no grant signing/renewal."""

from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path

from ..common import utc_now
from .durable import Refused, canonical, digest
from .mission_ledger import MissionLedger, validate_limits


def register(store, document, eff):
    from . import authz

    if eff.mode not in ("PILOT", "ACTIVE"):
        raise Refused("MISSION_ACTIVE_AUTHORITY_REQUIRED")
    required = {"mission_id", "lineage", "limits", "authorization_ref", "request", "orders"}
    if not required <= set(document) or set(document) - required - {"admission_authorization_ref"}:
        raise Refused("MISSION_ADMIN_INPUT_INVALID")
    limits = document["limits"]
    ref = document["authorization_ref"]
    current = document.get("admission_authorization_ref")
    if "admission_authorization_ref" in document and (not isinstance(current, str) or not current
                                                    or current != eff.authorization_id):
        raise Refused("MISSION_CONTINUATION_AUTHORITY_INVALID")
    active_ref = current or ref
    grant = authz.find(eff.mode, eff.sha256 or "", ref=active_ref, action="recover_workorder", request=document["request"])
    if not grant.allow:
        raise Refused(grant.code)
    auth = json.loads((authz.AUTH_DIR / f"{active_ref}.json").read_text())
    if current:
        if auth.get("authorization_id") != current:
            raise Refused("AUTH_ID_MISMATCH")
        validate_limits(limits)
        check = authz.verify(auth, policy_sha256=eff.sha256 or "", mode=eff.mode,
                             action="recover_workorder", request=document["request"])
        if not check.allow:
            raise Refused(check.code)
    expiry = datetime.fromisoformat(auth["expires_utc"].replace("Z", "+00:00")).timestamp()
    caps = {
        "max_attempts": int(eff.get("budgets.max_order_attempts")),
        "max_jobs": int(eff.get("budgets.max_recovery_model_calls_per_order")),
        "max_tokens": int(eff.get("budgets.max_model_tokens_per_order")),
    }
    caps.update(
        max_requests=eff.get("budgets.max_inference_requests_per_order", caps["max_jobs"] * 8),
        max_tools=eff.get("budgets.max_tool_calls_per_order", caps["max_jobs"] * 8),
        max_corrections=1,
    )
    if any(type(value) is not int or value < 1 for value in caps.values()):
        raise Refused("MISSION_POLICY_CAP_INVALID")
    if any(limits.get(k, cap + 1) > cap for k, cap in caps.items()) or limits.get("deadline", float("inf")) > min(
        expiry, time.time() + float(eff.get("budgets.max_order_wall_seconds"))
    ):
        raise Refused("MISSION_LIMIT_EXCEEDS_CURRENT_AUTHORITY_OR_POLICY")
    ledger = MissionLedger(store)
    with store.tx() as c:
        existing = c.execute("SELECT 1 FROM afo_missions WHERE mission_id=?", (document["mission_id"],)).fetchone()
    if existing:
        rec = ledger.snapshot(document["mission_id"])
        if rec["lineage"] != document["lineage"] or rec["limits"] != limits or rec["authorization_ref"] != ref:
            raise Refused("MISSION_ALLOWANCE_RESET_FORBIDDEN")
        if current:
            if (time.time() >= limits["deadline"] or rec["attempts"] >= limits["max_attempts"]
                    or rec["requests"] >= limits["max_requests"]
                    or rec["tools"] >= limits["max_tools"] or rec["charged_tokens"] >= limits["max_tokens"]
                    or rec["unbounded_historical_usage"]):
                raise Refused("MISSION_ALLOWANCE_EXHAUSTED")
            # New current authority can admit a continuation; it cannot rewrite the
            # old grant, mission row, explicit time amendments or spent counters.
            ident = "mission-continuation-" + digest([document, digest(auth), eff.sha256])
            record = {"schema": "forge-c/mission-continuation-authority/1", "document": document,
                      "grant_sha256": digest(auth), "policy_sha256": eff.sha256, "accepted_at": utc_now(),
                      "mission_snapshot_sha256": digest(rec), "allowances_reset": False, "deadline_changed": False}
            with store.tx() as c:
                prior = c.execute("SELECT record,sha256 FROM afo_independent_decisions WHERE decision_id=?", (ident,)).fetchone()
                if prior:
                    saved = json.loads(prior["record"])
                    if (digest(saved) != prior["sha256"] or saved.get("document") != document
                            or saved.get("grant_sha256") != digest(auth) or saved.get("policy_sha256") != eff.sha256):
                        raise Refused("MISSION_CONTINUATION_RECEIPT_CHANGED")
                c.execute("INSERT OR IGNORE INTO afo_independent_decisions VALUES (?,?,?,?)",
                          (ident, "MISSION_CONTINUATION_AUTHORITY", canonical(record).decode(), digest(record)))
    else:
        if current:
            raise Refused("MISSION_CONTINUATION_REQUIRES_EXISTING_MISSION")
        rec = ledger.register(document["mission_id"], document["lineage"], limits, ref, authorize=lambda *_: grant.allow)
    for entry in document["orders"]:
        order = store.order(entry["order_id"])
        if not order:
            raise Refused("MISSION_ORDER_UNKNOWN")
        env = json.loads(order["envelope"])
        allowed = authz.find(
            eff.mode,
            eff.sha256 or "",
            ref=active_ref,
            action="recover_workorder",
            request={"order_id": env["request_id"], "driver_class": env["driver_class"], "model": env["model_profile"]},
        )
        if not allowed.allow:
            raise Refused(allowed.code)
        ledger.link(rec["mission_id"], order["order_id"], continuation_of=entry.get("continuation_of"))
    return ledger.snapshot(rec["mission_id"])


def import_snapshot(store, mission_id, path, sha256):
    """Operator-only migration of an immutable exported history; imports cannot create capacity."""
    from ..common import sha256_file

    p = Path(path)
    if p.is_symlink() or sha256_file(p) != sha256:
        raise Refused("HISTORY_SNAPSHOT_CHANGED")
    doc = json.loads(p.read_text())
    ledger = MissionLedger(store)
    ledger.snapshot(mission_id)
    if doc.get("mission_id") != mission_id:
        raise Refused("HISTORY_MISSION_MISMATCH")
    for row in doc["executions"]:
        if not row.get("native_run_id") or not row.get("server_identity") or not row.get("evidence_refs"):
            raise Refused("HISTORY_NATIVE_PROVENANCE_REQUIRED")
        ledger.execution(
            mission_id,
            row["server_identity"] + ":" + row["native_run_id"],
            row["kind"],
            reserved_tokens=row["reserved_tokens"],
            reported_tokens=row.get("reported_tokens"),
            imported=True,
            evidence_refs=row["evidence_refs"],
        )
    return ledger.snapshot(mission_id)
