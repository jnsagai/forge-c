"""Finite real target-call controls; no inference or production phase qualification."""

import copy
import json
import shutil

import pytest
from forge_factory.common import canonical_json, sha256_file
from forge_factory.inspection import swtrace, uspec_plan
from forge_factory.mcp.servers import evidence, sim
from forge_factory.mcp.servers import tests as U
from forge_factory.workflow import unit_target_wwdg_timing as W
from test_unit_target_observation import ctx, record, write


@pytest.fixture
def ws(tmp_path):
    vendor = write(
        tmp_path,
        "inputs/vendor/include/stm32n6xx.h",
        """#include <stdint.h>
typedef struct { volatile uint32_t CR, CFR, SR; } WWDG_TypeDef;
#define WWDG ((WWDG_TypeDef *)0x50002C00U)
""",
    )
    ll = write(
        tmp_path,
        "software/ll/stm32n6xx_ll_wwdg.h",
        """#include "stm32n6xx.h"
static inline void LL_WWDG_ClearFlag_EWKUP(WWDG_TypeDef *x) { x->SR = 0U; }
static inline void LL_WWDG_SetConfig(WWDG_TypeDef *x, uint32_t p, uint32_t w, uint32_t e) { x->CFR = w | (p << 11U) | (e << 9U); }
static inline void LL_WWDG_SetCounter(WWDG_TypeDef *x, uint32_t counter) { x->CR = counter; }
static inline uint32_t LL_WWDG_GetFlag(WWDG_TypeDef *x) { return x->SR & 1U; }
""",
    )
    write(
        tmp_path,
        "software/hal/stm32n6xx_hal_wwdg.h",
        """#include "stm32n6xx_ll_wwdg.h"
typedef enum { HAL_OK, HAL_ERROR } hal_status_t;
typedef struct { uint32_t prescaler, window, counter, ewi_enable; } hal_wwdg_config_t;
hal_status_t HAL_WWDG_Init(const hal_wwdg_config_t *config);
hal_status_t HAL_WWDG_Refresh(uint32_t counter);
hal_status_t HAL_WWDG_GetEarlyWakeupFlag(uint32_t *flag);
hal_status_t HAL_WWDG_ClearEarlyWakeupFlag(void);
""",
    )
    write(
        tmp_path,
        "software/hal/stm32n6xx_hal_wwdg.c",
        """#include "stm32n6xx_hal_wwdg.h"
hal_status_t HAL_WWDG_Init(const hal_wwdg_config_t *config) {
 if (!config) { return HAL_ERROR; }
 LL_WWDG_SetConfig(WWDG, config->prescaler, config->window, config->ewi_enable);
 LL_WWDG_SetCounter(WWDG, config->counter | 0x80U); return HAL_OK;
}
hal_status_t HAL_WWDG_Refresh(uint32_t counter) { LL_WWDG_SetCounter(WWDG, counter); return HAL_OK; }
hal_status_t HAL_WWDG_GetEarlyWakeupFlag(uint32_t *flag) { *flag = LL_WWDG_GetFlag(WWDG); return HAL_OK; }
hal_status_t HAL_WWDG_ClearEarlyWakeupFlag(void) { LL_WWDG_ClearFlag_EWKUP(WWDG); return HAL_OK; }
""",
    )
    budget = {
        "schema": "forge-c/simulation-performance-budget/1",
        "instructions_per_call": 2000,
        "microseconds_per_call": 1000,
        "performance_mips": 100,
        "test_source": "software/tests/target/test_performance.c",
    }
    write(
        tmp_path,
        ".forge-run/manifest.json",
        {
            "layer": "HAL",
            "peripheral": "wwdg",
            "simulation_performance": budget,
            "budgets": {"flash_bytes": 4096, "static_ram_bytes": 1024, "stack_bytes": 1024},
            "provided": [{"path": "software/ll/stm32n6xx_ll_wwdg.h", "role": "provided_ll_driver", "sha256": sha256_file(ll)}],
            "provided_build": {
                "style": "cmsis",
                "files": [{"path": "inputs/vendor/include/stm32n6xx.h", "sha256": sha256_file(vendor)}],
            },
        },
    )
    write(
        tmp_path,
        "workproducts/SWE.1/software_requirements.md",
        "- **SWR-027** When a scoped HAL_WWDG_ API is measured in the declared instrumented target scenario at 100 MIPS, "
        "the WWDG driver shall execute at most 2000 target instructions per call.\n"
        "- **SWR-028** When a scoped HAL_WWDG_ API is measured in the declared instrumented target scenario at 100 MIPS, "
        "the WWDG driver shall complete each call in at most 1000 microseconds of virtual time.\n",
    )
    behaviour = "In the declared instrumented target scenario at 100 MIPS, complete within 2000 instructions and 1000 microseconds of virtual time."
    tasks, specs, cases = [], [], []
    for n, (function, ut, suffix) in enumerate(
        zip(W.FUNCTIONS, ("UT-011", "UT-016", "UT-020", "UT-025"), (11, 5, 4, 5), strict=True), 1
    ):
        unit, uspec = f"SWU-HAL-{n:02d}", f"USPEC-HAL-{n:02d}-{suffix:02d}"
        tasks.append(
            {
                "ut": ut,
                "uspec": uspec,
                "unit": unit,
                "functions": [function],
                "behaviour": behaviour,
                "swrs": ["SWR-027", "SWR-028"],
                "constraints_verified_at_swe6": [],
                "kind": "requirement",
                "test_kind": "positive",
                "unknown_swrs": [],
            }
        )
        cases.append({"ut": ut, "uspec": uspec, "function": function, "expected_status": "HAL_OK"})
        specs.append(
            f"## {unit}: {function}\n- SWC: SWC_HAL\n- Functions: {function}\n"
            f"- **{uspec}** {behaviour} Traces: SWR-027, SWR-028\n"
        )
    unit = write(tmp_path, swtrace.UNITS_MD, "\n".join(specs))
    write(
        tmp_path,
        uspec_plan.PLAN,
        {
            "schema": uspec_plan.SCHEMA,
            "tasks": tasks,
            "closure": [],
            "unit_specification": {"path": swtrace.UNITS_MD, "sha256": sha256_file(unit)},
        },
    )
    write(
        tmp_path,
        "workproducts/SWE.2/api_calls.json",
        {
            "schema": "forge-c/api-calls/1",
            "calls": {
                "INIT": {
                    "function": W.FUNCTIONS[0],
                    "args": [
                        "&(const hal_wwdg_config_t){ .prescaler = 0U, .window = 0x50U, .counter = 0x7FU, .ewi_enable = 1U }"
                    ],
                },
                "REFRESH": {"function": W.FUNCTIONS[1], "args": ["0x7FU"]},
                "GET": {"function": W.FUNCTIONS[2], "args": ["&(uint32_t){0U}"]},
                "CLEAR": {"function": W.FUNCTIONS[3], "args": []},
            },
        },
    )
    write(
        tmp_path,
        W.DECLARATION,
        {
            "schema": W.SCHEMA,
            "scenario": W.SCENARIO,
            "config": {"prescaler": 0, "window": 0x50, "counter": 0x7F, "ewi_enable": 1},
            "refresh_counter": 0x7F,
            "query_initial": 0,
            "cases": cases,
        },
    )
    return tmp_path


