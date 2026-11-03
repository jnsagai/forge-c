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


def test_revalidation_after_assembly_compiles_changed_candidate_against_current_defines(ws2):
    """A cached VALID record still needs current validation; neither duplicates nor a stale pristine header suffice."""
    import copy

    us = swe3.units(ws2)
    swe3.assemble_code(ws2, [(u, {"doc": CODE["code:" + u["id"]]}) for u in us])
    path = swe3._header(ws2)
    original = path.read_bytes()
    good = copy.deepcopy(CODE["code:SWU-LL-01"])
    assert swe3.validate_code(ws2, good, us[0]) == []
    assert path.read_bytes() == original
    broken = copy.deepcopy(good)
    broken["code"] = broken["code"].replace("= 0x0000CCCCU;", "= ;")
    assert any("compile:" in e for e in swe3.validate_code(ws2, broken, us[0]))
    assert path.read_bytes() == original
    # A changed current define must not be hidden by the pristine pre-assembly snapshot.
    text = path.read_text()
    import re

    changed, count = re.subn(r"(#define LL_IWDG_KR_OFFSET\s+)[^\n]+", r"\g<1>UNKNOWN_CURRENT_OFFSET", text)
    assert count == 1
    path.write_text(changed)
    assert any("compile:" in e for e in swe3.validate_code(ws2, good, us[0]))


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


def test_swe3_inspector_receives_the_frozen_swe2_architecture_and_baseline_records(ws2):
    """CAPA-116 (run WO-F014-CMP-SWE3-OBL-20261102-08): SWE3-01/03 judge the design against the software architecture
    and SWE3-06 the change/trace provenance; the structured inspector receives the frozen SWE.2 baseline it was frozen
    on and both baseline records, never a changed or missing upstream silently."""
    from forge_factory.inspection.engine import Store
    from forge_factory.lrtx import review

    st = Store(ws2)
    bl = st.freeze("SWE.3", "swe3-author")
    up = st.latest_baseline("SWE.2")
    assert bl["upstream"]["SWE.2"] == up["baseline_hash"]
    got, srcs = review.evidence(ws2, "SWE.3")
    texts = {s["path"]: s["text"] for s in srcs}
    assert got == bl
    want = [f for f in up["files"] if not f.endswith((".svg", ".reqif"))]
    assert "workproducts/SWE.2/software_architecture.md" in want
    assert all(texts[f] == (ws2 / f).read_text() for f in want)
    for rec in (f"configuration/baselines/SWE.3/{bl['baseline_id']}.json",
                f"configuration/baselines/SWE.2/{up['baseline_id']}.json"):
        assert json.loads(texts[rec]) == json.loads((ws2 / rec).read_text())
    assert not any(p.startswith("inputs/") for p in texts)  # no instance declaration: no device header
    item = next(c for c in st.applicable(st.checklist("SWE.3"))["checks"] if c["id"] == "SWE3-01")
    assert review.item_packet(ws2, "SWE.3", item, got, srcs, "m")["accounting"]["fits"]
    assert all(review.upstream_sources(ws2, p, bl) == [] for p in ("SWE.1", "SWE.2", "SWE.6"))
    arch = ws2 / "workproducts/SWE.2/software_architecture.md"
    arch.write_text(arch.read_text() + "\nchanged after the freeze\n")
    with pytest.raises(ValueError, match="UPSTREAM_CHANGED:SWE.2"):
        review.evidence(ws2, "SWE.3")
    with pytest.raises(ValueError, match="UPSTREAM_BASELINE_NOT_FOUND:SWE.3:SWE.2"):
        review.upstream_sources(ws2, "SWE.3", {**bl, "upstream": {"SWE.1": bl["upstream"]["SWE.1"]}})


