"""SWE3-08: RCC register definitions generated from RM0486 inputs and verified against them (deterministic)."""
import json
import os
import subprocess
import sys

from forge_factory.inspection.regmap import FUNCTIONS_MARKER, check_regmap, generate, parse_section

RM_CR = """<!-- source: RM0486 section 14.10.1 starting p.479 -->
#### 14.10.1 RCC control register (RCC_CR)
```text
                Address offset: 0x0
                Reset value: 0x0000 0008
         Bits 31:12 Reserved, must be kept at reset value.
                Bit 11 PLL4ON: PLL4 enable
           Bits 7:5 Reserved, must be kept at reset value.
             Bit 4 HSEON: HSE oscillator enable
             Bit 3 HSION: HSI oscillator enable
```
"""
RM_CFG = """#### 14.10.9 RCC configuration register (RCC_CFGR1)
                Address offset: 0x20
            Bits 25:24 SYSSW[1:0]: system clock switch
             Bits 21:20 CPUSW: CPU clock switch
"""
ARCH = ("# A\n## Components\nx\n## Interfaces\nx\n## Requirement allocation\n| R | F |\n|---|---|\n| SWR-001 | f |\n"
        "## Register table\n| Name | Offset |\n|---|---|\n| RCC_CR | 0x0 |\n| RCC_CFGR1 | 0x20 |\n| RCC_NOPE | 0x9 |\n")


def ws_with_inputs(tmp_path):
    sec = tmp_path / "inputs/sections/RM0486"
    sec.mkdir(parents=True)
    (sec / "14.10.1_RCC_control_register_RCC_CR.md").write_text(RM_CR)
    (sec / "14.10.9_RCC_CFGR1.md").write_text(RM_CFG.replace("SYSSW[1:0]", "SYSSW"))
    (tmp_path / "workproducts/SWE.2").mkdir(parents=True)
    (tmp_path / "workproducts/SWE.2/software_architecture.md").write_text(ARCH)
    return tmp_path


def test_parse_section_fields_and_offset():
    r = parse_section(RM_CR)
    assert r["name"] == "RCC_CR" and r["offset"] == 0 and r["reset"] == "0x00000008"
    assert r["fields"] == {"PLL4ON": (11, 11), "HSEON": (4, 4), "HSION": (3, 3)}  # Reserved ranges excluded


def test_generate_from_swe2_table_and_conformance_pass(tmp_path):
    ws = ws_with_inputs(tmp_path)
    res = generate(ws)
    assert res["status"] == "PARTIAL" and res["issues"] == ["NOT_IN_RM:RCC_NOPE"] and res["registers"] == 2
    h = (ws / "software/ll/stm32n6xx_ll_rcc.h").read_text()
    assert "#define LL_RCC_CR_HSION_MSK 0x00000008U" in h and "#define LL_RCC_CFGR1_SYSSW_MSK 0x03000000U" in h
    assert "#define LL_RCC_CFGR1_OFFSET 0x020U" in h and FUNCTIONS_MARKER in h
    assert check_regmap(ws)["verdict"] == "PASS"
    assert json.loads((ws / "verification/static/register_map_generation.json").read_text())["not_in_rm_inputs"] == \
        ["RCC_NOPE"]


def test_invented_or_altered_definitions_fail(tmp_path):
    ws = ws_with_inputs(tmp_path)
    generate(ws)
    p = ws / "software/ll/stm32n6xx_ll_rcc.h"
    p.write_text(p.read_text().replace("LL_RCC_CR_HSION_MSK 0x00000008U", "LL_RCC_CR_HSION_MSK 0x00000001U")
                 .replace(FUNCTIONS_MARKER, "#define LL_RCC_LSEON_OFFSET 0x1U\n#define LL_RCC_CR_FOO_POS 3U"))
    f = check_regmap(ws)["major_findings"]
    assert "REGMAP:MSK_MISMATCH:CR_HSION:0x1!=0x8" in f and "REGMAP:OFFSET_FOR_UNKNOWN_REGISTER:LSEON" in f
    assert "REGMAP:POS_FOR_UNKNOWN_FIELD:CR_FOO" in f


def test_verify_node_fails_on_register_map_even_if_guideline_passes(tmp_path):
    from test_guideline_check import HAL_C, HAL_H, LL_H

    ws = ws_with_inputs(tmp_path)
    (ws / "software/hal").mkdir(parents=True)
    (ws / "software/ll").mkdir(parents=True)
    (ws / "software/hal/stm32n6xx_hal_rcc.h").write_text(HAL_H)
    (ws / "software/hal/stm32n6xx_hal_rcc.c").write_text(HAL_C)
    (ws / "software/ll/stm32n6xx_ll_rcc.h").write_text(LL_H.replace("#endif", "#define LL_RCC_CR_OFFSET 0x004U\n#endif"))
    r = subprocess.run([sys.executable, "-m", "forge_factory.inspection.gate", "--workspace", str(ws), "--phase", "SWE.3",
                        "--step", "verify", "--check", "hal_guideline"], capture_output=True, text=True,
                       env={**os.environ, "FORGE_EVENTS_DIR": str(tmp_path / "ev")})
    out = json.loads(r.stdout)
    assert r.returncode != 0 and out["verdict"] == "FAIL" and out["violations"] == 0
    assert out["register_map_findings"] == ["REGMAP:OFFSET_MISMATCH:CR:0x4!=0x0"]
