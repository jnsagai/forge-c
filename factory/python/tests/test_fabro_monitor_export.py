"""Export of work orders as queue records for the external fabro_dashboard monitor (evidence-derived only)."""
import json

from forge_factory.dashboard.fabro_monitor_export import export_all, export_workorder


def wo(tmp_path, name, rows, package=None):
    ws = tmp_path / "workorders" / name / "workspace"
    (ws / ".forge-run/gates").mkdir(parents=True)
    (ws / ".forge-run/fabro_run_id").write_text("RUN1\n")
    (ws / ".forge-run/gates/gate-log.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    if package:
        (ws / ".forge-run/package.json").write_text(json.dumps(package))
    return ws


PASS1 = {"phase": "SWE.1", "step": "inspect", "gate": {"decision": "PASS"}}
REWORK3 = {"phase": "SWE.3", "step": "route", "gate": {"decision": "REWORK", "reason": "NO_BASELINE"}}


def test_running_work_order_shows_phase_progress_not_agent_claims(tmp_path):
    ws = wo(tmp_path, "WO-A", [PASS1, {"phase": "SWE.2", "step": "inspect", "agent_status": "PASS",
                                       "gate": {"decision": "REWORK"}}])
    rec = export_workorder(ws, "RUNNING")
    st = {i["id"]: i["status"] for i in rec["items"]}
    assert st == {"SWE.1": "succeeded", "SWE.2": "running", "SWE.3": "pending", "SWE.4": "pending", "SWE.5": "pending",
                  "SWE.6": "pending", "package": "pending"}
    assert rec["status"] == "running" and rec["run_id"] == "RUN1" and "not a safety approval" in rec["notes"]
    assert json.loads((ws.parent / "dashboard/queue.json").read_text()) == rec


def test_blocked_and_governor_cancelled_runs(tmp_path):
    pkg = {"package_status": "BLOCKED", "gap_count": 35, "archive_sha256": "ab" * 32}
    blocked = export_workorder(wo(tmp_path, "WO-B", [PASS1, {"phase": "SWE.2", "step": "inspect", "gate": {"decision": "PASS"}},
                                                     REWORK3, {"phase": "SWE.3", "step": "route", "gate": {
                                                         "decision": "BLOCKED", "reason": "rework budget exhausted"}}], pkg))
    st = {i["id"]: i["status"] for i in blocked["items"]}
    assert st["SWE.3"] == "blocked" and st["SWE.4"] == "not_reached" and st["package"] == "blocked"
    assert blocked["status"] == "blocked" and "35 gaps" in blocked["notes"]
    gov = export_workorder(wo(tmp_path, "WO-C", [PASS1, {"step": "governor", "result": "TOKEN_BUDGET_EXHAUSTED"}], pkg))
    assert {i["id"]: i["status"] for i in gov["items"]}["SWE.2"] == "cancelled"


def test_export_all_skips_finished_exports(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path))
    wo(tmp_path, "WO-D", [PASS1], {"package_status": "READY_FOR_OFFLINE_REVIEW", "gap_count": 0})
    assert export_all() == 1 and export_all() == 0
