"""RPR-109 (Fabro run WO-F014-CMP-SWE2-IWDG-20261102-03, cloud comparison line, 2026-11-02): IWDG LL structured SWE.2.
The rework router of the SWE.2 author visit sent every finding naming an SWR id to the interface task only. The
inspector's SWE2-06 finding on the design-owned 'Safety mechanisms, degraded states and dependencies' text (it called
the IWDG_PR field width/mask unresolved, citing SWR-005 as evidence) never reached the design task; the design
checkpoint was reused unchanged and SWE2-06 failed three times (BLOCKED STUCK SAME_ITEM_FAILED_3X).

Scenario: the real swe2._visit with the visit-3 rework findings of that run (shortened); the task runner answers with
scripted VALID documents and records which findings each task received (rendering, gates and writes are stubbed: not
part of the symptom). Symptom: the design task receives no finding on its Safety mechanisms text."""
import sys
import tempfile
from pathlib import Path

SIG = "a SWE.2 finding on a design-owned section citing an SWR id never reaches the design task"
FINDINGS = [
    "SWE2-06: Minor - workproducts/SWE.2/software_architecture.md, Requirement allocation table, SWR-012: states "
    "SWR-019/SWR-020 are outside the task requirement list, contradicting their inclusion in frozen SWE.1.",
    "SWE2-06: Minor - workproducts/SWE.2/software_architecture.md, Safety mechanisms, degraded states and dependencies: "
    "lists the PR field width and mask as undecidable, although its Interfaces and Register table fix bits 3:0 and "
    "mask 0xFU consistently with SWE.1 SWR-005.",
]


def main() -> int:
    from forge_factory.assurance import hardware
    from forge_factory.lrtx import structured as S
    from forge_factory.lrtx import swe2

    got: dict[str, list[str]] = {}

    def run_task(_ws, _phase, task, _build, _check, _budget, findings=None, max_repairs=2):
        got[task] = list(findings or [])
        return {"task": task, "status": "VALID", "doc": {"functions": [], "allocation": [], "calls": []}, "errors": []}

    hardware.index = lambda _p: {}
    swe2.V.run_task = run_task
    swe2.V.write_scoped = lambda *_a, **_k: None
    swe2.render = lambda *_a, **_k: {}
    swe2.self_check = lambda _ws: []
    swe2.reply = lambda _ws, status, issues, *_a, **_k: {"status": status, "issues": issues}
    S.record = lambda *_a, **_k: None
    with tempfile.TemporaryDirectory() as td:
        rep = swe2._visit(Path(td), "m", {"calls": 0, "max_calls": 8}, list(FINDINGS))
    if rep.get("status") != "PASS" or "design" not in got:
        print(f"REPRODUCER_ERROR:SCENARIO_NOT_REACHED:visit {rep.get('status')} tasks {sorted(got)}")
        return 2
    if any("Safety mechanisms" in f for f in got["design"]):
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
