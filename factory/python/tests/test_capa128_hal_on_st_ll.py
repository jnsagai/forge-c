"""CAPA-128 (WO-F014-SWE3-CRCHAL-20261103-L27): a HAL work order on an ST-delivered (FROZEN brownfield) LL was not
buildable on the native HAL path - the LL test double generator rejected ST's `__STATIC_INLINE` header, and the HAL
workspace got the ST LL header (which includes stm32n6xx.h) without the LL work order's vendor includes, host CMSIS
stub or defines. The HAL work order now gets the same build inputs as the provided LL work order (hash-bound), the
double accepts the ST forms, and `static inline` (greenfield) doubles are byte-identical."""
import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest
from forge_factory import workorder as WO
from forge_factory.brownfield import cmsis
from forge_factory.common import REPO_ROOT, sha256_bytes
from forge_factory.inspection import engine
from forge_factory.mcp import sdk
from forge_factory.mcp.servers import build as B
from forge_factory.mcp.servers import tests as T
from forge_factory.workflow import ll_fake
from forge_factory.workflow import scaffold as SC

ST_LL = """#ifndef STM32N6xx_LL_WWDG_H
#define STM32N6xx_LL_WWDG_H
#ifdef __cplusplus
extern "C" {
#endif
#include "stm32n6xx.h"
#if defined (WWDG)
/**
  * @brief  Enable the window watchdog.
  * @param  WWDGx WWDG Instance
  */
__STATIC_INLINE void LL_WWDG_Enable(WWDG_TypeDef *WWDGx)
{
  SET_BIT(WWDGx->CR, WWDG_CR_WDGA);
}
__STATIC_INLINE uint32_t LL_WWDG_IsEnabled(const WWDG_TypeDef *WWDGx)
{
  return ((READ_BIT(WWDGx->CR, WWDG_CR_WDGA) == (WWDG_CR_WDGA)) ? 1UL : 0UL);
}
__STATIC_INLINE void LL_WWDG_SetCounter(WWDG_TypeDef *WWDGx, uint32_t Counter)
{
  MODIFY_REG(WWDGx->CR, WWDG_CR_T, (WWDG_CR_T & Counter));
}
__STATIC_FORCEINLINE  uint16_t LL_WWDG_GetCounter16(const WWDG_TypeDef *WWDGx)
{
  return (uint16_t)READ_REG(WWDGx->CR);
}
__STATIC_INLINE void LL_WWDG_SetWindow(WWDG_TypeDef *WWDGx, uint32_t Window, uint8_t Unused, uint32_t More)
{
  WRITE_REG(WWDGx->CFR, Window);
}
#endif
#ifdef __cplusplus
}
#endif
#endif
"""
DEV = """#ifndef STM32N6XX_H
#define STM32N6XX_H
#include "core_cm55.h"
typedef struct { __IO uint32_t CR; __IO uint32_t CFR; __IO uint32_t SR; } WWDG_TypeDef;
#define WWDG_CR_T 0x7FUL
#define WWDG_CR_WDGA 0x80UL
#define WWDG ((WWDG_TypeDef *)0x50003000UL)
#define SET_BIT(REG, BIT) ((REG) |= (BIT))
#define READ_BIT(REG, BIT) ((REG) & (BIT))
#define READ_REG(REG) ((REG))
#define WRITE_REG(REG, VAL) ((REG) = (VAL))
#define MODIFY_REG(REG, CLEARMASK, SETMASK) WRITE_REG((REG), (((READ_REG(REG)) & (~(CLEARMASK))) | (SETMASK)))
#endif
"""
ARM_CORE = '#ifndef __arm__\n#error "CMSIS core header: Arm only"\n#endif\n#include <stdint.h>\n#define __IO volatile\n#define __STATIC_INLINE static inline\n'
FAKE_TEST = """#include <stdio.h>
#define LL_FAKE_IMPLEMENTATION
#include "stm32n6xx_ll_wwdg.h"
int main(void)
{
    uint16_t c;
    ll_fake_reset();
    if (LL_WWDG_IsEnabled(WWDG) != 0U) { return 1; }
    LL_WWDG_Enable(WWDG);
    if (LL_WWDG_IsEnabled(WWDG) != 1U) { return 2; }
    LL_WWDG_SetCounter(WWDG, 0x55U);
    LL_WWDG_SetWindow(WWDG, 0x40U, 1U, 7U);
    ll_fake_return_from(LL_FAKE_LL_WWDG_GetCounter16, 1U, 0x1234U);
    c = LL_WWDG_GetCounter16(WWDG);
    if ((ll_fake_last_arg(LL_FAKE_LL_WWDG_SetCounter, 0U) != 0x55U) || (ll_fake_last_arg(LL_FAKE_LL_WWDG_SetWindow, 0U)
        != 0x40U) || (ll_fake_last_arg(LL_FAKE_LL_WWDG_SetWindow, 1U) != 1U) || (c != 0x1234U)) { return 3; }
    if (ll_fake_set_state(LL_FAKE_LL_WWDG_IsEnabled, 0U) != 1U || LL_WWDG_IsEnabled(WWDG) != 0U) { return 4; }
    printf("FAKE_OK\\n");
    return 0;
}
"""


