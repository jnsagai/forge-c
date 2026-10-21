"""Feature 010 P2: structured SWE.2 for the local profile (LRTX-T014/T015) with a scripted model, on top of the
structured SWE.1 (frozen by the unchanged gate). The rendered architecture must pass the unchanged SWE.2 author gate."""
from __future__ import annotations

import io
import json
import sys

import pytest
from forge_factory.lrtx import structured as S
from forge_factory.lrtx import swe1, swe2
from test_lrtx_swe1 import ANSWERS, _scripted, pytestmark, ws  # noqa: F401 - fixture and owner-input precondition


def _fn(name, returns="void", params=(), op="writes the key", fields=("IWDG_KR.KEY",)):
    return {"name": name, "returns": returns, "params": [{"name": p, "type": "uint32_t"} for p in params],
            "operation": op, "fields": list(fields)}


IFACE = {"functions": [
    _fn("LL_IWDG_Enable"), _fn("LL_IWDG_ReloadCounter"), _fn("LL_IWDG_EnableWriteAccess"),
    _fn("LL_IWDG_DisableWriteAccess"),
    _fn("LL_IWDG_SetPrescaler", params=("prescaler",), op="masked RMW of PR", fields=("IWDG_PR.PR",)),
    _fn("LL_IWDG_SetReloadCounter", params=("counter",), op="masked RMW of RLR", fields=("IWDG_RLR.RL",)),
    _fn("LL_IWDG_IsActive", "uint32_t", op="reads IWDG_SR.ONF", fields=("IWDG_SR.ONF",)),
    _fn("LL_IWDG_IsActiveFlag_PVU", "uint32_t", op="reads IWDG_SR.PVU", fields=("IWDG_SR.PVU",)),
    _fn("LL_IWDG_IsActiveFlag_RVU", "uint32_t", op="reads IWDG_SR.RVU", fields=("IWDG_SR.RVU",))],
    "allocation": [{"swr": s, "functions": [f], "responsibility": "implements the requirement"} for s, f in (
        ("SWR-001", "LL_IWDG_Enable"), ("SWR-002", "LL_IWDG_ReloadCounter"), ("SWR-003", "LL_IWDG_EnableWriteAccess"),
        ("SWR-004", "LL_IWDG_DisableWriteAccess"), ("SWR-005", "LL_IWDG_SetPrescaler"),
        ("SWR-006", "LL_IWDG_SetReloadCounter"), ("SWR-007", "LL_IWDG_IsActive"), ("SWR-008", "LL_IWDG_IsActiveFlag_PVU"),
        ("SWR-009", "LL_IWDG_IsActiveFlag_RVU"))],
    "calls": [{"case": c, "function": f, "args": a} for c, f, a in (
        ("START", "LL_IWDG_Enable", []), ("REFRESH", "LL_IWDG_ReloadCounter", []),
        ("UNLOCK", "LL_IWDG_EnableWriteAccess", []), ("LOCK", "LL_IWDG_DisableWriteAccess", []),
        ("SET_PRESCALER", "LL_IWDG_SetPrescaler", ["5U"]), ("SET_RELOAD", "LL_IWDG_SetReloadCounter", ["0xFFFU"]),
        ("ONF_SET", "LL_IWDG_IsActive", []), ("PVU_SET", "LL_IWDG_IsActiveFlag_PVU", []),
        ("RVU_SET", "LL_IWDG_IsActiveFlag_RVU", []))]}
TXT = ("The single developed component SWC_LL owns only stateless register operations; the caller owns sequencing, "
       "polling bounds and integration of the register block.")
DESIGN = {"components": TXT,
          "register_access": "Volatile accesses through the register-block array; IWDG_KR takes whole-register writes, "
                             "PR and RLR use a masked read-modify-write that preserves other bits; clocks and reset belong "
                             "to the integration.",
          "timing_and_error_handling": "No waiting and no error codes at LL level; every function is one register "
                                       "operation and callers bound their own polling loops.",
          "memory_and_stack": "Flash at most 4096 B, static RAM 64 B budget with 0 B used (no state), stack at most 128 "
                              "B per call: only automatic uint32_t temporaries.",
          "concurrency_and_reentrancy": "The LL is reentrant (no state); a read-modify-write is not atomic, so callers "
                                        "serialise access and never call it from an ISR concurrently with the same "
                                        "register.",
          "safety_and_dependencies": "The LL provides no safety mechanism or degraded state of its own; it depends on the "
                                     "caller for refresh scheduling and on the integration for the register mapping.",
          "decisions": ["Header-only static inline LL without state."],
          "sequences": [{"title": "Configure and start", "steps": [
              {"function": "LL_IWDG_EnableWriteAccess", "repeat_until": "", "note": ""},
              {"function": "LL_IWDG_SetPrescaler", "repeat_until": "", "note": ""},
              {"function": "LL_IWDG_IsActiveFlag_PVU", "repeat_until": "PVU is 0", "note": "caller bounds the loop"},
              {"function": "LL_IWDG_Enable", "repeat_until": "", "note": ""}]}]}