@pytest.mark.skipif(not TOOLS, reason="gcc/arm-none-eabi-gcc/clang/cppcheck not installed")
def test_capa118_baseline_frozen_after_rework_carries_the_reworked_as_built_design(ws2, monkeypatch):
    """CAPA-118 (run WO-F014-CMP-SWE3-IWDG-20261102-08): the as-built design was written once, so the baselines frozen
    after code rework carried the round-1 diagram. The scaffold before each author round re-renders it from the code."""
    from forge_factory.common import sha256_file
    from forge_factory.inspection import unit_scaffold
    from forge_factory.inspection.engine import Store
    from forge_factory.lrtx import visit as V

    def round_(code):
        monkeypatch.setattr(S, "call", _scripted(code, []))
        assert swe3.visit_code(ws2, "m")["status"] == "PASS"
        unit_scaffold.scaffold(ws2)
        assert swe3.visit_design(ws2)["status"] == "PASS"
        assert _gate(ws2, "SWE.3", monkeypatch) == 0
        return Store(ws2).latest_baseline("SWE.3")

    rel = "workproducts/SWE.3/detailed_design/SWU-LL-01.puml"
    old = ":ll_iwdg_regs[LL_IWDG_KR_OFFSET / 4U] = 0x0000CCCCU;"
    first = round_(CODE)
    assert old in (ws2 / rel).read_text()
    V._ckpt(ws2, "SWE.3", "code:SWU-LL-01").unlink()  # rework: the unit's code task is answered again
    body = "    const uint32_t key = 0x0000CCCCU;\n    ll_iwdg_regs[LL_IWDG_KR_OFFSET / 4U] = key;"
    second = round_({**CODE, "code:SWU-LL-01": _doc(1, "LL_IWDG_Enable", "void", [], body, "write 0x0000CCCCU to "
                                                    "IWDG_KR", ["SWR-001"])})
    assert second["baseline_id"] != first["baseline_id"] and second["files"][rel] == sha256_file(ws2 / rel)
    text = (ws2 / rel).read_text()
    assert ":const uint32_t key = 0x0000CCCCU;" in text and ":ll_iwdg_regs[LL_IWDG_KR_OFFSET / 4U] = key;" in text
    assert old not in text
    hdr = (ws2 / "software/ll/stm32n6xx_ll_iwdg.h").read_text()
    want = unit_scaffold._activity("SWU-LL-01", "LL_IWDG_Enable", ["LL_IWDG_Enable"], unit_scaffold._bodies(hdr))
    assert unit_scaffold._generated_form(text) == unit_scaffold._generated_form(want)
    # an author-changed design is kept (the agent line refines the scaffold's design)
    (ws2 / rel).write_text(text.replace("@enduml", "note left: refined by the author\n@enduml"))
    unit_scaffold.scaffold(ws2)
    assert "refined by the author" in (ws2 / rel).read_text()


@pytest.mark.skipif(not TOOLS, reason="gcc/arm-none-eabi-gcc/clang/cppcheck not installed")
def test_capa121_design_carries_the_static_call_bound_of_the_simulation_budget(ws2, monkeypatch):
    """CAPA-121 (runs WO-F014-CMP-SWE3-OBL/IWDG-20261102-09): the rendered design gave flash/RAM/stack but no bound for
    the simulation performance requirements and SWE3-03 failed three times. The factory renders the static per-call
    bound of the measured wrappers (frozen evidence file); orders without the budget are unchanged."""
    from forge_factory import static_timing as ST
    from forge_factory.inspection import unit_scaffold
    from forge_factory.inspection.engine import Store
    from forge_factory.lrtx import review

    monkeypatch.setattr(S, "call", _scripted(CODE, []))
    assert swe3.visit_code(ws2, "m")["status"] == "PASS"
    unit_scaffold.scaffold(ws2)
    assert swe3.visit_design(ws2)["status"] == "PASS"
    assert "## Timing bound" not in (ws2 / "workproducts/SWE.3/detailed_design.md").read_text()
    assert not (ws2 / ST.EVIDENCE).exists()
    mp = ws2 / ".forge-run/manifest.json"
    m = json.loads(mp.read_text())
    m["simulation_performance"] = {"schema": "forge-c/simulation-performance-budget/1", "instructions_per_call": 64,
                                   "microseconds_per_call": 100, "performance_mips": 100,
                                   "test_source": "software/tests/target/test_performance.c"}
    mp.write_text(json.dumps(m, indent=1))
    assert swe3.visit_design(ws2)["status"] == "PASS"
    dd = (ws2 / "workproducts/SWE.3/detailed_design.md").read_text()
    rec = json.loads((ws2 / ST.EVIDENCE).read_text())
    assert rec["status"] == "WITHIN_BUDGET" and len(rec["functions"]) == 9
    for fn, r in rec["functions"].items():
        assert f"| {fn} | static (straight-line) | {r['static_instructions']} | {r['virtual_ns_bound']} | WITHIN_BUDGET |" in dd
    assert ST.SECTION in dd and "hardware WCET is not claimed" in dd
    assert _gate(ws2, "SWE.3", monkeypatch) == 0
    bl = Store(ws2).latest_baseline("SWE.3")
    assert ST.EVIDENCE in bl["files"]
    got, srcs = review.evidence(ws2, "SWE.3")
    assert json.loads({s["path"]: s["text"] for s in srcs}[ST.EVIDENCE]) == rec
    item = next(c for c in Store(ws2).applicable(Store(ws2).checklist("SWE.3"))["checks"] if c["id"] == "SWE3-03")
    assert review.item_packet(ws2, "SWE.3", item, got, srcs, "m")["accounting"]["fits"]


