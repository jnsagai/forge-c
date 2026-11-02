"""RPR-118 (Fabro run WO-F014-CMP-SWE3-IWDG-20261102-08, cloud comparison line, loop10, 2026-11-02): IWDG LL 0009h,
structured SWE.3. The deterministic unit scaffold (workflow node swe3_units, before every SWE.3 author round) wrote each
as-built unit design workproducts/SWE.3/detailed_design/<unit>.puml only when it was missing. After the code rework of
rounds 2 and 3 the frozen baselines BL-SWE.3-002/-003 carried the round-1 diagrams (SWU-LL-01 still showed
'(uint32_t)LL_IWDG_KR_KEY_MSK', SWU-LL-07 an 'if' the code no longer had) and SWE3-06 failed on the stale diagrams.

Scenario: the real inspection.unit_scaffold.scaffold on a scratch LL workspace, run once, the code reworked, run
again (as the workflow does before each author round). Symptom: the design no longer matches the reworked code."""
import json
import sys
import tempfile
from pathlib import Path

SIG = "the as-built SWE.3 unit design is not re-rendered from the reworked code and stays stale"
HEADER = "software/ll/stm32n6xx_ll_iwdg.h"
DOC = "/**\n * @brief Start the IWDG.\n * @unit SWU-LL-01\n * @spec USPEC-LL-01-01\n */\n"
V1 = "ll_iwdg_regs[LL_IWDG_KR_OFFSET / 4U] = ((uint32_t)0x0000CCCCU & (uint32_t)LL_IWDG_KR_KEY_MSK);"
V2 = "ll_iwdg_regs[LL_IWDG_KR_OFFSET / 4U] = (((uint32_t)0x0000CCCCU << LL_IWDG_KR_KEY_POS) & LL_IWDG_KR_KEY_MSK);"


def _code(stmt: str) -> str:
    return ("#ifndef LL_H\n#define LL_H\n" + DOC + "static inline void LL_IWDG_Enable(void)\n{\n    " + stmt +
            "\n}\n#endif\n")


def main() -> int:
    from forge_factory.inspection import unit_scaffold as US

    with tempfile.TemporaryDirectory() as td:
        ws = Path(td)
        (ws / ".forge-run").mkdir()
        (ws / ".forge-run/manifest.json").write_text(json.dumps({"layer": "LL"}))
        (ws / HEADER).parent.mkdir(parents=True)
        design = ws / "workproducts/SWE.3/detailed_design/SWU-LL-01.puml"
        try:
            (ws / HEADER).write_text(_code(V1))
            US.scaffold(ws)
            first = design.read_text()
            (ws / HEADER).write_text(_code(V2))  # SWE.3 rework: the code task changed the unit
            US.scaffold(ws)
            second = design.read_text()
        except Exception as exc:  # noqa: BLE001
            print(f"REPRODUCER_ERROR:SCENARIO_NOT_REACHED:{type(exc).__name__}:{str(exc)[:120]}")
            return 2
    if V1.rstrip(";") not in first:
        print("REPRODUCER_ERROR:SCENARIO_NOT_REACHED:the first round did not render the code")
        return 2
    if V2.rstrip(";") not in second or V1.rstrip(";") in second:
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
