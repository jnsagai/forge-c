"""RPR-093 (Fabro run WO-F014-SWE4-IWDG-20261101-L1, Omniverse2, 2026-11-01): the SWE.4 inspector failed SWE4-04
(cppcheck MISRA-10.6/12.1 in the frozen SWE.3 LL header without review or deviation record). The rework routed that
finding, which names no UT id, to every SWE.4 test task; the test tasks cannot change SWE.3 code, so the visit spent
~1.5 h of repair calls (VISIT_CALL_BUDGET_EXHAUSTED) without effect until the order was cancelled.

Scenario: a SWE.4 test visit with two test tasks and one SWE4-04 rework finding, through the real swe4._visit_tests
routing (task execution, file writes and run_unit are stubbed: they are not part of the symptom). Symptom: a test task
receives the SWE4-04 finding."""
import sys
import tempfile
from pathlib import Path

SIG = "a SWE4-04 static-analysis finding on the SWE.3 code is routed to the SWE.4 test tasks"
FINDING = "SWE4-04: cppcheck FAIL MISRA-10.6 at stm32n6xx_ll_iwdg.h:135 has no review or deviation record"


def main() -> int:
    from forge_factory.lrtx import structured as S
    from forge_factory.lrtx import swe4, tools
    got = {}
    unit = {"id": "SWU-LL-01", "swrs": ["SWR-001", "SWR-002"], "function": {"name": "LL_X", "params": []}}
    swe4.cases = lambda _ws: [{"ut": u, "swr": s, "statement": "", "effects": [], "unit": unit}
                              for u, s in (("UT-001", "SWR-001"), ("UT-002", "SWR-002"))]

    def run_task(_ws, _ph, task, _build, _check, _budget, findings=None):
        got[task] = list(findings or [])
        return {"task": task, "status": "VALID", "doc": {"code": "x", "kinds": ["positive"]}, "errors": []}

    swe4.V.run_task = run_task
    swe4.V.write_scoped = lambda *_a, **_k: None
    swe4.V.reply = lambda _ws, _ph, status, issues, *_a, **_k: {"status": status, "issues": issues}
    swe4._with_tests = lambda *_a: ""
    swe4._harness = lambda ws: Path(ws) / "software/tests/unit/test_x.c"
    S.record = lambda *_a, **_k: None
    tools.call = lambda *_a, **_k: {"status": "PASS", "issues": [], "summary": "2 passed"}
    with tempfile.TemporaryDirectory() as td:
        ws = Path(td)
        swe4._visit_tests(ws, "m", {"calls": 0, "max_calls": 10, "log": []}, [FINDING])
    if not got:
        print("REPRODUCER_ERROR:SCENARIO_NOT_REACHED:no SWE.4 test task ran")
        return 2
    if any(FINDING in f for f in got.values()):
        print(f"SYMPTOM_PRESENT:{SIG}")
        return 1
    print("SYMPTOM_ABSENT")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"REPRODUCER_ERROR:{type(exc).__name__}:{str(exc)[:160]}")
        sys.exit(2)
