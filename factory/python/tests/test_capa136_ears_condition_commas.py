"""CAPA-136 (WO-F014-SWE1-WWDGHAL-20261103-L32): the EARS checker split a condition at its first comma, so a
negative-path requirement listing several invalid arguments, or an event over several operations, was
EARS_PATTERN_NONCONFORMANT with no hint. The condition now ends at the comma before "[then] the <system> shall";
statements the first-comma form matched keep the identical split, and a keyword statement that still has no split gets
an actionable suffix after the unchanged code token."""
import pytest
from forge_factory.inspection.ears import Requirement, check_document, check_statement, classify
from forge_factory.lrtx.swe1 import ears_hint

SYS = {"WWDG driver"}


@pytest.mark.parametrize("text,pattern", [
    ("If the WWDG driver is called with a NULL handle, a prescaler above 7, a window below 0x40, or an early wake-up "
     "selection other than 0 or 1, then the WWDG driver shall return HAL_ERROR without writing any WWDG register.",
     "UNWANTED"),
    ("When the WWDG driver performs activation, configuration or refresh, the WWDG driver shall not wait on a flag.",
     "EVENT"),
    ("While the window, the counter and the prescaler are unchanged, the WWDG driver shall keep the CFR value.",
     "STATE"),
    ("Where the early wake-up, the window or the counter feature is configured, the WWDG driver shall set CFR.",
     "OPTIONAL"),
    ("While the watchdog is enabled, when the counter, the window or the prescaler is written, the WWDG driver shall "
     "write CR before CFR.", "COMPLEX"),
])
def test_conditions_with_commas_are_classified_with_the_system_before_shall(text, pattern):
    r = check_statement(Requirement("SWR-001", text, 0), SYS)
    assert (r.pattern, r.findings) == (pattern, [])


def test_the_first_comma_split_is_kept_when_it_already_matched():
    r = check_statement(Requirement("SWR-002", "When the clock is ready, the WWDG driver shall set A, B and C.", 0),
                        SYS)
    assert (r.pattern, r.findings) == ("EVENT", [])
    assert classify("If the counter is 0x3F, then the WWDG driver shall reset the device.") == "UNWANTED"


def test_a_keyword_statement_without_a_system_shall_split_stays_nonconformant_with_a_hint():
    r = check_statement(Requirement("SWR-003", "If the handle is NULL, a divider above 15 shall be refused.", 0), SYS)
    assert r.pattern is None
    (f,) = [x for x in r.findings if "NONCONFORMANT" in x]
    assert f.startswith("SWR-003:EARS_PATTERN_NONCONFORMANT:expected 'If <condition>, then the WWDG driver shall")
    assert "start with The/When/While/Where/If..then" in ears_hint(f.split(":", 1)[1], "WWDG driver")  # lrtx/swe1
    w = check_statement(Requirement("SWR-004", "When the counter is written, a refresh shall follow.", 0), set())
    assert any(":expected 'When <condition>, the <system> shall" in x for x in w.findings)


def test_a_statement_without_an_ears_keyword_keeps_the_bare_code():
    r = check_statement(Requirement("SWR-005", "Window configuration shall be validated by the WWDG driver.", 0), SYS)
    assert "SWR-005:EARS_PATTERN_NONCONFORMANT" in r.findings


def test_weak_modals_and_the_system_name_check_still_apply_to_comma_conditions():
    md = ("- **SWR-006** When the WWDG driver performs activation, configuration or refresh, the WWDG driver shall "
          "return and may log the event.\n"
          "- **SWR-007** If a NULL handle, a prescaler above 7, or a window below 0x40 is given, then the WWDG driver "
          "then shall return HAL_ERROR.\n")
    rep = check_document(md, SYS)
    assert any("SWR-006:EARS_WEAK_MODAL:may" in f for f in rep["minor_findings"])
    assert "SWR-007:EARS_UNKNOWN_SYSTEM_NAME" in rep["major_findings"] and rep["verdict"] == "FAIL"
