"""Owner decision 2026-11-03: SWE.1 requirements and SWE.3 USPEC items cover negative paths and corner cases, not
only the positive path; the SWE.4 test kind follows from the USPEC item (one test per USPEC item)."""
from __future__ import annotations

import json

import pytest
from forge_factory.inspection.uspec_plan import uspec_kind
from forge_factory.lrtx import swe1, swe3
from test_lrtx_swe1 import pytestmark, ws  # noqa: F401 - fixture and owner-input precondition
from test_lrtx_swe2 import ws1  # noqa: F401 - fixture
from test_lrtx_swe3 import CODE, ws2  # noqa: F401 - fixture

G = {"register": "IWDG_PR", "fields": {"PR": {"msb": 3, "lsb": 0}}}


def _doc(statement, effect, opens=()):
    return {"requirements": [{"key": "k", "statement": statement, "effects": [effect]}], "open_points": list(opens)}


W = {"case": "SET", "register": "IWDG_PR", "field": "PR", "op": "write", "value": "0x5"}


def test_ar7_value_write_needs_a_corner_case():
    plain = "When LL_IWDG_SetPrescaler is called with a value, the IWDG LL driver shall write the value to IWDG_PR.PR."
    assert swe1.corner_case_findings(_doc(plain, W), G)[0].startswith("AR-7: the write of IWDG_PR.PR (4 bits)")
    assert swe1.corner_case_findings(_doc(plain, {**W, "requested": "0x15"}), G) == []  # CAPA-120 requested/value
    above = plain[:-1] + ", so that a value above 15U is confined to the field."
    assert swe1.corner_case_findings(_doc(above, W), G) == []
    assert swe1.corner_case_findings(_doc(plain, W, ["IWDG_PR.PR: no invalid input exists (4-bit argument type)"]),
                                      G) == []


def test_ar7_never_blocks_constants_flags_or_full_width_fields():
    key = "When LL_IWDG_Enable is called, the IWDG LL driver shall write 0x0000CCCC to IWDG_KR.KEY."
    kr = {"register": "IWDG_KR", "fields": {"KEY": {"msb": 15, "lsb": 0}}}
    assert swe1.corner_case_findings(_doc(key, {**W, "register": "IWDG_KR", "field": "KEY"}), kr) == []
    flag = {"case": "S", "register": "IWDG_PR", "field": "PR", "op": "set", "value": ""}
    assert swe1.corner_case_findings(_doc("When X is called with a value, it shall set IWDG_PR.PR.", flag), G) == []
    full = {"register": "R", "fields": {"DR": {"msb": 31, "lsb": 0}}}
    st = "When X is called with a value, the driver shall write the value to R.DR."
    assert swe1.corner_case_findings(_doc(st, {**W, "register": "R", "field": "DR"}), full) == []


def test_swe1_packets_carry_ar7_only_with_unit_verification(ws):  # noqa: F811
    inv = swe1.inventory(ws)
    assert swe1.AR_NEGATIVE in swe1.group_packet(ws, swe1.groups(inv)[0], "m")["instructions"]
    assert swe1.AR_NEGATIVE in swe1.crosscut_packet(ws, [], "m")["instructions"]
    m = json.loads((ws / ".forge-run/manifest.json").read_text())
    m.pop("unit_verification")
    (ws / ".forge-run/manifest.json").write_text(json.dumps(m))
    assert swe1.AR_NEGATIVE not in swe1.group_packet(ws, swe1.groups(inv)[0], "m")["instructions"]


def test_swe3_value_or_flag_unit_needs_a_negative_or_corner_item(ws2):  # noqa: F811
    u = swe3.units(ws2)[4]
    good = CODE["code:SWU-LL-05"]
    assert swe3.validate_code(ws2, good, u) == []  # 'preserving other bits' is a negative item
    assert swe3.USPEC_NEGATIVE_RULE in swe3.code_packet(ws2, u, "m")["instructions"]
    nominal = json.loads(json.dumps(good))
    nominal["spec_items"][0]["behaviour"] = "The unit shall write prescaler to IWDG_PR.PR."
    assert any("negative or corner-case behaviour" in f for f in swe3.validate_code(ws2, nominal, u))
    enable = swe3.units(ws2)[0]  # (void) -> void: no value, no flag - never required
    assert swe3.validate_code(ws2, CODE["code:SWU-LL-01"], enable) == []


@pytest.mark.parametrize("text,kind", [
    ("Write the requested divider into the 4-bit IWDG_PR.PR field, confining the argument to its range.", "boundary"),
    ("Update IWDG_PR.PR while leaving all remaining bits of that register unchanged.", "negative"),
    ("Return 1U when IWDG_SR.ONF is set, else 0U.", "negative"),
    ("Write the start key 0x0000CCCC to IWDG_KR as a write-only key (never read).", "positive"),
    ("Return HAL_TIMEOUT when the ready flag stays clear for the whole timeout.", "error")])
def test_swe4_test_kind_follows_from_the_uspec_item(text, kind):
    assert uspec_kind(text) == kind


def test_swe4_kinds_must_contain_the_uspec_kind():
    from forge_factory.lrtx import swe4

    c = {"uspec": "USPEC-LL-05-02", "plan": {"test_kind": "negative"},
         "unit": {"function": {"name": "LL_X_Set", "params": [{"type": "uint32_t", "name": "v"}]}}}
    body = "LL_X_Set(1U); EXPECT_EQ(r, 1U);"
    assert swe4._kind_errors({"kinds": ["positive"]}, c, body) == [
        "USPEC-LL-05-02 is a negative behaviour: the test checks it and kinds includes negative"]
    assert swe4._kind_errors({"kinds": ["negative"]}, c, body) == []  # positive is not demanded for a negative item
    b = {**c, "plan": {"test_kind": "boundary"}}
    assert swe4._kind_errors({"kinds": ["boundary"]}, b, body)[0].startswith("kind boundary needs the field limits")
