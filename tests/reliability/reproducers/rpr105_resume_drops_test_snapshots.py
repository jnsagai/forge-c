"""RPR-105 (packages of Fabro runs WO-F014-SWE6-OBL-20261101-L6 and WO-F014-SWE6-IWDG-20261101-L6, Omniverse2,
2026-11-01/02): both greenfield lineages passed SWE.1-SWE.6 by resume, but their offline-review packages were BLOCKED
(TEST_HISTORY_INTEGRITY: TEST_SNAPSHOT_MISSING_OR_UNREADABLE): the resume carried evidence/test-integrity.jsonl but not
the content-addressed test snapshots it references.

Scenario: a source order whose SWE.1-SWE.4 passed, with a test-integrity record and its snapshot, resumed by a new
greenfield order through the real workorder.resume_from (the gate decision is stubbed). Symptom: the new order has the
integrity record but not the snapshot."""
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

SIG = "a greenfield resume carries the test-integrity log but not the test snapshots it references"


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        os.environ["FORGE_STATE_DIR"] = str(root / "state")
        os.environ["FORGE_EVENTS_DIR"] = str(root / "state/events")
        src = root / "state/workorders/WO-SRC/workspace"
        dst = root / "state/workorders/WO-DST/workspace"
        for ws, wo in ((src, "WO-SRC"), (dst, "WO-DST")):
            (ws / ".forge-run").mkdir(parents=True)
            (ws / ".forge-run/manifest.json").write_text(json.dumps({"work_order": wo, "layer": "LL"}))
        from forge_factory.inspection.defects import INTEGRITY_LOG, SNAPSHOTS
        body = b"static void ut_ut_001(void) { CHECK(\"UT-001\", 1); }\n"
        digest = hashlib.sha256(body).hexdigest()
        (src / SNAPSHOTS).mkdir(parents=True)
        (src / SNAPSHOTS / digest).write_bytes(body)
        (src / INTEGRITY_LOG).parent.mkdir(parents=True, exist_ok=True)
        (src / INTEGRITY_LOG).write_text(json.dumps({"op": "run_unit", "phase": "SWE.4",
                                                     "files": {"software/tests/unit/test_x.c": digest}}) + "\n")
        for ws in (src, dst):
            subprocess.run(["git", "init", "-q"], cwd=ws, check=True)
            subprocess.run(["git", "-c", "user.email=r@x", "-c", "user.name=r", "commit", "-q", "--allow-empty", "-m",
                            "init"], cwd=ws, check=True)
        from forge_factory import workorder
        from forge_factory.inspection import engine
        engine.Store.gate = lambda self, ph: {"phase": ph, "decision": "PASS" if ph in ("SWE.1", "SWE.2", "SWE.3", "SWE.4")
                                              else "REWORK", "reason": "scenario", "failed_inspections": 0,
                                              "max_rework_cycles": 3}
        man = json.loads((dst / ".forge-run/manifest.json").read_text())
        remaining = workorder.resume_from(dst, man, "WO-SRC")
        if not remaining or remaining[0] != "SWE.5" or not (dst / INTEGRITY_LOG).is_file():
            print(f"REPRODUCER_ERROR:SCENARIO_NOT_REACHED:{remaining}")
            return 2
        carried = (dst / SNAPSHOTS / digest).is_file()
    if carried:
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
