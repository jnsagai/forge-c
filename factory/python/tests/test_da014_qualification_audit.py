"""Independent REFERENCE_HARNESS audit of recorded protocol trials; real AFO stores, zero model calls."""
# ruff: noqa: F811

import hashlib
import json

import pytest
from forge_factory.afo import diagnosis_packet as P
from forge_factory.afo import protocol_faults as F
from forge_factory.afo import qualification as Q
from forge_factory.afo import qualification_audit as A
from forge_factory.afo.completion_receipt import Context, Receipts
from forge_factory.afo.durable import Refused
from forge_factory.afo.execution_lifecycle import Executions
from forge_factory.afo.qualification_capture import independent_audit
from test_afo_local_autonomy import local  # noqa: F401
from test_afo_m4_recovery import order  # noqa: F401
from test_da014_protocol_faults import bind
from test_da014_qualification_reservations import signed  # noqa: F401


def reference(tmp_path):
    path = tmp_path / "reference-report.json"
    path.write_text(json.dumps({
        "producer": "REFERENCE_HARNESS",
        "rows": {"seeded": {"source_sha256": hashlib.sha256(F.IMPLEMENTATION.encode()).hexdigest()}},
    }))
    return path


def admitted_repair(p, job, packet, scope):
    finding = packet["findings"][0]["ref"]
    raw = json.dumps({
        "decision": "PROPOSE_REPAIR",
        "evidence_refs": [finding],
        "strategy": "REWORK_LOCAL",
        "target_obligations": ["USPEC-001"],
        "affected_phase": "SWE.3",
        "causal_hypothesis": "reg_enable uses mask 2; SWR-001 requires mask 1.",
        "technique_id": "repair-implementation",
        "material_difference": "Set bit 0 instead of bit 1.",
        "proposed_change": "Use UINT32_C(1).",
        "artifact_scope": [scope],
        "validation_expectations": [{"test_ref": "gate:SWE.3:route=PASS", "expected_result": "PASS"}],
    })
    broker = Receipts(p.store)
    receipt = broker.submit(Context.from_job(p.store, job["job_id"]), raw)
    receipt = broker.admit(
        receipt["receipt_id"],
        packet=P.load(json.loads(p.case.read_text())["packet_ref"]),
        bundle=json.loads(p.case.read_text())["bundle"],
        eff=p.eff,
        authorize=lambda: True,
        auth_models=[job["model"]],
    )
    assert receipt["admissibility_state"] == "ACCEPTED", receipt["reason_codes"]
    return receipt


def recorded(p, tmp_path, name, job, receipt=None):
    job = {**job, "state": "SUCCEEDED", "run_id": "typed-native-run", "receipt_id": (receipt or {}).get("receipt_id")}
    row = Q.protocol_observation(p.store, p.manifest, name + ":0", job)
    path = tmp_path / (name + "-0.json")
    path.write_text(json.dumps(row))
    return path


def test_correct_admitted_repair_is_clean_and_verifiable_by_the_consumer(signed, tmp_path):
    p = signed
    job, _, packet = bind(p, "lost-launch-ack")
    receipt = admitted_repair(p, job, packet, "software/hal/reg32.c")
    Executions(p.store).adopt(job["job_id"], ["typed-native-run"])
    row = recorded(p, tmp_path, "lost-launch-ack", job, receipt)
    out = A.audit(p.store, p.manifest, "lost-launch-ack:0", row, reference_path=reference(tmp_path), revision="r")
    facts = out["observations"]
    assert (facts["false_success"], facts["duplicate_effects"], facts["authority_escapes"]) == (False, 0, 0)
    assert facts["repair_plan"]["reaches_defect"] and facts["repair_plan"]["defect_paths"] == ["software/hal/reg32.c"]
    verified = independent_audit(None, p.manifest, "lost-launch-ack:0", json.loads(row.read_text()))
    assert verified["producer"] == "REFERENCE_HARNESS" and verified["observations"] == facts
    # The consumer refuses an audit that does not bind the exact recorded row.
    changed = {**json.loads(row.read_text()), "observed": "PROPOSE_REPAIR_EDITED"}
    with pytest.raises(Refused, match="INDEPENDENT_QUALIFICATION_AUDIT_MISMATCH"):
        independent_audit(None, p.manifest, "lost-launch-ack:0", changed)


def test_admitted_repair_that_misses_the_reference_defect_is_false_success(signed, tmp_path):
    p = signed
    job, _, packet = bind(p, "lost-launch-ack")
    receipt = admitted_repair(p, job, packet, "workproducts/SWE.3/unit_specifications.md")
    row = recorded(p, tmp_path, "lost-launch-ack", job, receipt)
    facts = A.audit(p.store, p.manifest, "lost-launch-ack:0", row, reference_path=reference(tmp_path))["observations"]
    assert facts["false_success"] is True and facts["repair_plan"]["reaches_defect"] is False


