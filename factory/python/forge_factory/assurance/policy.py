"""EASA-T011/T013 and AT-067 — assurance policy: profile (STANDARD/ENHANCED/HIGH_ASSURANCE) independent of the
product ASIL, schema-validated, hash-pinned to an approved version, safely reloadable, and mode transitions
OBSERVE_ONLY -> PILOT -> ENFORCING only with human authorization (and, for ENFORCING, a validated pilot).

Profiles are cumulative: a higher profile must contain every requirement of the lower ones (no shortcut).
"""
from __future__ import annotations

import copy
from pathlib import Path

from ..common import REPO_ROOT, canonical_json, sha256_bytes, utc_now
from ..events.emit import emit
from . import contracts

PROFILES = ("STANDARD", "ENHANCED", "HIGH_ASSURANCE")
MODES = ("OBSERVE_ONLY", "PILOT", "ENFORCING")
POLICY_PATH = REPO_ROOT / "config/factory/assurance-policy.yaml"
AGENT_PREFIXES = ("agent", "ai", "llm", "swe", "fabro", "repair", "claude", "deepseek", "qwen")

# Evidence requirements per phase. STANDARD = what the existing 002-004 gates already demand.
_STANDARD = {
    "SWE.1": ["SOURCE_LINKED_REQUIREMENTS", "INDEPENDENT_INSPECTION", "TRACE_REQ_TO_TEST"],
    "SWE.2": ["COMPONENT_ALLOCATION", "INTERFACE_DEFINITION", "INDEPENDENT_INSPECTION"],
    "SWE.3": ["COMPILE_WARNINGS_CLEAN", "STATIC_ANALYSIS", "REGISTER_MAP_CONFORMANCE", "INDEPENDENT_INSPECTION"],
    "SWE.4": ["REQUIREMENTS_DERIVED_TESTS", "STATEMENT_COVERAGE", "BRANCH_COVERAGE", "INDEPENDENT_INSPECTION"],
    "SWE.5": ["REQUIREMENTS_DERIVED_INTEGRATION_TESTS", "RESOURCE_USAGE", "FIDELITY_LABEL"],
    "SWE.6": ["REQUIREMENTS_OBSERVED_TESTS", "FIDELITY_LABEL"],
}
_ENHANCED_ADD = {
    "SWE.1": ["SOURCE_CONTRADICTION_CHECK", "TESTABILITY_CHECK", "TWO_WAY_TRACE"],
    "SWE.2": ["IRQ_RESOURCE_OWNERSHIP", "PLANTUML_SEMANTIC_CONSISTENCY", "FLOW_SCHEDULING_ANALYSIS"],
    "SWE.3": ["REGISTER_ACCESS_SEMANTICS", "MISRA_RULE_COVERAGE_MATRIX", "CONCURRENCY_ANALYSIS", "RESOURCE_BUDGETS"],
    "SWE.4": ["INDEPENDENT_ORACLE", "MUTATION_EVIDENCE", "NEGATIVE_BOUNDARY_CASES", "API_EXECUTION_PROOF"],
    "SWE.5": ["FAULT_INJECTION", "BOUNDARY_INTEGRATION", "RAW_OUTCOME_VALIDATION"],
    "SWE.6": ["DEGRADED_TRANSITION_SCENARIOS", "MEASURED_REQUIREMENT_OBSERVATION"],
}
_HIGH_ADD = {
    "SWE.1": ["FORMALIZED_CONSTRAINTS"], "SWE.2": ["ADVERSARIAL_INTERFACE_REVIEW"],
    "SWE.3": ["BOUNDED_PROOF_WHERE_FEASIBLE"], "SWE.4": ["SELECTED_MCDC", "EXTENDED_MUTATION"],
    "SWE.5": ["DIVERSE_TARGET_CAMPAIGN"], "SWE.6": ["INDEPENDENT_SCENARIO_ORACLE"],
}


def profile_requirements(profile: str) -> dict[str, list[str]]:
    if profile not in PROFILES:
        raise ValueError(f"unknown profile {profile}")
    out = copy.deepcopy(_STANDARD)
    for add in ([_ENHANCED_ADD] if profile == "ENHANCED" else [_ENHANCED_ADD, _HIGH_ADD] if profile == "HIGH_ASSURANCE"
                else []):
        for ph, reqs in add.items():
            out[ph] += reqs
    return out


def policy_sha(pol: dict) -> str:
    return sha256_bytes(canonical_json({k: v for k, v in pol.items() if k != "last_verified_policy_sha"}))


def validate(pol: dict) -> list[str]:
    issues = contracts.errors("assurance-policy", pol)
    if issues:
        return issues
    base = profile_requirements(pol["profile"])
    for ph in (pol.get("requirements") or {}):
        if ph not in base:
            issues.append(f"UNKNOWN_PHASE:{ph}")
    if pol["mode"] != "OBSERVE_ONLY" and not _authorized(pol.get("authorization")):
        issues.append("MODE_WITHOUT_HUMAN_AUTHORIZATION")
    return issues


