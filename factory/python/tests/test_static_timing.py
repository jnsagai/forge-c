"""CAPA-121 + owner/coordinator 2026-11-03: the SWE.3 per-call bound of the simulation performance budget.

BOUNDED_STATIC for acyclic code (straight-line or forward branches only), MEASURED_IN_SIMULATION at SWE.3 for every
other function, NOT_BOUNDED only when the measurement is impossible; the author gate renders it on every SWE.3 path."""
from __future__ import annotations

import json
import shutil

import pytest
from forge_factory import static_timing as ST

ARM = all(shutil.which(t) for t in ("arm-none-eabi-gcc", "arm-none-eabi-objdump"))


def _renode() -> bool:
    from forge_factory.mcp.servers import sim

    return sim.renode_bin() is not None


SIM = ARM and _renode()


def _fn(name: str, *lines: str) -> str:
    return f"00000000 <{name}>:\n" + "\n".join(f"   {2 * k:x}:\t{ln}" for k, ln in enumerate(lines)) + "\n\n"


STRAIGHT = _fn("f", "f64c 42cc \tmovw\tr2, #52428\t; 0xcccc", "4b01      \tldr\tr3, [pc, #4]\t; (c <f+0xc>)",
               "601a      \tstr\tr2, [r3, #0]", "4770      \tbx\tlr", "bf00      \tnop", "00000000 \t.word\t0x00000000")


def test_straight_line_function_counts_up_to_the_return_and_skips_padding_and_literal_pool():
    r = ST.analyse(STRAIGHT, ["f"])["f"]
    assert r["static_instructions"] == 4 and r["bound"] == "BOUNDED_STATIC" and r["method"] == "STATIC_STRAIGHT_LINE"
    pop = _fn("g", "b510      \tpush\t{r4, lr}", "6040      \tstr\tr0, [r0, #4]", "bd10      \tpop\t{r4, pc}")
    assert ST.analyse(pop, ["g"])["g"]["static_instructions"] == 3
    it = _fn("h", "2800      \tcmp\tr0, #0", "bf18      \tit\tne", "2001      \tmovne\tr0, #1", "4770      \tbx\tlr")
    assert ST.analyse(it, ["h"])["h"]["static_instructions"] == 4  # conditional execution, no branch


def test_forward_branches_inside_the_function_get_a_sound_static_bound_up_to_the_final_return():
    """(b): each instruction of acyclic code executes at most once; branch targets past an early return count."""
    fwd = _fn("p", "b108      \tcbz\tr0, 8 <p+0x8>", "6801      \tldr\tr1, [r0, #0]", "d001      \tbeq.n\ta <p+0xa>",
              "4088      \tbxeq\tlr", "2000      \tmovs\tr0, #0", "4770      \tbx\tlr", "bf00      \tnop")
    r = ST.analyse(fwd, ["p"])["p"]
    assert r["bound"] == "BOUNDED_STATIC" and r["method"] == "STATIC_FORWARD_BRANCHES" and r["static_instructions"] == 6
    early = _fn("q", "d002      \tbne.n\t6 <q+0x6>", "4770      \tbx\tlr", "bf00      \tnop", "2001      \tmovs\tr0, #1",
                "4770      \tbx\tlr")
    assert ST.analyse(early, ["q"])["q"]["static_instructions"] == 5  # the target after the first return is reachable


@pytest.mark.parametrize(("ins", "why"), [
    ("d1fc      \tbne.n\t0 <x>", "BACKWARD_BRANCH"), ("f7ff fffe \tbl\t0 <y>", "CALL_LOOP_OR_WAIT"),
    ("b108      \tcbz\tr0, 10 <x+0x10>", "BRANCH_OUTSIDE_FUNCTION"), ("f000 c001 \tle\tlr, 0 <x>", "CALL_LOOP_OR_WAIT"),
    ("e8df f000 \ttbb\t[pc, r0]", "CALL_LOOP_OR_WAIT"), ("bf30      \twfi", "CALL_LOOP_OR_WAIT"),
    ("f000 b800 \tb.w\t20 <y>", "BRANCH_OUTSIDE_FUNCTION"), ("4718      \tbx\tr3", "CALL_LOOP_OR_WAIT"),
    ("4687      \tmov\tpc, r0", "CALL_LOOP_OR_WAIT"), ("f850 fb04 \tldr.w\tpc, [r0], #4", "CALL_LOOP_OR_WAIT")])
