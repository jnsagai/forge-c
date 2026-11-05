"""Owner 2026-11-01 ("frozen case, never repair, otherwise we repair"): a cppcheck finding located in FROZEN delivered
code is a DELIVERED_CODE finding for the owner (a package gap unless dispositioned), never a failure the factory would
route to repair; the same finding in code the factory authors still fails cppcheck (it is repaired)."""
import shutil

import pytest
from forge_factory.brownfield import package as BP
from forge_factory.mcp.servers import analysis
from test_m2_mcp import call, ws  # noqa: F401 - fixture

pytestmark = pytest.mark.skipif(shutil.which("cppcheck") is None, reason="cppcheck not installed")
SRC = "unsigned int f(unsigned int a, unsigned int b)\n{\n    return a << b + 1U;\n}\n"  # MISRA 12.1 (precedence)


def test_a_misra_finding_in_frozen_delivered_code_goes_to_the_owner_not_to_repair(ws, monkeypatch):  # noqa: F811
    (ws / "software/src/vendor.c").write_text(SRC)
    monkeypatch.setattr(analysis, "frozen_paths", lambda w: {"software/src/vendor.c"})
    r = call(analysis, "forge-analysis-mcp", "cppcheck", {}, "swe3-author", "SWE.3")
    found = [x for x in BP.static_findings(ws) if x.startswith("STATIC_ANALYSIS:MISRA-")]
    assert found and all(":software/src/vendor.c:" in x for x in found), BP.static_findings(ws)
    assert not any(i.startswith("MISRA-") and "vendor.c" in i for i in r["issues"])  # nothing left to repair
    assert any(i.startswith("DELIVERED_CODE:MISRA-") for i in r["issues"])
    monkeypatch.setattr(analysis, "frozen_paths", lambda w: set())  # authored (or FIX_ALLOWED) code: repaired
    r = call(analysis, "forge-analysis-mcp", "cppcheck", {}, "swe3-author", "SWE.3")
    assert r["status"] == "FAIL" and any(i.startswith("MISRA-") and "vendor.c" in i for i in r["issues"])
