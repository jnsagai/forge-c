"""Bounded, value-free diagnostics for rejected semantic proposals (Omniverse2 2026-10-25: CONTRACT_INVALID only)."""
# ruff: noqa: F811

import json

from forge_factory.afo import semantic_proposal as S
from forge_factory.afo.completion_receipt import Context, Receipts
from test_afo_local_autonomy import local  # noqa: F401
from test_afo_m4_recovery import order  # noqa: F401
from test_da014_protocol_faults import bind
from test_da014_qualification_reservations import signed  # noqa: F401

SECRET = "SECRET-PROSE-THAT-MUST-NOT-BE-STORED"


def test_unparseable_output_reports_only_the_parse_code_and_size():
    out = S.diagnose('{"decision": "PROPOSE_REPAIR", ' + SECRET)
    assert out == {"bytes": len('{"decision": "PROPOSE_REPAIR", ' + SECRET), "parse": "INVALID_JSON"}


def test_missing_repair_fields_name_the_declared_branch_without_values():
    raw = json.dumps({"decision": "PROPOSE_REPAIR", "evidence_refs": ["r1"], "causal_hypothesis": SECRET, SECRET: 1})
    out = S.diagnose(raw)
    assert out["parse"] == "OK" and out["decision"] == "PROPOSE_REPAIR" and out["unknown_key_count"] == 1
    assert out["keys"] == ["causal_hypothesis", "decision", "evidence_refs"]
    branch = [i for i in out["issues"] if i.get("branch")]
    assert branch and {i["branch"] for i in branch} == {"PROPOSE_REPAIR"}
    assert any(i["validator"] == "required" for i in branch)
    assert SECRET not in json.dumps(out)


def test_wrong_types_report_the_schema_path():
    out = S.diagnose(json.dumps({"decision": "CLOSE_BLOCKED", "evidence_refs": "not-a-list", "blocking_reason": 3}))
    paths = {(i.get("branch"), i["path"], i["validator"]) for i in out["issues"]}
    # Property types are checked outside the decision branches; the declared branch adds its own failures.
    assert (None, "evidence_refs", "type") in paths and (None, "blocking_reason", "enum") in paths
    assert ("CLOSE_BLOCKED", "", "required") in paths
    assert all(i.get("branch") in (None, "CLOSE_BLOCKED") for i in out["issues"])


def test_invalid_decision_reports_every_branch_and_non_object_output():
    assert S.diagnose(json.dumps({"decision": SECRET}))["decision"] == "INVALID"
    assert {i.get("branch") for i in S.diagnose(json.dumps({"decision": SECRET}))["issues"]} >= set(S.DECISIONS)
    assert S.diagnose("[1, 2]")["type"] == "list"


def test_rejected_submission_stores_the_diagnostic_and_the_row_exposes_it(signed):
    from forge_factory.afo import qualification as Q

    p = signed
    job, _, _ = bind(p, "empty-output")
    raw = json.dumps({"decision": "PROPOSE_REPAIR", "evidence_refs": [], "proposed_change": SECRET})
    receipt = Receipts(p.store).submit(Context.from_job(p.store, job["job_id"]), raw)
    assert receipt["submission_state"] == "REJECTED" and receipt["reason_codes"] == ["CONTRACT_INVALID"]
    with p.store.tx() as c:
        stored = json.loads(c.execute("SELECT record FROM afo_semantic_proposals WHERE job_id=?", (job["job_id"],)).fetchone()[0])
    assert stored["diagnostic"]["decision"] == "PROPOSE_REPAIR" and SECRET not in json.dumps(stored)
    job.update(state="FAILED", error="NO_ACCEPTED_SEMANTIC_PROPOSAL", receipt_id=receipt["receipt_id"])
    row = Q.protocol_observation(p.store, p.manifest, "empty-output:0", job)
    assert row["observed"] == "REJECTED" and row["proposal_diagnostic"] == stored["diagnostic"]


VALID = [
    {
        "decision": "PROPOSE_REPAIR",
        "evidence_refs": ["ev-1"],
        "strategy": "REWORK_LOCAL",
        "target_obligations": ["USPEC-001"],
        "affected_phase": "SWE.3",
        "causal_hypothesis": "The implementation sets bit 1 instead of bit 0.",
        "technique_id": "repair-implementation",
        "material_difference": "Set the required EN bit",
        "proposed_change": "Use UINT32_C(1) as the EN mask",
        "artifact_scope": ["software/hal"],
        "validation_expectations": [{"test_ref": "gate:SWE.3:route=PASS", "expected_result": "PASS"}],
    },
    {
        "decision": "NEEDS_EVIDENCE",
        "evidence_refs": ["ev-1"],
        "missing_evidence": [{"obligation_ref": "SWR-001", "evidence_kind": "AUTHORITATIVE_INPUT", "reason": "absent"}],
    },
    {"decision": "CLOSE_BLOCKED", "evidence_refs": ["ev-1"], "blocking_reason": "OUT_OF_SCOPE", "explanation": "Out of scope."},
]


def test_wire_schema_is_closed_per_decision_and_free_of_unsupported_keywords():
    from jsonschema import Draft202012Validator

    wire = S.wire_schema()
    text = json.dumps(wire)
    assert '"not"' not in text and '"oneOf"' not in text and '"if"' not in text
    assert [b["properties"]["decision"]["const"] for b in wire["anyOf"]] == list(S.DECISIONS)
    for branch in wire["anyOf"]:
        assert branch["additionalProperties"] is False and set(branch["required"]) <= set(branch["properties"])
    Draft202012Validator.check_schema(wire)


def test_wire_schema_accepts_valid_answers_and_rejects_the_observed_one_key_answer():
    from forge_factory.afo.durable import schema
    from jsonschema import Draft202012Validator

    wire, authority = Draft202012Validator(S.wire_schema()), Draft202012Validator(schema("semantic-proposal"))
    for proposal in VALID:
        assert wire.is_valid(proposal) and authority.is_valid(proposal), proposal["decision"]
    assert not wire.is_valid({"decision": "PROPOSE_REPAIR"})
    # Fields of another decision are outside each closed branch, as in the authoritative contract.
    assert not wire.is_valid({**VALID[2], "proposed_change": "x"}) and not authority.is_valid({**VALID[2], "proposed_change": "x"})
    assert not wire.is_valid({**VALID[0], "explanation": "x"}) and not authority.is_valid({**VALID[0], "explanation": "x"})


def test_native_request_carries_the_wire_schema_and_the_broker_keeps_the_authority(signed):
    from forge_factory.afo.durable_agent import request_material

    p = signed
    job, _, _ = bind(p, "empty-output")
    body, measured = request_material(job)
    assert body["response_format"]["json_schema"]["schema"] == S.wire_schema()
    assert measured["wire_request_sha256"]
    raw = json.dumps({**VALID[0], "evidence_refs": ["not-in-case"]})
    assert Receipts(p.store).submit(Context.from_job(p.store, job["job_id"]), raw)["submission_state"] == "STORED"
