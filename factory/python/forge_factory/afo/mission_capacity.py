"""Explicit operator capacity amendments; no automatic refill or exhausted-mission reset."""
from __future__ import annotations

import json
import re
from contextlib import nullcontext

from ..common import utc_now
from .durable import Refused, canonical, digest

KIND = "MISSION_CAPACITY_AMENDMENT"
SCHEMA = "forge-c/mission-capacity-amendment/1"
CAPS = {"max_attempts": "attempts", "max_jobs": "jobs", "max_requests": "requests",
        "max_tokens": "charged_tokens", "max_tools": "tools", "max_corrections": "corrections"}
POLICY = {"max_attempts": "max_order_attempts", "max_jobs": "max_recovery_model_calls_per_order",
          "max_requests": "max_inference_requests_per_order", "max_tokens": "max_model_tokens_per_order",
          "max_tools": "max_tool_calls_per_order"}


def prefix(mission_id):
    return "mission-capacity-" + digest(mission_id)[:24] + "-"


def records(c, mission_id):
    start = prefix(mission_id)
    rows = c.execute("SELECT decision_id,record,sha256 FROM afo_independent_decisions "
                     "WHERE decision_id>=? AND decision_id<? AND kind=? ORDER BY rowid",
                     (start, start + "\uffff", KIND)).fetchall()
    if len(rows) > 8:
        raise Refused("MISSION_CAPACITY_AMENDMENT_LIMIT")
    result = []
    for row in rows:
        record = json.loads(row["record"])
        if (digest(record) != row["sha256"] or record.get("mission_id") != mission_id
                or row["decision_id"] != start + digest(record["document"])):
            raise Refused("MISSION_CAPACITY_HISTORY_CHANGED")
        result.append(record)
    return result


def effective(c, base, current):
    amendments = records(c, base["mission_id"])
    if not amendments:
        return current
    caps = {key: base["limits"][key] for key in CAPS}
    for record in amendments:
        new = record["document"]["limits"]
        if (record["initial_record_sha256"] != digest(base) or record["old_limits"] != caps
                or set(new) != set(CAPS) or any(type(new[k]) is not int or new[k] < caps[k] for k in CAPS)
                or new == caps or new["max_corrections"] != caps["max_corrections"]):
            raise Refused("MISSION_CAPACITY_HISTORY_CHANGED")
        caps = new
    return {**current, "limits": {**current["limits"], **caps},
            "initial_limits": base["limits"], "initial_authorization_ref": base["authorization_ref"],
            "capacity_amendments": [{k: r[k] for k in ("authorization_ref", "old_limits", "document", "accepted_at")}
                                    for r in amendments]}


