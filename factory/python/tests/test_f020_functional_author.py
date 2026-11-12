"""Feature 020 T015 (US2, FR-014..FR-019): the structured functional-level SWE.1 author.

Task plan: one task per service group of the order's scope rule (the use cases that exercise its functions; for an LL
component the LL service group), one state-behaviour task and one HAL design-constraint task from the guideline input.
Packets are bounded: the input section index, the RM sections of the use cases' features, the guideline for the
design constraints and the functional-level skill reference - never a chapter text or delivered code. The answer
schema is contracts/functional-requirement.schema.json (its conditional rules are deterministic validators). Every
rule violation is rejected with the requirement key and the rule. Model calls are scripted (never a real model)."""
from __future__ import annotations

import copy
import json

import pytest
from f020_swe1 import MODEL, TASKS, answers, author, derive, prepared, trace
from forge_factory.common import REPO_ROOT

CONTRACT = json.loads((REPO_ROOT / "specs/020-usart-benchmark-pilot/contracts/functional-requirement.schema.json")
                      .read_text())
OWNER_PROFILE = "local-rtx-v2-omniverse2-ornith-think-afo-finite-review-20261104"


@pytest.fixture()
def ws(tmp_path, monkeypatch):
    return prepared(tmp_path, monkeypatch)


def test_task_plan_follows_the_scope_groups_state_and_guideline(ws):
    from forge_factory.lrtx import swe1_functional as F

    plan = F.plan(ws)
    assert [t["id"] for t in plan] == TASKS
    by = {t["id"]: t for t in plan}
    assert by["requirements:g_initialisation"]["functions"] == ["HAL_SER_Init", "HAL_SER_DeInit", "HAL_SER_MspInit"]
    assert by["requirements:g_initialisation"]["use_cases"] == ["UC-01"]
    assert by["requirements:g_ll_data_and_flags"]["functions"] == [
        "LL_SER_TransmitData", "LL_SER_ReceiveData", "LL_SER_IsActiveFlag_TXE", "LL_SER_IsActiveFlag_ORE",
        "LL_SER_ClearFlag_ORE"]
    assert by["requirements:g_blocking_transfer"]["features"] == ["42.3.1", "42.3.2"]
    assert all("HAL_SER_EnableLoop" not in t.get("functions", []) for t in plan)  # out of scope: no task
    assert by["requirements:state_behaviour"]["origins"] == ["state_behaviour", "awaiting_traceability"]
    assert by["requirements:design_constraints"]["guideline"] == ["IN-05"]


def test_packets_are_bounded_and_use_the_contract_schema(ws):
    from forge_factory.lrtx import swe1_functional as F

    req_schema = {k: v for k, v in CONTRACT.items() if k not in ("$schema", "title", "allOf")}
    for t in F.plan(ws):
        p = F.task_packet(ws, t, MODEL)
        assert p["role"] == "swe1-author" and p["task"] == t["id"] and p["accounting"]["fits"]
        assert p["output_schema"]["properties"]["requirements"]["items"] == req_schema
        paths = [s["path"] for s in p["sources"]]
        assert "inputs/RM9999-rev2-ch42-ser.md" not in paths  # never the chapter text
        assert not any(x.startswith("software/") or x.endswith("delivered-interface.json") for x in paths)
        assert ".fabro/skills/swe1-author/references/functional-level.md" in paths
        text = "\n".join(m["content"] for m in p["_messages"])
        for banned in ("static inline", "Address offset", "SER_TypeDef", "return HAL_OK;"):  # no code, no register text
            assert banned not in text, (t["id"], banned)
        assert "lessons_offered" not in p
    p = F.task_packet(ws, F.plan(ws)[1], MODEL)
    assert [s["path"] for s in p["sources"]][:3] == ["inputs/index.md", "inputs/sections/RM9999/42.3.1_Transmitter.md",
                                                     "inputs/sections/RM9999/42.3.2_Receiver.md"]
    d = F.task_packet(ws, F.plan(ws)[-1], MODEL)
    assert "inputs/hal_guideline.md" in [s["path"] for s in d["sources"]]


def test_the_template_config_yields_the_contract_schema(ws):
    from forge_factory.governance import level as L
    from forge_factory.lrtx import swe1_functional as F

    sch = F.requirement_schema(L.load_template("swe1-functional-v1"))
    assert sch == {k: v for k, v in CONTRACT.items() if k not in ("$schema", "title", "allOf")}


