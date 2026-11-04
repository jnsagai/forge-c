"""Existing WWDG model observation controls. No model inference or production workspace writes."""
import base64
import copy
import json
import shutil

import pytest
from forge_factory.common import canonical_json, sha256_file
from forge_factory.mcp.sdk import ToolContext
from forge_factory.mcp.servers import sim
from forge_factory.workflow import unit_target_observation as O
from forge_factory.workflow import unit_target_timing as T


def write(ws, rel, value):
    path = ws / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value) if isinstance(value, dict) else value)
    return path


@pytest.fixture
def ws(tmp_path):
    # Separate fresh CONTROL origin: explicit zero preserves reserved reset bits
    # when writing. The original ST complement expression has its own negative.
    vendor = write(tmp_path, "inputs/vendor/include/stm32n6xx.h", """#include <stdint.h>
typedef struct { volatile uint32_t CR, CFR, SR; } WWDG_TypeDef;
#define WWDG ((WWDG_TypeDef *)0x50002C00U)
#define WWDG_CR_WDGA 0x80U
#define WWDG_SR_EWIF 1U
""")
    ll = write(tmp_path, "software/ll/stm32n6xx_ll_wwdg.h", """#include "stm32n6xx.h"
static inline void LL_WWDG_ClearFlag_EWKUP(WWDG_TypeDef *x) { x->SR = 0U; }
""")
    write(tmp_path, "software/hal/stm32n6xx_hal_wwdg.h", """#include "stm32n6xx_ll_wwdg.h"
typedef enum { HAL_OK, HAL_ERROR } hal_status_t;
hal_status_t HAL_WWDG_ClearEarlyWakeupFlag(void);
""")
    write(tmp_path, "software/hal/stm32n6xx_hal_wwdg.c", """#include "stm32n6xx_hal_wwdg.h"
hal_status_t HAL_WWDG_ClearEarlyWakeupFlag(void) { LL_WWDG_ClearFlag_EWKUP(WWDG); return HAL_OK; }
""")
    write(tmp_path, ".forge-run/manifest.json", {"layer": "HAL", "peripheral": "wwdg", "provided": [
        {"path": str(ll.relative_to(tmp_path)), "sha256": sha256_file(ll), "role": "provided_ll_driver"}],
        "provided_build": {"style": "cmsis", "files": [
            {"path": str(vendor.relative_to(tmp_path)), "sha256": sha256_file(vendor)}]}})
    write(tmp_path, "workproducts/SWE.1/software_requirements.md", "- **SWR-034** " + O.SWR + "\n")
    unit = write(tmp_path, "workproducts/SWE.3/unit_specifications.md", "Frozen CONTROL specification.\n")
    write(tmp_path, "workproducts/SWE.4/unit_test_plan.json", {"tasks": [
        {"ut": "UT-021", "uspec": "USPEC-HAL-04-03", "functions": [O.FUNCTION], "behaviour": O.BEHAVIOUR,
         "swrs": ["SWR-033", "SWR-034"]}], "unit_specification": {
             "path": "workproducts/SWE.3/unit_specifications.md", "sha256": sha256_file(unit)}})
    write(tmp_path, "workproducts/SWE.2/api_calls.json", {"calls": {"CLEAR": {"function": O.FUNCTION, "args": []}}})
    write(tmp_path, O.DECLARATION, O.CASE)
    return tmp_path


def ctx(ws):
    return ToolContext("forge-tests-mcp", "run_unit", "swe4-author", "SWE.4", ws, "CONTROL-WWDG")


def record(ws, fragment, context):
    result = {k: fragment[k] for k in ("status", "metrics", "artifact_refs")}
    result["provenance"] = {"invocation_id": context.invocation_id}
    write(ws, "evidence/tool-results.jsonl", json.dumps({"op": "run_unit", "result": result}) + "\n")
    return result


def test_absent_declaration_retains_default(tmp_path):
    assert O.run(ctx(tmp_path)) is None and O.trace(tmp_path) == ([], {}, [])
    assert O.expected_tests(tmp_path) == []


@pytest.mark.parametrize("field,value", [("ut", "UT-020"), ("uspec", "USPEC-HAL-04-01"),
                                        ("function", "HAL_WWDG_Refresh"), ("scenario", "fake-registers")])
def test_no_arbitrary_case_or_requirement(ws, field, value):
    case = copy.deepcopy(O.CASE)
    case[field] = value
    write(ws, O.DECLARATION, case)
    guard = "FROZEN_PREDICATE_UNSUPPORTED" if field in ("ut", "uspec") else "SCOPE_OR_CASE_INVALID"
    with pytest.raises(O.ObservationError, match=guard):
        O.declaration(ws)


def test_declaration_only_is_never_passing_evidence(ws):
    assert O.declaration(ws) == O.CASE
    assert O.trace(ws)[1] == {} and "NO_EXECUTED_UNIT_RUN" in O.trace(ws)[2][0]
    assert O.expected_tests(ws) == [{"id": "UT-021", "uspec": "USPEC-HAL-04-03", "function": O.FUNCTION,
                                   "file": O.DECLARATION, "status": "DECLARED_NOT_EXECUTED"}]


