"""Two-question diagnosis (owner 2026-10-25: split the decision); typed provider answers, zero model calls."""
# ruff: noqa: F811

import copy
import json

import pytest
from forge_factory.afo import diagnosis_packet as P
from forge_factory.afo import qualification as Q
from forge_factory.afo import semantic_proposal as S
from forge_factory.afo.completion_receipt import Context, Receipts
from forge_factory.afo.durable import Refused, schema
from forge_factory.afo.durable_agent import dealias, ref_aliases, request_material, two_step_answer
from jsonschema import Draft202012Validator
from test_afo_local_autonomy import local  # noqa: F401
from test_afo_m4_recovery import order  # noqa: F401
from test_da014_protocol_faults import bind
from test_da014_qualification_reservations import signed  # noqa: F401

AUTHORITY = Draft202012Validator(schema("semantic-proposal"))


def two_step_job(p, name="lost-launch-ack"):
    job, _, packet = bind(p, name)
    job = copy.deepcopy(job)
    job["qualification_identity"] = {**job["qualification_identity"], "task_class": S.TWO_STEP}
    return job, packet, ref_aliases(packet)


def answers(*contents):
    calls = []

    def send(body, measured, index):
        calls.append((index, body["response_format"]["json_schema"]["name"], body))
        return {"choices": [{"message": {"content": json.dumps(contents[index])}}]}

    return send, calls


def repair(aliases_seen):
    return {
        "proposed_change": "Use UINT32_C(1) as the EN mask in reg_enable.",
        "material_difference": "Sets the required bit 0 instead of bit 1.",
        "technique_id": "repair-implementation",
        "strategy": "REWORK_LOCAL",
        "affected_phase": "SWE.3",
        "target_obligations": ["USPEC-001"],
        "artifact_scope": ["software/hal"],
        "validation_expectations": [{"test_ref": "gate:SWE.3:route=PASS", "expected_result": "PASS"}],
    }


def test_question_schemas_only_offer_this_cases_references_and_catalogue(signed):
    p = signed
    job, packet, aliases = two_step_job(p)
    body, measured = request_material(job, step=1)
    wire = body["response_format"]["json_schema"]["schema"]
    assert measured["two_step_question"] == 1 and body["response_format"]["json_schema"]["name"] == "diagnosis_conflict"
    for branch in wire["anyOf"]:
        assert list(branch["properties"])[:3] == ["rationale", "evidence_refs", "conflict"]
        assert set(branch["properties"]["evidence_refs"]["items"]["enum"]) == set(aliases.values())
    second = S.technique_schema(packet, packet["obligations"])
    assert set(second["anyOf"][0]["properties"]["technique_id"]["enum"]) == set(packet["techniques"])
    assert S.technique_schema({**packet, "techniques": {}}, packet["obligations"]) == {"anyOf": [second["anyOf"][-1]]}
    with pytest.raises(Refused, match="TWO_STEP_SECOND_QUESTION_REQUIRES_ESTABLISHED_CONFLICT"):
        request_material(job, step=2, prior={"conflict": "NO"})


def test_established_conflict_and_catalogued_technique_assemble_a_repair(signed):
    p = signed
    job, packet, aliases = two_step_job(p)
    finding, artifact = aliases[packet["findings"][0]["ref"]], aliases[packet["artifacts"][-1]["ref"]]
    first = {"rationale": "The contract requires mask 1; reg_enable uses mask 2.", "evidence_refs": [finding, artifact],
             "conflict": "YES"}
    send, calls = answers(first, repair(aliases))
    raw = two_step_answer(p.store, job, send)
    proposal = json.loads(dealias(job, raw))
    assert [c[:2] for c in calls] == [(0, "diagnosis_conflict"), (1, "diagnosis_technique")]
    assert json.loads(calls[1][2]["messages"][1]["content"])["question_1_answer"] == first
    assert proposal["decision"] == "PROPOSE_REPAIR" and proposal["causal_hypothesis"] == first["rationale"]
    assert AUTHORITY.is_valid(proposal)
    S.check(proposal, P.load(json.loads(p.case.read_text())["packet_ref"]))
    receipt = Receipts(p.store).submit(Context.from_job(p.store, job["job_id"]), dealias(job, raw))
    assert receipt["submission_state"] == "STORED" and receipt["decision"] == "PROPOSE_REPAIR"


@pytest.mark.parametrize(
    "first,second,decision,reason",
    [
        ({"conflict": "UNKNOWN", "missing_evidence": [
            {"obligation_ref": "USPEC-001", "evidence_kind": "AUTHORITATIVE_INPUT", "reason": "contract absent"}]},
         None, "NEEDS_EVIDENCE", None),
        ({"conflict": "NO"}, None, "CLOSE_BLOCKED", "UNSUPPORTED_HYPOTHESIS"),
        ({"conflict": "YES"}, {"explanation": "No listed technique applies.", "technique_id": "NONE"},
         "CLOSE_BLOCKED", "NO_ALLOWED_MATERIAL_STRATEGY"),
    ],
)
def test_other_answers_assemble_contract_valid_decisions_with_bounded_requests(signed, first, second, decision, reason):
    p = signed
    job, packet, aliases = two_step_job(p)
    first = {"rationale": "Stated comparison.", "evidence_refs": [aliases[packet["findings"][0]["ref"]]], **first}
    send, calls = answers(first, second)
    proposal = json.loads(dealias(job, two_step_answer(p.store, job, send)))
    assert proposal["decision"] == decision and proposal.get("blocking_reason") == reason
    assert AUTHORITY.is_valid(proposal)
    assert len(calls) == (2 if first["conflict"] == "YES" else 1)


def test_an_answer_outside_the_question_grammar_reaches_the_broker_unchanged(signed):
    p = signed
    job, _, _ = two_step_job(p)
    bad = {"conflict": "MAYBE", "evidence_refs": ["not-a-case-ref"], "rationale": "x"}
    send, calls = answers(bad)
    raw = two_step_answer(p.store, job, send)
    assert json.loads(raw) == bad and len(calls) == 1
    receipt = Receipts(p.store).submit(Context.from_job(p.store, job["job_id"]), raw)
    assert receipt["submission_state"] == "REJECTED"


def test_single_response_jobs_are_unchanged_and_mission_requests_follow_the_signed_task_class(signed):
    p = signed
    job, _, _ = bind(p, "lost-launch-ack")
    assert not S.two_step(job)
    assert Q.requests_per_job({"task_class": S.TWO_STEP}) == 2 and Q.requests_per_job({"task_class": "other"}) == 1