def _one(task: str, mutate) -> dict:
    a = copy.deepcopy(answers()[task])
    mutate(a["requirements"][0])
    return a


CASES = [
    ("requirements:g_blocking_transfer", lambda r: r.pop("test_level"), "TEMPLATE_ATTRIBUTE_MISSING"),
    ("requirements:g_blocking_transfer", lambda r: r.update(origin_group="awaiting_traceability"),
     "LINKS_ON_AWAITING"),
    ("requirements:g_blocking_transfer", lambda r: r.update(links=[]), "LINKS_MISSING"),
    ("requirements:g_blocking_transfer", lambda r: r.update(origin_group="state_behaviour"), "ORIGIN_GROUP_NOT_OF_TASK"),
    ("requirements:g_blocking_transfer", lambda r: r.update(links=[trace("IN-42", "42.3.1")]), "LINK_INPUT_UNKNOWN"),
    ("requirements:g_blocking_transfer", lambda r: r.update(links=[trace("IN-06", "HAL_SER_Transmit")]),
     "LINK_TO_DELIVERED_CODE"),
    ("requirements:g_blocking_transfer", lambda r: r.update(links=[trace("IN-02", "99.9")]), "LINK_LOCATOR_UNKNOWN"),
    ("requirements:g_blocking_transfer", lambda r: r.update(links=[derive("IN-02", "42.3.1", "")]),
     "DERIVE_WITHOUT_RATIONALE"),
    ("requirements:g_blocking_transfer", lambda r: r.update(use_cases=["UC-77"]), "USE_CASE_UNKNOWN"),
    ("requirements:g_blocking_transfer", lambda r: r.update(use_cases=[]), "USE_CASE_MISSING"),
    ("requirements:g_blocking_transfer", lambda r: r.update(
        statement="When HAL_SER_Transmit is called, the SER HAL driver shall send the data as ser_hal.c does."),
     "CODE_AS_SOURCE"),
    ("requirements:g_blocking_transfer", lambda r: r.update(
        statement="When HAL_SER_Transmit is called, the SER HAL driver shall write the data to SER_TDR."),
     "LEVEL_REGISTER_TERM"),
    ("requirements:g_ll_configuration", lambda r: r.update(
        statement="When LL_SER_Enable is called, the SER LL driver shall set the UE bit."), "LEVEL_REGISTER_TERM"),
    ("requirements:g_ll_data_and_flags", lambda r: r.update(
        statement="When LL_SER_TransmitData is called, the SER LL driver shall write the TDR member."),
     "LEVEL_REGISTER_TERM"),
    ("requirements:g_ll_data_and_flags", lambda r: r.update(
        statement="When LL_SER_ClearFlag_ORE is called, the SER LL driver shall write SER_ICR_ORECF."),
     "LEVEL_REGISTER_TERM"),
    ("requirements:g_ll_data_and_flags", lambda r: r.update(
        statement="When LL_SER_TransmitData is called, the SER LL driver shall write to address 0x40001010."),
     "LEVEL_HEX_VALUE"),
    ("requirements:g_initialisation", lambda r: r.update(
        statement="When HAL_SER_Init is called, the SER HAL driver shall leave the status at its reset value 0x0080."),
     "LEVEL_HEX_VALUE"),
    ("requirements:g_initialisation", lambda r: r.update(statement="The driver should initialise the interface."),
     "EARS_"),
    ("requirements:design_constraints", lambda r: r.update(verification_method="test"),
     "DESIGN_CONSTRAINT_NOT_BY_INSPECTION"),
    ("requirements:design_constraints", lambda r: r.update(type="functional"), "HAL_DESIGN_CONSTRAINT_TYPE"),
]


@pytest.mark.parametrize("task, mutate, rule", CASES, ids=[c[2] + f"-{i}" for i, c in enumerate(CASES)])
def test_each_rule_violation_is_rejected_with_key_and_rule(ws, task, mutate, rule):
    from forge_factory.lrtx import swe1_functional as F

    t = {x["id"]: x for x in F.plan(ws)}[task]
    assert F.validate_task(ws, answers()[task], t) == []
    a = _one(task, mutate)
    key = a["requirements"][0]["key"]
    errs = F.validate_task(ws, a, t)
    assert any(e.startswith(f"[{key}] {rule}") for e in errs), errs


