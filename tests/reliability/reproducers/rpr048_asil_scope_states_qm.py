"""RPR-048 (r144-r152): with the owner scope SC-RCC-2026-10-18 (ASIL B) a prepared RCC work order still carried the
example's target.safety_allocation 'OUT_OF_SCOPE: QM development ...', so SWE.1 wrote 'QM development scope' into
ASIL B work products and no gate or pilot check noticed."""
import json
import os
import sys
import tempfile
from pathlib import Path

SIG = "ASIL scope work order states QM safety allocation"


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        os.environ["FORGE_STATE_DIR"] = str(Path(td) / "state")
        os.environ["FORGE_EVENTS_DIR"] = str(Path(td) / "state/events")
        from forge_factory import workorder
        from forge_factory.common import REPO_ROOT

        # the real example spec (target, scope, budgets) with one small input: the datasheets are not in git
        spec = json.loads((REPO_ROOT / "examples/0002a-arm_55_rcc_ll/workorder.json").read_text())
        ex = Path(td) / "examples/0002a-arm_55_rcc_ll"
        ex.mkdir(parents=True)
        (ex / "in.md").write_text("# input\n")
        spec["inputs"] = [{"path": "in.md", "role": "datasheet"}]
        (ex / "workorder.json").write_text(json.dumps(spec))
        workorder.REPO_ROOT = Path(td)  # inputs must lie under the root; the owner scope still comes from the repo
        ws, man = workorder.prepare(ex, "WO-RPR048")
        alloc = str(man["target"].get("safety_allocation", ""))
        sc = json.loads((ws / ".forge-run/safety_scope.json").read_text())["scope"]
    if sc["target_asil"] in ("A", "B", "C", "D") and ("QM" in alloc or "OUT_OF_SCOPE" in alloc):
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
