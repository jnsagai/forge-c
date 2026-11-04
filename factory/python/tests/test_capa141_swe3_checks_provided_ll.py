"""CAPA-141 (CRC HAL L31D SWE.3): SWE3-07 counted Cube2-guideline violations located in the provided FROZEN ST LL
header against the HAL, and SWE3-08 raised REGMAP:NO_REGISTER_DEFINES for a HAL on a provided CMSIS LL. The provided
LL's violations are now delivered-code observations (package, CAPA-130 path) and the HAL is checked for defining no
registers itself; greenfield HALs and LL work orders keep their reports."""
from pathlib import Path

from forge_factory import workorder as WO
from forge_factory.brownfield import package as BP
from forge_factory.inspection.guideline import check_workspace
from forge_factory.inspection.regmap import check_defines, check_regmap, _ident, _short, rm_registers
from test_capa128_hal_on_st_ll import _iwdg_hal_example, _source_ll, env  # noqa: F401 - pytest fixture

HAL_H = ("#ifndef STM32N6XX_HAL_IWDG_H\n#define STM32N6XX_HAL_IWDG_H\n#include <stdint.h>\n"
         "#include \"stm32n6xx_ll_iwdg.h\"\ntypedef enum { HAL_OK = 0, HAL_ERROR = 1 } hal_status_t;\n"
         "hal_status_t HAL_IWDG_Start(uint32_t on);\n#endif /* STM32N6XX_HAL_IWDG_H */\n")
HAL_C = ("#include \"stm32n6xx_hal_iwdg.h\"\nhal_status_t HAL_IWDG_Start(uint32_t on)\n{\n    hal_status_t status = HAL_ERROR;\n"
         "    if (on != 0U)\n    {\n        LL_IWDG_Enable(IWDG);\n        status = HAL_OK;\n    }\n    return status;\n}\n")
LL = "software/ll/stm32n6xx_ll_iwdg.h"


def _hal(env, cmsis=True):  # noqa: F811
    _source_ll(env / "state", cmsis_delivery=cmsis)
    ws, man = WO.prepare(_iwdg_hal_example(env), "WO-HAL-141" + ("" if cmsis else "-GF"), "WO-LL-ST")
    (ws / "software/hal").mkdir(parents=True, exist_ok=True)
    (ws / "software/hal/stm32n6xx_hal_iwdg.h").write_text(HAL_H)
    (ws / "software/hal/stm32n6xx_hal_iwdg.c").write_text(HAL_C)
    return ws, man


def test_provided_frozen_ll_guideline_violations_are_not_hal_findings(env):  # noqa: F811
    ws, man = _hal(env)
    assert man["provided"][0]["delivered_code_mode"] == "FROZEN"
    rep = check_workspace(ws)
    assert all(v["file"] != LL for v in rep["violations"]), rep["violations"]
    assert rep["provided_frozen_files"] == [LL]
    assert rep["provided_frozen_violations"] and all(v["file"] == LL for v in rep["provided_frozen_violations"])


def test_a_violation_in_the_hals_own_file_stays_a_finding(env):  # noqa: F811
    ws, _ = _hal(env)
    (ws / "software/hal/_reg_probe.h").write_text("#ifndef X\n#define X 1\n#endif\n")
    rep = check_workspace(ws)
    own = {(v["rule"], v["file"]) for v in rep["violations"]}
    assert ("GL-FILE-01", "software/hal/_reg_probe.h") in own and rep["verdict"] == "FAIL"


def test_the_package_reports_the_provided_ll_observations_once_per_rule_and_file(env):  # noqa: F811
    ws, _ = _hal(env)
    gaps = [g for g in BP.findings(ws) if g["id"].startswith("DELIVERED_CODE:GUIDELINE:")]
    assert gaps and all(f":{LL} (" in g["id"] for g in gaps) and "source work order WO-LL-ST" in gaps[0]["detail"]
    assert len({g["id"] for g in gaps}) == len(gaps)


def test_regmap_for_a_hal_on_a_provided_cmsis_ll_checks_the_hal_defines_no_registers(env):  # noqa: F811
    ws, _ = _hal(env)
    rep = check_regmap(ws)
    assert rep["verdict"] == "PASS" and rep["mode"] == "PROVIDED_LL", rep
    assert rep["stats"]["register_map_verified_in"] == "WO-LL-ST" and "REGMAP:NO_REGISTER_DEFINES" not in str(rep)
    (ws / "software/hal/stm32n6xx_hal_iwdg.c").write_text(HAL_C + "#define IWDG_KR_OFFSET 0x00U\n")
    bad = check_regmap(ws)
    assert bad["verdict"] == "FAIL" and bad["major_findings"][0].startswith(
        "REGMAP:HAL_DEFINES_REGISTER:IWDG_KR_OFFSET:software/hal/stm32n6xx_hal_iwdg.c")


def test_a_greenfield_hal_keeps_both_reports(env):  # noqa: F811
    ws, man = _hal(env, cmsis=False)
    assert "provided_build" not in man and all("delivered_code_mode" not in p for p in man["provided"])
    rep = check_workspace(ws)
    assert "provided_frozen_violations" not in rep and "provided_frozen_files" not in rep
    i = _ident(ws)
    p = ws / i["header"]
    want = (check_defines(p.read_text(errors="replace"), {_short(k): v for k, v in rm_registers(ws).items()},
                          i["define"]) if p.is_file() else {"verdict": "FAIL", "major_findings": ["REGMAP:NO_LL_HEADER"],
                                                           "stats": {}})
    got = check_regmap(ws)
    assert got == want and "mode" not in got
