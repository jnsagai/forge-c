"""CAPA-132 (WO-F014-SWE3-CRCHAL-20261103-L27): "fatal error: stm32n6xx.h: No such file or directory" reached neither
the compile result's issues (FAIL with an empty list) nor run_unit's diagnostics, and clang_analyze passed the unit it
could not analyse. Fatal diagnostics are issues now, and a failed unit never has an empty issue list."""
import json
import subprocess

import pytest
from forge_factory.mcp import sdk
from forge_factory.mcp.servers import analysis as A
from forge_factory.mcp.servers import build as B
from forge_factory.mcp.servers import tests as T

HAL_H = "#ifndef HAL_X_H\n#define HAL_X_H\n#include <stdint.h>\nuint32_t HAL_RCC_Probe(void);\n#endif\n"
FATAL = '#include "stm32n6xx_hal_rcc.h"\n#include "stm32n6xx.h"\nuint32_t HAL_RCC_Probe(void)\n{\n    return 0U;\n}\n'
OK = '#include "stm32n6xx_hal_rcc.h"\nuint32_t HAL_RCC_Probe(void)\n{\n    return 0U;\n}\n'
TEST = ('#include <stdio.h>\n#include "stm32n6xx_hal_rcc.h"\nint main(void)\n{\n    printf("UT-001 %s\\n", '
        'HAL_RCC_Probe() == 0U ? "PASS" : "FAIL");\n    return 0;\n}\n')


@pytest.fixture()
def ws(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("FORGE_EVENTS_DIR", str(tmp_path / "events"))
    w = tmp_path / "ws"
    for rel, text in {".forge-run/manifest.json": json.dumps({"layer": "HAL"}), "software/hal/stm32n6xx_hal_rcc.h": HAL_H,
                      "software/hal/stm32n6xx_hal_rcc.c": FATAL, "software/tests/unit/test_rcc.c": TEST}.items():
        (w / rel).parent.mkdir(parents=True, exist_ok=True)
        (w / rel).write_text(text)
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=w, check=True)
    return w


def _ctx(ws, srv, op, role, ph):
    return sdk.ToolContext(srv, op, role, ph, ws, "t")


def test_fatal_missing_header_is_an_issue_of_every_tool(ws):
    c = B.compile_(_ctx(ws, "forge-build-mcp", "compile", "swe3-author", "SWE.3"), B.CompileIn(profile="host-clang"))
    assert c["status"] == "FAIL" and any("fatal error: 'stm32n6xx.h' file not found" in i or
                                         "fatal error: stm32n6xx.h: No such file" in i for i in c["issues"]), c["issues"]
    u = T.run_unit(_ctx(ws, "forge-tests-mcp", "run_unit", "swe4-author", "SWE.4"), T.RunIn())
    assert u["status"] == "FAIL" and any("stm32n6xx.h" in i for i in u["issues"]), u["issues"]
    a = A.clang_analyze(_ctx(ws, "forge-analysis-mcp", "clang_analyze", "swe3-author", "SWE.3"), A.AnalyzeIn())
    assert a["status"] == "FAIL" and any("stm32n6xx.h" in i for i in a["issues"]), a["issues"]


def test_clean_sources_stay_clean(ws):
    (ws / "software/hal/stm32n6xx_hal_rcc.c").write_text(OK)
    c = B.compile_(_ctx(ws, "forge-build-mcp", "compile", "swe3-author", "SWE.3"), B.CompileIn(profile="host-clang"))
    a = A.clang_analyze(_ctx(ws, "forge-analysis-mcp", "clang_analyze", "swe3-author", "SWE.3"), A.AnalyzeIn())
    assert (c["status"], c["issues"], a["status"], a["issues"]) == ("PASS", [], "PASS", [])
