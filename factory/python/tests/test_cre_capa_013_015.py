"""CAPA-013..015 (r81-r83 + gate-log analysis 2026-10-16): real LL size/stack measurement, early stop on a stuck
phase, turn budget scaled with the allocated work."""
import json
import os
import shutil

import pytest
from forge_factory.common import REPO_ROOT as REPO
from forge_factory.inspection import gate as G
from forge_factory.policy import governor as GV

LL_H = ("#ifndef STM32N6XX_LL_RCC_H\n#define STM32N6XX_LL_RCC_H\n#include <stdint.h>\n#define LL_RCC_REG_COUNT 1024U\n"
        "extern volatile uint32_t ll_rcc_regs[LL_RCC_REG_COUNT];\n"
        "static inline void LL_RCC_HSI_Enable(void)\n{\n    ll_rcc_regs[0U] |= 8U;\n}\n"
        "static inline uint32_t LL_RCC_HSI_IsReady(void)\n{\n    return ((ll_rcc_regs[1U] & 8U) != 0U) ? 1U : 0U;\n}\n"
        "#endif /* STM32N6XX_LL_RCC_H */\n")


def _ws(tmp_path, layer="LL", arch=None):
    ws = tmp_path / "ws"
    (ws / ".forge-run/gates").mkdir(parents=True)
    (ws / ".forge-run/manifest.json").write_text(json.dumps({"layer": layer}))
    if arch:
        (ws / "workproducts/SWE.2").mkdir(parents=True)
        (ws / "workproducts/SWE.2/software_architecture.md").write_text(arch)
    return ws


@pytest.mark.skipif(not shutil.which("arm-none-eabi-gcc"), reason="GNU Arm not installed")
def test_ll_size_and_stack_are_really_measured(tmp_path, monkeypatch):
    from forge_factory.layer import LL_HEADER, LL_TU, LL_TU_TEXT
    from forge_factory.mcp import sdk
    from forge_factory.mcp.servers import build as B

    ws = _ws(tmp_path)
    for rel, txt in {LL_HEADER: LL_H, LL_TU: LL_TU_TEXT}.items():
        (ws / rel).parent.mkdir(parents=True, exist_ok=True)
        (ws / rel).write_text(txt)
    for k, v in {"FORGE_MCP_TRUST": "env", "FORGE_WORKSPACE": str(ws), "FORGE_EVENTS_DIR": str(ws / ".ev"),
                 "FORGE_STATE_DIR": str(ws / ".st"), "FORGE_ROLE": "swe3-author", "FORGE_PHASE": "SWE.3"}.items():
        monkeypatch.setitem(os.environ, k, v)
    op = {o.name: o for o in B.OPERATIONS}
    assert sdk.invoke("forge-build-mcp", op["compile"], {"profile": "target-cm55-gcc"})["status"] == "PASS"
    size = sdk.invoke("forge-build-mcp", op["measure_elf"], {"profile": "target-cm55-gcc"})
    stack = sdk.invoke("forge-build-mcp", op["stack_usage"], {"profile": "target-cm55-gcc"})
    assert size["metrics"]["flash_bytes"] > 0 and stack["metrics"]["functions"] >= 2
    assert not list((ws / "software").rglob("forge_ll_measure.c"))  # build directory only, never a product source


def _log(ws, rows):
    with (ws / ".forge-run/gates/gate-log.jsonl").open("a") as fh:
        for r in rows:
            fh.write(json.dumps({"phase": "SWE.3", "ts": "2026-10-16T12:00:00Z", **r}) + "\n")


