"""Owner QM classification, functional gate preservation and real-tool delivery fixtures."""
import copy
import json
import shutil

import pytest
import yaml
from forge_factory import development_execution as D
from forge_factory import provided_requirements as P
from forge_factory import workorder as W
from forge_factory.acp import statements
from forge_factory.afo.durable import digest
from forge_factory.assurance import package, scope
from forge_factory.brownfield import resume
from forge_factory.brownfield.inject import inject
from forge_factory.common import REPO_ROOT
from forge_factory.inspection import gate
from forge_factory.inspection.engine import Store, load_checklist
from forge_factory.lrtx import profile, review, swe1
from forge_factory.release import finalize, qm
from forge_factory.workflow.builder import build
from incremental_idr_anchor import Anchor
from test_simulation_performance import TEST

EXAMPLE = REPO_ROOT / "examples/0014f-st-cube-crc-idr-qm"


@pytest.fixture
def prepared(tmp_path, monkeypatch):
    for key in ("STATE", "EVENTS", "ARCHIVE"):
        monkeypatch.setenv("FORGE_" + key + "_DIR", str(tmp_path / key))
    monkeypatch.delenv("FORGE_OPERATIONS_INTENT", raising=False)
    return W.prepare(EXAMPLE, "WO-QM-FIXTURE", purpose="QM")


def test_actual_review_and_new_owner_classification_import_without_inference(prepared, monkeypatch):
    ws, man = prepared
    old = json.loads((EXAMPLE.parent / "0014e-st-cube-crc-idr-simulation/provided-requirements.json").read_text())
    doc, _ = P.validate(ws)
    assert {k: v for k, v in P.payload(old).items() if k != "scope_sha256"} == {
        k: v for k, v in P.payload(doc).items() if k != "scope_sha256"}
    assert doc["review"]["original_functional_review"] == old["review"]
    assert man["safety_target"] == "QM" and qm.workspace_record(ws)["classification"] == "QM"
    assert scope.evaluate(qm.scope_record("WO", "hash")["scope"], {}, qm.scope_record("WO", "hash")["na"])["issues"] == []
    Anchor(ws, monkeypatch)  # Binding only; no substitute verdict is used in this check.
    assert P.materialize(ws)["status"] == "PASS"
    assert gate.step_author(Store(ws), "SWE.1", json.dumps({"status": "PASS", "artifacts": [], "issues": [], "next_action": "next"})) == 0
    assert Store(ws).gate("SWE.1")["decision"] == "REINSPECT"
    assert inject(ws)["status"] == "REFUSED"
    assert "QM development" in swe1.safety_text(ws)
    assert all(not (ws / i["path"]).exists() for i in man["delivered"])


def test_qm_tailors_only_safety_clauses_and_does_not_accept_a_functional_failure(prepared, monkeypatch):
    ws, man = prepared
    Anchor(ws, monkeypatch)
    assert P.materialize(ws)["status"] == "PASS"
    store = Store(ws)
    assert gate.step_author(store, "SWE.1", json.dumps({"status": "PASS", "artifacts": [], "issues": [], "next_action": "next"})) == 0
    changes = qm.binding()["owner_decision"]["criterion_tailoring"]
    for n in range(1, 7):
        raw = load_checklist(f"SWE.{n}", brownfield=True)
        effective = store.checklist(f"SWE.{n}")
        assert raw["policy"] == effective["policy"]
        assert len(raw["checks"]) == len(effective["checks"])
        for a, b in zip(raw["checks"], effective["checks"], strict=True):
            assert {k: v for k, v in a.items() if k != "criterion"} == {k: v for k, v in b.items() if k != "criterion"}
            if a["id"] not in changes:
                assert a == b
        assert raw["sha256"] != effective["sha256"]
    baseline = store.latest_baseline("SWE.1")
    verdicts = {c["id"]: {"verdict": "PASS", "evidence_refs": ["workproducts/SWE.1/software_requirements.md"]}
                for c in store.checklist("SWE.1")["checks"]}
    verdicts["SWE1-03"] = {"verdict": "FAIL", "evidence_refs": ["workproducts/SWE.1/software_requirements.md"],
                           "findings": ["Explicit functional failure-handling defect fixture; QM must still block."]}
    record = store.record_inspection("SWE.1", "swe1-inspector", baseline["baseline_id"], verdicts)
    assert record["verdict"] == "FAIL" and store.gate("SWE.1")["decision"] != "PASS"
    assert inject(ws)["status"] == "REFUSED"
    # The old safety criterion is preserved for old/other work orders.
    assert next(c for c in load_checklist("SWE.1")["checks"] if c["id"] == "SWE1-03")["criterion"] == (
        "Failure handling, reset/startup behavior and safe states are specified.")


