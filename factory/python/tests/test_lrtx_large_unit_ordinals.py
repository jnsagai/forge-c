"""Generators already emit100+ naturally; every consuming schema/parser must retain the complete ID."""
import json

import pytest
from forge_factory.inspection import swtrace as T
from forge_factory.lrtx import structured as S
from forge_factory.lrtx import swe3, swe4


@pytest.mark.parametrize("ordinal", [99, 100, 999, 1000])
@pytest.mark.parametrize("layer", ["LL", "HAL"])
def test_unit_specs_and_doxygen_preserve_large_ordinal_identity(ordinal, layer):
    unit, spec = f"SWU-{layer}-{ordinal:02d}", f"USPEC-{layer}-{ordinal:02d}-01"
    text = (f"## {unit}: Unit\n- SWC: SWC_{layer}\n- Functions: func\n"
            f"- **{spec}** Required observable behaviour. Traces: SWR-001\n")
    parsed = T.parse_units(text)
    assert len(parsed) == 1 and parsed[0]["id"] == unit and parsed[0]["specs"][0]["id"] == spec
    assert parsed[0]["specs"][0]["swrs"] == ["SWR-001"]
    code = f"/** @unit {unit}\n * @spec {spec}\n */\nstatic inline void func(void) {{}}\n"
    found = T.functions_with_docs(code)
    assert found[0]["units"] == [unit] and found[0]["specs"] == [spec]


def test_model_output_schema_accepts_unit100_without_accepting_short_or_malformed_ids():
    doc = {"code": "complete function content " * 4, "spec_items": [{"id": "USPEC-LL-100-01",
            "behaviour": "The unit shall implement its allocated effect.", "traces": ["SWR-001"]}]}
    assert S.validate(doc, swe3.CODE_SCHEMA) == []
    for ident in ("USPEC-LL-1-01", "USPEC-LL-100-1", "USPEC-LL-100-01-extra"):
        doc["spec_items"][0]["id"] = ident
        assert S.validate(doc, swe3.CODE_SCHEMA)


def test_unit_verification_checks_complete_three_digit_spec_id(tmp_path, monkeypatch):
    unit = {"id": "SWU-LL-100", "function": {"name": "LL_PORT_Get"}}
    case = {"ut": "UT-100", "unit": unit}
    monkeypatch.setattr(swe4, "_unit_specs", lambda *a: [{"id": "USPEC-LL-100-01"}])
    monkeypatch.setattr(swe3, "_ident", lambda _: {"pfx": "PORT"})
    header = tmp_path / "port.h"
    header.write_text("")
    monkeypatch.setattr(swe3, "_header", lambda _: header)
    compilations = []
    monkeypatch.setattr(swe4, "_compile_test", lambda *args: compilations.append(args) or [])
    code = '/** @test UT-100 @verifies USPEC-LL-100-01 */\nstatic void ut_ut_100(void) { CHECK("UT-100", LL_PORT_Get() == 0U); }'
    assert swe4.validate_test(tmp_path, {"code": code}, case) == [] and len(compilations) == 1
    assert swe4.validate_test(tmp_path, {"code": code.replace("USPEC-LL-100-01", "USPEC-LL-101-01")}, case)
    assert len(compilations) == 1  # Wrong ownership cannot reach compilation.


def test_scaffold_function_sync_uses_whole_unit100(tmp_path, monkeypatch):
    from forge_factory.inspection import unit_scaffold as U

    path = tmp_path / U.UNITS_MD
    path.parent.mkdir(parents=True)
    path.write_text("## SWU-LL-100: Unit\n- SWC: SWC_LL\n- Functions: old_func\n"
                    "- **USPEC-LL-100-01** Observable behaviour. Traces: SWR-001\n")
    header = tmp_path / "port.h"
    header.write_text("/** @unit SWU-LL-100\n * @spec USPEC-LL-100-01\n */\nstatic inline void new_func(void) {}\n")
    monkeypatch.setattr(U, "code_files", lambda _: [header])
    result = U.sync_trace(tmp_path)
    assert result["functions"] == [{"unit": "SWU-LL-100", "removed": ["old_func"], "added": ["new_func"]}]
    assert T.parse_units(path.read_text())[0]["functions"] == ["new_func"]
    assert json.loads((tmp_path / U.SYNC_LOG).read_text())["functions"] == result["functions"]