def effective(pol: dict, scope: dict) -> dict:
    """AT-010: the profile changes evidence requirements only; the target ASIL is copied from the safety scope."""
    reqs = profile_requirements(pol["profile"])
    for ph, extra in (pol.get("requirements") or {}).items():
        reqs[ph] = list(dict.fromkeys(reqs.get(ph, []) + list(extra)))
    return {"target_asil": scope["target_asil"], "product_asil_source": scope["product_asil_source"],
            "profile": pol["profile"], "requirements": reqs, "policy_sha": policy_sha(pol)}


def _human(who: str | None) -> bool:
    return bool(who) and not str(who).lower().startswith(AGENT_PREFIXES)


def _authorized(auth: dict | None) -> bool:
    return bool(auth) and _human(auth.get("approved_by")) and bool(auth.get("approved_at")) and bool(auth.get("reference"))


def approve(store, pol: dict, approver: str) -> str:
    if not _human(approver):
        raise PermissionError("policy approval requires a human owner, not an agent")
    if validate(pol):
        raise ValueError("cannot approve an invalid policy")
    return store.append("policy", "approved", {"policy_sha": policy_sha(pol), "approved_by": approver,
                                               "approved_at": utc_now()}, actor=approver)


def approved_shas(store) -> set[str]:
    return {r["record"]["policy_sha"] for r in store.history("policy", "approved")}


class PolicyHolder:
    """Holds the active policy. reload() only switches to a schema-valid policy whose sha was approved by a human;
    otherwise the previous policy stays active and an audit event is emitted (fail closed, no partial reload)."""

    def __init__(self, store, path: Path = POLICY_PATH):
        self.store, self.path = store, path
        self.active = contracts.load(contracts.POLICY_EXAMPLE)  # built-in OBSERVE_ONLY default
        self.source = "builtin-default"
        self.reload()

    def reload(self) -> tuple[bool, list[str]]:
        if not self.path.is_file():
            return False, ["POLICY_FILE_ABSENT"]
        try:
            cand = contracts.load(self.path)
        except Exception as exc:  # noqa: BLE001 - malformed YAML must not crash the gate
            issues = [f"POLICY_UNREADABLE:{type(exc).__name__}"]
        else:
            issues = validate(cand) if isinstance(cand, dict) else ["POLICY_NOT_A_MAPPING"]
            if not issues and policy_sha(cand) not in approved_shas(self.store):
                issues.append("POLICY_NOT_APPROVED")
        if issues:
            emit("audit", "WARN", f"assurance policy reload refused: {issues[0]}", tool_id="easa-policy")
            return False, issues
        self.active, self.source = cand, str(self.path)
        return True, []


def mode_preconditions(cur: str, target: str, authorization: dict | None, pilot_rec: dict | None) -> list[str]:
    """Pure check (no record written): what blocks the switch cur -> target. Used by request_mode and, read-only, by
    the EASA-T070 readiness decision."""
    issues = []
    if target not in MODES:
        issues.append(f"UNKNOWN_MODE:{target}")
    elif MODES.index(target) > MODES.index(cur):
        if not _authorized(authorization):
            issues.append("HUMAN_AUTHORIZATION_MISSING")
        if target == "ENFORCING":
            r = (pilot_rec or {}).get("record", {})
            if not pilot_rec or pilot_rec["kind"] != "mode" or r.get("pilot_status") != "PASS":
                issues.append("VALIDATED_PILOT_MISSING")
            elif r.get("false_positive_rate") is None or r.get("false_negative_rate") is None:
                issues.append("PILOT_ERROR_RATES_NOT_MEASURED")
            elif not _human(r.get("independent_review_by")):
                issues.append("PILOT_INDEPENDENT_REVIEW_MISSING")
            if cur != "PILOT":
                issues.append("ENFORCING_REQUIRES_PILOT_FIRST")
    return issues


def request_mode(store, pol: dict, target: str, authorization: dict | None = None,
                 pilot_record_id: str | None = None) -> dict:
    """AT-067: OBSERVE_ONLY -> PILOT needs human authorization; -> ENFORCING also needs a PASS pilot record with a
    measured false-positive/negative analysis and an independent review. Downgrades are always allowed."""
    cur = pol["mode"]
    pilot = store.get(pilot_record_id) if pilot_record_id and target == "ENFORCING" else None
    issues = mode_preconditions(cur, target, authorization, pilot)
    decision = {"from": cur, "to": target, "decision": "REJECTED" if issues else "ACCEPTED", "issues": issues,
                "policy_sha": policy_sha(pol), "authorization": authorization, "pilot_record": pilot_record_id}
    store.append("mode", "transition", decision, actor=(authorization or {}).get("approved_by") or "unauthorized")
    if issues:
        emit("audit", "WARN", f"assurance mode switch {cur}->{target} rejected: {issues[0]}", tool_id="easa-policy")
    return {**decision, "mode": cur if issues else target}
