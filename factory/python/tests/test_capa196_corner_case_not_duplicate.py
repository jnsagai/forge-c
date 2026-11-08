"""CAPA-196 (WO-F014-SWE1-GPIOL-20261107-L40F): the SWE.1 author could never converge. AR-7 demands a corner case for
a valued field write ("an effect with requested and the field value"); the author wrote it as requested 0x5 -> 0x1, and
the cross-task consistency rule "same write, other words" then flagged it as a duplicate of the in-range 0x1 write and
asked to remove it, which AR-7 demanded again (LRTX_REPAIR_STUCK; the assembly was never written)."""
from forge_factory.lrtx import swe1 as S

# the two requirements of WO-F014-SWE1-GPIOL-20261107-L40F, task requirements:GPIO_OSPEEDR_3 (statements shortened)
MEDIUM = {"key": "set_pin_speed_medium",
          "statement": "When LL_GPIO_SetPinSpeed is called with LL_GPIO_PIN_9 and LL_GPIO_SPEED_FREQ_MEDIUM, the driver "
                       "shall write the value 0x01 to GPIO_OSPEEDR.OSPEED9.",
          "effects": [{"case": "MEDIUM", "field": "OSPEED9", "op": "write", "register": "GPIO_OSPEEDR", "value": "0x1"}]}
OUT_OF_DOMAIN = {"key": "set_pin_speed_medium_out_of_domain",
                 "statement": "When LL_GPIO_SetPinSpeed is called with LL_GPIO_PIN_9 and a Speed value outside the 2-bit "
                              "domain such as 0x5, the driver shall write the masked value 0x1 to GPIO_OSPEEDR.OSPEED9.",
                 "effects": [{"case": "OUT_OF_DOMAIN", "field": "OSPEED9", "op": "write", "register": "GPIO_OSPEEDR",
                              "requested": "0x5", "value": "0x1"}]}
CROSS = {"task": "requirements:CROSS", "doc": {"requirements": []}}


def _rec(task, *reqs):
    return {"task": task, "doc": {"requirements": list(reqs)}}


def test_reproducer_and_prevention_the_ar7_corner_case_is_not_a_duplicate():
    got = S.consistency([({}, _rec("requirements:GPIO_OSPEEDR_3", MEDIUM, OUT_OF_DOMAIN))], CROSS)
    assert got == []  # before CAPA-196: "[set_pin_speed_medium_out_of_domain] duplicates [set_pin_speed_medium] ..."


def test_a_plain_duplicate_write_is_still_flagged():
    twin = {**MEDIUM, "key": "set_pin_speed_medium_again",
            "statement": "Calling LL_GPIO_SetPinSpeed with pin 9 and medium speed shall set OSPEED9 to 0x1."}
    got = S.consistency([({}, _rec("requirements:GPIO_OSPEEDR_3", MEDIUM, twin))], CROSS)
    assert len(got) == 1 and "duplicates [set_pin_speed_medium]" in got[0][1] and "both write 0x1" in got[0][1]


def test_an_identical_statement_is_still_a_duplicate_even_with_requested():
    copy = {**OUT_OF_DOMAIN, "key": "copy_of_out_of_domain"}
    got = S.consistency([({}, _rec("requirements:GPIO_OSPEEDR_3", OUT_OF_DOMAIN, copy))], CROSS)
    assert len(got) == 1 and "duplicates [set_pin_speed_medium_out_of_domain]" in got[0][1]


def test_contradictory_set_and_clear_are_still_found():
    a = {"key": "a", "statement": "A sets BIT.", "effects": [{"case": "X", "field": "F", "op": "set", "register": "R", "value": None}]}
    b = {"key": "b", "statement": "B clears BIT.", "effects": [{"case": "X", "field": "F", "op": "clear", "register": "R", "value": None}]}
    got = S.consistency([({}, _rec("requirements:R", a, b))], CROSS)
    assert any("contradictory ops set and clear" in f for _t, f in got)
