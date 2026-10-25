"""DA-013: native liveness is independent of terminal business outcome.

A transport cancel acknowledgment is never termination evidence. No listing gap,
lease timeout, or idle GPU observation releases the inference owner.
"""

from __future__ import annotations

import json
import os

from ..common import utc_now
from ..fabro.client import run_status
from .durable import Refused, canonical, digest, validate
from .mission_ledger import MissionLedger

TERMINAL_NATIVE = {"SUCCEEDED", "FAILED", "CANCELLED", "CANCELED"}


class Executions:
    def __init__(self, store):
        self.store = store

    def get(self, job_id: str) -> dict | None:
        with self.store.tx() as c:
            row = c.execute("SELECT record FROM afo_execution_liveness WHERE job_id=?", (job_id,)).fetchone()
        return json.loads(row[0]) if row else None

    def reserve(self, job_id: str, mission_id: str, nonce: str) -> dict:
        old = self.get(job_id)
        if old:
            if old["mission_id"] != mission_id or old["launch_nonce"] != nonce:
                raise Refused("EXECUTION_IDENTITY_REBOUND")
            return old
        epoch = MissionLedger(self.store).acquire_inference(job_id, mission_id)
        rec = {
            "schema_version": "1.0",
            "mission_id": mission_id,
            "job_id": job_id,
            "execution_id": "execution-" + digest([mission_id, job_id, nonce])[:24],
            "revision": 1,
            "lease_epoch": epoch,
            "launch_nonce": nonce,
            "authorization_state": "VALID",
            "admission_state": "RESERVED",
            "identity_state": "NONE",
            "native_run_ids": [],
            "execution_liveness": "NOT_STARTED",
            "cancellation_state": "NOT_REQUESTED",
            "cancel_attempts": 0,
            "last_cancel_error": None,
            "resource_lease": "HELD",
            "task_outcome": "ACTIVE",
            "terminal_reason": None,
            "quiescence_evidence_ref": None,
            "outcome_evidence_ref": None,
            "last_reconciled_at": None,
        }
        validate("execution-lifecycle", rec)
        with self.store.tx() as c:
            c.execute(
                "INSERT OR IGNORE INTO afo_execution_liveness VALUES (?,?,?,?)",
                (rec["execution_id"], job_id, mission_id, canonical(rec).decode()),
            )
        return self.get(job_id)

    def _write(self, rec: dict, expected_revision: int) -> dict:
        validate("execution-lifecycle", rec)
        with self.store.tx() as c:
            old = c.execute("SELECT record FROM afo_execution_liveness WHERE job_id=?", (rec["job_id"],)).fetchone()
            if not old or json.loads(old[0])["revision"] != expected_revision:
                raise Refused("EXECUTION_FENCE_STALE")
            if rec["execution_liveness"] in ("QUIESCENT", "NOT_STARTED") and rec.get("resource_lease") == "HELD":
                active = c.execute(
                    "SELECT COUNT(*) FROM afo_request_ledger WHERE job_id=? AND state NOT IN ('QUIESCENT','RESERVED')",
                    (rec["job_id"],),
                ).fetchone()[0]
                if active:
                    raise Refused("PROVIDER_QUIESCENCE_UNPROVEN")
            owner = c.execute("SELECT holder,epoch FROM afo_resource_ownership WHERE resource='inference'").fetchone()
            if rec["resource_lease"] == "HELD" and (
                not owner or owner["holder"] != rec["job_id"] or owner["epoch"] != rec["lease_epoch"]
            ):
                raise Refused("EXECUTION_LEASE_FENCED")
            rec = {**rec, "revision": expected_revision + 1, "last_reconciled_at": utc_now()}
            c.execute("UPDATE afo_execution_liveness SET record=? WHERE job_id=?", (canonical(rec).decode(), rec["job_id"]))
        return rec

    def dispatch_intent(self, job_id: str) -> dict:
        rec = self.get(job_id)
        if rec["admission_state"] != "RESERVED" or rec["authorization_state"] != "VALID" or rec["task_outcome"] != "ACTIVE":
            raise Refused("EXECUTION_NOT_DISPATCHABLE")
        return self._write(
            {
                **rec,
                "admission_state": "DISPATCH_INTENT_RECORDED",
                "identity_state": "UNCONFIRMED",
                "execution_liveness": "POSSIBLY_LIVE",
            },
            rec["revision"],
        )

    def not_dispatched(self, job_id: str, *, failure_type: str) -> dict:
        """Only the local launch boundary supplies this proof; native errors never do."""
        rec = self.get(job_id)
        self._check_not_dispatched(rec)
        proof = {
            "kind": "LOCAL_LAUNCH_NOT_STARTED",
            "job_id": job_id,
            "launch_nonce": rec["launch_nonce"],
            "lease_epoch": rec["lease_epoch"],
            "failure_type": failure_type,
            "evidence_ref": "local-launch-not-started:" + digest([job_id, rec["launch_nonce"], rec["lease_epoch"], failure_type]),
        }
        self._save_evidence(job_id, "LAUNCH_NOT_STARTED", proof)
        return self._quiescent(rec, proof)

    @staticmethod
    def _check_not_dispatched(rec):
        if (
            rec["admission_state"] != "DISPATCH_INTENT_RECORDED"
            or rec["native_run_ids"]
            or rec["identity_state"] not in ("NONE", "UNCONFIRMED")
        ):
            raise Refused("LAUNCH_NOT_STARTED_CONTRADICTED")

    def adopt(self, job_id: str, run_ids: list[str]) -> dict:
        rec = self.get(job_id)
        ids = sorted(set(rec["native_run_ids"]) | set(run_ids))
        if not ids or rec["admission_state"] == "RESERVED" or rec["resource_lease"] == "RELEASED":
            raise Refused("NATIVE_ADOPTION_WITHOUT_LIVE_INTENT")
        return self._write(
            {
                **rec,
                "native_run_ids": ids,
                "admission_state": "NATIVE_ACCEPTED",
                "identity_state": "CONFIRMED" if len(ids) == 1 else "AMBIGUOUS",
                "execution_liveness": "LIVE" if len(ids) == 1 else "UNKNOWN",
            },
            rec["revision"],
        )

    def outcome(self, job_id: str, outcome: str, reason: str, evidence_ref: str | None = None) -> dict:
        rec = self.get(job_id)
        if rec["task_outcome"] != "ACTIVE" and rec["task_outcome"] != outcome:
            raise Refused("TERMINAL_TASK_REENTRY_FORBIDDEN")
        if outcome == "RECOVERED":
            raise Refused("RECOVERED_REQUIRES_INDEPENDENT_VERIFICATION")
        return self._write(
            {
                **rec,
                "task_outcome": outcome,
                "terminal_reason": reason,
                "outcome_evidence_ref": evidence_ref or "execution-outcome:" + digest([job_id, outcome, reason]),
                "cancellation_state": "REQUESTED"
                if rec["execution_liveness"] in ("POSSIBLY_LIVE", "LIVE", "UNKNOWN")
                and rec["cancellation_state"] == "NOT_REQUESTED"
                else rec["cancellation_state"],
            },
            rec["revision"],
        )

    def revoke(self, job_id: str, state="REVOKED") -> dict:
        rec = self.get(job_id)
        if state not in ("REVOKED", "EXPIRED"):
            raise Refused("AUTHORIZATION_STATE_INVALID")
        return self._write(
            {
                **rec,
                "authorization_state": state,
                "cancellation_state": "REQUESTED"
                if rec["execution_liveness"] in ("POSSIBLY_LIVE", "LIVE", "UNKNOWN")
                and rec["cancellation_state"] == "NOT_REQUESTED"
                else rec["cancellation_state"],
            },
            rec["revision"],
        )

    def reconcile(self, job_id: str, client, *, cancel=False) -> dict:
        rec = self.get(job_id)
        if rec["resource_lease"] == "RELEASED":
            return rec
        proof = self._evidence(job_id, "QUIESCENCE")
        if rec["execution_liveness"] in ("QUIESCENT", "NOT_STARTED") and proof:
            MissionLedger(self.store).release_inference(job_id, proof=proof)
            return self._write({**rec, "resource_lease": "RELEASED"}, rec["revision"])
        not_started = self._evidence(job_id, "LAUNCH_NOT_STARTED")
        if not_started:
            self._check_not_dispatched(rec)
            if any(not_started.get(k) != rec[k] for k in ("job_id", "launch_nonce", "lease_epoch")):
                raise Refused("LAUNCH_NOT_STARTED_BINDING_CHANGED")
            return self._quiescent(rec, not_started)
        if rec["admission_state"] == "RESERVED":
            # Dispatch intent and the external effect are ordered; this execution never contacted native Fabro.
            if cancel or rec["authorization_state"] != "VALID" or rec["task_outcome"] != "ACTIVE":
                return self._quiescent(rec, {"kind": "NOT_DISPATCHED", "evidence_ref": "execution-intent:" + rec["execution_id"]})
            return rec
        if not rec["native_run_ids"] or rec["identity_state"] == "AMBIGUOUS":
            try:
                hits = [
                    r["id"]
                    for r in client.list_runs(limit=200)
                    if (r.get("labels") or {}).get("afo_agent") == job_id
                    and (r.get("labels") or {}).get("afo_nonce") == rec["launch_nonce"]
                ]
                if hits:
                    rec = self.adopt(job_id, hits)
            except Exception:  # noqa: BLE001, S110 - retained uncertainty, never a relaunch permission
                pass
        if not rec["native_run_ids"]:
            return self._write({**rec, "execution_liveness": "UNKNOWN"}, rec["revision"])
        observations, all_terminal = {}, True
        ids = rec["native_run_ids"]
        cursor = (self._evidence(job_id, "CURSOR") or {"offset": 0})["offset"] % len(ids)
        bounded = (ids[cursor:] + ids[:cursor])[:4]
        self._save_evidence(job_id, "CURSOR", {"offset": (cursor + len(bounded)) % len(ids)})
        for rid in bounded:
            try:
                if os.environ.get("FORGE_DURABLE_AUTONOMY") == "1":
                    from .dependency_wait import probe

                    observed = probe(
                        self.store, "native:" + job_id, "status:" + rid, lambda rid=rid: self._observe_native(client, rid)
                    )
                    status = observed.get("result", {}).get("status", "UNKNOWN")
                else:
                    status = run_status(client.get_run(rid))
            except Exception:  # noqa: BLE001 - unreachable/404 is not proof of native termination
                status = "UNKNOWN"
            observations[rid] = status
            if status not in TERMINAL_NATIVE:
                all_terminal = False
        # Multiple nonce matches can conceal other dispatch outcomes. A bounded list alone cannot settle that ambiguity.
        if all_terminal and rec["identity_state"] == "CONFIRMED":
            return self._quiescent(
                rec,
                {
                    "kind": "AUTHORITATIVE_NATIVE_TERMINAL",
                    "evidence_ref": "native-terminals:" + digest(observations),
                    "native_run_ids": rec["native_run_ids"],
                    "observations": observations,
                },
            )
        if cancel or rec["authorization_state"] != "VALID" or rec["task_outcome"] != "ACTIVE":
            rec["cancellation_state"] = "REQUESTED"
            for rid, status in observations.items():
                if status in TERMINAL_NATIVE:
                    continue
                rec["cancel_attempts"] += 1
                try:
                    if os.environ.get("FORGE_DURABLE_AUTONOMY") == "1":
                        from .dependency_wait import probe

                        cancel_observation = probe(
                            self.store,
                            "native:" + job_id,
                            "cancel:" + rid,
                            lambda rid=rid: {"ok": False, "code": client.cancel(rid)},
                        )
                        if not cancel_observation.get("due"):
                            rec["cancel_attempts"] -= 1
                            continue
                        code = cancel_observation.get("result", {}).get("code")
                    else:
                        code = client.cancel(rid)
                    if code in (200, 202, 204):
                        rec["cancellation_state"] = "ACKNOWLEDGED"
                        rec["last_cancel_error"] = None
                    else:
                        rec["last_cancel_error"] = f"HTTP_{code}"
                except Exception as exc:  # noqa: BLE001 - cancellation remains pending and visible
                    rec["last_cancel_error"] = type(exc).__name__
        rec["execution_liveness"] = (
            "LIVE" if rec["identity_state"] == "CONFIRMED" and all(s != "UNKNOWN" for s in observations.values()) else "UNKNOWN"
        )
        return self._write(rec, rec["revision"])

    @staticmethod
    def _observe_native(client, rid):
        status = run_status(client.get_run(rid))
        return {"ok": status != "UNKNOWN", "status": status}

    def _evidence(self, job_id, kind):
        with self.store.tx() as c:
            row = c.execute(
                "SELECT record,sha256 FROM afo_execution_evidence WHERE job_id=? AND kind=?", (job_id, kind)
            ).fetchone()
        if not row:
            return None
        value = json.loads(row["record"])
        if digest(value) != row["sha256"]:
            raise Refused("EXECUTION_EVIDENCE_CHANGED")
        return value

    def _save_evidence(self, job_id, kind, value):
        with self.store.tx() as c:
            old = c.execute("SELECT sha256 FROM afo_execution_evidence WHERE job_id=? AND kind=?", (job_id, kind)).fetchone()
            if kind in ("QUIESCENCE", "LAUNCH_NOT_STARTED") and old and old[0] != digest(value):
                raise Refused("QUIESCENCE_EVIDENCE_REBOUND")
            c.execute(
                "INSERT INTO afo_execution_evidence VALUES (?,?,?,?) ON CONFLICT(job_id,kind) "
                "DO UPDATE SET record=excluded.record,sha256=excluded.sha256",
                (job_id, kind, canonical(value).decode(), digest(value)),
            )

    def _quiescent(self, rec: dict, proof: dict) -> dict:
        self._save_evidence(rec["job_id"], "NATIVE_TERMINAL", proof)
        try:
            rec = self._write(
                {
                    **rec,
                    "execution_liveness": "NOT_STARTED"
                    if rec["admission_state"] == "RESERVED" or proof["kind"] == "LOCAL_LAUNCH_NOT_STARTED"
                    else "QUIESCENT",
                    "identity_state": "NONE" if proof["kind"] == "LOCAL_LAUNCH_NOT_STARTED" else rec["identity_state"],
                    "quiescence_evidence_ref": None
                    if rec["admission_state"] == "RESERVED" or proof["kind"] == "LOCAL_LAUNCH_NOT_STARTED"
                    else proof["evidence_ref"],
                    "cancellation_state": "QUIESCENCE_CONFIRMED"
                    if rec["cancellation_state"] != "NOT_REQUESTED" or rec["authorization_state"] != "VALID"
                    else "NOT_REQUESTED",
                },
                rec["revision"],
            )
        except Refused as exc:
            if exc.code != "PROVIDER_QUIESCENCE_UNPROVEN":
                raise
            self._save_evidence(rec["job_id"], "NATIVE_TERMINAL", proof)
            return self._write({**rec, "execution_liveness": "UNKNOWN", "quiescence_evidence_ref": None}, rec["revision"])
        self._save_evidence(rec["job_id"], "QUIESCENCE", proof)
        MissionLedger(self.store).release_inference(rec["job_id"], proof=proof)
        return self._write({**rec, "resource_lease": "RELEASED"}, rec["revision"])

    def pending(self) -> list[dict]:
        with self.store.tx() as c:
            rows = [json.loads(r[0]) for r in c.execute("SELECT record FROM afo_execution_liveness")]
        return [r for r in rows if r["resource_lease"] == "HELD"]

    def verified_outcome(self, job_id, decision_id):
        """Only the independent release/gate decision can complete an engineering recovery."""
        with self.store.tx() as c:
            row = c.execute(
                "SELECT record,sha256 FROM afo_independent_decisions WHERE decision_id=? AND kind='VERIFICATION'", (decision_id,)
            ).fetchone()
        if not row:
            raise Refused("INDEPENDENT_VERIFICATION_UNRESOLVED")
        decision = json.loads(row["record"])
        if digest(decision) != row["sha256"]:
            raise Refused("INDEPENDENT_VERIFICATION_CHANGED")
        from .completion_receipt import Receipts

        receipt = Receipts(self.store).latest(decision["receipt_id"])
        if not receipt or receipt["job_id"] != job_id or decision["plan_sha256"] != receipt["bound_plan"]["sha256"]:
            raise Refused("VERIFICATION_EXECUTION_BINDING_MISMATCH")
        rec = self.get(job_id)
        if rec["execution_liveness"] != "QUIESCENT" or rec["resource_lease"] != "RELEASED":
            raise Refused("VERIFIED_RECOVERY_NATIVE_QUIESCENCE_REQUIRED")
        outcome = "RECOVERED" if decision["passed"] else "BLOCKED"
        if rec["task_outcome"] not in ("ACTIVE", outcome):
            raise Refused("TERMINAL_TASK_REENTRY_FORBIDDEN")
        return self._write(
            {
                **rec,
                "task_outcome": outcome,
                "terminal_reason": "INDEPENDENT_REPAIR_VERIFIED" if decision["passed"] else "REPAIR_VERIFICATION_FAILED",
                "outcome_evidence_ref": "afo-decision:" + decision_id,
            },
            rec["revision"],
        )
