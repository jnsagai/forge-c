"""RPR-002 (r73): the fix author changed nothing, the gate re-froze the same baseline and the defect became FIXED.
Fixed by dabdbe3 (DEFECT_NOT_ADDRESSED)."""
import json
import sys
import tempfile
from pathlib import Path

SIG = "author gate froze an unchanged baseline while a defect was IN_FIX"


def main() -> int:
    from forge_factory.inspection import defects as D
    from forge_factory.inspection import gate as G
    from forge_factory.inspection.engine import Store

    ws = Path(tempfile.mkdtemp(prefix="rpr002-"))
    (ws / "workproducts/SWE.1").mkdir(parents=True)
    (ws / "workproducts/SWE.1/software_requirements.md").write_text(
        "- **SWR-014** If a parameter is invalid, then the RCC driver shall return HAL_ERROR without any register write.\n")
    f = "software/tests/software/scn_invalid_param.c"
    (ws / f).parent.mkdir(parents=True)
    (ws / f).write_text("/* SWR-014 */\n")
    (ws / "evidence").mkdir()
    (ws / "evidence/tool-results.jsonl").write_text(json.dumps({
        "ts_utc": "2026-10-16T03:15:00Z", "phase": "SWE.6", "op": "run_robot", "server": "forge-tests-mcp",
        "result": {"status": "FAIL", "issues": [], "summary": "robot"}}) + "\n")
    D.report(ws, detected_phase="SWE.6", reported_by="swe6-author", kind="CODE", summary="no parameter validation",
             requirement_ids=["SWR-014"], test_files=[f], evidence_refs=[],
             requirement_quote="shall return HAL_ERROR without any register write")
    bl = {"baseline_id": "BL-SWE.3-002", "frozen_at": "2026-10-16T03:18:56Z", "baseline_hash": "H", "files": {},
          "upstream": {}}
    Store.latest_baseline = lambda self, p: bl
    Store.current_hash = lambda self, p: "H"
    Store.missing_outputs = lambda self, p: []
    Store.freeze = lambda self, p, role: bl
    Store.stale_reason = lambda self, p, b: None
    D.take_upstream(ws, "SWE.3")  # IN_FIX after the baseline was frozen
    rc = G.step_author(Store(ws), "SWE.3", '{"status":"PASS","artifacts":[],"issues":[],"next_action":"next"}')
    if rc == 0:
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
