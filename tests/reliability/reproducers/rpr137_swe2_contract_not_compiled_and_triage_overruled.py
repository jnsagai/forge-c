"""RPR-137 (local run WO-F014-SWE3-CRCHAL-20261103-L31B, Omniverse2, CRC HAL order 0014m on run/gen13 f02766d9,
2026-11-03): SWE.3 was BLOCKED "STUCK: identical deterministic rejection twice (CONTRACT_CALL_DOES_NOT_COMPILE:
workproducts/SWE.2/api_calls.json:'crc' undeclared)": the SWE.2 call contract passed `&crc` as the result pointer of
HAL_CRC_Calculate/Accumulate and nothing declares `crc`. Two factory gaps let it through:
 (a) SWE.2 compiled its call contract only in instance mode or for a brownfield delivery; a greenfield HAL (also one on
     a provided ST LL, CAPA-128) gets its interface header only at SWE.3, so SWE.2 checked nothing and PASSED (L27, L31);
 (b) the SWE.3 author reported DEF-001 (ARCHITECTURE -> SWE.2), the SWE.2 author REJECTED it ("a SWE.3 harness fix"),
     and inspection/gate.step_triage returned to SWE.3 because the SWE.2 baseline was intact - without re-running the
     SWE.2 deterministic checks on the file the defect cites.

Scenario (synthetic, writes only to a scratch dir; tracked IWDG RM inputs): the real workorder.prepare of a HAL work order
with --provided-from a synthetic FROZEN CMSIS LL work order (as RPR-135), at its SWE.2 state (no HAL header yet): an SWE.2
interface declaring `uint32_t HAL_IWDG_Read(uint32_t *p_value);`, a one-case call contract READ(HAL_IWDG_Read, <arg>).
(a) lrtx.swe2.self_check (the deterministic SWE.2 checks) on arg `&value`; (b) a REJECTED ARCHITECTURE defect citing the
contract, the latest upstream loop, an intact SWE.2 baseline (stubbed), then gate.step_triage(SWE.2).
Symptom: (a) no CONTRACT_CALL_DOES_NOT_COMPILE finding names `value`, or (b) the triage RETURNs although the cited
contract still does not compile. Controls: the self-contained arg `&(uint32_t){0U}` gets no such finding and its
rejected defect still RETURNs (an altered control is an error, not ABSENT)."""
import json
import os
import sys
import tempfile
from pathlib import Path

SIG = "an SWE.2 call contract with an undeclared argument passes SWE.2 and the SWE.2 triage returns its rejected defect"
ST_IWDG = ("#ifndef STM32N6xx_LL_IWDG_H\n#define STM32N6xx_LL_IWDG_H\n#include \"stm32n6xx.h\"\n"
           "#define LL_IWDG_KEY_ENABLE 0x0000CCCCU\n"
           "__STATIC_INLINE void LL_IWDG_Enable(IWDG_TypeDef *IWDGx)\n{\n  WRITE_REG(IWDGx->KR, LL_IWDG_KEY_ENABLE);\n}\n#endif\n")
IWDG_DEV = ("#ifndef STM32N6XX_H\n#define STM32N6XX_H\n#include \"core_cm55.h\"\n"
            "typedef struct { __IO uint32_t KR; __IO uint32_t PR; __IO uint32_t RLR; __IO uint32_t SR; } IWDG_TypeDef;\n"
            "#define IWDG ((IWDG_TypeDef *)0x56004800UL)\n#define WRITE_REG(REG, VAL) ((REG) = (VAL))\n#endif\n")
ARM_CORE = "#ifndef __arm__\n#error \"CMSIS core header: Arm only\"\n#endif\n"
ARCH = ("# Software architecture\n\n## Interface\n\n### `HAL_IWDG_Read(uint32_t *p_value)`\n\n```c\n"
        "uint32_t HAL_IWDG_Read(uint32_t *p_value);\n```\n\nStores the watchdog counter to the location `p_value`.\n")