actual = pytest.mark.skipif(not (sim.renode_bin() and shutil.which("arm-none-eabi-gcc")), reason="Arm/Renode unavailable")


def test_nonselected_default_and_declared_not_executed(ws, tmp_path):
    assert W.declaration(ws)["config"]["counter"] == 127
    assert len(W.expected_tests(ws)) == 4
    assert set(W.trace(ws)[1].values()) == {"FAIL"}
    assert any("NO_EXECUTED_UNIT_RUN" in x for x in W.trace(ws)[2])
    empty = tmp_path / "empty"
    empty.mkdir()
    assert W.run(ctx(empty)) is None and W.trace(empty) == ([], {}, [])


@pytest.mark.parametrize("field,value", [("prescaler", 8), ("window", 0x3F), ("counter", True), ("ewi_enable", 2)])
def test_invalid_configuration(ws, field, value):
    decl = W.declaration(ws)
    decl["config"][field] = value
    write(ws, W.DECLARATION, decl)
    with pytest.raises(ValueError, match="ARGUMENT_INVALID"):
        W.declaration(ws)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d["config"].update(window=0x51),
        lambda d: d.update(refresh_counter=0x70),
        lambda d: d.update(query_initial=1),
        lambda d: d.update(scenario="fake"),
        lambda d: d["cases"][0].update(expected_status="HAL_ERROR"),
        lambda d: d["cases"][0].update(function=W.FUNCTIONS[1]),
        lambda d: d["cases"][0].update(uspec="USPEC-HAL-01-01"),
        lambda d: d["cases"][0].update(ut="UT-025"),
        lambda d: d["cases"].pop(),
    ],
)
def test_changed_or_unknown_declaration_refuses(ws, mutate):
    value = W.declaration(ws)
    mutate(value)
    write(ws, W.DECLARATION, value)
    with pytest.raises(ValueError):
        W.declaration(ws)
    assert W.run(ctx(ws))["status"] == "FAIL"


