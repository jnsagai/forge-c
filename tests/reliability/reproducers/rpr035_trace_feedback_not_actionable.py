"""RPR-035 (r115): SWE.3 trace rejections were not actionable - PlantUML's bare 'No diagram found' for every design
and CODE:SPEC_NOT_IMPLEMENTED:<id> without the unit/functions to tag; the author spent the rework budget."""
import json
import sys
import tempfile
from pathlib import Path

SIG = "SWE.3 trace feedback not actionable"


def main() -> int:
    from forge_factory.inspection import swtrace

    with tempfile.TemporaryDirectory() as td:
        ws = Path(td) / "WO" / "workspace"
        files = {".forge-run/manifest.json": json.dumps({"layer": "LL"}),
                 "workproducts/SWE.3/unit_specifications.md": "## SWU-LL-01: HSI\n- SWC: SWC_LL\n- Functions: LL_RCC_HSI_Enable\n"
                 "- **USPEC-LL-01-01** Set HSION. Traces: SWR-001\n- **USPEC-LL-01-02** Keep other bits. Traces: SWR-001\n",
                 "software/ll/stm32n6xx_ll_rcc.h": "/**\n * @brief e\n * @unit SWU-LL-01\n * @spec USPEC-LL-01-01\n */\n"
                 "static inline void LL_RCC_HSI_Enable(void)\n{\n}\n"}
        for rel, t in files.items():
            (ws / rel).parent.mkdir(parents=True, exist_ok=True)
            (ws / rel).write_text(t)
        f = swtrace.check_code(ws, doxygen=False)["major_findings"]
        ok1 = any(x.startswith("CODE:SPEC_NOT_IMPLEMENTED:USPEC-LL-01-02 (") and "LL_RCC_HSI_Enable" in x for x in f)
        p = Path(td) / "bad.puml"
        p.write_text("@startuml\nstart\nif (x\n@enduml\n")
        ok2 = True
        if swtrace._plantuml_jar() is not None:
            ok2 = "syntax:" in swtrace.render_ok(p)[1]
    if ok1 and ok2:
        print("SYMPTOM_ABSENT")
        return 0
    print(f"SYMPTOM_PRESENT:{SIG}")
    return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"REPRODUCER_ERROR:{type(exc).__name__}:{str(exc)[:160]}")
        sys.exit(2)
