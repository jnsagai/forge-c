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


CHOICE = {"reason": "The implementation uses the wrong mask; repair it.", "technique_id": "repair-implementation"}
PLAN = {"strategy": "REWORK_LOCAL", "owner_phase": "SWE.3"}


def repair(aliases_seen):
    return {
        "proposed_change": "Use UINT32_C(1) as the EN mask in reg_enable.",
        "material_difference": "Sets the required bit 0 instead of bit 1.",
        "affected_phase": "SWE.3",
        "target_obligations": ["USPEC-001"],
        "artifact_scope": ["software/hal/reg32.c"],
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
    choice = S.technique_choice_schema(packet)
    # Flat, small questions: no anyOf around the repair fields (never produced by the local decoder).
    assert "anyOf" not in choice and list(choice["properties"]) == ["reason", "technique_id"]
    assert choice["properties"]["technique_id"]["enum"] == [*sorted(packet["techniques"]), "NONE"]
    assert S.technique_choice_schema({**packet, "techniques": {}})["properties"]["technique_id"]["enum"] == ["NONE"]
    assert "anyOf" not in json.dumps(S.repair_schema(packet["obligations"]))
    with pytest.raises(Refused, match="TWO_STEP_SECOND_QUESTION_REQUIRES_ESTABLISHED_CONFLICT"):
        request_material(job, step=2, prior={"question_1_answer": {"conflict": "NO"}})
    with pytest.raises(Refused, match="TWO_STEP_REPAIR_REQUIRES_CATALOGUED_TECHNIQUE"):
        request_material(job, step=3, prior={"question_1_answer": {"conflict": "YES"},
                                             "question_2_answer": {"technique_id": "NONE"}})


def test_established_conflict_and_catalogued_technique_assemble_a_repair(signed):
    p = signed
    job, packet, aliases = two_step_job(p)
    finding, artifact = aliases[packet["findings"][0]["ref"]], aliases[packet["artifacts"][-1]["ref"]]
    first = {"rationale": "The contract requires mask 1; reg_enable uses mask 2.", "evidence_refs": [finding, artifact],
             "conflict": "YES"}
    send, calls = answers(first, CHOICE, PLAN, repair(aliases))
    raw = two_step_answer(p.store, job, send)
    proposal = json.loads(dealias(job, raw))
    assert [c[:2] for c in calls] == [(0, "diagnosis_conflict"), (1, "diagnosis_technique_choice"),
                                      (2, "diagnosis_strategy"), (3, "diagnosis_repair")]
    fourth = json.loads(calls[3][2]["messages"][1]["content"])
    assert fourth["question_1_answer"] == first and fourth["question_2_answer"] == CHOICE and fourth["question_3_answer"] == PLAN
    assert "primary_sources" not in fourth and calls[1][2]["max_tokens"] == 512 and calls[3][2]["max_tokens"] == 1024
    # The scope offered is the responsible phase's case artifacts only (REWORK_LOCAL: the case phase SWE.3).
    scope = calls[3][2]["response_format"]["json_schema"]["schema"]["properties"]["artifact_scope"]["items"]["enum"]
    assert scope and all(path.startswith(("workproducts/SWE.3/", "software/")) for path in scope)
    assert "owner_phase" not in proposal and proposal["strategy"] == "REWORK_LOCAL"
    assert proposal["technique_id"] == "repair-implementation"
    assert proposal["decision"] == "PROPOSE_REPAIR" and proposal["causal_hypothesis"] == first["rationale"]
    assert AUTHORITY.is_valid(proposal)
    S.check(proposal, P.load(json.loads(p.case.read_text())["packet_ref"]))
    receipt = Receipts(p.store).submit(Context.from_job(p.store, job["job_id"]), dealias(job, raw))
    assert receipt["submission_state"] == "STORED" and receipt["decision"] == "PROPOSE_REPAIR"


@pytest.mark.parametrize(
    "first,choice,decision,reason",
    [
        ({"conflict": "UNKNOWN", "missing_evidence": [
            {"obligation_ref": "USPEC-001", "evidence_kind": "AUTHORITATIVE_INPUT", "reason": "contract absent"}]},
         None, "NEEDS_EVIDENCE", None),
        ({"conflict": "NO"}, None, "CLOSE_BLOCKED", "UNSUPPORTED_HYPOTHESIS"),
        ({"conflict": "YES"}, {"reason": "No listed technique applies.", "technique_id": "NONE"},
         "CLOSE_BLOCKED", "NO_ALLOWED_MATERIAL_STRATEGY"),
    ],
)
def test_other_answers_assemble_contract_valid_decisions_with_bounded_requests(signed, first, choice, decision, reason):
    p = signed
    job, packet, aliases = two_step_job(p)
    first = {"rationale": "Stated comparison.", "evidence_refs": [aliases[packet["findings"][0]["ref"]]], **first}
    send, calls = answers(first, choice)
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
    assert Q.requests_per_job({"task_class": S.TWO_STEP}) == 4 and Q.requests_per_job({"task_class": "other"}) == 1


def test_repair_question_offers_declared_tests_and_owner_phase_follows_the_strategy(signed):
    p = signed
    job, packet, aliases = two_step_job(p)
    wire = S.repair_schema(packet["obligations"], packet["tests"])
    item = wire["properties"]["validation_expectations"]["items"]["properties"]
    assert item["test_ref"]["enum"] == sorted(packet["tests"])
    plan = S.strategy_schema("SWE.3")
    assert "SWITCH_PREAPPROVED_MODEL_PROFILE" not in plan["properties"]["strategy"]["enum"]
    first = {"rationale": "SWE.2 specifies mask 2 against SWR-001.", "evidence_refs": [aliases[packet["findings"][0]["ref"]]],
             "conflict": "YES"}
    rework = S.assemble(first, CHOICE, repair(aliases), PLAN)
    assert "owner_phase" not in rework and AUTHORITY.is_valid(json.loads(dealias(job, json.dumps(rework))))
    upstream_plan = {"strategy": "RETURN_TO_OWNING_UPSTREAM_PHASE", "owner_phase": "SWE.2"}
    upstream = S.assemble(first, CHOICE, {**repair(aliases), "artifact_scope": ["workproducts/SWE.2/x.md"]}, upstream_plan)
    assert upstream["owner_phase"] == "SWE.2" and AUTHORITY.is_valid(json.loads(dealias(job, json.dumps(upstream))))
    body, _ = request_material(job, step=4, prior={"question_1_answer": first, "question_2_answer": CHOICE,
                                                    "question_3_answer": upstream_plan})
    assert json.loads(body["messages"][1]["content"])["tests"] == packet["tests"]
    offered = body["response_format"]["json_schema"]["schema"]["properties"]["artifact_scope"]["items"]
    # An upstream return is offered only the owner phase's artifacts, never the implementation file.
    assert "software/hal/reg32.c" not in json.dumps(offered)


def test_question_grammars_offer_only_contract_legal_phases_scopes_and_verdicts(signed):
    p = signed
    job, packet, aliases = two_step_job(p)
    paths = [a["path"] for a in packet["artifacts"]]
    wire = S.repair_schema(packet["obligations"], packet["tests"], phase="SWE.3", paths=paths)
    assert wire["properties"]["affected_phase"]["enum"] == ["SWE.3"]
    assert S.strategy_schema("SWE.3")["properties"]["owner_phase"]["enum"] == ["SWE.1", "SWE.2", "SWE.3"]
    assert wire["properties"]["artifact_scope"]["items"]["enum"] == sorted(set(paths))
    # An incomplete packet admits only NEEDS_EVIDENCE under the contract, so only UNKNOWN is offered.
    incomplete = S.conflict_schema({"F1", "A1"}, complete=False, obligations={"USPEC-001": {}})
    assert [b["properties"]["conflict"]["const"] for b in incomplete["anyOf"]] == ["UNKNOWN"]
    missing = incomplete["anyOf"][0]["properties"]["missing_evidence"]["items"]["properties"]["obligation_ref"]
    assert missing == {"enum": ["USPEC-001"]}
    body, _ = request_material(job, step=1)
    verdicts = [b["properties"]["conflict"]["const"] for b in body["response_format"]["json_schema"]["schema"]["anyOf"]]
    assert verdicts == (["YES", "NO", "UNKNOWN"] if packet["complete"] else ["UNKNOWN"])


def test_later_questions_repeat_only_the_cited_findings_and_citations_are_capped(signed):
    """b7ce315: four requests for the nine-finding case exceeded the frozen job envelope."""
    p = signed
    job, packet, aliases = two_step_job(p)
    first_wire = request_material(job, step=1)[0]["response_format"]["json_schema"]["schema"]
    assert all(b["properties"]["evidence_refs"]["maxItems"] == 6 for b in first_wire["anyOf"])
    cited = aliases[packet["artifacts"][0]["ref"]]  # cites an artifact, no finding
    body, _ = request_material(job, step=2, prior={"question_1_answer": {"rationale": "r", "evidence_refs": [cited],
                                                                         "conflict": "YES"}})
    assert json.loads(body["messages"][1]["content"])["findings"] == []
