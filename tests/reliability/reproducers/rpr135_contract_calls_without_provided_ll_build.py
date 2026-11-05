"""RPR-135 (local run WO-F014-SWE3-CRCHAL-20261103-L31, Omniverse2, CRC HAL order 0014m on run/gen12 347e9381,
2026-11-03): SWE.3 of a HAL work order on an ST-delivered (CMSIS) LL was BLOCKED "STUCK: identical deterministic
rejection twice (CONTRACT_CALL_DOES_NOT_COMPILE:workproducts/SWE.2/api_calls.json:stm32n6xx.h: No such file or
directory)". assurance/register_contract.check_compiles compiles the SWE.2 call contract against the HAL header with
plain gcc and the HAL/LL include dirs only: its branches cover instance mode and brownfield deliveries, but not a HAL
with a CAPA-128 `provided_build`, so the provided ST LL header's #include "stm32n6xx.h" has no host device directory,
forced host mapping or defines - the contract can never compile, whatever the author does.

Scenario (synthetic, ST style, writes only to a scratch dir; tracked IWDG RM inputs): the real workorder.prepare of a
HAL work order with --provided-from a synthetic FROZEN CMSIS LL work order (ST-style IWDG LL including stm32n6xx.h, a
vendor device header, an Arm-only core header; all six gates PASS), a HAL header/source calling LL_IWDG_Enable(IWDG), a
one-case call contract (HAL_IWDG_Start()), then check_compiles as the SWE.3 gate calls it (software/hal + software/ll).
Symptom: the valid contract is reported CONTRACT_CALL_DOES_NOT_COMPILE. Controls: the same HAL with a greenfield
provided LL (no provided_build) compiles; a contract calling an undeclared function is still reported (an altered
control is an error, not ABSENT)."""
import json
import os
import sys
import tempfile
from pathlib import Path

SIG = "the SWE.2 call contract of a HAL on an ST (CMSIS) LL cannot compile: no provided LL build inputs in check_compiles"
ST_IWDG = ("#ifndef STM32N6xx_LL_IWDG_H\n#define STM32N6xx_LL_IWDG_H\n#include \"stm32n6xx.h\"\n"
           "#define LL_IWDG_KEY_ENABLE 0x0000CCCCU\n"
           "__STATIC_INLINE void LL_IWDG_Enable(IWDG_TypeDef *IWDGx)\n{\n  WRITE_REG(IWDGx->KR, LL_IWDG_KEY_ENABLE);\n}\n#endif\n")
GREEN_IWDG = ("#ifndef STM32N6XX_LL_IWDG_H\n#define STM32N6XX_LL_IWDG_H\n#include <stdint.h>\n"
              "extern volatile uint32_t ll_iwdg_regs[64];\n#define IWDG 0\n"
              "static inline void LL_IWDG_Enable(int unused)\n{\n  (void)unused;\n  ll_iwdg_regs[0] = 0x0000CCCCU;\n}\n#endif\n")
IWDG_DEV = ("#ifndef STM32N6XX_H\n#define STM32N6XX_H\n#include \"core_cm55.h\"\n"
            "typedef struct { __IO uint32_t KR; __IO uint32_t PR; __IO uint32_t RLR; __IO uint32_t SR; } IWDG_TypeDef;\n"
            "#define IWDG ((IWDG_TypeDef *)0x56004800UL)\n#define WRITE_REG(REG, VAL) ((REG) = (VAL))\n#endif\n")
ARM_CORE = "#ifndef __arm__\n#error \"CMSIS core header: Arm only\"\n#endif\n"
HAL_H = ("#ifndef STM32N6XX_HAL_IWDG_H\n#define STM32N6XX_HAL_IWDG_H\n#include <stdint.h>\n#include \"stm32n6xx_ll_iwdg.h\"\n"
         "uint32_t HAL_IWDG_Start(void);\n#endif\n")
HAL_C = "#include \"stm32n6xx_hal_iwdg.h\"\nuint32_t HAL_IWDG_Start(void)\n{\n    LL_IWDG_Enable(IWDG);\n    return 0U;\n}\n"


