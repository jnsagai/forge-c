"""RPR-117 (Fabro run WO-F014-CMP-SWE3-IWDG-20261102-08, cloud comparison line, loop10, 2026-11-02): IWDG LL 0009h,
structured SWE.3. The factory-rendered as-built unit design workproducts/SWE.3/detailed_design/SWU-LL-01.puml cut the
start-key assignment at 110 characters ('... & (uint32_t)LL_IWDG_KR_K'), so the inspector failed SWE3-06 in all three
rounds: the unit diagram does not match the source.

Scenario: the real inspection.unit_scaffold rendering (function bodies parsed from the code, as-built activity) on the
LL_IWDG_Enable statement of that run and on a function longer than the old statement cap (no file is read or written).
Symptom: a rendered activity label ends mid-identifier or a statement of the function is missing from the diagram."""
import sys

SIG = "the factory-rendered SWE.3 unit design cuts a code statement or drops statements of the function"
STMT = ("ll_iwdg_regs[LL_IWDG_KR_OFFSET / 4U] = (((uint32_t)0x0000CCCCU << LL_IWDG_KR_KEY_POS) & "
        "(uint32_t)LL_IWDG_KR_KEY_MSK);")
CODE = ("static inline void LL_IWDG_Enable(void)\n{\n    " + STMT + "\n}\n\n"
        "static inline void LL_IWDG_Many(void)\n{\n" +
        "".join(f"    ll_iwdg_regs[{i}U] = {i}U;\n" for i in range(24)) + "}\n")


def main() -> int:
    from forge_factory.inspection import unit_scaffold as US

    try:
        bodies = US._bodies(CODE)
        puml = US._activity("SWU-LL-01", "", ["LL_IWDG_Enable", "LL_IWDG_Many"], bodies)
    except Exception as exc:  # noqa: BLE001
        print(f"REPRODUCER_ERROR:SCENARIO_NOT_REACHED:{type(exc).__name__}:{str(exc)[:120]}")
        return 2
    if "partition LL_IWDG_Enable" not in puml or "ll_iwdg_regs[LL_IWDG_KR_OFFSET / 4U]" not in puml:
        print("REPRODUCER_ERROR:SCENARIO_NOT_REACHED:the statement was not rendered")
        return 2
    whole = STMT.rstrip(";")
    if whole not in puml or "ll_iwdg_regs[23U] = 23U" not in puml:
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
