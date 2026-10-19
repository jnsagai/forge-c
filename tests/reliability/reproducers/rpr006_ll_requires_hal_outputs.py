"""RPR-006 (r80): the SWE.3 presence gate required software/hal/*.c|h in an LL-only work order (ADR-0009), so a
complete LL phase could not be frozen (MISSING_REQUIRED_OUTPUT) and burned a rework cycle."""
import json
import sys
import tempfile
from pathlib import Path

SIG = "SWE.3 presence gate requires HAL files in an LL work order"


def main() -> int:
    from forge_factory.inspection.engine import Store

    ws = Path(tempfile.mkdtemp(prefix="rpr006-"))
    (ws / ".forge-run").mkdir(parents=True)
    (ws / ".forge-run/manifest.json").write_text(json.dumps({"layer": "LL", "provided": []}))
    for rel, txt in {"workproducts/SWE.3/detailed_design.md": "# Detailed design\n",
                     "software/ll/stm32n6xx_ll_rcc.h": "#ifndef X\n#define X\n#endif /* X */\n",
                     "software/src/stm32n6xx_ll_rcc.c": "#include \"stm32n6xx_ll_rcc.h\"\n"}.items():
        (ws / rel).parent.mkdir(parents=True, exist_ok=True)
        (ws / rel).write_text(txt)
    missing = Store(ws).missing_outputs("SWE.3")
    if any("software/hal/" in m for m in missing):
        print(f"SYMPTOM_PRESENT:{SIG}")
        return 1
    print("SYMPTOM_ABSENT")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001 - API drift is reported, never counted as a reproduction
        print(f"REPRODUCER_ERROR:{type(exc).__name__}:{str(exc)[:160]}")
        sys.exit(2)
