"""Finite target-case controls, including actual CPU-only Renode execution; no model inference."""
import json
import shutil

import pytest
from forge_factory.common import sha256_file
from forge_factory.mcp.sdk import ToolContext
from forge_factory.mcp.servers import evidence, sim
from forge_factory.workflow import unit_target_timing as T


def write(ws, name, value):
    path = ws / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) if isinstance(value, (dict, list)) else value)
    return path


@pytest.fixture
def ws(tmp_path):
    budget = {"schema": "forge-c/simulation-performance-budget/1", "instructions_per_call": 2000,
              "microseconds_per_call": 1000, "performance_mips": 100,
              "test_source": "software/tests/target/test_performance.c"}
    write(tmp_path, ".forge-run/manifest.json", {"layer": "HAL", "peripheral": "crc", "simulation_performance": budget,
          "budgets": {"flash_bytes": 4096, "static_ram_bytes": 1024, "stack_bytes": 1024}})
    write(tmp_path, "configuration/system_names.json", ["CRC driver"])
    header = """#include <stdint.h>
typedef struct { uint32_t polynomial, polynomial_size, init_value, input_reverse, output_reverse; } hal_crc_config_t;
typedef enum { HAL_OK, HAL_ERROR } hal_status_t;
hal_status_t HAL_CRC_Init(const hal_crc_config_t *config);
hal_status_t HAL_CRC_Calculate(const uint32_t *buffer, uint32_t count, uint32_t *result);
hal_status_t HAL_CRC_Accumulate(const uint32_t *buffer, uint32_t count, uint32_t *result);
"""
    write(tmp_path, "software/hal/stm32n6xx_hal_crc.h", header)
    write(tmp_path, "software/hal/stm32n6xx_hal_crc.c", """#include "stm32n6xx_hal_crc.h"
hal_status_t HAL_CRC_Init(const hal_crc_config_t *config) { return config->polynomial & 1U ? HAL_OK : HAL_ERROR; }
hal_status_t HAL_CRC_Calculate(const uint32_t *buffer, uint32_t count, uint32_t *result) {
    volatile uint32_t value = 0U;
    for (uint32_t i = 0U; i < count; i++) { value ^= buffer[i]; }
    *result = value; return count == 64U ? HAL_OK : HAL_ERROR;
}
hal_status_t HAL_CRC_Accumulate(const uint32_t *buffer, uint32_t count, uint32_t *result) {
    volatile uint32_t value = *result;
    for (uint32_t i = 0U; i < count; i++) { value ^= buffer[i]; }
    *result = value; return count == 64U ? HAL_OK : HAL_ERROR;
}
""")
    unit = write(tmp_path, "workproducts/SWE.3/unit_specifications.md", "Frozen fixture USPEC inputs.\n")
    write(tmp_path, "workproducts/SWE.2/api_calls.json", {"calls": {"INIT_VALID": {
        "function": "HAL_CRC_Init", "args": ["&(const hal_crc_config_t){ .polynomial = 0x04c11db7U, "
            ".polynomial_size = 0U, .init_value = 0xffffffffU, .input_reverse = 0U, .output_reverse = 0U }"]}}})
    cases, tasks = [], []
    for n, fn in enumerate(T.FUNCTIONS, 1):
        ut, uspec = f"UT-{n:03d}", f"USPEC-HAL-{n:02d}-07"
        prefix = "For the specified valid configuration" if n == 1 else "For a 64-word buffer"
        text = f"{prefix} in the instrumented target simulation at 100 MIPS, execute at most 2000 instructions and use at most 1000 microseconds per call."
        cases.append({"ut": ut, "uspec": uspec, "function": fn, "word_count": 0 if n == 1 else 64, "expected_status": "HAL_OK"})
        tasks.append({"ut": ut, "uspec": uspec, "functions": [fn], "behaviour": text})
    unit.write_text("# Frozen fixture specifications\n\n" + "\n".join(
        f"## SWU-HAL-{n:02d}: {task['functions'][0]}\n- SWC: SWC_HAL\n"
        f"- Functions: {task['functions'][0]}\n- **{task['uspec']}** {task['behaviour']} Traces: SWR-001\n"
        for n, task in enumerate(tasks, 1)))
    write(tmp_path, "workproducts/SWE.4/unit_test_plan.json", {"tasks": tasks, "closure": [],
          "unit_specification": {"path": "workproducts/SWE.3/unit_specifications.md", "sha256": sha256_file(unit)}})
    write(tmp_path, T.DECLARATION, {"schema": T.SCHEMA, "config": {"polynomial": 0x04c11db7, "polynomial_size": 0,
          "init_value": 0xffffffff, "input_reverse": 0, "output_reverse": 0}, "cases": cases})
    return tmp_path


