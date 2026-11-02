"""Owner change 2026-11-02 ("Build all four"; "Allow access logging"): the SWE.1 author packets carry the author contract
rules AR-1..AR-6 from the cloud cross-inspection of local SWE.1 baselines (classes X5-X11), in generic wording, and a
prohibition requirement is verified by the simulation's register-access log (X12) instead of "never a count of register
accesses". Packets of other phases are unchanged."""
from __future__ import annotations

import re

from forge_factory.lrtx import structured as S
from forge_factory.lrtx import swe1, swe2
from test_lrtx_swe1 import ANSWERS, _scripted, pytestmark, ws  # noqa: F401 - fixture and owner-input precondition
from test_lrtx_swe2 import _gate

RULE_IDS = ("AR-1", "AR-2", "AR-3", "AR-4", "AR-5", "AR-6")
# generic wording: no register, field, function, peripheral or vendor identifier in any rule text
SPECIFIC = re.compile(r"\b[A-Z]{2,}_[A-Z0-9_]+\b|\bLL_\w+|\bHAL_\w+|\bRM\d{4}\b|\b(?:IWDG|RCC|CRC|GPIO|SPI|USART|TIM|"
                      r"STM32\w*|ST)\b")
ALL_RULES = (swe1.AR_DOMAIN, swe1.AR_ENABLING, swe1.AR_DISCRIMINATING, swe1.AR_OBLIGATIONS, swe1.AR_OBLIGATION_GAPS,
             swe1.AR_PRESERVATION, swe1.AR_PAGE, swe1.PROHIBITION_RULE)


def test_rule_texts_are_generic():
    for text in ALL_RULES:
        assert not SPECIFIC.search(text), text
    assert "register-access log" in swe1.PROHIBITION_RULE and "never by final register contents alone" in \
        swe1.PROHIBITION_RULE


def test_register_task_packet_carries_ar1_ar2_ar3_ar6_and_the_access_log_rule(ws):  # noqa: F811
    inv = swe1.inventory(ws)
    p = swe1.group_packet(ws, swe1.groups(inv)[0], "m")
    instr = p["instructions"]
    for rule in (swe1.AR_DOMAIN, swe1.AR_ENABLING, swe1.AR_DISCRIMINATING, swe1.AR_PAGE, swe1.PROHIBITION_RULE):
        assert rule in instr
    assert swe1.AR_PRESERVATION not in instr  # the all-function rule belongs to the cross-cutting task
    assert "never a count of register accesses" not in instr
    assert p["accounting"]["fits"] and p["accounting"]["estimated_prompt_tokens"] < 6000


def test_crosscut_packet_carries_ar3_ar5_ar6_and_the_access_log_rule(ws):  # noqa: F811
    p = swe1.crosscut_packet(ws, [{"key": "k", "statement": "The IWDG LL driver shall do x."}], "m")
    instr = p["instructions"]
    for rule in (swe1.AR_DISCRIMINATING, swe1.AR_PRESERVATION, swe1.AR_PAGE, swe1.PROHIBITION_RULE):
        assert rule in instr
    assert "a write changes only the named bits" not in instr  # X10: the example no longer induces 'one field'
    assert "changes only the fields its requirement names, except the side effects the source documents" in instr
    assert p["accounting"]["fits"]


def test_owner_obligation_rule_carries_ar4():
    obl = {"_path": "inputs/owner-obligations.json", "obligations": [
        {"id": "OBL-a", "critical": True, "effects": []}, {"id": "OBL-b", "critical": False, "effects": []}]}
    reg, cross = swe1.obligation_rule(obl, False), swe1.obligation_rule(obl, True)
    assert swe1.AR_OBLIGATIONS in reg and swe1.AR_OBLIGATIONS in cross
    assert swe1.AR_OBLIGATION_GAPS not in reg  # register tasks have no obligation_gaps field
    assert swe1.AR_OBLIGATION_GAPS in cross and "Critical obligations always need an implementing requirement" in cross


def test_swe2_packets_are_unchanged_by_the_swe1_rules(ws, monkeypatch):  # noqa: F811
    monkeypatch.setattr(S, "call", _scripted(ANSWERS, []))
    assert swe1.visit(ws, "m")["status"] == "PASS" and _gate(ws, "SWE.1", monkeypatch) == 0
    before = swe2.interfaces_packet(ws, "m")
    text = before["instructions"] + "".join(m["content"] for m in before["_messages"])
    assert not any(r in text for r in RULE_IDS) and "register-access log" not in text
    for name in ("AR_DOMAIN", "AR_ENABLING", "AR_DISCRIMINATING", "AR_OBLIGATIONS", "AR_OBLIGATION_GAPS",
                 "AR_PRESERVATION", "AR_PAGE", "PROHIBITION_RULE", "REGISTER_RULES", "CROSSCUT_RULES"):
        monkeypatch.setattr(swe1, name, "changed")
    assert swe2.interfaces_packet(ws, "m")["input_hash"] == before["input_hash"]


def test_a_prohibition_requirement_is_routed_to_the_target_access_log(tmp_path, monkeypatch):
    """Owner 2026-11-02 (X12): only the target simulation logs register accesses (the host fake keeps no access log), so
    an access-prohibiting requirement verified by a host unit test is a finding for the author."""
    from forge_factory import layer

    monkeypatch.setattr(layer, "profile", lambda _ws=None: {"register_prefix": "CRC", "rm": {"doc": "RM0486"}})
    monkeypatch.setattr(swe1, "_manifest", lambda _ws: {"scope": ["CRC_CR.REV_OUT output reversal."]})

    def check(statement, by):
        doc = {"requirements": [{"key": "no_access", "statement": statement, "source_page": 1,
                                 "verification": "Test passes when the register-access log shows no access.",
                                 "verified_by": by, "effects": []}], "not_covered": [], "open_points": []}
        g = {"id": "CRC_CR", "register": "CRC_CR", "section": "1.1", "pages": [],
             "fields": {"REV_OUT": {"msb": 8, "lsb": 7, "access": ["rw"]}}}
        return [f for f in swe1.validate_group(tmp_path, doc, g, "CRC LL driver", {}) if "prohibits" in f]

    for st in ("When a query function is called, the CRC LL driver shall not write any register.",
               "The CRC LL driver shall never access a register outside its scoped functions.",
               "When an out-of-domain value is passed, the CRC LL driver shall perform no register write.",
               "When the status is queried, the CRC LL driver shall not read or write CRC_DR."):
        assert len(check(st, "host_unit_test")) == 1, st
        assert check(st, "target_robot_test") == [], st
    for st in ("When the status is queried, the CRC LL driver shall not wait for the flag to change.",
               "When a field is written, the CRC LL driver shall not modify the other fields of the register."):
        assert check(st, "host_unit_test") == [], st
    # the startup invariant keeps its own (unchanged) rules, not a second finding
    assert check("While no LL function has been called after reset, the CRC LL driver shall not write any CRC "
                 "register.", "host_unit_test") == []
    assert "target_robot_test" in swe1.PROHIBITION_RULE and "host_unit_test" in swe1.PROHIBITION_RULE
