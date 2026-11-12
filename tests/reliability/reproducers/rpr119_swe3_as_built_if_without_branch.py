"""RPR-119 (Fabro run WO-F014-CMP-SWE3-IWDG-20261102-08, cloud comparison line, loop10, 2026-11-02): IWDG LL 0009h,
structured SWE.3. The as-built unit designs SWU-LL-07/08/09 drew the status-flag 'if' as an ordinary action
(':if (...) (control);') followed by an unconditional ':result = 1U;', with no branch keeping result = 0U, and the
inspector failed SWE3-06 in all three rounds: the diagrams do not represent the conditional return behaviour.

Scenario: the real inspection.unit_scaffold rendering (function bodies parsed from the code, as-built activity) of the
LL_IWDG_IsActiveFlag_PVU body of that run (no file is read or written). Symptom: the 'if' is not a PlantUML branch with
its whole condition, or the conditional assignment is drawn outside it."""
import sys

SIG = "the as-built SWE.3 unit design draws an if statement as a plain action without a branch"
COND = "(sr & LL_IWDG_SR_PVU_MSK) == LL_IWDG_SR_PVU_MSK"
CODE = ("static inline uint32_t LL_IWDG_IsActiveFlag_PVU(void)\n{\n    uint32_t result = 0U;\n"
        "    const uint32_t sr = (uint32_t)ll_iwdg_regs[LL_IWDG_SR_OFFSET / 4U];\n"
        f"    if ({COND})\n    {{\n        result = 1U;\n    }}\n    return result;\n}}\n")


def main() -> int:
    from forge_factory.inspection import unit_scaffold as US

    try:
        puml = US._activity("SWU-LL-07", "", ["LL_IWDG_IsActiveFlag_PVU"], US._bodies(CODE))
    except Exception as exc:  # noqa: BLE001
        print(f"REPRODUCER_ERROR:SCENARIO_NOT_REACHED:{type(exc).__name__}:{str(exc)[:120]}")
        return 2
    lines = [x.strip() for x in puml.splitlines()]
    if "partition LL_IWDG_IsActiveFlag_PVU {" not in lines or not any(COND in x for x in lines):
        print("REPRODUCER_ERROR:SCENARIO_NOT_REACHED:the function or its condition was not rendered")
        return 2
    try:
        start = lines.index(f"if ({COND}) then (yes)")
        end = lines.index("endif", start)
    except ValueError:
        print(f"SYMPTOM_PRESENT:{SIG}")
        return 1
    if ":result = 1U;" in lines[start + 1:end] and ":result = 1U;" not in lines[end:] and \
            lines.index(":uint32_t result = 0U;") < start:
        print("SYMPTOM_ABSENT")
        return 0
    print(f"SYMPTOM_PRESENT:{SIG}")
    return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"REPRODUCER_ERROR:{type(exc).__name__}:{str(exc)[:160]}")
        sys.exit(2)
