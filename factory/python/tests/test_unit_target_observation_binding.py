"""Actual-plan-shaped CONTROL and real CPU execution; no live phase or model qualification."""
import copy
import json

import pytest
from forge_factory.common import canonical_json, sha256_file
from forge_factory.inspection import swtrace, uspec_plan
from forge_factory.mcp.servers import evidence
from forge_factory.mcp.servers import tests as U
from forge_factory.workflow import provided_ll_unit as P
from forge_factory.workflow import unit_target_observation as O
from forge_factory.workflow import unit_target_timing as T
from test_unit_target_observation import actual, ctx, record, write
from test_unit_target_observation import ws as legacy_ws  # noqa: F401 - shared fixture

CASE = {"schema": "forge-c/swe4-wwdg-target-observation/1", "ut": "UT-023", "uspec": "USPEC-HAL-04-03",
        "function": "HAL_WWDG_ClearEarlyWakeupFlag", "scenario": "wwdg-ewif-clear-v1"}
BEHAVIOUR = "Preserve other writable fields and reserved bits at reset values during writes."
OTHER = ("When writing a WWDG field, the WWDG driver shall preserve the other writable fields in that register "
         "except for fields explicitly changed by the requested operation as the driver's defined behaviour.")


@pytest.fixture
def ws(legacy_ws):  # noqa: F811 - shared fixture
    ws = legacy_ws
    req = ws / swtrace.REQS
    req.write_text(req.read_text() + "- **SWR-033** " + OTHER + "\n")
    unit = write(ws, swtrace.UNITS_MD, "## SWU-HAL-04: Clear flag\n- SWC: SWC_HAL\n"
                 "- Functions: HAL_WWDG_ClearEarlyWakeupFlag\n"
                 "- **USPEC-HAL-04-01** Write 0 to EWIF and return HAL_OK. Traces: SWR-014, SWR-015, SWR-035, SWR-036\n"
                 "- **USPEC-HAL-04-03** " + BEHAVIOUR + " Traces: SWR-033, SWR-034\n")
    # The actual 4I numbering has a separate nominal 021/0401 and preservation 023/0403.
    plan = {"schema": uspec_plan.SCHEMA, "tasks": [
        {"ut": "UT-021", "uspec": "USPEC-HAL-04-01", "unit": "SWU-HAL-04", "functions": [O.FUNCTION],
         "behaviour": "Write 0 to EWIF and return HAL_OK.", "swrs": ["SWR-014", "SWR-015", "SWR-035", "SWR-036"]},
        {"ut": "UT-023", "uspec": "USPEC-HAL-04-03", "unit": "SWU-HAL-04", "functions": [O.FUNCTION],
         "behaviour": BEHAVIOUR, "swrs": ["SWR-033", "SWR-034"]}],
        "unit_specification": {"path": swtrace.UNITS_MD, "sha256": sha256_file(unit)}}
    write(ws, uspec_plan.PLAN, plan)
    write(ws, O.DECLARATION, CASE)
    return ws


def test_exact_actual_row_binds_without_renumbering_or_relabeling_nominal(ws):
    assert O.declaration(ws) == CASE
    assert O.expected_tests(ws)[0] == {"id": "UT-023", "uspec": "USPEC-HAL-04-03", "function": O.FUNCTION,
                                     "file": O.DECLARATION, "status": "DECLARED_NOT_EXECUTED"}
    assert O.trace(ws)[1] == {}  # declaration is not credit
    write(ws, O.DECLARATION, {**CASE, "ut": "UT-021", "uspec": "USPEC-HAL-04-01"})
    with pytest.raises(O.ObservationError, match="FROZEN_PREDICATE_UNSUPPORTED"):
        O.declaration(ws)
    write(ws, O.DECLARATION, O.CASE)  # old literal pair does not bind the actual nominal row either
    with pytest.raises(O.ObservationError, match="FROZEN_PREDICATE_UNSUPPORTED"):
        O.declaration(ws)


def test_legacy_contract_cannot_admit_new_identifiers_or_behaviour(legacy_ws):  # noqa: F811 - shared fixture
    assert O.declaration(legacy_ws) == O.CASE
    for case, behaviour in [({**O.CASE, "ut": "UT-023"}, O.BEHAVIOUR), (O.CASE, BEHAVIOUR)]:
        plan = json.loads((legacy_ws / uspec_plan.PLAN).read_text())
        plan["tasks"][0].update(ut=case["ut"], behaviour=behaviour)
        write(legacy_ws, uspec_plan.PLAN, plan)
        write(legacy_ws, O.DECLARATION, case)
        with pytest.raises(O.ObservationError, match="FROZEN_PREDICATE_UNSUPPORTED"):
            O.declaration(legacy_ws)


