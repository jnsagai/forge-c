"""Feature 010 P4: structured SWE.3 (LL) for the local profile with a scripted model on top of the structured SWE.1/SWE.2
(frozen by the unchanged gates): register map generator, unit code tasks, the real compile/swe3_all/cppcheck tools,
the unit scaffold, the rendered design, then the unchanged SWE.3 author gate."""
from __future__ import annotations

import io
import json
import shutil
import sys

import pytest
from forge_factory.lrtx import structured as S
from forge_factory.lrtx import swe2, swe3
from test_lrtx_swe1 import _scripted, pytestmark, ws  # noqa: F401 - fixture and owner-input precondition
from test_lrtx_swe2 import DESIGN, IFACE, ws1  # noqa: F401 - fixture

TOOLS = all(shutil.which(t) for t in ("gcc", "arm-none-eabi-gcc", "clang", "cppcheck"))


def _doc(n, name, returns, params, body, spec, traces):
    sig = f"static inline {returns} {name}({', '.join('uint32_t ' + p for p in params) or 'void'})"
    code = (f"/**\n * @brief {spec}\n * @unit SWU-LL-{n:02d}\n * @spec USPEC-LL-{n:02d}-01\n */\n{sig}\n{{\n{body}\n}}")
    return {"code": code, "spec_items": [{"id": f"USPEC-LL-{n:02d}-01", "behaviour": f"The unit shall {spec}.",
                                          "traces": traces}]}


def _key(n, name, key, swr):
    return _doc(n, name, "void", [], f"    ll_iwdg_regs[LL_IWDG_KR_OFFSET / 4U] = {key};", f"write {key} to IWDG_KR",
                [swr])


def _set(n, name, p, reg, fld, swr):
    body = (f"    uint32_t reg = ll_iwdg_regs[LL_IWDG_{reg}_OFFSET / 4U];\n    reg &= ~LL_IWDG_{reg}_{fld}_MSK;\n"
            f"    reg |= (({p} << LL_IWDG_{reg}_{fld}_POS) & LL_IWDG_{reg}_{fld}_MSK);\n"
            f"    ll_iwdg_regs[LL_IWDG_{reg}_OFFSET / 4U] = reg;")
    return _doc(n, name, "void", [p], body, f"write {p} to IWDG_{reg}.{fld} preserving other bits", [swr])


def _query(n, name, fld, swr):
    body = ("    uint32_t result = 0U;\n"
            f"    if ((ll_iwdg_regs[LL_IWDG_SR_OFFSET / 4U] & LL_IWDG_SR_{fld}_MSK) != 0U)\n    {{\n"
            "        result = 1U;\n    }\n    return result;")
    return _doc(n, name, "uint32_t", [], body, f"return 1U when IWDG_SR.{fld} is set, else 0U", [swr])


CODE = {"code:SWU-LL-01": _key(1, "LL_IWDG_Enable", "0x0000CCCCU", "SWR-001"),
        "code:SWU-LL-02": _key(2, "LL_IWDG_ReloadCounter", "0x0000AAAAU", "SWR-002"),
        "code:SWU-LL-03": _key(3, "LL_IWDG_EnableWriteAccess", "0x00005555U", "SWR-003"),
        "code:SWU-LL-04": _key(4, "LL_IWDG_DisableWriteAccess", "0x00000000U", "SWR-004"),
        "code:SWU-LL-05": _set(5, "LL_IWDG_SetPrescaler", "prescaler", "PR", "PR", "SWR-005"),
        "code:SWU-LL-06": _set(6, "LL_IWDG_SetReloadCounter", "counter", "RLR", "RL", "SWR-006"),
        "code:SWU-LL-07": _query(7, "LL_IWDG_IsActive", "ONF", "SWR-007"),
        "code:SWU-LL-08": _query(8, "LL_IWDG_IsActiveFlag_PVU", "PVU", "SWR-008"),
        "code:SWU-LL-09": _query(9, "LL_IWDG_IsActiveFlag_RVU", "RVU", "SWR-009")}