@pytest.mark.parametrize("change", ["negation", "additional", "unit", "swrs", "defer", "duplicate"])
def test_changed_frozen_semantics_refuse(ws, change):
    plan = json.loads((ws / uspec_plan.PLAN).read_text())
    row = plan["tasks"][0]
    if change == "negation":
        row["behaviour"] = "Do not " + row["behaviour"]
    elif change == "additional":
        row["behaviour"] += " Also preserve a different predicate."
    elif change == "unit":
        row["unit"] = "SWU-HAL-99"
    elif change == "swrs":
        row["swrs"] = ["SWR-027"]
    elif change == "defer":
        row["constraints_verified_at_swe6"] = ["SWR-027"]
    else:
        plan["tasks"].append(copy.deepcopy(row))
    write(ws, uspec_plan.PLAN, plan)
    with pytest.raises(ValueError):
        W.declaration(ws)
    assert set(W.trace(ws)[1].values()) == {"FAIL"}


@pytest.mark.parametrize(
    "rel",
    [
        "software/ll/stm32n6xx_ll_wwdg.h",
        "inputs/vendor/include/stm32n6xx.h",
        "workproducts/SWE.3/unit_specifications.md",
        "workproducts/SWE.1/software_requirements.md",
    ],
)
def test_changed_approved_context_refuses(ws, rel):
    (ws / rel).write_text("changed")
    with pytest.raises(ValueError):
        W.declaration(ws)
    assert W.run(ctx(ws))["status"] == "FAIL"


def test_missing_declaration_overrides_honest_host_pass_in_trace_and_public_tool(ws):
    (ws / W.DECLARATION).unlink()
    write(
        ws,
        "software/tests/unit/test_host.c",
        """#include <stdio.h>
#define CHECK(ID,C) do { if (!(C)) return 1; puts(ID " PASS"); } while(0)
/** @test UT-025
 * @verifies USPEC-HAL-04-05
 */
int main(void) { CHECK("UT-025", 1); return 0; }
""",
    )
    out = U.run_unit(ctx(ws), U.RunIn(coverage=False))
    assert out["status"] == "FAIL"
    assert any("DECLARATION_REQUIRED" in i for i in out["issues"])
    record(ws, {"status": out["status"], "metrics": out["metrics"], "artifact_refs": out["artifact_refs"]}, ctx(ws))
    assert W.trace(ws)[1]["UT-025"] == "FAIL"
    assert any("TARGET_TIMING_NOT_VERIFIED:UT-025" in i for i in evidence._plan_findings(ws)[0])


