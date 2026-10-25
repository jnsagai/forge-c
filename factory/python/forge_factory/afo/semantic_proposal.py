"""DA-005/006/019/034/036: strict small judgments, deterministic administration.

Model decisions never carry identity, budgets, authority, receipt flags or verdicts.
The unchanged Feature 005 validator remains an additional independent barrier.
"""

from __future__ import annotations

from pathlib import Path

from ..inspection.engine import PHASE_PATHS
from . import contracts, recovery
from .diagnosis_packet import PHASES, evidence, scoped_path
from .durable import Refused, canonical, digest, strict_json, validate


def parse(raw: str | bytes | dict) -> dict:
    proposal = strict_json(raw) if isinstance(raw, (str, bytes)) else strict_json(canonical(raw))
    validate("semantic-proposal", proposal)
    text = " ".join(
        str(proposal.get(k, "")) for k in ("causal_hypothesis", "material_difference", "proposed_change", "explanation")
    )
    if recovery.DENY.search(text):
        raise Refused("PROPOSAL_WEAKENS_GATE_OR_POLICY")
    return proposal


def signature(proposal: dict) -> str:
    """Catalogued approach, target, scope and checks; wording/seeds/administrative IDs cannot buy another try."""
    return digest(
        {k: proposal.get(k) for k in ("decision", "strategy", "affected_phase", "owner_phase", "model_profile", "technique_id")}
        | {
            "targets": sorted(proposal.get("target_obligations", [])),
            "scope": sorted(proposal.get("artifact_scope", [])),
            "checks": sorted(v["test_ref"] for v in proposal.get("validation_expectations", [])),
        }
    )


def check(proposal: dict, packet: dict, *, authorized_profiles=()) -> None:
    refs = {a["ref"] for a in packet["artifacts"]} | {f["ref"] for f in packet["findings"]}
    if not set(proposal["evidence_refs"]) <= refs:
        raise Refused("PROPOSAL_EVIDENCE_NOT_IN_CASE")
    for ref in proposal["evidence_refs"]:
        evidence(packet, ref, role=packet["role"], phase=packet["binding"]["phase"])
    # Every required primary source is rechecked; a selected good reference cannot hide a stale decisive artifact.
    for art in packet["artifacts"]:
        evidence(packet, art["ref"], role=packet["role"], phase=packet["binding"]["phase"])
    if proposal["decision"] == "NEEDS_EVIDENCE":
        if any(x["obligation_ref"] not in packet["obligations"] for x in proposal["missing_evidence"]):
            raise Refused("UNKNOWN_EVIDENCE_OBLIGATION")
        return
    if proposal["decision"] == "CLOSE_BLOCKED":
        if proposal["blocking_reason"] == "NO_ALLOWED_MATERIAL_STRATEGY" and not packet["complete"]:
            raise Refused("INCOMPLETE_CASE_IS_NOT_NO_STRATEGY")
        return
    if not packet["complete"]:
        raise Refused("MISSING_EVIDENCE")
    if not set(proposal["target_obligations"]) <= set(packet["obligations"]):
        raise Refused("UNKNOWN_TARGET_OBLIGATION")
    if proposal["technique_id"] not in packet["techniques"]:
        raise Refused("UNKNOWN_REPAIR_TECHNIQUE")
    owner = proposal.get("owner_phase") or proposal["affected_phase"]
    if proposal["strategy"] == "RETURN_TO_OWNING_UPSTREAM_PHASE":
        if PHASES.index(owner) > PHASES.index(packet["binding"]["phase"]):
            raise Refused("UPSTREAM_OWNER_INVALID")
    elif proposal["affected_phase"] != packet["binding"]["phase"]:
        raise Refused("REPAIR_PHASE_MISMATCH")
    if proposal.get("model_profile") and proposal["model_profile"] not in authorized_profiles:
        raise Refused("LOCAL_ALTERNATIVE_NOT_QUALIFIED_AND_AUTHORIZED")
    for rel in proposal["artifact_scope"]:
        scoped_path(Path(packet["workspace"]), rel)
        if recovery.PROTECTED.search(rel) or not any(
            rel == p or rel.startswith(p.rstrip("/") + "/") for p in PHASE_PATHS.get(owner, [])
        ):
            raise Refused("REPAIR_SCOPE_DENIED", rel)
    for expectation in proposal["validation_expectations"]:
        test = packet["tests"].get(expectation["test_ref"])
        if not test or expectation["expected_result"] != test["expected_result"]:
            raise Refused("INDEPENDENT_TEST_EXPECTATION_UNRESOLVED")
    if signature(proposal) in packet["prior_strategies"]:
        raise Refused("SEMANTIC_STRATEGY_ALREADY_TRIED")


