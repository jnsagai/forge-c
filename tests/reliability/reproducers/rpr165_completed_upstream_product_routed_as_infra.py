#!/usr/bin/env python3
"""Frozen independent normal Store/defect/native-snapshot reproducer; no real inference or signature fixture."""
import json
import os
import tempfile
import time
from pathlib import Path

from forge_factory.afo import line_conductor as L
from forge_factory.common import pretty_json, utc_now
from forge_factory.inspection import defects as D
from forge_factory.inspection.engine import Store


def records(root: Path):
    wo, rid = "WO-F014-CMP-SWE4-WWDGHAL-20261104-T1G", "RUN-COMPLETED-UPSTREAM"
    ws = root / "workorders" / wo / "workspace"
    files = {
        ".forge-run/manifest.json": json.dumps({"work_order": wo, "created_at": utc_now(),
            "driver": "Fixture WWDG HAL", "phase_scope": {"stop_after": "SWE.4"}}),
        "workproducts/SWE.1/software_requirements.md": "- **SWR-001** The driver shall preserve register state.\n",
        "workproducts/SWE.2/software_architecture.md": "# Architecture\nRegister state must be preserved.\n",
        "software/hal/driver.c": "int driver_state(void) { return 0; }\n",
    }
    for rel, value in files.items():
        path = ws / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value)
    store = Store(ws)
    for phase in ("SWE.1", "SWE.2", "SWE.3"):
        baseline = store.freeze(phase, f"swe{phase[-1]}-author")
    checklist = store.applicable(store.checklist("SWE.3"))
    inspection = store.record_inspection("SWE.3", "swe3-inspector", baseline["baseline_id"],
        {row["id"]: {"verdict": "FAIL", "findings": ["State preservation is not established."],
                     "evidence_refs": ["workproducts/SWE.2/software_architecture.md:1"]}
         for row in checklist["checks"]})
    defect = D.report(ws, detected_phase="SWE.3", reported_by="swe3-inspector", kind="ARCHITECTURE",
        summary="Architecture does not establish state preservation.", requirement_ids=["SWR-001"],
        test_files=[], evidence_refs=["workproducts/SWE.2/software_architecture.md:1"],
        requirement_quote="The driver shall preserve register state.")
    gate = store.gate("SWE.3")
    assert gate["decision"] == "REWORK" and gate["reason"] == inspection["inspection_id"]
    rows = [{"phase": "SWE.3", "step": "author", "result": "FROZEN"},
            {"phase": "SWE.3", "step": "inspect", "gate": gate},
            {"phase": "SWE.3", "step": "route", "gate": {"decision": "UPSTREAM", "phase": "SWE.3"}},
            {"phase": "SWE.2", "step": "upstream", "result": "NONE"}]
    path = ws / ".forge-run/gates/gate-log.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps({"ts": utc_now(), **row}) + "\n" for row in rows))
    (ws / ".forge-run/package.json").write_text(json.dumps({"package_status": "BLOCKED"}))
    (ws / ".forge-run/fabro_run_id").write_text(rid)
    run = {"id": rid, "source_directory": str(ws), "lifecycle": {"status": {"kind": "succeeded", "reason": "completed"}}}
    return ws, wo, rid, run, inspection, defect

def observed(value):
    ws, wo, rid, run, _, _ = value
    observer = L.Observer("cloud", fabro=L.FabroView(snapshot={rid: run}), lookback_s=86400)
    rows, _ = observer.issues(time.time(), frozenset({wo}))
    return next(row for row in rows if row["wo"] == wo)


def main():
    with tempfile.TemporaryDirectory(prefix="rpr165-") as temporary:
        root = Path(temporary)
        os.environ["FORGE_EVENTS_DIR"] = str(root / "events")
        outcomes = []
        for name in ("completed", "failed", "foreign", "stale", "closed"):
            state = root / name / "state"
            os.environ["FORGE_STATE_DIR"] = str(state)
            value = records(state)
            ws, _, _, run, _, defect = value
            if name == "failed":
                run["lifecycle"]["status"] = {"kind": "failed", "reason": "workflow_error"}
            elif name == "foreign":
                run["source_directory"] = str(ws.parent / "other")
            elif name == "stale":
                (ws / "software/hal/driver.c").write_text("int changed(void) { return 1; }\n")
            elif name == "closed":
                path = ws / D.DIR / (defect["id"] + ".json")
                doc = json.loads(path.read_text())
                doc["status"] = "REJECTED"
                path.write_text(pretty_json(doc))
            before = {p: p.read_bytes() for p in ws.rglob("*") if p.is_file()}
            result = observed(value)
            if any(p.read_bytes() != data for p, data in before.items()):
                print("ERROR:read_only_observer_changed_source")
                return 2
            if name != "completed" and result["class"] != "INFRA":
                print("ERROR:unsafe_product_override_control:" + name)
                return 2
            if name == "completed":
                correct = (result["class"] == "PRODUCT"
                           and result["proposals"][0]["strategy"] == "RETURN_TO_OWNING_UPSTREAM_PHASE"
                           and result["proposals"][0]["args"]["phase"] == "SWE.2")
                outcomes.append(correct)
        if not all(outcomes):
            print("SYMPTOM_PRESENT:completed native upstream product finding routed as infrastructure")
            return 1
        print("SYMPTOM_ABSENT")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