@actual
def test_real_four_direct_calls_and_sealed_public_unit_result(ws):
    context = ctx(ws)
    out = U.run_unit(context, U.RunIn(coverage=False))
    assert out["status"] == "PASS", out
    assert out["metrics"]["wwdg_timing_ut_passed"] == 4
    assert all(t["status"] == "PASS" and len(t["samples"]) == 1 for t in W.verify(ws, out))
    record(ws, out, context)
    assert set(W.trace(ws)[1].values()) == {"PASS"}
    assert not evidence._plan_findings(ws)[0]
    assert json.loads(U.progress_path(ws, "SWE.4", "run_unit").read_text())["passed"] == 4
    assert all(tag > 999 for tag in W.PRIVATE_CHECKS.values())


@actual
@pytest.mark.parametrize("fault", ["bad-status", "slow-call"])
def test_actual_target_status_and_budget_failure(ws, fault):
    p = ws / "software/hal/stm32n6xx_hal_wwdg.c"
    if fault == "bad-status":
        p.write_text(p.read_text().replace("return HAL_OK;", "return HAL_ERROR;"))
    else:
        p.write_text(
            p.read_text().replace(
                "LL_WWDG_SetCounter(WWDG, counter);",
                "volatile uint32_t i; for(i=0;i<10000;i++) {} LL_WWDG_SetCounter(WWDG, counter);",
            )
        )
    context = ctx(ws)
    out = U.run_unit(context, U.RunIn(coverage=False))
    assert out["status"] == "FAIL", out
    assert any(t["status"] == "FAIL" for t in W.verify(ws, out))
    integrity = json.loads((ws / "evidence/test-integrity.jsonl").read_text().splitlines()[-1])
    assert W.DECLARATION in integrity["assert_failed"]


@actual
def test_proof_source_status_binary_raw_invocation_tamper_refuses(ws):
    context = ctx(ws)
    fragment = W.run(context)
    result = record(ws, fragment, context)
    assert fragment["status"] == "PASS", fragment
    assert len(W.verify(ws, result)) == 4
    changed = copy.deepcopy(result)
    changed["provenance"]["invocation_id"] = "foreign"
    with pytest.raises(ValueError, match="BINDING_CHANGED"):
        W.verify(ws, changed)
    proof_ref = result["metrics"][W.METRIC]
    proof_path = ws / "evidence/raw" / (proof_ref.split(":")[-1] + ".json")
    proof = json.loads(proof_path.read_text())
    proof["tests"][0]["status"] = "FAIL"
    new_ref = context.store(canonical_json(proof), "json")
    changed = copy.deepcopy(result)
    changed["metrics"][W.METRIC] = new_ref
    changed["artifact_refs"].append(new_ref)
    with pytest.raises(ValueError, match="OUTCOME_CHANGED"):
        W.verify(ws, changed)
    raw_ref = proof["engine_result"]["artifact_refs"][0]
    raw = ws / "evidence/raw" / (raw_ref.split(":")[-1] + ".log")
    raw.write_bytes(raw.read_bytes() + b"changed")
    with pytest.raises(ValueError, match="ARTIFACT_CHANGED"):
        W.verify(ws, result)


def test_mailbox_and_samples_are_complete_exact_and_actual(ws):
    value = W.declaration(ws)
    measured = {"status": "PASS", "samples": {f: [{"instructions": 10, "virtual_nanoseconds": 100}] for f in W.FUNCTIONS}}
    mailbox = {"magic_ok": True, "done": True, "passed": 4, "failed": 0, "failed_ids": []}
    assert len(W._outcomes(value, measured, mailbox)) == 4
    for change in [{"done": False}, {"failed": 1}, {"passed": 3, "failed": 1, "failed_ids": [25]}]:
        with pytest.raises(ValueError):
            W._outcomes(value, measured, mailbox | change)
    measured["samples"][W.FUNCTIONS[0]].append({"instructions": 10, "virtual_nanoseconds": 100})
    assert W._outcomes(value, measured, mailbox)[0]["status"] == "FAIL"


