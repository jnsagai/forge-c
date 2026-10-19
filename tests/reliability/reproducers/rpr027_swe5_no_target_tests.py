"""RPR-027 (r97): SWE.5 rework re-entered at the SWE.5 author, whose procedure assumed the target tests already
existed; run_renode reported NO_TESTS twice and the phase stopped (STUCK)."""
import sys

SIG = "SWE.5 author procedure cannot recover missing target tests"


def main() -> int:
    from forge_factory.workflow import prompts
    from forge_factory.workflow.builder import build

    build("RPR-027", layer="LL", chunk_lines=150)
    if "NO_TESTS" not in prompts.author_prompt("SWE.5"):
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
