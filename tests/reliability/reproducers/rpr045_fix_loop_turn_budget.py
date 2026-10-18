"""RPR-045 (r135/r136/r137): a SWE.3 visit that re-enters to fix an upstream CODE defect had the same turn budget as a
first pass although it must re-read context, fix code and re-validate specs, designs and trace; all three HAL fix
visits ended TURN_BUDGET_EXHAUSTED."""
import json
import sys
import tempfile
from pathlib import Path

SIG = "fix-loop visit has the first-pass turn budget"


def main() -> int:
    from forge_factory.policy import governor as GV

    with tempfile.TemporaryDirectory() as td:
        ws = Path(td) / "WO" / "workspace"
        (ws / ".forge-run/defects").mkdir(parents=True)
        first = GV.turn_limit("swe3-author", str(ws))
        (ws / ".forge-run/defects/DEF-001.json").write_text(json.dumps(
            {"id": "DEF-001", "status": "IN_FIX", "target_phase": "SWE.3", "kind": "CODE"}))
        loop = GV.turn_limit("swe3-author", str(ws))
    if loop <= first:
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
