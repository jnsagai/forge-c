"""T023: deterministic requirement-quality rules (research R4). Each rule has a passing and a failing case."""
from __future__ import annotations

import pytest

from forge_hi import quality
from hi_helpers import SYS_ITEMS, make_project, req


def codes(items, stage="sys-req", **kw):
    return sorted({i["code"] for i in quality.check_items(items, stage=stage, **kw)})


GOOD = req("SYS-SUP-010", "The supervisor shall enter the safe state within 50 ms after a fault is detected.",
           ["STK-SUP-001"])


def test_good_item_passes():
    assert codes([GOOD]) == []


def test_duplicate_id():
    assert "IQ-12.duplicate-id" in codes([GOOD, dict(GOOD)])
    assert "IQ-12.duplicate-id" in codes([GOOD], other_ids={"SYS-SUP-010"})
    assert "IQ-12.duplicate-id" not in codes([GOOD], other_ids={"SYS-SUP-099"})


def test_id_format_and_prefix():
    assert "IQ-12.id-format" in codes([dict(GOOD, id="SYS-1")])
    assert "IQ-12.id-prefix" in codes([dict(GOOD, id="SWR-SUP-010")], stage="sys-req")
    assert codes([dict(GOOD, id="DRV-IWDG-001")], stage="sw-req") == []


@pytest.mark.parametrize("text,code", [
    ("The supervisor enters the safe state within 50 ms after a fault.", "IQ-11.shall-missing"),
    ("The supervisor shall enter the safe state and shall report the fault within 50 ms.", "IQ-11.shall-multiple"),
])
def test_shall_count(text, code):
    assert code in codes([dict(GOOD, text=text)])


@pytest.mark.parametrize("term", ["quickly", "as appropriate", "periodically", "TBD", "should", "and/or", "etc"])
def test_each_banned_term_is_flagged(term):
    text = f"The supervisor shall enter the safe state {term} after a fault is detected."
    assert "IQ-03.ambiguous-term" in codes([dict(GOOD, text=text)])


def test_banned_term_list_is_complete_and_each_entry_fires():
    terms, *_ = quality._lists()
    for t in terms:
        found = quality.ambiguous_terms(f"The unit shall do X {t} here.")
        assert found, t


def test_banned_term_not_matched_inside_words():
    assert quality.ambiguous_terms("The handsome breakfast shall be manifest.") == []


def test_multiple_obligations():
    text = "The supervisor shall enter the safe state within 50 ms and report the fault code."
    assert "IQ-05.multiple-obligations" in codes([dict(GOOD, text=text)])
    one = "The supervisor shall report the fault code and the time stamp within 10 ms."
    assert "IQ-05.multiple-obligations" not in codes([dict(GOOD, text=one)])


def test_missing_verification_method():
    item = {k: v for k, v in GOOD.items() if k != "verification_method"}
    assert "IQ-06.verification-method-missing" in codes([item])
    assert "IQ-06.verification-method-not-allowed" in codes([GOOD], allowed_methods=("analysis",))


def test_missing_source():
    assert "IQ-12.source-missing" in codes([dict(GOOD, sources=[])])


@pytest.mark.parametrize("text,bad", [
    ("The supervisor shall enter the safe state within 50 after a fault.", True),
    ("The supervisor shall enter the safe state within 50 ms after a fault.", False),
    ("The supervisor shall enter the safe state within 50ms after a fault.", False),
    ("The supervisor shall use at most 10 % of the processor time.", False),
    ("The supervisor shall keep the safe state after 3 consecutive faults.", False),
    ("The diagnostic line shall run at 115200 baud.", False),
    ("The supervisor shall keep the timeout below 50.", True),
])
def test_number_without_unit(text, bad):
    assert ("IQ-11.value-without-unit" in codes([dict(GOOD, text=text)])) is bad


def test_ids_and_hex_are_not_numbers():
    assert quality.bare_numbers("Refresh per RM0486 using key 0xAAAA as in SYS-SUP-001.") == []


def test_derived_without_rationale():
    assert "IQ-12.rationale-missing" in codes([dict(GOOD, derived=True)])
    assert "IQ-12.rationale-missing" not in codes([dict(GOOD, derived=True, rationale="Needed by the reset design.")])


def test_heuristic_rules_can_be_waived_with_rationale_only():
    text = "The supervisor shall enter the safe state within 50 ms and report the fault code."
    waived = dict(GOOD, text=text, attributes={"quality_waivers": [
        {"rule": "IQ-05.multiple-obligations", "rationale": "Entering and reporting are one atomic reaction here."}]})
    assert "IQ-05.multiple-obligations" not in codes([waived])
    short = dict(waived, attributes={"quality_waivers": [{"rule": "IQ-05.multiple-obligations", "rationale": "ok"}]})
    assert "IQ-05.multiple-obligations" in codes([short])
    not_waivable = dict(GOOD, sources=[], attributes={"quality_waivers": [
        {"rule": "IQ-12.source-missing", "rationale": "Trying to waive a non-heuristic rule."}]})
    assert "IQ-12.source-missing" in codes([not_waivable])


def test_gate_pass_fail_and_not_run(tmp_project):
    make_project(tmp_project, sys_items=SYS_ITEMS)
    doc = quality.run(tmp_project, "sys-req")
    assert doc["verdict"] == "PASS", doc["issues"]
    assert (tmp_project / "hi/sys-req/gates/quality.json").is_file()
    assert doc["evidence"][0]["path"] == "hi/sys-req/requirements.json"

    make_project(tmp_project, sys_items=[dict(SYS_ITEMS[0], text="The supervisor reacts quickly.")])
    doc = quality.run(tmp_project, "sys-req")
    assert doc["verdict"] == "FAIL"
    assert {"IQ-11.shall-missing", "IQ-03.ambiguous-term"} <= {i["code"] for i in doc["issues"]}

    assert quality.run(tmp_project, "sw-req")["verdict"] == "NOT_RUN"
    assert quality.run(tmp_project, "sys-arch")["verdict"] == "NOT_RUN"


def test_ids_unique_across_stages(tmp_project):
    make_project(tmp_project, sys_items=SYS_ITEMS,
                 swr_items=[req("SWR-SUP-001", "The monitor shall flag the task within 2 cycles.", ["SYS-SUP-001"])])
    assert quality.run(tmp_project, "sw-req")["verdict"] == "PASS"
