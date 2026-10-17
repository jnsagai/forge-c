"""EASA-T002 — ISO 26262-6:2018 availability, copyright boundary and normative authority (fail closed).

The repository holds NO standard text. A licensed copy may be registered locally (outside the repo) through
FORGE_ISO26262_6_2018_PATH; only its sha256 and edition are recorded. Without a registered copy AND a reviewer-signed
per-table reconciliation, the method catalog stays PROVISIONAL and every normative/compliance assertion is rejected.
Even a reconciled catalog never authorizes an ISO 26262 compliance or ASIL approval claim by the factory.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

from ..common import REPO_ROOT, sha256_file

EDITION = "ISO 26262-6:2018"
ENV = "FORGE_ISO26262_6_2018_PATH"
COMPLIANCE_PATTERNS = [r"\bISO\s*26262[^.\n]{0,40}\b(complian\w*|conform\w*|certif\w*)",
                       r"\b(complian\w*|conform\w*|certif\w*)[^.\n]{0,40}\bISO\s*26262",
                       r"\bASIL[ _-]?[A-D][ _-]?(approved|compliant|certified)\b", r"\bASIL_[A-D]_APPROVED\b",
                       r"\b(ASPICE|Automotive SPICE)[^.\n]{0,30}\b(CL ?[1-5]|capability level [1-5])\b(?! not)",
                       r"\bsafety[- ]certified\b"]


def standard_access() -> dict:
    """What is actually available. The path must be outside the repository (no redistribution)."""
    p = os.environ.get(ENV)
    if not p:
        return {"edition": EDITION, "licensed_copy": "NOT_AVAILABLE", "sha256": None,
                "normative_verification": "BLOCKED", "reason": f"{ENV} not set: no licensed copy registered"}
    path = Path(p).resolve()
    if not path.is_file():
        return {"edition": EDITION, "licensed_copy": "NOT_AVAILABLE", "sha256": None,
                "normative_verification": "BLOCKED", "reason": "registered path does not exist"}
    if REPO_ROOT.resolve() in path.parents:
        return {"edition": EDITION, "licensed_copy": "REJECTED_IN_REPOSITORY", "sha256": None,
                "normative_verification": "BLOCKED", "reason": "copyrighted standard must not be stored in the repo"}
    return {"edition": EDITION, "licensed_copy": "REGISTERED", "sha256": sha256_file(path),
            "normative_verification": "REQUIRES_REVIEWER_RECONCILIATION", "reason": None}


NEGATION = re.compile(r"\b(not|no|never|without|nor|cannot|isn't|is not|does not|doesn't|don't|won't|aren't|NOT_CLAIMED|NOT CLAIMED)\b", re.I)


def compliance_assertions(text: str) -> list[str]:
    """Phrases that ASSERT ISO/ASIL/ASPICE conformance, approval or certification. A phrase inside a negated clause
    ("is not an ISO 26262 conformance statement", "no ASIL approval") is a disclaimer, not an assertion."""
    hits = []
    for rx in COMPLIANCE_PATTERNS:
        for m in re.finditer(rx, text, re.I):
            clause_start = max(text.rfind(c, 0, m.start()) for c in (".", ";", "\n", ":", "(", "|"))
            if NEGATION.search(text[clause_start + 1:m.end()]):
                continue
            hits.append(m.group(0))
    return hits


def assert_normative_claim(catalog: dict, claim_text: str) -> dict:
    """AT-002/AT-083: a compliance/normative assertion is REJECTED unless the catalog is reconciled; even then the
    factory may only state bounded engineering evidence (EASA-FR-071), so a compliance assertion is always rejected."""
    issues = []
    status = catalog.get("document_status") or catalog.get("norm_catalog_status")
    unchecked = [m["method_id"] for m in catalog.get("methods", []) if not m.get("normative_checked")]
    if status != "CONTROLLED_RECONCILED" or unchecked:
        issues.append(f"NORMATIVE_UNVERIFIED:{len(unchecked)} methods unchecked, catalog {status}")
    if compliance_assertions(claim_text):
        issues.append("COMPLIANCE_CLAIM_NOT_PERMITTED")
    return {"decision": "REJECTED" if issues else "ACCEPTED_AS_BOUNDED_EVIDENCE", "issues": issues}