def test_the_level_rule_names_its_term_source(ws):
    from forge_factory.lrtx import swe1_functional as F

    terms = F.level_terms(ws)
    assert terms["SER_CR"].startswith("RM register") and terms["ORECF"].startswith("RM field")
    assert terms["SER_ICR_ORECF"].startswith("CMSIS") and terms["TDR"]  # header symbol and register-block member
    assert "HAL_SER_Transmit" not in terms and "SER1" not in terms  # API names and instances are allowed


def test_visit_runs_every_task_and_passes(ws, monkeypatch):
    rep, calls = author(ws, monkeypatch)
    assert rep["status"] == "PASS", rep
    assert [p["task"] for p in calls] == TASKS
    rep2, calls2 = author(ws, monkeypatch)  # unchanged inputs: every validated task is reused, no model call
    assert rep2["status"] == "PASS" and calls2 == []


def test_an_invalid_answer_is_repaired_from_the_named_findings(ws, monkeypatch):
    by = answers()
    bad = _one("requirements:g_state", lambda r: r.update(
        statement="When HAL_SER_GetState is called, the SER HAL driver shall return the state from SER_ISR."))
    by["requirements:g_state"] = [bad, answers()["requirements:g_state"]]
    rep, calls = author(ws, monkeypatch, by)
    assert rep["status"] == "PASS"
    fixes = [p for p in calls if p["task"] == "requirements:g_state"]
    assert len(fixes) == 2 and any("[get_state] LEVEL_REGISTER_TERM" in f for f in fixes[1]["findings"])


def test_a_duplicate_statement_across_tasks_is_refused(ws, monkeypatch):
    by = answers()
    dup = copy.deepcopy(by["requirements:g_initialisation"]["requirements"][0])
    by["requirements:state_behaviour"]["requirements"].append({**dup, "origin_group": "state_behaviour",
                                                                "key": "dup"})
    rep, _calls = author(ws, monkeypatch, by)
    assert rep["status"] == "FAILED" and any("DUPLICATE_STATEMENT" in i for i in rep["issues"])


def test_without_a_passed_governance_package_the_author_refuses(tmp_path, monkeypatch):
    from forge_factory.lrtx import swe1_functional as F

    w = prepared(tmp_path, monkeypatch)
    st = w / ".forge-run/lrtx/SWE.1/governance/status.json"
    st.write_text(json.dumps({**json.loads(st.read_text()), "state": "COVERAGE_FAIL"}))
    rep = F.visit(w, MODEL)
    assert rep["status"] == "FAILED" and rep["issues"][0].startswith("SWE1_FUNCTIONAL_GOVERNANCE_NOT_PASSED")


def test_the_runner_selects_the_functional_author_only_for_functional_orders(ws, tmp_path):
    from forge_factory.lrtx import runner

    assert runner.author_module(ws, "author", "SWE.1") == "swe1_functional"
    reg = tmp_path / "reg"
    (reg / ".forge-run").mkdir(parents=True)
    (reg / ".forge-run/manifest.json").write_text(json.dumps({"layer": "LL"}))
    assert runner.author_module(reg, "author", "SWE.1") == "swe1"
    assert runner.author_module(ws, "author", "SWE.2") == "swe2"


def test_functional_orders_get_a_structured_swe1_regardless_of_the_profile_layers(tmp_path, monkeypatch):
    from forge_factory import workorder
    from forge_factory.workflow import builder

    monkeypatch.setenv("FORGE_LRTX_ROOT", str(tmp_path / "lrtx"))
    man = {"layer": "LL+HAL", "delivery": {"code_mode": "FROZEN", "build": {"style": "cmsis"}}}
    reg = workorder.local_profile_structured({"id": OWNER_PROFILE}, man, "m")
    assert "SWE.1" not in ((reg or {}).get("phases") or [])  # the profile gives LL+HAL no structured phase
    fun = workorder.local_profile_structured({"id": OWNER_PROFILE}, {**man, "swe1_level": "functional",
                                                                     "swe1_template": "swe1-functional-v1"}, "m")
    assert fun["phases"][0] == "SWE.1" and "SWE.1" in fun["inspect_phases"] and fun["two_phase_inspection"] is True
    g, _nodes = builder.build("WO-F020-S", layer="LL+HAL", trace=True, brownfield="FROZEN", delivery_style="cmsis",
                              stop_after="SWE.1", structured=fun,
                              assessment_manifest={"swe1_level": "functional", "swe1_template": "swe1-functional-v1"})
    assert "start -> swe1_governance" in g or "start -> swe1_governance_serve" in g
    assert "forge_factory.lrtx.runner author --phase SWE.1" in g and "swe1_iq_inspect" in g
