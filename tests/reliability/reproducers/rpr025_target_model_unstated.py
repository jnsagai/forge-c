"""RPR-025 (r86): the target-test and Robot procedures described the RCC model only as 'ready flags follow enable
bits'; authors treated RCC_SR as writable storage, their checks failed and they blamed correct code (DEF-003/004)."""
import sys

SIG = "target procedures do not state the RCC model semantics"


def main() -> int:
    from forge_factory.workflow import prompts
    from forge_factory.workflow.builder import build

    build("RPR-025", layer="LL", chunk_lines=150)
    texts = (prompts.target_test_author_prompt(), prompts.robot_test_author_prompt())
    if not all("read-only" in t and "0x00000F1F" in t for t in texts):
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
