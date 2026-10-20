"""RPR-064 (b006): host coverage of a delivery was reported over the whole delivered headers (ST: 28k lines, line 1.21%)
with no figure for the delivered scope functions the tests target."""
import json
import os
import sys
import tempfile
from pathlib import Path

SIG = "delivery coverage reported only over whole delivered files"
OTHER = "".join(f"static inline unsigned LL_RCC_Other{i}(unsigned v)\n{{\n    return v + {i}U;\n}}\n" for i in range(30))
HDR = ("#include <stdint.h>\nstatic inline unsigned LL_RCC_Scope(unsigned v)\n{\n    return (v != 0U) ? 1U : 0U;\n}\n"
       + OTHER)
TEST = ('#include <stdio.h>\n#include "stm32n6xx_ll_rcc.h"\nint main(void)\n{\n'
        '    int ok = (LL_RCC_Scope(1U) == 1U) && (LL_RCC_Scope(0U) == 0U);\n    printf("UT-001 %s\\n", ok ? "PASS" : "FAIL");\n'
        '    return ok ? 0 : 1;\n}\n')


def main() -> int:
    with tempfile.TemporaryDirectory() as d:
        os.environ["FORGE_STATE_DIR"] = str(Path(d) / "state")
        os.environ["FORGE_EVENTS_DIR"] = str(Path(d) / "state/events")
        from forge_factory.mcp import sdk
        from forge_factory.mcp.servers import tests as T

        ws = Path(d) / "ws"
        (ws / "software/ll").mkdir(parents=True)
        (ws / "software/tests/unit").mkdir(parents=True)
        (ws / ".forge-run/delivery").mkdir(parents=True)
        (ws / "software/ll/stm32n6xx_ll_rcc.h").write_text(HDR)
        (ws / "software/tests/unit/test_rcc.c").write_text(TEST)
        (ws / ".forge-run/delivery/scope.json").write_text(json.dumps({"functions": [{"name": "LL_RCC_Scope"}]}))
        (ws / ".forge-run/manifest.json").write_text(json.dumps({
            "layer": "LL", "code_mode": "FROZEN", "delivered": [{"path": "software/ll/stm32n6xx_ll_rcc.h",
                                                                   "role": "delivered_code"}],
            "delivery": {"code_mode": "FROZEN", "build": {"style": "forge"}}}))
        ctx = sdk.ToolContext("forge-tests-mcp", "run_unit", "swe4-author", "SWE.4", ws, "r")
        T.run_unit(ctx, T.RunIn(coverage=True))
        r = T.llvm_coverage(sdk.ToolContext("forge-tests-mcp", "llvm_coverage", "swe4-author", "SWE.4", ws, "r"),
                            T.CovIn())
    if r["metrics"].get("scope_function_pct") != 100.0:
        print(f"coverage: {r['summary']}")
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
