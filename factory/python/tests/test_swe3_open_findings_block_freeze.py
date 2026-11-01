"""CAPA-097 (run WO-F014-SWE3-IWDG-20261101-L1): the structured SWE.3 design node replaced the code node's FAILED reply
(open cppcheck MISRA findings) with PASS and the code froze; the design node now refuses while tool findings are open."""
import json

import pytest
from forge_factory.inspection import unit_scaffold
from forge_factory.lrtx import structured as S
from forge_factory.lrtx import swe3, tools
from test_lrtx_swe1 import _scripted, pytestmark, ws  # noqa: F401 - fixture and owner-input precondition
from test_lrtx_swe2 import ws1  # noqa: F401 - fixture
from test_lrtx_swe3 import CODE, TOOLS, ws2  # noqa: F401 - fixture

pytestmark = [pytestmark, pytest.mark.skipif(not TOOLS, reason="build tools not installed")]


def _coded(ws2, monkeypatch):  # noqa: F811
    monkeypatch.setattr(S, "call", _scripted(CODE, []))
    assert swe3.visit_code(ws2, "m")["status"] == "PASS"
    unit_scaffold.scaffold(ws2)
    return ws2


def test_open_code_visit_findings_block_the_design_pass(ws2, monkeypatch):  # noqa: F811
    w = _coded(ws2, monkeypatch)
    asm = w / ".forge-run/lrtx/SWE.3/code-assembly.json"
    asm.write_text(json.dumps({**json.loads(asm.read_text()), "issues": ["cppcheck: MISRA-12.1:stm32n6xx_ll_iwdg.h:122"]}))
    rep = swe3.visit_design(w)
    assert rep["status"] == "FAILED" and any("MISRA-12.1" in i for i in rep["issues"])


def test_a_cppcheck_fail_measured_at_design_blocks_the_freeze(ws2, monkeypatch):  # noqa: F811
    w = _coded(ws2, monkeypatch)
    real = tools.call

    def call(ws_, server, op, *a, **k):
        if op == "cppcheck":
            return {"status": "FAIL", "summary": "1 rule", "issues": ["MISRA-10.6:stm32n6xx_ll_iwdg.h:135"], "metrics": {}}
        return real(ws_, server, op, *a, **k)

    monkeypatch.setattr(tools, "call", call)
    rep = swe3.visit_design(w)
    assert rep["status"] == "FAILED" and rep["issues"] == ["cppcheck: MISRA-10.6:stm32n6xx_ll_iwdg.h:135"]
    assert (w / "workproducts/SWE.3/detailed_design.md").is_file()  # the design is still rendered for the record
