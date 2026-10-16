"""CAPA-013..015 (r81-r83 + gate-log analysis 2026-10-16): real LL size/stack measurement, early stop on a stuck
phase, turn budget scaled with the allocated work."""
import json
import os
import shutil

import pytest
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