def test_backward_branch_call_loop_table_wait_or_pc_write_has_no_static_bound(ins, why):
    r = ST.analyse(_fn("x", "6801      \tldr\tr1, [r0, #0]", ins, "4770      \tbx\tlr"), ["x"])["x"]
    assert r["status"] == "NOT_BOUNDED" and r["reason"].startswith("NO_STATIC_BOUND:" + why), r


def test_missing_return_code_after_return_and_missing_symbol_are_not_bounded():
    assert ST.analyse(_fn("x", "6801      \tldr\tr1, [r0, #0]"), ["x"])["x"]["reason"] == "NO_FINAL_RETURN"
    after = _fn("x", "4770      \tbx\tlr", "6801      \tldr\tr1, [r0, #0]")
    assert ST.analyse(after, ["x"])["x"]["reason"].startswith("CODE_AFTER_RETURN")
    assert ST.analyse(STRAIGHT, ["z"])["z"]["reason"] == "SYMBOL_NOT_IN_DISASSEMBLY"
    assert ST.analyse("", ["f"])["f"]["status"] == "NOT_BOUNDED"


HDR = ("#ifndef STM32N6XX_LL_RCC_H\n#define STM32N6XX_LL_RCC_H\n#include <stdint.h>\n"
       "extern volatile uint32_t ll_rcc_regs[1024U];\n"
       "static inline void LL_RCC_HSI_Enable(void)\n{\n    ll_rcc_regs[0U] = 8U;\n}\n{extra}"
       "#endif /* STM32N6XX_LL_RCC_H */\n")
LOOP = "static inline void LL_RCC_HSI_Wait(uint32_t n)\n{\n    while (n-- != 0U) { ll_rcc_regs[1U] = n; }\n}\n"


def _ws(tmp_path, extra="", budget=4, layer="LL", calls=None):
    (tmp_path / ".forge-run").mkdir(parents=True)
    m = {"layer": layer}
    if budget:
        m["simulation_performance"] = {"schema": "forge-c/simulation-performance-budget/1",
                                       "instructions_per_call": budget, "microseconds_per_call": 100,
                                       "performance_mips": 100, "test_source": "software/tests/target/test_performance.c"}
    (tmp_path / ".forge-run/manifest.json").write_text(json.dumps(m))
    (tmp_path / "software/ll").mkdir(parents=True)
    (tmp_path / "software/ll/stm32n6xx_ll_rcc.h").write_text(HDR.replace("{extra}", extra))
    if calls is not None:
        (tmp_path / "workproducts/SWE.2").mkdir(parents=True)
        (tmp_path / "workproducts/SWE.2/api_calls.json").write_text(json.dumps({"schema": "forge-c/api-calls/1",
                                                                              "calls": calls}))
    return tmp_path


WAIT_CALLS = {"HSI_ON": {"function": "LL_RCC_HSI_Enable", "args": []},
              "WAIT_5": {"function": "LL_RCC_HSI_Wait", "args": ["5U"]}}


