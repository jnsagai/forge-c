"""CAPA-244 (WO-F014-SWE2-TIMH-20261109-L47): in workproducts/SWE.2/api_calls.json each HAL_TIM_Init case line lacked
the '}' closing its case object. JSON nests the following cases inside it, so the gate's CONTRACT_NOT_JSON issue carried
only the end-of-file parser text "Expecting ',' delimiter: line 47 column 1"; the SWE.2 author resubmitted the same file
and the gate stopped the phase as STUCK. The issue now names the lines where the still-open objects begin when the parse
fails at the end of the file; every other parse error keeps its text."""
from __future__ import annotations

import json

from forge_factory.assurance.register_contract import _load, unclosed_hint

REL = "workproducts/SWE.2/api_calls.json"


def _write(tmp_path, text):
    (tmp_path / "workproducts/SWE.2").mkdir(parents=True)
    (tmp_path / REL).write_text(text)
    return tmp_path


def test_truncated_contract_names_the_missing_closing_brace(tmp_path):
    good = json.dumps({"cases": {"A": {"function": "HAL_X", "args": ["{ .a = 1U }"]}}}, indent=2)
    ws = _write(tmp_path, good[:-1] + "\n")  # the last '}' is missing, as in L47
    d, issues = _load(ws, REL)
    assert d is None and len(issues) == 1
    assert issues[0].startswith(f"CONTRACT_NOT_JSON:{REL}:Expecting ',' delimiter")
    assert issues[0].endswith("the file ends with 1 object(s)/array(s) still open, opened on line(s) 1: each must close "
                              "where it ends (e.g. a case line missing its closing '}'), not at the end of the file")


def test_case_lines_missing_their_closing_brace_are_named(tmp_path):
    # L47's shape: case lines 3-5 end '"],' without '}', so later cases nest inside them; the two outer closers at the
    # end close the innermost ones, and the hint names the still-open lines, the broken case line 3 among them
    text = ('{\n  "calls": {\n    "A": {"function": "HAL_X", "args": ["{ .a = 1U }"],\n'
            '    "B": {"function": "HAL_X", "args": ["{ .a = 2U }"],\n'
            '    "C": {"function": "HAL_X", "args": ["{ .a = 3U }"],\n'
            '    "D": {"function": "HAL_Y", "args": []}\n  }\n}\n')
    ws = _write(tmp_path, text)
    _, issues = _load(ws, REL)
    assert "3 object(s)/array(s) still open, opened on line(s) 1,2,3:" in issues[0]


def test_brackets_inside_strings_and_arrays_are_counted_correctly():
    text = '{"cases": {"A": {"args": ["{ not a brace }", "\\" ]"]'
    try:
        json.loads(text)
    except ValueError as exc:
        assert "3 object(s)/array(s) still open, opened on line(s) 1:" in unclosed_hint(text, exc)


def test_other_parse_errors_keep_their_text(tmp_path):
    ws = _write(tmp_path, '{"cases": {"A": 1,, "B": 2}}\n')
    _, issues = _load(ws, REL)
    assert len(issues) == 1 and "still open" not in issues[0]
    assert issues[0].startswith(f"CONTRACT_NOT_JSON:{REL}:")


def test_valid_contract_is_unchanged(tmp_path):
    ws = _write(tmp_path, '{"cases": {}}')
    assert _load(ws, REL) == ({"cases": {}}, [])
