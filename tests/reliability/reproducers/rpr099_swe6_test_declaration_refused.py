"""RPR-099 (Fabro run WO-F014-SWE6-OBL-20261101-L5, Omniverse2, 2026-11-01): CRC IDR greenfield SWE.6 resumed from
WO-F014-SWE5-OBL-20261101-L4. The startup scenario failed on target; the triage answered test_wrong with corrected
programs, but the TEST declaration passed the model's reason as the requirement quote and was refused
(REQUIREMENT_QUOTE_REQUIRED). The corrected scenario later passed 10/10 as an undeclared test change and the route
stopped the order STUCK.

Scenario: a SWE.6 visit whose run_robot fails for SWR-003 and whose triage answers test_wrong, through the real
swe6._visit_tests triage and the real defects.report (scenario authoring, file writes and the Robot run are stubbed:
not part of the symptom). Symptom: the TEST declaration is refused."""
import json
import os
import sys
import tempfile
from pathlib import Path

SIG = "a SWE.6 test_wrong triage declaration is refused because its requirement quote is the model's reason"
REQ = "While no LL function has been called after reset, the CRC LL driver shall not write any CRC register."


def main() -> int:
    from forge_factory.lrtx import structured as S
    from forge_factory.lrtx import swe6, tools
    with tempfile.TemporaryDirectory() as td:
        ws = Path(td) / "WO-RPR099/workspace"
        os.environ["FORGE_STATE_DIR"] = str(Path(td) / "state")
        (ws / ".forge-run").mkdir(parents=True)
        (ws / ".forge-run/manifest.json").write_text(json.dumps({"work_order": "WO-RPR099", "layer": "LL",
                                                                 "peripheral": "crc"}))
        (ws / "workproducts/SWE.1").mkdir(parents=True)
        (ws / "workproducts/SWE.1/software_requirements.md").write_text(f"# Software requirements\n\n- **SWR-003** {REQ}\n")
        scn = ws / "software/tests/software/scn_startup.c"
        scn.parent.mkdir(parents=True)
        scn.write_text("/* scenario */\n")
        doc = {"default_code": "int main(void){return 0;}", "never_ready_code": "", "never_ready_swrs": []}
        swe6.plan = lambda _ws: {"topics": {"startup": ["SWR-003"]}}
        swe6.scn_files = lambda topic: ("software/tests/software/scn_startup.c", "software/tests/software/scn_startup_nr.c")
        swe6._context = lambda _ws, _swrs: []
        swe6._write = lambda *_a: None
        swe6.validate_scenarios = lambda *_a: []
        swe6.V.run_task = lambda _ws, _ph, task, *_a, **_k: {"task": task, "status": "VALID", "doc": doc, "errors": []}
        swe6.V.reply = lambda _ws, _ph, status, issues, *_a, **_k: {"status": status, "issues": issues}
        swe6.V._ckpt = lambda _ws, _ph, task: Path(td) / f"{task.replace(':', '_')}.json"
        seen = {}
        S.record = lambda _ws, rel, data: seen.update({rel: data})
        S.call = lambda *_a, **_k: {"errors": [], "doc": {"verdict": "test_wrong", "reason": "the check compared CRC_POL "
                                    "at the wrong offset; the model keeps CRC_POL at 0x014", "code": "", **doc}}
        S.packet = lambda **k: k
        runs = iter([{"status": "FAIL", "summary": "robot: 0/1", "issues": [
            "ROBOT_FAIL:SWR-003:check 3 failed in scn_startup.c [default]"]}])
        tools.call = lambda *_a, **_k: next(runs, {"status": "PASS", "summary": "robot: 1/1", "issues": []})
        swe6._visit_tests(ws, "m", {"calls": 0, "max_calls": 10, "log": []}, [])
        filed = (seen.get("SWE.6/tests-assembly.json") or {}).get("defects")
        decl = list((ws / ".forge-run/defects").glob("DEF-*.json")) if (ws / ".forge-run/defects").is_dir() else []
    if filed is None:
        print("REPRODUCER_ERROR:SCENARIO_NOT_REACHED:the triage did not run")
        return 2
    if any("REQUIREMENT_QUOTE_REQUIRED" in str(x) for x in filed) or not decl:
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