@pytest.mark.skipif(not ARM, reason="arm-none-eabi toolchain not installed")
def test_bound_compiles_the_measured_wrappers_and_a_loop_without_a_call_contract_is_not_bounded(tmp_path):
    rec = ST.bound(_ws(tmp_path, LOOP))
    fs = rec["functions"]
    assert rec["schema"] == ST.SCHEMA and rec["profile"] == "target-cm55-gcc" and "-Os" in rec["flags"]
    assert fs["LL_RCC_HSI_Enable"]["status"] == "WITHIN_BUDGET" and fs["LL_RCC_HSI_Enable"]["static_instructions"] <= 4
    assert fs["LL_RCC_HSI_Enable"]["virtual_ns_bound"] == fs["LL_RCC_HSI_Enable"]["static_instructions"] * 10
    wait = fs["LL_RCC_HSI_Wait"]
    assert wait["status"] == "NOT_BOUNDED" and wait["static_reason"].startswith("NO_STATIC_BOUND:BACKWARD_BRANCH")
    assert wait["reason"].startswith("MEASUREMENT_") and rec["status"] == "NOT_BOUNDED"
    assert rec["header_sha256"] and rec["object_sha256"] and rec["hardware_wcet"] == "NOT_CLAIMED"
    text = "\n".join(ST.design_section(rec, ["SWR-016"]))
    assert "SWR-016" in text and "| LL_RCC_HSI_Wait | - | - | - | NOT_BOUNDED (MEASUREMENT_" in text
    assert "| LL_RCC_HSI_Enable | static (straight-line) |" in text
    assert ST.EVIDENCE in text and "SWE.6 Renode measurement" in text and "hardware WCET is not claimed" in text


@pytest.mark.skipif(not SIM, reason="arm-none-eabi toolchain or Renode not installed")
def test_a_loop_is_measured_in_the_pinned_simulation_within_and_over_budget(tmp_path):
    """(c): no static bound -> the factory measures the wrapper SWE.6 measures on the SWE.2 call-contract cases."""
    rec = ST.bound(_ws(tmp_path / "in", LOOP, budget=64, calls=WAIT_CALLS))
    wait = rec["functions"]["LL_RCC_HSI_Wait"]
    assert wait["bound"] == "MEASURED_IN_SIMULATION" and wait["status"] == "WITHIN_BUDGET", wait
    assert 4 < wait["measured_instructions"] <= 64 and wait["measured_virtual_ns"] == wait["measured_instructions"] * 10
    assert wait["paths"] == {"nominal": ["WAIT_5"], "timeout": "not exercised: no timeout case in the SWE.2 call contract"}
    assert rec["functions"]["LL_RCC_HSI_Enable"]["bound"] == "BOUNDED_STATIC" and rec["status"] == "WITHIN_BUDGET"
    m = rec["measurement"]
    assert m["simulator"].startswith("Renode 1.17.0") and m["platform_sha256"] and m["model_sha256"]
    assert "no injected interrupts or bus stalls" in m["conditions"] and m["default_elf_sha256"]
    text = "\n".join(ST.design_section(rec, []))
    assert f"| LL_RCC_HSI_Wait | measured in simulation | {wait['measured_instructions']} |" in text
    assert "covers only the paths listed" in text and ST.findings(rec, []) == []
    over = ST.bound(_ws(tmp_path / "over", LOOP, budget=8, calls=WAIT_CALLS))
    out = ST.findings(over, ["SWR-016"])
    assert over["functions"]["LL_RCC_HSI_Wait"]["status"] == "OVER_BUDGET"
    assert [f for f in out if "LL_RCC_HSI_Wait" in f][0].startswith(
        f"STATIC_TIMING_OVER_BUDGET: LL_RCC_HSI_Wait: measured {over['functions']['LL_RCC_HSI_Wait']['measured_instructions']}"
        " instr/")


@pytest.mark.skipif(not ARM, reason="arm-none-eabi toolchain not installed")
def test_renode_unavailable_is_not_bounded_with_the_reason_and_rejects(tmp_path, monkeypatch):
    from forge_factory.mcp.servers import sim

    monkeypatch.setattr(sim, "renode_bin", lambda: None)
    rec = ST.bound(_ws(tmp_path, LOOP, budget=64, calls=WAIT_CALLS))
    wait = rec["functions"]["LL_RCC_HSI_Wait"]
    assert wait == {**wait, "status": "NOT_BOUNDED", "reason": "MEASUREMENT_UNAVAILABLE:RENODE_NOT_INSTALLED"}
    out = ST.findings(rec, [])
    assert len(out) == 1 and out[0].startswith("STATIC_TIMING_NOT_BOUNDED: LL_RCC_HSI_Wait: no bound for the budget 64 ")
    assert "MEASUREMENT_UNAVAILABLE:RENODE_NOT_INSTALLED" in out[0] and "BACKWARD_BRANCH" in out[0]


