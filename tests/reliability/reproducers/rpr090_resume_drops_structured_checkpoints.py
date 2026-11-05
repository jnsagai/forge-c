"""RPR-090 (Fabro runs WO-F014-SWE3-IWDG-20261101-01 and WO-F014-SWE3-OBL-20261101-01, Omniverse2, 2026-11-01): both
resumed a greenfield order whose structured SWE.1 and SWE.2 passed, to run SWE.3 only. The structured SWE.3 author
refused within seconds (LRTX_SWE3_NEEDS_STRUCTURED_SWE2_INTERFACE): the resume copied the frozen work products and the
gate records but not the validated SWE.2 interface checkpoint that structured SWE.3 reads.

Scenario: a source order whose SWE.1 and SWE.2 passed (their gates answer PASS) with a VALID structured SWE.2 interface
checkpoint, resumed by a new greenfield order through the real workorder.resume_from. Symptom: the new order has no
SWE.2 interface checkpoint."""
import json
import os
import sys
import tempfile
from pathlib import Path

SIG = "a greenfield resume does not carry the validated structured checkpoints of the passed phases"


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
        (src / "workproducts/SWE.2").mkdir(parents=True)
        (src / "workproducts/SWE.2/software_architecture.md").write_text("# Software architecture\n")
        pk = src / ".forge-run/lrtx/SWE.2/packets"
        pk.mkdir(parents=True)
        (pk / "interfaces.json").write_text(json.dumps({"task": "interfaces", "status": "VALID",
                                                         "doc": {"functions": [], "allocation": [], "calls": []}}))
        import subprocess
        for ws in (src, dst):  # work-order workspaces are git repositories (resume commits the carried state)
            subprocess.run(["git", "init", "-q"], cwd=ws, check=True)
            subprocess.run(["git", "-c", "user.email=r@x", "-c", "user.name=r", "commit", "-q", "--allow-empty", "-m", "init"],
                           cwd=ws, check=True)
        from forge_factory import workorder
        from forge_factory.inspection import engine
        engine.Store.gate = lambda self, ph: {"phase": ph, "decision": "PASS" if ph in ("SWE.1", "SWE.2") else "REWORK",
                                              "reason": "scenario", "failed_inspections": 0, "max_rework_cycles": 3}
        man = json.loads((dst / ".forge-run/manifest.json").read_text())
        remaining = workorder.resume_from(dst, man, "WO-SRC")
        if not remaining or remaining[0] != "SWE.3":
            print(f"REPRODUCER_ERROR:SCENARIO_NOT_REACHED:resume did not carry SWE.1-SWE.2 ({remaining})")
            return 2
        carried = (dst / ".forge-run/lrtx/SWE.2/packets/interfaces.json").is_file()
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
