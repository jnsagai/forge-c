"""T009 (AT-06/07/08): author/inspector separation, frozen baselines, stale reinspection, bounded loops."""
import json

import pytest
from forge_factory.inspection.engine import PHASES, InspectionError, Store, load_checklist

EARS_OK = "- **SWR-001** When enable is requested, the RCC driver shall set the clock enable bit.\n"
EARS_BAD = "- **SWR-001** Clocks should be enabled quickly.\n"


def all_pass(phase, evidence="workproducts/x"):
    return {c["id"]: {"verdict": "PASS", "evidence_refs": [evidence]} for c in load_checklist(phase)["checks"]}


@pytest.fixture()
def store(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_EVENTS_DIR", str(tmp_path / "ev"))
    ws = tmp_path / "ws"
    (ws / "workproducts/SWE.1").mkdir(parents=True)
    (ws / "workproducts/SWE.1/software_requirements.md").write_text(EARS_OK)
    (ws / "configuration").mkdir()
    (ws / "configuration/system_names.json").write_text(json.dumps(["RCC driver"]))
    from test_swe2_architecture import add_reqif

    add_reqif(ws)  # SWE1-08: ReqIF export of the requirements
    return Store(ws)


def write_phase(store, phase, text="content"):
    p = store.workspace / f"workproducts/{phase}/doc.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)
    if phase == "SWE.2":  # SWE2-07/08 are decided deterministically from the architecture workproducts
        from test_swe2_architecture import ARCH_MIN, add_views

        (p.parent / "software_architecture.md").write_text(ARCH_MIN)
        add_views(store.workspace)
    if phase == "SWE.1":
        from test_swe2_architecture import add_reqif

        add_reqif(store.workspace)


def test_checklists_extend_pinned_v03_and_swe1_has_ears():
    for p in PHASES:
        c = load_checklist(p)
        assert c["policy"]["author_must_differ_from_inspector"] is True
    ids = [c["id"] for c in load_checklist("SWE.1")["checks"]]
    assert ids[:6] == [f"SWE1-0{i}" for i in range(1, 7)] and "SWE1-07" in ids


def test_happy_path_pass_with_distinct_roles(store):
    bl = store.freeze("SWE.1", "swe1-author")
    ins = store.record_inspection("SWE.1", "swe1-inspector", bl["baseline_id"], all_pass("SWE.1"))
    assert ins["verdict"] == "PASS" and ins["author_role"] != ins["inspector_role"]
    assert ins["items"]["SWE1-07"]["source"] == "deterministic"
    assert store.gate("SWE.1")["decision"] == "PASS"


def test_role_separation_enforced(store):
    bl = store.freeze("SWE.1", "swe1-author")
    with pytest.raises(InspectionError, match="INSPECTOR_ROLE_MISMATCH"):
        store.record_inspection("SWE.1", "swe1-author", bl["baseline_id"], all_pass("SWE.1"))
    with pytest.raises(InspectionError, match="INSPECTOR_ROLE_MISMATCH"):
        store.record_inspection("SWE.1", "swe2-inspector", bl["baseline_id"], all_pass("SWE.1"))
    with pytest.raises(InspectionError, match="AUTHOR_ROLE_MISMATCH"):
        store.freeze("SWE.1", "swe1-inspector")


def test_deterministic_ears_overrides_inspector_pass(store):
    (store.workspace / "workproducts/SWE.1/software_requirements.md").write_text(EARS_BAD)
    bl = store.freeze("SWE.1", "swe1-author")
    ins = store.record_inspection("SWE.1", "swe1-inspector", bl["baseline_id"], all_pass("SWE.1"))
    assert ins["verdict"] == "FAIL" and ins["items"]["SWE1-07"]["verdict"] == "FAIL"
    assert store.gate("SWE.1")["decision"] == "REWORK"


def test_stale_baseline_cannot_pass_and_records_immutable(store):
    bl = store.freeze("SWE.1", "swe1-author")
    (store.workspace / "workproducts/SWE.1/software_requirements.md").write_text(EARS_OK + EARS_OK.replace("001", "002"))
    ins = store.record_inspection("SWE.1", "swe1-inspector", bl["baseline_id"], all_pass("SWE.1"))
    assert ins["verdict"] == "FAIL" and ins["stale_reason"] == "BASELINE_CHANGED_AFTER_FREEZE"
    first = (store.insp / "SWE.1" / f"{ins['inspection_id']}.json").read_text()
    bl2 = store.freeze("SWE.1", "swe1-author")
    assert store.gate("SWE.1")["decision"] == "REINSPECT"
    store.record_inspection("SWE.1", "swe1-inspector", bl2["baseline_id"], all_pass("SWE.1"))
    assert (store.insp / "SWE.1" / f"{ins['inspection_id']}.json").read_text() == first  # initial verdict kept
    assert store.gate("SWE.1")["decision"] == "PASS"


def test_missing_evidence_or_verdict_is_a_finding(store):
    bl = store.freeze("SWE.1", "swe1-author")
    v = all_pass("SWE.1")
    v["SWE1-02"] = {"verdict": "PASS", "evidence_refs": []}
    del v["SWE1-03"]
    ins = store.record_inspection("SWE.1", "swe1-inspector", bl["baseline_id"], v)
    ids = {f["id"] for f in ins["findings"]}
    assert {"SWE1-02", "SWE1-03"} <= ids and ins["verdict"] == "FAIL"


def test_bounded_rework_then_blocked(store):
    for _ in range(3):
        (store.workspace / "workproducts/SWE.1/software_requirements.md").write_text(EARS_BAD + f"<!-- {_} -->")
        bl = store.freeze("SWE.1", "swe1-author")
        store.record_inspection("SWE.1", "swe1-inspector", bl["baseline_id"], all_pass("SWE.1"))
    g = store.gate("SWE.1")
    assert g["decision"] == "BLOCKED" and g["failed_inspections"] == 3


def test_upstream_change_invalidates_downstream(store):
    bl1 = store.freeze("SWE.1", "swe1-author")
    store.record_inspection("SWE.1", "swe1-inspector", bl1["baseline_id"], all_pass("SWE.1"))
    write_phase(store, "SWE.2")
    bl2 = store.freeze("SWE.2", "swe2-author")
    store.record_inspection("SWE.2", "swe2-inspector", bl2["baseline_id"], all_pass("SWE.2"))
    assert store.gate("SWE.2")["decision"] == "PASS"
    (store.workspace / "workproducts/SWE.1/software_requirements.md").write_text(
        EARS_OK + "- **SWR-002** The RCC driver shall report the active clock source.\n")
    assert store.impacted_by("SWE.1") == ["SWE.2"]
    assert store.gate("SWE.2")["decision"] == "REWORK"
    with pytest.raises(InspectionError, match="UPSTREAM_NOT_FROZEN"):
        store.freeze("SWE.2", "swe2-author")


def test_tampered_v03_checklist_detected(tmp_path, monkeypatch):
    import shutil

    from forge_factory.common import REPO_ROOT
    for rel in ["factory/checklists", "factory/release-manager/checklists"]:
        shutil.copytree(REPO_ROOT / rel, tmp_path / rel, copy_function=shutil.copyfile)  # the copy is ours: writable
    p = tmp_path / "factory/release-manager/checklists/SWE.3.yaml"
    p.write_text(p.read_text().replace("maximum_rework_cycles: 3", "maximum_rework_cycles: 99"))
    with pytest.raises(InspectionError, match="CHECKLIST_BASE_TAMPERED"):
        load_checklist("SWE.3", tmp_path)
