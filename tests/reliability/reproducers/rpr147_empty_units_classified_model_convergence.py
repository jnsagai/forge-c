"""RPR-147: mirror CRC HAL L27's repeated UNIT:NO_UNITS deterministic rejection through the real line classifier.
Synthetic manifests/gate logs only, in a scratch directory. Other unit findings, mixed missing outputs and a mere
exhausted rework budget remain model convergence; a root cause is only suspected, never asserted as verified.
"""
import json
import os
from pathlib import Path
import sys
import tempfile

SIG = "a repeated deterministic empty-unit inventory is routed to another model retry instead of factory diagnosis"


def issue(root, tag, codes, stuck=True):
    from forge_factory.afo import line_conductor as LC

    wo = f"WO-F014-SWE3-{tag}-20261103-L27"
    ws = root / "workorders" / wo / "workspace"
    p = ws / ".forge-run/gates"
    p.mkdir(parents=True)
    (p.parent / "manifest.json").write_text(json.dumps({"work_order": wo, "created_at": "2026-11-03T12:00:00Z",
        "driver": "synthetic CRC HAL", "phase_scope": {"stop_after": "SWE.3"}, "factory_revision": {"commit": "fixture"}}))
    (p.parent / "package.json").write_text('{"package_status":"BLOCKED"}')
    reason = "STUCK: identical deterministic rejection twice; stopped early" if stuck else "rework budget exhausted"
    log = [{"phase": "SWE.3", "step": "author", "result": "REJECTED", "status": "INCOMPLETE", "issues": codes},
           {"phase": "SWE.3", "step": "author", "result": "REJECTED", "status": "INCOMPLETE", "issues": codes},
           {"phase": "SWE.3", "step": "route", "gate": {"decision": "BLOCKED", "reason": reason}}]
    (p / "gate-log.jsonl").write_text("".join(json.dumps({"ts": "2026-11-03T12:01:00Z", **r}) + "\n" for r in log))
    return LC.classify_order(LC.order_rec(ws), "failed", {})


def main():
    with tempfile.TemporaryDirectory(prefix="forge-rpr147-") as td:
        root = Path(td)
        os.environ["FORGE_STATE_DIR"] = str(root)
        for tag, codes, stuck in (("CONTROL1", ["UNIT:SPEC_TODO:USPEC-HAL-01-01"], True),
                                  ("CONTROL2", ["UNIT:NO_UNITS", "MISSING_REQUIRED_OUTPUT:unit_specifications.md"], True),
                                  ("CONTROL3", ["UNIT:NO_UNITS"], False)):
            result = issue(root, tag, codes, stuck)
            if result is None or result["class"] != "MODEL_CONVERGENCE":
                print("REPRODUCER_ERROR:CONTROL_CHANGED:" + tag)
                return 2
        result = issue(root, "CRCHAL", ["UNIT:NO_UNITS"])
        if result is None:
            print("REPRODUCER_ERROR:SCENARIO_NOT_REACHED")
            return 2
        if result["class"] == "MODEL_CONVERGENCE":
            print("SYMPTOM_PRESENT:" + SIG)
            return 1
        if result["class"] != "FACTORY_DEFECT" or result["status"] != "WAITING_EXTERNAL_CHANGE" or not result.get("suspected"):
            print("REPRODUCER_ERROR:UNEXPECTED_CLASSIFICATION")
            return 2
        print("SYMPTOM_ABSENT")
        return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print("REPRODUCER_ERROR:" + type(exc).__name__ + ":" + str(exc)[:160])
        sys.exit(2)