def ctx(ws):
    return ToolContext("forge-tests-mcp", "run_unit", "swe4-author", "SWE.4", ws, "fixture")


def record(ws, fragment, context):
    result = {k: fragment[k] for k in ("status", "metrics", "artifact_refs")}
    result["provenance"] = {"invocation_id": context.invocation_id}
    write(ws, "evidence/tool-results.jsonl", json.dumps({"op": "run_unit", "result": result}) + "\n")
    return result


def test_no_declaration_preserves_legacy(tmp_path):
    assert T.run(ctx(tmp_path)) is None
    assert T.trace(tmp_path) == ([], {}, [])


@pytest.mark.parametrize("change,code", [
    (lambda v: v["cases"][1].update(word_count=1), "ARGUMENT_OR_UNIT"),
    (lambda v: v["cases"].pop(), "CASES_INCOMPLETE"),
    (lambda v: v["cases"][1].update(ut="UT-001"), "CASE_INVALID"),
    (lambda v: v["cases"][1].update(function="HAL_CRC_Init"), "ARGUMENT_OR_UNIT"),
    (lambda v: v["cases"][1].update(expected_status="HAL_ERROR"), "CASE_INVALID"),
    (lambda v: v["config"].update(polynomial="0U); return 0;"), "CONFIG_INVALID"),
    (lambda v: v["config"].update(polynomial=0), "CONFIG_INVALID"),
])
def test_typed_argument_refusals(ws, change, code):
    value = T.declaration(ws)
    change(value)
    write(ws, T.DECLARATION, value)
    with pytest.raises(T.TimingError, match=code):
        T.declaration(ws)


def test_exact_frozen_budget_and_unit_hash(ws):
    plan = json.loads((ws / "workproducts/SWE.4/unit_test_plan.json").read_text())
    plan["tasks"][1]["behaviour"] = plan["tasks"][1]["behaviour"].replace("64-word", "1-word")
    write(ws, "workproducts/SWE.4/unit_test_plan.json", plan)
    with pytest.raises(T.TimingError, match="FROZEN_PREDICATE"):
        T.declaration(ws)


def test_valid_but_different_config_is_not_the_frozen_call(ws):
    value = T.declaration(ws)
    value["config"]["polynomial"] = 0x1021
    write(ws, T.DECLARATION, value)
    with pytest.raises(T.TimingError, match="CONFIG_NOT_FROZEN_CALL_ARGUMENTS"):
        T.declaration(ws)


def test_unit_hash_changed_refuses(ws):
    (ws / "workproducts/SWE.3/unit_specifications.md").write_text("Changed")
    with pytest.raises(T.TimingError, match="FROZEN_PLAN_CHANGED"):
        T.declaration(ws)


def test_declaration_never_supplies_passing_trace_or_planned_body(ws):
    assert T.trace(ws)[1] == {}
    issues, total = evidence._plan_findings(ws)
    assert total == 3 and any("NO_EXECUTED_UNIT_RUN" in i for i in issues)
    assert sum("PLANNED_TEST_MISSING" in i for i in issues) == 3


