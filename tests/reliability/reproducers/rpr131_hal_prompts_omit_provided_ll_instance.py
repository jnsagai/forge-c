"""RPR-131 (CAPA-128 follow-up for WO-F014-SWE3-CRCHAL-20261103-L27, CRC HAL on the ST CRC LL, 2026-11-03): the
native HAL author prompts show the LL API of the greenfield LL - the peripheral profile's HAL example calls
LL_CRC_ResetCRCCalculationUnit(), LL_CRC_FeedData32(p_data[i]), LL_CRC_ReadData32() - while the PROVIDED ST LL takes
the CMSIS instance first (LL_CRC_FeedData32(CRC_TypeDef *CRCx, uint32_t InData)); nothing in the prompt names the
instance, so the SWE.3 author of a HAL on ST's LL is shown calls that do not compile against the provided header.

Scenario (synthetic, ST style; writes only to a scratch dir; tracked IWDG RM inputs): the real workorder.run of a
HAL work order with --provided-from a synthetic LL work order (all gates PASS), stopped where it builds the Fabro
graph (workorder.build is wrapped: the real builder runs, then the run stops before any preflight or launch). The
provided header is either ST style (__STATIC_INLINE, IWDG_TypeDef *IWDGx first) or the greenfield register-array
form. Symptom: the swe3_hal_author prompt of the ST case calls a provided LL function without the instance macro IWDG.
Control: the HAL graph prompts of the greenfield case are byte-identical to the baseline's (frozen sha256, scratch
path masked); a loosened or changed control is an error, not ABSENT."""
import hashlib
import json
import os
import re
import sys
import tempfile
from pathlib import Path

SIG = "the HAL author prompt calls the provided ST LL functions without their CMSIS instance argument"
GREEN_SHA = "52fac4dc96693d3755235e129ed89fa729d375d697dc180f33f0c1024fd2d9d7"
FNS = (("Enable", ""), ("EnableWriteAccess", ""), ("DisableWriteAccess", ""), ("ReloadCounter", ""),
       ("SetPrescaler", "uint32_t Prescaler"), ("SetReloadCounter", "uint32_t Counter"))


def st_header() -> str:
    body = "".join(f"__STATIC_INLINE void LL_IWDG_{n}(IWDG_TypeDef *IWDGx{', ' + a if a else ''})\n{{\n"
                   f"  WRITE_REG(IWDGx->KR, 0U);\n}}\n" for n, a in FNS)
    return ("#ifndef STM32N6xx_LL_IWDG_H\n#define STM32N6xx_LL_IWDG_H\n#include \"stm32n6xx.h\"\n" + body
            + "__STATIC_INLINE uint32_t LL_IWDG_IsActiveFlag_PVU(const IWDG_TypeDef *IWDGx)\n{\n"
            "  return ((READ_BIT(IWDGx->SR, 1U) == 1U) ? 1UL : 0UL);\n}\n#endif\n")


def green_header() -> str:
    body = "".join(f"static inline void LL_IWDG_{n}({a or 'void'})\n{{\n  ll_iwdg_regs[0] = 0U;\n}}\n" for n, a in FNS)
    return ("#ifndef STM32N6XX_LL_IWDG_H\n#define STM32N6XX_LL_IWDG_H\n#include <stdint.h>\n"
            "extern volatile uint32_t ll_iwdg_regs[64];\n" + body + "#endif\n")


class _Stop(Exception):
    pass


def hal_prompts(d: Path, tag: str, header: str) -> dict[str, str]:
    from forge_factory import workorder as WO
    from forge_factory.common import REPO_ROOT
    from forge_factory.inspection import engine

    engine.Store.gate = lambda self, ph: {"decision": "PASS"}
    src = d / f"state/workorders/WO-RPR131-LL-{tag}/workspace"
    (src / "software/ll").mkdir(parents=True)
    (src / ".forge-run").mkdir()
    (src / "software/ll/stm32n6xx_ll_iwdg.h").write_text(header)
    (src / ".forge-run/manifest.json").write_text(json.dumps({"layer": "LL", "peripheral": "iwdg"}))
    spec = json.loads((REPO_ROOT / "examples/0009b-iwdg-hal/workorder.json").read_text())
    rm = REPO_ROOT / "examples/0009-iwdg-st/inputs"
    spec["inputs"] = [{"path": str(rm / "RM0486-rev4-ch59-iwdg.md"), "role": "reference_manual_iwdg_chapter"},
                      {"path": str(rm / "RM0486-rev4-memory-map-excerpt-iwdg.md"), "role": "reference_manual_memory_map"}]
    spec.pop("simulation_performance", None)
    ex = d / f"ex-rpr131-{tag}"
    ex.mkdir()
    (ex / "workorder.json").write_text(json.dumps(spec))
    real, cap = WO.build, {}

    def capture(*a, **k):
        cap["dot"] = real(*a, **k)[0]
        raise _Stop

    WO.build = capture
    try:
        WO.run(ex, f"WO-RPR131-HAL-{tag}", provided_from=f"WO-RPR131-LL-{tag}", model="rpr-model", provider="rpr")
    except _Stop:
        pass
    finally:
        WO.build = real
    if "dot" not in cap:
        raise RuntimeError("the graph was not built")
    dot = cap["dot"].replace(str(d), "<scratch>")
    return dict(re.findall(r'\n  (\w+) \[[^\n]*?prompt="((?:[^"\\]|\\.)*)"', dot))


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        os.environ["FORGE_STATE_DIR"], os.environ["FORGE_EVENTS_DIR"] = str(d / "state"), str(d / "events")
        green = hal_prompts(d, "GF", green_header())
        st = hal_prompts(d, "ST", st_header())
    g = hashlib.sha256(json.dumps(green, sort_keys=True).encode()).hexdigest()
    if g != GREEN_SHA:
        print(f"REPRODUCER_ERROR:CONTROL_CHANGED:greenfield HAL graph prompts sha256 {g}")
        return 2
    p = st.get("swe3_hal_author", "")
    names = [f"LL_IWDG_{n}" for n, _ in FNS] + ["LL_IWDG_IsActiveFlag_PVU"]
    calls = re.findall(r"\b(" + "|".join(names) + r")\(([^()]*)\)", p)
    if not calls:
        print("REPRODUCER_ERROR:SCENARIO_NOT_REACHED:the HAL author prompt shows no provided LL call")
        return 2
    bare = [f"{n}({a})" for n, a in calls if not a.startswith("IWDG")]
    if bare:
        print(f"observed: {sorted(set(bare))[:4]}")
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
