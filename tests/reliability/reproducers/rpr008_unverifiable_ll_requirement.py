"""RPR-008 (r80): the LL SWE.1 procedure demanded a requirement on the number of register accesses, which a host
RAM register array cannot observe; SWE.4 inspection failed it as unverifiable (SWE4-02, DEF-001)."""
import sys

SIG = "LL SWE.1 procedure demands an access-count requirement"


def main() -> int:
    from forge_factory.workflow import prompts
    from forge_factory.workflow.builder import build

    build("RPR-008", layer="LL", chunk_lines=150)
    text = prompts.author_prompt("SWE.1")
    if "at most one read and one write" in text:
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