def _hostdir(tmp_path: Path) -> Path:
    d = tmp_path / "host"
    d.mkdir()
    (d / "stm32n6xx.h").write_text(DEV)
    (d / "core_cm55.h").write_text(cmsis.CORE_STUB)  # the host CMSIS stub of the brownfield host builds
    return d


def test_st_forms_get_a_double_that_records_scalar_arguments_and_follows_state_bits(tmp_path):
    fake = ll_fake.generate(ST_LL, "ll_wwdg_regs")
    for n in ("Enable", "IsEnabled", "SetCounter", "GetCounter16", "SetWindow"):
        assert f"    LL_FAKE_LL_WWDG_{n}," in fake
    # the instance pointer is the device, never a recorded argument (no pointer-to-uint32_t cast)
    assert "(uint32_t)(WWDGx)" not in fake and "(void)(WWDGx); ll_fake_internal_set_bit(0U, 1U); " in fake
    assert "return ll_fake_internal_query_bit(LL_FAKE_LL_WWDG_IsEnabled, 0U);" in fake
    assert "return (uint16_t)ll_fake_internal_query(LL_FAKE_LL_WWDG_GetCounter16, 0U, 0U);" in fake
    assert "(void)(WWDGx); (void)(More); ll_fake_internal_record(LL_FAKE_LL_WWDG_SetWindow, (uint32_t)(Window), " \
           "(uint32_t)(Unused));" in fake
    assert "SET_BIT(WWDGx->CR" not in fake and '#include "stm32n6xx.h"' in fake  # bodies replaced, the rest kept
    d = _hostdir(tmp_path)
    (d / "stm32n6xx_ll_wwdg.h").write_text(fake)
    (tmp_path / "t.c").write_text(FAKE_TEST)
    b = subprocess.run(["clang", "-std=c11", "-Wall", "-Wextra", "-Werror", "-isystem", str(d), str(tmp_path / "t.c"),
                        "-o", str(tmp_path / "t")], capture_output=True, text=True)
    assert b.returncode == 0, b.stderr[-800:]
    assert subprocess.run([str(tmp_path / "t")], capture_output=True, text=True).stdout.strip() == "FAKE_OK"
    (tmp_path / "t.cpp").write_text('extern "C" {\n#include "stm32n6xx_ll_wwdg.h"\n}\nint main() { return 0; }\n')
    x = subprocess.run(["clang++", "-std=c++17", "-Wall", "-Wextra", "-fsyntax-only", "-isystem", str(d),
                        str(tmp_path / "t.cpp")], capture_output=True, text=True)
    assert x.returncode == 0, x.stderr[-800:]  # the GoogleTest unit test includes the double as C++


def test_static_inline_doubles_are_byte_identical():
    """Frozen sha256 of the doubles generated by the baseline a88b61a5 (greenfield LL; resumed HAL work orders compare
    their double with the regenerated one in run_unit)."""
    from test_capa038_ll_fake import LL

    assert hashlib.sha256(ll_fake.generate(LL).encode()).hexdigest() == \
        "c383e2ab7680fdc25c6e23690ce2c6a76a8d036940e2092f9716cb5c343b1c6c"
    assert hashlib.sha256(ll_fake.generate(LL.replace("ll_rcc_regs", "ll_iwdg_regs"), "ll_iwdg_regs").encode()
                          ).hexdigest() == "6c2c863a8f09d60b3f6f150a1198dfbe15ba747e7d4f2505701a87a36118b565"


ST_IWDG = """#include "stm32n6xx.h"
__STATIC_INLINE void LL_IWDG_Enable(IWDG_TypeDef *IWDGx)
{
  WRITE_REG(IWDGx->KR, 0x0000CCCCU);
}
"""
IWDG_DEV = """#ifndef STM32N6XX_H
#define STM32N6XX_H
#include "core_cm55.h"
typedef struct { __IO uint32_t KR; __IO uint32_t PR; } IWDG_TypeDef;
#define IWDG ((IWDG_TypeDef *)0x56004800UL)
#define WRITE_REG(REG, VAL) ((REG) = (VAL))
#endif
"""


@pytest.fixture()
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("FORGE_EVENTS_DIR", str(tmp_path / "state/events"))
    monkeypatch.setattr(engine.Store, "gate", lambda self, ph: {"decision": "PASS"})
    return tmp_path


