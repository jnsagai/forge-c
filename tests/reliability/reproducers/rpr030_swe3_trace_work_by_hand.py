"""RPR-030 (r110): with the owner trace profile the SWE.3 design author had to write unit specifications, one PlantUML
design per unit and the MISRA statement by hand and exhausted its tool budget (46 > 45) in the third cycle."""
import sys

SIG = "trace-profile SWE.3 chain has no deterministic unit scaffold"


def main() -> int:
    from forge_factory.workflow import prompts
    from forge_factory.workflow.builder import build

    dot, _ = build("RPR-030", layer="LL", chunk_lines=150, trace=True)
    if "swe3_units" not in dot or "GENERATED" not in prompts.author_prompt("SWE.3"):
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
