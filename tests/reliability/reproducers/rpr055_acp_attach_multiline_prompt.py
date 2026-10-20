"""RPR-055 (i003): acp.attach matched node statements line by line; author nodes whose prompt holds real line breaks
(swe4_test_author, swe3_hal_author) stayed on the Fabro run model (DeepSeek) in runs that put every author on Codex."""
import sys
from pathlib import Path

SIG = "author node with a multi-line prompt left on the run model"


def main() -> int:
    from forge_factory import acp
    from forge_factory.workflow.builder import build

    left = []
    for layer in ("LL", "LL+HAL"):
        graph, nodes = build("WO-RPR055", layer=layer)
        g, done = acp.attach(graph, nodes, Path("/ws"))
        left += [n for n in ("swe4_test_author", "swe3_hal_author") if n in nodes and n not in done]
    if left:
        print(f"native author nodes: {', '.join(sorted(set(left)))}")
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
