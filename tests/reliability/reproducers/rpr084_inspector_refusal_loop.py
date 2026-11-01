"""RPR-084 (Fabro SWE.1 run WO-F014-SWE1-IWDG-20261101-02 on Omniverse2, 2026-11-01): the structured inspector refused
the frozen SWE.1 baseline before any model call (SOURCE_TOO_LARGE on a cited input) and recorded nothing; the route
re-inspected the unchanged baseline 166 times in 4 minutes until Fabro ended the run.

Scenario: the IWDG LL work order with a frozen, valid, never-inspected SWE.1 baseline; every inspector visit refuses
its sources (calls 0, same issue). Symptom: after five identical refusals the route gate still says REINSPECT."""
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


SIG = "an inspector refusal that repeats with zero model calls is re-inspected without bound"


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        os.environ["FORGE_STATE_DIR"] = str(root / "state")
        os.environ["FORGE_EVENTS_DIR"] = str(root / "state/events")
        ws = _iwdg(root, "WO-RPR084")
        from forge_factory.inspection.engine import Store
        from forge_factory.lrtx import review
        req = ws / "workproducts/SWE.1/software_requirements.md"
        req.parent.mkdir(parents=True, exist_ok=True)
        req.write_text("# Software requirements\n\n- **SWR-001** The IWDG driver shall write IWDG_KR.KEY.\n")
        st = Store(ws)
        st.freeze("SWE.1", "swe1-author")
        if st.gate("SWE.1")["decision"] != "REINSPECT":
            print("REPRODUCER_ERROR:SCENARIO_NOT_REACHED:the frozen baseline is not awaiting inspection")
            return 2
        review.source_char_limit = lambda _ws: 10
        for _ in range(5):
            rep = review.visit(ws, "SWE.1", "fixture")
            if rep["status"] != "FAILED" or not rep["issues"][0].startswith("SOURCE_TOO_LARGE:"):
                print("REPRODUCER_ERROR:SCENARIO_NOT_REACHED:the inspector did not refuse its sources")
                return 2
        g = Store(ws).gate("SWE.1")
    if g["decision"] == "REINSPECT":
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