@pytest.mark.skipif(not ARM, reason="arm-none-eabi toolchain not installed")
def test_over_budget_is_reported_and_orders_without_the_budget_are_unchanged(tmp_path):
    big = ("static inline void LL_RCC_HSI_Set(uint32_t v)\n{\n    ll_rcc_regs[2U] = v;\n    ll_rcc_regs[3U] = v + 1U;\n"
           "    ll_rcc_regs[4U] = v + 2U;\n}\n")
    rec = ST.bound(_ws(tmp_path / "a", big))
    assert rec["functions"]["LL_RCC_HSI_Set"]["status"] == "OVER_BUDGET" and rec["status"] == "OVER_BUDGET"
    assert ST.bound(_ws(tmp_path / "b", budget=0)) is None
    assert ST.bound(_ws(tmp_path / "c", budget=0, layer="HAL")) is None


NATIVE_DD = "# Detailed design\n\nWritten by the native SWE.3 author.\n\n## Resource usage\n\n- measured\n"


@pytest.mark.skipif(not ARM, reason="arm-none-eabi toolchain not installed")
def test_gate_renders_the_bound_into_a_native_design_and_fails_over_budget_with_a_precise_finding(tmp_path):
    """Owner 2026-11-03: the author gate renders the section on any SWE.3 path; over budget is a rework finding."""
    ws = _ws(tmp_path / "ok")
    (ws / ST.DESIGN).parent.mkdir(parents=True)
    (ws / ST.DESIGN).write_text(NATIVE_DD)
    assert ST.gate(ws) == []
    dd = (ws / ST.DESIGN).read_text()
    assert dd.startswith(NATIVE_DD.rstrip("\n")) and dd.count(ST.SECTION) == 1
    assert "| LL_RCC_HSI_Enable | static (straight-line) | 4 | 40 | WITHIN_BUDGET | every path (acyclic code) |" in dd
    rec = json.loads((ws / ST.EVIDENCE).read_text())
    assert ST.gate(ws) == [] and (ws / ST.DESIGN).read_text() == dd and json.loads((ws / ST.EVIDENCE).read_text()) == rec
    old = dd.replace(ST.SECTION, "## Timing bound (static analysis)").replace("WITHIN_BUDGET |", "edited |")
    (ws / ST.DESIGN).write_text(old + "\n## Later section\n\ntext\n")  # an earlier (CAPA-121) section is replaced
    ST.gate(ws)
    again = (ws / ST.DESIGN).read_text()
    assert again.count("## Timing bound") == 1 and "edited |" not in again and again.endswith("## Later section\n\ntext\n")
    big = ("static inline void LL_RCC_HSI_Set(uint32_t v)\n{\n    ll_rcc_regs[2U] = v;\n    ll_rcc_regs[3U] = v + 1U;\n"
           "    ll_rcc_regs[4U] = v + 2U;\n}\n")
    ws = _ws(tmp_path / "big", big)
    out = ST.gate(ws)
    assert len(out) == 1 and out[0].startswith("STATIC_TIMING_OVER_BUDGET: LL_RCC_HSI_Set: static bound ")
    assert "exceeds the budget 4 instr/100 us per call at 100 MIPS" in out[0] and len(out[0].split(" exceeds")[0]) < 80
    assert not (ws / ST.DESIGN).exists() and (ws / ST.EVIDENCE).is_file()  # presence of the design: the presence gate
    loop = ST.gate(_ws(tmp_path / "loop", LOOP))
    assert loop[0].startswith("STATIC_TIMING_NOT_BOUNDED: LL_RCC_HSI_Wait: no bound for the budget 4 instr/")
    assert ST.gate(_ws(tmp_path / "none", budget=0)) == []
    assert not (tmp_path / "none" / ST.EVIDENCE).exists()