def _gate(ws_, phase, monkeypatch):
    from forge_factory.inspection import gate

    monkeypatch.setattr(sys, "stdin", io.StringIO((ws_ / f".forge-run/lrtx/{phase}/reply.json").read_text()))
    return gate.main(["--workspace", str(ws_), "--phase", phase, "--step", "author"])


@pytest.fixture()
def ws1(ws, monkeypatch):  # noqa: F811
    monkeypatch.setattr(S, "call", _scripted(ANSWERS, []))
    assert swe1.visit(ws, "m")["status"] == "PASS" and _gate(ws, "SWE.1", monkeypatch) == 0
    return ws


def test_swe2_renders_an_architecture_the_unchanged_gate_freezes(ws1, monkeypatch):
    calls = []
    monkeypatch.setattr(S, "call", _scripted({"interfaces": IFACE, "design": DESIGN}, calls))
    rep = swe2.visit(ws1, "m")
    assert rep["status"] == "PASS", rep
    md = (ws1 / swe2.ARCH).read_text()
    assert "| SWR-011 | all LL functions (component-level constraint of SWC_LL" in md  # flash budget, no new function
    assert "| IWDG_PR | 0x04 | 3:0 (PR) |" in md
    st = (ws1 / swe2.STATIC).read_text()
    assert st.count("<<SWC>>") == 1 and "Allocated: SWR-001, SWR-002" in st and "SWR-013" in st
    assert "loop caller-bounded, until PVU is 0" in (ws1 / swe2.DYNAMIC).read_text()
    assert json.loads((ws1 / swe2.CALLS).read_text())["calls"]["SET_PRESCALER"]["args"] == ["5U"]
    assert _gate(ws1, "SWE.2", monkeypatch) == 0
    assert [p["task"] for p in calls] == ["interfaces", "design"]


def test_component_level_requirement_needs_no_function_and_unallocated_swr_is_repaired(ws1, monkeypatch):
    bad = json.loads(json.dumps(IFACE))
    bad["allocation"] = bad["allocation"][:-1]  # SWR-009 missing
    calls = []

    def iface(p):
        return IFACE if p["findings"] else bad
    monkeypatch.setattr(S, "call", _scripted({"interfaces": iface, "design": DESIGN}, calls))
    assert swe2.visit(ws1, "m")["status"] == "PASS"
    second = [p for p in calls if p["task"] == "interfaces"][1]
    assert "SWR-009 is not allocated" in second["findings"] and "function LL_IWDG_IsActiveFlag_RVU is not allocated to any " \
        "requirement" in second["findings"]
    assert not any("SWR-011" in f for f in second["findings"])  # component-level: not asked of the interface task


def test_wrong_write_argument_and_compliance_claim_are_findings(ws1):
    from forge_factory.assurance.hardware import index

    idx = index(ws1 / "inputs/sections/RM0486")
    wrong = json.loads(json.dumps(IFACE))
    wrong["calls"][4]["args"] = ["7U"]
    assert "case SET_PRESCALER: the argument must be the case value 0x5" in swe2.validate_interfaces(ws1, wrong, idx)
    claim = {**DESIGN, "safety_and_dependencies": DESIGN["safety_and_dependencies"] + " The LL is ISO 26262 compliant."}
    assert any("no compliance" in f for f in swe2.validate_design(ws1, claim, IFACE))
    nopoll = json.loads(json.dumps(DESIGN))
    nopoll["sequences"][0]["steps"][2]["repeat_until"] = ""
    assert any("polling loop" in f for f in swe2.validate_design(ws1, nopoll, IFACE))
