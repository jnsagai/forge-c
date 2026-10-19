"""RPR-004 (r75): the reporter extended the cited test file before its first post-fix run, so a correct fix could
never be VERIFIED (DEFECT_TEST_CHANGED). Fixed by 6d0c5de (gate re-verification from the test snapshot)."""
import json
import shutil
import sys
import tempfile
from pathlib import Path

SIG = "DEFECT_TEST_CHANGED for a correct fix whose cited test was only extended"
TEST = '#include <stdio.h>\nint drv(void);\nint main(void) { if (drv() == 1) { printf("UT-001 PASS\\n"); return 0; } ' \
       'printf("UT-001 FAIL\\n"); return 1; }\n'


def main() -> int:
    from forge_factory.common import sha256_file
    from forge_factory.inspection import defects as D

    ws = Path(tempfile.mkdtemp(prefix="rpr004-"))
    (ws / "workproducts/SWE.1").mkdir(parents=True)
    (ws / "workproducts/SWE.1/software_requirements.md").write_text(
        "- **SWR-014** If a parameter is invalid, then the RCC driver shall return HAL_ERROR without any register write.\n")
    (ws / "software/src").mkdir(parents=True)
    (ws / "software/src/drv.c").write_text("int drv(void) { return 1; }\n")
    rel = "software/tests/unit/test_drv.c"
    (ws / rel).parent.mkdir(parents=True)
    (ws / rel).write_text(TEST)
    snap = ws / ".forge-run/test-snapshots"
    snap.mkdir(parents=True)
    shutil.copyfile(ws / rel, snap / sha256_file(ws / rel))
    (ws / "evidence").mkdir()
    (ws / "evidence/tool-results.jsonl").write_text(json.dumps({
        "ts_utc": "2026-10-16T03:54:00Z", "phase": "SWE.4", "op": "run_unit", "server": "forge-tests-mcp",
        "result": {"status": "FAIL", "issues": ["TEST_FAIL:test_drv.c:exit1"], "summary": "unit"}}) + "\n")
    D.report(ws, detected_phase="SWE.4", reported_by="swe4-author", kind="CODE", summary="timeout bound rejected",
             requirement_ids=["SWR-014"], test_files=[rel], evidence_refs=[],
             requirement_quote="shall return HAL_ERROR without any register write")
    D.take_upstream(ws, "SWE.3")
    D.mark_fixed(ws, "SWE.3", "BL-SWE.3-003")
    with (ws / rel).open("a") as fh:
        fh.write("/* UT-059..: further tests added by the author */\n")
    issues = D.verify_on_freeze(ws, "SWE.4")
    if any(i.startswith("DEFECT_TEST_CHANGED") for i in issues):
        print(f"SYMPTOM_PRESENT:{SIG}")
        return 1
    if issues:
        print(f"REPRODUCER_ERROR:UNEXPECTED:{issues[0][:120]}")
        return 2
    print("SYMPTOM_ABSENT")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"REPRODUCER_ERROR:{type(exc).__name__}:{str(exc)[:160]}")
        sys.exit(2)
