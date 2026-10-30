"""Explain existing diagnosis data namespaces without inferring source authority.

This is provider context, not an evidence oracle, permission, baseline approval or
new store. All fields derive from the already sealed packet and frozen case.
"""
from __future__ import annotations

CONTEXT_RULES = (
    "The obligations map names incident repair work units, not every requirement in the product. "
    "diagnosis_context.required_requirement_ids is the global requirement-coverage inventory. A requirement can be "
    "present in primary_sources without having its own incident repair unit; a missing map key alone "
    "is not proof that its contract is absent. Keep global requirements and dependencies covered. "
    "Use supplied primary text or the established question_1_answer for available facts. "
    "diagnosis_context.known_missing_evidence retains recorded absences. Indexed-source completeness reports "
    "availability, not semantic correctness, baseline approval or source authority. "
    "diagnosis_context.case_scope is a declared data classification, never permission or release approval. For a "
    "declared synthetic fixture, assess the supplied synthetic contract within that fixture; do not "
    "require unrelated target-hardware facts. A genuinely missing decisive contract or unresolved "
    "authority still permits NEEDS_EVIDENCE. Never infer authority from a filename or phase alone. "
)


def context_contract(packet, case, selected):
    """Retain the full global inventory even when the current incident scope is one unit."""
    units = packet["obligations"]
    required = packet["required_obligations"]
    fixture = case.get("qualification_fixture")
    synthetic = (isinstance(fixture, dict)
                 and fixture.get("source_kind") == "SEEDED_PROTOCOL_NOT_PRODUCT"
                 and fixture.get("evaluation_holdout") is True)
    return {
        "schema": "forge-c/diagnosis-context-contract/1",
        "incident_unit_ids": sorted(units),
        "selected_incident_unit_ids": list(selected),
        "required_requirement_ids": list(required),
        "requirements_without_own_incident_unit": sorted(set(required) - set(units)),
        "global_unit_dependencies": {key: list(value["dependencies"]) for key, value in sorted(units.items())},
        "indexed_sources_complete": packet["complete"],
        "known_missing_evidence": list(packet["missing"]),
        "case_scope": {
            "kind": "DECLARED_SYNTHETIC_CONTRACT_FIXTURE" if synthetic else "WORK_ORDER_EVIDENCE",
            "authority": "NO_BASELINE_OR_RELEASE_AUTHORITY_INFERRED",
        },
        "coverage_status": "INVENTORY_ONLY_NOT_PROOF_OF_REQUIREMENT_SATISFACTION",
    }

