"""RPR-083 (Fabro SWE.1 runs WO-F014-SWE1-OBL-20261031-06 and -08 on Omniverse2, 2026-10-31, Ornith author): the
cross-cutting repairs returned the same finding up to ten times in a row, spending the whole repair budget.

Scenario: the IWDG LL work order; a scripted author returns the same invalid answer to every repair. Symptom: more
than two calls are spent although the second answer already repeats the findings of the first."""
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


SIG = "a repair answer with the same findings keeps consuming repair calls"


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        os.environ["FORGE_STATE_DIR"] = str(root / "state")
        os.environ["FORGE_EVENTS_DIR"] = str(root / "state/events")
        ws = _iwdg(root, "WO-RPR083")
        from forge_factory.assurance.hardware import index
        from forge_factory.lrtx import structured as S
        from forge_factory.lrtx import swe1
        from forge_factory.lrtx import visit as V
        broken = {"requirements": [{"key": "x", "statement": "The IWDG driver should maybe write IWDG_KR.KEY",
                                    "source_page": 2989, "verified_by": "host_unit_test", "effects": [],
                                    "verification": "Host unit test passes when the field holds the value."}],
                  "not_covered": [], "open_points": []}
        calls = []

        def call(packet, **_):
            calls.append(packet["task"])
            return {"doc": json.loads(json.dumps(broken)), "errors": [], "usage": {"prompt_tokens": 1,
                    "completion_tokens": 1}, "wall_ms": 1.0, "finish_reason": "stop"}

        S.call = call
        g = swe1.groups(swe1.inventory(ws))[0]
        idx = index(ws / "inputs/sections/RM0486")
        rec = V.run_task(ws, "SWE.1", "requirements:" + g["id"],
                         lambda fi, pr: swe1.group_packet(ws, g, "fixture", fi, pr),
                         lambda d: swe1.validate_group(ws, d, g, swe1.system_name(ws), idx),
                         {"calls": 0, "max_calls": 40}, max_repairs=5)
    if rec["status"] == "VALID":
        print("REPRODUCER_ERROR:SCENARIO_NOT_REACHED:the broken answer validated")
        return 2
    if len(calls) > 2:
        print(f"SYMPTOM_PRESENT:{SIG} ({len(calls)} calls)")
        return 1
    print("SYMPTOM_ABSENT")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"REPRODUCER_ERROR:{type(exc).__name__}:{str(exc)[:160]}")
        sys.exit(2)
