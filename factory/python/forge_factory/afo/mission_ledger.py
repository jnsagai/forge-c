"""DA-011/012/013: mission accounting and durable inference ownership in Conductor SQLite.

Limits and lineage are controller/authorization inputs, never proposal fields.
No expiry, continuation name or task outcome releases a possibly live resource.
"""

from __future__ import annotations

import json
import math
import time

from ..common import utc_now
from .durable import Refused, canonical, digest


def validate_limits(limits):
    """The ledger's finite-envelope validator is shared by campaign preparation."""
    required = ("max_attempts", "max_jobs", "max_requests", "max_tokens", "max_tools", "max_corrections")
    if not isinstance(limits, dict) or any(type(limits.get(k)) is not int or limits[k] < 0 for k in required):
        raise Refused("FINITE_MISSION_LIMITS_REQUIRED")
    if type(limits.get("deadline")) not in (int, float) or not math.isfinite(limits["deadline"]):
        raise Refused("FINITE_MISSION_AUTHORITY_REQUIRED")


class MissionLedger:
    def __init__(self, store):
        self.store = store

    def register(self, mission_id: str, lineage: str, limits: dict, authorization_ref: str, *, authorize) -> dict:
        validate_limits(limits)
        if not authorization_ref:
            raise Refused("FINITE_MISSION_AUTHORITY_REQUIRED")
        if not authorize(authorization_ref, limits):
            raise Refused("MISSION_REGISTRATION_NOT_AUTHORIZED")
        rec = {
            "mission_id": mission_id,
            "lineage": lineage,
            "limits": limits,
            "authorization_ref": authorization_ref,
            "created_at": utc_now(),
        }
        with self.store.tx() as c:
            old = c.execute("SELECT record FROM afo_missions WHERE mission_id=? OR lineage=?", (mission_id, lineage)).fetchone()
            if old:
                prior = json.loads(old[0])
                if any(prior[k] != rec[k] for k in ("mission_id", "lineage", "limits", "authorization_ref")):
                    raise Refused("MISSION_ALLOWANCE_RESET_FORBIDDEN")
                return prior
            c.execute("INSERT INTO afo_missions VALUES (?,?,?)", (mission_id, lineage, canonical(rec).decode()))
        return rec

    def link(self, mission_id: str, order_id: str, *, continuation_of: str | None = None) -> None:
        with self.store.tx() as c:
            if not c.execute("SELECT 1 FROM afo_missions WHERE mission_id=?", (mission_id,)).fetchone():
                raise Refused("MISSION_NOT_REGISTERED")
            if continuation_of:
                parent = c.execute("SELECT mission_id FROM afo_mission_orders WHERE order_id=?", (continuation_of,)).fetchone()
                if not parent or parent[0] != mission_id:
                    raise Refused("CONTINUATION_LINEAGE_MISMATCH")
            old = c.execute("SELECT mission_id FROM afo_mission_orders WHERE order_id=?", (order_id,)).fetchone()
            if old and old[0] != mission_id:
                raise Refused("ORDER_MISSION_REBIND_FORBIDDEN")
            c.execute("INSERT OR IGNORE INTO afo_mission_orders VALUES (?,?)", (order_id, mission_id))

    def for_order(self, order_id: str) -> str:
        with self.store.tx() as c:
            row = c.execute("SELECT mission_id FROM afo_mission_orders WHERE order_id=?", (order_id,)).fetchone()
        if not row:
            raise Refused("MISSION_LINK_REQUIRED", order_id)
        return row[0]

    @staticmethod
    def _snapshot(c, mission_id: str) -> dict:
        row = c.execute("SELECT record FROM afo_missions WHERE mission_id=?", (mission_id,)).fetchone()
        if not row:
            raise Refused("MISSION_NOT_REGISTERED")
        m = json.loads(row[0])
        from .mission_capacity import effective as capacity_effective
        from .mission_deadline import effective

        m = capacity_effective(c, m, effective(c, m))
        ex = [json.loads(r[0]) for r in c.execute("SELECT record FROM afo_mission_executions WHERE mission_id=?", (mission_id,))]
        req = [json.loads(r[0]) for r in c.execute("SELECT record FROM afo_request_ledger WHERE mission_id=?", (mission_id,))]
        # An imported native job and its observed requests must not both charge the same tokens.
        jobs_with_requests = {r["job_id"] for r in req}
        request_charges = {job: sum(r["charge"] for r in req if r["job_id"] == job) for job in jobs_with_requests}
        tokens = sum(max(r["charge"], request_charges.pop(r["identity"], 0)) for r in ex) + sum(request_charges.values())
        from collections import Counter

        counters = c.execute("SELECT job_id,kind,COUNT(*) AS n FROM afo_mission_counters WHERE mission_id=? "
                             "GROUP BY job_id,kind", (mission_id,)).fetchall()

        def count(kind, observed):
            # Later ingestion of the same native history replaces an aggregate
            # reservation, rather than adding it twice or making it disappear.
            total = 0
            for execution in ex:
                imported = (execution.get("historical_counts") or {}).get(kind, execution.get(kind, 0))
                total += max(imported, observed.pop(execution["identity"], 0))
            return total + sum(observed.values())

        requests = count("requests", dict(Counter(r["job_id"] for r in req)))
        tools = count("tools", {r["job_id"]: r["n"] for r in counters if r["kind"] == "TOOL"})
        corrections = count("corrections", {r["job_id"]: r["n"] for r in counters if r["kind"] == "CORRECTION"})
        return {
            **m,
            "attempts": sum(r["kind"] == "PRODUCT" for r in ex),
            "jobs": sum(r["kind"] in ("DIAGNOSIS", "MAINTENANCE", "LEARNING") for r in ex),
            "requests": requests,
            "tools": tools,
            "corrections": corrections,
            "charged_tokens": tokens,
            "usage_unknown": any(r.get("reported_tokens") is None for r in ex + req),
            "unique_executions": len(ex),
            "unbounded_historical_usage": any(
                r.get("imported") and r.get("reported_tokens") is None and r.get("reserved_tokens") == 0 for r in ex
            ),
        }

    def snapshot(self, mission_id: str) -> dict:
        with self.store.tx() as c:
            return self._snapshot(c, mission_id)

    def execution(
        self,
        mission_id: str,
        identity: str,
        kind: str,
        *,
        reserved_tokens: int,
        reported_tokens: int | None = None,
        imported=False,
        evidence_refs=(),
        historical_counts=None,
        now=None,
    ) -> dict:
        if (
            kind not in ("PRODUCT", "DIAGNOSIS", "MAINTENANCE", "LEARNING")
            or type(reserved_tokens) is not int
            or reserved_tokens < 0
        ):
            raise Refused("EXECUTION_ACCOUNTING_INVALID")
        if reported_tokens is not None and (type(reported_tokens) is not int or reported_tokens < 0):
            raise Refused("REPORTED_USAGE_INVALID")
        if historical_counts is not None and (
            not imported or not evidence_refs or not isinstance(historical_counts, dict)
            or set(historical_counts) != {"requests", "tools", "corrections"}
            or any(type(n) is not int or n < 0 for n in historical_counts.values())
        ):
            raise Refused("HISTORY_COUNTERS_INVALID")
        with self.store.tx() as c:
            row = c.execute("SELECT mission_id,record FROM afo_mission_executions WHERE identity=?", (identity,)).fetchone()
            if row:
                rec = json.loads(row["record"])
                if row["mission_id"] != mission_id or rec["kind"] != kind:
                    raise Refused("EXECUTION_IDENTITY_REBOUND")
                if reserved_tokens != rec["reserved_tokens"]:
                    raise Refused("EXECUTION_RESERVATION_REBOUND")
                if historical_counts is not None:
                    if not rec.get("imported"):
                        raise Refused("HISTORY_COUNTERS_INVALID")
                    if "historical_counts" in rec and rec["historical_counts"] != historical_counts:
                        raise Refused("HISTORY_COUNTERS_REBOUND")
                    rec["historical_counts"] = dict(historical_counts)
                    rec["evidence_refs"] = list(dict.fromkeys([*rec.get("evidence_refs", []), *evidence_refs]))
                if reported_tokens is not None:
                    rec["reported_tokens"] = max(reported_tokens, rec.get("reported_tokens") or 0)
                rec["charge"] = max(rec["charge"], rec.get("reported_tokens") or 0)
                c.execute("UPDATE afo_mission_executions SET record=? WHERE identity=?", (canonical(rec).decode(), identity))
                return rec
            snap = self._snapshot(c, mission_id)
            limits = snap["limits"]
            if not imported:
                if snap["unbounded_historical_usage"]:
                    raise Refused("HISTORICAL_USAGE_REQUIRES_INDEPENDENT_BOUND")
                if (time.time() if now is None else now) >= limits["deadline"]:
                    raise Refused("MISSION_DEADLINE_EXHAUSTED")
                count, cap = ("attempts", "max_attempts") if kind == "PRODUCT" else ("jobs", "max_jobs")
                if snap[count] >= limits[cap] or snap["charged_tokens"] + reserved_tokens > limits["max_tokens"]:
                    raise Refused("MISSION_ALLOWANCE_EXHAUSTED")
            rec = {
                "identity": identity,
                "kind": kind,
                "reserved_tokens": reserved_tokens,
                "reported_tokens": reported_tokens,
                "charge": max(reserved_tokens, reported_tokens or 0),
                "imported": bool(imported),
                "evidence_refs": list(evidence_refs),
                "created_at": utc_now(),
                **({"historical_counts": dict(historical_counts)} if historical_counts is not None else {}),
            }
            c.execute(
                "INSERT INTO afo_mission_executions VALUES (?,?,?,?)", (identity, mission_id, kind, canonical(rec).decode())
            )
            return rec

    def reserve_request(
        self,
        mission_id: str,
        job_id: str,
        request_id: str,
        *,
        body_sha256: str,
        input_tokens: int,
        output_cap: int,
        authorize,
        now=None,
        provider_instance=None,
    ) -> dict:
        if any(type(n) is not int or n < 0 for n in (input_tokens, output_cap)):
            raise Refused("REQUEST_LIMIT_INVALID")
        with self.store.tx() as c:
            old = c.execute("SELECT record FROM afo_request_ledger WHERE request_id=?", (request_id,)).fetchone()
            if old:
                rec = json.loads(old[0])
                if (rec["mission_id"], rec["job_id"], rec["body_sha256"]) != (mission_id, job_id, body_sha256):
                    raise Refused("REQUEST_ID_REBOUND")
                # A replay reads the reservation, but is never permission to send the generation again.
                return {**rec, "replay": True}
            if c.execute("SELECT 1 FROM afo_execution_evidence WHERE job_id=? AND kind='GENERATION_FENCE'", (job_id,)).fetchone():
                raise Refused("GENERATION_RETIREMENT_FENCED")
            snap = self._snapshot(c, mission_id)
            if not authorize() or (time.time() if now is None else now) >= snap["limits"]["deadline"]:
                raise Refused("REQUEST_NOT_AUTHORIZED")
            if snap["unbounded_historical_usage"]:
                raise Refused("HISTORICAL_USAGE_REQUIRES_INDEPENDENT_BOUND")
            if snap["charged_tokens"] > snap["limits"]["max_tokens"]:
                raise Refused("MISSION_TOKEN_CAPACITY_EXHAUSTED")
            if snap["requests"] >= snap["limits"]["max_requests"]:
                raise Refused("MISSION_REQUESTS_EXHAUSTED")
            charge = input_tokens + output_cap
            # A job reservation is an envelope; request reservations replace its charge, not add it twice.
            other = c.execute("SELECT record FROM afo_request_ledger WHERE job_id=?", (job_id,)).fetchall()
            job = c.execute(
                "SELECT record FROM afo_mission_executions WHERE identity=? AND mission_id=?", (job_id, mission_id)
            ).fetchone()
            if not job:
                raise Refused("REQUEST_JOB_NOT_RESERVED")
            envelope = json.loads(job[0])
            if sum(json.loads(r[0])["charge"] for r in other) + charge > envelope["reserved_tokens"]:
                raise Refused("JOB_TOKEN_ENVELOPE_EXHAUSTED")
            ownership = c.execute("SELECT holder FROM afo_resource_ownership WHERE resource=?", ("inference",)).fetchone()
            if not ownership or ownership[0] != job_id:
                raise Refused("EXECUTION_INFERENCE_LEASE_REQUIRED")
            slot = c.execute("SELECT holder FROM afo_resource_ownership WHERE resource=?", ("generation",)).fetchone()
            if slot and slot[0]:
                raise Refused("INFERENCE_REQUEST_BUSY")
            rec = {
                "request_id": request_id,
                "accounting": "settled-usage/1",
                "mission_id": mission_id,
                "job_id": job_id,
                "body_sha256": body_sha256,
                "input_tokens_reserved": input_tokens,
                "output_cap": output_cap,
                "reserved_tokens": charge,
                "reported_tokens": None,
                "charge": charge,
                "state": "RESERVED",
                "created_at": utc_now(),
                **(
                    {"provider_instance": provider_instance, "provider_instance_sha256": digest(provider_instance)}
                    if provider_instance is not None
                    else {}
                ),
            }
            c.execute(
                "INSERT INTO afo_request_ledger VALUES (?,?,?,?,?)",
                (request_id, mission_id, job_id, "RESERVED", canonical(rec).decode()),
            )
            c.execute(
                "INSERT INTO afo_resource_ownership VALUES ('generation',?,1,?) ON CONFLICT(resource) "
                "DO UPDATE SET holder=excluded.holder,epoch=epoch+1,record=excluded.record",
                (request_id, canonical({"mission_id": mission_id}).decode()),
            )
            return {**rec, "replay": False}

    def start_request(self, request_id, *, authorize):
        with self.store.tx() as c:
            row = c.execute("SELECT record,state FROM afo_request_ledger WHERE request_id=?", (request_id,)).fetchone()
            if not row or row["state"] != "RESERVED":
                raise Refused("REQUEST_START_FENCED")
            rec = json.loads(row["record"])
            if c.execute(
                "SELECT 1 FROM afo_execution_evidence WHERE job_id=? AND kind='GENERATION_FENCE'", (rec["job_id"],)
            ).fetchone():
                raise Refused("GENERATION_RETIREMENT_FENCED")
            table = "afo_product_jobs" if rec["job_id"].startswith("afo-product-") else "afo_local_agent_jobs"
            job = c.execute(f"SELECT record FROM {table} WHERE job_id=?", (rec["job_id"],)).fetchone()  # noqa: S608 - two literal table names
            order = (
                c.execute("SELECT state FROM afo_work_orders WHERE order_id=?", (json.loads(job[0])["order_id"],)).fetchone()
                if job
                else None
            )
            if not order or order[0] not in ("ADMITTED", "RUNNING", "WAITING_RECOVERY", "WAITING_EXTERNAL_CHANGE"):
                raise Refused("REQUEST_ORDER_NOT_ACTIVE")
            live = c.execute("SELECT record FROM afo_execution_liveness WHERE job_id=?", (rec["job_id"],)).fetchone()
            ex = json.loads(live[0]) if live else {}
            if (
                not authorize()
                or ex.get("resource_lease") != "HELD"
                or ex.get("task_outcome") != "ACTIVE"
                or ex.get("authorization_state") != "VALID"
                or ex.get("execution_liveness") in ("NOT_STARTED", "QUIESCENT")
            ):
                raise Refused("REQUEST_AUTHORITY_CHANGED_BEFORE_PROVIDER_SEND")
            rec.update(state="SENT", sent_at=utc_now())
            c.execute(
                "UPDATE afo_request_ledger SET state='SENT',record=? WHERE request_id=?", (canonical(rec).decode(), request_id)
            )
            return rec

    def reconcile_request(
        self,
        request_id: str,
        *,
        input_tokens=None,
        cached_tokens=None,
        output_tokens=None,
        quiescent: bool = False,
        evidence_ref: str | None = None,
    ) -> dict:
        with self.store.tx() as c:
            row = c.execute("SELECT record FROM afo_request_ledger WHERE request_id=?", (request_id,)).fetchone()
            if not row:
                raise Refused("UNKNOWN_REQUEST")
            rec = json.loads(row[0])
            if input_tokens is not None and output_tokens is not None:
                if any(type(n) is not int or n < 0 for n in (input_tokens, output_tokens, cached_tokens or 0)):
                    raise Refused("REPORTED_USAGE_INVALID")
                if input_tokens + output_tokens >= (rec.get("reported_tokens") or 0):
                    rec.update(input_tokens=input_tokens, cached_tokens=cached_tokens,
                               output_tokens=output_tokens, reported_tokens=input_tokens + output_tokens)
                rec["charge"] = max(rec["charge"], rec["reported_tokens"])
            if rec.get("accounting") == "settled-usage/1" and rec["state"] == "QUIESCENT":
                # A late usage observation cannot resurrect a completed request.
                quiescent, evidence_ref = True, rec["quiescence_ref"]
            rec["state"] = "QUIESCENT" if quiescent and evidence_ref else "UNKNOWN"
            rec["quiescence_ref"] = evidence_ref if rec["state"] == "QUIESCENT" else None
            if (rec.get("accounting") == "settled-usage/1" and rec["state"] == "QUIESCENT"
                    and rec.get("reported_tokens") is not None):
                # Release only the unused per-request reservation, inside the
                # unchanged job envelope. Mission/job charges and all original
                # reservation/history fields remain; unknown usage stays reserved.
                rec["charge"] = rec["reported_tokens"]
            c.execute(
                "UPDATE afo_request_ledger SET state=?,record=? WHERE request_id=?",
                (rec["state"], canonical(rec).decode(), request_id),
            )
            if rec["state"] == "QUIESCENT":
                c.execute(
                    "UPDATE afo_resource_ownership SET holder=NULL,epoch=epoch+1 WHERE resource='generation' AND holder=?",
                    (request_id,),
                )
            return rec

    def count(self, mission_id, job_id, kind, event_id):
        if kind not in ("TOOL", "CORRECTION"):
            raise Refused("MISSION_COUNTER_INVALID")
        with self.store.tx() as c:
            old = c.execute("SELECT * FROM afo_mission_counters WHERE event_id=?", (event_id,)).fetchone()
            if old:
                if (old["mission_id"], old["job_id"], old["kind"]) != (mission_id, job_id, kind):
                    raise Refused("MISSION_COUNTER_REBOUND")
                return
            snap = self._snapshot(c, mission_id)
            field, cap = ("tools", "max_tools") if kind == "TOOL" else ("corrections", "max_corrections")
            if snap[field] >= snap["limits"][cap]:
                raise Refused("MISSION_" + cap.upper() + "_EXHAUSTED")
            c.execute("INSERT INTO afo_mission_counters VALUES (?,?,?,?)", (event_id, mission_id, job_id, kind))

    def acquire_inference(self, job_id: str, mission_id: str) -> int:
        with self.store.tx() as c:
            old = c.execute("SELECT holder,epoch FROM afo_resource_ownership WHERE resource='inference'").fetchone()
            if old and old["holder"] not in (None, job_id):
                raise Refused("INFERENCE_EXECUTION_BUSY", old["holder"])
            if not c.execute(
                "SELECT 1 FROM afo_mission_executions WHERE identity=? AND mission_id=?", (job_id, mission_id)
            ).fetchone():
                raise Refused("EXECUTION_RESERVATION_REQUIRED")
            epoch = old["epoch"] if old and old["holder"] == job_id else (old["epoch"] + 1 if old else 1)
            c.execute(
                "INSERT INTO afo_resource_ownership VALUES ('inference',?,?,?) ON CONFLICT(resource) "
                "DO UPDATE SET holder=excluded.holder,epoch=excluded.epoch,record=excluded.record",
                (job_id, epoch, canonical({"mission_id": mission_id, "lease_expiry_releases": False}).decode()),
            )
            return epoch

    def release_inference(self, job_id: str, *, proof: dict) -> None:
        # Only execution_lifecycle supplies an authenticated proof. A task state or cancel ACK is insufficient.
        with self.store.tx() as c:
            r = c.execute("SELECT record FROM afo_execution_liveness WHERE job_id=?", (job_id,)).fetchone()
            if not r:
                raise Refused("QUIESCENCE_NOT_PROVEN")
            ex = json.loads(r[0])
            evidence = c.execute(
                "SELECT record,sha256 FROM afo_execution_evidence WHERE job_id=? AND kind='QUIESCENCE'", (job_id,)
            ).fetchone()
            if (
                ex.get("execution_liveness") not in ("NOT_STARTED", "QUIESCENT")
                or not evidence
                or json.loads(evidence["record"]) != proof
                or evidence["sha256"] != digest(proof)
                or not proof
            ):
                raise Refused("QUIESCENCE_NOT_PROVEN")
            active = c.execute(
                "SELECT COUNT(*) FROM afo_request_ledger WHERE job_id=? AND state NOT IN ('QUIESCENT','RESERVED')", (job_id,)
            ).fetchone()[0]
            if active:
                raise Refused("PROVIDER_QUIESCENCE_UNPROVEN")
            c.execute(
                "UPDATE afo_resource_ownership SET holder=NULL,epoch=epoch+1 WHERE resource='inference' AND holder=?", (job_id,)
            )
            for rr in c.execute("SELECT request_id,record FROM afo_request_ledger WHERE job_id=?", (job_id,)).fetchall():
                rec = json.loads(rr["record"])
                rec.update(state="QUIESCENT", quiescence_ref=proof["evidence_ref"])
                c.execute(
                    "UPDATE afo_request_ledger SET state=?,record=? WHERE request_id=?",
                    ("QUIESCENT", canonical(rec).decode(), rr["request_id"]),
                )
                c.execute(
                    "UPDATE afo_resource_ownership SET holder=NULL,epoch=epoch+1 WHERE resource='generation' AND holder=?",
                    (rr["request_id"],),
                )
