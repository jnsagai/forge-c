"""CAPA-095 (run WO-F014-SWE4-OBL-20261101-L3): a comment in a structured SWE.4 test ("read back unchanged (all bits
set)") was taken for a call to `unchanged` and the task stayed invalid; calls and identifiers are checked without comments."""
from forge_factory.lrtx import swe3, swe4


def test_comment_words_before_a_parenthesis_are_not_calls(tmp_path, monkeypatch):
    unit = {"id": "SWU-LL-01", "function": {"name": "LL_PORT_Get", "params": []}}
    case = {"ut": "UT-001", "unit": unit}
    monkeypatch.setattr(swe4, "_unit_specs", lambda *a: [{"id": "USPEC-LL-01-01"}])
    monkeypatch.setattr(swe3, "_ident", lambda _: {"pfx": "PORT"})
    header = tmp_path / "port.h"
    header.write_text("")
    monkeypatch.setattr(swe3, "_header", lambda _: header)
    monkeypatch.setattr(swe4, "_compile_test", lambda *a: [])
    code = ('/** @test UT-001 @verifies USPEC-LL-01-01 */\nstatic void ut_ut_001(void) {\n'
            '    /* positive: the register reads back unchanged (all bits set); LL_PORT_UNKNOWN (no define) */\n'
            '    CHECK("UT-001", LL_PORT_Get() == 0U); // stays clear (reset value)\n}')
    assert swe4.validate_test(tmp_path, {"code": code, "kinds": ["positive"]}, case) == []
    bad = code.replace("LL_PORT_Get() == 0U", "unchanged(LL_PORT_Get()) == 0U")
    assert any("call to unchanged" in e for e in swe4.validate_test(tmp_path, {"code": bad, "kinds": ["positive"]}, case))
