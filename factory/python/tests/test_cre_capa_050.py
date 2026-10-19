"""CAPA-050 (LL r166): the SWE.2 register table named rows RCC_CR.HSION (register.field); the register map generator
read only bare RCC_ names, found none and BLOCKED without writing the LL compile unit. The SWE.3 author then wrote
its own compile unit, which CAPA-046 rejects and which it has no tool to delete, until the rework budget ran out."""
import json

from forge_factory import layer as LY
from forge_factory.inspection.regmap import architecture_registers, generate
from test_swe3_regmap import ws_with_inputs

R166_TABLE = ("## Register table\n| Name | Offset | Bit position(s) | Access | RM0486 page |\n| --- | --- | --- | --- | --- |\n"
              "| RCC_CR.HSION | 0x000 | 3 | read/write | p.480 |\n| RCC_CR.HSEON | 0x000 | 4 | read/write | p.480 |\n"
              "| `RCC_CFGR1`[SYSSW] | 0x020 | 25:24 | read/write | p.490 |\n| RCC_CR (HSION) | 0x000 | 3 | rw | p.480 |\n")


def _ll(ws, table):
    p = ws / "workproducts/SWE.2/software_architecture.md"
    p.write_text(p.read_text().split("## Register table")[0] + table)
    (ws / ".forge-run").mkdir(exist_ok=True)
    (ws / ".forge-run/manifest.json").write_text(json.dumps({"layer": "LL"}))
    return ws


def test_capa050_register_dot_field_rows_name_their_register(tmp_path):
    ws = _ll(ws_with_inputs(tmp_path), R166_TABLE)
    assert architecture_registers(ws) == ["RCC_CR", "RCC_CFGR1"]
    res = generate(ws)
    assert res["status"] == "PASS" and res["registers"] == 2
    assert "#define LL_RCC_CR_HSION_MSK 0x00000008U" in (ws / "software/ll/stm32n6xx_ll_rcc.h").read_text()
    assert (ws / LY.LL_TU).read_text() == LY.LL_TU_TEXT


def test_capa050_underscore_joined_name_is_not_guessed(tmp_path):
    ws = _ll(ws_with_inputs(tmp_path), "## Register table\n| Name | Offset |\n|---|---|\n| RCC_CR_HSION | 0x0 |\n")
    assert architecture_registers(ws) == ["RCC_CR_HSION"]
    res = generate(ws)
    assert res["status"] == "BLOCKED" and res["issues"] == ["NO_REGISTERS_FROM_SWE2_TABLE", "NOT_IN_RM:RCC_CR_HSION"]
    assert (ws / LY.LL_TU).read_text() == LY.LL_TU_TEXT  # the compile unit exists even when the map is BLOCKED
