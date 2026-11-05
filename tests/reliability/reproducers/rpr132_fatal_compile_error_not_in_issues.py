"""RPR-132 (local run WO-F014-SWE3-CRCHAL-20261103-L27, Omniverse2, 2026-11-03): the first SWE.3 target compile of the
CRC HAL failed with "stm32n6xx_ll_crc.h:28:10: fatal error: stm32n6xx.h: No such file or directory", but the
forge-build-mcp compile result was FAIL with an EMPTY issue list ("0/1 units compiled"): the tools collect only lines
with ": error:" / ": warning:", and a fatal diagnostic reads ": fatal error:". The author saw no reason, spent its
budget on shell probes and wrote its own device-header stub. The same filter drops the line from run_unit's
BUILD_FAIL diagnostics, and clang_analyze, which fails only on collected lines, PASSES a unit it could not analyse.

Scenario (synthetic workspace in a scratch dir; host clang only): a HAL source including a missing header, through the
real compile (host-clang), run_unit (self-checking C harness) and clang_analyze operations of the revision under test.
Symptom: a FAIL without an issue naming the missing header, or clang_analyze PASS. Control: an ordinary compile error
(undeclared identifier) is reported by compile and run_unit as before (a loosened check is an error, not ABSENT)."""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

SIG = "a fatal compile error (missing header) is not in the tool issues and clang_analyze passes the unit"
HAL_H = "#ifndef HAL_X_H\n#define HAL_X_H\n#include <stdint.h>\nuint32_t HAL_RCC_Probe(void);\n#endif\n"
FATAL = '#include "stm32n6xx_hal_rcc.h"\n#include "rpr132_missing_device.h"\nuint32_t HAL_RCC_Probe(void)\n{\n    return 0U;\n}\n'
UNDECL = '#include "stm32n6xx_hal_rcc.h"\nuint32_t HAL_RCC_Probe(void)\n{\n    return rpr132_undeclared;\n}\n'
TEST = ('#include <stdio.h>\n#include "stm32n6xx_hal_rcc.h"\nint main(void)\n{\n    printf("UT-001 %s\\n", '
        'HAL_RCC_Probe() == 0U ? "PASS" : "FAIL");\n    return 0;\n}\n')


def run(td: Path, name: str, hal_c: str) -> dict:
    from forge_factory.mcp import sdk
    from forge_factory.mcp.servers import analysis as A
    from forge_factory.mcp.servers import build as B
    from forge_factory.mcp.servers import tests as T

    ws = td / name
    for rel, text in {".forge-run/manifest.json": json.dumps({"layer": "HAL"}),
                      "software/hal/stm32n6xx_hal_rcc.h": HAL_H, "software/hal/stm32n6xx_hal_rcc.c": hal_c,
                      "software/tests/unit/test_rcc.c": TEST}.items():
        (ws / rel).parent.mkdir(parents=True, exist_ok=True)
        (ws / rel).write_text(text)
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=ws, check=True)

    def ctx(srv, op, role, ph):
        return sdk.ToolContext(srv, op, role, ph, ws, "rpr132")

    return {"compile": B.compile_(ctx("forge-build-mcp", "compile", "swe3-author", "SWE.3"),
                                  B.CompileIn(profile="host-clang")),
            "unit": T.run_unit(ctx("forge-tests-mcp", "run_unit", "swe4-author", "SWE.4"), T.RunIn()),
            "analyze": A.clang_analyze(ctx("forge-analysis-mcp", "clang_analyze", "swe3-author", "SWE.3"), A.AnalyzeIn())}


def main() -> int:
    import os

    with tempfile.TemporaryDirectory() as td:
        os.environ["FORGE_STATE_DIR"], os.environ["FORGE_EVENTS_DIR"] = f"{td}/state", f"{td}/events"
        ctl = run(Path(td), "undeclared", UNDECL)
        bad = run(Path(td), "fatal", FATAL)
    for op in ("compile", "unit"):
        if ctl[op]["status"] != "FAIL" or not any("rpr132_undeclared" in i for i in ctl[op]["issues"]):
            print(f"REPRODUCER_ERROR:SCENARIO_NOT_REACHED:{op} control {ctl[op]['status']} {ctl[op]['issues'][:3]}")
            return 2
    missing = [op for op in ("compile", "unit", "analyze") if bad[op]["status"] == "PASS"
               or not any("rpr132_missing_device.h" in i for i in bad[op]["issues"])]
    if missing:
        print("observed: " + "; ".join(f"{op} {bad[op]['status']} {bad[op]['issues'][:2]}" for op in missing))
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
