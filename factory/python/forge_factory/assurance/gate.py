"""EASA-T020/T022 — assurance gate per SWE phase (EASA-FR-014/018/020/059).

Each requirement of the effective profile must be satisfied by ACCEPTED evidence: a validated tool execution or a
controlled review record signed by a human. An AI inspector's PASS text satisfies nothing on its own (AT-020).
Unobserved requirements stay NOT_RUN/UNKNOWN; any failing evidence makes the phase FAIL; anything missing BLOCKS.
KPIs (throughput, token cost, cycle time) are not inputs: they cannot trade against quality or safety evidence.
In OBSERVE_ONLY the decision is recorded with `enforced: false` and never changes the existing 002 gate outcome.
"""
from __future__ import annotations

from ..common import new_id
from . import contracts
from .policy import _human

REVIEW_KINDS = ("controlled_review", "independent_inspection_with_evidence")


def decide(*, work_order_id: str, phase: str, mode: str, requirements: list[str], evidence: dict[str, list[dict]],
           inspector_text: str | None, profile_hash: str, catalog_hash: str, baseline_hash: str,
           method_decision_refs: list[str] | None = None, claim_refs: list[str] | None = None,
           verifier_ref: str = "easa-gate", **ignored_kpis) -> dict:
    """evidence: requirement -> [{"ref", "kind": tool|controlled_review|ai_inspection, "accepted", "status",
    "reviewer"}]."""
    findings, per_req, refs = [], {}, []
    for req in requirements:
        items = evidence.get(req) or []
        ok = [e for e in items if e.get("accepted") and e.get("status") == "PASS" and
              (e.get("kind") == "tool" or (e.get("kind") in REVIEW_KINDS and _human(e.get("reviewer"))))]
        bad = [e for e in items if e.get("accepted") and e.get("status") == "FAIL"]
        ai_only = items and all(e.get("kind") == "ai_inspection" for e in items)
        refs += [e["ref"] for e in items if e.get("ref")]
        if bad:
            per_req[req] = "FAIL"
            findings.append(f"ASSURANCE_GATE_FAILED:{req}:{bad[0].get('ref')}")
        elif ok:
            per_req[req] = "PASS"
        elif ai_only:
            per_req[req] = "UNKNOWN"
            findings.append(f"AI_PASS_NOT_EVIDENCE:{req}")
        elif items:
            per_req[req] = "UNKNOWN"
            findings.append(f"EVIDENCE_NOT_ACCEPTED:{req}")
        else:
            per_req[req] = "NOT_RUN"
            findings.append(f"EVIDENCE_MISSING:{req}")
    if inspector_text and not requirements:
        findings.append("AI_PASS_NOT_EVIDENCE:no requirements evaluated")
    state = "FAIL" if "FAIL" in per_req.values() else ("PASS" if per_req and all(v == "PASS" for v in per_req.values())
                                                         else "BLOCKED")
    rec = {"gate_id": new_id("easa-gate"), "work_order_id": work_order_id, "phase": phase, "profile_hash": profile_hash,
           "method_catalog_hash": catalog_hash, "baseline_hash": baseline_hash,
           "method_decision_refs": method_decision_refs or [], "claim_refs": claim_refs or [],
           "evidence_refs": list(dict.fromkeys(refs)),
           "findings": findings, "state": state, "verifier_ref": verifier_ref}
    issues = contracts.errors("gate-decision", rec)
    if issues:
        raise ValueError(f"gate decision violates contract: {issues}")
    return {**rec, "requirements": per_req, "mode": mode, "enforced": mode == "ENFORCING",
            "ignored_inputs": sorted(ignored_kpis)}
