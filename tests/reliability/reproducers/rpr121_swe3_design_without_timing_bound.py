"""RPR-121 (Fabro runs WO-F014-CMP-SWE3-OBL-20261102-09 and WO-F014-CMP-SWE3-IWDG-20261102-09, cloud comparison line,
loop10, 2026-11-02): CRC IDR 0014i (instance mode) and IWDG LL 0009h, structured SWE.3. Both work orders carry a
simulation performance allocation (SWR "complete each measured call within 64 executed target instructions / 100
microseconds of virtual time in the pinned Renode simulation at 100 MIPS"). The deterministic SWE.3 design renderer
(lrtx/swe3.py visit_design) wrote the flash/RAM/stack tool results but no bound for these requirements, and the author
had no means to add one (the design is factory-rendered; swe3-author has no disassembly or simulation grant). The
inspector failed SWE3-03 ("ISR/concurrency, interrupts, timing and error propagation are bounded") in all three rounds:
BLOCKED STUCK SAME_ITEM_FAILED_3X.

Scenario: the real lrtx.swe3.visit_design on a scratch header-only LL workspace (two straight-line functions) with a
simulation performance budget in its manifest; the structured SWE.2/code checkpoints, the SWE.1 requirement texts and
the MCP tool results are stubbed, the compiler is the real arm-none-eabi-gcc.
Symptom: the rendered SWE.3 work products give no per-function bound of the executed instructions for the scoped
functions."""
import json
import re
import shutil
import sys
from pathlib import Path

SIG = "the SWE.3 detailed design gives no per-call timing bound for the simulation performance budget"
FUNCS = ("LL_RCC_HSI_Enable", "LL_RCC_HSI_IsReady")
LL_H = ("#ifndef STM32N6XX_LL_RCC_H\n#define STM32N6XX_LL_RCC_H\n#include <stdint.h>\n#define LL_RCC_REG_COUNT 1024U\n"
        "#define LL_RCC_CR_OFFSET 0x00U\n#define LL_RCC_CR_HSION_MSK 0x8U\n#define LL_RCC_SR_OFFSET 0x04U\n"
        "#define LL_RCC_SR_HSIRDY_MSK 0x8U\n"
        "extern volatile uint32_t ll_rcc_regs[LL_RCC_REG_COUNT];\n"
        "static inline void LL_RCC_HSI_Enable(void)\n{\n    ll_rcc_regs[LL_RCC_CR_OFFSET / 4U] = LL_RCC_CR_HSION_MSK;\n}\n"
        "static inline uint32_t LL_RCC_HSI_IsReady(void)\n{\n    return ((ll_rcc_regs[LL_RCC_SR_OFFSET / 4U] & "
        "LL_RCC_SR_HSIRDY_MSK) != 0U) ? 1U : 0U;\n}\n#endif /* STM32N6XX_LL_RCC_H */\n")
BUDGET = {"schema": "forge-c/simulation-performance-budget/1", "instructions_per_call": 64, "microseconds_per_call": 100,
          "performance_mips": 100, "test_source": "software/tests/target/test_performance.c"}
REQS = {"SWR-001": "When LL_RCC_HSI_Enable is called, the RCC LL driver shall set RCC_CR.HSION.",
        "SWR-002": "When LL_RCC_HSI_IsReady is called, the RCC LL driver shall return RCC_SR.HSIRDY.",
        "SWR-003": "When a scoped API is measured in the factory's pinned Renode simulation at 100 MIPS without injected "
                   "interrupts or bus stalls, the RCC LL driver shall complete each measured call within 64 executed "
                   "target instructions."}


def _workspace(ws: Path) -> None:
    (ws / ".forge-run").mkdir(parents=True)
    (ws / ".forge-run/manifest.json").write_text(json.dumps({"layer": "LL", "simulation_performance": BUDGET}))
    for rel, txt in {"software/ll/stm32n6xx_ll_rcc.h": LL_H,
                     "software/src/stm32n6xx_ll_rcc.c": '#include "stm32n6xx_ll_rcc.h"\n'}.items():
        (ws / rel).parent.mkdir(parents=True, exist_ok=True)
        (ws / rel).write_text(txt)


