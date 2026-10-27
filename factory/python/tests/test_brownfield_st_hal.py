"""Feature 015 F015-T065 (ST HAL code FROZEN): register effects of ST's handle-based classic HAL. The contract's C
argument for a handle is a compound literal; its designated initializers bind h->Instance and h->Init.X, the handle is
passed on into callees and expression macros, and decidable if/else chains and switch statements select their branch.
Unbound handle fields (h->State, ...) stay undecidable, so their branches are all kept."""
from forge_factory.brownfield import scope as S

MACROS = {"CRC": "((CRC_TypeDef *) CRC_BASE)", "CRC_CR_RESET": "(0x1UL << 0U)", "CRC_CR_POLYSIZE": "(0x3UL << 3U)",
          "CRC_POLYLENGTH_32B": "0x00000000U", "CRC_POLYLENGTH_8B": "(0x2UL << 3U)", "DEFAULT_CRC32_POLY": "0x04C11DB7U",
          "DEFAULT_POLYNOMIAL_ENABLE": "((uint8_t)0x00U)", "DEFAULT_POLYNOMIAL_DISABLE": "((uint8_t)0x01U)",
          "CRC_INPUTDATA_FORMAT_WORDS": "0x00000003U", "CRC_INPUTDATA_FORMAT_BYTES": "0x00000001U"}
SRC = """
#define __HAL_CRC_DR_RESET(__HANDLE__) ((__HANDLE__)->Instance->CR |= CRC_CR_RESET)
HAL_StatusTypeDef HAL_CRCEx_Polynomial_Set(CRC_HandleTypeDef *hcrc, uint32_t Pol, uint32_t PolyLength)
{
  WRITE_REG(hcrc->Instance->POL, Pol);
  MODIFY_REG(hcrc->Instance->CR, CRC_CR_POLYSIZE, PolyLength);
  return HAL_OK;
}
HAL_StatusTypeDef HAL_CRC_Init(CRC_HandleTypeDef *hcrc)
{
  if (hcrc == NULL)
  {
    return HAL_ERROR;
  }
  if (hcrc->State == HAL_CRC_STATE_RESET)
  {
    HAL_CRC_MspInit(hcrc);
  }
  if (hcrc->Init.DefaultPolynomialUse == DEFAULT_POLYNOMIAL_ENABLE)
  {
    WRITE_REG(hcrc->Instance->POL, DEFAULT_CRC32_POLY);
    MODIFY_REG(hcrc->Instance->CR, CRC_CR_POLYSIZE, CRC_POLYLENGTH_32B);
  }
  else
  {
    if (HAL_CRCEx_Polynomial_Set(hcrc, hcrc->Init.GeneratingPolynomial, hcrc->Init.CRCLength) != HAL_OK)
    {
      return HAL_ERROR;
    }
  }
  return HAL_OK;
}
uint32_t HAL_CRC_Calculate(CRC_HandleTypeDef *hcrc, uint32_t pBuffer[], uint32_t BufferLength)
{
  __HAL_CRC_DR_RESET(hcrc);
  switch (hcrc->InputDataFormat)
  {
    case CRC_INPUTDATA_FORMAT_WORDS:
      hcrc->Instance->DR = pBuffer[0];
      break;
    case CRC_INPUTDATA_FORMAT_BYTES:
      hcrc->Instance->DR = 0x11U;
      break;
    default:
      break;
  }
  return hcrc->Instance->DR;
}
"""
DEFS = {d.name: d for d in S.index(SRC, "hal.c")}
H = "&(CRC_HandleTypeDef){ .Instance = CRC, .Init = { .DefaultPolynomialUse = %s%s }, .InputDataFormat = %s }"


def fx(fn, *args):
    return [(e.op, e.register, e.mask) for e in S.register_effects(DEFS[fn], MACROS, "cmsis", list(args), DEFS,
                                                                   prefix="CRC") if e.op != "read"]


def test_handle_fields_from_a_compound_literal():
    assert S.handle_fields(H % ("DEFAULT_POLYNOMIAL_ENABLE", "", "CRC_INPUTDATA_FORMAT_WORDS")) == {
        "Instance": "CRC", "Init.DefaultPolynomialUse": "DEFAULT_POLYNOMIAL_ENABLE",
        "InputDataFormat": "CRC_INPUTDATA_FORMAT_WORDS"}
    assert S.handle_fields("&(CRC_HandleTypeDef){ .Init.CRCLength = CRC_POLYLENGTH_8B }") == {
        "Init.CRCLength": "CRC_POLYLENGTH_8B"}
    assert S.handle_fields("0x12U") is None and S.handle_fields("&buf") is None