@pytest.mark.parametrize("rel", ["software/ll/stm32n6xx_ll_wwdg.h", "inputs/vendor/include/stm32n6xx.h"])
def test_changed_approved_inputs_refuse(ws, rel):
    (ws / rel).write_text("changed")
    with pytest.raises(T.TimingError, match="APPROVED_INPUT_CHANGED"):
        O.declaration(ws)
    assert O.run(ctx(ws))["status"] == "FAIL"


def test_frozen_predicate_and_unit_bytes_are_required(ws):
    write(ws, "workproducts/SWE.1/software_requirements.md", "- **SWR-034** Permit arbitrary reserved writes.\n")
    with pytest.raises(O.ObservationError, match="FROZEN_PREDICATE"):
        O.declaration(ws)
    (ws / "workproducts/SWE.3/unit_specifications.md").write_text("changed")
    with pytest.raises(O.ObservationError, match="FROZEN_UNIT_CHANGED"):
        O.declaration(ws)


def test_no_workspace_factory_harness_override(ws):
    write(ws, "software/hal/forge_target_test.h", "#define TCHECK(N,C) ((void)0)\n")
    with pytest.raises(O.ObservationError, match="HARNESS_SHADOWED"):
        O.declaration(ws)


def test_precondition_uses_model_counter_not_a_fabricated_SR_set():
    source = O.harness()
    assert "WWDG->SR =" not in source and "WWDG->CR = WWDG_CR_WDGA | 0x40U" in source
    assert "before = WWDG->SR" in source and "after = WWDG->SR" in source


def test_missing_observation_or_unraised_flag_cannot_pass():
    mailbox = {"magic_ok": True, "done": True, "passed": 3, "failed": 0, "failed_ids": []}
    with pytest.raises(O.ObservationError, match="INCOMPLETE"):
        O._observed(mailbox, [])
    access = [{"phase": 1, "access": "R", "offset": 8, "value": 0},
              {"phase": 2, "access": "W", "offset": 8, "value": 0xfffffffe},
              {"phase": 3, "access": "R", "offset": 8, "value": 0}]
    assert O._observed(mailbox, access)["status"] == "FAIL"


actual = pytest.mark.skipif(not (sim.renode_bin() and shutil.which("arm-none-eabi-gcc")), reason="Arm/Renode unavailable")


@actual
def test_actual_target_observes_flag_then_clear_through_original_LL(ws):
    context = ctx(ws)
    before = {str(p.relative_to(ws)): p.read_bytes() for p in ws.rglob("*") if p.is_file()}
    fragment = O.run(context)
    assert fragment["status"] == "PASS", fragment
    result = record(ws, fragment, context)
    observed = O.verify(ws, result)[0]["observed"]
    assert observed["sr_before"] == 1 and observed["sr_after"] == 0
    assert observed["actual_hal_status_matches_HAL_OK"] is True
    assert observed["call_writes"] == [{"offset": 8, "value": 0}]
    assert observed["sr_reserved_write_values_valid"] is True
    assert O.trace(ws)[1] == {"UT-021": "PASS"}
    assert all((ws / path).read_bytes() == raw for path, raw in before.items())
    assert not (ws / "software/tests/target").exists()


@actual
def test_original_complement_write_does_not_receive_reserved_write_credit(ws):
    """Fresh CONTROL origin uses the actual original ST expression; no provided-code waiver/repin after execution."""
    path = ws / "software/ll/stm32n6xx_ll_wwdg.h"
    path.write_text(path.read_text().replace("x->SR = 0U", "x->SR = ~WWDG_SR_EWIF"))
    manifest = json.loads((ws / ".forge-run/manifest.json").read_text())
    manifest["provided"][0]["sha256"] = sha256_file(path)
    write(ws, ".forge-run/manifest.json", manifest)  # fixture origin binding BEFORE any execution
    context = ctx(ws)
    fragment = O.run(context)
    assert fragment["status"] == "FAIL", fragment
    observed = O.verify(ws, record(ws, fragment, context))[0]["observed"]
    assert observed["sr_before"] == 1 and observed["sr_after"] == 0
    assert observed["actual_hal_status_matches_HAL_OK"] is True
    assert observed["call_writes"] == [{"offset": 8, "value": 0xfffffffe}]
    assert observed["sr_reserved_write_values_valid"] is False
    assert O.trace(ws)[1] == {"UT-021": "FAIL"}


@pytest.mark.parametrize("writes", [[(8, 0xfffffffe)], [(8, 0), (8, 2)], [(8, 0), (4, 0)], [],
                                   [(8, -0x100000000)], [(8, 0x100000000)]])