def _design(ws: Path) -> dict:
    from forge_factory.assurance import register_contract
    from forge_factory.inspection import swtrace
    from forge_factory.lrtx import swe3, tools
    from forge_factory.lrtx import visit as V

    us = [{"id": f"SWU-LL-{n:02d}", "n": n, "swrs": [f"SWR-00{n}"],
           "function": {"name": f, "operation": "register access", "fields": [], "params": [],
                        "returns": "void" if n == 1 else "uint32_t"}} for n, f in enumerate(FUNCS, 1)]
    for u in us:
        ck = V._ckpt(ws, "SWE.3", f"code:{u['id']}")
        ck.parent.mkdir(parents=True, exist_ok=True)
        ck.write_text(json.dumps({"status": "VALID", "doc": {"code": "-", "spec_items": [
            {"id": f"USPEC-LL-{u['n']:02d}-01", "behaviour": f"The unit shall implement {u['function']['name']}.",
             "traces": u["swrs"]}]}}))
    canned = {"measure_elf": "text=12 data=0 bss=0", "stack_usage": "max frame 0 B", "cppcheck": "0 findings",
              "clang_analyze": "0 diagnostics"}

    def write(ws_, files, _node):
        for rel, text in files.items():
            (Path(ws_) / rel).parent.mkdir(parents=True, exist_ok=True)
            (Path(ws_) / rel).write_text(text)

    swe3.units = lambda _ws: us
    swe3._ident = lambda _ws: {"header": "stm32n6xx_ll_rcc.h", "pfx": "RCC", "block": "ll_rcc_regs", "fn": "LL_RCC_"}
    swtrace.component_constraints = lambda _ws: {"SWR-003"}
    register_contract._requirements = lambda _ws: dict(REQS)
    tools.call = lambda _ws, _srv, op, _a, _r, _p, *a, **k: {"status": "PASS", "summary": canned[op], "issues": [],
                                                             "metrics": {}}
    V.write_scoped = write
    rep = swe3.visit_design(ws)
    if rep.get("status") != "PASS":
        raise LookupError(f"visit_design did not render: {rep.get('issues')}")
    return {p.relative_to(ws).as_posix(): p.read_text() for p in sorted((ws / "workproducts/SWE.3").rglob("*"))
            if p.is_file()}


def _bounded(files: dict) -> dict[str, int]:
    """Per function: the instruction bound a timing section of the detailed design states for it."""
    dd = files.get("workproducts/SWE.3/detailed_design.md", "")
    sec = re.search(r"^##[^\n]*\b(?:[Tt]iming|[Ee]xecution time)\b[^\n]*\n(.*?)(?=^## |\Z)", dd, re.M | re.S)
    out = {}
    for f in FUNCS:
        row = re.search(r"^\|\s*" + re.escape(f) + r"\s*\|\s*(\d+)\s*\|", sec.group(1), re.M) if sec else None
        if row:
            out[f] = int(row.group(1))
    return out


def main() -> int:
    if not shutil.which("arm-none-eabi-gcc") or not shutil.which("arm-none-eabi-objdump"):
        print("REPRODUCER_ERROR:TOOL_MISSING:arm-none-eabi-gcc")
        return 2
    ws = Path.cwd() / "rpr121-ws"  # the runner's scratch cwd
    if ws.exists():
        shutil.rmtree(ws)
    _workspace(ws)
    try:
        files = _design(ws)
    except Exception as exc:  # noqa: BLE001
        print(f"REPRODUCER_ERROR:SCENARIO_NOT_REACHED:{type(exc).__name__}:{str(exc)[:120]}")
        return 2
    if "workproducts/SWE.3/detailed_design.md" not in files:
        print("REPRODUCER_ERROR:SCENARIO_NOT_REACHED:no detailed design rendered")
        return 2
    got = _bounded(files)
    if set(got) != set(FUNCS):
        print(f"SYMPTOM_PRESENT:{SIG}")
        return 1
    evidence = [json.loads(t) for p, t in files.items() if p.endswith(".json") and '"static_instructions"' in t]
    if len(evidence) != 1 or any(evidence[0]["functions"][f]["static_instructions"] != n for f, n in got.items()) \
            or any(not 1 <= n <= BUDGET["instructions_per_call"] for n in got.values()):
        print("REPRODUCER_ERROR:SCENARIO_NOT_REACHED:the stated bound is not backed by one frozen evidence file")
        return 2
    print("SYMPTOM_ABSENT")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"REPRODUCER_ERROR:{type(exc).__name__}:{str(exc)[:160]}")
        sys.exit(2)
