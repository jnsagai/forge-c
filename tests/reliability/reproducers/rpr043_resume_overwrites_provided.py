"""RPR-043 (r132/r133): resuming a HAL work order copied the source's provided LL header over the new work order's own
read-only copy and failed with Permission denied before the run started."""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

SIG = "resume overwrites provided read-only file"


def main() -> int:
    from forge_factory.inspection.engine import Store, load_checklist
    from forge_factory.workorder import resume_from

    with tempfile.TemporaryDirectory() as td:
        os.environ["FORGE_STATE_DIR"], os.environ["FORGE_EVENTS_DIR"] = str(Path(td) / "state"), str(Path(td) / "ev")
        src = Path(td) / "state/workorders/WO-SRC/workspace"
        for rel, txt in {"workproducts/SWE.1/software_requirements.md":
                         "- **SWR-001** When enable is requested, the RCC driver shall set the clock enable bit.\n",
                         "traceability/requirements_to_tests.csv": "requirement_id,test_id,test_file\nSWR-001,UT-001,t.c\n",
                         "traceability/provided_ll.h": "#define LL 1\n",
                         "configuration/system_names.json": json.dumps(["RCC driver"])}.items():
            (src / rel).parent.mkdir(parents=True, exist_ok=True)
            (src / rel).write_text(txt)
        from forge_factory.inspection.reqif_export import export

        export(src)
        s = Store(src)
        try:
            bl = s.freeze("SWE.1", "swe1-author")
            s.record_inspection("SWE.1", "swe1-inspector", bl["baseline_id"],
                                {c["id"]: {"verdict": "PASS", "evidence_refs": ["x"]} for c in load_checklist("SWE.1")["checks"]})
        except Exception as exc:  # noqa: BLE001 - fixture could not make SWE.1 stable
            print(f"REPRODUCER_ERROR:FIXTURE:{type(exc).__name__}:{str(exc)[:100]}")
            return 2
        ws = Path(td) / "state/workorders/WO-NEW/workspace"
        (ws / "traceability").mkdir(parents=True)
        (ws / ".forge-run").mkdir(parents=True)
        subprocess.run(["git", "init", "-q"], cwd=ws, check=True)
        mine = ws / "traceability/provided_ll.h"
        mine.write_text("#define LL 1\n")
        mine.chmod(0o444)
        import hashlib

        man = {"work_order": "WO-NEW", "provided": [{"path": "traceability/provided_ll.h",
                                                    "sha256": hashlib.sha256(b"#define LL 1\n").hexdigest()}]}
        try:
            resume_from(ws, man, "WO-SRC")
        except (PermissionError, OSError) as exc:
            print(f"SYMPTOM_PRESENT:{SIG}")  # {type(exc).__name__} on stderr only
            print(type(exc).__name__, file=sys.stderr)
            return 1
    print("SYMPTOM_ABSENT")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"REPRODUCER_ERROR:{type(exc).__name__}:{str(exc)[:160]}")
        sys.exit(2)
