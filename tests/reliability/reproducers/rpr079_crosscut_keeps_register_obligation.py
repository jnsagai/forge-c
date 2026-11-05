"""RPR-079 (Fabro SWE.1 run WO-F014-SWE1-OBL-20261031-04 on Omniverse2, 2026-10-31, Ornith author): the cross-cutting
answer repeated the CRC_IDR register requirements (write/read IDR, with register effects) citing their owner
obligations; since CAPA-079 the validator answered "keep [k] for owner obligation(s) ... but remove its effects", so the
author kept requirements that belong to the register task, and the one development repair pass ran out.

Scenario: IWDG LL work order with an obligation that has register effects (OBL-start-key: IWDG_KR.KEY write); a
cross-cutting answer contains a register requirement citing it. Symptom: the cross-cutting validator tells the author
to KEEP a requirement for an obligation with register effects."""
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

SIG = "cross-cutting validator tells the author to keep a register requirement for an obligation with register effects"
SYS = "IWDG LL driver"
OBL = {"schema": "forge-c/owner-obligations/1", "status": "DRAFT_FOR_OWNER_REVIEW", "owner": "rpr079",
       "source_inputs": [], "obligations": [
           {"id": "OBL-start-key", "statement": "Enable starts the watchdog by writing the start key.",
            "critical": True, "effects": [{"register": "IWDG_KR", "field": "KEY", "op": "write"}]}]}


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
            else:  # the git-ignored datasheet: SWE.1 reads the RM chapter only
                dst.write_text("# datasheet (reproducer stub)\n")
        shutil.copytree(REPO_ROOT / "examples/0009a-iwdg-ll/upstream", ex / "upstream")
        (ex / "workorder.json").write_text(json.dumps(spec))
        workorder.REPO_ROOT = root
        ws, _m = workorder.prepare(ex, "WO-RPR079")
        p = ws / "inputs/owner-obligations.json"
        p.write_text(json.dumps(OBL, indent=1))
        mp = ws / ".forge-run/manifest.json"
        man = json.loads(mp.read_text())
        man["inputs"].append({"path": "inputs/owner-obligations.json", "role": "owner_obligations",
                              "sha256": sha256_file(p), "bytes": p.stat().st_size})
        mp.write_text(json.dumps(man, indent=1))
        req = {"key": "start_again", "source_page": 2989, "verified_by": "host_unit_test",
               "obligations": ["OBL-start-key"], "verification": "Host unit test passes when IWDG_KR.KEY holds 0xCCCC.",
               "statement": f"When LL_IWDG_Enable is called, the {SYS} shall write 0x0000CCCC to IWDG_KR.KEY.",
               "effects": [{"case": "START2", "register": "IWDG_KR", "field": "KEY", "op": "write", "value": "0xCCCC"}]}
        startup = {"key": "startup", "source_page": 2989, "verified_by": "target_robot_test", "effects": [],
                   "obligations": [], "verification": "Robot target test passes when no register write is observed.",
                   "statement": f"While no LL function has been called after reset, the {SYS} shall not write any "
                                "IWDG register."}
        doc = {"requirements": [startup, req], "not_covered": [], "open_points": [], "obligation_gaps": []}
        out = swe1.validate_group(ws, doc, None, swe1.system_name(ws), index(ws / "inputs/sections/RM0486"))
    mine = [f for f in out if f.startswith("[start_again]")]
    if not mine:
        print("REPRODUCER_ERROR:SCENARIO_NOT_REACHED:no finding for the register requirement")
        return 2
    if any("keep [start_again]" in f for f in mine):
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
