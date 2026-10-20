"""RPR-061 (b006): the swe3_all validator applied the factory's greenfield SWE.3 checks to a frozen CMSIS delivery
(NO_REGISTER_DEFINES, LL_NOT_STATIC_INLINE for __STATIC_INLINE, out-of-scope APIs as unallocated) - DEF-002."""
import json
import sys
import tempfile
from pathlib import Path

SIG = "swe3_all applies greenfield checks to a delivery"
HDR = ("#include <stdint.h>\ntypedef struct { volatile uint32_t CR; } RCC_TypeDef;\n#define RCC ((RCC_TypeDef *)0x56028000U)\n"
       "#define RCC_CR_HSION (1U << 3)\n#define __STATIC_INLINE static inline\n"
       "__STATIC_INLINE void LL_RCC_HSI_Enable(void) { RCC->CR |= RCC_CR_HSION; }\n")


def main() -> int:
    from forge_factory.mcp import sdk
    from forge_factory.mcp.servers import docs as D

    with tempfile.TemporaryDirectory() as d:
        ws = Path(d)
        (ws / ".forge-run/delivery").mkdir(parents=True)
        (ws / "software/ll").mkdir(parents=True)
        (ws / "software/ll/stm32n6xx_ll_rcc.h").write_text(HDR)
        (ws / ".forge-run/delivery/scope.json").write_text(json.dumps({"functions": [
            {"name": "LL_RCC_HSI_Enable", "file": "software/ll/stm32n6xx_ll_rcc.h", "line": 6}]}))
        (ws / ".forge-run/manifest.json").write_text(json.dumps({
            "work_order": "WO-RPR061", "layer": "LL", "code_mode": "FROZEN",
            "delivered": [{"path": "software/ll/stm32n6xx_ll_rcc.h", "role": "delivered_code", "sha256": "x"}],
            "delivery": {"code_mode": "FROZEN", "build": {"style": "cmsis", "defines": [], "secure": False}}}))
        ctx = sdk.ToolContext("forge-docs-mcp", "validate_artifact", "swe3-author", "SWE.3", ws, "r")
        r = D.validate_artifact(ctx, D.ValidateIn(path="workproducts/SWE.3/detailed_design.md", check="swe3_all"))
    bad = [i for i in r["issues"] if "NO_REGISTER_DEFINES" in i or "LL_NOT_STATIC_INLINE" in i]
    if bad:
        print(f"greenfield findings: {bad[:2]}")
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
