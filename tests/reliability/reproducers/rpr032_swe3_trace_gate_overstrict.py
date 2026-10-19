"""RPR-032 (r111): complete SWE.3 work (specs filled, designs written, functions tagged) was rejected three times
because the designs did not cite USPEC ids and Doxygen (preprocessing off) warned on documented register defines."""
import json
import sys
import tempfile
from pathlib import Path

SIG = "SWE.3 trace gate rejects complete work (citation / Doxygen config)"
REQS = "- **SWR-001** When the HSI enable is requested, the RCC driver shall set RCC_CR.HSION.\n  - Source: RM0486 p.480\n"
ARCH = ('@startuml\ncomponent "RCC_LL\\\\nstm32n6xx_ll_rcc" <<SWC>> as SWC_LL\ncomponent "RCC" as RCC\n'
        "note right of SWC_LL\nAllocated: SWR-001\nend note\nSWC_LL --> RCC : IF-01 regs\n@enduml\n")
UNITS = ("# Units\n## SWU-LL-01: HSI\n- SWC: SWC_LL\n- Functions: LL_RCC_HSI_Enable\n"
         "- Design: workproducts/SWE.3/detailed_design/SWU-LL-01.puml\n"
         "- **USPEC-LL-01-01** Set HSION in RCC_CR. Traces: SWR-001\n")
DESIGN = "@startuml SWU-LL-01\ntitle SWU-LL-01 HSI\nstart\n:LL_RCC_HSI_Enable sets HSION;\nstop\n@enduml\n"
HDR = ("#include <stdint.h>\n/** @brief RCC_CR offset */\n#define LL_RCC_CR_OFFSET 0x000U\n"
       "/** @brief HSION mask */\n#define LL_RCC_CR_HSION_MSK 0x00000008U\n"
       "extern volatile uint32_t ll_rcc_regs[1024];\n/**\n * @brief Enable HSI.\n * @unit SWU-LL-01\n"
       " * @spec USPEC-LL-01-01\n */\nstatic inline void LL_RCC_HSI_Enable(void)\n{\n"
       "  ll_rcc_regs[LL_RCC_CR_OFFSET / 4U] |= LL_RCC_CR_HSION_MSK;\n}\n")


def main() -> int:
    from forge_factory.inspection import swtrace
    from forge_factory.layer import TRACE_PROFILE

    with tempfile.TemporaryDirectory() as td:
        ws = Path(td) / "WO" / "workspace"
        for rel, text in {".forge-run/manifest.json": json.dumps({"layer": "LL", "trace_profile": TRACE_PROFILE}),
                          "workproducts/SWE.1/software_requirements.md": REQS,
                          "workproducts/SWE.2/architecture_static.puml": ARCH,
                          "workproducts/SWE.3/unit_specifications.md": UNITS,
                          "workproducts/SWE.3/detailed_design/SWU-LL-01.puml": DESIGN,
                          "software/ll/stm32n6xx_ll_rcc.h": HDR}.items():
            (ws / rel).parent.mkdir(parents=True, exist_ok=True)
            (ws / rel).write_text(text)
        f = swtrace.check_phase(ws, "SWE.3")["major_findings"]
    bad = [x for x in f if "DESIGN_MISSING_SPEC_REF" in x or "DOXYGEN_WARNING" in x]
    if bad:
        print(f"SYMPTOM_PRESENT:{SIG}")
        return 1
    print("SYMPTOM_ABSENT" if not f else f"REPRODUCER_ERROR:unexpected findings {f[:2]}")
    return 0 if not f else 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"REPRODUCER_ERROR:{type(exc).__name__}:{str(exc)[:160]}")
        sys.exit(2)
