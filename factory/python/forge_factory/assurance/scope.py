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


# CAPA-044 (r144-r152): ASIL B work products stated "QM development scope" from a stale example manifest field
QM_CLAIM = re.compile(r"\bQM (?:development|scope)\b|OUT_OF_SCOPE:\s*QM\b|\bQM\b[^.\n]{0,40}\bno (?:software )?safety "
                      r"(?:requirements?|allocation)", re.I)


def scope_level_findings(scope: dict, text: str) -> list[str]:
    """Any ASIL level different from the approved scope, and a QM claim inside an ASIL A-D scope."""
    out = []
    asil = scope.get("target_asil")
    for m in re.finditer(r"\bASIL[ _-]?([A-D])\b", text):
        if asil == "QM" or m.group(1) != asil:
            out.append(f"ASIL_MISMATCH_TEXT:{m.group(0)}!={asil}")
    if asil in ("A", "B", "C", "D"):
        out += [f"QM_CLAIM_IN_ASIL_SCOPE:{' '.join(m.group(0).split())[:60]}!=ASIL {asil}" for m in QM_CLAIM.finditer(text)]
    return out


def claim_text_findings(scope: dict, text: str) -> list[str]:
    """AT-079: reject compliance/approval text, and any ASIL level different from the approved scope."""
    return [f"FALSE_COMPLIANCE_TEXT:{h}" for h in compliance_assertions(text)] + scope_level_findings(scope, text)


def allocation_status(rec: dict) -> str:
    """manifest target.safety_allocation for an owner scope (CAPA-044): the approved target, and the allocation
    review state - PENDING until the owner records an allocation review reference (never derived by an agent)."""
    sc = rec["scope"]
    head = f"ASIL {sc['target_asil']}" if sc["target_asil"] != "QM" else "QM"
    who = f"{sc['scope_id']}, approved by {rec['approved_by']} on {rec['approved_at']}"
    if sc["target_asil"] == "QM":
        return f"OUT_OF_SCOPE: QM development, no safety allocation or safety claims ({who})"
    if not sc.get("allocation_review_ref"):
        return f"{head} ({who}); software safety allocation PENDING owner allocation review"
    return f"{head} ({who}); allocation review {sc['allocation_review_ref']}"


DECISIONS = "config/factory/safety-scope.yaml"


def owner_scope(example: str, work_order_id: str, source_requirements_hash: str, repo=None) -> dict | None:
    """The owner's scope decision for an example work order, as a safety-scope record (None if none recorded).
    Refuses (ValueError) a decision that is not human-approved or whose ASIL source is not an approved allocation."""
    from pathlib import Path

    from ..common import REPO_ROOT, load_yaml

    p = Path(repo or REPO_ROOT) / DECISIONS
    if not p.is_file():
        return None
    for d in (load_yaml(p) or {}).get("decisions") or []:
        if example not in (d.get("examples") or []):
            continue
        if not _human(d.get("approved_by")) or not d.get("approved_at"):
            raise ValueError(f"SCOPE_DECISION_NOT_HUMAN_APPROVED:{d.get('scope_id')}")
        rec = {"scope_id": d["scope_id"], "work_order_id": work_order_id, "target_asil": d["target_asil"],
               "source_requirements_hash": source_requirements_hash, "hsi_hash": d.get("hsi_hash"),
               "allocation_review_ref": d.get("allocation_review_ref"),
               "product_asil_source": " ".join(str(d["product_asil_source"]).split())}
        issues = validate(rec)
        if issues:
            raise ValueError(f"SCOPE_DECISION_INVALID:{issues}")
        docs, doc_issues = owner_documents(d, source_requirements_hash, Path(repo or REPO_ROOT))
        return {"scope": rec, "na": d.get("na") or {}, "approved_by": d["approved_by"], "approved_at": d["approved_at"],
                "documents": docs, "document_issues": doc_issues}
    return None


DOC_DIR = "config/factory/safety-documents/"
DOC_FILES = {"software_safety_analysis": "safety/software_safety_analysis.md",
             "tool_assurance_assessment": "safety/tool_assurance_assessment.md"}
DRAFT_MARK = re.compile(r"\bDRAFT\b[^\n]{0,60}\bnot approved\b", re.I)


def owner_documents(decision: dict, source_requirements_hash: str, repo) -> tuple[list[dict], list[str]]:
    """OD-2026-10-19-11: the owner-signed safety documents of a scope decision that apply to this work order.

    A document counts only when its register entry (`safety_documents.<key>` in the scope decision) names a human
    approver and date, its file under config/factory/safety-documents/ still has the registered SHA-256, its basis is
    this work order's source requirements hash, and the file no longer carries the draft marker. Anything else is an
    issue and the document is left out, so the package stays BLOCKED on it. An agent never writes the register."""
    from ..common import sha256_bytes

    docs, issues = [], []
    reg = decision.get("safety_documents") or {}
    for key, rel in DOC_FILES.items():
        e = reg.get(key)
        if not isinstance(e, dict):
            issues.append(f"SAFETY_DOC_NOT_REGISTERED:{key}")
            continue
        src = str(e.get("path") or "")
        if not src.startswith(DOC_DIR) or ".." in src.split("/"):
            issues.append(f"SAFETY_DOC_PATH_INVALID:{key}")
            continue
        if not _human(e.get("approved_by")) or not e.get("approved_at") or not e.get("sha256"):
            issues.append(f"SAFETY_DOC_NOT_SIGNED:{key}")
            continue
        f = repo / src
        data = f.read_bytes() if f.is_file() else b""
        if not data or sha256_bytes(data) != e["sha256"]:
            issues.append(f"SAFETY_DOC_HASH_MISMATCH:{key}")
        elif e.get("basis") != source_requirements_hash:
            issues.append(f"SAFETY_DOC_BASIS_CHANGED:{key}")
        elif DRAFT_MARK.search(data.decode("utf-8", errors="replace")):
            issues.append(f"SAFETY_DOC_STILL_DRAFT:{key}")
        else:
            docs.append({"key": key, "path": rel, "source": src, "sha256": e["sha256"], "basis": e["basis"],
                         "approved_by": e["approved_by"], "approved_at": str(e["approved_at"]),
                         "decision": e.get("decision")})
    return docs, issues


def signed_documents(manifest: dict) -> dict[str, str]:
    """{workspace path: registered SHA-256} of the owner-signed safety documents copied into a work order."""
    return {d["path"]: d["sha256"] for d in manifest.get("owner_safety_documents") or []}


SCOPE_FILE = ".forge-run/safety_scope.json"


def workspace_scope_findings(ws, phase: str) -> list[str]:
    """CAPA-044 author gate: the phase's markdown work products (and the safety/upstream-gap files) must state the
    owner's approved safety level - no other ASIL, no QM claim in an ASIL scope. [] without an owner scope."""
    import json
    from pathlib import Path

    ws = Path(ws)
    p = ws / SCOPE_FILE
    if not p.is_file():
        return []
    sc = json.loads(p.read_text()).get("scope") or {}
    files = sorted((ws / "workproducts" / phase).rglob("*.md")) if (ws / "workproducts" / phase).is_dir() else []
    if phase == "SWE.1":
        files += sorted((ws / "safety").glob("*.md")) + [ws / "traceability/upstream_gaps.md"]
    out = []
    for f in files:
        if f.is_file():
            out += [f"SAFETY_SCOPE:{x}:{f.relative_to(ws)}" for x in scope_level_findings(sc, f.read_text(errors="replace"))]
    return sorted(set(out))[:10]