def test_harness_arguments_are_finite_and_real_return_is_observed(ws):
    text = T.harness(T.declaration(ws))
    assert "words[64]" in text and text.count("words, 64U, &result") == 2
    assert "TCHECK(1, HAL_CRC_Init(&config) == HAL_OK)" in text
    assert "instructions" not in text and "GTEST_SKIP" not in text


@pytest.mark.parametrize("which", ["provided", "vendor"])
def test_changed_approved_dependency_is_not_reapproved_by_current_hash(ws, which):
    ll = write(ws, "software/ll/stm32n6xx_ll_crc.h", "/* immutable provided LL */")
    vendor = write(ws, "inputs/vendor/include/vendor.h", "/* immutable vendor */")
    path = ws / ".forge-run/manifest.json"
    manifest = json.loads(path.read_text())
    manifest["provided"] = [{"path": str(ll.relative_to(ws)), "role": "provided_ll_driver", "sha256": sha256_file(ll)}]
    manifest["provided_build"] = {"style": "cmsis", "files": [{"path": str(vendor.relative_to(ws)), "sha256": sha256_file(vendor)}]}
    write(ws, ".forge-run/manifest.json", manifest)
    assert T.declaration(ws)
    (ll if which == "provided" else vendor).write_text("Changed")
    with pytest.raises(T.TimingError, match="APPROVED_INPUT_CHANGED"):
        T.declaration(ws)
    assert T.run(ctx(ws))["status"] == "FAIL"


def test_parent_symlink_cannot_relocate_header_inputs(ws):
    directory = ws / "software/hal"
    backup = ws / "hal-other"
    directory.rename(backup)
    directory.symlink_to(backup, target_is_directory=True)
    with pytest.raises(T.TimingError, match="INPUT_SYMLINK"):
        T.declaration(ws)


def test_parent_symlink_cannot_relocate_sealed_evidence(tmp_path):
    original = tmp_path / "elsewhere"
    original.mkdir()
    (tmp_path / "evidence").mkdir()
    (tmp_path / "evidence/raw").symlink_to(original, target_is_directory=True)
    ref = "artifact:sha256:" + "a"*64
    with pytest.raises(T.TimingError, match="INPUT_SYMLINK"):
        T._artifact(tmp_path, [ref], ref, "json")


def test_plan_spec_traversal_and_header_dependency_traversal_refuse(ws):
    path = ws / "workproducts/SWE.4/unit_test_plan.json"
    plan = json.loads(path.read_text())
    plan["unit_specification"]["path"] = "../outside.md"
    write(ws, "workproducts/SWE.4/unit_test_plan.json", plan)
    with pytest.raises(T.TimingError, match="PLAN_SPEC_PATH_INVALID"):
        T.declaration(ws)
    manifest = json.loads((ws / ".forge-run/manifest.json").read_text())
    manifest["provided"] = [{"path": "../outside.h", "role": "provided_ll_driver", "sha256": "a"*64}]
    write(ws, ".forge-run/manifest.json", manifest)
    with pytest.raises(T.TimingError, match="PROVIDED_LL_BINDING_INVALID"):
        T.declaration(ws)


actual = pytest.mark.skipif(not (sim.renode_bin() and shutil.which("arm-none-eabi-gcc")), reason="Arm/Renode unavailable")


@actual
def test_actual_renode_64_word_calls_are_sealed_and_planned(ws):
    from forge_factory.inspection.swtrace import build_all

    context = ctx(ws)
    before = {str(p.relative_to(ws)): p.read_bytes() for p in ws.rglob("*") if p.is_file()}
    fragment = T.run(context)
    assert fragment["status"] == "PASS", fragment
    result = record(ws, fragment, context)
    tests = T.verify(ws, result)
    assert [t["word_count"] for t in tests] == [0, 64, 64]
    assert all(t["status"] == "PASS" and t["observed_status_matches"] and len(t["samples"]) == 1 for t in tests)
    assert T.trace(ws)[1] == {"UT-001": "PASS", "UT-002": "PASS", "UT-003": "PASS"}
    assert evidence._plan_findings(ws) == ([], 3)
    matrix = build_all(ws, render=False, doxygen=False, upto="SWE.4", write=set(), export=False)
    assert matrix["findings"]["SWE.4"] == []
    assert all((ws / path).read_bytes() == data for path, data in before.items())
    assert not (ws / "software/tests/target").exists()  # generated harness never edits frozen workspace


