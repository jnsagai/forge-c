"""Real target/Renode cost evidence and negative controls; all semantic/review fixtures remain explicit."""
import copy
import importlib.util
import json

import pytest
from forge_factory import provided_requirements as P
from forge_factory import simulation_performance as F
from forge_factory.brownfield.inject import inject
from forge_factory.common import REPO_ROOT, pretty_json
from forge_factory.inspection import assessment_context as C
from forge_factory.lrtx import swe1
from forge_factory.mcp import sdk
from forge_factory.mcp.servers import sim
from test_incremental_delivery import imported, prepared, reviewed_fixture  # noqa: F401

BUDGET = {"schema": F.SCHEMA, "instructions_per_call": 64, "microseconds_per_call": 100,
          "performance_mips": 100, "test_source": F.TEST}
TEST = '''#include "forge_performance_calls.h"
#include "forge_target_test.h"
FORGE_MAILBOX_DEFINE;
int main(void) {
 const uint32_t values[]={0U,0xffffffffU,0xaaaaaaaaU,0x55555555U,0x80000001U};
 FORGE_TEST_BEGIN();
 for(unsigned int i=0;i<5U;i++) {
  forge_measure_LL_CRC_Write_IDR(CRC,values[i]);
  TCHECK(1,CRC->IDR==values[i]);
  CRC->IDR=~values[i];
  TCHECK(2,forge_measure_LL_CRC_Read_IDR(CRC)==~values[i]);
 }
 FORGE_TEST_END();return 0;
}
'''


@pytest.fixture
def measured(prepared, request):  # noqa: F811
    ws, man = prepared
    man[F.FIELD] = copy.deepcopy(BUDGET)
    man[F.FIELD].update(getattr(request, "param", {}))
    man[C.FIELD] = C.binding(man)
    path = ws / man["provided_requirements"]["path"]
    doc = json.loads(path.read_text())
    doc["scope_sha256"] = P.scope_identity(man)
    path.chmod(0o644)
    path.write_text(pretty_json(doc))
    reviewed_fixture(ws, man)  # Synthetic review of new performance allocations, NEVER the real owner review.
    ws, man = imported((ws, man))
    assert inject(ws)["status"] == "INJECTED"
    test = ws / F.TEST
    test.parent.mkdir(parents=True, exist_ok=True)
    test.write_text(TEST)
    return ws, man


def test_new_allocations_have_project_provenance_and_reject_old_review(prepared):  # noqa: F811
    ws, man = prepared
    prior = P.scope_identity(man)
    man[F.FIELD] = BUDGET
    assert P.scope_identity(man) != prior
    (ws / ".forge-run/manifest.json").write_text(pretty_json(man))
    with pytest.raises(ValueError, match="SCOPE_CHANGED"):
        P.validate(ws)
    rows = swe1.budget_requirements(ws, "CRC LL driver")
    assert len(rows) == 5
    assert all(r["upstream"] == "WO-SIMULATION-PERFORMANCE" for r in rows[-2:])
    assert all("reference-manual" in r["source"] for r in rows[-2:])


@pytest.mark.parametrize("change", [{"instructions_per_call": True}, {"microseconds_per_call": 0},
                                   {"performance_mips": -1}, {"test_source": "../arbitrary.c"}, {"extra": 1}])
def test_bad_performance_allocations_refuse(change):
    with pytest.raises(ValueError, match="BUDGET_INVALID"):
        F.validate({**BUDGET, **change})


