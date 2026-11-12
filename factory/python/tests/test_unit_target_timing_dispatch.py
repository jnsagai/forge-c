"""Exercise the public unit operation and its actual sealed target results."""
import json

from forge_factory.mcp.servers import tests as U
from forge_factory.workflow import unit_target_timing as T
from test_unit_target_timing import actual, ctx, write, ws  # noqa: F401 - shared fixtures


@actual
def test_unit_operation_executes_and_binds_all_target_rows(ws):  # noqa: F811
    context = ctx(ws)
    out = U.run_unit(context, U.RunIn(coverage=False))
    assert out["status"] == "PASS", out
    assert out["metrics"]["timing_ut_passed"] == 3 and out["metrics"]["silicon_verified"] is False
    assert len(T.verify(ws, out)) == 3
    progress = json.loads(U.progress_path(ws, "SWE.4", "run_unit").read_text())
    assert (progress["total"], progress["done"], progress["passed"]) == (3, 3, 3)
    write(ws, "evidence/tool-results.jsonl", json.dumps({"op": "run_unit", "result": out}) + "\n")
    assert T.trace(ws)[1] == {"UT-001": "PASS", "UT-002": "PASS", "UT-003": "PASS"}


@actual
def test_failed_target_status_makes_public_unit_operation_fail(ws):  # noqa: F811
    p = ws / "software/hal/stm32n6xx_hal_crc.c"
    p.write_text(p.read_text().replace("return count == 64U ? HAL_OK : HAL_ERROR;", "return HAL_ERROR;"))
    out = U.run_unit(ctx(ws), U.RunIn(coverage=False))
    assert out["status"] == "FAIL", out
    assert out["metrics"]["timing_ut_failed"] >= 1
    assert any(t["status"] == "FAIL" for t in T.verify(ws, out))


def test_invalid_declaration_does_not_allow_an_empty_unit_suite_to_pass(ws):  # noqa: F811
    (ws / T.DECLARATION).write_text('{"schema":"invalid"}')
    out = U.run_unit(ctx(ws), U.RunIn(coverage=False))
    assert out["status"] == "FAIL" and out["metrics"]["timing_ut_passed"] == 0


@actual
def test_target_and_host_cannot_duplicate_a_planned_unit(ws):  # noqa: F811
    write(ws, "software/tests/unit/test_duplicate.c", '''#include "stm32n6xx_hal_crc.h"
#define CHECK(ID,C) ((void)(ID), (C))
int main(void) {
 const hal_crc_config_t config = {1U,0U,0U,0U,0U};
 return CHECK("UT-001", HAL_CRC_Init(&config) == HAL_OK) ? 0 : 1;
}
''')
    out = U.run_unit(ctx(ws), U.RunIn(coverage=False))
    assert out["status"] == "FAIL" and any("DUPLICATE_TEST_ID:UT-001" in i for i in out["issues"])


@actual
def test_changing_a_failed_timing_configuration_requires_a_test_defect(ws):  # noqa: F811
    p = ws / "software/hal/stm32n6xx_hal_crc.c"
    p.write_text(p.read_text().replace("config->polynomial & 1U", "config->polynomial == 1U"))
    calls = ws / "workproducts/SWE.2/api_calls.json"
    contract = json.loads(calls.read_text())
    valid = contract["calls"]["INIT_VALID"]
    contract["calls"]["INIT_OTHER_VALID"] = {"function": valid["function"],
        "args": [valid["args"][0].replace("0x04c11db7U", "1U")]}
    calls.write_text(json.dumps(contract))
    assert U.run_unit(ctx(ws), U.RunIn(coverage=False))["status"] == "FAIL"
    integrity = [json.loads(line) for line in (ws / "evidence/test-integrity.jsonl").read_text().splitlines()]
    assert T.DECLARATION in integrity[-1]["assert_failed"]
    declaration = json.loads((ws / T.DECLARATION).read_text())
    declaration["config"]["polynomial"] = 1
    write(ws, T.DECLARATION, declaration)
    result = U.run_unit(ctx(ws), U.RunIn(coverage=False))
    assert result["metrics"]["timing_ut_passed"] == 3  # actual target cases now pass
    assert result["status"] == "FAIL" and any(T.DECLARATION in i for i in result["issues"])
