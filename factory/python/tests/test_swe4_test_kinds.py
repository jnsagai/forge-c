"""CAPA-092 (run WO-F014-SWE4-IWDG-20261101-L1, SWE4-02): structured SWE.4 tests declare their kinds and check the
field boundaries of value-taking functions; the report shows the declared kinds instead of labelling all positive."""
from __future__ import annotations

import pytest
from forge_factory.lrtx import structured as S
from forge_factory.lrtx import swe4
from test_lrtx_swe1 import _scripted, pytestmark, ws  # noqa: F401 - fixture and owner-input precondition
from test_lrtx_swe2 import ws1  # noqa: F401 - fixture
from test_lrtx_swe3 import TOOLS, ws2  # noqa: F401 - fixture
from test_lrtx_swe4 import TESTS, _t, ws3  # noqa: F401 - fixture

pytestmark = [pytestmark, pytest.mark.skipif(not TOOLS, reason="build tools not installed")]


def _case(ws, ut):
    return next(c for c in swe4.cases(ws) if c["ut"] == ut)


def test_a_value_taking_function_needs_declared_boundary_checks(ws3):
    c = _case(ws3, "UT-005")
    single = _t("UT-005", "USPEC-LL-05-01", '    LL_IWDG_SetPrescaler(5U);\n    CHECK("UT-005", (ll_iwdg_regs['
                'LL_IWDG_PR_OFFSET / 4U] & LL_IWDG_PR_PR_MSK) == 5U);')
    errs = swe4.validate_test(ws3, single, c)
    assert any("declare kind boundary" in e for e in errs)
    claimed = {**single, "kinds": ["positive", "boundary"]}  # declared but not done: one call only
    assert any("further calls" in e for e in swe4.validate_test(ws3, claimed, c))
    assert swe4.validate_test(ws3, TESTS["test:UT-005"], c) == []
    assert any("include positive" in e for e in swe4.validate_test(ws3, {**TESTS["test:UT-005"], "kinds": ["boundary"]}, c))
    no_value = _case(ws3, "UT-001")  # LL_IWDG_Enable takes no value: positive alone is valid
    assert swe4.validate_test(ws3, TESTS["test:UT-001"], no_value) == []


def test_report_shows_the_declared_kinds(ws3, monkeypatch):
    monkeypatch.setattr(S, "call", _scripted(TESTS, []))
    assert swe4.visit_tests(ws3, "m")["status"] == "PASS"
    swe4.visit_report(ws3)
    rpt = (ws3 / "workproducts/SWE.4/unit_verification_report.md").read_text()
    assert "| UT-005 | LL_IWDG_SetPrescaler | SWR-005 | positive, negative, boundary |" in rpt
    assert "## Test design per unit" in rpt and "none declared: " in rpt