def test_the_configuration_selects_the_branch_and_the_handle_reaches_the_callee():
    default = fx("HAL_CRC_Init", H % ("DEFAULT_POLYNOMIAL_ENABLE", "", "CRC_INPUTDATA_FORMAT_WORDS"))
    assert default == [("write", "CRC_POL", 0x04C11DB7), ("modify", "CRC_CR", 0)]
    custom = fx("HAL_CRC_Init", H % ("DEFAULT_POLYNOMIAL_DISABLE", ", .GeneratingPolynomial = 0x9BU, .CRCLength = "
                                     "CRC_POLYLENGTH_8B", "CRC_INPUTDATA_FORMAT_WORDS"))
    assert custom == [("write", "CRC_POL", 0x9B), ("modify", "CRC_CR", 0x10)]       # through HAL_CRCEx_Polynomial_Set
    both = fx("HAL_CRC_Init", "&(CRC_HandleTypeDef){ .Instance = CRC }")              # selector unbound: both kept
    assert ("write", "CRC_POL", 0x04C11DB7) in both and ("write", "CRC_POL", None) in both


def test_expression_macros_and_switch_cases():
    words = fx("HAL_CRC_Calculate", H % ("DEFAULT_POLYNOMIAL_ENABLE", "", "CRC_INPUTDATA_FORMAT_WORDS"), "buf", "1U")
    assert ("set", "CRC_CR", 1) in words and [r for r in words if r[1] == "CRC_DR"] == [("write", "CRC_DR", None)]
    byts = fx("HAL_CRC_Calculate", H % ("DEFAULT_POLYNOMIAL_ENABLE", "", "CRC_INPUTDATA_FORMAT_BYTES"), "buf", "1U")
    assert [r for r in byts if r[1] == "CRC_DR"] == [("write", "CRC_DR", 0x11)]
    unbound = fx("HAL_CRC_Calculate", "&(CRC_HandleTypeDef){ .Instance = CRC }", "buf", "1U")
    assert len([r for r in unbound if r[1] == "CRC_DR"]) == 2


def test_an_ll_call_is_bound_exactly_as_before():
    d = S.index("static inline void LL_CRC_SetPolynomialSize(CRC_TypeDef *CRCx, uint32_t PolySize)\n"
                "{\n  MODIFY_REG(CRCx->CR, CRC_CR_POLYSIZE, PolySize);\n}\n", "ll.h")[0]
    assert [(e.op, e.register, e.mask) for e in S.register_effects(d, MACROS, "cmsis", ["CRC", "CRC_POLYLENGTH_8B"],
                                                                   prefix="CRC")] == [("modify", "CRC_CR", 0x10)]


TEMPLATE = (b"/*#define HAL_ADC_MODULE_ENABLED   */\n/*#define HAL_CRC_MODULE_ENABLED   */\r\n"
            b"#define HAL_GPIO_MODULE_ENABLED\n#define HAL_RCC_MODULE_ENABLED\n#define HSE_VALUE 48000000UL\n")


def test_the_hal_conf_template_is_configured_with_exactly_the_listed_modules():
    import pytest
    from forge_factory.brownfield import delivery as D

    out = D.configure_hal_conf(TEMPLATE, ["CRC"]).decode()
    assert "\n#define HAL_CRC_MODULE_ENABLED\r\n" in out and "#define HSE_VALUE 48000000UL" in out
    assert "/*#define HAL_GPIO_MODULE_ENABLED */" in out and "/*#define HAL_RCC_MODULE_ENABLED */" in out
    assert out.count("_MODULE_ENABLED") == 4 and "/*#define HAL_ADC_MODULE_ENABLED */" in out
    with pytest.raises(D.DeliveryBlocked, match="DELIVERY_HAL_MODULE_UNKNOWN:XYZ"):
        D.configure_hal_conf(TEMPLATE, ["XYZ"])


def _st_hal_ws(tmp_path, monkeypatch):
    import json
    import shutil

    import pytest
    from forge_factory import workorder as WO
    from forge_factory.common import REPO_ROOT

    if shutil.which("arm-none-eabi-gcc") is None:
        pytest.skip("GNU Arm toolchain not installed")
    ex = REPO_ROOT / "examples/0014d-st-cube-crc-hal"
    src = json.loads((ex / "workorder.json").read_text())["delivery"]["source"]
    import os

    if not Path(os.path.expandvars(src)).is_dir():
        pytest.skip("ST stm32n6xx-hal-driver v1.4.0 not on this host")
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("FORGE_EVENTS_DIR", str(tmp_path / "state/events"))
    ws, _ = WO.prepare(ex, "WO-ST-HAL-CRC")
    return ws, json.loads((ws / ".forge-run/manifest.json").read_text())


from pathlib import Path  # noqa: E402