def _iwdg_hal_example(tmp_path: Path) -> Path:
    spec = json.loads((REPO_ROOT / "examples/0009b-iwdg-hal/workorder.json").read_text())
    rm = REPO_ROOT / "examples/0009-iwdg-st/inputs"  # tracked inputs only
    spec["inputs"] = [{"path": str(rm / "RM0486-rev4-ch59-iwdg.md"), "role": "reference_manual_iwdg_chapter"},
                      {"path": str(rm / "RM0486-rev4-memory-map-excerpt-iwdg.md"), "role": "reference_manual_memory_map"}]
    spec.pop("simulation_performance", None)
    ex = tmp_path / "ex-capa128-iwdg-hal"
    ex.mkdir(exist_ok=True)
    (ex / "workorder.json").write_text(json.dumps(spec))
    return ex


def _source_ll(state: Path, cmsis_delivery: bool = True) -> Path:
    src = state / "workorders/WO-LL-ST/workspace"
    files = {"software/ll/stm32n6xx_ll_iwdg.h": ST_IWDG}
    if cmsis_delivery:
        files |= {"inputs/vendor/include/stm32n6xx.h": IWDG_DEV, "inputs/vendor/include/core_cm55.h": ARM_CORE}
    for rel, text in files.items():
        (src / rel).parent.mkdir(parents=True, exist_ok=True)
        (src / rel).write_text(text)
    (src / ".forge-run").mkdir()
    man = {"work_order": "WO-LL-ST", "layer": "LL", "peripheral": "iwdg"}
    if cmsis_delivery:
        man |= {"code_mode": "FROZEN", "delivery": {"code_mode": "FROZEN", "build": {
            "style": "cmsis", "defines": ["STM32N657xx"], "secure": True}},
            "delivered": [{"path": p, "sha256": sha256_bytes(t.encode()), "bytes": len(t.encode()), "licence": "X",
                           "role": "delivered_code" if p.startswith("software/") else "delivered_dependency"}
                          for p, t in files.items()]}
    (src / ".forge-run/manifest.json").write_text(json.dumps(man))
    return src


def test_hal_on_a_cmsis_ll_gets_its_vendor_build_inputs_hash_bound(env):
    src = _source_ll(env / "state")
    assert cmsis.host_flags(src) == ["-isystem", str(src / cmsis.HOST_DIR), "-DSTM32N657xx"]  # LL work order unchanged
    ws, man = WO.prepare(_iwdg_hal_example(env), "WO-HAL-ST", "WO-LL-ST")
    pb = man["provided_build"]
    assert pb["source_work_order"] == "WO-LL-ST" and pb["defines"] == ["STM32N657xx"] and pb["secure"] is True
    assert {f["path"] for f in pb["files"]} == {"inputs/vendor/include/stm32n6xx.h", "inputs/vendor/include/core_cm55.h"}
    for f in pb["files"]:
        p = ws / f["path"]
        assert p.read_bytes() == (src / f["path"]).read_bytes() and (p.stat().st_mode & 0o222) == 0
        assert sha256_bytes(p.read_bytes()) == f["sha256"] and f["licence"] == "X"
    assert not cmsis.is_cmsis(ws) and cmsis.provided_build(ws) == pb  # the HAL itself is no brownfield delivery
    hd = ws / cmsis.HOST_DIR
    assert cmsis.host_flags(ws) == ["-isystem", str(hd), "-include", str(hd / "forge_host_device.h"), "-DSTM32N657xx"]
    assert cmsis.host_flags(ws, force_include=False) == ["-isystem", str(hd), "-DSTM32N657xx"]
    assert cmsis.target_flags(ws) == ["-isystem", str(ws / cmsis.VENDOR_DIR), "-DSTM32N657xx", "-mcmse"]
    assert (hd / "core_cm55.h").read_text() == cmsis.CORE_STUB  # the host stub, never the Arm-only core header
    assert SC.unit_test(ws).endswith(".cpp")  # the HAL keeps its GoogleTest unit tests
    p = ws / "inputs/vendor/include/stm32n6xx.h"
    p.chmod(0o644)
    p.write_text(IWDG_DEV + "/* edited */\n")
    with pytest.raises(ValueError, match="PROVIDED_BUILD_INPUT_CHANGED:inputs/vendor/include/stm32n6xx.h"):
        cmsis.host_flags(ws)


