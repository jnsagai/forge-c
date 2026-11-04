"""Normal provided-LL CODE ownership is deferred to SWE.3, without a forward upstream loop."""
import copy
import json
import shutil
import subprocess

import pytest
from forge_factory.common import pretty_json, sha256_bytes
from forge_factory.inspection import defects as D
from forge_factory.inspection import provided_changes as PC
from forge_factory.inspection import provided_early_code as E
from forge_factory.inspection.engine import Store
from forge_factory.policy.authz import Authorizer, Binding

LL = "software/ll/stm32n6xx_ll_wwdg.h"
QUOTE = "The driver shall preserve all reserved register bits at their reset values."


@pytest.fixture
def provided(tmp_path, monkeypatch):
    ws = tmp_path / "state/workorders/WO-CONTROL-EARLY2/workspace"
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("FORGE_EVENTS_DIR", str(tmp_path / "events"))
    raw = b"static inline void LL_Clear(void) { /* provided implementation */ }\n"
    data = {"work_order": "WO-CONTROL-EARLY2", "layer": "HAL", "peripheral": "wwdg",
            "unit_verification": "uspec-gtest-v1", "purpose": "ASPICE_ONLY",
            "provided": [{"path": LL, "role": "provided_ll_driver", "sha256": sha256_bytes(raw),
                          "source_work_order": "WO-CONTROL-LL", "source_package": "READY_FOR_OFFLINE_REVIEW"}]}
    for rel, value in {".forge-run/manifest.json": pretty_json(data), LL: raw.decode(),
                       "workproducts/SWE.1/software_requirements.md": "- **SWR-034** " + QUOTE + "\n"}.items():
        path = ws / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value)
    PC.save_original(ws, LL, raw)
    assert PC.enabled(ws)
    return ws


def report(ws, phase="SWE.2", evidence=None):
    return D.report(ws, detected_phase=phase, reported_by="swe" + phase[-1] + "-author", kind="CODE",
        summary=LL + " does not preserve reserved reset values.", requirement_ids=["SWR-034"], test_files=[],
        evidence_refs=evidence if evidence is not None else [LL + ":1"], requirement_quote=QUOTE)


def test_normal_early_provided_code_is_recorded_for_its_future_owner(provided):
    row = report(provided)
    assert row["status"] == "OPEN" and row["target_phase"] == "SWE.3"
    assert row["target_kind"] == "PROVIDED_CODE"
    assert row["provided_code_reference"]["path"] == LL
    assert D.open_from(provided, "SWE.2") == []
    assert D.take_upstream(provided, "SWE.3") == []
    assert D.loops_used(provided) == 0


def test_same_owner_provided_code_is_claimed_without_broadening_phase_permissions(provided):
    row = report(provided, "SWE.3")
    assert row["status"] == "IN_FIX"
    auth = Authorizer(Binding("CONTROL", str(provided), {
        "two": {"role": "swe2-author", "phase": "SWE.2"}, "three": {"role": "swe3-author", "phase": "SWE.3"}}))
    assert not auth.decide("two", "write_file", {"path": LL, "content": "CONTROL"}).allow
    assert auth.decide("three", "write_file", {"path": LL, "content": "CONTROL"}).allow


@pytest.mark.parametrize("change", ["disabled", "foreign_file", "vendor_input", "missing_original", "symlink"])
def test_early_exception_requires_the_existing_exact_provided_scope(provided, change):
    evidence = [LL + ":1"]
    if change == "disabled":
        path = provided / ".forge-run/manifest.json"
        doc = json.loads(path.read_text())
        doc.pop("unit_verification")
        path.write_text(pretty_json(doc))
    elif change in ("foreign_file", "vendor_input"):
        rel = "software/hal/other.c" if change == "foreign_file" else "inputs/vendor/include/device.h"
        path = provided / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("CONTROL\n")
        evidence = [rel + ":1"]
    elif change == "missing_original":
        (provided / PC.ORIGINALS / LL).unlink()
    else:
        original = provided / PC.ORIGINALS / LL
        copy = provided / "copy.h"
        copy.write_bytes(original.read_bytes())
        original.unlink()
        original.symlink_to(copy)
    with pytest.raises(D.DefectError):
        report(provided, evidence=evidence)


def prefix(ws):
    """Real Store gates with explicit synthetic independent inspector verdicts; no model qualification."""
    from test_resume_from import _all_pass
    from test_swe2_architecture import ARCH_MIN, add_reqif, add_views

    for rel, text in {"configuration/system_names.json": '["driver"]',
                      "traceability/requirements_to_tests.csv": "requirement_id,test_id,test_file\nSWR-034,UT-034,t.c\n",
                      "workproducts/SWE.2/software_architecture.md": ARCH_MIN.replace("SWR-001", "SWR-034")}.items():
        path = ws / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    add_reqif(ws)
    add_views(ws)
    for path in (ws / "workproducts/SWE.2").glob("*.puml"):
        path.write_text(path.read_text().replace("_rcc", "_wwdg"))
    store = Store(ws)
    for phase in ("SWE.1", "SWE.2"):
        base = store.freeze(phase, "swe" + phase[-1] + "-author")
        rec = store.record_inspection(phase, "swe" + phase[-1] + "-inspector", base["baseline_id"], _all_pass(phase))
        assert rec["verdict"] == "PASS", rec
        assert store.gate(phase)["decision"] == "PASS"