def test_dynamic_alternate_authored_form_still_requires_the_parsed_domain(ws):
    unit = ws / swtrace.UNITS_MD
    unit.write_text(unit.read_text().replace(BEHAVIOUR, O.BEHAVIOUR))
    plan = json.loads((ws / uspec_plan.PLAN).read_text())
    plan["tasks"][1]["behaviour"] = O.BEHAVIOUR
    plan["unit_specification"]["sha256"] = sha256_file(unit)
    write(ws, uspec_plan.PLAN, plan)
    assert O.declaration(ws) == CASE
    assert O._binding(ws)["validation_domain"] == "parsed-frozen-uspec-v2"
    req = ws / swtrace.REQS
    req.write_text(req.read_text().replace(OTHER, "Preserve some other fields."))
    with pytest.raises(O.ObservationError, match="FROZEN_PREDICATE_UNSUPPORTED"):
        O.declaration(ws)


@pytest.mark.parametrize("field,value", [("ut", "UT-000"), ("ut", "UT-1000"), ("uspec", "USPEC-HAL-04-01"),
    ("function", "HAL_WWDG_Refresh"), ("scenario", "arbitrary-writes")])
def test_dynamic_scope_and_wrong_row_refuse(ws, field, value):
    write(ws, O.DECLARATION, {**CASE, field: value})
    with pytest.raises(O.ObservationError):
        O.declaration(ws)


@pytest.mark.parametrize("fault", ["duplicate_ut", "duplicate_uspec", "duplicate_spec", "wrong_function", "extra_swr",
                                  "wrong_unit", "forged_uspec", "negation", "symbolic_negation", "extra_condition",
                                  "unknown_synonym"])
def test_ambiguous_or_forged_semantics_cannot_bind(ws, fault):
    plan = json.loads((ws / uspec_plan.PLAN).read_text())
    row = plan["tasks"][1]
    if fault == "duplicate_ut":
        plan["closure"] = [copy.deepcopy(row)]
    elif fault == "duplicate_uspec":
        plan["closure"] = [{**row, "ut": "UT-099"}]
    elif fault == "duplicate_spec":
        unit = ws / swtrace.UNITS_MD
        unit.write_text(unit.read_text() + "\n## SWU-HAL-99: Duplicate\n- Functions: " + O.FUNCTION +
                        "\n- **USPEC-HAL-04-03** " + BEHAVIOUR + " Traces: SWR-033, SWR-034\n")
        plan["unit_specification"]["sha256"] = sha256_file(unit)
    elif fault == "wrong_function":
        row["functions"] = ["HAL_WWDG_Refresh"]
    elif fault == "extra_swr":
        row["swrs"].append("SWR-032")
    elif fault == "wrong_unit":
        row["unit"] = "SWU-HAL-01"
    elif fault == "forged_uspec":
        row["uspec"] = "USPEC-HAL-99-99"
        write(ws, O.DECLARATION, {**CASE, "uspec": row["uspec"]})
    else:
        old = row["behaviour"]
        row["behaviour"] = ({"negation": "Do not " + old, "symbolic_negation": "! " + old,
                             "extra_condition": old + " On every repeated clear call.",
                             "unknown_synonym": "Keep other writable fields and reserved bits at reset values during writes."}[fault])
        unit = ws / swtrace.UNITS_MD
        unit.write_text(unit.read_text().replace(old, row["behaviour"]))
        plan["unit_specification"]["sha256"] = sha256_file(unit)
    write(ws, uspec_plan.PLAN, plan)
    with pytest.raises(O.ObservationError, match="FROZEN_PREDICATE_UNSUPPORTED"):
        O.declaration(ws)


@pytest.mark.parametrize("swr", ["SWR-033", "SWR-034"])
def test_dynamic_path_requires_both_exact_frozen_requirement_clauses(ws, swr):
    path = ws / swtrace.REQS
    path.write_text(path.read_text().replace("**" + swr + "** When", "**" + swr + "** Not when"))
    with pytest.raises(O.ObservationError, match="FROZEN_PREDICATE_UNSUPPORTED"):
        O.declaration(ws)