def bind(proposal: dict, packet: dict, *, budget: dict, policy_ref: str, authorized_profiles=()) -> dict | None:
    proposal = parse(proposal)
    check(proposal, packet, authorized_profiles=authorized_profiles)
    if proposal["decision"] == "NEEDS_EVIDENCE":
        return None
    b, sig = packet["binding"], signature(proposal)
    closed = proposal["decision"] == "CLOSE_BLOCKED"
    plan = {
        "schema_version": "1.0",
        "plan_id": "afo-plan-" + digest([b, sig])[:24],
        "order_id": b["order_id"],
        "attempt_id": b["attempt_id"],
        "failure_fingerprint": b["fingerprint"],
        "strategy": "CLOSE_BLOCKED" if closed else proposal["strategy"],
        "affected_phase": b["phase"] if closed else proposal["affected_phase"],
        "material_difference_ref": "semantic-strategy:" + sig,
        "artifact_scope": [] if closed else proposal["artifact_scope"],
        "validation_tests": [] if closed else [x["test_ref"] for x in proposal["validation_expectations"]],
        "budget_estimate": {k: int(budget[k]) for k in ("tokens_max", "wall_seconds_max", "turns_max")},
        "rationale_code": proposal["blocking_reason"] if closed else "EVIDENCE_BOUND_SEMANTIC_REPAIR",
        "policy_decision_id": policy_ref,
        "notes": "semantic-proposal:" + digest(proposal),
    }
    if proposal.get("model_profile"):
        plan["model_profile"] = proposal["model_profile"]
    if proposal.get("owner_phase"):
        plan["owner_phase"] = proposal["owner_phase"]
        plan["upstream_invalidation"] = list(PHASES[PHASES.index(proposal["owner_phase"]) + 1 :])
    contracts.require("recovery-plan", plan)
    return plan


def capability_route(
    *,
    complete: bool,
    fits: bool,
    qualified: bool,
    can_partition: bool,
    alternatives: list[dict],
    allowed_profiles: list[str],
    remaining: bool,
) -> dict:
    if not remaining:
        return {"outcome": "EXHAUSTED", "action": "BLOCK"}
    if not complete:
        return {"outcome": "MISSING_EVIDENCE", "action": "WAIT_FOR_EVIDENCE"}
    if not fits and can_partition:
        return {"outcome": "REPARTITION", "action": "PARTITION_WITH_COVERAGE"}
    if qualified and fits:
        return {"outcome": "ELIGIBLE", "action": "ADMIT"}
    for alt in alternatives:
        if alt.get("qualified") and alt.get("profile") in allowed_profiles and alt.get("local_only") is True:
            return {"outcome": "QUALIFIED_ALTERNATIVE", "action": "USE_LOCAL_PROFILE", "profile": alt["profile"]}
    return {"outcome": "CAPABILITY_LIMIT", "action": "BLOCK", "cause": "UNQUALIFIED_OR_OBSERVED_BOUND"}


def rank_candidates(candidates: list[dict], *, budget: int, stall_limit: int = 2) -> dict:
    """Independent closure/regression feedback only; confidence and votes are intentionally unused."""
    if budget < 0 or stall_limit < 1:
        raise Refused("SEARCH_LIMIT_INVALID")
    seen, accepted, stalled = set(), [], 0
    best = -1
    for candidate in candidates[:budget]:
        sig = signature(parse(candidate["proposal"]))
        if sig in seen:
            return {"outcome": "STALLED", "reason": "REPEATED_STRATEGY", "evaluated": len(seen)}
        seen.add(sig)
        verification = candidate.get("verification") or {}
        if not verification.get("independent") or not verification.get("receipt_ref"):
            raise Refused("INDEPENDENT_VERIFIER_FEEDBACK_REQUIRED")
        closure = len(set(verification.get("closed_obligations", [])))
        if verification.get("regressions") or verification.get("unsupported_properties"):
            closure = -1
        stalled = stalled + 1 if closure <= best else 0
        best = max(best, closure)
        if verification.get("all_required_pass") and closure > 0:
            accepted.append((closure, sig, candidate))
        if stalled >= stall_limit:
            break
    if accepted:
        _, sig, value = max(accepted, key=lambda x: (x[0], x[1]))
        return {"outcome": "VERIFIED_CANDIDATE", "signature": sig, "candidate": value, "evaluated": len(seen)}
    return {"outcome": "STALLED" if stalled >= stall_limit else "EXHAUSTED", "evaluated": len(seen)}
