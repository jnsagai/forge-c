"""Explicit, deterministic node procedures for small local models (qwen3:8b).

Observed (ADR-0005): "follow the skill" is insufficient for an 8B model; it froze baselines before writing
any workproduct. Node prompts therefore spell out read -> write -> validate -> freeze -> reply, with the
exact file formats the deterministic gates check. The SKILL remains the role contract (loaded first).
"""
from __future__ import annotations

from ..inspection.engine import load_checklist

READ = ("When you write_file, put real line breaks in the content (one C statement per line); never write \\n escape "
        "sequences as text. Work step by step. After every tool result, immediately continue with the next numbered step; never summarize or "
        "explain tool output. Never read inputs/index.md or the large inputs/*.md documents; read only the section files "
        "named in these steps, each at most once.")
SECTIONS: dict[str, str] = {}  # section number -> section file path, set by the workflow builder per work order


def sec(*nums: str) -> str:
    return ", ".join(SECTIONS.get(n, f"(section {n} unavailable)") for n in nums)
REPLY = 'Finish with ONLY this JSON (no other text): {"status":"PASS","artifacts":["<paths you wrote>"],"issues":[],"next_action":"next"}'
FIX = "If inspection/{p}/ has INS-*.json files or .forge-run/gates/gate-log.jsonl has {p} entries, read the newest and fix every listed finding first."

AUTHOR_STEPS = {
    "SWE.1": [
        "read_file these RM0486 section files: {s1}.",
        "write_file workproducts/SWE.1/software_requirements.md: a '# Software requirements' title, then 8-15 requirements, "
        "one per line exactly like: - **SWR-001** When the HSI enable is requested, the RCC driver shall set RCC_CR.HSION. "
        "Each statement uses EARS (The/When/While/Where/If..then), exactly one 'shall', the system name 'RCC driver', and ends "
        "with a period. Put '  - Source: RM0486 p.<page>' on the next line under each requirement.",
        "write_file safety/software_safety_requirements.md listing the safety-relevant SWR IDs (timeouts, error returns).",
        "write_file traceability/requirements_to_tests.csv with header requirement_id,test_id,test_file and one row per SWR "
        "(test_id UT-001.., test_file software/tests/unit/test_rcc.c).",
        "Call mcp__forge_docs_mcp__validate_artifact with path workproducts/SWE.1/software_requirements.md and check ears; "
        "fix and repeat until status PASS.",
        "Call mcp__forge_evidence_mcp__freeze_baseline with phase SWE.1."],
    "SWE.2": [
        "Read workproducts/SWE.1/software_requirements.md and these RM0486 section files: {s1}.",
        "write_file workproducts/SWE.2/software_architecture.md with sections: Components (LL header-only stm32n6xx_ll_rcc.h, "
        "HAL stm32n6xx_hal_rcc.c/.h), Register access (extern volatile uint32_t register-block array placed at the RCC "
        "base by the linker, indexed by offset/4; no integer-to-pointer casts; host tests define the array), Interfaces (each HAL_RCC_ API with hal_status_t and parameters), Timeouts and error handling, Memory and "
        "stack budget (flash<=4096 B, RAM<=64 B, stack<=128 B), Requirement allocation table (SWR -> function), and a "
        "Register table with one row per register/bit used: name | offset | bit position(s) | access | RM0486 page. RCC base "
        "address 0x56028000 (RM0486 p.176). SWE.3 will implement only from this table.",
        "Call mcp__forge_docs_mcp__validate_artifact with path workproducts/SWE.2/software_architecture.md and check "
        "architecture; fix every finding (rewrite the file with write_file) and repeat until status PASS. Never write "
        "your JSON reply into a workproduct file.",
        "Call mcp__forge_evidence_mcp__freeze_baseline with phase SWE.2."],
    "SWE.3": [
        "read_file software/ll/stm32n6xx_ll_rcc.h, software/hal/stm32n6xx_hal_rcc.h and software/hal/stm32n6xx_hal_rcc.c "
        "(written by the LL and HAL steps). Never change the generated register defines.",
        "Call mcp__forge_build_mcp__compile with profile target-cm55-gcc, then with profile host-clang. Fix each error with "
        "ONE small edit_file call (old_string = the few exact lines to replace, at most 40 lines), then compile again.",
        "Call mcp__forge_docs_mcp__validate_artifact with check hal_guideline and then with check register_map; fix every "
        "violation the same way and repeat until both PASS.",
        "Call mcp__forge_analysis_mcp__clang_analyze and mcp__forge_analysis_mcp__cppcheck; fix real defects by changing "
        "the code (suppression comments are ignored and forbidden).",
        "write_file workproducts/SWE.3/detailed_design.md (at most 40 lines): '# Detailed design', then a table "
        "| Function | Purpose | Registers/bits (RM0486 page) | SWR IDs | with one row per HAL_RCC_ function.",
        "Call mcp__forge_evidence_mcp__freeze_baseline with phase SWE.3."],
    "SWE.4": [
        "Read software/hal/stm32n6xx_hal_rcc.h, software/ll/stm32n6xx_ll_rcc.h and traceability/requirements_to_tests.csv.",
        "write_file software/tests/unit/test_rcc.c: a self-checking C program with main() returning 0 only if all checks pass; "
        "define 'volatile uint32_t ll_rcc_regs[LL_RCC_REG_COUNT];' as the fake RCC block (host), cover every HAL_RCC_ function incl. timeout and "
        "invalid-parameter paths; print one line per test case 'UT-00x PASS|FAIL'.",
        "Call mcp__forge_tests_mcp__run_unit; fix failures. Then call mcp__forge_tests_mcp__llvm_coverage.",
        "write_file workproducts/SWE.4/unit_verification_report.md: test cases, SWR mapping, results, coverage numbers from the tool.",
        "Update traceability/requirements_to_tests.csv so every SWR has a test_id implemented in test_rcc.c.",
        "Call mcp__forge_evidence_mcp__freeze_baseline with phase SWE.4."],
    "SWE.5": [
        "Read workproducts/SWE.2/software_architecture.md and software/tests/unit/test_rcc.c.",
        "write_file software/tests/integration/test_rcc_integration.c: self-checking program exercising HAL+LL together "
        "(enable oscillator then peripheral clock then reset sequence, and a forced timeout).",
        "Call mcp__forge_tests_mcp__run_integration; fix failures. Call mcp__forge_sim_mcp__run_renode once and record its result.",
        "write_file workproducts/SWE.5/integration_verification_report.md with sequences, results and the simulator status.",
        "Call mcp__forge_evidence_mcp__freeze_baseline with phase SWE.5."],
    "SWE.6": [
        "Read workproducts/SWE.1/software_requirements.md, the SWE.4 and SWE.5 reports and traceability/requirements_to_tests.csv.",
        "Call mcp__forge_tests_mcp__run_integration and mcp__forge_evidence_mcp__validate_trace.",
        "write_file workproducts/SWE.6/software_verification_report.md: table SWR -> test id -> result -> evidence, list "
        "untested requirements as issues, state that results are host-only (no target verification).",
        "Call mcp__forge_evidence_mcp__freeze_baseline with phase SWE.6."],
}


