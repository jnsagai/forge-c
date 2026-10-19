"""EASA-T019/T057/T058 — Claim-Argument-Evidence graph with counterevidence (EASA-FR-023/057/058).

States are computed, never asserted:
  SUPPORTED   every evidence ref is an accepted, hash-bound verification record, no counterevidence, all
              sub-claims SUPPORTED, verifier independent of the author;
  CONTESTED   any counterevidence (e.g. a failing run for the same requirement) — the rebuttal link is kept;
  UNSUPPORTED no accepted evidence (e.g. every node "PASS" but no hashes), or a sub-claim UNSUPPORTED;
  UNKNOWN     evidence references that cannot be resolved yet.
A claim whose assertion is a safety approval/certification conclusion is REFUSED whoever verifies it, and an AI
author can never verify its own claim.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from . import contracts
from .normative import compliance_assertions

SAFETY_CONCLUSION = re.compile(r"\b(safe(ty)? (for|to) (release|production)|safety (approved|accepted|signed[- ]off)|"
                               r"meets (all )?safety (goals|requirements)|ASIL[ _-]?[A-D][ _-]?approved|"
                               r"release(d)? for production)\b", re.I)


@dataclass
class Claim:
    claim_id: str
    work_order_id: str
    assertion: str
    argument: str
    evidence_refs: list[str] = field(default_factory=list)
    counterevidence_refs: list[str] = field(default_factory=list)
    verifier_ref: str = ""
    author_ref: str = ""
    children: list[str] = field(default_factory=list)


class CaseGraph:
    def __init__(self, evidence_index: dict[str, dict]):
        """evidence_index: ref -> {"accepted": bool, "sha256": str|None, "status": PASS/FAIL/..., "requirement": id}."""
        self.ev = evidence_index
        self.claims: dict[str, Claim] = {}

    def add(self, c: Claim) -> None:
        self.claims[c.claim_id] = c

    def evaluate(self, cid: str, _seen: frozenset = frozenset()) -> dict:
        c = self.claims[cid]
        reasons = []
        if cid in _seen:
            return {"status": "UNSUPPORTED", "reasons": ["CIRCULAR_ARGUMENT"]}
        if SAFETY_CONCLUSION.search(c.assertion) or compliance_assertions(c.assertion):
            return {"status": "UNSUPPORTED", "reasons": ["UNAUTHORIZED_SAFETY_CONCLUSION_REFUSED"], "refused": True}
        if not c.verifier_ref or c.verifier_ref == c.author_ref:
            reasons.append("SELF_VERIFIED_OR_NO_VERIFIER")
        good, unknown = [], []
        for ref in c.evidence_refs:
            e = self.ev.get(ref)
            if e is None:
                unknown.append(ref)
            elif e.get("accepted") and e.get("sha256") and e.get("status") == "PASS":
                good.append(ref)
            elif e.get("status") == "FAIL":
                c.counterevidence_refs = sorted(set(c.counterevidence_refs) | {ref})
            else:
                reasons.append(f"EVIDENCE_NOT_ACCEPTED:{ref}")
        kids = {k: self.evaluate(k, _seen | {cid}) for k in c.children}
        if c.counterevidence_refs:
            return {"status": "CONTESTED", "reasons": [f"REBUTTED_BY:{r}" for r in c.counterevidence_refs],
                    "children": kids}
        if any(k["status"] == "CONTESTED" for k in kids.values()):
            return {"status": "CONTESTED", "reasons": ["SUBCLAIM_CONTESTED"], "children": kids}
        if not good and not kids and not unknown:
            reasons.append("NO_HASH_BOUND_EVIDENCE")
        if any(k["status"] in ("UNSUPPORTED",) for k in kids.values()):
            reasons.append("SUBCLAIM_UNSUPPORTED")
        if reasons:
            return {"status": "UNSUPPORTED", "reasons": reasons, "children": kids}
        if unknown or any(k["status"] == "UNKNOWN" for k in kids.values()):
            return {"status": "UNKNOWN", "reasons": [f"UNRESOLVED_EVIDENCE:{u}" for u in unknown], "children": kids}
        return {"status": "SUPPORTED", "reasons": [], "children": kids}

    def record(self, cid: str) -> dict:
        c, r = self.claims[cid], self.evaluate(cid)
        rec = {"claim_id": c.claim_id, "work_order_id": c.work_order_id, "assertion": c.assertion,
               "argument": c.argument, "evidence_refs": c.evidence_refs, "counterevidence_refs": c.counterevidence_refs,
               "status": r["status"], "verifier_ref": c.verifier_ref or "none"}
        assert not contracts.errors("assurance-claim", rec), contracts.errors("assurance-claim", rec)
        return {**rec, "reasons": r["reasons"]}
