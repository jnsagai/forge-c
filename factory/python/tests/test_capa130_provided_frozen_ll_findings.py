"""CAPA-130 (CRC HAL on the ST CRC LL, L27 follow-up): cppcheck findings located in the PROVIDED, FROZEN ST LL header
(MISRA-20.7 in ST's register macros) were HAL issues; they are now delivered-code findings for the owner (package
gaps unless dispositioned), as in the LL work order. Findings in the HAL's own code stay HAL issues."""
import shutil
from pathlib import Path

import pytest
from forge_factory import workorder as WO
from forge_factory.brownfield import package as BP
from forge_factory.brownfield import provided_frozen_paths
from forge_factory.mcp import sdk
from forge_factory.mcp.servers import analysis as A
from test_capa128_hal_on_st_ll import _iwdg_hal_example, _source_ll, env  # noqa: F401 - pytest fixture

pytestmark = pytest.mark.skipif(not shutil.which("cppcheck") or not Path(A.MISRA_ADDON).is_file(),
                                reason="cppcheck with the MISRA addon not available")
MACRO = "#define LL_IWDG_WriteReg(__INSTANCE__, __REG__, __VALUE__) WRITE_REG(__INSTANCE__->__REG__, __VALUE__)\n"
HAL_H = ("#ifndef STM32N6XX_HAL_IWDG_H\n#define STM32N6XX_HAL_IWDG_H\n#include <stdint.h>\n"
         "#include \"stm32n6xx_ll_iwdg.h\"\nuint32_t HAL_IWDG_Start(uint32_t on);\n#endif /* STM32N6XX_HAL_IWDG_H */\n")
HAL_C = ("#include \"stm32n6xx_hal_iwdg.h\"\nuint32_t HAL_IWDG_Start(uint32_t on)\n{\n    uint32_t status = 1U;\n"
         "    if (on != 0U)\n    {\n        LL_IWDG_Enable(IWDG);\n        status = 0U;\n    }\n    return status;\n}\n")
HAL_C_TWO_RETURNS = ("#include \"stm32n6xx_hal_iwdg.h\"\nuint32_t HAL_IWDG_Start(uint32_t on)\n{\n    if (on != 0U)\n"
                     "    {\n        LL_IWDG_Enable(IWDG);\n        return 0U;\n    }\n    return 1U;\n}\n")


def _cppcheck(ws):
    return A.cppcheck(sdk.ToolContext("forge-analysis-mcp", "cppcheck", "swe3-author", "SWE.3", ws, "r"), A.AnalyzeIn())


def _hal(env, monkeypatch):  # noqa: F811
    import test_capa128_hal_on_st_ll as T128

    monkeypatch.setattr(T128, "ST_IWDG", T128.ST_IWDG.replace('#include "stm32n6xx.h"\n',
                                                               '#include "stm32n6xx.h"\n' + MACRO))
    _source_ll(env / "state")
    ws, man = WO.prepare(_iwdg_hal_example(env), "WO-HAL-ST", "WO-LL-ST")
    (ws / "software/hal").mkdir(parents=True, exist_ok=True)
    (ws / "software/hal/stm32n6xx_hal_iwdg.h").write_text(HAL_H)
    return ws, man


def test_provided_frozen_ll_findings_are_delivered_code_not_hal_issues(env, monkeypatch):  # noqa: F811
    ws, man = _hal(env, monkeypatch)
    assert man["provided"][0]["delivered_code_mode"] == "FROZEN"
    assert provided_frozen_paths(man) == ["software/ll/stm32n6xx_ll_iwdg.h"]
    (ws / "software/hal/stm32n6xx_hal_iwdg.c").write_text(HAL_C)
    r = _cppcheck(ws)
    assert r["status"] == "PASS", r["issues"]
    assert any(i.startswith("DELIVERED_CODE:MISRA-20.7:software/ll/stm32n6xx_ll_iwdg.h:") for i in r["issues"])
    gaps = BP.findings(ws)  # the owner sees them in the HAL's package, as in the LL work order's
    assert gaps and all(g["id"].startswith("DELIVERED_CODE:STATIC_ANALYSIS:MISRA-20.7:software/ll/") for g in gaps)
    assert "source work order WO-LL-ST" in gaps[0]["detail"]


def test_findings_in_the_hals_own_code_stay_hal_issues(env, monkeypatch):  # noqa: F811
    ws, _ = _hal(env, monkeypatch)
    (ws / "software/hal/stm32n6xx_hal_iwdg.c").write_text(HAL_C_TWO_RETURNS)
    r = _cppcheck(ws)
    assert r["status"] == "FAIL" and any(i.startswith("MISRA-15.5:stm32n6xx_hal_iwdg.c") for i in r["issues"])


def test_greenfield_provided_ll_is_not_classed_delivered(env):  # noqa: F811
    _source_ll(env / "state", cmsis_delivery=False)
    ws, man = WO.prepare(_iwdg_hal_example(env), "WO-HAL-GF", "WO-LL-ST")
    assert "delivered_code_mode" not in man["provided"][0] and provided_frozen_paths(man) == []
    assert A.frozen_paths(ws) == set() and A.vendor_paths(ws) == set() and BP.findings(ws) == []
