"""RPR-102 (Fabro run WO-F014-SWE5-IWDG-20261101-L5, Omniverse2, 2026-11-02): IWDG LL greenfield SWE.5 resumed from
WO-F014-SWE4-IWDG-20261101-L5. The visit ended FAILED with the integration test's failures and the status note
'defect filed: DEF-001'; the note names no test file, so the next visit routed it to every SWE.5 file and re-authored
the passing target test (about 10 minutes and 77k tokens per call) until the order was cancelled.

Scenario: a SWE.5 visit carrying an integration-test failure and the note, through the real swe5._visit_tests routing
(task execution is stubbed and the visit stops after the tasks: not part of the symptom). Symptom: the target file's
task receives the note."""
import sys
import tempfile
from pathlib import Path

SIG = "a visit status note (defect filed) is routed to every SWE.5 test file as a repair finding"


def main() -> int:
    from forge_factory.lrtx import swe5
    got = {}
    swe5.files = lambda _ws: {"target": "software/tests/target/test_iwdg_target.c",
                              "integration": "software/tests/integration/test_iwdg_integration.c"}

    swe5.V.run_task = lambda _ws, _ph, task, _b, _c, _bud, findings=None: (got.update({task: list(findings or [])}) or
                                                                           {"task": task, "status": "INVALID",
                                                                            "errors": ["stop"], "doc": None})
    swe5.V.reply = lambda *_a, **_k: {"status": "FAILED"}
    with tempfile.TemporaryDirectory() as td:
        swe5._visit_tests(Path(td), "m", {"calls": 0, "max_calls": 5, "log": []},
                          ["run_integration: TEST_FAIL:test_iwdg_integration.c:exit1", "defect filed: DEF-001"])
    if "file:target" not in got:
        print("REPRODUCER_ERROR:SCENARIO_NOT_REACHED:no target task")
        return 2
    if any(f.startswith("defect filed:") for f in got["file:target"]):
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
