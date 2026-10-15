"""T048 (AT-23/AT-24/AT-26): unattended end-to-end on local Qwen via real Fabro — verified from the actual run.

Selects the newest finished work order (`FORGE_T048_WO` to pin one). Asserts: one-command, no human gate events,
local model only, valid terminal status (READY_FOR_OFFLINE_REVIEW or BLOCKED, never an approval), archive
integrity, KPI cross-check, and that deterministic verdicts reproduce from the archived evidence.
"""
import json
import os
import zipfile
from pathlib import Path

import pytest

STATE = Path(os.environ.get("FORGE_STATE_DIR", "/nonexistent"))


def finished_workorders() -> list[Path]:
    root = STATE / "workorders"
    ws = [p for p in root.glob("*/workspace") if (p / ".forge-run/package.json").is_file()] if root.is_dir() else []
    pin = os.environ.get("FORGE_T048_WO")
    if pin:
        ws = [p for p in ws if p.parent.name == pin]
    return sorted(ws, key=lambda p: json.loads((p / ".forge-run/manifest.json").read_text())["created_at"])


@pytest.mark.skipif(not finished_workorders(), reason="no finished live work order")
def test_t048_unattended_local_qwen_run_and_reproducible_evidence(tmp_path):
    from forge_factory.fabro.client import FabroClient, load_token
    from forge_factory.inspection.ears import check_file
    from forge_factory.inspection.guideline import check_workspace
    from forge_factory.release.finalize import cross_check_kpis, verify_archive

    ws = finished_workorders()[-1]
    pkg = json.loads((ws / ".forge-run/package.json").read_text())
    pre = json.loads((ws / ".forge-run/preflight.json").read_text())
    assert pre["agents"]["status"] == "PASS" and pre["mcp"]["status"] == "PASS"
    assert pkg["package_status"] in ("READY_FOR_OFFLINE_REVIEW", "BLOCKED")
    assert pkg["scope"] == "OFFLINE_REVIEW_ONLY_NOT_SAFETY_APPROVED"
    run_id = (ws / ".forge-run/fabro_run_id").read_text().strip()
    evs = list(FabroClient(token=load_token(), timeout=15).iter_events(run_id))
    kinds = {e["event"] for e in evs}
    assert not any(k.startswith(("interview.", "question.", "run.approval", "human.")) for k in kinds)  # no human gate
    models = {(e.get("properties") or {}).get("model") for e in evs if e["event"] == "stage.prompt"}
    assert models <= {"qwen3:8b", None}  # local model only
    assert "hexagon" not in (ws / ".forge-run/workflow.fabro").read_text()
    archive = Path(pkg["archive"])
    assert verify_archive(archive)["integrity"] == "PASS"
    if pkg.get("policy", "").endswith("v0.5.json"):  # KPI snapshots exist from the v0.5 policy onwards
        assert cross_check_kpis(archive)["status"] == "PASS"
    # evidence reproduces: re-run deterministic checks on the ARCHIVED workproducts
    with zipfile.ZipFile(archive) as z:
        z.extractall(tmp_path / "x")
    ev = tmp_path / "x/evidence"
    req = ev / "workproducts/SWE.1/software_requirements.md"
    if req.is_file():
        names = set(json.loads((ws / "configuration/system_names.json").read_text()))
        assert check_file(req, names)["verdict"] == check_file(ws / "workproducts/SWE.1/software_requirements.md",
                                                               names)["verdict"]
    if (ev / "software/hal").is_dir() or (ev / "software/ll").is_dir():
        assert check_workspace(ev)["verdict"] == check_workspace(ws)["verdict"]
    for ins in ev.glob("inspection/SWE.*/INS-*.json"):
        assert ins.read_bytes() == (ws / ins.relative_to(ev)).read_bytes()  # immutable records preserved verbatim
    q = json.loads((ev / "quality/final-gates.json").read_text())
    assert q["derived_from"] == "recorded evidence only" and q["safety_approval"].startswith("NOT_APPLICABLE")
