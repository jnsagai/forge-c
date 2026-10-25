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


DECISIONS = ("PROPOSE_REPAIR", "NEEDS_EVIDENCE", "CLOSE_BLOCKED")


def wire_schema() -> dict:
    """Grammar-friendly generation constraint derived from the unchanged authoritative contract.

    Omniverse2 2026-10-25: through the local provider the authoritative schema (top-level oneOf
    with branch-level required/not) constrained nothing useful; Qwen returned only
    {"decision": ...}. This is an anyOf of closed objects, one per decision, without not/oneOf.
    It is only a decoding aid: every answer is still parsed against the authoritative schema.
    """
    from .durable import schema

    contract = schema("semantic-proposal")
    branches = []
    for branch in contract["oneOf"]:
        decision = branch["properties"]["decision"]["const"]
        forbidden = {name for rule in branch.get("not", {}).get("anyOf", []) for name in rule["required"]}
        properties = {k: v for k, v in contract["properties"].items() if k not in forbidden}
        properties["decision"] = {"const": decision}
        branches.append(
            {"type": "object", "properties": properties, "required": branch["required"], "additionalProperties": False}
        )
    return {"anyOf": branches}


def diagnose(raw: str | bytes | dict) -> dict:
    """Value-free shape facts of a rejected proposal: no field values, prose, raw output or reasoning."""
    import re

    from jsonschema import Draft202012Validator

    from .durable import schema

    def name(part):
        return str(part) if re.fullmatch(r"[A-Za-z0-9_]{1,40}", str(part)) else "<other>"

    def issue(e, branch=None):
        rec = {"path": "/".join(name(p) for p in e.absolute_path)[:120], "validator": str(e.validator)[:40]}
        return {**rec, "branch": branch} if branch else rec

    data = raw if isinstance(raw, bytes) else raw.encode() if isinstance(raw, str) else canonical(raw)
    out = {"bytes": len(data)}
    try:
        value = strict_json(data, 65536)
    except Refused as exc:
        return {**out, "parse": exc.code}
    contract = schema("semantic-proposal")
    known = set(contract.get("properties", {}))
    out.update(parse="OK", type=type(value).__name__)
    if isinstance(value, dict):
        out["keys"] = sorted(k for k in value if k in known)
        out["unknown_key_count"] = sum(k not in known for k in value)
        declared = value.get("decision")
        out["decision"] = declared if declared in DECISIONS else ("INVALID" if "decision" in value else None)
    issues = []
    for e in list(Draft202012Validator(contract).iter_errors(value))[:4]:
        issues.append(issue(e))
        if e.validator == "oneOf":
            # Report only the branch the proposal declared (or every branch when it declared none), four issues each.
            per_branch = {}
            for index, sub in enumerate(e.context or []):
                branch = DECISIONS[sub.relative_schema_path[0]] if sub.relative_schema_path else str(index)
                if out.get("decision") in (None, "INVALID", branch) and per_branch.get(branch, 0) < 4:
                    per_branch[branch] = per_branch.get(branch, 0) + 1
                    issues.append(issue(sub, branch))
    out["issues"] = issues[:20]
    return out


TWO_STEP = "two-step-diagnosis"


def two_step(job) -> bool:
    """Only a signed qualification identity (or measured role capability) selects the two-question mode."""
    identity = job.get("qualification_identity") or ((job.get("role_capabilities") or {}).get(job.get("role")) or {}).get(
        "identity"
    )
    return bool(identity) and identity.get("task_class") == TWO_STEP


def _evidence_items(aliases):
    return {"type": "array", "items": {"enum": sorted(aliases)}, "minItems": 1, "maxItems": 16, "uniqueItems": True}


def conflict_schema(aliases, *, complete=True) -> dict:
    """Question 1: is there a requirement conflict? Rationale precedes the verdict in generation order.

    The contract admits only NEEDS_EVIDENCE for an incomplete packet, so then only UNKNOWN is offered and the
    question measures the missing-evidence answer (disclosed with the qualification results).
    """
    from .durable import schema

    contract = schema("semantic-proposal")["properties"]
    base = {"rationale": {"type": "string", "minLength": 1, "maxLength": 500}, "evidence_refs": _evidence_items(aliases)}
    branches = []
    for verdict in ("YES", "NO", "UNKNOWN") if complete else ("UNKNOWN",):
        properties = {**base, "conflict": {"const": verdict}}
        required = ["rationale", "evidence_refs", "conflict"]
        if verdict == "UNKNOWN":
            properties["missing_evidence"] = contract["missing_evidence"]
            required.append("missing_evidence")
        branches.append({"type": "object", "properties": properties, "required": required, "additionalProperties": False})
    return {"anyOf": branches}


