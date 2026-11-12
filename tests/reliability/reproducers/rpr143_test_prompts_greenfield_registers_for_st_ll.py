"""RPR-143 (local run WO-F014-SWE5-CRCHAL-20261103-L31B, CRC HAL on the ST CRC LL, Omniverse2, 2026-11-04): the SWE.5
target test of the HAL did not build - 'll_crc_regs' undeclared, 'LL_CRC_DR_OFFSET' undeclared - because the native
HAL prompts tell the author to check "ll_crc_regs[LL_CRC_<REG>_OFFSET / 4U] bits" and never to define ll_crc_regs
"(the linker places it)": the greenfield register-block array of the peripheral profile. A HAL on a PROVIDED ST (CMSIS)
LL has no such array and no <REG>_OFFSET defines; its registers are the CMSIS instance's (CRC->DR), reached through
the provided LL functions (LL_CRC_ReadData32(CRC)). CAPA-131 fixed the LL calls of these prompts (providedize) but
left the register-access wording of the SWE.5 target, SWE.6 scenario, and SWE.2/SWE.3 register notes untouched.

Scenario (synthetic, writes only to a scratch dir): the real workflow builder builds the HAL graph of a work order whose
provided LL header is ST style (CRC_TypeDef *CRCx first), with the instance API derived by the real
brownfield.cmsis.provided_api. Symptom: a HAL prompt of that graph names the register-block array or a <REG>_OFFSET
define. Control: the HAL graph of a greenfield work order (no provided API) keeps the register-block wording and is
byte-identical to the baseline's (frozen sha256 with the host's checkout, data root and interpreter masked); a loosened
or changed control is an error, not ABSENT."""
import hashlib
import json
import re
import sys
import tempfile
from pathlib import Path

SIG = "a HAL prompt for a provided ST LL names the greenfield register-block array or a <REG>_OFFSET define"
GREEN_SHA = "c39528d3ce72965d96c70928d980575bf332d1d71eba3e5e274cfe0848150c5a"
ST_HDR = ('#include "stm32n6xx.h"\n'
          "__STATIC_INLINE void LL_CRC_ResetCRCCalculationUnit(CRC_TypeDef *CRCx)\n{\n  SET_BIT(CRCx->CR, CRC_CR_RESET);\n}\n"
          "__STATIC_INLINE void LL_CRC_FeedData32(CRC_TypeDef *CRCx, uint32_t InData)\n{\n  WRITE_REG(CRCx->DR, InData);\n}\n"
          "__STATIC_INLINE uint32_t LL_CRC_ReadData32(const CRC_TypeDef *CRCx)\n{\n"
          "  return (uint32_t)(READ_REG(CRCx->DR));\n}\n")
GREENFIELD = re.compile(r"ll_crc_regs|LL_CRC_<REG>_OFFSET|LL_CRC_REG_COUNT")


def prompts_of(dot: str) -> dict[str, str]:
    return dict(re.findall(r'\n  (\w+) \[[^\n]*?prompt="((?:[^"\\]|\\.)*)"', dot))


def graph(api) -> str:
    from forge_factory.workflow import builder

    dot, _ = builder.build("WO-RPR143", chunk_lines=150, layer="HAL", trace=True, isolation=True, peripheral="crc",
                           uspec_gtest=True, **({"provided_api": api} if api else {}))
    return dot.replace(builder._env(), "<ENV>").replace(sys.executable, "<PY>")


def main() -> int:
    from forge_factory.brownfield.cmsis import provided_api

    with tempfile.TemporaryDirectory() as td:
        ws = Path(td) / "ws"
        (ws / ".forge-run").mkdir(parents=True)
        (ws / "software/ll").mkdir(parents=True)
        (ws / ".forge-run/manifest.json").write_text(json.dumps({"layer": "HAL", "peripheral": "crc"}))
        (ws / "software/ll/stm32n6xx_ll_crc.h").write_text(ST_HDR)
        api = provided_api(ws)
    if not api or api.get("instance") != "CRC":
        print(f"REPRODUCER_ERROR:SCENARIO_NOT_REACHED:provided_api {api}")
        return 2
    green = graph(None)
    gp = prompts_of(green)
    if "ll_crc_regs[LL_CRC_<REG>_OFFSET / 4U] bits" not in gp.get("swe5_target_author", ""):
        print("REPRODUCER_ERROR:CONTROL_CHANGED:greenfield swe5_target_author lost its register-block wording")
        return 2
    sha = hashlib.sha256(green.encode()).hexdigest()
    if sha != GREEN_SHA:
        print(f"REPRODUCER_ERROR:CONTROL_CHANGED:greenfield HAL graph sha256 {sha}")
        return 2
    st = prompts_of(graph(api))
    if "swe5_target_author" not in st or "swe6_test_author" not in st:
        print("REPRODUCER_ERROR:SCENARIO_NOT_REACHED:no SWE.5 target / SWE.6 test author node")
        return 2
    hits = sorted({f"{n}:{m.group(0)}" for n, t in st.items() for m in GREENFIELD.finditer(t)})
    if hits:
        print("observed: " + "; ".join(hits[:8]))
        print(f"SYMPTOM_PRESENT:{SIG}")
        return 1
    print("SYMPTOM_ABSENT")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"REPRODUCER_ERROR:{type(exc).__name__}:{str(exc)[:160]}")
        sys.exit(2)