def test_changed_frozen_unit_is_not_accepted_by_retained_plan(ws):
    path = ws / swtrace.UNITS_MD
    path.write_text(path.read_text() + "\nCHANGED\n")
    with pytest.raises(O.ObservationError, match="FROZEN_UNIT_CHANGED"):
        O.declaration(ws)


@actual
@pytest.mark.parametrize("ut", ["UT-023", "UT-901", "UT-902"])
def test_actual_dynamic_execution_uses_planned_ids_and_private_mailbox_checks(ws, ut):
    plan = json.loads((ws / uspec_plan.PLAN).read_text())
    plan["tasks"][1]["ut"] = ut
    write(ws, uspec_plan.PLAN, plan)
    write(ws, O.DECLARATION, {**CASE, "ut": ut})
    context = ctx(ws)
    fragment = O.run(context)
    assert fragment["status"] == "PASS", fragment
    result = record(ws, fragment, context)
    tested = O.verify(ws, result)[0]
    assert (tested["id"], tested["uspec"], tested["status"]) == (ut, "USPEC-HAL-04-03", "PASS")
    assert tested["observed"]["call_writes"] == [{"offset": 8, "value": 0}]
    assert tested["observed"]["sr_reserved_write_values_valid"] is True
    assert O.trace(ws)[1] == {ut: "PASS"}
    proof = json.loads(T._artifact(ws, result["artifact_refs"], result["metrics"][O.METRIC], "json"))
    assert proof["identity"]["case"]["ut"] == ut
    assert proof["identity"]["plan_binding"]["validation_domain"] == "parsed-frozen-uspec-v2"
    assert all(n > 999 for n in proof["identity"]["mailbox_checks"].values())
    proof["tests"][0]["id"] = "UT-021"
    ref = context.store(canonical_json(proof), "json")
    result["artifact_refs"].append(ref)
    result["metrics"][O.METRIC] = ref
    with pytest.raises(O.ObservationError, match="RESULT_CHANGED"):
        O.verify(ws, result)


@actual
def test_dynamic_public_unit_keeps_nominal_host_row_and_complete_plan_credit(ws):
    # Fresh CONTROL origin setup, before any execution or stored evidence.
    device = ws / "inputs/vendor/include/stm32n6xx.h"
    device.write_text("#ifndef CONTROL_DEVICE_H\n#define CONTROL_DEVICE_H\n" + device.read_text() + "#endif\n")
    manifest = json.loads((ws / ".forge-run/manifest.json").read_text())
    manifest.update(unit_verification="uspec-gtest-v1", hal_unit_isolation="ll-fake-v1")
    manifest["provided_build"]["files"][0]["sha256"] = sha256_file(device)
    write(ws, ".forge-run/manifest.json", manifest)
    write(ws, "software/tests/unit/test_nominal.cpp", P.MARKER + '\n#include <gtest/gtest.h>\nextern "C" {\n'
          '#include "stm32n6xx_hal_wwdg.h"\n}\n/** @test UT-021 @verifies USPEC-HAL-04-01 */\n'
          'TEST(Nominal, UT_021) { WWDG->SR=1U; EXPECT_EQ(HAL_WWDG_ClearEarlyWakeupFlag(),HAL_OK); '
          'EXPECT_EQ(WWDG->SR,0U); }\n')
    result = U.run_unit(ctx(ws), U.RunIn(coverage=False))
    assert result["status"] == "PASS", result
    assert result["metrics"]["observation_ut_passed"] == 1
    write(ws, "evidence/tool-results.jsonl", json.dumps({"op": "run_unit", "result": result}) + "\n")
    assert O.trace(ws)[1] == {"UT-023": "PASS"}
    assert evidence._plan_findings(ws) == ([], 2)
    progress = json.loads(U.progress_path(ws, "SWE.4", "run_unit").read_text())
    assert (progress["total"], progress["done"], progress["passed"]) == (2, 2, 2)


def test_guidance_selects_plan_instead_of_hardcoded_identifiers():
    from forge_factory.workflow import prompts as Q
    before = Q.ASSESSMENT["manifest"]
    try:
        Q.ASSESSMENT["manifest"] = {"layer": "HAL", "peripheral": "wwdg", "hal_unit_isolation": "ll-fake-v1",
            "unit_verification": "uspec-gtest-v1", "provided_build": {"style": "cmsis"}, "provided": [{}]}
        note = Q.unit_target_observation_note()
        assert "exact planned UT and USPEC" in note and "UT-021" not in note
        assert "zero readback alone" in note and "0xFFFFFFFE" in note
    finally:
        Q.ASSESSMENT["manifest"] = before