def test_identical_deterministic_rejections_stop_the_phase(tmp_path):
    ws = _ws(tmp_path)
    rej = {"step": "author", "result": "REJECTED", "issues": ["DEFECT_TEST_CHANGED:DEF-001:software/ll/x.h"]}
    _log(ws, [rej])
    assert G.stuck_signature(ws, "SWE.3") is None  # one rejection is not stuck
    _log(ws, [rej])
    assert G.stuck_signature(ws, "SWE.3") == ("DEFECT_TEST_CHANGED:DEF-001:software/ll/x.h",)
    _log(ws, [{"step": "author", "result": "REJECTED", "issues": ["AGENT_OUTPUT_PROSE"]},
              {"step": "author", "result": "REJECTED", "issues": ["AGENT_OUTPUT_PROSE"]}])
    assert G.stuck_signature(ws, "SWE.3") is None  # model-behaviour issues may differ next time: not stuck
    _log(ws, [rej, {"step": "author", "result": "REJECTED", "issues": ["MISSING_REQUIRED_OUTPUT:x"]}])
    assert G.stuck_signature(ws, "SWE.3") is None  # different codes = progress


ALLOC = "# A\n## Requirement allocation\n| SWR | Function |\n|---|---|\n" + "".join(
    f"| SWR-{i:03d} | LL_RCC_F{i}_Enable |\n" for i in range(1, 31))


def test_turn_budget_scales_with_the_allocated_work(tmp_path):
    ws = _ws(tmp_path, arch=ALLOC)
    base = GV.turn_limit("swe3-author")
    assert GV.turn_limit("swe3-author", str(ws)) == base + (30 - 12) // 2
    assert GV.turn_limit("swe3-inspector", str(ws)) == GV.turn_limit("swe3-inspector")  # inspectors unchanged
    small = _ws(tmp_path / "s", arch=ALLOC.split("| SWR-013")[0])
    assert GV.turn_limit("swe3-author", str(small)) == base  # at or below the reference size: authored budget


