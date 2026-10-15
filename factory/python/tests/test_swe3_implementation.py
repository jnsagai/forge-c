"""SWE3-09: allocated HAL functions really implemented; LL calls defined; no commented-out code (MISRA Dir 4.4)."""
from forge_factory.inspection.implementation import check_implementation, commented_out_code

ARCH = ("# A\n## Requirement allocation\n| SWR | Function |\n|---|---|\n| SWR-001 | `HAL_RCC_HSI_Enable` |\n"
        "| SWR-002 | HAL_RCC_HSI_Disable |\n| SWR-003 | timeout bound HAL_RCC_TIMEOUT_VALUE (macro, r30) |\n")
LL = ("#ifndef STM32N6XX_LL_RCC_H\n#define STM32N6XX_LL_RCC_H\n#include <stdint.h>\n"
      "extern volatile uint32_t ll_rcc_regs[1024U];\n"
      "static inline void LL_RCC_HSI_Enable(void)\n{\n    ll_rcc_regs[0U] |= 8U;\n}\n"
      "static inline void LL_RCC_HSI_Disable(void)\n{\n    ll_rcc_regs[0U] &= ~8U;\n}\n"
      "// LL_RCC access functions (SWE.3 LL author)\n#endif /* STM32N6XX_LL_RCC_H */\n")
HDR = ("#ifndef STM32N6XX_HAL_RCC_H\n#define STM32N6XX_HAL_RCC_H\n#include \"stm32n6xx_ll_rcc.h\"\n"
       "typedef enum {HAL_OK = 0U, HAL_ERROR = 1U} hal_status_t;\n"
       "hal_status_t HAL_RCC_HSI_Enable(void);\nhal_status_t HAL_RCC_HSI_Disable(void);\n#endif /* STM32N6XX_HAL_RCC_H */\n")
SRC = ("#include \"stm32n6xx_hal_rcc.h\"\nhal_status_t HAL_RCC_HSI_Enable(void)\n{\n    LL_RCC_HSI_Enable();\n"
       "    return HAL_OK;\n}\nhal_status_t HAL_RCC_HSI_Disable(void)\n{\n    LL_RCC_HSI_Disable();\n    return HAL_OK;\n}\n")


def ws(tmp_path, hdr=HDR, src=SRC, ll=LL):
    for rel, txt in (("workproducts/SWE.2/software_architecture.md", ARCH), ("software/hal/stm32n6xx_hal_rcc.h", hdr),
                     ("software/hal/stm32n6xx_hal_rcc.c", src), ("software/ll/stm32n6xx_ll_rcc.h", ll)):
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(txt)
    return tmp_path


def test_complete_implementation_passes(tmp_path):
    rep = check_implementation(ws(tmp_path))
    assert rep["verdict"] == "PASS", rep and rep["stats"]["hal_defined"] == 2


def test_r15_unterminated_comment_hides_everything(tmp_path):
    hidden = SRC.replace("hal_status_t HAL_RCC_HSI_Enable(void)\n{", "/* HAL_RCC API implementation\n"
                         "hal_status_t HAL_RCC_HSI_Enable(void)\n{", 1) + "*/\n"
    f = check_implementation(ws(tmp_path, src=hidden))["major_findings"]
    assert "IMPL:NOT_DEFINED:HAL_RCC_HSI_Enable" in f and any(x.startswith("IMPL:COMMENTED_OUT_CODE") for x in f)


def test_missing_declaration_static_api_and_undefined_ll_call(tmp_path):
    src = SRC.replace("hal_status_t HAL_RCC_HSI_Disable(void)\n{\n    LL_RCC_HSI_Disable();",
                      "static hal_status_t HAL_RCC_HSI_Disable(void)\n{\n    LL_RCC_HSI_Off();")
    hdr = HDR.replace("hal_status_t HAL_RCC_HSI_Disable(void);\n", "")
    f = check_implementation(ws(tmp_path, hdr=hdr, src=src))["major_findings"]
    assert {"IMPL:NOT_DECLARED:HAL_RCC_HSI_Disable", "IMPL:STATIC_API:HAL_RCC_HSI_Disable",
            "IMPL:LL_CALL_UNDEFINED:LL_RCC_HSI_Off"} <= set(f)


def test_commented_out_code_detector_ignores_prose():
    assert commented_out_code("/* Enables the HSI oscillator (see RM0486 p.480). */\nint x;\n") == []
    assert commented_out_code("// count = count + 1U;\n/*\n  LL_RCC_HSI_Enable();\n*/\n") == [1, 3]


def test_swe4_scaffold_is_idempotent_and_has_no_test_logic(tmp_path):
    from forge_factory.workflow.scaffold import TEST_CASES_MARKER, UNIT_TEST, scaffold

    assert scaffold(tmp_path)["created"] is True
    text = (tmp_path / UNIT_TEST).read_text()
    assert TEST_CASES_MARKER in text and "CHECK(\"UT-" not in text  # harness only; UT cases are agent-authored
    (tmp_path / UNIT_TEST).write_text(text.replace(TEST_CASES_MARKER, "static void ut_x(void) {}\n" + TEST_CASES_MARKER))
    assert scaffold(tmp_path)["created"] is False and "ut_x" in (tmp_path / UNIT_TEST).read_text()


def test_r26_function_pointer_helper_and_return_calls_are_not_declarations(tmp_path):
    from forge_factory.inspection.guideline import check_workspace

    helper = ("#include \"stm32n6xx_hal_rcc.h\"\n"
              "static hal_status_t hal_rcc_wait_ready(uint32_t timeout, uint32_t (*is_ready)(void))\n{\n"
              "    uint32_t count = 0U;\n    while ((is_ready() == 0U) && (count < timeout))\n    {\n        count++;\n"
              "    }\n    return (is_ready() != 0U) ? HAL_OK : HAL_TIMEOUT;\n}\n"
              "hal_status_t HAL_RCC_HSI_Enable(void)\n{\n    LL_RCC_HSI_Enable();\n"
              "    return hal_rcc_wait_ready(1000U, LL_RCC_HSI_IsReady);\n}\n"
              "hal_status_t HAL_RCC_HSI_Disable(void)\n{\n    LL_RCC_HSI_Disable();\n    return HAL_OK;\n}\n")
    w = ws(tmp_path, src=helper)
    rep = check_implementation(w)
    assert rep["verdict"] == "PASS", rep["major_findings"]
    g = check_workspace(w)
    assert not [v for v in g["violations"] if v["rule"] in ("GL-API-01", "GL-ARG-01")], g["violations"][:5]
