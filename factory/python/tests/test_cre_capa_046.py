"""CAPA-046 (r103 SWE3-02, r159 SWE3-01): the SWE.3 inspector failed the mandated register access (extern
ll_rcc_regs placed by the linker: "no RCC base 0x56028000 in the code"); the LL author then added an integer-to-pointer
address unit (software/src/stm32n6xx_ll_rcc_addr.c), which no gate rejected and which made the header-only oracle
crash at link time instead of reporting a build failure."""
import json
import shutil

import pytest
from forge_factory import layer as LY
from forge_factory.assurance import oracle_gen
from forge_factory.assurance import verifiers as V
from forge_factory.inspection.implementation import check_implementation
from forge_factory.workflow import prompts
from forge_factory.workflow.builder import build
from test_easa_register_contract import HAL_C, ws  # noqa: F401 - the HAL rc-v1 workspace fixture
from test_layer_split import ARCH, ws_with

needs_cc = pytest.mark.skipif(not shutil.which("gcc"), reason="gcc not installed")


@pytest.fixture(autouse=True)
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("FORGE_EVENTS_DIR", str(tmp_path / "state/events"))
    yield
    prompts.LAYER["layer"] = "LL+HAL"  # module state set by build(); never leak into other tests


def test_ll_authored_compile_unit_is_rejected_generated_unit_is_not(tmp_path):
    w = ws_with(tmp_path, "LL")
    (w / "workproducts/SWE.2").mkdir(parents=True)
    (w / "workproducts/SWE.2/software_architecture.md").write_text(ARCH)
    (w / "software/ll").mkdir(parents=True)
    (w / LY.LL_HEADER).write_text(
        "#ifndef STM32N6XX_LL_RCC_H\n#define STM32N6XX_LL_RCC_H\n#include <stdint.h>\n"
        "extern volatile uint32_t ll_rcc_regs[1024U];\n"
        "static inline void LL_RCC_HSI_Enable(void)\n{\n    ll_rcc_regs[0U] |= 1U;\n}\n"
        "static inline uint32_t LL_RCC_HSI_IsReady(void)\n{\n    return ((ll_rcc_regs[1U] & 2U) != 0U) ? 1U : 0U;\n}\n"
        "#endif /* STM32N6XX_LL_RCC_H */\n")
    (w / LY.LL_TU).parent.mkdir(parents=True)
    (w / LY.LL_TU).write_text(LY.LL_TU_TEXT)
    assert check_implementation(w)["verdict"] == "PASS"
    (w / "software/src/stm32n6xx_ll_rcc_addr.c").write_text(
        "#include <stdint.h>\nvolatile uint32_t *LL_RCC_MemPtr(uintptr_t a) { return (volatile uint32_t *)a; }\n")
    r = check_implementation(w)
    assert r["verdict"] == "FAIL"
    assert r["major_findings"] == ["IMPL:LL_EXTRA_COMPILE_UNIT:software/src/stm32n6xx_ll_rcc_addr.c"]


@needs_cc
def test_oracle_link_failure_is_a_build_failure_not_a_crash(ws):  # noqa: F811
    p = ws / "software/hal/stm32n6xx_hal_rcc.c"
    p.write_text(HAL_C.replace("hal_status_t HAL_RCC_HSE_Enable(", "void forge_unresolved(void);\n"
                               "hal_status_t HAL_RCC_HSE_Enable(", 1).replace("    LL_RCC_HSE_Enable();\n",
                                                                           "    forge_unresolved();\n    LL_RCC_HSE_Enable();\n", 1))
    r = oracle_gen.run(ws, [ws / "software/hal", ws / "software/ll"], [p], "stm32n6xx_hal_rcc.h")
    assert r["status"] == "BUILD_FAILED" and "forge_unresolved" in r["reason"]
    v = V.v_oracle(ws)
    assert v["status"] == "FAIL" and any(f.startswith("ORACLE_BUILD_FAILED") for f in v["findings"])


@pytest.mark.parametrize("layer", ["LL", "HAL", "LL+HAL"])
def test_swe2_swe3_inspectors_are_told_the_register_block_design(layer):
    build("WO-C46", layer=layer, chunk_lines=150)
    for ph in ("SWE.2", "SWE.3"):
        assert prompts.REGISTER_BLOCK_NOTE in prompts.inspector_prompt(ph)
    for ph in ("SWE.1", "SWE.4", "SWE.5", "SWE.6"):
        assert prompts.REGISTER_BLOCK_NOTE not in prompts.inspector_prompt(ph)
    assert "integer-to-pointer" in prompts.REGISTER_BLOCK_NOTE and json.dumps(prompts.REGISTER_BLOCK_NOTE)
