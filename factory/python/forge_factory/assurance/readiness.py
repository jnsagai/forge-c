"""EASA-T063/T070 — assurance readiness record (contract `assurance-readiness`) and the reviewer-readable assurance
case summary. ENFORCING readiness is decided only from real evidence and authorization (policy.request_mode); this
module never switches the mode and never states a safety approval (`safety_approval` is always null)."""
from __future__ import annotations

from ..common import utc_now
from . import catalog, contracts, matrix, policy


def record(mode: str, e2e_yield: float | None, blocking: list[str]) -> dict:
    rep = matrix.build()
    counts = rep["task_counts"]
    impl = "COMPLETE" if counts.get("PASS", 0) == len(rep["tasks"]) else ("PARTIAL" if counts.get("PASS") else "SPEC_ONLY")
    rec = {"feature": "006-enhanced-ai-software-assurance", "implementation": impl, "configured_mode": mode,
           "normative_catalog_status": "RECONCILED" if catalog.status(catalog.load()) == "RECONCILED" else "UNVERIFIED",
           "technical_gates": "DEMONSTRATED" if e2e_yield else "NOT_DEMONSTRATED", "e2e_product_yield": e2e_yield,
           "safety_approval": None, "blocking_items": blocking}
    issues = contracts.errors("assurance-readiness", rec)
    if issues:
        raise ValueError(issues)
    return rec


def case_summary(readiness: dict, findings: list[dict], limitations: list[str]) -> str:
    rep = matrix.build()
    pol = contracts.load(policy.POLICY_PATH if policy.POLICY_PATH.is_file() else contracts.POLICY_EXAMPLE)
    lines = ["# Feature 006 assurance case summary (generated)", "", f"Generated {utc_now()} at `{rep['git_head'][:12]}`.",
             "", "This is bounded engineering evidence for offline human review. It is not an ISO 26262 or Automotive "
             "SPICE conformance statement, not an ASIL approval and not a safety sign-off.", "",
             "## Readiness", "", f"- Implementation: {readiness['implementation']}; configured mode: "
             f"{readiness['configured_mode']} (profile {pol['profile']}).",
             f"- Normative method catalog: {readiness['normative_catalog_status']} (47-entry secondary working index; "
             "no licensed ISO 26262-6:2018 copy registered).",
             f"- Technical gates end to end: {readiness['technical_gates']}; product yield: "
             f"{readiness['e2e_product_yield'] if readiness['e2e_product_yield'] is not None else 'not measured'}.",
             "- Safety approval: none (outside the factory).", "", "## Blocking items", ""]
    lines += [f"- {b}" for b in readiness["blocking_items"]] or ["- none"]
    lines += ["", "## Top-level claims", "", "| Claim | Status | Evidence / counterevidence |", "|---|---|---|"]
    lines += [f"| {f['claim']} | {f['status']} | {f['evidence']} |" for f in findings]
    lines += ["", "## Stated limitations", ""] + [f"- {x}" for x in limitations]
    c = rep["task_counts"]
    lines += ["", "## Task and requirement status", "", "Tasks: " + ", ".join(f"{k} {v}" for k, v in sorted(c.items())) +
              ". FRs: " + ", ".join(f"{k} {v}" for k, v in rep["fr_counts"].items()) +
              ". Details: `docs/assurance/EASA-STATUS.md`.", ""]
    return "\n".join(lines)
