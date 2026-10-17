"""EASA-T063/T070 — assurance readiness record (contract `assurance-readiness`) and the reviewer-readable assurance
case summary. ENFORCING readiness is decided only from real evidence and authorization (policy.request_mode); this
module never switches the mode and never states a safety approval (`safety_approval` is always null)."""
from __future__ import annotations

from pathlib import Path

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


def pilot_yield(work_orders: list[str]) -> dict:
    """End-to-end product yield of real pilot work orders: READY_FOR_OFFLINE_REVIEW packages / finished runs."""
    import json

    from ..common import state_dir

    seen = {}
    for wo in work_orders:
        p = state_dir() / "workorders" / wo / "workspace/.forge-run/package.json"
        if p.is_file():
            seen[wo] = json.loads(p.read_text()).get("package_status")
    ready = [w for w, s in seen.items() if s == "READY_FOR_OFFLINE_REVIEW"]
    return {"runs": seen, "finished": len(seen), "ready": len(ready),
            "yield": round(len(ready) / len(seen), 3) if seen else None}


def decide(work_orders: list[str], store=None) -> dict:
    """EASA-T070: may EASA switch to ENFORCING? Read-only: evaluates the same preconditions as policy.request_mode
    (without recording a request), plus catalog, independence-free technical evidence and pilot yield. Never switches
    the mode, never approves safety."""
    from .store import AssuranceStore

    pol = contracts.load(policy.POLICY_PATH if policy.POLICY_PATH.is_file() else contracts.POLICY_EXAMPLE)
    store = store or AssuranceStore()
    modes = [r for r in store.history("mode") if '"pilot_status"' in str(r.get("record") or "")]
    pilot = modes[-1] if modes else None
    blocking = [f"MODE:{i}" for i in policy.mode_preconditions(pol["mode"], "ENFORCING", None, pilot)]
    if not policy.POLICY_PATH.is_file():
        blocking.append("POLICY:FILE_ABSENT (built-in example policy, OBSERVE_ONLY)")
    if catalog.status(catalog.load()) != "RECONCILED":
        blocking.append("CATALOG:UNVERIFIED (no licensed ISO 26262-6:2018 source, no competent-reviewer reconciliation)")
    y = pilot_yield(work_orders)
    if not y["ready"]:
        blocking.append(f"E2E:NO_READY_PACKAGE ({y['finished']} finished pilot runs, 0 READY_FOR_OFFLINE_REVIEW)")
    rec = record(pol["mode"], y["yield"], blocking)  # 0.0 is a measurement, not "not measured"
    return {"decision": "NOT_READY" if blocking else "ELIGIBLE_FOR_OWNER_DECISION", "readiness": rec, "pilots": y,
            "note": "Readiness only; switching the mode needs policy.request_mode with a human authorization."}


def main(argv: list[str] | None = None) -> int:
    import argparse
    import json

    from ..common import REPO_ROOT, pretty_json

    ap = argparse.ArgumentParser(prog="forge_factory.assurance.readiness")
    ap.add_argument("--work-orders", nargs="*", default=[f"WO-0002A-STM32N6-RCC-LL-r{n}" for n in range(108, 140)])
    ap.add_argument("--out", type=Path, default=REPO_ROOT / "evidence/easa/status/readiness.json")
    ap.add_argument("--case", type=Path, default=REPO_ROOT / "docs/assurance/ASSURANCE-CASE.md")
    a = ap.parse_args(argv)
    d = decide(a.work_orders)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(pretty_json(d))
    rep = matrix.build()
    open_ = [{"claim": t, "status": v["status"], "evidence": v.get("reason") or "-"}
             for t, v in {**rep["tasks"], **rep["addendum_tasks"]}.items() if v["status"] != "PASS"]
    lim = ["Renode is a behavioural model, not HIL; no physical target; RCC_CR reset value differs from the RM",
           "Formal checks (CBMC, Eva) cover runtime errors and bounded termination only, with registers as memory",
           "Author and inspector share one model and provider: independence PARTIAL",
           "False-positive rate on unseen packages NOT_MEASURED; the seeded corpus was designed by the implementer"]
    a.case.write_text(case_summary(d["readiness"], open_, lim))
    print(json.dumps({"decision": d["decision"], "blocking": d["readiness"]["blocking_items"]}))
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
