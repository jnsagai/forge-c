"""Resume from the last stable phase: only leading PASSED phases are carried over; restart at the first non-PASS."""
import json
import subprocess

from forge_factory.inspection.engine import Store, load_checklist
from forge_factory.workorder import resume_from
from test_swe2_architecture import ARCH_MIN, add_reqif, add_views


def _all_pass(phase):
    return {c["id"]: {"verdict": "PASS", "evidence_refs": ["x"]} for c in load_checklist(phase)["checks"]}


def test_resume_carries_only_leading_passed_phases(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("FORGE_EVENTS_DIR", str(tmp_path / "ev"))
    src = tmp_path / "state/workorders/WO-SRC/workspace"
    for rel, txt in {"workproducts/SWE.1/software_requirements.md":
                     "- **SWR-001** When enable is requested, the RCC driver shall set the clock enable bit.\n",
                     "traceability/requirements_to_tests.csv": "requirement_id,test_id,test_file\nSWR-001,UT-001,t.c\n",
                     "configuration/system_names.json": json.dumps(["RCC driver"]),
                     "workproducts/SWE.2/software_architecture.md": ARCH_MIN,
                     "workproducts/SWE.3/detailed_design.md": "# D\n"}.items():
        (src / rel).parent.mkdir(parents=True, exist_ok=True)
        (src / rel).write_text(txt)
    add_reqif(src)
    add_views(src)
    s = Store(src)
    for ph, insp in (("SWE.1", "swe1-inspector"), ("SWE.2", "swe2-inspector")):
        bl = s.freeze(ph, f"swe{ph[-1]}-author")
        assert s.record_inspection(ph, insp, bl["baseline_id"], _all_pass(ph))["verdict"] == "PASS"
    s.freeze("SWE.3", "swe3-author")  # frozen but never inspected -> not stable
    ws = tmp_path / "state/workorders/WO-NEW/workspace"
    (ws / ".forge-run").mkdir(parents=True)
    subprocess.run(["git", "init", "-q"], cwd=ws, check=True)
    man = {"work_order": "WO-NEW"}
    remaining = resume_from(ws, man, "WO-SRC")
    assert remaining == ["SWE.3", "SWE.4", "SWE.5", "SWE.6"]
    d = Store(ws)
    assert d.gate("SWE.1")["decision"] == "PASS" and d.gate("SWE.2")["decision"] == "PASS"
    assert not (ws / "configuration/baselines/SWE.3").exists() and not (ws / "workproducts/SWE.3").exists()
    rec = json.loads((ws / ".forge-run/manifest.json").read_text())["resumed_from"]
    assert rec["source_work_order"] == "WO-SRC" and rec["restart_phase"] == "SWE.3"
    assert set(rec["stable_phases"]) == {"SWE.1", "SWE.2"}
