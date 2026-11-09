"""WO-F014-SWE1-WWDGL-20261109-L44E phase 1: two requirements could not converge because a deterministic rule
contradicted a correct inspection finding (SWR-006: a field-positioned requested constant; SWR-017: the REGISTER.FIELD
convention applied to a cross-cutting requirement)."""
from forge_factory.assurance import register_contract as RC
from forge_factory.lrtx import swe1_quality as Q


def _e(value, requested):
    return {"case": "PRESCALER_SET", "register": "WWDG_CFR", "field": "WDGTB", "op": "write", "value": value,
            "requested": requested}


def test_a_constant_at_the_field_position_is_accepted():
    assert RC.requested_problem(_e("0x2", "0x5000"), 3, 11) is None  # LL_WWDG_SetPrescaler(0x5000) -> WDGTB 010


def test_right_aligned_truncation_still_holds_and_wrong_values_are_refused():
    assert RC.requested_problem(_e("0x234", "0x1234"), 12, 0) is None  # CAPA-120 truncating write unchanged
    assert RC.requested_problem(_e("0x0", "0x5000"), 3, 11) is None  # the low-bits reading stays valid
    msg = RC.requested_problem(_e("0x4", "0x5000"), 3, 11)
    assert msg and "0x0" in msg and "0x2" in msg and "bits 13:11" in msg
    assert RC.requested_problem(_e("0x2", "0x5000"), 3, 0) is not None  # a bit-0 field has no positioned reading


def test_a_cross_cutting_requirement_is_never_asked_to_name_a_register_field():
    assert "must NOT name a register field" in Q.CROSSCUT_CONVENTION
