"""Owner decision 2026-11-03 (C): structural coverage of the scoped driver code is a BLOCKING SWE.4 gate.

- every purpose: 100% line (statement) and 100% branch coverage;
- additionally 100% MC/DC when the work-order purpose is a safety purpose;
- "not applicable" stays acceptable: llvm-cov counts no branch points / decisions (percentage None).

Purpose (the work-order manifest's `purpose`, set by workorder.prepare --purpose): ASPICE_ONLY and QM are the owner's
non-safety engineering lanes (release/aspice.py: "Safety assurance is not assessed in this lane"; QM = quality
management). DEVELOPMENT and FORMAL_REVIEW are the safety-development lanes (release/development.py: SSA/TAA signatures
deferred or strict) and require MC/DC as well. A manifest without a known purpose is refused, never guessed.

Applies to work orders with unit_verification (prepared after 2026-11-03); older work orders keep the reported
(non-blocking) coverage goal they were run with. Measures come from the latest llvm_coverage tool result (LLVM 19
source-based coverage, -fcoverage-mcdc), which must be newer than the latest run_unit.
"""
from __future__ import annotations

import json
from pathlib import Path

NON_SAFETY = ("ASPICE_ONLY", "QM")
SAFETY = ("DEVELOPMENT", "FORMAL_REVIEW")


def purpose(ws: Path) -> str | None:
    try:
        return json.loads((Path(ws) / ".forge-run/manifest.json").read_text()).get("purpose")
    except (OSError, ValueError):
        return None


def required(ws: Path) -> dict:
    """{'purpose', 'measures': [(label, metric key)], 'mcdc': bool} for this work order."""
    p = purpose(ws)
    if p not in NON_SAFETY + SAFETY:
        raise ValueError(f"COVERAGE_GATE_PURPOSE_UNKNOWN:{p}")
    measures = [("line", "line_pct"), ("branch", "branch_pct")]
    if p in SAFETY:
        measures.append(("MC/DC", "mcdc_pct"))
    return {"purpose": p, "measures": measures, "mcdc": p in SAFETY}


def enabled(ws: Path) -> bool:
    from ..layer import uspec_gtest

    return uspec_gtest(ws)


def _scope_keys(metrics: dict) -> dict:
    """A brownfield delivery measures its scope functions (CAPA-060): regions stand for statements there."""
    if "scope_functions" in metrics:
        return {"line_pct": metrics.get("scope_region_pct"), "branch_pct": metrics.get("scope_branch_pct"),
                "mcdc_pct": metrics.get("mcdc_pct")}
    return metrics


def evaluate(ws: Path, cov: dict | None = None, run_ts: str | None = None) -> dict:
    """{'status': PASS|FAIL, 'purpose', 'rows': [{measure, value, status}], 'findings': [...]}. `cov`: an llvm_coverage
    result (default: the latest recorded one)."""
    from ..release.finalize import latest, tool_results

    req = required(ws)
    findings, rows = [], []
    if cov is None:
        res = tool_results(Path(ws))
        rec = latest(res, "forge-tests-mcp", "llvm_coverage")
        run = latest(res, "forge-tests-mcp", "run_unit")
        cov = rec["result"] if rec else None
        if rec and run and rec.get("ts_utc", "") < run.get("ts_utc", ""):
            findings.append("COVERAGE_GATE:STALE (the latest llvm_coverage is older than the latest run_unit)")
    if not cov or cov.get("status") != "PASS":
        findings.append(f"COVERAGE_GATE:NOT_MEASURED (llvm_coverage {cov.get('status') if cov else 'NOT_RUN'})")
        return {"status": "FAIL", "purpose": req["purpose"], "rows": rows, "findings": findings}
    m = _scope_keys(cov.get("metrics") or {})
    for label, key in req["measures"]:
        v = m.get(key)
        if v is None:
            rows.append({"measure": label, "value": None, "status": "NOT_APPLICABLE"})
        elif float(v) >= 100.0:
            rows.append({"measure": label, "value": v, "status": "MET"})
        else:
            rows.append({"measure": label, "value": v, "status": "NOT_MET"})
            findings.append(f"COVERAGE_GATE:{label.replace('/', '').upper()}_NOT_100:{v}% (purpose {req['purpose']}: "
                            f"100% {label} coverage of the scoped driver code is blocking)")
    if not req["mcdc"]:
        v = m.get("mcdc_pct")
        rows.append({"measure": "MC/DC", "value": v, "status": "REPORTED (not blocking for this purpose)"})
    return {"status": "FAIL" if findings else "PASS", "purpose": req["purpose"], "rows": rows, "findings": findings}


def findings(ws: Path) -> list[str]:
    """Author-gate findings (empty for work orders without unit_verification)."""
    if not enabled(ws):
        return []
    try:
        return evaluate(ws)["findings"]
    except ValueError as exc:
        return [str(exc)]


def report_lines(ev: dict) -> list[str]:
    out = [f"Coverage gate (owner 2026-11-03, purpose {ev['purpose']}): 100% line and branch coverage of the scoped "
           "driver code are blocking" + (", and 100% MC/DC" if any(r["measure"] == "MC/DC" and
                                                                     not r["status"].startswith("REPORTED")
                                                                     for r in ev["rows"]) else "") +
           "; a measure llvm-cov does not count (no branch points or decisions) is not applicable.", ""]
    for r in ev["rows"]:
        v = "n/a" if r["value"] is None else f"{r['value']}%"
        out.append(f"- {r['measure']}: {v} - {r['status']}")
    out.append(f"- gate: {ev['status']}")
    return out