def target(src):
    ws = src.parents[1] / "WO-CONTROL-NEXT3/workspace"
    man = copy.deepcopy(json.loads((src / ".forge-run/manifest.json").read_text()))
    man["work_order"] = "WO-CONTROL-NEXT3"
    for rel in ("software/ll", E.PC.ORIGINALS):
        shutil.copytree(src / rel, ws / rel)
    (ws / ".forge-run/manifest.json").write_text(pretty_json(man))
    subprocess.run(["git", "init", "-q"], cwd=ws, check=True)
    return ws, man


def test_actual_phase2_pass_normal_resume_and_deterministic_phase3_claim(provided):
    from forge_factory import workorder as W
    from forge_factory.inspection.gate import step_verify

    finding = report(provided)
    prefix(provided)  # the OPEN forward CODE does not force a false upstream or phase2 result
    old_input = D.report(provided, detected_phase="SWE.2", reported_by="swe2-author", kind="INPUT",
                         summary="CONTROL missing external input", requirement_ids=["SWR-034"], test_files=[], evidence_refs=[])
    ws, man = target(provided)
    assert W.resume_from(ws, man, "WO-CONTROL-EARLY2") == ["SWE.3", "SWE.4", "SWE.5", "SWE.6"]
    assert D.all_defects(ws) == [finding]
    assert old_input["id"] not in [d["id"] for d in D.all_defects(ws)]
    assert not (ws / "configuration/baselines/SWE.3").exists()
    assert not (ws / "inspection/SWE.3").exists()
    assert json.loads((ws / E.RECEIPT).read_text())["inherited_verdict"] is False
    assert step_verify(Store(ws), "SWE.3", "provided_code_claim") == 0
    assert D.all_defects(ws)[0]["status"] == "IN_FIX"
    assert D.loops_used(ws) == 0
    assert step_verify(Store(ws), "SWE.3", "provided_code_claim") == 0  # idempotent re-entry
    assert len(D.all_defects(ws)[0]["history"]) == 2
    assert not (ws / "configuration/baselines/SWE.3").exists()


@pytest.mark.parametrize("change", ["prefix", "input", "defect_binding", "symlink", "premature_edit"])
def test_deferred_claim_refuses_changed_scope_without_claiming(provided, change):
    report(provided)
    prefix(provided)
    if change == "prefix":
        (provided / "workproducts/SWE.2/software_architecture.md").write_text("CHANGED\n")
    elif change == "input":
        original = provided / PC.ORIGINALS / LL
        original.chmod(0o644)
        original.write_text("CHANGED\n")
    elif change == "defect_binding":
        row = D.all_defects(provided)[0]
        row[E.FIELD]["original_sha256"] = "0" * 64
        D._save(provided, row)
    elif change == "premature_edit":
        (provided / LL).write_text("ILLEGAL PREMATURE EDIT\n")
    else:
        original = provided / PC.ORIGINALS / LL
        copy = provided / "original-copy.h"
        copy.write_bytes(original.read_bytes())
        original.unlink()
        original.symlink_to(copy)
    with pytest.raises(ValueError, match="EARLY_PROVIDED_CODE"):
        E.claim(provided)
    assert D.all_defects(provided)[0]["status"] == "OPEN"


def test_graph_claim_precedes_author_but_default_graph_is_unchanged():
    from forge_factory.workflow import builder as B
    options = {"layer": "HAL", "uspec_gtest": True, "phases": ["SWE.3"], "stop_after": "SWE.3"}
    legacy, legacy_nodes = B.build("WO-CONTROL", **options)
    graph, nodes = B.build("WO-CONTROL", provided_code_handoff=True, **options)
    assert "swe3_provided_code_claim" not in legacy
    assert 'start -> swe3_provided_code_claim' in graph
    assert 'swe2_inspect_gate -> swe3_provided_code_claim' in graph
    assert 'swe3_provided_code_claim -> swe3_hal_author [condition="outcome=succeeded"]' in graph
    assert 'swe3_provided_code_claim -> finalize' in graph
    assert nodes == legacy_nodes  # no new AI role/permission
    assert B.build("WO-CONTROL", **options) == (legacy, legacy_nodes)


def test_early_verification_uses_phase4_only_after_validating_reference(provided):
    row = report(provided)
    assert D.verification_phase(provided, row) == "SWE.4"
    ordinary = dict(row, target_kind="GENERATED_CODE", detected_phase="SWE.5")
    assert D.verification_phase(provided, ordinary) == "SWE.5"
    row[E.FIELD]["path"] = "software/ll/other.h"
    with pytest.raises(ValueError, match="EARLY_PROVIDED_CODE"):
        D.verification_phase(provided, row)
