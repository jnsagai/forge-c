"""RPR-081 (Fabro SWE.1 run WO-F014-SWE1-OBL-20261031-06 on Omniverse2, 2026-10-31, Ornith author, high-allowance
policy): the cross-cutting listing showed each functional requirement as 'statement (obligations: ...)'; the author
copied that into its own statements, which then did not end with a period. The only finding was
'EARS_MISSING_TERMINATOR: end the statement with a period'; ten repairs kept the text and SWE.1 blocked.

Scenario: IWDG LL work order with declared obligations; a cross-cutting statement ends with '(obligations: ...)'.
Symptom: no finding tells the author to move the obligation ids out of the statement."""
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

SIG = "a statement carrying '(obligations: ...)' gets no finding that names the obligation text"
SYS = "IWDG LL driver"
OBL = {"schema": "forge-c/owner-obligations/1", "status": "DRAFT_FOR_OWNER_REVIEW", "owner": "rpr081",
       "source_inputs": [], "obligations": [
           {"id": "OBL-no-startup-writes", "statement": "Nothing is written before the first driver call.",
            "critical": True}]}


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        os.environ["FORGE_STATE_DIR"] = str(root / "state")
        os.environ["FORGE_EVENTS_DIR"] = str(root / "state/events")
        from forge_factory import workorder
        from forge_factory.assurance.hardware import index
        from forge_factory.common import REPO_ROOT, sha256_file
        from forge_factory.lrtx import swe1

        spec = json.loads((REPO_ROOT / "examples/0009a-iwdg-ll/workorder.json").read_text())
        ex = root / "examples/0009a-iwdg-ll"
        ex.mkdir(parents=True)
        for item in spec["inputs"]:
            src, dst = REPO_ROOT / "examples/0009a-iwdg-ll" / item["path"], ex / item["path"]
            dst.parent.mkdir(parents=True, exist_ok=True)
            if src.is_file() and item["role"] != "datasheet":
                shutil.copyfile(src, dst)
            else:
                dst.write_text("# datasheet (reproducer stub)\n")
        shutil.copytree(REPO_ROOT / "examples/0009a-iwdg-ll/upstream", ex / "upstream")
        (ex / "workorder.json").write_text(json.dumps(spec))
        workorder.REPO_ROOT = root
        ws, _m = workorder.prepare(ex, "WO-RPR081")
        p = ws / "inputs/owner-obligations.json"
        p.write_text(json.dumps(OBL, indent=1))
        mp = ws / ".forge-run/manifest.json"
        man = json.loads(mp.read_text())
        man["inputs"].append({"path": "inputs/owner-obligations.json", "role": "owner_obligations",
                              "sha256": sha256_file(p), "bytes": p.stat().st_size})
        mp.write_text(json.dumps(man, indent=1))
        req = {"key": "startup", "source_page": 2989, "verified_by": "target_robot_test", "effects": [],
               "obligations": ["OBL-no-startup-writes"], "verification": "Robot test passes when no write occurs.",
               "statement": f"While no LL function has been called after reset, the {SYS} shall not write any IWDG "
                            "register. (obligations: OBL-no-startup-writes)"}
        doc = {"requirements": [req], "not_covered": [], "open_points": [], "obligation_gaps": []}
        out = swe1.validate_group(ws, doc, None, swe1.system_name(ws), index(ws / "inputs/sections/RM0486"))
    mine = [f for f in out if f.startswith("[startup]")]
    if not mine:
        print("REPRODUCER_ERROR:SCENARIO_NOT_REACHED:no finding for the tagged statement")
        return 2
    if not any("obligation" in f.lower() for f in mine):
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
