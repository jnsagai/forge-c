"""Explicit owner-signed product time windows; immutable budgets/history in the existing AFO store."""
from __future__ import annotations

import json
import math
import re
import time
from datetime import datetime

from ..common import utc_now
from .durable import Refused, canonical, digest

KIND = "MISSION_DEADLINE_EXTENSION"
SCHEMA = "forge-c/mission-deadline-extension/1"


def prefix(mission_id):
    return "mission-deadline-" + digest(mission_id)[:24] + "-"


def records(c, mission_id):
    start = prefix(mission_id)
    rows = c.execute("SELECT decision_id,record,sha256 FROM afo_independent_decisions "
                     "WHERE decision_id>=? AND decision_id<? AND kind=? ORDER BY rowid",
                     (start, start + "\uffff", KIND)).fetchall()
    if len(rows) > 8:
        raise Refused("MISSION_DEADLINE_EXTENSION_LIMIT")
    result = []
    for row in rows:
        record = json.loads(row["record"])
        if (digest(record) != row["sha256"] or record.get("mission_id") != mission_id
                or row["decision_id"] != start + digest(record["document"])):
            raise Refused("MISSION_DEADLINE_HISTORY_CHANGED")
        result.append(record)
    return result


def effective(c, base):
    extensions = records(c, base["mission_id"])
    if not extensions:
        return base
    deadline = base["limits"]["deadline"]
    for record in extensions:
        if (record["initial_record_sha256"] != digest(base) or record["old_deadline"] != deadline
                or not deadline < record["deadline_epoch"] or not math.isfinite(record["deadline_epoch"])):
            raise Refused("MISSION_DEADLINE_HISTORY_CHANGED")
        deadline = record["deadline_epoch"]
    return {**base, "limits": {**base["limits"], "deadline": deadline},
            "authorization_ref": extensions[-1]["authorization_ref"], "initial_limits": base["limits"],
            "initial_authorization_ref": base["authorization_ref"],
            "deadline_extensions": [{k: r[k] for k in ("old_deadline", "deadline_epoch", "authorization_ref", "accepted_at")}
                                    for r in extensions]}


def extend(store, document, eff):
    """Called only by authenticated operator CLI, never exposed through runtime-agent MCP."""
    from . import authz
    from .mission_ledger import MissionLedger

    fields = {"schema", "mission_id", "snapshot_sha256", "deadline_epoch", "authorization_ref", "request", "reason"}
    if (not isinstance(document, dict) or set(document) != fields or document.get("schema") != SCHEMA
            or not isinstance(document.get("mission_id"), str) or not 1 <= len(document["mission_id"]) <= 128
            or not re.fullmatch(r"[0-9a-f]{64}", str(document.get("snapshot_sha256", "")))
            or not isinstance(document.get("authorization_ref"), str)
            or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", document["authorization_ref"])
            or not isinstance(document.get("request"), dict)
            or set(document["request"]) != {"order_id", "driver_class", "model"}
            or any(not isinstance(v, str) or not 1 <= len(v) <= 256 for v in document["request"].values())
            or type(document.get("deadline_epoch")) not in (float, int)
            or not math.isfinite(document["deadline_epoch"])
            or not isinstance(document.get("reason"), str) or not 1 <= len(document["reason"].strip()) <= 500):
        raise Refused("MISSION_DEADLINE_EXTENSION_INPUT_INVALID")
    mid = document["mission_id"]
    decision_id = prefix(mid) + digest(document)
    with store.tx() as c:
        replay = next((r for r in records(c, mid) if r["document"] == document), None)
        if replay:
            return replay  # Historical receipt, no effect or current dispatch authority even after expiry/revocation.
    if eff.mode not in ("PILOT", "ACTIVE"):
        raise Refused("MISSION_ACTIVE_AUTHORITY_REQUIRED")
    def current_grant():
        try:
            auth = json.loads((authz.AUTH_DIR / (document["authorization_ref"] + ".json")).read_text())
        except FileNotFoundError as exc:
            raise Refused("AUTH_RECORD_MISSING") from exc
        except (ValueError, UnicodeError) as exc:
            raise Refused("AUTH_NOT_JSON") from exc
        if not isinstance(auth, dict):
            raise Refused("AUTH_SCHEMA_INVALID")
        if auth.get("authorization_id") != document["authorization_ref"]:
            raise Refused("AUTH_ID_MISMATCH")
        decision = authz.verify(auth, policy_sha256=eff.sha256 or "", mode=eff.mode,
                                action="recover_workorder", request=document["request"])
        if not decision.allow:
            raise Refused(decision.code)
        if auth.get("signed_runbook_ref") != "mission-deadline-extension-014:" + digest(document):
            raise Refused("MISSION_DEADLINE_EXTENSION_NOT_OWNER_SIGNED")
        return auth

    auth = current_grant()
    now = time.time()
    expiry = datetime.fromisoformat(auth["expires_utc"].replace("Z", "+00:00")).timestamp()
    deadline = document["deadline_epoch"]
    if not now < deadline <= min(expiry, now + float(eff.get("budgets.max_order_wall_seconds"))):
        raise Refused("MISSION_DEADLINE_EXCEEDS_CURRENT_AUTHORITY")
    with store.tx() as c:
        prior = records(c, mid)
        replay = next((r for r in prior if r["document"] == document), None)
        if replay:
            return replay
        fresh = current_grant()
        if digest(fresh) != digest(auth) or not time.time() < min(expiry, deadline):
            raise Refused("MISSION_DEADLINE_AUTHORITY_CHANGED")
        snapshot = MissionLedger._snapshot(c, mid)
        if document["snapshot_sha256"] != digest(snapshot):
            raise Refused("MISSION_SNAPSHOT_CHANGED")
        limits = snapshot["limits"]
        if (snapshot["attempts"] >= limits["max_attempts"] or snapshot["charged_tokens"] >= limits["max_tokens"]
                or snapshot["requests"] >= limits["max_requests"] or snapshot["tools"] >= limits["max_tools"]
                or snapshot["unbounded_historical_usage"]):
            raise Refused("MISSION_NON_TIME_ALLOWANCE_EXHAUSTED")
        if len(prior) >= 8:
            raise Refused("MISSION_DEADLINE_EXTENSION_LIMIT")
        if deadline <= limits["deadline"] or document["authorization_ref"] == snapshot["authorization_ref"]:
            raise Refused("MISSION_DEADLINE_EXTENSION_NOT_PROSPECTIVE")
        for row in c.execute("SELECT record FROM afo_execution_liveness"):
            execution = json.loads(row[0])
            if execution.get("mission_id") == mid and execution.get("resource_lease") != "RELEASED":
                raise Refused("MISSION_NATIVE_QUIESCENCE_REQUIRED")
        base = json.loads(c.execute("SELECT record FROM afo_missions WHERE mission_id=?", (mid,)).fetchone()[0])
        record = {"schema": "forge-c/mission-deadline-receipt/1", "mission_id": mid, "document": document,
                  "initial_record_sha256": digest(base), "old_deadline": limits["deadline"],
                  "deadline_epoch": deadline, "authorization_ref": document["authorization_ref"],
                  "grant_sha256": digest(auth), "accepted_at": utc_now(), "native_effects": False,
                  "allowance_counters_reset": False, "non_time_caps_changed": False}
        c.execute("INSERT INTO afo_independent_decisions VALUES (?,?,?,?)",
                  (decision_id, KIND, canonical(record).decode(), digest(record)))
        return record
