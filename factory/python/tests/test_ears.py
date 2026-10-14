"""SWE1-07: deterministic EARS conformance (user clarification 2026-10-14)."""
import pytest
from forge_factory.inspection.ears import check_document, classify


@pytest.mark.parametrize("text,pattern", [
    ("The RCC driver shall reject a null configuration pointer.", "UBIQUITOUS"),
    ("When the PLL lock flag is not set within 100 us, the RCC driver shall return FORGE_RCC_TIMEOUT.", "EVENT"),
    ("While the clock tree is locked, the RCC driver shall reject frequency change requests.", "STATE"),
    ("Where the LSE oscillator is fitted, the RCC driver shall provide an LSE enable API.", "OPTIONAL"),
    ("If a register read-back mismatch is detected, then the RCC driver shall enter the safe state.", "UNWANTED"),
    ("While in low-power mode, when a wake-up event occurs, the RCC driver shall restore the HSI clock.", "COMPLEX"),
    ("Where the PLL is fitted, while the clock is unlocked, if the lock times out, then the RCC driver shall "
     "report FORGE_RCC_TIMEOUT.", "COMPLEX"),
])
def test_ears_patterns_recognised(text, pattern):
    assert classify(text) == pattern
    doc = f"- **SWR-001** {text}\n"
    r = check_document(doc, {"RCC driver"})
    assert r["verdict"] == "PASS", r


@pytest.mark.parametrize("text,finding", [
    ("The driver should be fast.", "EARS_NO_SHALL"),
    ("The RCC driver shall enable the PLL and shall configure the bus.", "EARS_NOT_ATOMIC_2_SHALL"),
    ("Clock configuration shall be validated by the RCC driver.", "EARS_PATTERN_NONCONFORMANT"),
    ("On reset the RCC driver shall clear flags.", "EARS_PATTERN_NONCONFORMANT"),
])
def test_nonconformant_requirements_fail(text, finding):
    r = check_document(f"| SWR-010 | {text} | functional |\n")
    assert r["verdict"] == "FAIL"
    assert any(finding in f for f in r["major_findings"])


def test_minor_findings_do_not_hide_but_do_not_block():
    r = check_document("- **SWR-002** The RCC driver shall configure clocks efficiently\n")
    assert r["verdict"] == "PASS"
    assert any("VAGUE" in f for f in r["minor_findings"]) and any("TERMINATOR" in f for f in r["minor_findings"])


def test_duplicate_ids_and_empty_document_fail():
    dup = "- **SWR-001** The RCC driver shall a.\n- **SWR-001** The RCC driver shall b.\n"
    assert "SWR-001:DUPLICATE_ID" in check_document(dup)["major_findings"]
    assert check_document("no requirements")["major_findings"] == ["SWE1:NO_REQUIREMENTS_FOUND"]


def test_unknown_system_name_flagged():
    r = check_document("- **SWR-003** The GPIO driver shall toggle.\n", {"RCC driver"})
    assert "SWR-003:EARS_UNKNOWN_SYSTEM_NAME" in r["major_findings"]