@pytest.mark.parametrize("fault", ["missing-binding", "classification", "scope-record", "context", "purpose"])
def test_missing_changed_or_mislabeled_qm_scope_refuses(prepared, fault):
    ws, man = prepared
    if fault == "missing-binding":
        del man[qm.FIELD]
    elif fault == "classification":
        man["safety_target"] = "B"
    elif fault == "purpose":
        man["purpose"] = "FORMAL_REVIEW"
    elif fault == "context":
        del man["inspection_assessment_context"]
    else:
        path = ws / scope.SCOPE_FILE
        path.chmod(0o600)
        record = json.loads(path.read_text())
        record["scope"]["target_asil"] = "B"
        path.write_text(json.dumps(record))
    (ws / ".forge-run/manifest.json").write_text(json.dumps(man))
    if fault == "context":
        with pytest.raises(ValueError):
            review.evidence(ws, "SWE.1")
        with pytest.raises(ValueError):
            Store(ws).checklist("SWE.1")
    else:
        assert scope.workspace_scope_findings(ws, "SWE.1") == ["QM_SCOPE_BINDING_CHANGED"]


def test_generic_qm_on_existing_rcc_preserves_previous_asil_history(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("FORGE_EVENTS_DIR", str(tmp_path / "events"))
    ws, man = W.prepare(REPO_ROOT / "examples/0002a-arm_55_rcc_ll", "WO-QM-RCC", purpose="QM")
    assert man["historical_safety_scope"]["scope"]["target_asil"] == "B"
    assert qm.workspace_record(ws) and man["safety_target"] == "QM"
    assert json.loads((ws / scope.SCOPE_FILE).read_text())["scope"]["target_asil"] == "QM"
    assert not man.get("owner_safety_documents")
    contract = resume.contract(man)
    other = copy.deepcopy(man)
    other["work_order"] = "WO-ANOTHER"
    other["historical_safety_scope"]["scope"]["work_order_id"] = other["work_order"]
    assert resume.contract(other) == contract
    other[qm.FIELD]["classification"] = "B"
    assert resume.contract(other) != contract
    other["purpose"] = "ASPICE_ONLY"
    with pytest.raises(resume.ResumeRefused):
        resume.contract(other)


def test_qm_profile_keeps_exact_inference_settings_and_explicit_lane():
    new = profile.load("local-rtx-v2-omniverse2-q38-qm-mtp")
    old = profile.load("local-rtx-v2-omniverse2-q38-aspice-mtp")
    qm.validate_profile("QM", new)
    for key in ("models", "runtime", "structured", "gateway", "admission"):
        assert new[key] == old[key]
    for purpose, prof in (("QM", old), ("ASPICE_ONLY", new)):
        with pytest.raises(ValueError):
            qm.validate_profile(purpose, prof)
    assert D.binding(D.HIGH, "QM")["purpose"] == "QM"
    assert "purpose" not in D.binding(D.HIGH, "ASPICE_ONLY")


def test_native_and_structured_inspectors_receive_the_same_frozen_qm_criteria(prepared, monkeypatch):
    ws, man = prepared
    Anchor(ws, monkeypatch)
    assert P.materialize(ws)["status"] == "PASS"
    st = Store(ws)
    st.freeze("SWE.1", "swe1-author")
    baseline, sources = review.evidence(ws, "SWE.1")
    criterion = next(c for c in st.checklist("SWE.1")["checks"] if c["id"] == "SWE1-03")
    packet = review.item_packet(ws, "SWE.1", criterion, baseline, sources, "qwen3.8:27b-q8_0")
    assert packet["criteria"] == ["SWE1-03: " + criterion["criterion"]]
    assert packet["assessment_scope"]["binding_sha256"] == digest(qm.workspace_record(ws))
    assert packet["assessment_scope"]["instruction"] in packet["_messages"][0]["content"]
    assert "safety-oriented ASPICE work order" not in packet["_messages"][0]["content"]
    graph, nodes = build(man["work_order"], layer="LL", brownfield="FROZEN", peripheral="crc",
                         operation_scope=man["operation_scope"], execution_policy=man["development_execution"],
                         assessment_manifest=man)
    bodies = {name: graph[start:end] for start, end, _i, name, attrs in statements(graph) if 'prompt="' in attrs}
    for n in (2, 6):
        for check in st.checklist(f"SWE.{n}")["checks"]:
            assert (check["id"] + ": " + check["criterion"][:70]) in bodies[f"swe{n}_inspector"]
    for name in bodies:
        if name in nodes:
            assert qm.PROMPT_SCOPE in bodies[name]
    with pytest.raises(ValueError, match="QM_ASSESSMENT_MANIFEST_REQUIRED"):
        build(man["work_order"], execution_policy=man["development_execution"])


@pytest.fixture(scope="module")
def completed_qm(tmp_path_factory):
    root = tmp_path_factory.mktemp("qm-real-tools")
    with pytest.MonkeyPatch.context() as mp:
        for key in ("STATE", "EVENTS", "ARCHIVE"):
            mp.setenv("FORGE_" + key + "_DIR", str(root / key))
        mp.delenv("FORGE_OPERATIONS_INTENT", raising=False)
        ws, man = W.prepare(EXAMPLE, "WO-QM-END-TO-END-FIXTURE", purpose="QM")
        anchor = Anchor(ws, mp)
        assert P.materialize(ws)["status"] == "PASS"
        anchor.finish("SWE.1")  # Scripted semantic verdicts, real ordinary gates.
        assert inject(ws)["status"] == "INJECTED"
        anchor.architecture()
        anchor.implementation()
        anchor.unit()
        anchor.write("SWE.5", {"software/tests/target/test_performance.c": TEST})
        anchor.integration()
        anchor.validation()
        result = finalize.finalize(ws, "qm-real-tool-fixture")
        assert result["package_status"] == "READY_FOR_OFFLINE_REVIEW"
        assert qm.workspace_record(ws)
    return ws


def test_real_six_phase_qm_fixture_and_independent_missing_trace_negative(completed_qm, tmp_path, monkeypatch):
    ws = tmp_path / "mutant"
    shutil.copytree(completed_qm, ws)
    for key in ("STATE", "EVENTS", "ARCHIVE"):
        monkeypatch.setenv("FORGE_" + key + "_DIR", str(tmp_path / key))
    assert package.scope_dispositions(ws, tmp_path / "stage")["classification"] == "QM"
    for n in range(1, 7):
        assert Store(ws).gate(f"SWE.{n}")["decision"] == "PASS"
    p = ws / "traceability/requirements_to_tests.csv"
    p.write_text("requirement_id,test_id\n")
    result = finalize.finalize(ws, "qm-broken-trace-fixture")
    assert result["package_status"] == "BLOCKED"


def test_disabled_qm_policy_does_not_remove_required_gates(prepared, tmp_path, monkeypatch):
    ws, man = prepared
    root = tmp_path / "disabled"
    path = root / qm.POLICY
    path.parent.mkdir(parents=True)
    decision = copy.deepcopy(man[qm.FIELD]["owner_decision"])
    decision["enabled"] = False
    path.write_text(yaml.safe_dump(decision))
    monkeypatch.setattr(qm, "REPO_ROOT", root)
    assert scope.workspace_scope_findings(ws, "SWE.1") == ["QM_SCOPE_BINDING_CHANGED"]
    stage = tmp_path / "stage"
    (stage / "quality").mkdir(parents=True)
    (stage / "quality/final-gates.json").write_text('{"open_findings": []}')
    assert qm.effective_policy(finalize.POLICY_V04, ws, stage) == finalize.POLICY_V04
    assert json.loads((stage / "quality/final-gates.json").read_text())["open_findings"][0]["id"] == "QM_SCOPE_BINDING_CHANGED"