def test_a_changed_source_vendor_file_is_refused_and_greenfield_ll_adds_nothing(env):
    src = _source_ll(env / "state")
    (src / "inputs/vendor/include/stm32n6xx.h").write_text(IWDG_DEV + "/* not the delivered file */\n")
    with pytest.raises(ValueError, match="PROVIDED_BUILD_INPUT_MISMATCH:WO-LL-ST:inputs/vendor/include/stm32n6xx.h"):
        WO.prepare(_iwdg_hal_example(env), "WO-HAL-ST-2", "WO-LL-ST")
    shutil.rmtree(env / "state/workorders/WO-LL-ST")
    _source_ll(env / "state", cmsis_delivery=False)
    ws, man = WO.prepare(_iwdg_hal_example(env), "WO-HAL-GF", "WO-LL-ST")
    assert "provided_build" not in man and not (ws / cmsis.VENDOR_DIR).exists()
    assert cmsis.host_flags(ws) == [] and cmsis.target_flags(ws) == []


HAL_H = """#ifndef STM32N6XX_HAL_IWDG_H
#define STM32N6XX_HAL_IWDG_H
#include <stdint.h>
#include "stm32n6xx_ll_iwdg.h"
uint32_t HAL_IWDG_Start(void);
#endif /* STM32N6XX_HAL_IWDG_H */
"""
HAL_C = """#include "stm32n6xx_hal_iwdg.h"
uint32_t HAL_IWDG_Start(void)
{
    LL_IWDG_Enable(IWDG);
    return 0U;
}
"""
UT = """TEST(SWU_HAL_01, UT_001)
{
    ut_reset();
    EXPECT_EQ(HAL_IWDG_Start(), 0U);
    EXPECT_EQ(ll_fake_calls(LL_FAKE_LL_IWDG_Enable), 1U);
}
"""
IT = """#include <stdio.h>
#include "stm32n6xx_hal_iwdg.h"
int main(void)
{
    /** @test IT-001 */
    (void)HAL_IWDG_Start();
    printf("IT-001 %s\\n", forge_host_iwdg.KR == 0x0000CCCCU ? "PASS" : "FAIL");
    return forge_host_iwdg.KR == 0x0000CCCCU ? 0 : 1;
}
"""


def _ctx(ws, srv, op, role, ph):
    return sdk.ToolContext(srv, op, role, ph, ws, "r")


def test_native_hal_path_builds_and_tests_on_the_provided_cmsis_ll(env):
    """The HAL unit test (GoogleTest) on the generated double, the host integration test on the real ST-style LL (the
    HAL's own `IWDG` reaches the host RAM struct) and the target compile all build with the provided build inputs."""
    from forge_factory.gtest_toolchain import GtestToolchainError, load

    try:
        load()
    except GtestToolchainError:
        pytest.skip("pinned GoogleTest toolchain not installed")
    _source_ll(env / "state")
    ws, _ = WO.prepare(_iwdg_hal_example(env), "WO-HAL-ST", "WO-LL-ST")
    (ws / "software/hal").mkdir(parents=True, exist_ok=True)
    (ws / "software/hal/stm32n6xx_hal_iwdg.h").write_text(HAL_H)
    (ws / "software/hal/stm32n6xx_hal_iwdg.c").write_text(HAL_C)
    assert SC._scaffold(ws)["ll_fake"] and not ll_fake.modified(ws)
    p = ws / SC.unit_test(ws)
    p.write_text(p.read_text().replace(SC.TEST_CASES_MARKER, UT + SC.TEST_CASES_MARKER))
    r = T.run_unit(_ctx(ws, "forge-tests-mcp", "run_unit", "swe4-author", "SWE.4"), T.RunIn())
    assert r["status"] == "PASS", r["issues"]
    (ws / "software/tests/integration").mkdir(parents=True)
    (ws / "software/tests/integration/test_iwdg_integration.c").write_text(IT)
    r = T.run_integration(_ctx(ws, "forge-tests-mcp", "run_integration", "swe5-author", "SWE.5"), T.RunIn())
    assert r["status"] == "PASS", r["issues"]
    for prof in ("host-clang",) + (("target-cm55-gcc",) if shutil.which("arm-none-eabi-gcc") else ()):
        r = B.compile_(_ctx(ws, "forge-build-mcp", "compile", "swe3-author", "SWE.3"), B.CompileIn(profile=prof))
        assert r["status"] == "PASS", (prof, r["summary"], r["issues"])


ST = Path(os.path.expandvars("$FORGE_DATA_ROOT/inputs/st/stm32n6xx-hal-driver-v1.4.0/src/stm32n6xx-hal-driver-1.4.0/Inc"))


@pytest.mark.skipif(not (ST / "stm32n6xx_ll_crc.h").is_file(), reason="ST downloads not available")
def test_every_st_ll_header_of_the_benchmark_gets_a_double():
    for p in ("crc", "wwdg", "iwdg", "gpio", "spi", "usart", "tim", "rcc", "bus"):
        fake = ll_fake.generate((ST / f"stm32n6xx_ll_{p}.h").read_text(errors="replace"), f"ll_{p}_regs")
        assert "LL_FAKE_COUNT" in fake and "(uint32_t)(" + p.upper() + "x)" not in fake, p