def test_st_crc_hal_intake_needs_no_provided_ll_and_builds(tmp_path, monkeypatch):
    """F015-T065: ST's CRC HAL with its framework headers and the configured hal_conf.h; no provided LL work order,
    no LL test double (the HAL accesses the registers through its handle)."""
    from forge_factory.common import state_dir

    ws, m = _st_hal_ws(tmp_path, monkeypatch)
    assert m["layer"] == "HAL" and m["hal_standalone"] is True and "hal_unit_isolation" not in m and m["provided"] == []
    import json

    intake = json.loads((state_dir() / "workorders/WO-ST-HAL-CRC/delivered/intake.json").read_text())
    assert intake["status"] == "ACCEPTED" and intake["build_check"]["status"] == "PASS"
    conf = [r for r in intake["files"] if r["path"].endswith("stm32n6xx_hal_conf.h")][0]
    assert conf["configured_from"]["hal_modules"] == ["CRC"] and len(conf["configured_from"]["sha256"]) == 64


def test_st_hal_prompts_describe_the_delivered_handle_api(tmp_path, monkeypatch):
    import re

    from forge_factory.workflow import prompts as P
    from forge_factory.workflow.builder import build

    ws, m = _st_hal_ws(tmp_path, monkeypatch)
    build("WO-ST-HAL-CRC", goal="x", sections={}, layer="HAL", trace=True, brownfield="FROZEN", peripheral="crc",
          delivery_style="cmsis", hal_standalone=True)
    texts = [P.unit_test_author_prompt(), P.target_test_author_prompt(), P.robot_test_author_prompt()] + \
        [P.author_prompt(p) for p in ("SWE.1", "SWE.2", "SWE.4", "SWE.5", "SWE.6")]
    joined = " ".join(texts)
    assert not re.search(r"\bll_crc_regs\b|LL_CRC_|hal_crc_config_t|hal_status_t|stm32n6xx_ll_crc|forge_host_rcc|"
                         r"HAL_CRC_TIMEOUT_VALUE|CRC_CSR", joined)
    assert "CRC_HandleTypeDef" in joined and '#include "stm32n6xx_hal.h"' in joined and "forge_host_crc" in joined
    build("WO-X", goal="x", sections={}, layer="HAL", trace=True, brownfield="FROZEN", peripheral="crc",
          delivery_style="cmsis", hal_standalone=False)
    assert "CRC_HandleTypeDef" not in P.author_prompt("SWE.2")                      # factory HAL texts unchanged


def _manifest_ws(tmp_path, peripheral, standalone=True):
    import json

    (tmp_path / ".forge-run").mkdir(parents=True)
    (tmp_path / ".forge-run/manifest.json").write_text(json.dumps(
        {"layer": "HAL", "hal_standalone": standalone, "peripheral": peripheral}))
    return tmp_path


def test_host_tests_map_the_concrete_instance_the_st_hal_compares_against(tmp_path):
    """ST UART_SetConfig compares huart->Instance with USART1 (UART_GETCLOCKSOURCE): on the host USART1 must be the
    RAM struct too, or the HAL dereferences the device address (host test exit-11)."""
    from forge_factory.brownfield import cmsis

    h = cmsis.host_header(_manifest_ws(tmp_path, "usart"))
    assert "#define USART (&forge_host_usart)" in h and "#define USART1 (&forge_host_usart)" in h
    crc = cmsis.host_header(_manifest_ws(tmp_path / "c", "crc"))                     # instance == prefix: once
    assert crc.count("#define CRC (&forge_host_crc)") == 1


def test_standalone_hal_views_need_no_ll_component_and_no_timeout_path_without_waits(tmp_path):
    from forge_factory.inspection import views
    from forge_factory.layer import components

    crc, usart = _manifest_ws(tmp_path / "c", "crc"), _manifest_ws(tmp_path / "u", "usart")
    assert components("HAL", crc) == ("stm32n6xx_hal_crc",)
    assert components("HAL", _manifest_ws(tmp_path / "f", "crc", standalone=False)) == ("stm32n6xx_hal_crc",
                                                                                         "stm32n6xx_ll_crc")
    for ws, comp in ((crc, "stm32n6xx_hal_crc"), (usart, "stm32n6xx_hal_uart")):
        (ws / "workproducts/SWE.2").mkdir(parents=True)
        (ws / views.STATIC).write_text(f'@startuml\ncomponent "{comp}" as SWC_HAL\n@enduml\n')
        (ws / views.DYNAMIC).write_text("@startuml\nparticipant Caller\nCaller -> SWC_HAL : HAL_OK\n@enduml\n")
    assert not [f for f in views.check_views(crc)["major_findings"] if "MISSING_COMPONENT" in f or "TIMEOUT" in f]
    assert "VIEWS:DYNAMIC_MISSING_TIMEOUT_PATH" in views.check_views(usart)["major_findings"]  # UART waits (HAL_GetTick)
