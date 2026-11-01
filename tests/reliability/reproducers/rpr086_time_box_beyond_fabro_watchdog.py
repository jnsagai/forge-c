"""RPR-086 (Fabro SWE.1 run WO-F014-SWE1-RCC-20261101-02, 01M6AMZB126SW8SQY9CB4C80E1, Omniverse2, 2026-11-01): the RCC LL
SWE.1 author node ran 30 min (9 register tasks, Ornith thinking) without exiting; Fabro's stall watchdog ended the run
('node "swe1_author" had no activity for 1800s'). A command node reports activity only when it exits; the structured
time box (visit_time_s) is what makes it exit and continue, and the profile asked for 21600 s.

Scenario: the SWE.1 workflow built for the Ornith thinking profile. Symptom: the author node's time box is not below
Fabro's 1800 s stall watchdog."""
import os
import re
import sys

SIG = "the structured author node's time box is not below Fabro's 1800 s stall watchdog"


def main() -> int:
    os.environ["FORGE_LRTX_ROOT"] = "/reproducer/lrtx"
    from forge_factory.workflow.builder import build
    from forge_factory.workorder import local_profile_structured
    st = local_profile_structured({"id": "local-rtx-v2-omniverse2-ornith-think-author-q38-inspector"}, {"layer": "LL"},
                                  "qwen3.8:27b-q8_0")
    if not st or "SWE.1" not in st.get("phases", []):
        print("REPRODUCER_ERROR:SCENARIO_NOT_REACHED:the profile has no structured SWE.1 author")
        return 2
    dot, _nodes = build("WO-RPR086", layer="LL", trace=True, peripheral="crc", structured=st, stop_after="SWE.1")
    m = re.search(r"^  swe1_author \[.*?--time-budget (\d+)", dot, re.M)
    if m is None:
        print("REPRODUCER_ERROR:SCENARIO_NOT_REACHED:no structured swe1_author node with a time budget")
        return 2
    if int(m.group(1)) >= 1800:
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