def technique_choice_schema(packet) -> dict:
    """Question 2: one flat enum choice (reason first). No anyOf: a large repair branch inside anyOf was never
    produced by the local decoder in any batch, even when its own text named the fitting technique."""
    return {
        "type": "object",
        "properties": {
            "reason": {"type": "string", "minLength": 1, "maxLength": 300},
            "technique_id": {"enum": [*sorted(packet.get("techniques") or {}), "NONE"]},
        },
        "required": ["reason", "technique_id"],
        "additionalProperties": False,
    }


def repair_schema(obligations, tests=None, *, phase=None, paths=None) -> dict:
    """Question 3 (after a catalogued technique was chosen): flat repair fields, bounds inside the contract's.

    Test references are enums of the case's declared independent tests. owner_phase is always asked and kept
    by assembly only with RETURN_TO_OWNING_UPSTREAM_PHASE (the contract forbids it otherwise); a model switch
    is not offered here because no authorized alternative catalogue is part of this question.
    The case phase fixes affected_phase, an upstream owner can only be that phase or an earlier one, and the
    scope is limited to the case's artifact paths; the broker still checks owner/scope consistency.
    """
    from .durable import schema

    contract = schema("semantic-proposal")["properties"]
    text = {"type": "string", "minLength": 1, "maxLength": 300}
    phases = contract["affected_phase"]["enum"]
    return {
        "type": "object",
        "properties": {
            "strategy": {"enum": [s for s in contract["strategy"]["enum"] if s != "SWITCH_PREAPPROVED_MODEL_PROFILE"]},
            "affected_phase": {"enum": [phase]} if phase else contract["affected_phase"],
            "owner_phase": {"enum": phases[: phases.index(phase) + 1]} if phase else contract["owner_phase"],
            "target_obligations": {"type": "array", "items": {"enum": sorted(obligations)}, "minItems": 1, "maxItems": 4},
            "artifact_scope": {
                "type": "array",
                "items": {"enum": sorted(set(paths))} if paths else {"type": "string", "minLength": 1, "maxLength": 200},
                "minItems": 1,
                "maxItems": 4,
            },
            "proposed_change": text,
            "material_difference": text,
            "validation_expectations": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "test_ref": {"enum": sorted(tests)} if tests else {"type": "string", "minLength": 2, "maxLength": 120},
                        "expected_result": {"enum": sorted({t["expected_result"] for t in tests.values()})}
                        if tests
                        else {"type": "string", "minLength": 1, "maxLength": 120},
                    },
                    "required": ["test_ref", "expected_result"],
                    "additionalProperties": False,
                },
                "minItems": 1,
                "maxItems": 4,
            },
        },
        "required": [
            "strategy", "affected_phase", "owner_phase", "target_obligations", "artifact_scope", "proposed_change",
            "material_difference", "validation_expectations",
        ],
        "additionalProperties": False,
    }


def assemble(first: dict, choice: dict | None = None, repair: dict | None = None) -> dict:
    """Deterministic semantic proposal from the answers; the broker still validates it against the contract."""
    refs = first["evidence_refs"]
    if first["conflict"] == "UNKNOWN":
        return {"decision": "NEEDS_EVIDENCE", "evidence_refs": refs, "missing_evidence": first["missing_evidence"]}
    if first["conflict"] == "NO":
        return {
            "decision": "CLOSE_BLOCKED",
            "evidence_refs": refs,
            "blocking_reason": "UNSUPPORTED_HYPOTHESIS",
            "explanation": first["rationale"],
        }
    if choice is None or choice["technique_id"] == "NONE" or repair is None:
        return {
            "decision": "CLOSE_BLOCKED",
            "evidence_refs": refs,
            "blocking_reason": "NO_ALLOWED_MATERIAL_STRATEGY",
            "explanation": (choice or {}).get("reason") or first["rationale"],
        }
    fields = dict(repair)
    if fields.get("strategy") != "RETURN_TO_OWNING_UPSTREAM_PHASE":
        fields.pop("owner_phase", None)  # the contract allows owner_phase only with that strategy
    return {
        "decision": "PROPOSE_REPAIR",
        "evidence_refs": refs,
        "causal_hypothesis": first["rationale"],
        "technique_id": choice["technique_id"],
        **fields,
    }


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
