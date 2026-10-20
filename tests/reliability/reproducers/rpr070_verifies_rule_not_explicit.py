"""RPR-070 (h004, h005, rc1): every IWDG HAL v2 SWE.4 author first put SWR/SWU ids into '@verifies' (rule text: '@verifies
USPEC-...-..' without saying other ids are invalid); each time UT:UNKNOWN_SPEC_REF cost one of the three rework cycles
(rc1 then BLOCKED). The prompt and the finding did not state the rule."""
import sys

SIG = "the unit-test trace rule does not exclude SWR/SWU ids from @verifies"


def main() -> int:
    from forge_factory.workflow import prompts as P

    old = P.TRACE["on"]
    try:
        P.TRACE["on"] = True
        rule = " ".join(P.trace_step("ut"))
    finally:
        P.TRACE["on"] = old
    if "ONLY USPEC ids" not in rule:
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