@pytest.mark.skipif(not TOOLS, reason="gcc/arm-none-eabi-gcc/clang/cppcheck not installed")
def test_owner_timing_gate_rejects_over_budget_and_renders_the_bound_on_the_native_path(ws2, monkeypatch):
    """Owner 2026-11-03: an over-budget (or unbounded) static timing result fails the SWE.3 design/author gate with a
    finding naming the function, the count and the budget, routed to that unit's code rework; the native SWE.3 path (a
    design the author wrote) gets the same factory-rendered bound at the author gate."""
    from forge_factory import static_timing as ST
    from forge_factory.inspection import unit_scaffold
    from forge_factory.inspection.engine import Store
    from forge_factory.lrtx import visit as V

    monkeypatch.setattr(S, "call", _scripted(CODE, []))
    assert swe3.visit_code(ws2, "m")["status"] == "PASS"
    unit_scaffold.scaffold(ws2)
    mp = ws2 / ".forge-run/manifest.json"

    def budget(n):
        m = json.loads(mp.read_text())
        m["simulation_performance"] = {"schema": "forge-c/simulation-performance-budget/1", "instructions_per_call": n,
                                       "microseconds_per_call": 100, "performance_mips": 100,
                                       "test_source": "software/tests/target/test_performance.c"}
        mp.write_text(json.dumps(m, indent=1))

    budget(3)
    rep = swe3.visit_design(ws2)
    assert rep["status"] == "FAILED"
    enable = next(i for i in rep["issues"] if "LL_IWDG_Enable:" in i)
    assert enable.startswith("STATIC_TIMING_OVER_BUDGET: LL_IWDG_Enable: static bound 4 instr/40 ns exceeds the budget "
                             "3 instr/100 us per call")  # function, count and budget within the compact reply
    assert V.full_issue(ws2, "SWE.3", enable).endswith("reduce the code of LL_IWDG_Enable")
    assert _gate(ws2, "SWE.3", monkeypatch) != 0 and Store(ws2).latest_baseline("SWE.3") is None
    found = V.rework_findings(ws2, "SWE.3", "")
    assert any(f.startswith("STATIC_TIMING_OVER_BUDGET: LL_IWDG_Enable:") for f in found)
    assert any("LL_IWDG_Enable:" in f for f in swe3._route(found, swe3.units(ws2))["code:SWU-LL-01"])
    budget(64)  # native path: the author wrote the design; the author gate renders the bound and freezes it
    dd = ws2 / ST.DESIGN
    dd.write_text("# Detailed design\n\nNative SWE.3 author design of the IWDG LL.\n")
    (ws2 / ST.EVIDENCE).unlink()
    V.reply(ws2, "SWE.3", "PASS", [])  # the native author's PASS answer the gate reads
    assert _gate(ws2, "SWE.3", monkeypatch) == 0
    text = dd.read_text()
    assert text.startswith("# Detailed design\n\nNative SWE.3 author design") and text.count(ST.SECTION) == 1
    assert "| LL_IWDG_Enable | static (straight-line) | 4 | 40 | WITHIN_BUDGET |" in text
    bl = Store(ws2).latest_baseline("SWE.3")
    assert {ST.EVIDENCE, ST.DESIGN} <= set(bl["files"])