@actual
def test_normal_passed_phase_carry_preserves_four_target_rows_across_two_boundaries(tmp_path, monkeypatch):
    """Actual tools and normal resume; deterministic fixture inspections are not real role qualification."""
    from forge_factory import workorder
    from forge_factory.common import REPO_ROOT
    from forge_factory.inspection.engine import PHASES, Store
    from forge_factory.mcp import sdk
    from forge_factory.workflow import unit_target_carry as carry
    from test_swe2_architecture import add_reqif
    from test_unit_target_carry import destination, git, guarded_header, pass_control

    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("FORGE_EVENTS_DIR", str(tmp_path / "events"))
    source = tmp_path / "state/workorders/WO-CONTROL-WWDG/workspace"
    source.mkdir(parents=True)
    ws.__wrapped__(source)
    manifest = json.loads((source / ".forge-run/manifest.json").read_text())
    manifest.update(
        work_order="WO-CONTROL-WWDG",
        created_at="2026-01-01T00:00:00Z",
        factory_revision={"commit": git(REPO_ROOT, "rev-parse", "HEAD"), "dirty": False, "branch": "CONTROL"},
    )
    for rel in ["inputs/vendor/include/stm32n6xx.h", "software/ll/stm32n6xx_ll_wwdg.h", "software/hal/stm32n6xx_hal_wwdg.h"]:
        guarded_header(source / rel)
    for item in manifest["provided"] + manifest["provided_build"]["files"]:
        item["sha256"] = sha256_file(source / item["path"])
    write(source, ".forge-run/manifest.json", manifest)
    write(source, "configuration/system_names.json", '["WWDG driver"]')
    write(
        source,
        "traceability/requirements_to_tests.csv",
        "requirement_id,test_id,test_file\n"
        "SWR-027,VT-027,software/tests/software/test_027.robot\nSWR-028,VT-028,software/tests/software/test_028.robot\n",
    )
    add_reqif(source)
    write(
        source,
        "workproducts/SWE.2/software_architecture.md",
        "# Architecture\n## Components\nHAL, LL\n"
        "## Interfaces\n" + ", ".join(W.FUNCTIONS) + "\n## Requirement allocation\n| SWR | Function |\n|---|---|\n"
        "| SWR-027, SWR-028 | "
        + ", ".join(W.FUNCTIONS)
        + " |\n## Register table\n| Name | Offset |\n|---|---|\n| WWDG_SR | 0x8 |\n",
    )
    write(
        source,
        swtrace.ARCH,
        '@startuml\ncomponent "stm32n6xx_hal_wwdg" <<SWC>> as SWC_HAL\n'
        'component "stm32n6xx_ll_wwdg" <<SWC>> as SWC_LL\nnote right of SWC_HAL : Allocated: SWR-027, SWR-028\n'
        "SWC_HAL --> SWC_LL : IF-01 watchdog\n@enduml\n",
    )
    write(
        source,
        "workproducts/SWE.2/architecture_dynamic.puml",
        "@startuml\nparticipant Caller\nparticipant HAL\nCaller -> HAL : HAL_WWDG_Init()\nHAL --> Caller : HAL_OK\n@enduml\n",
    )
    write(source, "workproducts/SWE.3/detailed_design.md", "# Private CONTROL\nFour finite target calls.\n")
    rows = W.required_rows(source)
    code = source / "software/hal/stm32n6xx_hal_wwdg.c"
    text = code.read_text()
    for row in rows:
        text = text.replace(
            "hal_status_t " + row["functions"][0],
            f"/** @unit {row['unit']} @spec {row['uspec']} */\nhal_status_t " + row["functions"][0],
        )
        write(source, swtrace.DESIGN_DIR + "/" + row["unit"] + ".puml", "@startuml\nstart\n:Finite target call;\nstop\n@enduml\n")
    code.write_text(text)
    write(source, "software/tests/unit/test_control.c", "int main(void) { return 0; }\n")
    write(source, "workproducts/SWE.4/unit_verification_report.md", "# Private CONTROL\nActual target tool output.\n")
    store = Store(source)
    for phase in PHASES[:3]:
        pass_control(store, phase)
    with monkeypatch.context() as control:
        for key, value in {
            "FORGE_MCP_TRUST": "env",
            "FORGE_ROLE": "swe4-author",
            "FORGE_PHASE": "SWE.4",
            "FORGE_WORKSPACE": str(source),
            "FORGE_RUN_ID": "CONTROL-NOT-LIVE",
        }.items():
            control.setenv(key, value)
        result = sdk.invoke("forge-tests-mcp", U.OPERATIONS[0], {"coverage": False})
    assert result["status"] == "PASS", result
    pass_control(store, "SWE.4")
    git(source, "init", "-q")
    git(source, "add", "-A")
    git(source, "-c", "user.name=CONTROL", "-c", "user.email=control@example.invalid", "commit", "-qm", "CONTROL")
    dest, man = destination(source, "WO-CONTROL-WWDG5")
    assert workorder.resume_from(dest, man, "WO-CONTROL-WWDG") == ["SWE.5", "SWE.6"]
    assert set(carry.trace(dest, W)[1].values()) == {"PASS"} and not carry.trace(dest, W)[2]
    assert not evidence._plan_findings(dest)[0]
    report = swtrace.build_all(dest, render=False, doxygen=False, upto="SWE.5", write=set(), export=False)
    assert not report["findings"]["SWE.4"], report
    write(dest, "software/tests/integration/test_control.c", "int main(void) { return 0; }\n")
    write(
        dest,
        "software/tests/target/test_performance.c",
        W.harness(W.declaration(dest)).replace('#include "forge_performance_calls.h"', '#include "stm32n6xx_hal_wwdg.h"'),
    )
    write(dest, "workproducts/SWE.5/integration_verification_report.md", "# Private CONTROL\nActual CPU tools.\n")
    with monkeypatch.context() as control:
        for key, value in {
            "FORGE_MCP_TRUST": "env",
            "FORGE_ROLE": "swe5-author",
            "FORGE_PHASE": "SWE.5",
            "FORGE_WORKSPACE": str(dest),
            "FORGE_RUN_ID": "CONTROL-NOT-LIVE",
        }.items():
            control.setenv(key, value)
        host = sdk.invoke("forge-tests-mcp", U.OPERATIONS[1], {"coverage": False})
        target = sdk.invoke("forge-sim-mcp", sim.OPERATIONS[0], {})
    assert host["status"] == target["status"] == "PASS", (host, target)
    pass_control(Store(dest), "SWE.5")
    phase6, man6 = destination(dest, "WO-CONTROL-WWDG6")
    assert workorder.resume_from(phase6, man6, "WO-CONTROL-WWDG5") == ["SWE.6"]
    assert not carry.trace(phase6, W)[2] and set(carry.trace(phase6, W)[1].values()) == {"PASS"}
    entry = json.loads((phase6 / carry.PATH).read_text())["entries"][W.METRIC]
    assert entry["creator_work_order"] == "WO-CONTROL-WWDG"
    receipt = phase6 / carry.PATH
    original = receipt.read_bytes()
    receipt.unlink()
    assert set(carry.trace(phase6, W)[1].values()) == {"FAIL"}
    receipt.write_bytes(original)
    path = phase6 / "software/hal/stm32n6xx_hal_wwdg.c"
    original = path.read_bytes()
    path.write_bytes(original + b"\n/*changed*/")
    assert set(carry.trace(phase6, W)[1].values()) == {"FAIL"}


