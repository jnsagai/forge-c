"""EASA-T010/T015 — per-work-order applicability of every catalog method (EASA-FR-008/009/070).

Decisions: APPLICABLE, NOT_APPLICABLE_WITH_RATIONALE, ALTERNATIVE_SELECTED, NOT_SUPPORTED, UNKNOWN. No implicit
waiver: a method without a decision is UNKNOWN; N/A and ALTERNATIVE need a rationale and a human reviewer;
an alternative must be another method of the SAME table (ISO tables list alternative combinations per table);
NOT_SUPPORTED is a visible gap. A decision is changed only by a new record superseding the old one.
"""
from __future__ import annotations

from . import contracts
from .policy import _human

DECISIONS = ("APPLICABLE", "NOT_APPLICABLE_WITH_RATIONALE", "ALTERNATIVE_SELECTED", "NOT_SUPPORTED", "UNKNOWN")


def check(dec: dict, catalog: dict) -> list[str]:
    issues = contracts.errors("method-applicability", dec)
    methods = {m["method_id"]: m for m in catalog["methods"]}
    m = methods.get(dec.get("method_id"))
    if m is None:
        return issues + [f"UNKNOWN_METHOD:{dec.get('method_id')}"]
    d = dec.get("decision")
    rationale = str(dec.get("rationale") or "").strip()
    if d in ("NOT_APPLICABLE_WITH_RATIONALE", "ALTERNATIVE_SELECTED", "NOT_SUPPORTED") and len(rationale) < 20:
        issues.append(f"RATIONALE_REQUIRED:{d}")
    if d in ("NOT_APPLICABLE_WITH_RATIONALE", "ALTERNATIVE_SELECTED") and not _human(dec.get("reviewer_ref")):
        issues.append("HUMAN_REVIEWER_REQUIRED")
    if d == "ALTERNATIVE_SELECTED":
        alt = methods.get(dec.get("alternative_method_ref") or "")
        if alt is None:
            issues.append("ALTERNATIVE_UNKNOWN")
        elif alt["table"] != m["table"] or alt["method_id"] == m["method_id"]:
            issues.append("ALTERNATIVE_NOT_IN_SAME_TABLE")
    elif dec.get("alternative_method_ref"):
        issues.append("ALTERNATIVE_REF_WITHOUT_ALTERNATIVE_DECISION")
    return issues


def record(store, dec: dict, catalog: dict, supersedes: str | None = None) -> tuple[str | None, list[str]]:
    issues = check(dec, catalog)
    if issues:
        return None, issues
    prev = store.current("applicability", f"{dec['work_order_id']}:{dec['method_id']}")
    if prev and supersedes != prev["record_id"]:
        return None, ["DECISION_EXISTS_SUPERSEDE_EXPLICITLY"]
    rid = store.append("applicability", f"{dec['work_order_id']}:{dec['method_id']}", dec,
                       actor=dec.get("reviewer_ref") or "factory", work_order_id=dec["work_order_id"],
                       supersedes=supersedes)
    return rid, []


def coverage(store, work_order_id: str, catalog: dict) -> dict:
    """Every catalog method gets a decision; missing ones are UNKNOWN (reported, never assumed applicable/N-A)."""
    out = {}
    for m in catalog["methods"]:
        cur = store.current("applicability", f"{work_order_id}:{m['method_id']}")
        out[m["method_id"]] = cur["record"]["decision"] if cur else "UNKNOWN"
    counts = {d: sum(1 for v in out.values() if v == d) for d in DECISIONS}
    return {"work_order_id": work_order_id, "methods": out, "counts": counts, "total": len(out),
            "gaps": sorted(k for k, v in out.items() if v in ("UNKNOWN", "NOT_SUPPORTED"))}


def gate_view(decisions: dict[str, str], evidence: dict[str, list[str]], na_allowed_by_policy: set[str]) -> dict:
    """AT-011: APPLICABLE needs evidence; N/A counts only if the policy allows N/A for that method."""
    issues = []
    for mid, d in decisions.items():
        if d in ("APPLICABLE", "ALTERNATIVE_SELECTED") and not evidence.get(mid):
            issues.append(f"EVIDENCE_MISSING:{mid}")
        elif d == "NOT_APPLICABLE_WITH_RATIONALE" and mid not in na_allowed_by_policy:
            issues.append(f"NA_NOT_ALLOWED_BY_POLICY:{mid}")
        elif d in ("UNKNOWN", "NOT_SUPPORTED"):
            issues.append(f"METHOD_{d}:{mid}")
    return {"state": "BLOCKED" if issues else "PASS", "issues": issues}
