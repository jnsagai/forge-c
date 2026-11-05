"""Real preparation/request boundaries obey the sealed dependency graph; no inference."""
# ruff: noqa: F811
import json
import time

import pytest
from forge_factory.afo import diagnosis_packet as P
from forge_factory.afo import durable_agent as D
from forge_factory.afo import local_agent as L
from forge_factory.afo.durable import Refused, canonical
from forge_factory.afo.mission_ledger import MissionLedger
from test_afo_local_autonomy import local  # noqa: F401
from test_afo_m4_recovery import order  # noqa: F401
from test_da014_protocol import protocol  # noqa: F401


def graph_case(local, tmp_path, dependencies=None):
    store, order, bundle, eff, ws, _ = local
    source = ws / "workproducts/SWE.3/contract.md"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text("Primary contract: prerequisite first. Global constraint: preserve both effects.\n")
    dependencies = dependencies if dependencies is not None else {"AAA-DEPENDENT": ["ZZZ-PREREQUISITE"],
                                                               "ZZZ-PREREQUISITE": []}
    ref = P.seal(ws, bundle,
                 [{"id": oid, "obligation_id": oid, "detail": f"Independent counterexample for {oid}."}
                  for oid in dependencies],
                 [{"path": "workproducts/SWE.3/contract.md"}], dependencies=dependencies,
                 required_obligations=[*dependencies, "REQ-GLOBAL-3"])
    packet = P.load(ref)
    case = tmp_path / "dependency-case.json"
    case.write_text(json.dumps({"bundle": bundle, "workspace": str(ws), "packet_ref": ref,
                                "mission_id": "dependency-control"}))
    job = {"case": str(case), "role": "afo-recovery-planner", "model": "qwen3.6:35b-a3b",
           "profile": "local-rtx-v2-omniverse2"}
    return job, packet, case


@pytest.mark.parametrize("step", [None, 1, 2, 3, 4])
def test_actual_request_selects_prerequisite_and_preserves_global_inventory(local, tmp_path, step):
    job, packet, case = graph_case(local, tmp_path)
    before = canonical(packet), case.read_bytes()
    prior = {"question_1_answer": {"conflict": "YES", "evidence_refs": ["F1"], "rationale": "Effect conflict."},
             "question_2_answer": {"technique_id": "repair-implementation"},
             "question_3_answer": {"strategy": "REWORK_LOCAL", "owner_phase": "SWE.3"}}
    body, measured = D.request_material(job, step=step, prior=prior)
    doc = json.loads(body["messages"][1]["content"])
    context = doc["diagnosis_context"]
    assert context["selected_incident_unit_ids"] == ["ZZZ-PREREQUISITE"]
    assert context["global_unit_dependencies"] == {k: v["dependencies"] for k, v in packet["obligations"].items()}
    assert set(context["required_requirement_ids"]) == {*packet["obligations"], "REQ-GLOBAL-3"}
    if step in (None, 1):
        assert doc["packet"]["remaining_obligations"] == ["AAA-DEPENDENT"]
        assert doc["primary_sources"][0]["text"].startswith("Primary contract:")
        assert doc["packet"]["global_constraints"] == packet["global_constraints"]
    assert measured["serialized_bytes"] > 0
    assert before == (canonical(P.load(json.loads(case.read_text())["packet_ref"])), case.read_bytes())


def test_actual_prepare_persists_same_prerequisite_without_resetting_original_reservation(local, tmp_path):
    store, order, bundle, eff, ws, _ = local
    _, packet, case = graph_case(local, tmp_path)
    ledger = MissionLedger(store)
    deadline = time.time() + 600
    limits = dict(max_attempts=3, max_jobs=2, max_requests=8, max_tokens=64000, max_tools=4,
                  max_corrections=1, deadline=deadline)
    ledger.register("dependency-control", "dependency-control-lineage", limits, "TEST-AUTH",
                    authorize=lambda *a: True)
    ledger.link("dependency-control", order["order_id"])
    job = L.prepare(store, order, bundle["attempt_id"], "afo-recovery-planner", case, ws, eff)
    assert job["selected_obligations"] == ["ZZZ-PREREQUISITE"]
    snapshot = ledger.snapshot("dependency-control")
    assert snapshot["jobs"] == 1 and snapshot["charged_tokens"] == job["reserved_tokens"]
    body, _ = D.request_material(job)
    assert json.loads(body["messages"][1]["content"])["diagnosis_context"]["selected_incident_unit_ids"] == job["selected_obligations"]
    assert L.prepare(store, order, bundle["attempt_id"], job["role"], case, ws, eff) == job
    assert ledger.snapshot("dependency-control") == snapshot
    assert P.partition(packet, max_bytes=100000)[0]["obligation_id"] == job["selected_obligations"][0]