@pytest.mark.parametrize("tamper", ["functions", "erased-plan-semantics", "removed-rows"])
def test_plan_mutation_or_omission_cannot_enable_host_credit(ws, tamper):
    plan = json.loads((ws / uspec_plan.PLAN).read_text())
    if tamper == "functions":
        for row in plan["tasks"]:
            row["functions"] = ["HAL_CRC_Init"]
    elif tamper == "erased-plan-semantics":
        for row in plan["tasks"]:
            row.update(swrs=["SWR-999"], behaviour="Host-only substitute.")
    else:
        plan["tasks"] = []
    write(ws, uspec_plan.PLAN, plan)
    (ws / W.DECLARATION).unlink()
    write(
        ws,
        "software/tests/unit/test_host.c",
        "/** @test UT-025\n * @verifies USPEC-HAL-04-05\n */\nint main(void) { return 0; }\n",
    )
    assert W.selected(ws)
    assert W.run(ctx(ws))["status"] == "FAIL"
    assert W.trace(ws)[1]["UT-025"] == "FAIL"


def test_symlinked_requirement_or_vendor_parent_is_not_a_new_input(ws, tmp_path):
    requirement = ws / swtrace.REQS
    saved = tmp_path / "saved-requirements.md"
    requirement.rename(saved)
    requirement.symlink_to(saved)
    with pytest.raises(ValueError, match="SYMLINK"):
        W.declaration(ws)
    requirement.unlink()
    saved.rename(requirement)
    vendor = ws / "inputs/vendor/include"
    saved = tmp_path / "saved-vendor"
    vendor.rename(saved)
    vendor.symlink_to(saved, target_is_directory=True)
    with pytest.raises(ValueError, match="SYMLINK"):
        W.declaration(ws)