SMALL = ("Keep every write_file/edit_file content under 40 lines; long tool calls are lost. Make one call per "
         "function group and continue with the next group after each result.")
LL_STEPS = [
    "read_file software/ll/stm32n6xx_ll_rcc.h: its register definitions (LL_RCC_<REG>_OFFSET, LL_RCC_<REG>_<FIELD>_POS, "
    "LL_RCC_<REG>_<FIELD>_MSK) were GENERATED from RM0486; never change or add register defines. Then read "
    "workproducts/SWE.2/software_architecture.md (Interfaces and Requirement allocation only).",
    "For EACH oscillator/PLL and each peripheral the HAL needs, make ONE edit_file call on software/ll/stm32n6xx_ll_rcc.h "
    "with old_string exactly '{marker}' and new_string = that group's functions, a blank line, then the same marker "
    "line again (so the next group can be inserted). A group is: static inline void LL_RCC_<Name>_Enable(void) and "
    "LL_RCC_<Name>_Disable(void), plus static inline uint32_t LL_RCC_<Name>_IsReady(void) (oscillators/PLLs, flag "
    "in RCC_SR) or LL_RCC_<Name>_IsEnabled(void) (peripherals); each body is one statement on "
    "ll_rcc_regs[LL_RCC_<REG>_OFFSET / 4U] using only the generated _MSK defines (enables in RCC_CR / RCC_AHB1ENR, "
    "resets in RCC_AHB1RSTR with LL_RCC_<Name>_ForceReset/ReleaseReset). Real line breaks only.",
    "Call mcp__forge_docs_mcp__validate_artifact with check register_map; it must be PASS.",
    "Reply with the list of LL_RCC_ function names you declared.",
]
HAL_MARKER = "/* HAL_RCC API implementation (SWE.3 HAL author) */"
HAL_H_MARKER = "/* HAL_RCC API prototypes (SWE.3 HAL author) */"
HAL_STEPS = [
    "read_file software/ll/stm32n6xx_ll_rcc.h (use only the LL_RCC_ functions and defines declared there; never invent "
    "LL names) and workproducts/SWE.2/software_architecture.md (Interfaces and Requirement allocation).",
    "write_file software/hal/stm32n6xx_hal_rcc.h with exactly: '#ifndef STM32N6XX_HAL_RCC_H', '#define "
    "STM32N6XX_HAL_RCC_H', '#include \"stm32n6xx_ll_rcc.h\"', 'typedef enum {HAL_OK=0U,HAL_ERROR=1U,HAL_TIMEOUT=2U} "
    "hal_status_t;', '#define HAL_RCC_TIMEOUT_VALUE 1000U', the line '{hmarker}', '#endif /* STM32N6XX_HAL_RCC_H */' and "
    "a final newline.",
    "Insert the API prototypes with edit_file on that header: old_string exactly '{hmarker}', new_string = at most 8 "
    "prototypes 'hal_status_t HAL_RCC_<Name>_Enable(void);' etc., a blank line, then the marker again; repeat until "
    "every interface of the architecture is declared.",
    "write_file software/hal/stm32n6xx_hal_rcc.c with exactly: '#include \"stm32n6xx_hal_rcc.h\"', a blank line, the line "
    "'{marker}' and a final newline.",
    "For EACH API group make ONE edit_file call on software/hal/stm32n6xx_hal_rcc.c with old_string exactly '{marker}' "
    "and new_string = that group's function definitions (at most 40 lines), a blank line, then the marker again. Each "
    "function calls only LL_RCC_ functions; every wait loop is 'while ((LL_RCC_<Name>_IsReady() == 0U) && (count < "
    "HAL_RCC_TIMEOUT_VALUE))' then returns HAL_TIMEOUT if count reached the limit, else HAL_OK; locals lower case.",
    "Reply with the list of HAL_RCC_ functions you implemented.",
]


