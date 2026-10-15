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
        "HAL stm32n6xx_hal_rcc.c/.h), Register access (volatile uint32_t at base+offset; base pointer replaceable for host "
        "tests), Interfaces (each HAL_RCC_ API with hal_status_t and parameters), Timeouts and error handling, Memory and "
        "stack budget (flash<=4096 B, RAM<=64 B, stack<=128 B), Requirement allocation table (SWR -> function), and a "
        "Register table with one row per register/bit used: name | offset | bit position(s) | access | RM0486 page. RCC base "
        "address 0x56028000 (RM0486 p.176). SWE.3 will implement only from this table.",
        "Call mcp__forge_docs_mcp__validate_artifact with path workproducts/SWE.2/software_architecture.md and check "
        "architecture; fix every finding (rewrite the file with write_file) and repeat until status PASS. Never write "
        "your JSON reply into a workproduct file.",
        "Call mcp__forge_evidence_mcp__freeze_baseline with phase SWE.2."],
    "SWE.3": [
        "Read workproducts/SWE.2/software_architecture.md (its register table is your only hardware source; do not read the RM) "
        "and read_file software/ll/stm32n6xx_ll_rcc.h (written by the LL step). If the LL header is missing a register or "
        "bit you need, rewrite it with write_file (same rules: defines and static inline LL_RCC_ functions only).",
        "write_file software/hal/stm32n6xx_hal_rcc.h: guard STM32N6XX_HAL_RCC_H, #include \"stm32n6xx_ll_rcc.h\", typedef "
        "enum {HAL_OK=0U,HAL_ERROR=1U,HAL_TIMEOUT=2U} hal_status_t, lower-case hal_ types ending _t, API prototypes "
        "HAL_RCC_... with const pointers for config.",
        "write_file software/hal/stm32n6xx_hal_rcc.c: implement the API calling ONLY LL_RCC_ functions and macros that are "
        "declared in software/ll/stm32n6xx_ll_rcc.h (never invent LL names); every wait loop is while((cond) && (count < "
        "timeout)); every parameter is used or cast to (void); no device RPN #if, no heap, no recursion, local arrays <=128 "
        "bytes, parameters lower case.",
        "write_file workproducts/SWE.3/detailed_design.md: per function purpose, registers/bits used with RM page, SWR IDs.",
        "Call mcp__forge_build_mcp__compile with profile target-cm55-gcc, then with profile host-clang. To fix errors, "
        "rewrite the whole affected file with write_file (do not use edit_file), then compile again.",
        "Call mcp__forge_docs_mcp__validate_artifact with check hal_guideline; fix every violation and repeat until PASS.",
        "Call mcp__forge_analysis_mcp__clang_analyze and mcp__forge_analysis_mcp__cppcheck; fix real defects.",
        "Call mcp__forge_evidence_mcp__freeze_baseline with phase SWE.3."],
    "SWE.4": [
        "Read software/hal/stm32n6xx_hal_rcc.h, software/ll/stm32n6xx_ll_rcc.h and traceability/requirements_to_tests.csv.",
        "write_file software/tests/unit/test_rcc.c: a self-checking C program with main() returning 0 only if all checks pass; "
        "use a static uint32_t register array as the fake RCC block (host), cover every HAL_RCC_ function incl. timeout and "
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


LL_STEPS = [
    "Read workproducts/SWE.2/software_architecture.md (its register table is your only hardware source; do not read the RM).",
    "write_file software/ll/stm32n6xx_ll_rcc.h: guard STM32N6XX_LL_RCC_H, #include <stdint.h>, RCC base as an "
    "overridable define (#ifndef LL_RCC_BASE / #define LL_RCC_BASE 0x56028000UL / #endif, so host tests can redirect it) "
    "and #define LL_RCC_REG(off) (*(volatile uint32_t *)(LL_RCC_BASE + (off))), register "
    "offsets as LL_RCC_..._OFFSET defines, bit masks as LL_RCC_..._Msk defines, and for each oscillator/clock/reset bit "
    "in the table small static inline functions named LL_RCC_<Name>_Enable, LL_RCC_<Name>_Disable and "
    "LL_RCC_<Name>_IsReady (returning uint32_t 0U/1U) as applicable; no enum; types lower case ending _t prefixed ll_.",
    "Reply with the list of LL_RCC_ function names you declared.",
]


def ll_author_prompt() -> str:
    """SWE.3 step 1 (fresh, small context): the LL header alone; the HAL step then implements against it."""
    steps = ["Call use_skill with skill_name swe3-author.", READ] + LL_STEPS + [REPLY]
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
