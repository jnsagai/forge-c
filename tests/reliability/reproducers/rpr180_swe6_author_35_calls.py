"""RPR-180 (owner lane, Omniverse2, 2026-11-07, L90X on V17): the SWE.6 author spent about 30 of its 35 tool calls on
glob/read before writing, hit TURN_BUDGET_EXHAUSTED and the attempt ended 0/24. The 35-call author budget dates from
2026-10-15 (qwen3:8b). Owner 2026-11-07: raise every limit that can stop autonomous operation.

Scenario: the registry budget of the SWE.6 author for a plain workspace.
Symptom: the per-visit author budget is 35 calls or fewer."""
import json
import sys
import tempfile
from pathlib import Path

SIG = "the SWE.6 author's per-visit tool budget is still the 35-call limit L90X exhausted"


def main() -> int:
    from forge_factory.policy import governor as G
    with tempfile.TemporaryDirectory() as td:
        ws = Path(td)
        (ws / ".forge-run").mkdir()
        (ws / ".forge-run/manifest.json").write_text(json.dumps({}))
        limit = G.turn_limit("swe6-author", str(ws))
    if limit <= 35:
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
