"""Owner decision 2026-11-03 (B): requirement-based unit tests are GoogleTest/GoogleMock 1.11.0 TESTs against the C
driver; run_unit builds and runs them, maps each TEST to its UT id, Matrix 4 reads their @test/@verifies blocks and
the LLVM source-based coverage of the driver code is unchanged."""
from __future__ import annotations

import json
import shutil
import subprocess

import pytest
from forge_factory import gtest_toolchain as G
from forge_factory.lrtx import structured as S
from forge_factory.lrtx import swe4
from forge_factory.mcp.servers import tests as TS
from forge_factory.workflow import scaffold
from test_lrtx_swe1 import _scripted, pytestmark, ws  # noqa: F401 - fixture and owner-input precondition
from test_lrtx_swe2 import ws1  # noqa: F401 - fixture
from test_lrtx_swe3 import TOOLS, ws2  # noqa: F401 - fixture
from test_lrtx_swe4 import TESTS, ws3  # noqa: F401 - fixture


def _have_gtest() -> bool:
    try:
        G.load()
    except G.GtestToolchainError:
        return False
    return shutil.which("clang++") is not None


GTEST = pytest.mark.skipif(not (TOOLS and _have_gtest()), reason="pinned googletest toolchain not installed")


def test_gtest_xml_results_map_to_ut_ids(tmp_path):
    x = tmp_path / "r.xml"
    x.write_text('<testsuites><testsuite name="SWU_LL_01"><testcase name="UT_001" classname="SWU_LL_01" '
                 'status="run" result="completed"/><testcase name="UT_002" classname="SWU_LL_01" status="run">'
                 '<failure message="t.cpp:9&#x0A;Expected equality: 5 vs 6"/></testcase><testcase name="Other" '
                 'classname="X" status="notrun" result="skipped"/></testsuite></testsuites>')
    assert TS.gtest_results(x) == [{"id": "UT-001", "status": "PASS", "message": ""},
                                   {"id": "UT-002", "status": "FAIL", "message": "t.cpp:9 Expected equality: 5 vs 6"},
                                   {"id": "X.Other", "status": "SKIPPED", "message": ""}]


@GTEST
def test_gtest_harness_run_unit_matrix4_and_coverage(ws3, monkeypatch):  # noqa: F811
    monkeypatch.setattr(S, "call", _scripted(TESTS, []))
    assert swe4.visit_tests(ws3, "m")["status"] == "PASS"
    h = ws3 / "software/tests/unit/test_iwdg.cpp"
    text = h.read_text()
    assert "#include <gtest/gtest.h>" in text and "TEST(SWU_LL_05, UT_005)" in text and "CHECK(" not in text
    assert not (ws3 / "software/tests/unit/test_iwdg.c").exists()
    from forge_factory.lrtx import tools as T

    run = T.call(ws3, "forge-tests-mcp", "run_unit", {}, "swe4-author", "SWE.4")
    assert run["status"] == "PASS", run["issues"]
    from forge_factory.inspection.swtrace import build_all, check_results, latest_run

    res = check_results(latest_run(ws3, "run_unit")["raw"])
    assert res == {t: "PASS" for t in sorted(res)} and len(res) == 9  # one result line per TEST
    rep = build_all(ws3, upto="SWE.4", render=False, doxygen=False, export=False, write={4})
    assert rep["findings"]["SWE.4"] == []  # Matrix 4 complete: every USPEC verified by a passing gtest TEST
    cov = T.call(ws3, "forge-tests-mcp", "llvm_coverage", {}, "swe4-author", "SWE.4")
    assert cov["status"] == "PASS" and cov["metrics"]["line_pct"] == 100.0, cov
    assert swe4.visit_report(ws3)["status"] == "PASS"
    rpt = (ws3 / "workproducts/SWE.4/unit_verification_report.md").read_text()
    assert "GoogleTest/GoogleMock 1.11.0" in rpt and "| UT-005 | USPEC-LL-05-01 |" in rpt and "| PASS |" in rpt


@GTEST
def test_a_failing_gtest_names_the_test_and_values(ws3, monkeypatch):  # noqa: F811
    hdr = ws3 / "software/ll/stm32n6xx_ll_iwdg.h"
    monkeypatch.setattr(S, "call", _scripted(TESTS, []))
    assert swe4.visit_tests(ws3, "m")["status"] == "PASS"
    hdr.write_text(hdr.read_text().replace("= 0x0000AAAAU;", "= 0x0000AAABU;"))
    from forge_factory.lrtx import tools as T

    run = T.call(ws3, "forge-tests-mcp", "run_unit", {}, "swe4-author", "SWE.4")
    assert run["status"] == "FAIL"
    assert any(i.startswith("GTEST_FAIL:test_iwdg.cpp#UT-002:") for i in run["issues"]), run["issues"]
    assert swe4._failures(run).keys() == {"UT-002"}


