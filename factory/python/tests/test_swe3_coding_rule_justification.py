"""Owner 2026-11-01 (MISRA policy A): SWE.3 must fix or justify each coding-rule finding before freeze. A cppcheck finding
is attributed to the function containing its line; only that unit's code task can justify it, for that rule; justified
findings are recorded (never as approved deviations) and do not block the freeze."""
import json

import pytest
from forge_factory.inspection import unit_scaffold
from forge_factory.lrtx import structured as S
from forge_factory.lrtx import swe3, tools
from forge_factory.lrtx import visit as V
from test_lrtx_swe1 import _scripted, pytestmark, ws  # noqa: F401 - fixture and owner-input precondition
from test_lrtx_swe2 import ws1  # noqa: F401 - fixture
from test_lrtx_swe3 import CODE, TOOLS, ws2  # noqa: F401 - fixture

pytestmark = [pytestmark, pytest.mark.skipif(not TOOLS, reason="build tools not installed")]


def _line_of(w, fn):
    text = swe3._header(w).read_text().splitlines()
    return next(n for n, ln in enumerate(text, 1) if f" {fn}(" in ln and "static inline" in ln) + 1


def _cpp(w, fn, rule="MISRA-12.1"):
    return f"{rule}:{swe3._header(w).name}:{_line_of(w, fn)}"


def test_findings_are_attributed_and_only_the_owning_unit_can_justify_them(ws2, monkeypatch):  # noqa: F811
    monkeypatch.setattr(S, "call", _scripted(CODE, []))
    assert swe3.visit_code(ws2, "m")["status"] == "PASS"
    us = swe3.units(ws2)
    a, b = us[0], us[1]
    finding = _cpp(ws2, a["function"]["name"])
    open_, just = swe3.coding_rule_findings(ws2, [finding], us)
    assert open_ == [f"{finding} (in {a['function']['name']})"] and just == []
    why = {"rule": "MISRA-12.1", "rationale": "the shift and mask follow the generated define order and are explicit"}
    ck = V._ckpt(ws2, "SWE.3", f"code:{b['id']}")
    st = json.loads(ck.read_text())
    st["doc"]["coding_rule_justifications"] = [why]  # another unit's justification does not count
    ck.write_text(json.dumps(st))
    assert swe3.coding_rule_findings(ws2, [finding], us)[1] == []
    ck = V._ckpt(ws2, "SWE.3", f"code:{a['id']}")
    st = json.loads(ck.read_text())
    st["doc"]["coding_rule_justifications"] = [{**why, "rule": "MISRA-10.6"}]  # another rule does not count
    ck.write_text(json.dumps(st))
    assert swe3.coding_rule_findings(ws2, [finding], us)[1] == []
    st["doc"]["coding_rule_justifications"] = [why]
    ck.write_text(json.dumps(st))
    open_, just = swe3.coding_rule_findings(ws2, [finding], us)
    assert open_ == [] and just[0]["unit"] == a["id"] and just[0]["rule"] == "MISRA-12.1"
    assert S.validate(st["doc"], swe3.CODE_SCHEMA) == []


def test_a_justified_finding_freezes_and_is_recorded_not_as_an_approved_deviation(ws2, monkeypatch):  # noqa: F811
    monkeypatch.setattr(S, "call", _scripted(CODE, []))
    assert swe3.visit_code(ws2, "m")["status"] == "PASS"
    unit_scaffold.scaffold(ws2)
    us = swe3.units(ws2)
    a = us[0]
    ck = V._ckpt(ws2, "SWE.3", f"code:{a['id']}")
    st = json.loads(ck.read_text())
    st["doc"]["coding_rule_justifications"] = [{"rule": "MISRA-12.1", "rationale": "explicit precedence would "
                                                "duplicate the generated define; the expression is unambiguous"}]
    ck.write_text(json.dumps(st))
    finding = _cpp(ws2, a["function"]["name"])
    real = tools.call
    monkeypatch.setattr(tools, "call", lambda w, srv, op, *x, **k: {"status": "FAIL", "summary": "1 rule", "metrics": {},
                        "issues": [finding]} if op == "cppcheck" else real(w, srv, op, *x, **k))
    assert swe3.visit_design(ws2)["status"] == "PASS"
    rec = json.loads((ws2 / swe3.JUSTIFICATIONS).read_text())
    assert rec["approved_deviation"] is False and rec["justified"][0]["function"] == a["function"]["name"]
    assert "justified by the author" in (ws2 / "workproducts/SWE.3/detailed_design.md").read_text()
    unit_scaffold.misra_statement(ws2)
    md = (ws2 / unit_scaffold.DEVIATIONS_MD).read_text()
    assert "NOT approved deviations): 1" in md and "Approved deviation records: 0 (none)" in md
