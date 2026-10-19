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
    (src / "build/target-cm55-gcc").mkdir(parents=True)
    (src / "build/target-cm55-gcc/driver.elf").write_bytes(b"ELF")  # build of SWE.3 sources: only with a stable SWE.3
    ws = tmp_path / "state/workorders/WO-NEW/workspace"
    (ws / ".forge-run").mkdir(parents=True)
    subprocess.run(["git", "init", "-q"], cwd=ws, check=True)
    man = {"work_order": "WO-NEW"}
    remaining = resume_from(ws, man, "WO-SRC")
    assert remaining == ["SWE.3", "SWE.4", "SWE.5", "SWE.6"]
    d = Store(ws)
    assert d.gate("SWE.1")["decision"] == "PASS" and d.gate("SWE.2")["decision"] == "PASS"
    assert not (ws / "configuration/baselines/SWE.3").exists() and not (ws / "workproducts/SWE.3").exists()
    assert not (ws / "build/target-cm55-gcc").exists()
    rec = json.loads((ws / ".forge-run/manifest.json").read_text())["resumed_from"]
    assert rec["source_work_order"] == "WO-SRC" and rec["restart_phase"] == "SWE.3"
    assert set(rec["stable_phases"]) == {"SWE.1", "SWE.2"}


def _stable_swe1(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("FORGE_EVENTS_DIR", str(tmp_path / "ev"))
    src = tmp_path / "state/workorders/WO-SRC/workspace"
    for rel, txt in {"workproducts/SWE.1/software_requirements.md":
                     "- **SWR-001** When enable is requested, the RCC driver shall set the clock enable bit.\n",
                     "traceability/requirements_to_tests.csv": "requirement_id,test_id,test_file\nSWR-001,UT-001,t.c\n",
                     "traceability/provided_ll.h": "#define LL 1\n",
                     "configuration/system_names.json": json.dumps(["RCC driver"])}.items():
        (src / rel).parent.mkdir(parents=True, exist_ok=True)
        (src / rel).write_text(txt)
    add_reqif(src)
    s = Store(src)
    bl = s.freeze("SWE.1", "swe1-author")
    assert s.record_inspection("SWE.1", "swe1-inspector", bl["baseline_id"], _all_pass("SWE.1"))["verdict"] == "PASS"
    ws = tmp_path / "state/workorders/WO-NEW/workspace"
    (ws / "traceability").mkdir(parents=True)
    (ws / ".forge-run").mkdir(parents=True)
    subprocess.run(["git", "init", "-q"], cwd=ws, check=True)
    return src, ws


def test_capa040_provided_read_only_file_is_kept_and_must_match(tmp_path, monkeypatch):
    """CAPA-040 (r132/r133): a HAL resume copied the source's provided LL header over the new work order's own
    read-only copy (Permission denied). Provided files are never copied; a different source copy refuses the resume."""
    import hashlib

    import pytest

    src, ws = _stable_swe1(tmp_path, monkeypatch)
    mine = ws / "traceability/provided_ll.h"
    mine.write_text("#define LL 1\n")
    mine.chmod(0o444)
    man = {"work_order": "WO-NEW", "provided": [{"path": "traceability/provided_ll.h",
                                                "sha256": hashlib.sha256(b"#define LL 1\n").hexdigest()}]}
    assert resume_from(ws, man, "WO-SRC")[0] == "SWE.2"
    assert mine.read_text() == "#define LL 1\n" and (mine.stat().st_mode & 0o777) == 0o444
    (src / "traceability/provided_ll.h").write_text("#define LL 2\n")
    with pytest.raises(ValueError, match="RESUME_PROVIDED_MISMATCH:traceability/provided_ll.h"):
        resume_from(ws, man, "WO-SRC")