@actual
def test_actual_functional_failure_never_becomes_timing_pass(ws):
    path = ws / "software/hal/stm32n6xx_hal_crc.c"
    path.write_text(path.read_text().replace("count == 64U ? HAL_OK", "count == 63U ? HAL_OK"))
    context = ctx(ws)
    fragment = T.run(context)
    assert fragment["status"] == "FAIL", fragment
    result = record(ws, fragment, context)
    tests = T.verify(ws, result)
    assert all(t["status"] == "FAIL" for t in tests[1:])
    assert all(t["observed_status_matches"] is False for t in tests[1:])
    assert any("TARGET_TIMING_NOT_VERIFIED" in i for i in evidence._plan_findings(ws)[0])


@actual
def test_actual_over_budget_and_stale_evidence_refuse(ws):
    manifest = json.loads((ws / ".forge-run/manifest.json").read_text())
    manifest["simulation_performance"]["instructions_per_call"] = 1
    write(ws, ".forge-run/manifest.json", manifest)
    plan = json.loads((ws / "workproducts/SWE.4/unit_test_plan.json").read_text())
    for task in plan["tasks"]:
        task["behaviour"] = task["behaviour"].replace("2000 instructions", "1 instructions")
    write(ws, "workproducts/SWE.4/unit_test_plan.json", plan)
    context = ctx(ws)
    fragment = T.run(context)
    assert fragment["status"] == "FAIL" and fragment["tests"], fragment
    result = record(ws, fragment, context)
    assert all(t["status"] == "FAIL" for t in T.verify(ws, result))
    path = ws / "software/hal/stm32n6xx_hal_crc.c"
    path.write_text(path.read_text() + "\n/* changed */")
    with pytest.raises(T.TimingError, match="BINDING_CHANGED"):
        T.verify(ws, result)
    assert T.trace(ws)[1] == {}


@actual
def test_actual_seals_reject_artifact_and_invocation_tampering(ws):
    from forge_factory.common import canonical_json

    context = ctx(ws)
    fragment = T.run(context)
    assert fragment["status"] == "PASS", fragment
    result = record(ws, fragment, context)
    result["provenance"]["invocation_id"] = "foreign-invocation"
    with pytest.raises(T.TimingError, match="BINDING_CHANGED"):
        T.verify(ws, result)
    result["provenance"]["invocation_id"] = context.invocation_id
    reference = result["metrics"][T.METRIC]
    proof_path = ws / "evidence/raw" / (reference.split(":")[-1] + ".json")
    proof = json.loads(proof_path.read_text())
    proof["observation"]["passed"] = 2
    new_ref = context.store(canonical_json(proof), "json")
    result["metrics"][T.METRIC] = new_ref
    result["artifact_refs"].append(new_ref)
    with pytest.raises(T.TimingError, match="STATUS_OBSERVATION_CHANGED"):
        T.verify(ws, result)
    proof_path.write_text("tampered")
    result["metrics"][T.METRIC] = reference
    with pytest.raises(T.TimingError, match="ARTIFACT_CHANGED"):
        T.verify(ws, result)


@actual
def test_latest_failed_or_missing_measurement_cannot_reuse_old_success(ws):
    context = ctx(ws)
    fragment = T.run(context)
    assert fragment["status"] == "PASS", fragment
    record(ws, fragment, context)
    assert T.trace(ws)[1]["UT-002"] == "PASS"
    write(ws, "evidence/tool-results.jsonl", json.dumps({"op": "run_unit", "result": {
        "status": "PASS", "metrics": {}, "artifact_refs": [], "provenance": {"invocation_id": "new"}}}) + "\n")
    assert T.trace(ws)[1] == {}
    assert evidence._plan_findings(ws)[0]