def test_real_simulator_reports_each_function_and_robot_uses_the_measurement(measured, monkeypatch):
    ws, _ = measured
    monkeypatch.setenv("FORGE_MCP_TRUST", "env")
    monkeypatch.setenv("FORGE_WORKSPACE", str(ws))
    monkeypatch.setenv("FORGE_ROLE", "swe5-author")
    monkeypatch.setenv("FORGE_PHASE", "SWE.5")
    operation = next(op for op in sim.OPERATIONS if op.name == "run_renode")
    result = sdk.invoke("forge-sim-mcp", operation, {})
    assert result["status"] == "PASS", result
    report = F.verify_result(ws, result)
    assert report["status"] == "PASS" and report["hardware_wcet"] == "NOT_MEASURED"
    assert len(report["samples"]) == 2
    for samples in report["samples"].values():
        assert len(samples) == 5
        assert all(s == {"instructions": 2, "virtual_nanoseconds": 20} for s in samples)
    spec = importlib.util.spec_from_file_location("perf_robot", REPO_ROOT / "factory/sim/stm32n6/ForgeTarget.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    robot = module.ForgeTarget(str(ws))
    robot.run_target_scenario(F.TEST)
    robot.simulation_performance_should_meet_budget()
    robot.last["performance"]["status"] = "FAIL"
    with pytest.raises(AssertionError, match="no complete passing"):
        robot.simulation_performance_should_meet_budget()


def test_incomplete_and_over_budget_measurements_are_not_passes(measured):
    ws, _ = measured
    plan = {"symbols": ["forge_measure_LL_CRC_Write_IDR"]}
    assert F.report(ws, plan, "")["status"] == "FAIL"
    for text, code in [
        ("FORGE_PERF|forge_measure_LL_CRC_Write_IDR|BEGIN|10|100\n", "INCOMPLETE_CALL"),
        ("FORGE_PERF|forge_measure_LL_CRC_Write_IDR|BEGIN|10|100\n"
         "FORGE_PERF|forge_measure_LL_CRC_Write_IDR|END|75|750\n", "CALL_BUDGET_EXCEEDED"),
        ("FORGE_PERF|forge_measure_LL_CRC_Write_IDR|BEGIN|10|100\n"
         "FORGE_PERF|forge_measure_LL_CRC_Write_IDR|END|12|100\n", "VIRTUAL_CLOCK_ACCOUNTING_MISMATCH"),
    ]:
        result = F.report(ws, plan, text)
        assert result["status"] == "FAIL" and any(code in issue for issue in result["issues"])


def test_no_actual_calls_refuse_even_when_symbols_are_present(measured):
    ws, _ = measured
    with pytest.raises(ValueError, match="DIRECT_CALL_COVERAGE_MISSING"):
        F.plan(ws, "00000000 <forge_measure_LL_CRC_Write_IDR>:\n00000004 <forge_measure_LL_CRC_Read_IDR>:\n")


def test_measurement_plan_handles_a_different_driver_namespace(tmp_path):
    (tmp_path / ".forge-run/delivery").mkdir(parents=True)
    (tmp_path / ".forge-run/manifest.json").write_text(json.dumps({F.FIELD: BUDGET}))
    (tmp_path / ".forge-run/delivery/scope.json").write_text(json.dumps({"functions": [{"name": "LL_TIMER_GetState"}]}))
    plan = F.plan(tmp_path, "00000010 <forge_measure_LL_TIMER_GetState>:\n"
                 " 0: f000 f806 bl 10 <forge_measure_LL_TIMER_GetState>\n")
    assert plan["hooks"] == [("forge_measure_LL_TIMER_GetState", "BEGIN", 16),
                              ("forge_measure_LL_TIMER_GetState", "END", 4)]
    observed = F.report(tmp_path, plan, "FORGE_PERF|forge_measure_LL_TIMER_GetState|BEGIN|1|10\n"
                        "FORGE_PERF|forge_measure_LL_TIMER_GetState|END|3|30\n")
    assert observed["status"] == "PASS"  # Synthetic protocol fixture, not a TIMER product qualification.


def test_changed_inputs_refuse_before_execution(measured, tmp_path):
    ws, _ = measured
    source = ws / F.TEST
    elf = tmp_path / "test_performance.elf"
    built, _, errors = sim.build_image(ws, source, elf)
    assert built, errors
    source.write_text(source.read_text() + "\n/* changed after compile */\n")
    result, evidence = sim.run_image(sim.renode_bin(), elf, "default", tmp_path, ws)
    assert result is None and b"BUILD_INPUT_CHANGED" in evidence


@pytest.mark.parametrize("measured", [{"instructions_per_call": 1_000_000}], indirect=True)
def test_real_slow_probe_fails_time_budget_while_functional_checks_pass(measured, monkeypatch):
    ws, _ = measured
    from forge_factory.common import sha256_file

    original = F.prepare
    header = ws / "software/ll/stm32n6xx_ll_crc.h"
    before = sha256_file(header)

    def slow_probe(workspace, output):
        unit = original(workspace, output)
        text = unit.read_text().replace("{ LL_CRC_Write_IDR(",
                                       "{ for(volatile unsigned int i=0;i<100000U;i++) { __asm__ volatile(\"nop\"); } "
                                       "LL_CRC_Write_IDR(")
        assert text != unit.read_text()
        unit.write_text(text)  # Isolated generated probe mutant, never a change to the ST delivery.
        return unit

    monkeypatch.setattr(F, "prepare", slow_probe)
    monkeypatch.setenv("FORGE_MCP_TRUST", "env")
    monkeypatch.setenv("FORGE_WORKSPACE", str(ws))
    monkeypatch.setenv("FORGE_ROLE", "swe5-author")
    monkeypatch.setenv("FORGE_PHASE", "SWE.5")
    result = sdk.invoke("forge-sim-mcp", next(op for op in sim.OPERATIONS if op.name == "run_renode"), {})
    assert result["status"] == "FAIL" and result["metrics"]["failed"] == 0
    report = F.verify_result(ws, result)
    samples = report["samples"]["forge_measure_LL_CRC_Write_IDR"]
    assert samples and all(s["instructions"] < 1_000_000 and s["virtual_nanoseconds"] > 100_000 for s in samples)
    assert report["status"] == "FAIL" and sha256_file(header) == before


def test_nine_requirement_real_tool_anchor_and_tampered_proof_block_release(measured, monkeypatch, tmp_path):
    from forge_factory.release import finalize
    from incremental_idr_anchor import Anchor

    ws, man = measured
    anchor = Anchor(ws, monkeypatch)
    anchor.architecture()
    anchor.implementation()
    anchor.unit()
    anchor.integration()
    anchor.validation()
    checks, _, _ = finalize.derive_gates(ws, man["budgets"])
    assert checks["resource_budgets"]
    result = finalize.finalize(ws, "simulation-budget-provider-fixture")
    assert result["package_status"] == "READY_FOR_OFFLINE_REVIEW", result["gaps"]
    latest = finalize.latest(finalize.tool_results(ws), "forge-sim-mcp", "run_renode")["result"]
    proof_ref = latest["metrics"]["simulation_performance_report"]
    proof = ws / "evidence/raw" / (proof_ref.split(":")[-1] + ".json")
    proof.write_text(proof.read_text() + "\nCHANGED\n")
    assert not finalize.derive_gates(ws, man["budgets"])[0]["resource_budgets"]
    monkeypatch.setenv("FORGE_ARCHIVE_DIR", str(tmp_path / "tampered-proofs"))
    assert finalize.finalize(ws, "tampered-proof-fixture")["package_status"] == "BLOCKED"
