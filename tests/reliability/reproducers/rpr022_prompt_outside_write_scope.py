"""RPR-022 (r84 DEF-002): an author procedure told the role to write a file outside its authorized write scope (SWE.4
-> traceability/requirements_to_tests.csv); the write was denied and escalated as a FACTORY defect."""
import re
import sys

SIG = "author procedure writes outside the role write scope"


def main() -> int:
    from forge_factory.policy.authz import ROLE_WRITE_PREFIXES
    from forge_factory.workflow import prompts
    from forge_factory.workflow.builder import build

    for layer in ("LL", "HAL", "LL+HAL"):
        build("RPR-022", layer=layer, chunk_lines=150)
        for n in range(1, 7):
            role = f"swe{n}-author"
            for path in re.findall(r"write_file ([\w./-]+)", prompts.author_prompt(f"SWE.{n}")):
                if not any(path.startswith(p) for p in ROLE_WRITE_PREFIXES[role]):
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
