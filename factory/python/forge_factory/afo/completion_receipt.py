"""DA-008/009: transactional proposal receipts, independent decisions and completion.

SQLite is authoritative; filesystem projections are recoverable. Native prose and
native SUCCEEDED are not submission, admissibility or verification authorities.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from ..common import sha256_file, utc_now
from . import recovery, semantic_proposal
from .diagnosis_packet import load as load_packet
from .durable import Refused, canonical, digest, immutable_json, validate
from .mission_ledger import MissionLedger


@dataclass(frozen=True)
class Context:
    mission_id: str
    order_id: str
    attempt_id: str
    job_id: str
    case_sha256: str
    launch_nonce: str

    @classmethod
    def from_job(cls, store, job_id: str):
        with store.tx() as c:
            row = c.execute("SELECT record FROM afo_local_agent_jobs WHERE job_id=?", (job_id,)).fetchone()
        if not row:
            raise Refused("PROPOSAL_JOB_UNBOUND")
        j = json.loads(row[0])
        path = Path(j["case"])
        if not path.is_file() or sha256_file(path) != j["case_sha256"]:
            raise Refused("FROZEN_CASE_CHANGED")
        mission = MissionLedger(store).for_order(j["order_id"])
        if mission != j.get("mission_id"):
            raise Refused("JOB_MISSION_MISMATCH")
        return cls(mission, j["order_id"], j["attempt_id"], job_id, j["case_sha256"], j["nonce"])


class Receipts:
    def __init__(self, store):
        self.store = store

    def latest(self, receipt_id: str) -> dict | None:
        with self.store.tx() as c:
            row = c.execute(
                "SELECT record,sha256 FROM afo_completion_receipts WHERE receipt_id=? ORDER BY revision DESC LIMIT 1",
                (receipt_id,),
            ).fetchone()
        if not row:
            return None
        value = json.loads(row["record"])
        if digest(value) != row["sha256"]:
            raise Refused("RECEIPT_INTEGRITY_FAILED")
        return value

    def for_job(self, ctx: Context) -> list[dict]:
        with self.store.tx() as c:
            values = [json.loads(r[0]) for r in c.execute("SELECT record FROM afo_completion_receipts WHERE revision=1")]
        return [
            self.latest(r["receipt_id"])
            for r in values
            if r["job_id"] == ctx.job_id
            and r["launch_nonce"] == ctx.launch_nonce
            and r["case_sha256"] == ctx.case_sha256
            and r["mission_id"] == ctx.mission_id
        ]

    @staticmethod
    def _insert(c, rec: dict) -> None:
        validate("completion-receipt", rec)
        c.execute(
            "INSERT INTO afo_completion_receipts VALUES (?,?,?,?)",
            (rec["receipt_id"], rec["revision"], canonical(rec).decode(), digest(rec)),
        )

    def submit(self, ctx: Context, raw: str | bytes | dict, *, max_corrections: int = 1) -> dict:
        # Re-resolve authenticated context; callers cannot invent a nonce/case binding.
        if Context.from_job(self.store, ctx.job_id) != ctx:
            raise Refused("SUBMISSION_CONTEXT_MISMATCH")
        original = raw if isinstance(raw, bytes) else raw.encode() if isinstance(raw, str) else canonical(raw)
        error, proposal = None, None
        try:
            proposal = semantic_proposal.parse(raw)
            phash, basis = digest(proposal), "CANONICAL_JSON"
        except Refused as exc:
            phash, basis, error = hashlib.sha256(original).hexdigest(), "RAW_BYTES", exc.code
        rid = "receipt-" + digest([ctx.job_id, ctx.launch_nonce, phash])[:24]
        with self.store.tx() as c:
            old = c.execute(
                "SELECT record FROM afo_completion_receipts WHERE receipt_id=? ORDER BY revision DESC LIMIT 1", (rid,)
            ).fetchone()
            if old:
                return json.loads(old[0])
            n = c.execute(
                "SELECT COUNT(*) FROM afo_semantic_proposals WHERE job_id=? AND nonce=?", (ctx.job_id, ctx.launch_nonce)
            ).fetchone()[0]
            snap = MissionLedger._snapshot(c, ctx.mission_id)
            if n and snap["corrections"] >= snap["limits"]["max_corrections"]:
                raise Refused("MISSION_CORRECTIONS_EXHAUSTED")
            if n > max_corrections:
                raise Refused("PROPOSAL_CORRECTIONS_EXHAUSTED")
            if n:
                c.execute(
                    "INSERT INTO afo_mission_counters VALUES (?,?,?,?)",
                    ("correction:" + rid, ctx.mission_id, ctx.job_id, "CORRECTION"),
                )
            rec = {
                "schema_version": "1.0",
                "receipt_id": rid,
                "revision": 1,
                "previous_receipt_sha256": None,
                "created_at": utc_now(),
                **ctx.__dict__,
                "proposal_sha256": phash,
                "proposal_hash_basis": basis,
                "proposal_ref": "semantic-proposal:" + phash if proposal is not None else None,
                "decision": proposal["decision"] if proposal is not None else None,
                "submission_state": "STORED" if proposal is not None else "REJECTED",
                "admissibility_state": "PENDING" if proposal is not None else "NOT_EVALUATED",
                "admissibility_receipt_ref": None,
                "bound_plan": None,
                "execution_state": "NOT_REQUESTED",
                "execution_id": None,
                "verification_receipt_ref": None,
                "reason_codes": [error] if error else [],
            }
            stored = {"proposal": proposal, "reason": error}
            if error:
                stored["diagnostic"] = semantic_proposal.diagnose(original)
            c.execute(
                "INSERT INTO afo_semantic_proposals VALUES (?,?,?,?)",
                (phash, ctx.job_id, ctx.launch_nonce, canonical(stored).decode()),
            )
            self._insert(c, rec)
        return rec

    def _advance(
        self, rid: str, expected: int, changes: dict, *, decision: tuple | None = None, effect: tuple | None = None
    ) -> dict:
        allowed = {
            "admissibility_state",
            "admissibility_receipt_ref",
            "bound_plan",
            "execution_state",
            "execution_id",
            "verification_receipt_ref",
            "reason_codes",
        }
        if not set(changes) <= allowed:
            raise Refused("RECEIPT_IMMUTABLE_IDENTITY")
        if changes.get("execution_state") == "VERIFIED" and (not decision or decision[1] != "VERIFICATION"):
            raise Refused("INDEPENDENT_VERIFICATION_RECEIPT_REQUIRED")
        with self.store.tx() as c:
            row = c.execute(
                "SELECT record,sha256 FROM afo_completion_receipts WHERE receipt_id=? ORDER BY revision DESC LIMIT 1", (rid,)
            ).fetchone()
            if not row or json.loads(row["record"])["revision"] != expected:
                raise Refused("RECEIPT_REVISION_FENCED")
            old = json.loads(row["record"])
            if digest(old) != row["sha256"]:
                raise Refused("RECEIPT_CHAIN_BROKEN")
            rec = {**old, **changes, "revision": expected + 1, "previous_receipt_sha256": row["sha256"], "created_at": utc_now()}
            if decision:
                did, kind, data = decision
                c.execute(
                    "INSERT OR IGNORE INTO afo_independent_decisions VALUES (?,?,?,?)",
                    (did, kind, canonical(data).decode(), digest(data)),
                )
            if effect:
                eid, kind, payload = effect
                old_effect = c.execute("SELECT record FROM afo_durable_effects WHERE effect_id=?", (eid,)).fetchone()
                if old_effect and json.loads(old_effect[0]) != payload:
                    raise Refused("EFFECT_IDENTITY_REBOUND")
                c.execute(
                    "INSERT OR IGNORE INTO afo_durable_effects VALUES (?,?,?,1,?,?)",
                    (eid, kind, rec["job_id"], "PENDING", canonical(payload).decode()),
                )
            self._insert(c, rec)
        return rec

    def proposal(self, rec: dict) -> dict | None:
        with self.store.tx() as c:
            row = c.execute(
                "SELECT record FROM afo_semantic_proposals WHERE job_id=? AND nonce=? AND proposal_sha256=?",
                (rec["job_id"], rec["launch_nonce"], rec["proposal_sha256"]),
            ).fetchone()
        if not row:
            raise Refused("PROPOSAL_RECORD_MISSING")
        proposal = json.loads(row[0])["proposal"]
        if proposal is not None and digest(proposal) != rec["proposal_sha256"]:
            raise Refused("PROPOSAL_RECORD_CHANGED")
        return proposal

    def admit(self, rid: str, *, packet: dict, bundle: dict, eff, authorize, auth_models=()) -> dict:
        rec = self.latest(rid)
        if rec is None:
            raise Refused("RECEIPT_MISSING")
        if rec["submission_state"] != "STORED" or rec["admissibility_state"] != "PENDING":
            return rec
        reason, plan = None, None
        ctx = Context(
            rec["mission_id"], rec["order_id"], rec["attempt_id"], rec["job_id"], rec["case_sha256"], rec["launch_nonce"]
        )
        try:
            if Context.from_job(self.store, rec["job_id"]) != ctx:
                raise Refused("CASE_BINDING_CHANGED")
            with self.store.tx() as c:
                j = json.loads(
                    c.execute("SELECT record FROM afo_local_agent_jobs WHERE job_id=?", (rec["job_id"],)).fetchone()[0]
                )
            case = json.loads(Path(j["case"]).read_text())
            if digest(packet) != case["packet_ref"]["sha256"] or load_packet(case["packet_ref"]) != packet:
                raise Refused("RECEIPT_PACKET_MISMATCH")
            if packet["binding"]["order_id"] != rec["order_id"] or packet["binding"]["attempt_id"] != rec["attempt_id"]:
                raise Refused("RECEIPT_CASE_MISMATCH")
            if not authorize():
                raise Refused("ADMISSION_NOT_AUTHORIZED")
            order = self.store.order(rec["order_id"])
            if not order or order["state"] not in ("RUNNING", "WAITING_RECOVERY"):
                raise Refused("ORDER_NOT_ACTIVE")
            prior = [r for r in self.for_job(ctx) if r["receipt_id"] != rid and r["admissibility_state"] == "ACCEPTED"]
            if prior:
                raise Refused("JOB_ALREADY_HAS_ACCEPTED_PROPOSAL")
            snap = MissionLedger(self.store).snapshot(rec["mission_id"])
            import time

            if time.time() >= snap["limits"]["deadline"] or snap["charged_tokens"] > snap["limits"]["max_tokens"]:
                raise Refused("MISSION_ALLOWANCE_EXHAUSTED")
            proposal = self.proposal(rec)
            if (
                j.get("selected_obligations")
                and proposal["decision"] == "PROPOSE_REPAIR"
                and not set(proposal["target_obligations"]) <= set(j["selected_obligations"])
            ):
                raise Refused("PROPOSAL_OUTSIDE_COHERENT_OBJECTIVE")
            plan = semantic_proposal.bind(
                proposal,
                packet,
                budget=dict(recovery.ATTEMPT_ESTIMATE),
                policy_ref="policy:" + str(eff.sha256),
                authorized_profiles=auth_models,
            )
            if plan is not None:
                issues = recovery.validate(plan, bundle, store=self.store, order=order, eff=eff, auth_models=list(auth_models))
                if issues:
                    raise Refused("PLAN_INADMISSIBLE", issues[0])
        except (Refused, ValueError, KeyError) as exc:
            reason = exc.code if isinstance(exc, Refused) else "INVALID_AUTHORITATIVE_STATE"
        decision = {
            "receipt_id": rid,
            "case_sha256": rec["case_sha256"],
            "policy_sha256": eff.sha256,
            "accepted": reason is None,
            "reason": reason,
            "plan": plan if reason is None else None,
        }
        did = "admissibility-" + digest(decision)[:24]
        bound = (
            {"plan_id": plan["plan_id"], "artifact_ref": "afo-bound-plan:" + did, "sha256": digest(plan)}
            if plan is not None and reason is None
            else None
        )
        return self._advance(
            rid,
            rec["revision"],
            {
                "admissibility_state": "REJECTED" if reason else "ACCEPTED",
                "admissibility_receipt_ref": "afo-decision:" + did,
                "bound_plan": bound,
                "execution_state": "NOT_APPLICABLE" if not reason and rec["decision"] != "PROPOSE_REPAIR" else "NOT_REQUESTED",
                "reason_codes": [reason] if reason else [],
            },
            decision=(did, "ADMISSIBILITY", decision),
        )

    def bound_plan(self, rec: dict) -> dict | None:
        if rec["admissibility_state"] != "ACCEPTED" or not rec["bound_plan"]:
            return None
        did = rec["admissibility_receipt_ref"].removeprefix("afo-decision:")
        with self.store.tx() as c:
            row = c.execute("SELECT kind,record,sha256 FROM afo_independent_decisions WHERE decision_id=?", (did,)).fetchone()
        if not row or row["kind"] != "ADMISSIBILITY":
            raise Refused("ADMISSIBILITY_REFERENCE_UNRESOLVED")
        data = json.loads(row["record"])
        if digest(data) != row["sha256"] or not data["accepted"] or data["receipt_id"] != rec["receipt_id"]:
            raise Refused("ADMISSIBILITY_REFERENCE_INVALID")
        plan = data["plan"]
        if digest(plan) != rec["bound_plan"]["sha256"]:
            raise Refused("BOUND_PLAN_HASH_CHANGED")
        return plan

    def request_dispatch(self, rid: str, *, authorize) -> dict:
        rec = self.latest(rid)
        if rec["execution_state"] != "NOT_REQUESTED":
            return rec
        if rec["admissibility_state"] != "ACCEPTED" or rec["decision"] != "PROPOSE_REPAIR" or not authorize():
            raise Refused("RECEIPT_NOT_DISPATCHABLE")
        # All corrections for one job/nonce share one effective implementation intent.
        eid = "implementation-" + digest([rec["job_id"], rec["launch_nonce"]])[:24]
        payload = {"receipt_id": rid, "plan_sha256": rec["bound_plan"]["sha256"], "case_sha256": rec["case_sha256"]}
        return self._advance(
            rid,
            rec["revision"],
            {"execution_state": "DISPATCH_PENDING", "execution_id": eid},
            effect=(eid, "IMPLEMENTATION", payload),
        )

    def compact(self, rid: str) -> dict:
        rec = self.latest(rid)
        accepted = rec["admissibility_state"] == "ACCEPTED"
        status = "PASS" if accepted and rec["decision"] == "PROPOSE_REPAIR" else "BLOCKED" if accepted else "FAILED"
        return {
            "status": status,
            "artifacts": ["afo-receipt:" + rid] + ([f"afo-plan:{rec['bound_plan']['plan_id']}"] if rec["bound_plan"] else []),
            "issues": rec["reason_codes"],
            "next_action": "next" if status == "PASS" else "halt",
        }

    def project(self, rid: str, destination: Path) -> dict:
        # Distinct receipt revisions get immutable projections; the caller can atomically choose the current pointer.
        value = self.compact(rid)
        immutable_json(destination, value)
        return value

    def verify_chain(self, rid: str) -> bool:
        with self.store.tx() as c:
            rows = c.execute(
                "SELECT record,sha256 FROM afo_completion_receipts WHERE receipt_id=? ORDER BY revision", (rid,)
            ).fetchall()
        previous = None
        for n, row in enumerate(rows, 1):
            value = json.loads(row["record"])
            validate("completion-receipt", value)
            if value["revision"] != n or value["previous_receipt_sha256"] != previous or digest(value) != row["sha256"]:
                raise Refused("RECEIPT_CHAIN_BROKEN")
            previous = row["sha256"]
        return bool(rows)


def for_plan(store, plan_id):
    broker = Receipts(store)
    with store.tx() as c:
        ids = [r[0] for r in c.execute("SELECT DISTINCT receipt_id FROM afo_completion_receipts")]
    matches = [r for rid in ids if (r := broker.latest(rid)).get("bound_plan") and r["bound_plan"]["plan_id"] == plan_id]
    if len(matches) > 1:
        raise Refused("BOUND_PLAN_RECEIPT_AMBIGUOUS")
    return matches[0] if matches else None


def applying(store, receipt_id, attempt_id):
    broker = Receipts(store)
    rec = broker.latest(receipt_id)
    if rec["execution_state"] in ("APPLYING", "VERIFYING", "VERIFIED", "FAILED"):
        return rec
    if rec["execution_state"] != "DISPATCH_PENDING":
        raise Refused("REPAIR_DISPATCH_NOT_REQUESTED")
    with store.tx() as c:
        row = c.execute("SELECT record FROM afo_attempts WHERE attempt_id=?", (attempt_id,)).fetchone()
    attempt = json.loads(row[0]) if row else {}
    if attempt.get("recovery_plan_id") != rec["bound_plan"]["plan_id"]:
        raise Refused("REPAIR_ATTEMPT_NOT_BOUND")
    result = broker._advance(receipt_id, rec["revision"], {"execution_state": "APPLYING"})
    with store.tx() as c:
        effect = c.execute("SELECT record FROM afo_durable_effects WHERE effect_id=?", (rec["execution_id"],)).fetchone()
        payload = {**json.loads(effect[0]), "attempt_id": attempt_id}
        c.execute(
            "UPDATE afo_durable_effects SET state='APPLYING',record=? WHERE effect_id=?",
            (canonical(payload).decode(), rec["execution_id"]),
        )
    return result


def verified_attempt(store, attempt, workspace):
    """Independent release/inspection authorities only; native SUCCEEDED is intentionally unused."""
    plan_id = attempt["record"].get("recovery_plan_id")
    if not plan_id:
        return None
    rec = for_plan(store, plan_id)
    if not rec:
        return None
    broker = Receipts(store)
    if rec["execution_state"] in ("VERIFIED", "FAILED"):
        return rec
    if rec["execution_state"] == "DISPATCH_PENDING":
        rec = applying(store, rec["receipt_id"], attempt["attempt_id"])
    if rec["execution_state"] == "APPLYING":
        rec = broker._advance(rec["receipt_id"], rec["revision"], {"execution_state": "VERIFYING"})
    from ..inspection.engine import Store as InspectionStore
    from .dispatch import package_verdict

    verdict = package_verdict(Path(workspace) / ".forge-run/package.json")
    if verdict["verdict"] == "PENDING":
        return rec
    gates = {f"SWE.{i}": InspectionStore(Path(workspace)).gate(f"SWE.{i}") for i in range(1, 7)}
    passed = verdict["verdict"] == "READY_FOR_OFFLINE_REVIEW" and all(g["decision"] == "PASS" for g in gates.values())
    decision = {
        "receipt_id": rec["receipt_id"],
        "attempt_id": attempt["attempt_id"],
        "plan_sha256": rec["bound_plan"]["sha256"],
        "package": verdict,
        "gates": gates,
        "passed": passed,
        "authority": "EXISTING_RELEASE_AND_INSPECTION_GATES",
    }
    did = "verification-" + digest(decision)[:24]
    result = broker._advance(
        rec["receipt_id"],
        rec["revision"],
        {
            "execution_state": "VERIFIED" if passed else "FAILED",
            "verification_receipt_ref": "afo-decision:" + did if passed else None,
            "reason_codes": [] if passed else ["INDEPENDENT_REPAIR_VERIFICATION_FAILED"],
        },
        decision=(did, "VERIFICATION", decision),
    )
    from .execution_lifecycle import Executions

    if Executions(store).get(rec["job_id"]):
        Executions(store).verified_outcome(rec["job_id"], did)
    return result
