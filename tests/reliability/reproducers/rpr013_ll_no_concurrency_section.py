"""RPR-013 (r82): the LL SWE.2 procedure did not ask for a concurrency/reentrancy section although LL writes are
non-atomic read-modify-writes of shared RCC registers; SWE2-03 failed on a one-line note."""
import sys

SIG = "LL SWE.2 procedure omits concurrency and reentrancy"


def main() -> int:
    from forge_factory.workflow import prompts
    from forge_factory.workflow.builder import build

    build("RPR-013", layer="LL", chunk_lines=150)
    if "Concurrency and reentrancy" not in prompts.author_prompt("SWE.2"):
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
