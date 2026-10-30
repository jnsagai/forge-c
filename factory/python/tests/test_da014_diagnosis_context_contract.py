"""Generic requirement/incident namespaces, genuine missing facts and measured complete requests."""
import copy
import json
from pathlib import Path

import pytest
from forge_factory.afo import diagnosis_packet as P
from forge_factory.afo import durable_agent as D
from forge_factory.afo import semantic_proposal as S
from forge_factory.afo.diagnosis_context import context_contract
from forge_factory.afo.durable import canonical
from forge_factory.lrtx import profile


def case_job(tmp_path, monkeypatch, *, fixture=False, missing=False):
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("FORGE_EVENTS_DIR", str(tmp_path / "events"))
    ws = tmp_path / "workspace"
    paths = ("workproducts/SWE.1/requirements.md", "software/ll/device.c")
    for relative, text in zip(paths, ("REQ-DEVICE-12: return the input with bit0 set.", "unit_set returns input | 2."), strict=True):
        p = ws / relative
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
    bundle = {"bundle_id": "context-b", "order_id": "context-o", "attempt_id": "context-a",
              "phase": "SWE.3", "fingerprint": "context-f"}
    ref = P.seal(ws, bundle,
                 [{"id": "effect", "obligation_id": "UNIT-DEVICE-7", "detail": "REQ-DEVICE-12 demands bit0."}],
                 [{"path": p} for p in paths if not missing],
                 missing=["AUTHORITATIVE_INPUT:REQ-DEVICE-12"] if missing else [],
                 required_obligations=["REQ-DEVICE-12", "UNIT-DEVICE-7"])
    case = {"bundle": bundle, "workspace": str(ws), "packet_ref": ref}
    if fixture:
        case["qualification_fixture"] = {"source_kind": "SEEDED_PROTOCOL_NOT_PRODUCT", "evaluation_holdout": True,
                                         "expected": "MUST_NOT_REACH_MODEL", "prospective_fault": "PRIVATE_TEST_CONTROL"}
    path = tmp_path / "case.json"
    path.write_text(json.dumps(case))
    return {"case": str(path), "role": "afo-recovery-planner", "model": "qwen3.8:27b-q8_0",
            "profile": "local-rtx-v2-omniverse2-q38-qm-demo-repair-mtp"}, case, P.load(ref)


def test_current_request_distinguishes_global_requirements_from_incident_units(tmp_path, monkeypatch):
    job, _, packet = case_job(tmp_path, monkeypatch)
    before = canonical(packet)
    body, measured = D.request_material(job)
    doc = json.loads(body["messages"][1]["content"])
    context = doc["diagnosis_context"]
    assert context["required_requirement_ids"] == ["REQ-DEVICE-12", "UNIT-DEVICE-7"]
    assert context["incident_unit_ids"] == context["selected_incident_unit_ids"] == ["UNIT-DEVICE-7"]
    assert context["requirements_without_own_incident_unit"] == ["REQ-DEVICE-12"]
    assert "REQ-DEVICE-12" in doc["primary_sources"][0]["text"]
    assert "missing map key alone" in body["messages"][0]["content"]
    assert canonical(P.load(json.loads(Path(job["case"]).read_text())["packet_ref"])) == before
    from forge_factory.llm_gateway import sanitize_request
    effective = sanitize_request(body, policy=profile.load(job["profile"])["gateway"]["reasoning"])
    assert measured["sha256"] == P.measure_request(effective)["sha256"]
    assert measured["serialized_bytes"] == len(canonical(effective))


def test_scope_classification_cannot_leak_expected_outcomes_or_invent_authority(tmp_path, monkeypatch):
    job, _, _ = case_job(tmp_path, monkeypatch, fixture=True)
    body, _ = D.request_material(job)
    context = json.loads(body["messages"][1]["content"])["diagnosis_context"]
    assert context["case_scope"]["kind"] == "DECLARED_SYNTHETIC_CONTRACT_FIXTURE"
    assert context["case_scope"]["authority"] == "NO_BASELINE_OR_RELEASE_AUTHORITY_INFERRED"
    assert "MUST_NOT_REACH_MODEL" not in canonical(body).decode()
    assert "PRIVATE_TEST_CONTROL" not in canonical(body).decode()
    assert "INVENTORY_ONLY" in context["coverage_status"]


def test_genuine_missing_primary_evidence_stays_missing_and_proposal_rules_stay_strict(tmp_path, monkeypatch):
    job, _, packet = case_job(tmp_path, monkeypatch, missing=True)
    body, _ = D.request_material(job)
    doc = json.loads(body["messages"][1]["content"])
    assert doc["packet"]["complete"] is False and doc["packet"]["missing"] == packet["missing"]
    assert doc["primary_sources"] == []
    assert "genuinely missing decisive contract" in body["messages"][0]["content"]
    proposal = {"decision": "NEEDS_EVIDENCE", "evidence_refs": [packet["findings"][0]["ref"]],
                "missing_evidence": [{"evidence_kind": "AUTHORITATIVE_INPUT", "obligation_ref": "UNIT-DEVICE-7",
                                      "reason": "The decisive primary contract is missing."}]}
    S.check(proposal, packet)
    duplicate = copy.deepcopy(proposal)
    duplicate["missing_evidence"] *= 2
    from forge_factory.afo.durable import Refused
    with pytest.raises(Refused, match="CONTRACT_INVALID"):
        S.parse(duplicate)


def test_later_small_questions_keep_global_coverage_and_dependency_inventory(tmp_path, monkeypatch):
    job, _, _ = case_job(tmp_path, monkeypatch)
    prior = {"question_1_answer": {"conflict": "YES", "evidence_refs": ["F1"], "rationale": "Contract vs implementation."}}
    body, _ = D.request_material(job, step=2, prior=prior)
    doc = json.loads(body["messages"][1]["content"])
    assert doc["diagnosis_context"]["required_requirement_ids"] == ["REQ-DEVICE-12", "UNIT-DEVICE-7"]
    assert doc["diagnosis_context"]["global_unit_dependencies"] == {"UNIT-DEVICE-7": []}
    assert "primary_sources" not in doc


@pytest.mark.parametrize("value", [None, [], {"source_kind": "SEEDED_PROTOCOL_NOT_PRODUCT", "evaluation_holdout": False},
                                   {"source_kind": "WORK_ORDER", "evaluation_holdout": True}])
def test_unknown_or_unmatched_scope_does_not_establish_fixture_authority(value):
    packet = {"obligations": {"UNIT-A": {"dependencies": ["UNIT-B"]}, "UNIT-B": {"dependencies": []}},
              "required_obligations": ["REQ-OTHER", "UNIT-A", "UNIT-B"]}
    context = context_contract(packet, {"qualification_fixture": value}, ["UNIT-A"])
    assert context["case_scope"]["kind"] == "WORK_ORDER_EVIDENCE"
    assert context["global_unit_dependencies"] == {"UNIT-A": ["UNIT-B"], "UNIT-B": []}
    assert context["requirements_without_own_incident_unit"] == ["REQ-OTHER"]