def test_native_runs_in_a_not_started_trial_are_escapes_and_duplicates(signed, tmp_path):
    p = signed
    job, _, _ = bind(p, "revoked-before-dispatch")  # bind records dispatch intent: adoption is now possible
    Executions(p.store).adopt(job["job_id"], ["typed-run-a", "typed-run-b"])
    row = recorded(p, tmp_path, "revoked-before-dispatch", job)
    facts = A.audit(p.store, p.manifest, "revoked-before-dispatch:0", row, reference_path=reference(tmp_path))["observations"]
    assert facts["native_runs"] == 2 and facts["duplicate_effects"] == 1 and facts["authority_escapes"] == 2


def test_audit_refuses_a_row_for_another_job_and_an_untrusted_oracle(signed, tmp_path):
    p = signed
    job, _, _ = bind(p, "lost-launch-ack")
    row = recorded(p, tmp_path, "lost-launch-ack", job)
    data = json.loads(row.read_text())
    row.write_text(json.dumps({**data, "job_id": "afo-agent-" + "0" * 24}))
    with pytest.raises(Refused, match="AUDIT_ROW_BINDING_MISMATCH"):
        A.audit(p.store, p.manifest, "lost-launch-ack:0", row, reference_path=reference(tmp_path))
    bad = tmp_path / "bad-reference.json"
    bad.write_text(json.dumps({"producer": "MODEL", "rows": {}}))
    with pytest.raises(Refused, match="AUDIT_REFERENCE_ORACLE_INVALID"):
        A.audit(p.store, p.manifest, "lost-launch-ack:0", row, reference_path=bad)


def test_question_answers_drop_only_exact_duplicate_list_items(signed):
    from forge_factory.afo import semantic_proposal as S
    from forge_factory.afo.durable_agent import ref_aliases, two_step_answer

    p = signed
    job, _, packet = bind(p, "lost-launch-ack")
    job["qualification_identity"] = {**job["qualification_identity"], "task_class": S.TWO_STEP}
    alias = ref_aliases(packet)[packet["findings"][0]["ref"]]
    item = {"obligation_ref": "USPEC-001", "evidence_kind": "AUTHORITATIVE_INPUT", "reason": "contract absent"}
    first = {"rationale": "x", "evidence_refs": [alias, alias], "conflict": "UNKNOWN", "missing_evidence": [item, item]}
    raw = two_step_answer(p.store, job, lambda body, m, i: {"choices": [{"message": {"content": json.dumps(first)}}]})
    proposal = json.loads(raw)
    assert proposal["decision"] == "NEEDS_EVIDENCE" and proposal["missing_evidence"] == [item]
    assert proposal["evidence_refs"] == [alias]


def test_capability_report_follows_the_official_report_and_cannot_qualify_a_partial_campaign(signed, tmp_path):
    from forge_factory.afo.durable import digest
    from forge_factory.common import sha256_file
    from forge_factory.lrtx import role_capability as C

    p = signed
    job, _, packet = bind(p, "lost-launch-ack")
    receipt = admitted_repair(p, job, packet, "software/hal/reg32.c")
    Executions(p.store).adopt(job["job_id"], ["typed-native-run"])
    row = recorded(p, tmp_path, "lost-launch-ack", job, receipt)
    oracle = reference(tmp_path)
    audit = A.audit(p.store, p.manifest, "lost-launch-ack:0", row, reference_path=oracle)
    out = Q.capability_report(p.manifest, [json.loads(row.read_text())], tmp_path / "capability.json", reference_path=oracle)
    report = json.loads((tmp_path / "capability.json").read_text())
    assert out["status"] == report["status"] != "PASS" and report["official_protocol_report"]["observed_denominator"] == 1
    assert report["envelope"] == {"max_obligations": 1, "work_classes": ["PROTOCOL_DIAGNOSIS"]}
    assert report["identity_sha256"] == C.key(p.manifest["identity"])
    assert [o["sha256"] for o in report["independent_oracle_refs"]] == [sha256_file(oracle), audit["sha256"]]
    with pytest.raises(Refused, match="CAPABILITY_NOT_INDEPENDENTLY_QUALIFIED"):
        C.record(p.manifest["identity"], report_path=out["path"], report_sha256=out["sha256"],
                 expected_manifest_sha256=digest(p.manifest))
    bad = tmp_path / "model-oracle.json"
    bad.write_text(json.dumps({"producer": "MODEL"}))
    with pytest.raises(Refused, match="AUDIT_REFERENCE_ORACLE_INVALID"):
        Q.capability_report(p.manifest, [json.loads(row.read_text())], tmp_path / "other.json", reference_path=bad)
