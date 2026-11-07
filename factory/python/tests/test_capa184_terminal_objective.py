"""CAPA-184: the planner's single objective is the gate rejection that ended the attempt, not a hash-ordered old one."""
import pytest
from forge_factory.afo import diagnosis_packet as P
from forge_factory.afo.durable import Refused


def packet(obligations, findings):
    return {"obligations": {k: {"id": k, "dependencies": deps, "finding_refs": refs}
                            for k, (deps, refs) in obligations.items()},
            "findings": [{"ref": r, "id": i, "detail": d} for r, i, d in findings]}


def test_l90aa_shape_selects_the_gate_rejection_over_an_earlier_unit_failure():
    p = packet({"OBL-035863739bc938b91b5b": ([], ["f-unit"]), "OBL-326d944a4957990dba65": ([], ["f-author"]),
                "OBL-40ee06779e2049d433c3": ([], ["f-robot"])},
               [("f-unit", "run_unit:0", "TEST_FAIL:test_crc.cpp:exit1"),
                ("f-author", "author:0", "MISSING_REQUIRED_OUTPUT:workproducts/SWE.6/software_verification_report.md"),
                ("f-robot", "run_robot:3", "REQUIREMENT_NOT_OBSERVED:SWR-001")])
    assert P.select_obligation(p) == ["OBL-326d944a4957990dba65"]


def test_a_gate_rejection_with_an_unmet_prerequisite_waits_for_it():
    p = packet({"OBL-a": ([], ["f-unit"]), "OBL-b": (["OBL-a"], ["f-route"])},
               [("f-unit", "run_unit:0", "TEST_FAIL"), ("f-route", "route:0", "STUCK")])
    assert P.select_obligation(p) == ["OBL-a"]
    with pytest.raises(Refused, match="OBLIGATION_DEPENDENCY_UNSATISFIED"):
        P.select_obligation(p, ["OBL-b"])


def test_without_a_gate_rejection_the_order_is_unchanged():
    p = packet({"OBL-b": ([], ["f2"]), "OBL-a": ([], ["f1"])},
               [("f1", "run_unit:0", "TEST_FAIL"), ("f2", "cppcheck:1", "MISRA")])
    assert P.select_obligation(p) == ["OBL-a"]


def test_an_explicit_selection_is_still_honoured():
    p = packet({"OBL-a": ([], ["f1"]), "OBL-b": ([], ["f2"])},
               [("f1", "run_unit:0", "TEST_FAIL"), ("f2", "author:0", "MISSING")])
    assert P.select_obligation(p, ["OBL-a"]) == ["OBL-a"]
