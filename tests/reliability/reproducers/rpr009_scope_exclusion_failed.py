"""RPR-009 (r80): SWE.5 inspection failed SWE5-03 ("no interrupt interaction tested") although the work order lists
interrupts as out of scope: neither the SWE.5 report procedure nor the inspector procedure carried the scope."""
import sys

SIG = "verification inspectors judge excluded work-order scope as missing tests"


def main() -> int:
    from forge_factory.workflow import prompts
    from forge_factory.workflow.builder import build

    build("RPR-009", layer="LL", chunk_lines=150)
    ok = "Scope exclusions" in prompts.author_prompt("SWE.5") and all(
        "Out of scope" in prompts.inspector_prompt(p) for p in ("SWE.4", "SWE.5", "SWE.6"))
    if not ok:
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
