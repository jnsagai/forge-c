"""RPR-101 (Fabro run WO-F014-SWE4-IWDG-20261101-L4, Omniverse2, 2026-11-01): IWDG LL greenfield SWE.4 resumed from
WO-F014-SWE3-IWDG-20261101-L4. The generated SWE.4 report stated 'none declared: error' for every unit; the LL
accessors have no error behaviour, but the inspector read it as missing error tests and failed SWE4-02. No test rework
can change the generated report.

Scenario: the real swe4.visit_report for one unit whose test declares positive only (a void function without a value
whose requirement states no error behaviour); tool calls and the file write are stubbed (not part of the symptom).
Symptom: the report gives no applicability for the kinds without a test."""
import json
import sys
import tempfile
from pathlib import Path

SIG = "the SWE.4 report lists test kinds without a test and gives no applicability for them"


def main() -> int:
    from forge_factory.lrtx import swe4, tools
    unit = {"id": "SWU-LL-01", "swrs": ["SWR-001"], "function": {"name": "LL_IWDG_Enable", "returns": "void", "params": []}}
    swe4.cases = lambda _ws: [{"ut": "UT-001", "swr": "SWR-001", "unit": unit, "effects": [],
                               "statement": "The IWDG LL driver shall write 0x0000CCCC to IWDG_KR.KEY."}]
    swe4._declared_kinds = lambda _ws, _ut: ["positive"]
    tools.call = lambda *_a, **_k: {"status": "PASS", "summary": "ok", "issues": [], "metrics": {"line_pct": 100.0}}
    out = {}
    swe4.V.write_scoped = lambda _ws, files, *_a, **_k: out.update(files)
    swe4.V.reply = lambda *_a, **_k: {}
    with tempfile.TemporaryDirectory() as td:
        ws = Path(td)
        (ws / "evidence").mkdir()
        (ws / "evidence/tool-results.jsonl").write_text("")
        swe4.visit_report(ws)
    md = out.get("workproducts/SWE.4/unit_verification_report.md", "")
    if "## Test design per unit" not in md:
        print("REPRODUCER_ERROR:SCENARIO_NOT_REACHED:no test design section")
        return 2
    sec = md.split("## Test design per unit", 1)[1].split("## ", 1)[0]
    if "error: not applicable" in sec and "boundary: not applicable" in sec and "negative: NOT COVERED" in sec:
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
