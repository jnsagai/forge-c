"""Authenticated operator provisioning of bounded mission lineage; no grant signing/renewal."""

from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path

from .durable import Refused
from .mission_ledger import MissionLedger


def register(store, document, eff):
    from . import authz

    if eff.mode not in ("PILOT", "ACTIVE"):
        raise Refused("MISSION_ACTIVE_AUTHORITY_REQUIRED")
    required = {"mission_id", "lineage", "limits", "authorization_ref", "request", "orders"}
    if set(document) != required:
        raise Refused("MISSION_ADMIN_INPUT_INVALID")
    limits = document["limits"]
    ref = document["authorization_ref"]
    grant = authz.find(eff.mode, eff.sha256 or "", ref=ref, action="recover_workorder", request=document["request"])
    if not grant.allow:
        raise Refused(grant.code)
    auth = json.loads((authz.AUTH_DIR / f"{ref}.json").read_text())
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
    else:
        rec = ledger.register(document["mission_id"], document["lineage"], limits, ref, authorize=lambda *_: grant.allow)
    for entry in document["orders"]:
        order = store.order(entry["order_id"])
        if not order:
            raise Refused("MISSION_ORDER_UNKNOWN")
        env = json.loads(order["envelope"])
        allowed = authz.find(
            eff.mode,
            eff.sha256 or "",
            ref=ref,
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