@pytest.mark.parametrize("selected", [["AAA-DEPENDENT"], ["UNKNOWN"], [], "ZZZ-PREREQUISITE",
                                      ["AAA-DEPENDENT", "ZZZ-PREREQUISITE"]])
def test_explicit_invalid_or_unready_scope_never_serializes(local, tmp_path, selected):
    job, _, _ = graph_case(local, tmp_path)
    with pytest.raises(Refused):
        D.request_material({**job, "selected_obligations": selected,
                            "completed_obligations": {"ZZZ-PREREQUISITE": {"result": "PASS"}}})


@pytest.mark.parametrize("dependencies", [
    {"READY": [], "CYCLE-A": ["CYCLE-B"], "CYCLE-B": ["CYCLE-A"]},
    {"READY": [], "LATER": ["MISSING"]},
    {"READY": [], "SELF": ["SELF"]},
])
def test_disconnected_invalid_graph_refuses_even_when_one_root_is_ready(local, tmp_path, dependencies):
    job, packet, _ = graph_case(local, tmp_path, dependencies)
    with pytest.raises(Refused, match="OBLIGATION_DEPENDENCY_MISSING_OR_CYCLIC"):
        D.request_material({**job, "selected_obligations": ["READY"]})
    with pytest.raises(Refused, match="OBLIGATION_DEPENDENCY_MISSING_OR_CYCLIC"):
        P.partition(packet, max_bytes=100000)


def test_an_explicit_independent_root_is_allowed_without_calling_it_completed(local, tmp_path):
    job, _, _ = graph_case(local, tmp_path, {"A": [], "Z": [], "DEPENDENT": ["A"]})
    body, _ = D.request_material({**job, "selected_obligations": ["Z"]})
    doc = json.loads(body["messages"][1]["content"])
    assert doc["diagnosis_context"]["selected_incident_unit_ids"] == ["Z"]
    assert doc["packet"]["remaining_obligations"] == ["A", "DEPENDENT"]


def test_empty_inventory_refuses_before_request_serialization(local, tmp_path):
    job, _, _ = graph_case(local, tmp_path, {})
    with pytest.raises(Refused, match="COHERENT_OBJECTIVE_REQUIRED"):
        D.request_material(job)


@pytest.mark.parametrize("dependencies", [{}, {"A": ["MISSING"]},
                                          {"A": ["B"], "B": ["A"]}])
def test_invalid_prepare_charges_no_job_or_new_allowance(local, tmp_path, dependencies):
    store, order, bundle, eff, ws, _ = local
    _, _, case = graph_case(local, tmp_path, dependencies)
    ledger = MissionLedger(store)
    ledger.register("dependency-control", "dependency-control-lineage",
                    dict(max_attempts=3, max_jobs=2, max_requests=8, max_tokens=64000, max_tools=4,
                         max_corrections=1, deadline=time.time() + 600), "TEST-AUTH", authorize=lambda *a: True)
    ledger.link("dependency-control", order["order_id"])
    before = ledger.snapshot("dependency-control")
    with pytest.raises(Refused):
        L.prepare(store, order, bundle["attempt_id"], "afo-recovery-planner", case, ws, eff)
    assert ledger.snapshot("dependency-control") == before
    assert L.records(store, order["order_id"]) == []


def test_broker_refuses_a_legacy_dependent_job_even_without_new_request(protocol, tmp_path):
    from forge_factory.afo.completion_receipt import Context, Receipts
    from forge_factory.common import sha256_file

    p = protocol
    ref = P.seal(p.ws, p.bundle,
                 [{"id": "dependent", "obligation_id": "USPEC-001", "detail": "Dependent counterexample"},
                  {"id": "root", "obligation_id": "ZZZ", "detail": "Unresolved prerequisite"}],
                 [{"path": p.source.relative_to(p.ws).as_posix()}], dependencies={"USPEC-001": ["ZZZ"]})
    case = tmp_path / "legacy-dependent.json"
    case.write_text(json.dumps({"packet_ref": ref}))
    legacy = {**p.job, "case": str(case), "case_sha256": sha256_file(case), "selected_obligations": ["USPEC-001"]}
    with p.store.tx() as c:
        c.execute("UPDATE afo_local_agent_jobs SET record=? WHERE job_id=?", (json.dumps(legacy), legacy["job_id"]))
    broker = Receipts(p.store)
    stored = broker.submit(Context.from_job(p.store, legacy["job_id"]), p.proposal)
    assert stored["submission_state"] == "STORED"
    rejected = broker.admit(stored["receipt_id"], packet=P.load(ref), bundle=p.bundle, eff=p.eff, authorize=lambda: True)
    assert rejected["admissibility_state"] == "REJECTED"
    assert rejected["reason_codes"] == ["OBLIGATION_DEPENDENCY_UNSATISFIED"]
    assert rejected["bound_plan"] is None
    with pytest.raises(Refused):
        broker.request_dispatch(stored["receipt_id"], authorize=lambda: True)