@pytest.mark.skipif(not shutil.which("arm-none-eabi-gcc"), reason="GNU Arm not installed")
def test_robot_driver_keywords_measure_a_header_only_ll(tmp_path):
    """CAPA-016 (r83 DEF-003): 'Driver Stack Should Be At Most' failed with 'no call graph produced' on an LL."""
    import importlib.util

    from forge_factory.common import REPO_ROOT
    from forge_factory.layer import LL_HEADER, LL_TU, LL_TU_TEXT

    spec = importlib.util.spec_from_file_location("ForgeTarget", REPO_ROOT / "factory/sim/stm32n6/ForgeTarget.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    ws = _ws(tmp_path)
    for rel, txt in {LL_HEADER: LL_H, LL_TU: LL_TU_TEXT}.items():
        (ws / rel).parent.mkdir(parents=True, exist_ok=True)
        (ws / rel).write_text(txt)
    lib = mod.ForgeTarget(str(ws))
    stack, unbounded = lib._stack()
    assert unbounded == [] and 0 <= stack <= 128  # a bounded call graph (leaf LL frames may be 0 B at -Os)
    assert lib.driver_stack_should_be_at_most(128) == stack
    assert 0 < lib.driver_flash_size_should_be_at_most(4096)
    assert lib.driver_static_ram_should_be_at_most(0) == 0


def _trace(ws, rows):
    (ws / "workproducts/SWE.1").mkdir(parents=True, exist_ok=True)
    (ws / "workproducts/SWE.1/software_requirements.md").write_text(
        "- **SWR-001** When the HSI enable function is called, the RCC LL driver shall set RCC_CR.HSION.\n"
        "- **SWR-019** The RCC LL driver shall use at most 4096 bytes of flash.\n")
    (ws / "traceability").mkdir(exist_ok=True)
    (ws / "traceability/requirements_to_tests.csv").write_text("requirement_id,test_id,test_file\n" + rows)
    (ws / "software/tests/unit").mkdir(parents=True, exist_ok=True)
    (ws / "software/tests/unit/test_rcc.c").write_text('CHECK("UT-001", 1);\n')


def test_swe4_trace_rejects_phantom_test_ids_before_its_baseline(tmp_path, monkeypatch):
    """CAPA-017 (r83): validate_trace skipped the phantom check while SWE.4 was being authored."""
    from forge_factory.mcp import sdk
    from forge_factory.mcp.servers import evidence as EV

    ws = _ws(tmp_path)
    for k, v in {"FORGE_MCP_TRUST": "env", "FORGE_WORKSPACE": str(ws), "FORGE_EVENTS_DIR": str(ws / ".ev"),
                 "FORGE_STATE_DIR": str(ws / ".st"), "FORGE_ROLE": "swe4-author", "FORGE_PHASE": "SWE.4"}.items():
        monkeypatch.setitem(os.environ, k, v)
    op = next(o for o in EV.OPERATIONS if o.name == "validate_trace")
    _trace(ws, "SWR-001,UT-001,software/tests/unit/test_rcc.c\nSWR-019,UT-019,software/tests/unit/test_rcc.c\n")
    out = sdk.invoke("forge-evidence-mcp", op, {})
    assert out["status"] == "FAIL" and any("TEST_ID_NOT_IN_FILE:UT-019" in i for i in out["issues"])
    _trace(ws, "SWR-001,UT-001,software/tests/unit/test_rcc.c\n"
               "SWR-019,SWR-019,software/tests/software/test_rcc_requirements.robot\n")
    out = sdk.invoke("forge-evidence-mcp", op, {})
    assert out["status"] == "PASS" and out["metrics"]["planned_test_links"] == 1  # Robot suite due at SWE.6


R84_H = ("#ifndef STM32N6XX_LL_RCC_H\n#define STM32N6XX_LL_RCC_H\n#include <stdint.h>\n"
         "static inline void LL_RCC_HSI_Enable(volatile uint32_t *rcc)\n{\n    rcc[0U] |= 8U;\n}\n"
         "static inline uint32_t LL_RCC_HSI_IsReady(const volatile uint32_t *rcc)\n{\n"
         "    return ((rcc[1U] & 8U) != 0U) ? 1U : 0U;\n}\n#endif /* STM32N6XX_LL_RCC_H */\n")


def test_measurement_unit_handles_any_ll_signature():
    """CAPA-018 (r84): pointer-parameter LL functions were not instantiated, size/stack stayed 0."""
    from forge_factory.layer import ll_measure_unit

    unit = ll_measure_unit(R84_H)
    assert "void forge_measure_LL_RCC_HSI_Enable(volatile uint32_t *rcc) { LL_RCC_HSI_Enable(rcc); }" in unit
    assert "return LL_RCC_HSI_IsReady(rcc);" in unit
    assert "forge_measure_LL_RCC_HSI_Enable(void) { LL_RCC_HSI_Enable(); }" in ll_measure_unit(LL_H)


def test_ll_check_keeps_the_generated_register_block_and_void_api(tmp_path):
    """CAPA-019 (r84): a pointer API replaced the generated ll_rcc_regs block; SWE.2/SWE.3 then contradicted."""
    from forge_factory.inspection.implementation import check_implementation
    from forge_factory.layer import LL_HEADER

    ws = _ws(tmp_path, arch="# A\n## Requirement allocation\n| SWR | Function |\n|---|---|\n"
                             "| SWR-001 | LL_RCC_HSI_Enable |\n| SWR-002 | LL_RCC_HSI_IsReady |\n")
    (ws / "software/ll").mkdir(parents=True)
    (ws / LL_HEADER).write_text(R84_H)
    f = check_implementation(ws)["major_findings"]
    assert "IMPL:LL_REG_BLOCK_DECLARATION_MISSING" in f and "IMPL:LL_SIGNATURE_NOT_VOID:LL_RCC_HSI_Enable" in f
    (ws / LL_HEADER).write_text(LL_H)
    assert check_implementation(ws)["verdict"] == "PASS"
    scope = json.loads((REPO / "examples/0002a-arm_55_rcc_ll/workorder.json").read_text())["scope"][0]
    assert "ll_rcc_regs" in scope and "pointer" not in scope


def test_author_prompts_only_write_inside_their_role_scope():
    """CAPA-020 (r84 DEF-002): the SWE.4 procedure told the author to write traceability/, outside its write scope."""
    import re

    from forge_factory.policy.authz import ROLE_WRITE_PREFIXES
    from forge_factory.workflow import prompts
    from forge_factory.workflow.builder import build

    for layer in ("LL", "HAL", "LL+HAL"):
        _, nodes = build("WO-W", layer=layer, chunk_lines=150)
        for ph in ("SWE.1", "SWE.2", "SWE.3", "SWE.4", "SWE.5", "SWE.6"):
            role = f"swe{ph[-1]}-author"
            for path in re.findall(r"write_file ([\w./-]+)", prompts.author_prompt(ph)):
                assert any(path.startswith(p) for p in ROLE_WRITE_PREFIXES[role]), (layer, ph, path)
    prompts.LAYER["layer"] = "LL+HAL"


def test_reqif_robot_traced_requirement_has_distinct_ids(tmp_path):
    """CAPA-021 (r85): test_id = SWR id (Robot-verified requirement, CAPA-020) duplicated the requirement's xs:ID."""
    from forge_factory.inspection.reqif_export import export

    ws = tmp_path / "w"
    (ws / "workproducts/SWE.1").mkdir(parents=True)
    (ws / "workproducts/SWE.1/software_requirements.md").write_text(
        "- **SWR-001** When the HSI enable function is called, the RCC LL driver shall set RCC_CR.HSION.\n"
        "  - Source: RM0486 p.479\n"
        "- **SWR-019** The RCC LL driver shall use at most 4096 bytes of flash.\n  - Source: work-order budget\n")
    (ws / "traceability").mkdir()
    (ws / "traceability/requirements_to_tests.csv").write_text(
        "requirement_id,test_id,test_file\nSWR-001,UT-001,software/tests/unit/test_rcc.c\n"
        "SWR-019,SWR-019,software/tests/software/test_rcc_requirements.robot\n")
    out = export(ws)
    assert out["verdict"] == "PASS" and out["spec_objects"] == 4, out  # 2 SWR + 2 test objects, distinct ids


def test_duplicate_check_ids_fail_the_run(tmp_path, monkeypatch):
    """CAPA-022 (r86): duplicated UT ids were only found by the SWE.4 inspector (two rework cycles)."""
    from forge_factory.layer import LL_HEADER, LL_TU, LL_TU_TEXT
    from forge_factory.mcp import sdk
    from forge_factory.mcp.servers import tests as T
    from forge_factory.workflow import scaffold as SC

    ws = _ws(tmp_path)
    for rel, txt in {LL_HEADER: LL_H, LL_TU: LL_TU_TEXT}.items():
        (ws / rel).parent.mkdir(parents=True, exist_ok=True)
        (ws / rel).write_text(txt)
    for k, v in {"FORGE_MCP_TRUST": "env", "FORGE_WORKSPACE": str(ws), "FORGE_EVENTS_DIR": str(ws / ".ev"),
                 "FORGE_STATE_DIR": str(ws / ".st"), "FORGE_ROLE": "swe4-author", "FORGE_PHASE": "SWE.4"}.items():
        monkeypatch.setitem(os.environ, k, v)
    SC.scaffold(ws)
    ut = (ws / SC.UNIT_TEST).read_text().replace(SC.TEST_CASES_MARKER, (
        "static void ut_a(void)\n{\n    ut_reset_regs();\n    LL_RCC_HSI_Enable();\n"
        "    CHECK(\"UT-001\", (ll_rcc_regs[0] & 8U) != 0U);\n    CHECK(\"UT-001\", LL_RCC_HSI_IsReady() == 0U);\n}\n"
        + SC.TEST_CASES_MARKER)).replace(SC.TEST_CALLS_MARKER, "ut_a();\n    " + SC.TEST_CALLS_MARKER)
    (ws / SC.UNIT_TEST).write_text(ut)
    out = sdk.invoke("forge-tests-mcp", next(o for o in T.OPERATIONS if o.name == "run_unit"), {"coverage": False})
    assert out["status"] == "FAIL" and any(i.startswith("DUPLICATE_TEST_ID:UT-001") for i in out["issues"])


def test_target_procedures_state_the_rcc_model_exactly():
    """CAPA-023 (r86): authors assumed RCC_SR was plain storage; the model text must match rcc_model.py."""
    from forge_factory.workflow import prompts
    from forge_factory.workflow.builder import build

    model = (REPO / "factory/sim/stm32n6/rcc_model.py").read_text()
    assert "READY_MASK = 0x00000F1F" in model and "if off == 0x004:" in model
    for layer in ("LL", "HAL", "LL+HAL"):
        build("WO-M", layer=layer, chunk_lines=150)
        for text in (prompts.target_test_author_prompt(), prompts.robot_test_author_prompt()):
            assert "RCC_SR (offset 0x004), which is read-only" in text and "0x00000F1F" in text
    prompts.LAYER["layer"] = "LL+HAL"


def test_traced_test_must_call_the_allocated_api(tmp_path, monkeypatch):
    """CAPA-024 (r86/r92/r93 SWE4-02): a traced unit test exercised a different function than its requirement."""
    from forge_factory.mcp import sdk
    from forge_factory.mcp.servers import evidence as EV

    ws = _ws(tmp_path, arch="# A\n## Requirement allocation\n| SWR | Function |\n|---|---|\n"
                             "| SWR-001 | LL_RCC_HSI_Enable |\n| SWR-002 | LL_RCC_HSI_IsReady |\n")
    for k, v in {"FORGE_MCP_TRUST": "env", "FORGE_WORKSPACE": str(ws), "FORGE_EVENTS_DIR": str(ws / ".ev"),
                 "FORGE_STATE_DIR": str(ws / ".st"), "FORGE_ROLE": "swe4-author", "FORGE_PHASE": "SWE.4"}.items():
        monkeypatch.setitem(os.environ, k, v)
    (ws / "workproducts/SWE.1").mkdir(parents=True)
    (ws / "workproducts/SWE.1/software_requirements.md").write_text(
        "- **SWR-001** When the HSI enable function is called, the RCC LL driver shall set RCC_CR.HSION.\n"
        "- **SWR-002** When the HSI ready query is called, the RCC LL driver shall return 1U if RCC_SR.HSIRDY is set.\n")
    (ws / "traceability").mkdir()
    (ws / "traceability/requirements_to_tests.csv").write_text(
        "requirement_id,test_id,test_file\nSWR-001,UT-001,software/tests/unit/test_rcc.c\n"
        "SWR-002,UT-002,software/tests/unit/test_rcc.c\n")
    (ws / "software/tests/unit").mkdir(parents=True)
    shifted = ('static void ut_a(void)\n{\n    LL_RCC_HSI_IsReady();\n    CHECK("UT-001", 1);\n}\n'
               'static void ut_b(void)\n{\n    LL_RCC_HSI_Enable();\n    CHECK("UT-002", 1);\n}\n')
    (ws / "software/tests/unit/test_rcc.c").write_text(shifted)
    op = next(o for o in EV.OPERATIONS if o.name == "validate_trace")
    out = sdk.invoke("forge-evidence-mcp", op, {})
    assert out["status"] == "FAIL"
    assert any(i.startswith("TEST_DOES_NOT_CALL_ALLOCATED_API:UT-001:SWR-001") for i in out["issues"])
    (ws / "software/tests/unit/test_rcc.c").write_text(shifted.replace("IsReady();\n    CHECK(\"UT-001\"", "Enable();\n"
        "    CHECK(\"UT-001\"").replace("Enable();\n    CHECK(\"UT-002\"", "IsReady();\n    CHECK(\"UT-002\""))
    assert sdk.invoke("forge-evidence-mcp", op, {})["status"] == "PASS"


def test_swe5_author_writes_missing_target_tests():
    """CAPA-025 (r97): SWE.5 rework could not recover when the target-test step had written no target tests."""
    from forge_factory.workflow import prompts
    from forge_factory.workflow.builder import build

    for layer in ("LL", "HAL", "LL+HAL"):
        build("WO-T", layer=layer, chunk_lines=150)
        assert "If it reports NO_TESTS" in prompts.author_prompt("SWE.5")
    prompts.LAYER["layer"] = "LL+HAL"