def test_every_write_must_preserve_reserved_bits_and_touch_only_SR(writes):
    mailbox = {"magic_ok": True, "done": True, "passed": 3, "failed": 0, "failed_ids": []}
    access = [{"phase": 1, "access": "R", "offset": 8, "value": 1}] + [
        {"phase": 2, "access": "W", "offset": offset, "value": value} for offset, value in writes] + [
        {"phase": 3, "access": "R", "offset": 8, "value": 0}]
    test = O._observed(mailbox, access)
    assert test["status"] == "FAIL" and test["observed"]["sr_reserved_write_values_valid"] is False


@actual
def test_historical_proof_schema_requires_reverification(ws):
    context = ctx(ws)
    fragment = O.run(context)
    assert fragment["status"] == "PASS", fragment
    result = record(ws, fragment, context)
    proof = json.loads(T._artifact(ws, result["artifact_refs"], result["metrics"][O.METRIC], "json"))
    proof["schema"] = "forge-c/swe4-target-observation-proof/1"
    proof_ref = context.store(canonical_json(proof), "json")
    result["artifact_refs"].append(proof_ref)
    result["metrics"][O.METRIC] = proof_ref
    with pytest.raises(O.ObservationError, match="PROOF_VERSION_UNSUPPORTED"):
        O.verify(ws, result)
    proof["schema"] = O.PROOF
    proof["tests"][0]["observed"]["sr_reserved_write_values_valid"] = False
    proof_ref = context.store(canonical_json(proof), "json")
    result["artifact_refs"].append(proof_ref)
    result["metrics"][O.METRIC] = proof_ref
    with pytest.raises(O.ObservationError, match="RESULT_CHANGED"):
        O.verify(ws, result)  # the reserved-write verdict is recomputed from sealed raw access observations


@actual
@pytest.mark.parametrize("bad_call", ["(void)0", "WWDG->SR = WWDG_SR_EWIF"])
def test_wrong_HAL_does_not_clear_target_flag(ws, bad_call):
    path = ws / "software/hal/stm32n6xx_hal_wwdg.c"
    path.write_text(path.read_text().replace("LL_WWDG_ClearFlag_EWKUP(WWDG)", bad_call))
    context = ctx(ws)
    fragment = O.run(context)
    assert fragment["status"] == "FAIL", fragment
    result = record(ws, fragment, context)
    test = O.verify(ws, result)[0]
    assert test["status"] == "FAIL" and test["observed"]["sr_after"] == 1


@actual
def test_actual_status_failure_is_not_hidden_by_correct_register_effect(ws):
    path = ws / "software/hal/stm32n6xx_hal_wwdg.c"
    path.write_text(path.read_text().replace("return HAL_OK", "return HAL_ERROR"))
    context = ctx(ws)
    fragment = O.run(context)
    assert fragment["status"] == "FAIL", fragment
    test = O.verify(ws, record(ws, fragment, context))[0]
    assert test["observed"]["sr_after"] == 0 and test["observed"]["actual_hal_status_matches_HAL_OK"] is False


@actual
def test_source_ELF_and_invocation_cannot_change_after_measurement(ws):
    context = ctx(ws)
    fragment = O.run(context)
    assert fragment["status"] == "PASS", fragment
    result = record(ws, fragment, context)
    write(ws, "evidence/tool-results.jsonl", json.dumps({"op": "run_unit", "result": {
        "status": "PASS", "metrics": {}, "artifact_refs": [], "provenance": {"invocation_id": "new"}}}) + "\n")
    assert O.trace(ws)[1] == {}  # a later unbound result cannot reuse the old proof
    result["provenance"]["invocation_id"] = "different"
    with pytest.raises(O.ObservationError, match="BINDING_CHANGED"):
        O.verify(ws, result)
    result["provenance"]["invocation_id"] = context.invocation_id
    proof = json.loads(T._artifact(ws, result["artifact_refs"], result["metrics"][O.METRIC], "json"))
    access_path = ws / "evidence/raw" / (proof["access_log_ref"].split(":")[-1] + ".log")
    original_access = access_path.read_bytes()
    access_path.write_text("changed")
    with pytest.raises(T.TimingError, match="ARTIFACT_CHANGED"):
        O.verify(ws, result)
    access_path.write_bytes(original_access)
    binary = json.loads(T._artifact(ws, result["artifact_refs"], proof["elf_artifact_ref"], "json"))
    binary["data"] = base64.b64encode(b"different ELF").decode()
    binary_ref = context.store(canonical_json(binary), "json")
    proof["elf_artifact_ref"] = binary_ref
    proof_ref = context.store(canonical_json(proof), "json")
    result["artifact_refs"] += [binary_ref, proof_ref]
    result["metrics"][O.METRIC] = proof_ref
    with pytest.raises(O.ObservationError, match="ELF_CHANGED"):
        O.verify(ws, result)
    (ws / "software/hal/stm32n6xx_hal_wwdg.c").write_text("changed")
    with pytest.raises(O.ObservationError, match="BINDING_CHANGED"):
        O.verify(ws, result)
    assert O.trace(ws)[1] == {}