HAL_H = ("#ifndef STM32N6XX_HAL_RCC_H\n#define STM32N6XX_HAL_RCC_H\n#include <stdint.h>\nuint32_t HAL_GetTick(void);\n"
         "uint32_t HAL_RCC_Refresh(void);\nuint32_t HAL_RCC_Init(uint32_t timeout);\n#endif\n")
HAL_C = ('#include "stm32n6xx_hal_rcc.h"\nextern volatile uint32_t ll_rcc_regs[1024U];\n'
         "uint32_t HAL_RCC_Refresh(void)\n{\n    ll_rcc_regs[0U] = 0xAAAAU;\n    return 0U;\n}\n"
         "uint32_t HAL_RCC_Init(uint32_t timeout)\n{\n    uint32_t st = 0U;\n    if (timeout == 0U)\n    {\n"
         "        st = 1U;\n    }\n    else\n    {\n        const uint32_t start = HAL_GetTick();\n"
         "        ll_rcc_regs[0U] = 8U;  /* HSION; the model mirrors it to RCC_SR.HSIRDY unless never_ready */\n"
         "        while ((ll_rcc_regs[1U] & 8U) == 0U)\n        {\n"
         "            if ((HAL_GetTick() - start) >= timeout) { st = 3U; break; }\n        }\n    }\n    return st;\n}\n")
HAL_CALLS = {"INIT": {"function": "HAL_RCC_Init", "args": ["{timeout}"]},
             "INIT_ZERO": {"function": "HAL_RCC_Init", "args": ["0U"]},
             "REFRESH": {"function": "HAL_RCC_Refresh", "args": []}}


def _hal(tmp_path, calls=None, budget=2000):
    ws = _ws(tmp_path, budget=budget, layer="HAL", calls=calls)
    (ws / "software/hal").mkdir(parents=True)
    (ws / "software/hal/stm32n6xx_hal_rcc.h").write_text(HAL_H)
    (ws / "software/hal/stm32n6xx_hal_rcc.c").write_text(HAL_C)
    return ws


@pytest.mark.skipif(not ARM, reason="arm-none-eabi toolchain not installed")
def test_hal_order_bounds_acyclic_functions_statically_and_refuses_without_measurement_means(tmp_path):
    rec = ST.bound(_hal(tmp_path))
    fs = rec["functions"]
    assert rec["layer"] == "HAL" and rec["source"] == "software/hal/stm32n6xx_hal_rcc.c" and rec["source_sha256"]
    assert fs["HAL_RCC_Refresh"]["bound"] == "BOUNDED_STATIC" and fs["HAL_RCC_Refresh"]["status"] == "WITHIN_BUDGET"
    init = fs["HAL_RCC_Init"]
    assert init["status"] == "NOT_BOUNDED" and "static_instructions" not in init and "measured_instructions" not in init
    assert init["static_reason"].startswith("NO_STATIC_BOUND:") and init["reason"].startswith("MEASUREMENT_")
    out = [f for f in ST.findings(rec, ["SWR-020"]) if "HAL_RCC_Init" in f]
    assert len(out) == 1 and out[0].startswith("STATIC_TIMING_NOT_BOUNDED: HAL_RCC_Init: no bound for the budget")
    assert "(SWR-020)" in out[0]


def _swr(ws, *lines):
    (ws / "workproducts/SWE.1").mkdir(parents=True, exist_ok=True)
    (ws / "workproducts/SWE.1/software_requirements.md").write_text(
        "# Software requirements\n\n" + "".join(f"- **SWR-{k:03d}** {s}\n" for k, s in enumerate(lines, 1)))


