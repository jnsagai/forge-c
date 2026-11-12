"""Owner 2026-11-02 ("the current local run show author cell in running tool checks, but the tool station is saying no
SWE.4 tool run yet"): a phase's task list is known only from its packets, so "every known task valid" does not mean the
author runs its tool checks. When the visit's last record says where the next node execution resumes, that task is
the current one and no tool check is claimed."""
import json
import time

from forge_factory.lrtx import progress_api as P


def _ws(tmp_path, resume_issue, ut8_status=None):
    ws = tmp_path / "WO-T/workspace"
    d = ws / ".forge-run/lrtx/SWE.4"
    (d / "packets").mkdir(parents=True)
    (ws / ".forge-run/manifest.json").write_text(json.dumps({"work_order": "WO-T"}))
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - 60))
    (d / "visit-state.json").write_text(json.dumps({"calls": 9, "continuations": 3, "open": True,
                                                   "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - 600))}))
    for n in range(1, 8):
        (d / f"packets/test__UT-00{n}.json").write_text(json.dumps({"task": f"test:UT-00{n}", "status": "VALID", "at": now}))
    if ut8_status:
        (d / "packets/test__UT-008.json").write_text(json.dumps({"task": "test:UT-008", "status": ut8_status, "at": now}))
    (d / "visits.jsonl").write_text(json.dumps({"at": now, "status": "CONTINUE", "issues": [resume_issue]}) + "\n")
    return ws


def test_between_time_boxes_the_resume_task_is_current_not_tool_checks(tmp_path):
    a = P.progress(_ws(tmp_path, "time box used; the next node execution resumes at test:UT-008"))["active"]
    assert a["current"] == "UT-008" and a["checking"] is False and a["total"] is None
    assert "running the tool checks" not in a["text"] and "now UT-008" in a["text"]


def test_a_resume_task_with_a_packet_counts_in_the_total(tmp_path):
    a = P.progress(_ws(tmp_path, "time box used; the next node execution resumes at test:UT-008", "INVALID"))["active"]
    assert a["current"] == "UT-008" and a["total"] == 8 and a["checking"] is False


def test_all_tasks_valid_without_a_resume_point_is_still_the_check_step(tmp_path):
    a = P.progress(_ws(tmp_path, "nothing to resume"))["active"]
    assert a["checking"] is True and "running the tool checks" in a["text"]