def amend(store, document, eff):
    """Authenticated operator CLI only. Does not admit work, extend time or reopen any order."""
    from . import authz
    from .mission_ledger import MissionLedger
    from .operations import Intent, configured

    fields = {"schema", "mission_id", "snapshot_sha256", "limits", "authorization_ref", "request", "reason",
              "operator_epoch"}
    if (not isinstance(document, dict) or set(document) != fields or document.get("schema") != SCHEMA
            or not isinstance(document.get("mission_id"), str) or not 1 <= len(document["mission_id"]) <= 128
            or not re.fullmatch(r"[0-9a-f]{64}", str(document.get("snapshot_sha256", "")))
            or not isinstance(document.get("authorization_ref"), str)
            or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", document["authorization_ref"])
            or not isinstance(document.get("request"), dict)
            or set(document["request"]) != {"order_id", "driver_class", "model"}
            or any(not isinstance(v, str) or not 1 <= len(v) <= 256 for v in document["request"].values())
            or type(document.get("operator_epoch")) is not int or document["operator_epoch"] < 0
            or not isinstance(document.get("reason"), str) or not 1 <= len(document["reason"].strip()) <= 500
            or not isinstance(document.get("limits"), dict) or set(document["limits"]) != set(CAPS)
            or any(type(v) is not int or v < 1 for v in document["limits"].values())):
        raise Refused("MISSION_CAPACITY_INPUT_INVALID")
    mid = document["mission_id"]
    with store.tx() as c:
        replay = next((r for r in records(c, mid) if r["document"] == document), None)
        if replay:
            return replay  # Receipt only: no new dispatch authority after expiry, revoke or stop.
    if eff.mode not in ("PILOT", "ACTIVE"):
        raise Refused("MISSION_ACTIVE_AUTHORITY_REQUIRED")

    def current_grant():
        path = authz.AUTH_DIR / (document["authorization_ref"] + ".json")
        try:
            auth = json.loads(path.read_text())
        except FileNotFoundError as exc:
            raise Refused("AUTH_RECORD_MISSING") from exc
        except (ValueError, UnicodeError) as exc:
            raise Refused("AUTH_NOT_JSON") from exc
        if not isinstance(auth, dict):
            raise Refused("AUTH_SCHEMA_INVALID")
        if auth.get("authorization_id") != document["authorization_ref"]:
            raise Refused("AUTH_ID_MISMATCH")
        allowed = authz.verify(auth, policy_sha256=eff.sha256 or "", mode=eff.mode,
                               action="recover_workorder", request=document["request"])
        if not allowed.allow:
            raise Refused(allowed.code)
        if auth.get("signed_runbook_ref") != "mission-capacity-amendment-014:" + digest(document):
            raise Refused("MISSION_CAPACITY_NOT_OWNER_SIGNED")
        return auth

    auth = current_grant()
    new = document["limits"]
    policy_caps = {cap: eff.get("budgets." + key) for cap, key in POLICY.items()}
    if (any(type(value) is not int or value < 1 for value in policy_caps.values())
            or any(new[key] > value for key, value in policy_caps.items())):
        raise Refused("MISSION_CAPACITY_EXCEEDS_POLICY")
    intent = Intent() if configured() else None
    # Same lock ordering as operator pause/stop: intent, then the existing database.
    with intent.lock() if intent else nullcontext():
        observed = intent.read() if intent else {"mode": "RUNNING", "epoch": 0}
        if observed["mode"] != "RUNNING" or observed["epoch"] != document["operator_epoch"]:
            raise Refused("OPERATIONS_CAPACITY_FENCED")
        with store.tx() as c:
            prior = records(c, mid)
            replay = next((r for r in prior if r["document"] == document), None)
            if replay:
                return replay
            fresh = current_grant()
            if digest(fresh) != digest(auth):
                raise Refused("MISSION_CAPACITY_AUTHORITY_CHANGED")
            snapshot = MissionLedger._snapshot(c, mid)
            if document["snapshot_sha256"] != digest(snapshot):
                raise Refused("MISSION_SNAPSHOT_CHANGED")
            old = {key: snapshot["limits"][key] for key in CAPS}
            if (any(snapshot[count] >= old[cap] for cap, count in CAPS.items())
                    or snapshot["unbounded_historical_usage"]):
                raise Refused("MISSION_NON_TIME_ALLOWANCE_EXHAUSTED")
            if (new == old or any(new[k] < old[k] for k in CAPS)
                    or new["max_corrections"] != old["max_corrections"]):
                raise Refused("MISSION_CAPACITY_NOT_PROSPECTIVE")
            if len(prior) >= 8:
                raise Refused("MISSION_CAPACITY_AMENDMENT_LIMIT")
            for row in c.execute("SELECT record FROM afo_execution_liveness"):
                execution = json.loads(row[0])
                if execution.get("mission_id") == mid and execution.get("resource_lease") != "RELEASED":
                    raise Refused("MISSION_NATIVE_QUIESCENCE_REQUIRED")
            for row in c.execute("SELECT record FROM afo_local_agent_jobs"):
                job = json.loads(row[0])
                if job.get("mission_id") == mid and job.get("state") not in (
                        "SUCCEEDED", "FAILED", "BLOCKED", "CANCELLED", "TIMED_OUT"):
                    raise Refused("MISSION_NATIVE_QUIESCENCE_REQUIRED")
            base = json.loads(c.execute("SELECT record FROM afo_missions WHERE mission_id=?", (mid,)).fetchone()[0])
            record = {"schema": "forge-c/mission-capacity-receipt/1", "mission_id": mid,
                      "document": document, "initial_record_sha256": digest(base), "old_limits": old,
                      "authorization_ref": document["authorization_ref"], "grant_sha256": digest(auth),
                      "accepted_at": utc_now(), "native_effects": False, "deadline_changed": False,
                      "allowance_counters_reset": False, "orders_reopened": False}
            c.execute("INSERT INTO afo_independent_decisions VALUES (?,?,?,?)",
                      (prefix(mid) + digest(document), KIND, canonical(record).decode(), digest(record)))
            return record
