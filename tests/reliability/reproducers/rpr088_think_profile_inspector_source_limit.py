"""RPR-088 (Fabro SWE.1 run WO-F014-SWE1-RCC-20261101-03, 01M6AX62VKEJ0RY4S57NED425T, Omniverse2, 2026-11-01): the RCC LL
SWE.1 baseline (61 register groups) froze, then the inspector refused it before any model call:
SOURCE_TOO_LARGE:workproducts/SWE.1/register_effects.json:107046>40000. The Ornith thinking profile kept the inherited
40 000-character per-source loading bound; the other Omniverse2 profiles set inspection_max_source_chars 1048576.

Scenario: a workspace bound to the Ornith thinking profile whose frozen register_effects.json has the RCC-03 size.
Symptom: the inspector's per-source loading bound refuses that file."""
import json
import sys
import tempfile
from pathlib import Path

SIG = "the thinking profile's inspector refuses a frozen RCC-size register_effects.json as too large"


def main() -> int:
    from forge_factory.lrtx import review
    from forge_factory.lrtx import structured as S
    with tempfile.TemporaryDirectory() as td:
        ws = Path(td)
        (ws / ".forge-run").mkdir()
        (ws / ".forge-run/manifest.json").write_text(json.dumps(
            {"local_profile": {"id": "local-rtx-v2-omniverse2-ornith-think-author-q38-inspector"}}))
        rel = "workproducts/SWE.1/register_effects.json"
        (ws / rel).parent.mkdir(parents=True)
        (ws / rel).write_text(json.dumps({"schema": "forge-c/register-effects/1", "effects": []}) + " " * 107046)
        limit = review.source_char_limit(ws)
        try:
            S.source(ws, rel, max_chars=limit)
        except S.PacketRefused as exc:
            if "SOURCE_TOO_LARGE" not in str(exc):
                print(f"REPRODUCER_ERROR:SCENARIO_NOT_REACHED:{str(exc)[:120]}")
                return 2
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
