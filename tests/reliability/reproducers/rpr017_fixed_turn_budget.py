"""RPR-017 (r81): the SWE.3 author turn budget was fixed at the authored 35 calls regardless of the allocated work;
a 16-function LL needed 36 and lost a rework cycle (TURN_BUDGET_EXHAUSTED)."""
import sys
import tempfile
from pathlib import Path

SIG = "author turn budget ignores the allocated work"


def main() -> int:
    from forge_factory.policy import governor as GV

    ws = Path(tempfile.mkdtemp(prefix="rpr017-"))
    (ws / "workproducts/SWE.2").mkdir(parents=True)
    (ws / "workproducts/SWE.2/software_architecture.md").write_text(
        "# A\n## Requirement allocation\n| SWR | Function |\n|---|---|\n" +
        "".join(f"| SWR-{i:03d} | HAL_RCC_F{i}_Enable |\n" for i in range(1, 31)))
    base = next(a.max_turns for a in GV.load_agents()[0] if a.id == "swe3-author")
    limit = GV.turn_limit("swe3-author", str(ws)) if hasattr(GV, "turn_limit") else base
    if limit <= base:
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
