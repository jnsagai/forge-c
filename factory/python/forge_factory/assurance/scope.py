"""EASA-T005/T012/T059 — product safety scope, separate from the assurance profile (ADR-0010).

The target ASIL comes ONLY from an approved external allocation reference. ASIL A-D work orders need HSI, the
allocation review, a software safety analysis and a tool confidence/assurance assessment; any missing item BLOCKS
assurance READY. A QM work order may mark those items NOT_APPLICABLE only with a written rationale and a human
approver reference; silent omission blocks. Generated text that claims an ASIL/ISO status the scope does not have is
rejected (AT-079).
"""
from __future__ import annotations

import re

from . import contracts
from .normative import compliance_assertions
from .policy import _human

SAFETY_DOCS = ("software_safety_analysis", "tool_assurance_assessment")
FORBIDDEN_ASIL_SOURCES = ("assurance-profile", "profile", "agent", "llm", "generated", "inferred")


def validate(scope: dict) -> list[str]:
    issues = contracts.errors("safety-scope", scope)
    src = str(scope.get("product_asil_source", "")).lower()
    if any(src.startswith(x) for x in FORBIDDEN_ASIL_SOURCES) or not src:
        issues.append("ASIL_SOURCE_NOT_APPROVED_ALLOCATION")
    return issues


def evaluate(scope: dict, docs: dict[str, str | None], na: dict[str, dict] | None = None) -> dict:
    """docs: {doc_name: evidence ref or None}. na: {doc_name: {rationale, approved_by}} for QM scope only."""
    issues = validate(scope)
    na = na or {}
    asil = scope.get("target_asil")
    dispositions = {}
    if asil in ("A", "B", "C", "D"):
        if not scope.get("hsi_hash"):
            issues.append("SAFETY_EVIDENCE_MISSING:hsi")
        if not scope.get("allocation_review_ref"):
            issues.append("SAFETY_EVIDENCE_MISSING:allocation_review")
        for d in SAFETY_DOCS:
            if docs.get(d):
                dispositions[d] = "PRESENT"
            else:
                dispositions[d] = "MISSING"
                issues.append(f"SAFETY_EVIDENCE_MISSING:{d}")
            if d in na:
                issues.append(f"NA_NOT_PERMITTED_FOR_ASIL:{d}")
    elif asil == "QM":
        for d in SAFETY_DOCS:
            if docs.get(d):
                dispositions[d] = "PRESENT"
                continue
            n = na.get(d) or {}
            if len(str(n.get("rationale", "")).strip()) >= 20 and _human(n.get("approved_by")):
                dispositions[d] = "NOT_APPLICABLE_QM"
            else:
                dispositions[d] = "MISSING"
                issues.append(f"QM_NA_WITHOUT_RATIONALE:{d}")
    return {"target_asil": asil, "state": "BLOCKED" if issues else "SATISFIED", "issues": issues,
            "dispositions": dispositions, "safety_approval": None}


def claim_text_findings(scope: dict, text: str) -> list[str]:
    """AT-079: reject compliance/approval text, and any ASIL level different from the approved scope."""
    out = [f"FALSE_COMPLIANCE_TEXT:{h}" for h in compliance_assertions(text)]
    asil = scope.get("target_asil")
    for m in re.finditer(r"\bASIL[ _-]?([A-D])\b", text):
        if asil == "QM" or m.group(1) != asil:
            out.append(f"ASIL_MISMATCH_TEXT:{m.group(0)}!={asil}")
    return out