@actual
def test_alternate_frozen_arguments_do_not_erase_failed_test_history(ws):
    code = ws / "software/hal/stm32n6xx_hal_wwdg.c"
    code.write_text(code.read_text().replace("if (!config)", "if (!config || config->window == 80U)"))
    contract_path = ws / "workproducts/SWE.2/api_calls.json"
    contract = json.loads(contract_path.read_text())
    contract["calls"]["OTHER_VALID_INIT"] = copy.deepcopy(contract["calls"]["INIT"])
    contract["calls"]["OTHER_VALID_INIT"]["args"][0] = contract["calls"]["INIT"]["args"][0].replace("0x50U", "0x51U")
    write(ws, "workproducts/SWE.2/api_calls.json", contract)
    first = U.run_unit(ctx(ws), U.RunIn(coverage=False))
    assert first["status"] == "FAIL" and first["metrics"]["wwdg_timing_ut_failed"] == 1
    value = W.declaration(ws)
    value["config"]["window"] = 81
    write(ws, W.DECLARATION, value)
    second = U.run_unit(ctx(ws), U.RunIn(coverage=False))
    assert second["metrics"]["wwdg_timing_ut_passed"] == 4
    assert second["status"] == "FAIL" and any("UNDECLARED_TEST_CHANGE" in i for i in second["issues"])


@actual
def test_host_and_target_duplicate_id_cannot_pass_public_unit(ws):
    write(
        ws,
        "software/tests/unit/test_duplicate.c",
        """#include <stdio.h>
#define CHECK(ID,C) do { if (!(C)) return 1; puts(ID " PASS"); } while(0)
/** @test UT-025
 * @verifies USPEC-HAL-04-05
 */
int main(void) { CHECK("UT-025", 1); return 0; }
""",
    )
    out = U.run_unit(ctx(ws), U.RunIn(coverage=False))
    assert out["metrics"]["wwdg_timing_ut_passed"] == 4
    assert out["status"] == "FAIL" and any("DUPLICATE_TEST_ID:UT-025" in i for i in out["issues"])


def test_changed_budget_missing_swr_and_shadowed_harness_refuse(ws):
    path = ws / ".forge-run/manifest.json"
    original = path.read_text()
    manifest = json.loads(original)
    manifest["simulation_performance"]["instructions_per_call"] = 1
    write(ws, ".forge-run/manifest.json", manifest)
    with pytest.raises(ValueError, match="FROZEN_REQUIREMENT"):
        W.declaration(ws)
    path.write_text(original)
    write(ws, "software/hal/forge_target_test.h", "#define TCHECK(N,C) ((void)0)\n")
    with pytest.raises(ValueError, match="HARNESS_SHADOWED"):
        W.declaration(ws)