def _gate(ws_, phase, monkeypatch):
    from forge_factory.inspection import gate

    monkeypatch.setattr(sys, "stdin", io.StringIO((ws_ / f".forge-run/lrtx/{phase}/reply.json").read_text()))
    return gate.main(["--workspace", str(ws_), "--phase", phase, "--step", "author"])


@pytest.fixture()
def ws2(ws1, monkeypatch):  # noqa: F811
    from forge_factory.inspection import regmap

    monkeypatch.setattr(S, "call", _scripted({"interfaces": IFACE, "design": DESIGN}, []))
    assert swe2.visit(ws1, "m")["status"] == "PASS" and _gate(ws1, "SWE.2", monkeypatch) == 0
    regmap.generate(ws1)
    return ws1


def test_units_follow_the_swe2_interface(ws2):
    us = swe3.units(ws2)
    assert [u["id"] for u in us][:2] == ["SWU-LL-01", "SWU-LL-02"] and us[4]["swrs"] == ["SWR-005"]
    p = swe3.code_packet(ws2, us[4], "m")
    assert p["accounting"]["fits"] and "LL_IWDG_PR_PR_MSK" in p["_messages"][1]["content"]
    assert "LL_IWDG_SR_ONF_MSK" not in p["_messages"][1]["content"]  # only the registers this unit accesses


def test_code_validation_catches_casts_wrong_signature_unknown_defines_and_traces(ws2):
    u = swe3.units(ws2)[4]
    good = CODE["code:SWU-LL-05"]
    assert swe3.validate_code(ws2, good, u) == []
    bad = json.loads(json.dumps(good))
    bad["code"] = bad["code"].replace("uint32_t prescaler", "uint8_t prescaler").replace(
        "ll_iwdg_regs[LL_IWDG_PR_OFFSET / 4U] = reg;", "*(volatile uint32_t *)0x56004804U = reg | LL_IWDG_PR_FOO;")
    bad["spec_items"][0]["traces"] = ["SWR-001"]
    found = " ".join(swe3.validate_code(ws2, bad, u))
    for frag in ("signature must be exactly", "integer-to-pointer cast", "LL_IWDG_PR_FOO is not a generated define",
                 "SWR-001, which is not allocated", "SWR-005 (allocated to LL_IWDG_SetPrescaler) is traced by no"):
        assert frag in found, (frag, found)


@pytest.mark.skipif(not TOOLS, reason="gcc/arm-none-eabi-gcc/clang/cppcheck not installed")
def test_structured_code_and_design_pass_the_unchanged_swe3_gate(ws2, monkeypatch):
    from forge_factory.inspection import unit_scaffold

    calls = []
    monkeypatch.setattr(S, "call", _scripted(CODE, calls))
    rep = swe3.visit_code(ws2, "m")
    assert rep["status"] == "PASS", rep
    hdr = (ws2 / "software/ll/stm32n6xx_ll_iwdg.h").read_text()
    assert hdr.count("static inline") == 9 and hdr.index("LL_IWDG_Enable") < hdr.index("access functions (SWE.3")
    tr = [json.loads(x) for x in (ws2 / "evidence/tool-results.jsonl").read_text().splitlines()]
    assert {(r["op"], r["result"]["status"]) for r in tr} >= {("compile", "PASS"), ("cppcheck", "PASS")}
    assert swe3.visit_code(ws2, "m")["status"] == "PASS" and len(calls) == 9  # reassembly never duplicates
    assert (ws2 / "software/ll/stm32n6xx_ll_iwdg.h").read_text().count("static inline") == 9
    unit_scaffold.scaffold(ws2)
    rep = swe3.visit_design(ws2)
    assert rep["status"] == "PASS", rep
    um = (ws2 / "workproducts/SWE.3/unit_specifications.md").read_text()
    assert "TODO" not in um and "Traces: SWR-001, SWR-010, SWR-011, SWR-012, SWR-013" in um
    assert _gate(ws2, "SWE.3", monkeypatch) == 0
