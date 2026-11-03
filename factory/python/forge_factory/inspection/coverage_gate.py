"""Owner decision 2026-11-03 (C): structural coverage of the scoped driver code is a BLOCKING SWE.4 gate.

- owner rule 2026-11-03: the order's quality block states target and minimum per measure (forge_factory.quality);
  without it the defaults are target = minimum = 100% line (statement) and branch, + 100% MC/DC for a safety purpose;
- the gate FAILS only below a minimum; below the target it passes and the shortfall is reported;
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
    """{'purpose', 'measures': [(label, metric key, quality key)], 'mcdc': bool, 'quality': {...}, 'source'}: the
    order's structural-coverage targets/minimums (owner rule 2026-11-03; defaults without a quality block)."""
    from ..quality import for_workspace

    p = purpose(ws)
    if p not in NON_SAFETY + SAFETY:
        raise ValueError(f"COVERAGE_GATE_PURPOSE_UNKNOWN:{p}")
    q, src = for_workspace(ws)
    sc = q["structural_coverage"]
    names = {"line": ("line", "line_pct"), "branch": ("branch", "branch_pct"), "mcdc": ("MC/DC", "mcdc_pct")}
    measures = [(names[k][0], names[k][1], k) for k in ("line", "branch", "mcdc") if k in sc]
    return {"purpose": p, "measures": measures, "mcdc": "mcdc" in sc, "quality": sc, "source": src}


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
    """{'status': PASS|FAIL, 'target_met': bool, 'purpose', 'rows': [{measure, key, value, target, minimum, status}],
    'findings': [...], 'shortfall': [...]}. FAIL only below a MINIMUM; below the target is reported (shortfall).
    `cov`: an llvm_coverage result (default: the latest recorded one)."""
    from ..quality import judge
    from ..release.finalize import latest, tool_results

    req = required(ws)
    findings, rows, shortfall = [], [], []
    if cov is None:
        res = tool_results(Path(ws))
        rec = latest(res, "forge-tests-mcp", "llvm_coverage")
        run = latest(res, "forge-tests-mcp", "run_unit")
        cov = rec["result"] if rec else None
        if rec and run and rec.get("ts_utc", "") < run.get("ts_utc", ""):
            findings.append("COVERAGE_GATE:STALE (the latest llvm_coverage is older than the latest run_unit)")
    if not cov or cov.get("status") != "PASS":
        findings.append(f"COVERAGE_GATE:NOT_MEASURED (llvm_coverage {cov.get('status') if cov else 'NOT_RUN'})")
        return {"status": "FAIL", "target_met": False, "purpose": req["purpose"], "rows": rows, "findings": findings,
                "shortfall": shortfall, "source": req["source"]}
    m = _scope_keys(cov.get("metrics") or {})
    for label, key, qk in req["measures"]:
        v, pair = m.get(key), req["quality"][qk]
        st = judge(v, pair)
        rows.append({"measure": label, "key": qk, "value": v, "target": pair["target"], "minimum": pair["minimum"],
                     "status": st})
        name = label.replace("/", "").upper()
        if st == "BELOW_MINIMUM":
            findings.append(f"COVERAGE_GATE:{name}_BELOW_MINIMUM:{v}% (minimum {pair['minimum']}%, target "
                            f"{pair['target']}%, purpose {req['purpose']}: blocking)")
        elif st == "BELOW_TARGET":
            shortfall.append(f"COVERAGE_BELOW_TARGET:{name}:{v}% (target {pair['target']}%, minimum "
                             f"{pair['minimum']}% met)")
    if not req["mcdc"]:
        rows.append({"measure": "MC/DC", "key": "mcdc", "value": m.get("mcdc_pct"), "target": None, "minimum": None,
                     "status": "REPORTED (not required by this order)"})
    met = not findings and not shortfall
    return {"status": "FAIL" if findings else "PASS", "target_met": met, "purpose": req["purpose"], "rows": rows,
            "findings": findings, "shortfall": shortfall, "source": req["source"]}


def findings(ws: Path) -> list[str]:
    """Author-gate findings (empty for work orders without unit_verification)."""
    if not enabled(ws):
        return []
    try:
        return evaluate(ws)["findings"]
    except ValueError as exc:
        return [str(exc)]


def report_lines(ev: dict) -> list[str]:
    out = [f"Coverage gate (owner 2026-11-03, purpose {ev['purpose']}, quality {ev.get('source', 'defaults')}): the "
           "line works toward the target; the gate fails only below the order's minimum; a measure llvm-cov does not "
           "count (no branch points or decisions) is not applicable.", ""]
    for r in ev["rows"]:
        v = "n/a" if r["value"] is None else f"{r['value']}%"
        lim = "" if r["target"] is None else f" (target {r['target']}%, minimum {r['minimum']}%)"
        out.append(f"- {r['measure']}: {v}{lim} - {r['status']}")
    out.append(f"- gate: {ev['status']}" + ("" if ev.get("target_met") else " - target NOT met (see Quality achieved "
                                                                           "vs target)"))
    return out
