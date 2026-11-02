"""CAPA-121: the SWE.3 static per-call bound of the simulation performance budget (straight-line LL code only)."""
from __future__ import annotations

import json
import shutil

import pytest
from forge_factory import static_timing as ST

ARM = all(shutil.which(t) for t in ("arm-none-eabi-gcc", "arm-none-eabi-objdump"))


def _fn(name: str, *lines: str) -> str:
    return f"00000000 <{name}>:\n" + "\n".join(f"   {2 * k:x}:\t{ln}" for k, ln in enumerate(lines)) + "\n\n"


STRAIGHT = _fn("f", "f64c 42cc \tmovw\tr2, #52428\t; 0xcccc", "4b01      \tldr\tr3, [pc, #4]\t; (c <f+0xc>)",
               "601a      \tstr\tr2, [r3, #0]", "4770      \tbx\tlr", "bf00      \tnop", "00000000 \t.word\t0x00000000")


def test_straight_line_function_counts_up_to_the_return_and_skips_padding_and_literal_pool():
    assert ST.analyse(STRAIGHT, ["f"])["f"]["static_instructions"] == 4
    pop = _fn("g", "b510      \tpush\t{r4, lr}", "6040      \tstr\tr0, [r0, #4]", "bd10      \tpop\t{r4, pc}")
    assert ST.analyse(pop, ["g"])["g"]["static_instructions"] == 3
    it = _fn("h", "2800      \tcmp\tr0, #0", "bf18      \tit\tne", "2001      \tmovne\tr0, #1", "4770      \tbx\tlr")
    assert ST.analyse(it, ["h"])["h"]["static_instructions"] == 4  # conditional execution, no branch


@pytest.mark.parametrize("ins", ["d1fc      \tbne.n\t0 <x>", "f7ff fffe \tbl\t0 <y>", "b108      \tcbz\tr0, 6 <x+0x6>",
                                 "f000 c001 \tle\tlr, 0 <x>", "e8df f000 \ttbb\t[pc, r0]", "bf30      \twfi",
                                 "f000 b800 \tb.w\t0 <y>", "4718      \tbx\tr3", "4687      \tmov\tpc, r0",
                                 "f850 fb04 \tldr.w\tpc, [r0], #4", "4088      \tbxeq\tlr"])
def test_any_branch_call_loop_wait_or_pc_write_before_the_return_refuses_a_static_bound(ins):
    r = ST.analyse(_fn("x", "6801      \tldr\tr1, [r0, #0]", ins, "4770      \tbx\tlr"), ["x"])["x"]
    assert r["status"] == "NOT_BOUNDED" and r["reason"].startswith("NOT_STRAIGHT_LINE"), r


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


def _ws(tmp_path, extra="", budget=True, layer="LL"):
    (tmp_path / ".forge-run").mkdir(parents=True)
    m = {"layer": layer}
    if budget:
        m["simulation_performance"] = {"schema": "forge-c/simulation-performance-budget/1", "instructions_per_call": 4,
                                       "microseconds_per_call": 100, "performance_mips": 100,
                                       "test_source": "software/tests/target/test_performance.c"}
    (tmp_path / ".forge-run/manifest.json").write_text(json.dumps(m))
    (tmp_path / "software/ll").mkdir(parents=True)
    (tmp_path / "software/ll/stm32n6xx_ll_rcc.h").write_text(HDR.replace("{extra}", extra))
    return tmp_path


@pytest.mark.skipif(not ARM, reason="arm-none-eabi toolchain not installed")
def test_bound_compiles_the_measured_wrappers_and_refuses_a_loop(tmp_path):
    rec = ST.bound(_ws(tmp_path, LOOP))
    fs = rec["functions"]
    assert rec["schema"] == ST.SCHEMA and rec["profile"] == "target-cm55-gcc" and "-Os" in rec["flags"]
    assert fs["LL_RCC_HSI_Enable"]["status"] == "WITHIN_BUDGET" and fs["LL_RCC_HSI_Enable"]["static_instructions"] <= 4
    assert fs["LL_RCC_HSI_Enable"]["virtual_ns_bound"] == fs["LL_RCC_HSI_Enable"]["static_instructions"] * 10
    assert fs["LL_RCC_HSI_Wait"]["status"] == "NOT_BOUNDED" and rec["status"] == "NOT_BOUNDED"
    assert rec["header_sha256"] and rec["object_sha256"] and rec["hardware_wcet"] == "NOT_CLAIMED"
    text = "\n".join(ST.design_section(rec, ["SWR-016"]))
    assert "SWR-016" in text and "| LL_RCC_HSI_Wait | - | - | NOT_BOUNDED (NOT_STRAIGHT_LINE" in text
    assert ST.EVIDENCE in text and "SWE.6 Renode measurement" in text


@pytest.mark.skipif(not ARM, reason="arm-none-eabi toolchain not installed")
def test_over_budget_is_reported_and_orders_without_the_budget_are_unchanged(tmp_path):
    big = ("static inline void LL_RCC_HSI_Set(uint32_t v)\n{\n    ll_rcc_regs[2U] = v;\n    ll_rcc_regs[3U] = v + 1U;\n"
           "    ll_rcc_regs[4U] = v + 2U;\n}\n")
    rec = ST.bound(_ws(tmp_path / "a", big))
    assert rec["functions"]["LL_RCC_HSI_Set"]["status"] == "OVER_BUDGET" and rec["status"] == "OVER_BUDGET"
    assert ST.bound(_ws(tmp_path / "b", budget=False)) is None
    assert ST.bound(_ws(tmp_path / "c", layer="HAL")) is None