def scenario(d: Path, name: str, cmsis_ll: bool, function: str) -> list[str]:
    from forge_factory import workorder as WO
    from forge_factory.assurance import register_contract as RC
    from forge_factory.common import REPO_ROOT, sha256_bytes

    spec = json.loads((REPO_ROOT / "examples/0009b-iwdg-hal/workorder.json").read_text())
    rm = REPO_ROOT / "examples/0009-iwdg-st/inputs"
    spec["inputs"] = [{"path": str(rm / "RM0486-rev4-ch59-iwdg.md"), "role": "reference_manual_iwdg_chapter"},
                      {"path": str(rm / "RM0486-rev4-memory-map-excerpt-iwdg.md"), "role": "reference_manual_memory_map"}]
    spec.pop("simulation_performance", None)
    ex = d / f"ex-{name}"
    ex.mkdir()
    (ex / "workorder.json").write_text(json.dumps(spec))
    src_wo = f"WO-RPR135-LL-{name}"
    src = Path(os.environ["FORGE_STATE_DIR"]) / "workorders" / src_wo / "workspace"
    files = {"software/ll/stm32n6xx_ll_iwdg.h": ST_IWDG if cmsis_ll else GREEN_IWDG}
    if cmsis_ll:
        files |= {"inputs/vendor/include/stm32n6xx.h": IWDG_DEV, "inputs/vendor/include/core_cm55.h": ARM_CORE}
    for rel, text in files.items():
        (src / rel).parent.mkdir(parents=True, exist_ok=True)
        (src / rel).write_text(text)
    (src / ".forge-run").mkdir()
    man = {"work_order": src_wo, "layer": "LL", "peripheral": "iwdg"}
    if cmsis_ll:
        man |= {"code_mode": "FROZEN", "delivery": {"code_mode": "FROZEN", "build": {
            "style": "cmsis", "defines": ["STM32N657xx"], "secure": True}},
            "delivered": [{"path": p, "sha256": sha256_bytes(t.encode()), "bytes": len(t.encode()), "licence": "X",
                           "role": "delivered_code" if p.startswith("software/") else "delivered_dependency"}
                          for p, t in files.items()]}
    (src / ".forge-run/manifest.json").write_text(json.dumps(man))
    ws, _ = WO.prepare(ex, f"WO-RPR135-HAL-{name}", src_wo)
    (ws / "software/hal").mkdir(parents=True, exist_ok=True)
    (ws / "software/hal/stm32n6xx_hal_iwdg.h").write_text(HAL_H)
    (ws / "software/hal/stm32n6xx_hal_iwdg.c").write_text(HAL_C)
    contract = {RC.EFFECTS: {"schema": "forge-c/register-effects/1",
                             "effects": [{"case": "START", "swr": "SWR-001", "op": "no_write"}]},
                RC.CALLS: {"calls": {"START": {"function": function, "args": []}}}}
    for rel, data in contract.items():
        (ws / rel).parent.mkdir(parents=True, exist_ok=True)
        (ws / rel).write_text(json.dumps(data))
    if not RC.cases(ws)[0]:
        raise RuntimeError(f"SCENARIO_NOT_REACHED:{name}:no contract case")
    return RC.check_compiles(ws, [ws / "software/hal", ws / "software/ll"], "stm32n6xx_hal_iwdg.h")


def main() -> int:
    from forge_factory.inspection import engine

    engine.Store.gate = lambda self, ph: {"decision": "PASS"}  # the synthetic source LL is verified (all six gates)
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        os.environ["FORGE_STATE_DIR"], os.environ["FORGE_EVENTS_DIR"] = str(d / "state"), str(d / "state/events")
        green = scenario(d, "green", False, "HAL_IWDG_Start")
        wrong = scenario(d, "wrong", True, "HAL_IWDG_Nope")
        st = scenario(d, "st", True, "HAL_IWDG_Start")
    if green:
        print(f"REPRODUCER_ERROR:CONTROL_CHANGED:greenfield HAL contract does not compile {green[:2]}")
        return 2
    if not any("HAL_IWDG_Nope" in f or "stm32n6xx.h" in f for f in wrong):
        print(f"REPRODUCER_ERROR:CONTROL_CHANGED:an undeclared contract call is not reported {wrong[:2]}")
        return 2
    if st:
        print("observed: " + "; ".join(st[:3]))
        print(f"SYMPTOM_PRESENT:{SIG}")
        return 1
    if not any("HAL_IWDG_Nope" in f for f in wrong):
        print(f"REPRODUCER_ERROR:CONTROL_CHANGED:the undeclared call is not the reported error {wrong[:2]}")
        return 2
    print("SYMPTOM_ABSENT")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"REPRODUCER_ERROR:{type(exc).__name__}:{str(exc)[:160]}")
        sys.exit(2)
