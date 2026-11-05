"""RPR-094 (Fabro run WO-F014-SWE4-OBL-20261101-L2, Omniverse2, 2026-11-01): CRC IDR greenfield SWE.4 resumed from
WO-F014-SWE3-OBL-20261101-L2. The straight-line LL functions have no branch points; llvm-cov reported branch None%
(mcp/servers/tests.py: no percentage when the count is 0). The deterministic SWE.4 report stated the goal '100%
statement/branch' next to 'branch None%' and recorded no finding; the inspector failed SWE4-05 (goal neither met nor
deviated). No test rework can change the generated report.

Scenario: the real swe4.visit_report with the recorded llvm_coverage metrics of that run (run_unit, validate_trace and the
file write are stubbed: not part of the symptom). Symptom: the report states no applicability for the undefined branch
percentage."""
import sys
import tempfile
from pathlib import Path

SIG = "the SWE.4 report states a branch coverage goal for code without branch points and no applicability"
COV = {"status": "PASS", "summary": "line 100.0% branch None% MC/DC None% (host)", "issues": [],
       "metrics": {"branch_pct": None, "environment": "host", "function_pct": 100.0, "line_pct": 100.0, "mcdc_pct": None,
                   "region_pct": 100.0, "target_evidence": False}}


def main() -> int:
    from forge_factory.lrtx import swe4, tools
    out = {}
    swe4.cases = lambda _ws: []
    tools.call = lambda _ws, _srv, op, *_a, **_k: COV if op == "llvm_coverage" else {"status": "PASS", "summary": "ok",
                                                                                        "issues": []}
    swe4.V.write_scoped = lambda _ws, files, *_a, **_k: out.update(files)
    swe4.V.reply = lambda *_a, **_k: {}
    with tempfile.TemporaryDirectory() as td:
        ws = Path(td)
        (ws / "evidence").mkdir()
        (ws / "evidence/tool-results.jsonl").write_text("")
        swe4.visit_report(ws)
    md = out.get("workproducts/SWE.4/unit_verification_report.md", "")
    if "## Coverage" not in md:
        print("REPRODUCER_ERROR:SCENARIO_NOT_REACHED:no coverage section rendered")
        return 2
    cov = md.split("## Coverage", 1)[1].split("## Results", 1)[0]
    if "branch: not applicable" in cov:
        print("SYMPTOM_ABSENT")
        return 0
    print(f"SYMPTOM_PRESENT:{SIG}")
    return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"REPRODUCER_ERROR:{type(exc).__name__}:{str(exc)[:160]}")
        sys.exit(2)