def ll_author_prompt() -> str:
    """SWE.3 step 1 (fresh, small context): LL access functions on the generated register map; HAL comes next."""
    from ..inspection.regmap import FUNCTIONS_MARKER

    steps = ["Call use_skill with skill_name swe3-author.", READ, SMALL] + \
        [x.replace("{marker}", FUNCTIONS_MARKER) for x in LL_STEPS] + [REPLY]
    return " ".join(f"{i}) {s}" for i, s in enumerate(steps, 1))


def hal_author_prompt() -> str:
    """SWE.3 step 2 (fresh context): HAL header/source built incrementally in small edits against the LL header."""
    steps = ["Call use_skill with skill_name swe3-author.", READ, SMALL] + \
        [x.replace("{marker}", HAL_MARKER).replace("{hmarker}", HAL_H_MARKER) for x in HAL_STEPS] + [REPLY]
    return " ".join(f"{i}) {s}" for i, s in enumerate(steps, 1))


def author_prompt(phase: str) -> str:
    n = phase[-1]
    fills = {"s1": sec("14.10.1", "14.10.2", "14.10.79", "14.10.64")}
    body = [x.format(**fills) if "{s" in x else x for x in AUTHOR_STEPS[phase]]
    steps = [f"Call use_skill with skill_name swe{n}-author.", READ, "read_file .forge-run/manifest.json.",
             FIX.format(p=phase)] + body + [REPLY]
    return " ".join(f"{i}) {s}" for i, s in enumerate(steps, 1))


def inspector_prompt(phase: str) -> str:
    n = phase[-1]
    items = "; ".join(f"{c['id']}: {c['criterion'][:70]}" for c in load_checklist(phase)["checks"])
    example = "; ".join(f"{c['id']}=PASS" for c in load_checklist(phase)["checks"][:2])
    steps = [f"Call use_skill with skill_name swe{n}-inspector.",
             f"glob configuration/baselines/{phase}/BL-*.json and read the newest one: note its baseline_id and files.",
             "read_file each listed workproduct (use offset/limit for long files). Never edit any file.",
             f"Judge each checklist item: {items}.",
             f"Call mcp__forge_evidence_mcp__check_inspection with phase {phase}, baseline_id <id>, and verdicts as ONE plain "
             f"string covering EVERY item, e.g. \"{example}; ...\" and for a failed item ID=FAIL:<short finding>. "
             "Items decided by deterministic tools are recomputed automatically.",
             'Finish with ONLY JSON: {"status":"PASS" or "REWORK","artifacts":["inspection/' + phase +
             '/<INS id>.json"],"issues":["<item id: finding>"],"next_action":"next" or "rework"}']
    return " ".join(f"{i}) {s}" for i, s in enumerate(steps, 1))
