"""RPR-082 (Fabro SWE.1 run WO-F014-SWE1-OBL-20261031-11 on Omniverse2, 2026-10-31): on an ASPICE-only work order the
allocated safety safe state is outside the owner scope (assessment context), yet the Qwen inspector failed SWE1-03
(major) because no safe state was specified; the one-repair policy then blocked SWE.1.

Scenario: the IWDG LL work order prepared as ASPICE_ONLY. Symptom: the SWE1-03 inspector notes do not tell the
inspector that the safe-state part is out of scope (and the baseline states nothing about it)."""
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path


def _iwdg(root, wo, purpose="DEVELOPMENT"):
    from forge_factory import workorder
    from forge_factory.common import REPO_ROOT
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
    ws, _m = workorder.prepare(ex, wo, purpose=purpose)
    return ws


SIG = "ASPICE-only SWE1-03 inspection is not told that the allocated safe state is outside the owner scope"


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        os.environ["FORGE_STATE_DIR"] = str(root / "state")
        os.environ["FORGE_EVENTS_DIR"] = str(root / "state/events")
        ws = _iwdg(root, "WO-RPR082", "ASPICE_ONLY")
        from forge_factory.inspection.assessment_context import view
        from forge_factory.lrtx import review
        v = view(json.loads((ws / ".forge-run/manifest.json").read_text())) or {}
        if "allocated safety safe state" not in (v.get("outside_owner_scope") or []):
            print("REPRODUCER_ERROR:SCENARIO_NOT_REACHED:not an ASPICE-only order with the safe state out of scope")
            return 2
        notes = " ".join(review._notes(ws, "SWE.1", "SWE1-03"))
    if "safe state" not in notes.lower():
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
