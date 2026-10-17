"""RPR-001 (r72): a TEST declaration did not cover later corrections of the same file on unchanged code, so a
passing suite was rejected as TEST_CHANGED_AFTER_FAIL. Fixed by 211d4fc (ADR-0008 L14)."""
import json
import sys
import tempfile
from pathlib import Path

SIG = "TEST_CHANGED_AFTER_FAIL after a declaration on unchanged code"


def main() -> int:
    from forge_factory.inspection import defects as D

    ws = Path(tempfile.mkdtemp(prefix="rpr001-"))
    (ws / "workproducts/SWE.1").mkdir(parents=True)
    (ws / "workproducts/SWE.1/software_requirements.md").write_text(
        "- **SWR-014** If a parameter is invalid, then the RCC driver shall return HAL_ERROR without any register write.\n")
    f = "software/tests/software/scn_invalid_param.c"
    (ws / f).parent.mkdir(parents=True)
    (ws / f).write_text("/* SWR-014 */\n")
    (ws / "software/hal").mkdir(parents=True)
    (ws / "software/hal/x.c").write_text("int x;\n")
    code = D.code_hash(ws)

    def run(status, ts, h, failed):
        p = ws / D.INTEGRITY_LOG
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a") as fh:
            fh.write(json.dumps({"ts_utc": ts, "phase": "SWE.6", "op": "run_robot", "status": status, "code_sha": code,
                                 "files": {f: h}, "assert_failed": failed}) + "\n")

    run("FAIL", "2026-10-15T10:00:00Z", "h1", [f])
    D.report(ws, detected_phase="SWE.6", reported_by="swe6-author", kind="TEST", summary="scenario drove a timeout",
             requirement_ids=["SWR-014"], test_files=[f], evidence_refs=[],
             requirement_quote="shall return HAL_ERROR without any register write")
    run("FAIL", D.utc_now(), "h2", [f])
    run("PASS", D.utc_now(), "h3", [])
    if D.bent_tests(ws, "SWE.6"):
        print(f"SYMPTOM_PRESENT:{SIG}")
        return 1
    print("SYMPTOM_ABSENT")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001 - API drift is reported, never counted as a reproduction
        print(f"REPRODUCER_ERROR:{type(exc).__name__}:{str(exc)[:160]}")
        sys.exit(2)
