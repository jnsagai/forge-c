"""RPR-087 (Fabro run WO-F014-SWE2-IWDG-20261101-01, 01M6AHMG3GCVVHHNS2ZTM45NCE, Omniverse2, 2026-11-01): under the
high-allowance policy the SWE.1 inspector failed SWE1-04 (CPU constraint) five times with reworded findings; stuck
detection compares exact findings, so the route kept granting rework until the run was cancelled.

Scenario: the IWDG LL work order with the high-allowance policy and a frozen SWE.1 baseline; three recorded inspections
in a row fail SWE1-04 with different wording. Symptom: the route still grants another rework."""
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


SIG = "the same checklist item failing three inspections in a row with reworded findings is reworked again"


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        os.environ["FORGE_STATE_DIR"] = str(root / "state")
        os.environ["FORGE_EVENTS_DIR"] = str(root / "state/events")
        ws = _iwdg(root, "WO-RPR087", "ASPICE_ONLY")
        from forge_factory import development_execution as D
        from forge_factory.inspection import gate
        from forge_factory.inspection.engine import Store
        m = json.loads((ws / ".forge-run/manifest.json").read_text())
        m["development_execution"] = D.binding(D.HIGH, "ASPICE_ONLY")
        (ws / ".forge-run/manifest.json").write_text(json.dumps(m))
        req = ws / "workproducts/SWE.1/software_requirements.md"
        req.parent.mkdir(parents=True, exist_ok=True)
        req.write_text("# Software requirements\n\n- **SWR-001** The IWDG driver shall write IWDG_KR.KEY.\n")
        st = Store(ws)
        bl = st.freeze("SWE.1", "swe1-author")
        if D.selected(ws) is None or D.selected(ws)["name"] != D.HIGH:
            print("REPRODUCER_ERROR:SCENARIO_NOT_REACHED:the high-allowance policy is not selected")
            return 2
        d = ws / "inspection/SWE.1"
        d.mkdir(parents=True, exist_ok=True)
        for n in (1, 2, 3):
            rec = {"inspection_id": f"INS-SWE.1-{n:03d}", "baseline_id": bl["baseline_id"],
                   "baseline_hash": bl["baseline_hash"], "verdict": "FAIL", "recorded_at": f"9999-01-01T00:00:0{n}Z",
                   "items": {"SWE1-03": {"verdict": "PASS"}, "SWE1-04": {"verdict": "FAIL"}},
                   "findings": [{"item": "SWE1-04", "detail": f"CPU constraint missing (wording {n})"}]}
            (d / f"INS-SWE.1-{n:03d}.json").write_text(json.dumps(rec))
        code = gate.step_route(Store(ws), "SWE.1")
    if code == 0:
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