def test_the_maximum_timeout_comes_from_the_frozen_requirements_then_the_scope(tmp_path):
    ws = _hal(tmp_path / "swr")
    _swr(ws, "When HAL_RCC_Init is called, the RCC driver shall wait for HSIRDY with timeout_ms at most "
             "HAL_RCC_TIMEOUT_MS = 20 ms.", "The RCC driver shall use at most 100 microseconds of virtual time.")
    assert ST.max_timeout(ws) == (20, "SWR-001: 'at most HAL_RCC_TIMEOUT_MS = 20 ms'")
    ws = _hal(tmp_path / "scope")
    m = json.loads((ws / ".forge-run/manifest.json").read_text())
    m["scope"] = ["Initialise", "wait bounded in TIME by a caller timeout in milliseconds (at most 48 ms, covering 6 LSI)"]
    (ws / ".forge-run/manifest.json").write_text(json.dumps(m))
    assert ST.max_timeout(ws) == (48, "work-order scope item 2: 'at most 48 ms'")
    ws = _hal(tmp_path / "two")
    _swr(ws, "The timeout shall be at most 20 ms.", "The timeout_ms shall be at most 30 milliseconds.")
    assert ST.max_timeout(ws)[1].startswith("CONFLICTING_MAX_TIMEOUT: 20 (SWR-001")
    assert ST.max_timeout(_hal(tmp_path / "none")) == (None, ST.NO_MAX)


@pytest.mark.skipif(not SIM, reason="arm-none-eabi toolchain or Renode not installed")
def test_hal_wait_is_measured_at_the_maximum_timeout_with_a_disclosed_tick_stub(tmp_path):
    """Coordinator 2026-11-03: the bound covers the worst case the API permits: {timeout} = the stated maximum."""
    ws = _hal(tmp_path / "max", HAL_CALLS)
    _swr(ws, "The RCC driver shall bound the HSIRDY wait by timeout_ms at most HAL_RCC_TIMEOUT_MS = 20 ms.")
    rec = ST.bound(ws)
    init = rec["functions"]["HAL_RCC_Init"]
    assert init["bound"] == "MEASURED_IN_SIMULATION" and init["status"] == "WITHIN_BUDGET", init
    assert init["paths"]["nominal"] == ["INIT", "INIT_ZERO"] and init["measured_instructions"] > 0
    m = rec["measurement"]
    assert m["timeout_argument"].startswith("20U = the maximum the frozen inputs allow (SWR-001") and "10U" in \
        m["timeout_argument"] and m["max_timeout_ticks"] == 20
    assert "factory stub" in m["time_base"] and "20 ms corresponds to 20 ticks" in m["time_base"]
    assert "Timeout argument: 20U" in "\n".join(ST.design_section(rec, []))
    short = _hal(tmp_path / "short", HAL_CALLS)
    _swr(short, "The RCC driver shall bound the HSIRDY wait by timeout_ms at most HAL_RCC_TIMEOUT_MS = 2 ms.")
    assert ST.bound(short)["functions"]["HAL_RCC_Init"]["measured_instructions"] <= init["measured_instructions"]


@pytest.mark.skipif(not SIM, reason="arm-none-eabi toolchain or Renode not installed")
def test_a_timeout_argument_without_a_stated_maximum_is_not_bounded_and_routes_upstream(tmp_path):
    rec = ST.bound(_hal(tmp_path, HAL_CALLS))
    init = rec["functions"]["HAL_RCC_Init"]
    assert init == {**init, "status": "NOT_BOUNDED", "reason": ST.NO_MAX} and rec["status"] == "NOT_BOUNDED"
    assert rec["functions"]["HAL_RCC_Refresh"]["status"] == "WITHIN_BUDGET"
    out = [f for f in ST.findings(rec, []) if "HAL_RCC_Init" in f]
    assert len(out) == 1 and "no maximum timeout argument stated" in out[0]
    assert out[0].endswith("report_defect kind REQUIREMENT (SWE.1) to state the maximum timeout")


TIMEOUT_CALLS = {**HAL_CALLS, "INIT_TIMEOUT": {"function": "HAL_RCC_Init", "args": ["{timeout}"]}}
TIMEOUT_SWR = "If HSIRDY is not set within timeout_ms, HAL_RCC_Init shall return HAL_TIMEOUT, timeout_ms at most 20 ms."


