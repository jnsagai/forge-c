"""Public unit/trace integration of the existing WWDG target observation."""
import json

import pytest
from forge_factory.common import sha256_file
from forge_factory.inspection import swtrace
from forge_factory.mcp.servers import evidence
from forge_factory.mcp.servers import tests as U
from forge_factory.workflow import unit_target_observation as O
from test_unit_target_observation import actual, ctx, write
from test_unit_target_observation import ws as observation_ws  # noqa: F401 - shared fixture


@pytest.fixture
def ws(observation_ws):  # noqa: F811 - shared fixture
    ws = observation_ws
    device = ws / "inputs/vendor/include/stm32n6xx.h"
    device.write_text("#ifndef CONTROL_DEVICE_H\n#define CONTROL_DEVICE_H\n" + device.read_text() + "\n#endif\n")
    manifest = ws / ".forge-run/manifest.json"
    man = json.loads(manifest.read_text())
    man["provided_build"]["files"][0]["sha256"] = sha256_file(device)
    manifest.write_text(json.dumps(man))
    unit = ws / "workproducts/SWE.3/unit_specifications.md"
    unit.write_text("## SWU-HAL-04: Clear flag\n- SWC: SWC_HAL\n- Functions: " + O.FUNCTION +
                    "\n- **USPEC-HAL-04-03** " + O.BEHAVIOUR + " Traces: SWR-033, SWR-034\n")
    plan = ws / "workproducts/SWE.4/unit_test_plan.json"
    value = json.loads(plan.read_text())
    value["unit_specification"]["sha256"] = sha256_file(unit)
    plan.write_text(json.dumps(value))
    return ws


@actual
def test_public_unit_operation_observes_real_flag_and_supports_planned_row(ws):
    context = ctx(ws)
    result = U.run_unit(context, U.RunIn(coverage=False))
    assert result["status"] == "PASS", result
    assert result["metrics"]["observation_ut_passed"] == 1
    tested = O.verify(ws, result)
    assert tested[0]["observed"]["sr_before"] == 1 and tested[0]["observed"]["sr_after"] == 0
    write(ws, "evidence/tool-results.jsonl", json.dumps({"op": "run_unit", "result": result}) + "\n")
    assert O.trace(ws)[1] == {"UT-021": "PASS"}
    assert evidence._plan_findings(ws) == ([], 1)
    progress = json.loads(U.progress_path(ws, "SWE.4", "run_unit").read_text())
    assert (progress["total"], progress["done"], progress["passed"]) == (1, 1, 1)


@actual
def test_actual_failed_predicate_is_recorded_for_test_change_protection(ws):
    source = ws / "software/hal/stm32n6xx_hal_wwdg.c"
    source.write_text(source.read_text().replace("LL_WWDG_ClearFlag_EWKUP(WWDG);", ""))
    result = U.run_unit(ctx(ws), U.RunIn(coverage=False))
    assert result["status"] == "FAIL" and result["metrics"]["observation_ut_failed"] == 1
    records = [json.loads(line) for line in (ws / "evidence/test-integrity.jsonl").read_text().splitlines()]
    assert O.DECLARATION in records[-1]["assert_failed"]


@actual
def test_host_and_target_cannot_duplicate_clear_flag_unit(ws):
    write(ws, "software/tests/unit/test_duplicate.c", '#include <stdio.h>\n'
          '#define CHECK(ID,C) do { printf("%s %s\\n",ID,(C)?"PASS":"FAIL"); } while(0)\n'
          'int main(void) { CHECK("UT-021",1); return 0; }\n')
    result = U.run_unit(ctx(ws), U.RunIn(coverage=False))
    assert result["status"] == "FAIL" and any("DUPLICATE_TEST_ID:UT-021" in i for i in result["issues"])


def test_invalid_scope_never_supplies_a_passing_empty_suite(ws):
    write(ws, O.DECLARATION, {**O.CASE, "scenario": "invented-register-model"})
    result = U.run_unit(ctx(ws), U.RunIn(coverage=False))
    assert result["status"] == "FAIL" and result["metrics"]["observation_ut_passed"] == 0


@actual
def test_actual_target_execution_is_accepted_by_matrix4(ws):
    reqs = ws / "workproducts/SWE.1/software_requirements.md"
    reqs.write_text(reqs.read_text() + "- **SWR-033** Preserve other writable fields when clearing the flag.\n")
    result = U.run_unit(ctx(ws), U.RunIn(coverage=False))
    assert result["status"] == "PASS", result
    write(ws, "evidence/tool-results.jsonl", json.dumps({"op": "run_unit", "result": result}) + "\n")
    report = swtrace.build_all(ws, upto="SWE.4", render=False, doxygen=False, export=False, write={4})
    assert report["findings"]["SWE.4"] == [], report["findings"]["SWE.4"]
