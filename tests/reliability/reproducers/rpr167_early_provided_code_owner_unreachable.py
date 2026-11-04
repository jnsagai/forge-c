#!/usr/bin/env python3
"""Independent normal provided-LL CODE API oracle; no model, signature fixture, NSS or live state."""
import json
import os
import tempfile
from pathlib import Path

from forge_factory.common import pretty_json, sha256_bytes
from forge_factory.inspection import defects as D
from forge_factory.inspection import provided_changes as PC

LL = "software/ll/stm32n6xx_ll_wwdg.h"
QUOTE = "The driver shall preserve all reserved register bits at their reset values."


def workspace(root, name, enabled=True):
    ws = root / name / "workspace"
    raw = b"static inline void LL_Clear(void) { /* normal supplied implementation */ }\n"
    manifest = {"work_order": "WO-CONTROL-" + name, "layer": "HAL", "peripheral": "wwdg",
                "purpose": "ASPICE_ONLY", "provided": [{"path": LL, "role": "provided_ll_driver",
                "sha256": sha256_bytes(raw), "source_work_order": "WO-CONTROL-LL",
                "source_package": "READY_FOR_OFFLINE_REVIEW"}]}
    if enabled:
        manifest["unit_verification"] = "uspec-gtest-v1"
    files = {".forge-run/manifest.json": pretty_json(manifest), LL: raw.decode(),
             "workproducts/SWE.1/software_requirements.md": "- **SWR-034** " + QUOTE + "\n"}
    for rel, data in files.items():
        path = ws / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(data)
    PC.save_original(ws, LL, raw)
    return ws


def report(ws, phase, path=LL):
    return D.report(ws, detected_phase=phase, reported_by="swe" + phase[-1] + "-author", kind="CODE",
        summary="Supplied flag-clear implementation does not preserve reserved reset values.",
        requirement_ids=["SWR-034"], test_files=[], evidence_refs=[path + ":1"], requirement_quote=QUOTE)


def main():
    with tempfile.TemporaryDirectory(prefix="rpr167-") as temporary:
        root = Path(temporary)
        os.environ["FORGE_STATE_DIR"] = str(root / "state")
        os.environ["FORGE_EVENTS_DIR"] = str(root / "events")
        missing = []
        for phase in ("SWE.2", "SWE.3"):
            ws = workspace(root, phase.replace(".", ""))
            try:
                row = report(ws, phase)
            except D.DefectError as exc:
                if str(exc).startswith(("TARGET_NOT_UPSTREAM:", "SAME_PHASE_USE_REWORK:")):
                    missing.append(phase)
                    continue
                raise
            expected = "OPEN" if phase == "SWE.2" else "IN_FIX"
            if row.get("kind") != "CODE" or row.get("target_phase") != "SWE.3" or row.get("status") != expected:
                missing.append(phase)
            if phase == "SWE.2" and (D.open_from(ws, phase) or D.take_upstream(ws, "SWE.3") or D.loops_used(ws)):
                missing.append("FALSE_FORWARD_UPSTREAM")
            if row.get("kind") != "CODE" or not row.get("requirement_quote") == QUOTE:
                raise RuntimeError("NORMAL_DEFECT_BINDING_LOST")
        for name in ("disabled", "other", "original"):
            ws = workspace(root, "NEG" + name, enabled=name != "disabled")
            path = LL
            if name == "other":
                path = "software/hal/other.c"
                (ws / path).parent.mkdir(parents=True, exist_ok=True)
                (ws / path).write_text("int other(void) { return 0; }\n")
            if name == "original":
                (ws / PC.ORIGINALS / LL).unlink()
            try:
                report(ws, "SWE.2", path)
            except D.DefectError:
                pass
            else:
                raise RuntimeError("OUT_OF_SCOPE_CODE_ACCEPTED:" + name)
        if missing:
            print("SYMPTOM_PRESENT:normal early provided LL CODE is refused or routed as a forward upstream loop")
            return 1
        print("SYMPTOM_ABSENT")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