@GTEST
def test_gtest_answer_validation(ws3):  # noqa: F811
    c = next(c for c in swe4.plan_cases(ws3, write=False) if c["ut"] == "UT-005")
    good = TESTS["test:UT-005"]
    assert swe4.validate_gtest(ws3, good, c) == []
    for bad, want in ((good["code"].replace("TEST(SWU_LL_05, UT_005)", "TEST(Iwdg, Prescaler)"), "exactly one `TEST("),
                      (good["code"].replace("@verifies USPEC-LL-05-01", "@verifies SWR-005"), "must name exactly"),
                      (good["code"].replace("EXPECT_TRUE(", "printf(\"%d\", "), "checks nothing"),
                      (good["code"].replace("ut_reset_regs();", "ut_reset_regs();\n    LL_IWDG_Enable();", 1),
                       "call to LL_IWDG_Enable")):
        assert any(want in e for e in swe4.validate_gtest(ws3, {**good, "code": bad}, c)), (want, bad)


@GTEST
def test_gmock_time_base_seam_drives_the_timeout_path(tmp_path):
    """The generated GoogleMock seam of a HAL time base (profile hal.time_base): unmocked +1 ms per call, mocked as the
    test scripts it."""
    t = G.load()
    (tmp_path / "hal.h").write_text("#include <stdint.h>\nuint32_t HAL_GetTick(void);\n"
                                    "int hal_wait(uint32_t timeout);\n")
    (tmp_path / "hal.c").write_text('#include "hal.h"\nint hal_wait(uint32_t timeout)\n{\n    uint32_t t0 = HAL_GetTick();\n'
                                    "    int st = 0;\n    while ((HAL_GetTick() - t0) <= timeout)\n    {\n"
                                    "        st++;\n        if (st > 5)\n        {\n            return 0;\n        }\n"
                                    "    }\n    return -1;\n}\n")
    test = (scaffold.GTEST_HEAD + 'extern "C" {\n#include "hal.h"\n}\n' + scaffold.GMOCK_TIME_BASE.format(
        tb="HAL_GetTick") + "TEST(SWU_HAL_01, UT_001)\n{\n    ut_tick = 0U;\n    EXPECT_EQ(hal_wait(100U), 0);\n}\n"
        "TEST(SWU_HAL_01, UT_002)\n{\n    UtTimeBaseMock tb;\n    EXPECT_CALL(tb.mock, Tick()).WillOnce(::testing::Return(0U))"
        ".WillRepeatedly(::testing::Return(11U));\n    EXPECT_EQ(hal_wait(10U), -1);\n}\n")
    (tmp_path / "t.cpp").write_text(test)
    cmd = (f"clang -std=c11 -c hal.c -o hal.o && clang++ -std=c++17 -Wall -Wextra {' '.join(t['cxx_flags'])} "
           f"-isystem {t['include']} -c t.cpp -o t.o && clang++ {' '.join(t['cxx_flags'])} t.o hal.o {t['gmock']} "
           f"{t['gtest']} {t['gtest'].replace('libgtest.a', 'libgtest_main.a')} -lpthread -o t && ./t")
    r = subprocess.run(cmd, shell=True, cwd=tmp_path, capture_output=True, text=True)  # noqa: S602 - fixed test command
    assert r.returncode == 0, r.stdout[-800:] + r.stderr[-800:]
    assert "[  PASSED  ] 2 tests." in r.stdout


def test_gtest_harness_text_has_no_c_harness_machinery():
    c = scaffold.HARNESS.replace('#include "stm32n6xx_hal_rcc.h"', '#include "stm32n6xx_ll_rcc.h"')
    import forge_factory.layer as L

    old = L.profile
    L.profile = lambda _w=None: {"hal": {}}
    try:
        g = scaffold.to_gtest(c, None)
    finally:
        L.profile = old
    assert 'extern "C" {\n#include "stm32n6xx_ll_rcc.h"\n}' in g and "volatile uint32_t ll_rcc_regs" in g
    assert "#define CHECK" not in g and "int main" not in g and scaffold.TEST_CALLS_MARKER not in g
    assert scaffold.TEST_CASES_MARKER in g and json.dumps(g)
