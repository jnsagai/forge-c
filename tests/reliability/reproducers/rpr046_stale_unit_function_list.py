"""RPR-046 (r129): after a code change in SWE.3 rework, a unit's 'Functions:' list still named a function the code no
longer had, so the trace gate rejected CODE:UNIT_FUNCTION_NOT_IN_CODE and a rework cycle went to bookkeeping."""
import json
import sys
import tempfile
from pathlib import Path

SIG = "unit function list not synchronised with the code"
UNITS = ("## SWU-HAL-01: HSE\n- SWC: SWC_HAL\n- Functions: HAL_RCC_HSE_Enable, HAL_RCC_Gone\n"
         "- **USPEC-HAL-01-01** Enable HSE. Traces: SWR-001\n")
CODE = ("/**\n * @brief Enable HSE.\n * @unit SWU-HAL-01\n * @spec USPEC-HAL-01-01\n */\n"
        "int HAL_RCC_HSE_Enable(void)\n{\n    return 0;\n}\n")


def main() -> int:
    from forge_factory.inspection import swtrace

    with tempfile.TemporaryDirectory() as td:
        ws = Path(td) / "WO" / "workspace"
        for rel, text in {".forge-run/manifest.json": json.dumps({"layer": "HAL"}),
                          "workproducts/SWE.3/unit_specifications.md": UNITS,
                          "software/hal/stm32n6xx_hal_rcc.c": CODE}.items():
            (ws / rel).parent.mkdir(parents=True, exist_ok=True)
            (ws / rel).write_text(text)
        try:
            from forge_factory.inspection.unit_scaffold import sync_trace

            sync_trace(ws)
        except ImportError:
            pass  # baseline: no synchronisation step
        f = swtrace.check_code(ws, doxygen=False)["major_findings"]
    if any(x.startswith("CODE:UNIT_FUNCTION_NOT_IN_CODE:SWU-HAL-01:HAL_RCC_Gone") for x in f):
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