def scenario(d: Path, name: str, arg: str) -> tuple[list[str], int]:
    from forge_factory import workorder as WO
    from forge_factory.assurance import register_contract as RC
    from forge_factory.common import REPO_ROOT, sha256_bytes
    from forge_factory.inspection import defects, engine
    from forge_factory.inspection import gate as G
    from forge_factory.lrtx import swe2

    spec = json.loads((REPO_ROOT / "examples/0009b-iwdg-hal/workorder.json").read_text())
    rm = REPO_ROOT / "examples/0009-iwdg-st/inputs"
    spec["inputs"] = [{"path": str(rm / "RM0486-rev4-ch59-iwdg.md"), "role": "reference_manual_iwdg_chapter"},
                      {"path": str(rm / "RM0486-rev4-memory-map-excerpt-iwdg.md"), "role": "reference_manual_memory_map"}]
    spec.pop("simulation_performance", None)
    ex = d / f"ex-{name}"
    ex.mkdir()
    (ex / "workorder.json").write_text(json.dumps(spec))
    src_wo = f"WO-RPR137-LL-{name}"
    src = Path(os.environ["FORGE_STATE_DIR"]) / "workorders" / src_wo / "workspace"
    files = {"software/ll/stm32n6xx_ll_iwdg.h": ST_IWDG, "inputs/vendor/include/stm32n6xx.h": IWDG_DEV,
             "inputs/vendor/include/core_cm55.h": ARM_CORE}
    for rel, text in files.items():
        (src / rel).parent.mkdir(parents=True, exist_ok=True)
        (src / rel).write_text(text)
    (src / ".forge-run").mkdir()
    man = {"work_order": src_wo, "layer": "LL", "peripheral": "iwdg", "code_mode": "FROZEN",
           "delivery": {"code_mode": "FROZEN", "build": {"style": "cmsis", "defines": ["STM32N657xx"], "secure": True}},
           "delivered": [{"path": p, "sha256": sha256_bytes(t.encode()), "bytes": len(t.encode()), "licence": "X",
                          "role": "delivered_code" if p.startswith("software/") else "delivered_dependency"}
                         for p, t in files.items()]}
    (src / ".forge-run/manifest.json").write_text(json.dumps(man))
    ws, _ = WO.prepare(ex, f"WO-RPR137-HAL-{name}", src_wo)
    contract = {RC.EFFECTS: {"schema": "forge-c/register-effects/1",
                             "effects": [{"case": "READ", "swr": "SWR-001", "op": "no_write"}]},
                RC.CALLS: {"schema": "forge-c/api-calls/1", "calls": {"READ": {"function": "HAL_IWDG_Read",
                                                                                "args": [arg]}}}}
    for rel, data in contract.items():
        (ws / rel).parent.mkdir(parents=True, exist_ok=True)
        (ws / rel).write_text(json.dumps(data))
    (ws / "workproducts/SWE.2/software_architecture.md").write_text(ARCH)
    if not RC.cases(ws)[0] or (ws / "software/hal/stm32n6xx_hal_iwdg.h").exists():
        raise RuntimeError(f"SCENARIO_NOT_REACHED:{name}:no contract case or an SWE.3 header at SWE.2")
    try:
        found = [f for f in swe2.self_check(ws) if f.startswith("CONTRACT_CALL_DOES_NOT_COMPILE")]
    except Exception as exc:  # noqa: BLE001 - a self-check that cannot run on the scenario is not the symptom
        raise RuntimeError(f"SCENARIO_NOT_REACHED:{name}:self_check {type(exc).__name__}:{str(exc)[:80]}") from exc
    rec = {"schema": "forge-c/defect/0.5", "id": "DEF-001", "kind": "ARCHITECTURE", "detected_phase": "SWE.3",
           "target_phase": "SWE.2", "reported_by": "swe3-author", "status": "REJECTED", "requirement_ids": ["SWR-001"],
           "summary": f"api_calls.json passes {arg} to HAL_IWDG_Read; the call does not compile",
           "evidence_refs": [RC.CALLS], "test_files": {},
           "history": [{"status": "OPEN"}, {"status": "IN_FIX", "loop": 1},
                       {"status": "REJECTED", "by": "swe2-author", "reason": "the SWE.3 harness must declare it"}]}
    defects._dir(ws).mkdir(parents=True, exist_ok=True)
    (defects._dir(ws) / "DEF-001.json").write_text(json.dumps(rec))
    (ws / defects.LOOPS).parent.mkdir(parents=True, exist_ok=True)
    (ws / defects.LOOPS).write_text(json.dumps({"ts": "2026-11-03T19:54:27Z", "target": "SWE.2",
                                                "defects": ["DEF-001"]}) + "\n")
    rc = G.step_triage(engine.Store(ws), "SWE.2")
    return found, rc


def main() -> int:
    from forge_factory.inspection import engine

    engine.Store.gate = lambda self, ph: {"decision": "PASS"}  # the synthetic source LL is verified (all six gates)
    engine.Store.latest_baseline = lambda self, ph: {"baseline_id": "BL-SWE.2-001", "frozen_at": "2026-11-03T19:00:00Z"}
    engine.Store.stale_reason = lambda self, ph, bl: None  # the SWE.2 baseline is intact (as in L31B)
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        os.environ["FORGE_STATE_DIR"], os.environ["FORGE_EVENTS_DIR"] = str(d / "state"), str(d / "state/events")
        good, good_rc = scenario(d, "good", "&(uint32_t){0U}")
        bad, bad_rc = scenario(d, "bad", "&value")
    if good:
        print(f"REPRODUCER_ERROR:CONTROL_CHANGED:a self-contained contract arg is reported {good[:2]}")
        return 2
    if good_rc != 1:
        print("REPRODUCER_ERROR:CONTROL_CHANGED:a rejected defect whose contract compiles no longer RETURNs")
        return 2
    missed = not any("'value'" in f for f in bad)
    if missed or bad_rc == 1:
        print(f"observed: SWE.2 contract findings {bad[:2] or 'none'}; triage {'RETURN' if bad_rc == 1 else 'FIX'}")
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