def _timeout_ws(path, budget, swr=True):
    ws = _hal(path, TIMEOUT_CALLS, budget=budget)
    (ws / "workproducts/SWE.1").mkdir(parents=True, exist_ok=True)
    (ws / "workproducts/SWE.1/register_effects.json").write_text(json.dumps(
        {"effects": [{"case": "INIT_TIMEOUT", "swr": "SWR-001", "status": "HAL_TIMEOUT"}]}))
    if swr:
        _swr(ws, TIMEOUT_SWR)
    else:  # the maximum is only in the work-order scope: no requirement bounds the timeout path
        m = json.loads((ws / ".forge-run/manifest.json").read_text())
        m["scope"] = ["the HSI wait is bounded by a caller timeout (at most 20 ms)"]
        (ws / ".forge-run/manifest.json").write_text(json.dumps(m))
    return ws


@pytest.mark.skipif(not SIM, reason="arm-none-eabi toolchain or Renode not installed")
def test_a_timeout_path_over_the_per_call_budget_passes_when_a_timeout_requirement_bounds_it(tmp_path):
    """Coordinator 2026-11-03 (option a): the per-call budget gates the non-timeout paths; a timeout path is bounded in
    real time by its timeout requirement and its simulated CPU cost is recorded, not gated."""
    ws = _timeout_ws(tmp_path, budget=60)
    (ws / ST.DESIGN).parent.mkdir(parents=True, exist_ok=True)
    (ws / ST.DESIGN).write_text("# Detailed design\n")
    rec = ST.bound(ws)
    init = rec["functions"]["HAL_RCC_Init"]
    tp = init["timeout_path"]
    assert init["status"] == "WITHIN_BUDGET" and init["measured_instructions"] <= 60, init
    assert tp["cases"] == ["INIT_TIMEOUT"] and tp["measured_instructions"] > 60  # over the per-call budget, not gated
    assert tp["real_time_bound"] == "<= 20 ms by SWR-001" and tp["cost"].startswith("CPU cost in simulation, not wall")
    assert tp["per_call_budget"].startswith("not gated") and all(s["scenario"] in ("default", "never_ready")
                                                               for s in init["samples"])
    assert rec["status"] == "WITHIN_BUDGET" and ST.gate(ws) == []
    dd = (ws / ST.DESIGN).read_text()
    assert "Budget scope: The per-call budget is gated on every path that does not end in a timeout" in dd
    assert "real time <= 20 ms by SWR-001" in dd and "No hardware WCET and no wall-time compliance" in dd
    assert json.loads((ws / ST.EVIDENCE).read_text())["budget_scope"] == ST.BUDGET_SCOPE


@pytest.mark.skipif(not SIM, reason="arm-none-eabi toolchain or Renode not installed")
def test_a_timeout_path_no_requirement_bounds_is_not_bounded_and_a_non_timeout_overrun_still_fails(tmp_path):
    rec = ST.bound(_timeout_ws(tmp_path / "noreq", budget=60, swr=False))
    init = rec["functions"]["HAL_RCC_Init"]
    assert init["status"] == "NOT_BOUNDED" and init["reason"] == ST.NO_TIMEOUT_REQ
    assert init["timeout_path"]["real_time_bound"] is None
    out = [f for f in ST.findings(rec, []) if "HAL_RCC_Init" in f]
    assert len(out) == 1 and "NO_TIMEOUT_REQUIREMENT" in out[0]
    assert out[0].endswith("report_defect kind REQUIREMENT (SWE.1) to state the maximum timeout")
    tight = ST.bound(_timeout_ws(tmp_path / "tight", budget=5))
    init = tight["functions"]["HAL_RCC_Init"]
    assert init["status"] == "OVER_BUDGET" and init["timeout_path"]["real_time_bound"] == "<= 20 ms by SWR-001"
    over = [f for f in ST.findings(tight, []) if "HAL_RCC_Init" in f]
    assert over[0].startswith(f"STATIC_TIMING_OVER_BUDGET: HAL_RCC_Init: measured {init['measured_instructions']} instr/")
