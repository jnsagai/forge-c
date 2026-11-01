"""CAPA-093 (run WO-F014-SWE4-IWDG-20261101-L1, SWE4-04): a static-analysis finding on the frozen SWE.3 code is not
routed to the SWE.4 test tasks, and the SWE.4 report quotes the SWE.3 coding-rule record with its open-gap status."""
from __future__ import annotations

import pytest
from forge_factory.lrtx import structured as S
from forge_factory.lrtx import swe4
from test_lrtx_swe1 import _scripted, pytestmark, ws  # noqa: F401 - fixture and owner-input precondition
from test_lrtx_swe2 import ws1  # noqa: F401 - fixture
from test_lrtx_swe3 import TOOLS, ws2  # noqa: F401 - fixture
from test_lrtx_swe4 import TESTS, ws3  # noqa: F401 - fixture

pytestmark = [pytestmark, pytest.mark.skipif(not TOOLS, reason="build tools not installed")]


def test_report_quotes_the_swe3_coding_rule_record(ws3, monkeypatch):
    monkeypatch.setattr(S, "call", _scripted(TESTS, []))
    assert swe4.visit_tests(ws3, "m")["status"] == "PASS"
    dev = ws3 / swe4.DEVIATIONS
    dev.parent.mkdir(parents=True, exist_ok=True)
    dev.write_text("# MISRA C:2012 deviations\n\n- Approved deviation records: 0 (none)\n")
    swe4.visit_report(ws3)
    rpt = (ws3 / "workproducts/SWE.4/unit_verification_report.md").read_text()
    assert "> - Approved deviation records: 0 (none)" in rpt and "Review status:" in rpt


def test_a_static_analysis_finding_is_not_routed_to_the_test_tasks(ws3, monkeypatch):
    calls = []
    monkeypatch.setattr(S, "call", _scripted(TESTS, calls))
    assert swe4.visit_tests(ws3, "m")["status"] == "PASS"
    n = len(calls)
    monkeypatch.setattr(swe4.V, "rework_findings", lambda ws, ph, since: [
        "SWE4-04: cppcheck FAIL MISRA-10.6 at stm32n6xx_ll_iwdg.h:135 has no review or deviation record"])
    assert swe4.visit_tests(ws3, "m")["status"] == "PASS"
    assert len(calls) == n  # every test task reused, no repair call spent on code SWE.4 cannot change
