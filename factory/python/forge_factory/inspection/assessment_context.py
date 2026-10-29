"""Versioned view of existing owner scope for inspectors; never an alternate verdict authority."""
from __future__ import annotations

from pathlib import Path

from ..afo.durable import digest
from ..common import sha256_file
from ..release import aspice

FIELD = "inspection_assessment_context"
FIELDS = ("purpose", "aspice_development", "target", "scope", "budgets", "layer", "operation_scope")


def binding(manifest):
    if manifest.get("purpose") != aspice.PURPOSE or aspice.selected(manifest) is None:
        raise ValueError("INSPECTION_ASSESSMENT_SCOPE_INVALID")
    return {"schema": "forge-c/inspection-assessment-context/1",
            "scope_sha256": digest({k: manifest.get(k) for k in FIELDS}),
            "renderer_sha256": sha256_file(Path(__file__))}


def view(manifest):
    # Old work orders and their historical inspection identities are unchanged.
    if FIELD not in manifest:
        return None
    if manifest[FIELD] != binding(manifest):
        raise ValueError("INSPECTION_ASSESSMENT_CONTEXT_CHANGED")
    record = manifest["aspice_development"]
    return {"schema": "forge-c/inspection-assessment-view/1", "purpose": aspice.PURPOSE,
            "binding": manifest[FIELD], "owner_policy_ref": record["policy_ref"],
            "owner_request": record["owner_decision"]["request"],
            "safety_assurance": "NOT_ASSESSED", "safety_release_approval": None,
            "assessed_aspice_compliance": None,
            "outside_owner_scope": ["safety allocation", "safety assurance", "allocated safety safe state"],
            "required_engineering_evidence": [
                "concrete startup/reset behavior", "supported invocation domain and caller responsibilities",
                "failure/error behavior required within that supported domain",
                "explicit measurable flash/RAM/stack/CPU/timing constraints",
                "functional source coverage, traceability and verification"],
            "missing_required_constraint": "OPEN_INPUT_GAP_NOT_SATISFIED",
            "unsupported_invocation_behavior": "NOT_INFERRED_FROM_EXCLUDED_DOMAIN",
            "declared_work_order_scope": manifest["scope"],
            "constraints_ref": ".forge-run/manifest.json#budgets",
            "effect_on_verdict": "NONE; inspector judges the original full criterion against this bound owner scope"}


def checklist(manifest, resolved):
    context = view(manifest)
    if context is None:
        return resolved
    return {**resolved, "assessment_context": context,
            "sha256": digest({"frozen_checklist_sha256": resolved["sha256"],
                              "assessment_context_sha256": digest(context)})}
