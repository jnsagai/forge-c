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
# ADR-0008 loopbacks. Upstream owners (SWE.1-3) fix defects routed to them; downstream roles report instead of bending.
FIX_DEFECTS = ("glob .forge-run/defects/DEF-*.json and read every defect with target_phase {p} and status IN_FIX: "
               "fix it in your phase's work products FIRST (its requirement_ids, summary and cited test files are the "
               "evidence; never edit the cited tests). First compare the defect with the cited requirement text in "
               "workproducts/SWE.1/software_requirements.md: a requirement as written always wins. If the defect asks "
               "for behaviour the requirement does not demand or contradicts, or is not in your phase, call "
               "mcp__forge_evidence_mcp__reject_defect with defect_id and a reason instead of changing anything.")
DEFECT_RULE = ("When a test fails, decide where the fault is. If the test matches the SWE.1 requirement and the driver "
               "code or the API/architecture is wrong, do NOT change the test: call "
               "mcp__forge_evidence_mcp__report_defect with kind CODE (the code violates the requirement AS WRITTEN; "
               "requirement_quote = the violated clause copied verbatim) or ARCHITECTURE (the API cannot express the "
               "clause copied verbatim into requirement_quote; first check that the requirement really demands the "
               "missing function - a test that calls a function the header does not declare is usually a TEST "
               "error), requirement_ids, test_files (the failing test files) and a summary, then finish with "
               "status REWORK. If you believe the requirement itself is wrong (e.g. real hardware behaves "
               "differently), report kind REQUIREMENT - never ask for code that contradicts a requirement. If the test "
               "itself is wrong, correct it and declare that with report_defect kind TEST (requirement_ids, "
               "test_files, requirement_quote = the clause the corrected test checks, why it was wrong). A defect you "
               "reported that is REJECTED in .forge-run/defects carries the owner's reason: correct your test (declare "
               "it as TEST) or, if the requirement itself is wrong, report kind REQUIREMENT - never re-report it. If a "
               "defect you reported turns out to be your own test error, correct the test and declare kind TEST on "
               "the same test file: that withdraws your defect. An expected value comes from the requirement, never from what the "
               "code produced: do not tune it until it matches (r76 tried +0, +1, +2, 12345 for a read count); if the "
               "requirement states a bound ('at most N'), check the bound (<=), not an exact count.")
INSPECT_DEFECT = ("If a finding is caused upstream (driver code, architecture or requirement - not in this phase's "
                  "work products), also record it with mcp__forge_evidence_mcp__report_defect (kind CODE, "
                  "ARCHITECTURE or REQUIREMENT, requirement_ids, summary; for CODE and ARCHITECTURE requirement_quote "
                  "= the clause copied verbatim) before check_inspection.")

# r77: the manifest's target.hsi_contract / target.safety_allocation record the owner's scope decision while
# upstream.status reports the unfilled approval template as NOT_PROVIDED; inspectors judged SWE1-01 both ways
# CAPA-007 (r80): SWE5-03 failed for "no interrupt interaction tested" although the work order excludes interrupts
WORK_ORDER_SCOPE_NOTE = ("Read .forge-run/manifest.json 'scope' once. A checklist item about behaviour that the scope "
                         "lists as 'Out of scope' (e.g. interrupts, PLL, low-power modes) is not applicable: judge it "
                         "PASS with 'N/A by work-order scope' when the report states the exclusion (FAIL only if the "
                         "report omits it or claims such behaviour was tested); never fail an item for not testing "
                         "excluded behaviour.")
OWNER_SCOPE_NOTE = ("SWE1-01: if .forge-run/manifest.json target.hsi_contract / target.safety_allocation record an owner "
                    "decision (e.g. HSI = RM0486 chapter, safety allocation OUT_OF_SCOPE or PENDING owner allocation review), "
                    "judge SWE1-01 against that "
                    "scope; upstream.status NOT_PROVIDED placeholders of the optional approval template are gaps to be "
                    "recorded in traceability/upstream_gaps.md, not a failure of SWE1-01.")

GATE_DECLARED_CHECK = ("glob .forge-run/defects/DEF-*.json: for every kind TEST defect with detected_phase {p} "
                       "(declared by the author, or by the route-gate after an upstream fix) read the CURRENT version "
                       "of each file in its test_files (it may have been corrected again after the declaration) and "
                       "the cited requirement, and FAIL the test-related item if the test no longer checks the "
                       "requirement as written (weakened check, removed case, or check bent to the code).")

AUTHOR_STEPS = {
    "SWE.1": [
        "read_file these RM0486 section files: {s1}.",
        "write_file workproducts/SWE.1/software_requirements.md: a '# Software requirements' title, then 8-15 requirements, "
        "one per line exactly like: - **SWR-001** When the HSI enable is requested, the RCC driver shall set RCC_CR.HSION. "
        "Each statement uses EARS (The/When/While/Where/If..then), exactly one 'shall', the system name 'RCC driver', and ends "
        "with a period. Put '  - Source: RM0486 p.<page>' and '  - Verification: <test method and pass criterion>' on "
        "the next lines under each requirement (the pass criterion uses the requirement's own bound, e.g. 'at most "
        "HAL_RCC_TIMEOUT_VALUE polling iterations', never an exact count of register reads or other implementation "
        "steps), and end the file with '## Open points' listing unresolved ambiguities "
        "(or 'none'). Add three measurable "
        "resource requirements from the .forge-run/manifest.json budgets, e.g. '- **SWR-0nn** The RCC driver shall occupy "
        "at most 4096 bytes of flash.' (likewise static RAM and stack), with '  - Source: work-order budget (owner "
        "development target)'. Add reset/startup requirements phrased as RCC driver behaviour with 'the RCC driver' as "
        "subject (e.g. '- **SWR-0nn** While no oscillator enable has been requested after reset, the RCC driver shall "
        "leave RCC_CR.HSEON at its reset value 0.'), one requirement per failure response (ready timeout -> the driver clears the "
        "enable bit it set (driver fallback state: oscillator/clock off) and returns HAL_TIMEOUT; invalid parameter -> "
        "HAL_ERROR without register writes, naming the invalid values: a NULL pointer, an unknown selector, and a "
        "timeout argument of 0 or greater than HAL_RCC_TIMEOUT_VALUE), and one measurable timing "
        "requirement (every wait is bounded by HAL_RCC_TIMEOUT_VALUE = 1000 polling iterations).",
        "write_file safety/software_safety_requirements.md: if the manifest target safety_allocation is OUT_OF_SCOPE, state "
        "'QM development scope: no software safety requirements are allocated (work-order owner decision)' and list no "
        "safety items; if it says 'software safety allocation PENDING owner allocation review', state 'Target <the ASIL "
        "from target.safety_allocation> (<its scope id>): software safety allocation PENDING owner allocation review - no "
        "software safety requirement is allocated yet; this is an open gap, not a QM claim', list no safety items and "
        "never write QM; otherwise list the safety-relevant SWR IDs.",
        "If inputs/upstream-inputs.yaml exists (human-approved HSI contract, safety allocation, budgets), read it and write "
        "one requirement per allocated software safety requirement with '  - Source: <SSR id>'. write_file "
        "traceability/upstream_gaps.md: '# Upstream coverage', (a) one row per upstream input from the manifest target "
        "(HSI contract, safety allocation, budgets): input | status as stated in the manifest | affected SWR IDs, and (b) "
        "a bidirectional trace table: upstream id (RM0486-<section number> or WO-BUDGET) | SWR IDs, plus for every SWR its "
        "upstream id. Never invent an allocation.",
        "write_file traceability/requirements_to_tests.csv with header requirement_id,test_id,test_file and one row per SWR: "
        "test_id UT-001.. and test_file software/tests/unit/test_rcc.c for requirements a host unit test verifies; for "
        "flash, static RAM, stack and target-only requirements test_id = the SWR id and test_file = "
        "software/tests/software/test_rcc_requirements.robot (verified by the SWE.6 Robot suite).",
        "Call mcp__forge_docs_mcp__validate_artifact with path workproducts/SWE.1/software_requirements.md and check ears; "
        "fix and repeat until status PASS.",
        "Do not call freeze_baseline: when you reply PASS the deterministic gate freezes the SWE.1 baseline."],
    "SWE.2": [
        "Read workproducts/SWE.1/software_requirements.md and these RM0486 section files: {s1}.",
        "write_file workproducts/SWE.2/software_architecture.md with sections: Components (LL header-only stm32n6xx_ll_rcc.h, "
        "HAL stm32n6xx_hal_rcc.c/.h), Register access (extern volatile uint32_t register-block array placed at the RCC "
        "base by the linker, indexed by offset/4; no integer-to-pointer casts; host tests define the array), Interfaces (each HAL_RCC_ API with hal_status_t, named exactly HAL_RCC_<Name>_Enable, HAL_RCC_<Name>_Disable, "
        "HAL_RCC_<Name>_Reset or HAL_RCC_<Name>_ReleaseReset where <Name> is HSI, HSE, MSI, LSI, LSE, PLL1..PLL4 or the "
        "peripheral, e.g. HAL_RCC_HSI_Enable), Timeouts and error handling, Memory and "
        "stack budget (flash<=4096 B, RAM<=64 B, stack<=128 B), Requirement allocation table (SWR -> function), and a "
        "Register table with one row per register/bit used: name | offset | bit position(s) | access | RM0486 page. RCC base "
        "address 0x56028000 (RM0486 p.176). SWE.3 will implement only from this table.",
        "Call mcp__forge_docs_mcp__validate_artifact with path workproducts/SWE.2/software_architecture.md and check "
        "architecture; fix every finding (rewrite the file with write_file) and repeat until status PASS. Never write "
        "your JSON reply into a workproduct file.",
        "write_file workproducts/SWE.2/architecture_static.puml: PlantUML component view between '@startuml' and "
        "'@enduml' with components named stm32n6xx_hal_rcc (HAL) and stm32n6xx_ll_rcc (LL, header-only), the RCC register "
        "block (0x56028000) and their dependencies (HAL -> LL -> registers).",
        "write_file workproducts/SWE.2/architecture_dynamic.puml: PlantUML sequence view(s) between '@startuml' and "
        "'@enduml' with participants Caller, stm32n6xx_hal_rcc, stm32n6xx_ll_rcc, RCC, showing an oscillator enable with "
        "the ready path (HAL_OK) and the timeout path (HAL_TIMEOUT) using the allocated HAL_RCC_ function names, plus a "
        "peripheral clock enable or reset sequence.",
        "Call mcp__forge_docs_mcp__validate_artifact with check plantuml; fix every finding and repeat until PASS.",
        "Do not call freeze_baseline: when you reply PASS the deterministic gate freezes the SWE.2 baseline."],
    "SWE.3": [
        "read_file workproducts/SWE.2/software_architecture.md (Memory and stack budget section only, use offset/limit).",
        "Call mcp__forge_analysis_mcp__cppcheck and mcp__forge_analysis_mcp__clang_analyze, then "
        "mcp__forge_build_mcp__measure_elf and mcp__forge_build_mcp__stack_usage with profile target-cm55-gcc. If "
        "cppcheck reports any finding, fix it in the code (MISRA 15.5: single return via a status variable; MISRA 11.9: "
        "use NULL, never 0, as null pointer constant; style variableScope: innermost block; no suppressions), re-run "
        "cppcheck and validate_artifact check swe3_all until both PASS, then measure.",
        "write_file workproducts/SWE.3/detailed_design.md: '# Detailed design'; a table | Function | Purpose | "
        "Registers/bits (RM0486 page) | SWR IDs | with one row per HAL_RCC_ function; '## Static analysis and MISRA "
        "(subset)' with the cppcheck and clang results exactly as the tools reported them (rules hit, counts; state that "
        "MISRA compliance is not claimed); '## Resource usage' with the measured flash/RAM (measure_elf) and maximum "
        "stack frame (stack_usage) next to the architecture budgets.",
        "Do not call freeze_baseline: when you reply PASS the deterministic gate freezes the SWE.3 baseline."],
    "SWE.4": [
        "read_file software/tests/unit/test_rcc.c (written by the unit-test step) and traceability/requirements_to_tests.csv.",
        "Call mcp__forge_tests_mcp__run_unit. Fix each failing test or compile error with ONE small edit_file call (at most "
        "40 lines) and run again until PASS. Never weaken a check to make it pass; a real driver defect is reported as an "
        "issue.",
        "Call mcp__forge_tests_mcp__llvm_coverage.",
        "write_file workproducts/SWE.4/unit_verification_report.md with these sections (SWE.4 checklist): '## Measures, "
        "environment, entry/exit criteria and regression' (host clang build, fake register array; entry: SWE.3 baseline "
        "frozen; exit: all UT PASS and coverage goal met or deviation recorded; regression: full suite re-run on every "
        "change); '## Test cases' table | UT id | function | SWR ids | kind (positive/negative/boundary/error) | result | "
        "with EXACTLY the UT ids of software/tests/unit/test_rcc.c; '## Mock fidelity' (plain RAM register array: no "
        "write-1-to-clear, read-only or hardware side effects; ready flags preset by the test; limitations listed); "
        "'## Static analysis' (cppcheck/clang results from SWE.3, deviations: none or listed); '## Coverage' (goal: 100% "
        "statement/branch of driver code; the llvm_coverage numbers exactly as reported; any shortfall listed as a "
        "deviation with reason); '## Findings' (open issues or 'none').",
        "read_file traceability/requirements_to_tests.csv (owned by SWE.1; you cannot edit it): every UT id it cites "
        "for software/tests/unit/test_rcc.c must appear in a CHECK of that file - add or rename your tests to match "
        "it (never cite or invent other ids). Then call mcp__forge_evidence_mcp__validate_trace and fix your tests "
        "until PASS; if the trace itself is wrong, report_defect kind REQUIREMENT.",
        "Do not call freeze_baseline: when you reply PASS the deterministic gate freezes the SWE.4 baseline."],
    "SWE.5": [
        "Read workproducts/SWE.2/software_architecture.md, software/hal/stm32n6xx_hal_rcc.h and software/tests/unit/test_rcc.c.",
        "write_file software/tests/integration/test_rcc_integration.c: self-checking host program exercising HAL+LL together "
        "(enable oscillator then peripheral clock then reset sequence, and a forced timeout).",
        "Call mcp__forge_tests_mcp__run_integration; fix failures.",
        "Call mcp__forge_sim_mcp__run_renode once (the target tests were written and run by the previous step) to get "
        "the target results for the report.",
        "write_file workproducts/SWE.5/integration_verification_report.md with sections: '## Plan' (component and "
        "integration measures), '## Integration sequence' (matches the architecture interfaces), '## Clock/reset "
        "interactions tested', '## Robustness, fault propagation, timing/resource budgets' (timeout paths, measured sizes), "
        "'## Results' (host results and the Renode target results exactly as reported), '## Simulation vs target "
        "limitations' (simulated Cortex-M55 with a behavioural RCC model: no clock-tree timing, no security filtering, no "
        "silicon verification), '## Scope exclusions' (each interaction the .forge-run/manifest.json scope lists as "
        "'Out of scope', e.g. interrupts or low-power modes, marked 'not applicable: excluded by work-order scope', or "
        "'none') and '## Open defects' (or 'none').",
        "Do not call freeze_baseline: when you reply PASS the deterministic gate freezes the SWE.5 baseline."],
    "SWE.6": [
        "Call mcp__forge_tests_mcp__run_robot FIRST (the scenario files and software/tests/software/"
        "test_rcc_requirements.robot were written by the previous step). Use only run_robot and validate_trace in this "
        "step - never run_integration, run_renode or build tools.",
        "REQUIREMENT_NOT_OBSERVED means YOUR test never checks what the requirement demands: add exactly the named "
        "TCHECK to the named scenario file and 'Target Check Should Pass    <n>' to that SWR test (an edit_file each), "
        "then run_robot again - this is not a tool problem, do not search the factory. "
        "If run_robot FAILs a check, decide BEFORE anything else, in at most 5 tool calls: read "
        "workproducts/SWE.1/software_requirements.md and use the CHECK_EXPR / REQUIREMENT_NOT_OBSERVED issues (they "
        "show what each failing check tests). For each failing requirement either correct the scenario/suite (and "
        "declare it with report_defect kind TEST) or, if the test is right, call report_defect (CODE or ARCHITECTURE "
        "with requirement_quote) and then finish immediately with status REWORK - do not write the report. A failing "
        "check that calls the driver and tests what the requirement names (e.g. 'rc == HAL_ERROR with rc = "
        "HAL_RCC_...(...)') is right by construction: never change, weaken or remove it - report it as CODE.",
        "When run_robot PASSes: call mcp__forge_evidence_mcp__validate_trace, then read the SWE.4 and SWE.5 reports.",
        "write_file workproducts/SWE.6/software_verification_report.md with: a table SWR -> Robot test -> pass/fail -> "
        "evidence (build/robot/output.xml, log.html), covering normal, boundary and failure behaviour; '## Fault responses "
        "and target constraints'; '## Regressions and defect status' (list every defect in .forge-run/defects); and "
        "'## Unverified items' stating accurately: host tests plus simulated Cortex-M55 target (Renode, behavioural RCC "
        "model) only, no silicon/board verification, safety allocation out of scope by owner decision.",
        "Do not call freeze_baseline: when you reply PASS the deterministic gate freezes the SWE.6 baseline."],
}


CHUNK = {"lines": 40}  # set per run by the workflow builder: 40 for local models (dropped long calls), larger for cloud
LAYER = {"layer": "LL+HAL"}  # ADR-0009: set per run by the workflow builder (LL | HAL | LL+HAL)
TRACE = {"on": False}  # owner addendum 2026-10-17 (EASA-OR-001..011): set per run by the workflow builder
ISOLATION = {"on": False}  # CAPA-038: HAL unit tests run on the generated LL test double (set by the builder)


def small() -> str:
    n = CHUNK["lines"]
    if n <= 40:
        return ("Keep every write_file/edit_file content under 40 lines; long tool calls are lost. Make one call per "
                "function group and continue with the next group after each result. Never call freeze_baseline in "
                "this step.")
    return (f"Keep every write_file/edit_file content under {n} lines and put SEVERAL function groups into one call "
            "(you have at most 20 tool calls in this step). Never call freeze_baseline in this step.")
REENTRY = ("If the file you are about to write already contains functions (an upstream defect sent the run back "
           "here), keep every existing function: only add or change what the defects in .forge-run/defects (status "
           "IN_FIX) and the changed architecture require; never duplicate a function.")


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
HAL_EXAMPLE = ("hal_status_t HAL_RCC_HSI_Enable(void)\n{\n    uint32_t count = 0U;\n    LL_RCC_HSI_Enable();\n"
               "    while ((LL_RCC_HSI_IsReady() == 0U) && (count < HAL_RCC_TIMEOUT_VALUE))\n    {\n        count++;\n"
               "    }\n    return (LL_RCC_HSI_IsReady() != 0U) ? HAL_OK : HAL_TIMEOUT;\n}")
HAL_MARKER = "// HAL_RCC API implementation (SWE.3 HAL author)"
HAL_H_MARKER = "// HAL_RCC API prototypes (SWE.3 HAL author)"
HAL_STEPS = [
    "read_file software/ll/stm32n6xx_ll_rcc.h (use only the LL_RCC_ functions and defines declared there; never invent "
    "LL names) and workproducts/SWE.2/software_architecture.md (Interfaces and Requirement allocation).",
    "write_file software/hal/stm32n6xx_hal_rcc.h with exactly: '#ifndef STM32N6XX_HAL_RCC_H', '#define "
    "STM32N6XX_HAL_RCC_H', '#include \"stm32n6xx_ll_rcc.h\"', 'typedef enum {HAL_OK=0U,HAL_ERROR=1U,HAL_TIMEOUT=2U} "
    "hal_status_t;', '#define HAL_RCC_TIMEOUT_VALUE 1000U', the line '{hmarker}', '#endif /* STM32N6XX_HAL_RCC_H */' and "
    "a final newline.",
    "Insert the API prototypes with edit_file on that header: old_string exactly '{hmarker}', new_string = at most 8 "
    "prototypes using EXACTLY the HAL_RCC_ names of the SWE.2 Requirement allocation table and EXACTLY the parameter "
    "lists and types given in the SWE.2 Interfaces section ('(void)' only where the architecture specifies no "
    "parameters; declare any configuration struct type it names, lower case ending _t, before the prototypes), a "
    "blank line, then the marker again; repeat until every allocated function is declared.",
    "Never define ll_rcc_regs or add other source files: the register block is placed by the linker on target and "
    "defined by the test harness on host; only the extern declaration in the LL header exists.",
    "write_file software/hal/stm32n6xx_hal_rcc.c with exactly: '#include \"stm32n6xx_hal_rcc.h\"', a blank line, the line "
    "'{marker}' and a final newline.",
    "For each API group (or several groups per call, see the size rule) make an edit_file call on software/hal/stm32n6xx_hal_rcc.c with old_string exactly '{marker}' "
    "and new_string = that group's function definitions (at most 40 lines), a blank line, then the marker again. Each "
    "function calls only LL_RCC_ functions and keeps the exact signature declared in the header. Oscillator/PLL Enable "
    "functions wait for the ready flag with a timeout like this example (adapt names; if the architecture passes a "
    "timeout or config parameter, use it instead of HAL_RCC_TIMEOUT_VALUE and check pointer parameters for NULL and "
    "a timeout of 0 or greater than HAL_RCC_TIMEOUT_VALUE first, returning HAL_ERROR before any register write): ```{hal_example}``` Disable functions wait until IsReady() == 0U the same "
    "way; peripheral clock enable/disable and reset functions call the LL function and return HAL_OK.",
    "Call mcp__forge_docs_mcp__validate_artifact with check swe3_all and fix what it reports (missing functions, guideline "
    "naming such as hal_ prefixed lower-case types ending _t) before replying.",
    "Reply with the list of HAL_RCC_ functions you implemented.",
]


UT_EXAMPLE = ("static void ut_hsi_enable(void)\n{\n    hal_status_t st;\n    ut_reset_regs();\n"
              "    ll_rcc_regs[LL_RCC_SR_OFFSET / 4U] = LL_RCC_SR_HSIRDY_MSK;\n    st = HAL_RCC_HSI_Enable();\n"
              "    CHECK(\"UT-001\", (st == HAL_OK) && ((ll_rcc_regs[LL_RCC_CR_OFFSET / 4U] & LL_RCC_CR_HSION_MSK) != 0U));\n"
              "    ut_reset_regs();\n    st = HAL_RCC_HSI_Enable();\n    CHECK(\"UT-002\", st == HAL_TIMEOUT);\n}")
FAKE_UT_EXAMPLE = ("static void ut_hse_enable(void)\n{\n    hal_status_t st;\n    ut_reset();\n"
                   "    ll_fake_return_from(LL_FAKE_LL_RCC_HSE_IsReady, 3U, 1U);  /* ready from the 3rd poll on */\n"
                   "    st = HAL_RCC_HSE_Enable(10U);\n"
                   "    CHECK(\"UT-001\", st == HAL_OK);\n"
                   "    CHECK(\"UT-001-ENABLED\", ll_fake_calls(LL_FAKE_LL_RCC_HSE_Enable) == 1U);\n"
                   "    CHECK(\"UT-001-ORDER\", ll_fake_index_of(LL_FAKE_LL_RCC_HSE_Enable, 1U) < "
                   "ll_fake_index_of(LL_FAKE_LL_RCC_HSE_IsReady, 1U));\n"
                   "    ut_reset();  /* never ready */\n    st = HAL_RCC_HSE_Enable(10U);\n"
                   "    CHECK(\"UT-002\", st == HAL_TIMEOUT);\n"
                   "    CHECK(\"UT-002-ROLLBACK\", ll_fake_calls(LL_FAKE_LL_RCC_HSE_Disable) == 1U);\n}")
FAKE_UT_FIRST = (
    "read_file software/tests/unit/test_rcc.c (GENERATED harness: CHECK(id, cond), ut_reset(), markers; never change "
    "it), software/tests/unit/ll_fake/stm32n6xx_ll_rcc.h (GENERATED test double of the provided LL API - read its "
    "'test double API' block: ll_fake_return_from(fn, n, value) makes an LL query return value from its n-th call on "
    "(default 0U = flag never set; a query of a bit an LL function writes, e.g. IsEnabled after Enable/Disable, follows "
    "that bit like the LL; IsReady-type hardware flags stay 0U until scripted), ll_fake_set_state(query_fn, value) "
    "presets the state an IsEnabled-type query reads (e.g. already enabled) without an LL call, ll_fake_calls(fn), "
    "ll_fake_index_of(fn, k) for call order, ll_fake_last_arg; never call ll_fake_internal_* (run_unit fails); never "
    "change it), software/hal/stm32n6xx_hal_rcc.h and traceability/requirements_to_tests.csv. HAL unit tests observe "
    "the HAL only through these LL calls (there is no register array); register effects are verified with the real LL "
    "in SWE.5. Count polls and order exactly as the HAL code does them and assert what the requirement states. Name "
    "every check of a test with that test's id: 'UT-007' or 'UT-007-<suffix>' inside the function tagged @test UT-007.")
UT_STEPS = [
    "read_file software/tests/unit/test_rcc.c (GENERATED harness: fake ll_rcc_regs, ut_reset_regs(), CHECK(id, cond), "
    "markers; never change it), software/hal/stm32n6xx_hal_rcc.h (the HAL_RCC_ functions to test) and "
    "traceability/requirements_to_tests.csv (the UT ids per SWR).",
    "For EACH HAL_RCC_ function (or Enable/Disable pair) make ONE edit_file call on software/tests/unit/test_rcc.c "
    "with old_string exactly '{cases}' and new_string = ONE complete static void test function with its body, a "
    "blank line, then the marker again. Never add prototypes or #define lines. Follow this example exactly (adapt "
    "names, registers and UT ids; use ONLY LL_RCC_<REG>_OFFSET / _MSK defines that exist in "
    "software/ll/stm32n6xx_ll_rcc.h - never registers from other STM32 families such as BDCR): ```{example}``` Wait-for-ready functions get a ready case and a timeout case; "
    "peripheral enable/reset functions check the bit in RCC_AHB1ENR / RCC_AHB1RSTR.",
    "Make ONE edit_file call with old_string exactly '{calls}' and new_string = one call line per test function "
    "(e.g. 'ut_hsi_enable();') followed by the marker again.",
    "Call mcp__forge_tests_mcp__run_unit once and report its summary.",
    "Reply with the list of UT ids you wrote.",
]


TARGET_MODEL = ("The simulated RCC (factory/sim/stm32n6/rcc_model.py) is behavioural: every register starts at 0 and is "
                "plain read/write storage EXCEPT RCC_SR (offset 0x004), which is read-only and always reads back "
                "RCC_CR & 0x00000F1F (ready flag = enable bit at the same position: LSI 0, LSE 1, MSI 2, HSI 3, HSE 4, "
                "PLL1..4 8..11), or 0 in scenario never_ready; writes to RCC_SR have no visible effect. Expected values "
                "in target checks follow this model.")  # CAPA-023 (r86): authors assumed RCC_SR was writable storage
PROVIDED = ("forge_target_test.h (TCHECK, FORGE_TEST_BEGIN/END, mailbox) and the Robot library ForgeTarget are provided by "
            "the factory build and run tools: do not search for them. " + TARGET_MODEL)

TARGET_STEPS = [
    "read_file software/hal/stm32n6xx_hal_rcc.h (the HAL API and its exact signatures). " + PROVIDED,
    "Target tests on the Renode STM32N6 (Cortex-M55) model: write software/tests/target/test_rcc_target.c (RCC model sets "
    "each RCC_SR ready flag when its RCC_CR enable bit is set) and software/tests/target/test_rcc_target_timeout.c (RCC "
    "model never sets ready flags: every wait must end in HAL_TIMEOUT). Each file: '#include \"stm32n6xx_hal_rcc.h\"', "
    "'#include \"forge_target_test.h\"', the line 'FORGE_MAILBOX_DEFINE;', then 'int main(void) { FORGE_TEST_BEGIN(); "
    "... FORGE_TEST_END(); return 0; }' with checks 'TCHECK(<number>, <condition>);' on HAL return values and "
    "ll_rcc_regs[LL_RCC_<REG>_OFFSET / 4U] bits. No printf, no stdlib, no ll_rcc_regs definition (the linker places it).",
    "Call mcp__forge_sim_mcp__run_renode; fix failing checks or build errors and repeat until it PASSes.",
    "Reply with the run_renode summary.",
]


ROBOT_STEPS = [
    "read_file software/tests/software/test_rcc_requirements.robot (GENERATED: one test case per SWR with its tags and "
    "the allowed keywords in its header; every body is a 'Fail    NOT IMPLEMENTED' placeholder), "
    "workproducts/SWE.1/software_requirements.md and software/hal/stm32n6xx_hal_rcc.h (exact HAL signatures). "
    + PROVIDED + " Read nothing else: no other sources, tests, reports or tools are needed in this step.",
    "Write the C scenario files software/tests/software/scn_<topic>.c (group requirements by topic, several checks per "
    "file) in the same form as the target tests: '#include \"stm32n6xx_hal_rcc.h\"', '#include \"forge_target_test.h\"', "
    "'FORGE_MAILBOX_DEFINE;', then 'int main(void) { FORGE_TEST_BEGIN(); TCHECK(<n>, <condition>); ... FORGE_TEST_END(); "
    "return 0; }' with conditions on HAL return values and ll_rcc_regs[LL_RCC_<REG>_OFFSET / 4U] & "
    "LL_RCC_<REG>_<FIELD>_MSK bits (always the _MSK macro, e.g. LL_RCC_CR_HSION_MSK; never LL_RCC_CR_HSION). No "
    "printf, no stdlib, no ll_rcc_regs definition.",
    "Rewrite software/tests/software/test_rcc_requirements.robot with ONE write_file: keep the header comment, "
    "'*** Settings ***', 'Library    ForgeTarget', every test case name and its [Tags] line exactly; replace each "
    "'Fail    NOT IMPLEMENTED' line by keywords, e.g. 'Run Target Scenario    scn_<topic>.c' then 'Target Check Should "
    "Pass    <n>' (add '    scenario=never_ready' for timeout behaviour; use 'Driver Flash Size Should Be At Most' / "
    "'Driver Static RAM Should Be At Most' / 'Driver Stack Should Be At Most' for size and stack requirements; "
    "'Target Check Should Pass    <n>' needs TCHECK(<n>, ...) in the scenario run last). Separate keyword and arguments with 4 spaces. "
    "The suite may use ONLY ForgeTarget keywords, keywords you define in the same file and Log/Should Be Equal: "
    "run_robot rejects any other library (Process, OperatingSystem), Resource/Variables imports, Evaluate, Run "
    "Keyword and inline Python expressions. Never write shell scripts.",
    "Call mcp__forge_tests_mcp__run_robot; fix build errors, UNCOVERED_REQUIREMENT and REQUIREMENT_NOT_OBSERVED "
    "issues (add exactly the named TCHECK and its 'Target Check Should Pass' line) and failing checks your test got "
    "wrong, and repeat until it PASSes - OR until the only failing checks call the driver and test exactly what the "
    "requirement names (e.g. CHECK_EXPR 'rc == HAL_ERROR with rc = HAL_RCC_...(...)' for 'shall return HAL_ERROR'). "
    "Then STOP editing: such a check is the evidence of a driver defect - never change, weaken or remove it; apply "
    "the defect rule below (report_defect kind CODE).",
    "Reply with the run_robot summary.",
]


def robot_test_author_prompt() -> str:
    """SWE.6 step 1 (fresh context): Robot requirement tests written and made to pass before the report author (r56)."""
    robot = LL_ROBOT_STEPS if _layer() == "LL" else ROBOT_STEPS
    steps = ["Call use_skill with skill_name swe6-author.", READ, small()] + robot + trace_step("vt") + [DEFECT_RULE] + \
        [REPLY]
    return " ".join(f"{i}) {s}" for i, s in enumerate(steps, 1))


def target_test_author_prompt() -> str:
    """SWE.5 step 1 (fresh context): Renode target tests written and made to pass before the integration author."""
    target = LL_TARGET_STEPS if _layer() == "LL" else TARGET_STEPS
    steps = ["Call use_skill with skill_name swe5-author.", READ, small()] + target + trace_step("tt") + [DEFECT_RULE] + \
        [REPLY]
    return " ".join(f"{i}) {s}" for i, s in enumerate(steps, 1))


def unit_test_author_prompt() -> str:
    """SWE.4 step 1 (fresh context): unit tests inserted into the generated harness in small edits."""
    from .scaffold import TEST_CALLS_MARKER, TEST_CASES_MARKER

    ut, example = (LL_UT_STEPS, LL_UT_EXAMPLE) if _layer() == "LL" else (UT_STEPS, UT_EXAMPLE)
    if ISOLATION["on"] and _layer() == "HAL":  # CAPA-038
        ut, example = [FAKE_UT_FIRST] + [x.replace("adapt names, registers and UT ids; use ONLY LL_RCC_<REG>_OFFSET / "
                                                  "_MSK defines that exist in software/ll/stm32n6xx_ll_rcc.h - never "
                                                  "registers from other STM32 families such as BDCR",
                                                  "adapt names and UT ids; use ONLY LL_FAKE_<LL function> ids from the "
                                                  "test double") for x in UT_STEPS[1:]], FAKE_UT_EXAMPLE
    steps = ["Call use_skill with skill_name swe4-author.", READ, small()] + \
        [x.replace("{cases}", TEST_CASES_MARKER).replace("{calls}", TEST_CALLS_MARKER).replace("{example}", example)
         for x in ut] + trace_step("ut") + [DEFECT_RULE, REPLY]
    return " ".join(f"{i}) {s}" for i, s in enumerate(steps, 1))


FIX3_STEPS = [
    "read_file software/hal/stm32n6xx_hal_rcc.h and software/hal/stm32n6xx_hal_rcc.c (the LL header register defines "
    "are machine-verified; read the LL header only if a compile error points into it). Never change the generated "
    "register defines.",
    "Call mcp__forge_build_mcp__compile with profile target-cm55-gcc, then with profile host-clang. Fix each error with "
    "an edit_file call (old_string = the exact lines to replace), then compile again. For 'no newline at end of file' "
    "replace the last line (e.g. the final #endif line) with the same text followed by a line break.",
    "Call mcp__forge_docs_mcp__validate_artifact with check swe3_all (HAL guideline + register map + implementation "
    "completeness in ONE call); fix every finding and repeat until it PASSes; re-compile after changes.",
    "Call mcp__forge_analysis_mcp__cppcheck; fix EVERY reported finding (MISRA and general/style) by restructuring the "
    "code, e.g. rule 15.5: one return at the end using a status variable; style variableScope: declare the variable in "
    "the innermost block that uses it; rule 11.9: NULL as null pointer constant; never add suppression comments. "
    "Repeat cppcheck until it PASSes, then re-run "
    "compile and swe3_all.",
    "Reply PASS only when both compiles, swe3_all and cppcheck PASS.",
]


TRIAGE_READ = {1: "workproducts/SWE.1/software_requirements.md",
               2: "workproducts/SWE.1/software_requirements.md and workproducts/SWE.2/software_architecture.md",
               3: "workproducts/SWE.1/software_requirements.md and software/hal/stm32n6xx_hal_rcc.h"}


# ---- ADR-0009: LL-only work order (header-only register access; the HAL is a later, separate work order) --------
LL_UT_EXAMPLE = ("static void ut_hsi(void)\n{\n    ut_reset_regs();\n"
                 "    ll_rcc_regs[LL_RCC_CR_OFFSET / 4U] = LL_RCC_CR_HSEON_MSK;\n    LL_RCC_HSI_Enable();\n"
                 "    CHECK(\"UT-001\", ((ll_rcc_regs[LL_RCC_CR_OFFSET / 4U] & LL_RCC_CR_HSION_MSK) != 0U) &&\n"
                 "          ((ll_rcc_regs[LL_RCC_CR_OFFSET / 4U] & LL_RCC_CR_HSEON_MSK) != 0U));\n"
                 "    CHECK(\"UT-002\", LL_RCC_HSI_IsReady() == 0U);\n"
                 "    ll_rcc_regs[LL_RCC_SR_OFFSET / 4U] = LL_RCC_SR_HSIRDY_MSK;\n"
                 "    CHECK(\"UT-003\", LL_RCC_HSI_IsReady() == 1U);\n}")
LL_API = ("static inline functions named exactly LL_RCC_<Name>_Enable, LL_RCC_<Name>_Disable, LL_RCC_<Name>_IsReady "
          "(oscillators: ready flag in RCC_SR), LL_RCC_<Name>_IsEnabled (peripheral clocks), "
          "LL_RCC_<Name>_ForceReset and LL_RCC_<Name>_ReleaseReset (peripheral resets), where <Name> is HSI or HSE "
          "(the oscillators in the work-order scope; never MSI, LSI, LSE or PLLs) or a peripheral of the provided "
          "RM sections; all take (void); Enable/Disable/Reset return void, IsReady/IsEnabled return uint32_t 1U or "
          "0U; list in Interfaces exactly the functions of the allocation table")
LL_AUTHOR_STEPS = {
    "SWE.1": [
        "read_file these RM0486 section files: {s1}.",
        "write_file workproducts/SWE.1/software_requirements.md: a '# Software requirements' title, then 12-26 requirements "
        "for the header-only RCC LL driver (register access only: no waiting, no timeouts, no parameters, no error "
        "codes - a separate HAL work order adds those later), one per line exactly like: - **SWR-001** When the HSI "
        "enable function is called, the RCC LL driver shall set RCC_CR.HSION. Each statement uses EARS "
        "(The/When/While/Where/If..then), exactly one 'shall', the system name 'RCC LL driver', and ends with a period. "
        "Put '  - Source: RM0486 p.<page>' and '  - Verification: <test method and pass criterion>' on the next lines "
        "under each requirement, and end the file with '## Open points' listing unresolved ambiguities (or 'none'). "
        "Cover: oscillator enable/disable (set/clear the enable bit), ready-flag queries (return 1U when the RCC_SR flag "
        "is set, else 0U), and for EACH peripheral bit documented in the RCC_AHB1ENR and RCC_AHB1RSTR section files "
        "(name the peripheral and the bit, e.g. RCC_AHB1ENR.GPDMA1EN - never 'the named bit of the addressed "
        "register') one requirement each for clock enable, clock disable, clock is-enabled query, reset assert and "
        "reset release; then that every "
        "write changes only the named bit and preserves all other bits of the register, and a reset/startup "
        "requirement (e.g. '- **SWR-0nn** While no LL function has been called after reset, the RCC LL driver shall "
        "not write any RCC register.'). Add three measurable resource requirements from the .forge-run/manifest.json "
        "budgets (flash, static RAM - the LL driver keeps no state - and stack) with '  - Source: work-order budget "
        "(owner development target)'. Every requirement must be verifiable by a host or target test that checks "
        "register bits and return values on the register array, or by the size/stack tools: never require a "
        "count of register accesses or other internal behaviour a RAM register array cannot observe.",
        AUTHOR_STEPS["SWE.1"][2], AUTHOR_STEPS["SWE.1"][3], AUTHOR_STEPS["SWE.1"][4], AUTHOR_STEPS["SWE.1"][5],
        AUTHOR_STEPS["SWE.1"][6]],
    "SWE.2": [
        "Read workproducts/SWE.1/software_requirements.md and these RM0486 section files: {s1}.",
        "write_file workproducts/SWE.2/software_architecture.md with sections: Components (only the LL header-only "
        "stm32n6xx_ll_rcc.h; no HAL in this work order - a later HAL work order builds on this LL), Register access "
        "(extern volatile uint32_t register-block array placed at the RCC base by the linker, indexed by offset/4; no "
        "integer-to-pointer casts; host tests define the array; read-modify-write that preserves other bits), "
        "Interfaces (each LL_RCC_ API: " + LL_API + "; one concrete function per oscillator and per peripheral, e.g. "
        "LL_RCC_GPDMA1_Enable - never a placeholder such as LL_RCC_<Peripheral>_Enable), Timing and error handling (no waiting and no error codes at "
        "LL level: each function is one register access; callers bound their own polling), Memory and stack budget "
        "(flash<=4096 B, RAM 0 B: no state, stack<=128 B), Concurrency and reentrancy (the LL keeps no state and is "
        "reentrant; a read-modify-write of a shared RCC register is not atomic: state whether the documented "
        "set/clear registers are used for atomic single-bit writes or that callers serialise access, e.g. in a "
        "critical section, and that no LL function is called from an ISR concurrently with the same register), "
        "Requirement allocation table (SWR -> the concrete LL_RCC_ "
        "function(s); a requirement on all functions lists them or says 'all LL functions'), "
        "and a Register table with one row per register/bit used: name | offset | bit position(s) | access | RM0486 "
        "page. RCC base address 0x56028000 (RM0486 p.176). SWE.3 will implement only from this table.",
        AUTHOR_STEPS["SWE.2"][2],
        "write_file workproducts/SWE.2/architecture_static.puml: PlantUML component view between '@startuml' and "
        "'@enduml' with a Caller, the component stm32n6xx_ll_rcc (LL, header-only) and the RCC register block "
        "(0x56028000) and their dependencies (Caller -> LL -> registers).",
        "write_file workproducts/SWE.2/architecture_dynamic.puml: PlantUML sequence view(s) between '@startuml' and "
        "'@enduml' with participants Caller, stm32n6xx_ll_rcc, RCC, showing an oscillator enable followed by the "
        "caller polling the LL ready query (the caller bounds the loop), plus a peripheral clock enable and a reset "
        "assert/release sequence, using the allocated LL_RCC_ function names.",
        AUTHOR_STEPS["SWE.2"][5], AUTHOR_STEPS["SWE.2"][6]],
    "SWE.3": [AUTHOR_STEPS["SWE.3"][0],
              AUTHOR_STEPS["SWE.3"][1].replace("then mcp__forge_build_mcp__measure_elf", "then "
                                               "mcp__forge_build_mcp__measure_elf (the generated compile unit "
                                               "software/src/stm32n6xx_ll_rcc.c includes the header-only LL)"),
              "write_file workproducts/SWE.3/detailed_design.md: '# Detailed design'; a table | Function | Purpose | "
              "Registers/bits (RM0486 page) | SWR IDs | with one row per LL_RCC_ function; '## Static analysis and "
              "MISRA (subset)' with the cppcheck and clang results exactly as the tools reported them (rules hit, "
              "counts; state that MISRA compliance is not claimed); '## Resource usage' with the measured flash/RAM "
              "(measure_elf) and maximum stack frame (stack_usage) of the compile unit next to the architecture "
              "budgets, noting that header-only inline code is accounted at its call sites.",
              AUTHOR_STEPS["SWE.3"][3]],
    "SWE.4": AUTHOR_STEPS["SWE.4"],
    "SWE.5": [
        "Read workproducts/SWE.2/software_architecture.md, software/ll/stm32n6xx_ll_rcc.h and software/tests/unit/test_rcc.c.",
        "write_file software/tests/integration/test_rcc_integration.c: self-checking host program (define "
        "'volatile uint32_t ll_rcc_regs[LL_RCC_REG_COUNT];' and a CHECK macro like the unit harness) exercising the LL "
        "sequences a HAL will use: oscillator enable then a bounded poll of the ready query with the flag preset, the "
        "same poll ending without ready when the flag is never set, peripheral clock enable then reset assert and "
        "release, and that operations on different groups preserve each other's bits.",
        AUTHOR_STEPS["SWE.5"][2], AUTHOR_STEPS["SWE.5"][3],
        AUTHOR_STEPS["SWE.5"][4].replace("(timeout paths, measured sizes)", "(bounded polling by the caller, "
                                         "measured sizes)"),
        AUTHOR_STEPS["SWE.5"][5]],
    "SWE.6": [AUTHOR_STEPS["SWE.6"][0],
              AUTHOR_STEPS["SWE.6"][1].replace("'rc == HAL_ERROR with rc = HAL_RCC_...(...)'",
                                               "'r == 1U with r = LL_RCC_..._IsReady()'"),
              AUTHOR_STEPS["SWE.6"][2],
              AUTHOR_STEPS["SWE.6"][3].replace("safety allocation out of scope by owner decision",
                                               "safety allocation out of scope by owner decision, HAL not part of "
                                               "this work order"),
              AUTHOR_STEPS["SWE.6"][4]],
}
LL_LL_STEPS = [
    LL_STEPS[0],
    "For EACH function group of the SWE.2 Requirement allocation table make ONE edit_file call (or several groups "
    "per call, see the size rule) on software/ll/stm32n6xx_ll_rcc.h with old_string exactly '{marker}' and "
    "new_string = that group's functions, a blank line, then the same marker line again (so the next group can be "
    "inserted). Interfaces: " + LL_API + ". Each body is one statement on ll_rcc_regs[LL_RCC_<REG>_OFFSET / 4U] using "
    "only the generated _MSK defines: Enable/ForceReset '|= MSK', Disable/ReleaseReset '&= ~MSK', IsReady/IsEnabled "
    "'return ((ll_rcc_regs[...] & MSK) != 0U) ? 1U : 0U;'. Implement exactly the allocated functions, no more: no helper functions, no HAL_ names, no loops or waiting (swe3_all fails IMPL:LL_NOT_ALLOCATED / HAL_CODE_IN_LL / LL_WAITS). Real "
    "line breaks only.",
    "Call mcp__forge_docs_mcp__validate_artifact with check swe3_all (register map + guideline + every allocated "
    "LL_RCC_ function defined) and fix what it reports; it must be PASS.",
    "Reply with the list of LL_RCC_ function names you declared.",
]
LL_FIX3_STEPS = [
    "read_file software/ll/stm32n6xx_ll_rcc.h (the access functions after the register defines). Never change the "
    "generated register defines or software/src/stm32n6xx_ll_rcc.c (generated compile unit).",
    *FIX3_STEPS[1:],
]
LL_UT_STEPS = [
    "read_file software/tests/unit/test_rcc.c (GENERATED harness: fake ll_rcc_regs, ut_reset_regs(), CHECK(id, cond), "
    "markers; never change it), software/ll/stm32n6xx_ll_rcc.h (the LL_RCC_ functions to test) and "
    "traceability/requirements_to_tests.csv (the UT ids per SWR).",
    "For EACH LL_RCC_ function group make ONE edit_file call on software/tests/unit/test_rcc.c with old_string exactly "
    "'{cases}' and new_string = ONE complete static void test function with its body, a blank line, then the marker "
    "again. Never add prototypes or #define lines. Follow this example exactly (adapt names, registers and UT ids; use "
    "ONLY LL_RCC_<REG>_OFFSET / _MSK defines that exist in software/ll/stm32n6xx_ll_rcc.h): ```{example}``` "
    "Enable/Disable and ForceReset/ReleaseReset cases check the named bit AND that a preset unrelated bit of the same "
    "register is preserved; IsReady/IsEnabled get a flag-set and a flag-clear case.",
    UT_STEPS[2], UT_STEPS[3], UT_STEPS[4],
]
LL_TARGET_STEPS = [
    "read_file software/ll/stm32n6xx_ll_rcc.h (the LL API and its exact names). " + PROVIDED,
    "Target tests on the Renode STM32N6 (Cortex-M55) model: write software/tests/target/test_rcc_target.c (RCC model sets "
    "each RCC_SR ready flag when its RCC_CR enable bit is set: Enable then a poll of at most 1000 iterations sees "
    "IsReady() == 1U; Disable clears the enable bit) and software/tests/target/test_rcc_target_timeout.c (RCC model "
    "never sets ready flags: after Enable, IsReady() stays 0U for 1000 polls). Each file: '#include "
    "\"stm32n6xx_ll_rcc.h\"', '#include \"forge_target_test.h\"', the line 'FORGE_MAILBOX_DEFINE;', then 'int "
    "main(void) { FORGE_TEST_BEGIN(); ... FORGE_TEST_END(); return 0; }' with checks 'TCHECK(<number>, <condition>);' "
    "on LL return values and ll_rcc_regs[LL_RCC_<REG>_OFFSET / 4U] bits. No printf, no stdlib, no ll_rcc_regs "
    "definition (the linker places it).",
    TARGET_STEPS[2], TARGET_STEPS[3],
]
LL_ROBOT_STEPS = [x.replace("software/hal/stm32n6xx_hal_rcc.h (exact HAL signatures)",
                            "software/ll/stm32n6xx_ll_rcc.h (exact LL names)")
                  .replace("'#include \"stm32n6xx_hal_rcc.h\"'", "'#include \"stm32n6xx_ll_rcc.h\"'")
                  .replace("conditions on HAL return values", "conditions on LL return values")
                  .replace("(e.g. CHECK_EXPR 'rc == HAL_ERROR with rc = HAL_RCC_...(...)' for 'shall return HAL_ERROR')",
                           "(e.g. CHECK_EXPR 'r == 1U with r = LL_RCC_..._IsReady()' for 'shall return 1U')")
                  for x in ROBOT_STEPS]
HAL_ON_PROVIDED_LL = ("The LL header software/ll/stm32n6xx_ll_rcc.h is PROVIDED read-only by an earlier, verified LL "
                      "work order (.forge-run/manifest.json 'provided'): never write or edit it; use only the LL_RCC_ "
                      "functions it already declares.")


def _layer() -> str:
    return LAYER["layer"]


def _t() -> tuple[str, str]:
    """(unit/spec id infix, developed SWC) of this work order."""
    return ("LL", "SWC_LL") if _layer() == "LL" else ("HAL", "SWC_HAL")


def trace_step(kind: str) -> list[str]:
    """Owner trace rules, only for work orders prepared with the owner trace profile (deterministically gated)."""
    if not TRACE["on"]:
        return []
    x, swc = _t()
    other = "the PROVIDED LL as SWC_LL (no allocation to it)" if _layer() == "HAL" else "no SWC_HAL"
    rules = {
        "swe2": "OWNER TRACE RULES (gate-checked, ARCH:* issues): in workproducts/SWE.2/architecture_static.puml the LL "
                "and the HAL are separate components, each exactly ONE element with the <<SWC>> stereotype - "
                f"'component \"RCC_{x}\\nstm32n6xx_{x.lower()}_rcc\" <<SWC>> as {swc}' (keep the module name "
                f"stm32n6xx_{x.lower()}_rcc in the label: the view check requires it) and {other}. Allocate EVERY SWR of "
                f"workproducts/SWE.1/software_requirements.md to {swc} with a note IN the diagram: 'note right of {swc}', "
                "'Allocated: SWR-001, SWR-002, ...', 'end note'. Label EVERY connection with a unique interface id, e.g. "
                f"'{swc} --> RCC : IF-01 register access'" + (" and 'SWC_HAL --> SWC_LL : IF-01 LL_RCC_* accessors'"
                                                           if _layer() != "LL" else "") + ". The gate generates "
                "workproducts/SWE.2/traceability/matrix_1_swr_to_architecture.csv.",
        "code": f"OWNER TRACE RULES: software units are the function groups of the SWE.2 allocation table (unit ids "
                f"SWU-{x}-01, SWU-{x}-02, ... in table order; one unit per group, e.g. HSI, HSE, ADC12, GPDMA1). Put a "
                "Doxygen block directly above EVERY function definition you write, in the same edit: '/**', ' * @brief "
                f"<one line>', ' * @unit SWU-{x}-01', ' * @spec USPEC-{x}-01-01', ' */' - number the spec items of a "
                f"unit USPEC-{x}-<unit nn>-01, -02, ... (one item per distinct behaviour: set, clear, query, wait, "
                "error). Static helper functions belong to the unit that calls them and get the same block.",
        "keep": "Keep every Doxygen /** ... @unit ... @spec ... */ block above its function when you edit code.",
        "swe3": "OWNER TRACE RULES (gate-checked, UNIT:*/CODE:* issues): the factory GENERATED "
                "workproducts/SWE.3/unit_specifications.md, one as-built PlantUML design per unit under "
                "workproducts/SWE.3/detailed_design/ and workproducts/SWE.3/misra_deviations.md from the code tags and "
                "tool results. Replace EVERY 'TODO' in unit_specifications.md (one edit_file per unit): each spec item gets "
                "the behaviour text and 'Traces: SWR-...'. You may refine the designs; the gate adds each design's "
                "USPEC citation itself. Do not rewrite these files from scratch. Resource budgets (flash/RAM/stack) "
                "and initial-state invariants ('While no ... has been called ...') are component-level: do NOT create "
                "units or functions for them and never edit "
                "software/src/stm32n6xx_ll_rcc.c (generated). Format reference: "
                f"for each unit '## SWU-{x}-nn: <name>', "
                f"'- SWC: {swc}', '- Functions: <exact C function names of the unit, incl. static helpers>', '- Design: "
                f"workproducts/SWE.3/detailed_design/SWU-{x}-nn.puml' and one line per spec item used in the code: "
                f"'- **USPEC-{x}-nn-mm** <the behaviour the unit shall implement> Traces: SWR-001, SWR-003' (only SWRs "
                f"allocated to {swc} in the architecture diagram; every allocated SWR is traced by at least one item). "
                "For EACH unit write_file workproducts/SWE.3/detailed_design/<unit id>.puml: a PlantUML activity "
                "diagram between @startuml and @enduml whose title contains the unit id and which names every function "
                "of the unit. The gate generates workproducts/SWE.3/unit_specifications/<unit>.reqif, runs Doxygen and "
                "writes workproducts/SWE.3/traceability/matrix_2 and matrix_3.",
        "ut": "OWNER TRACE RULES: directly above each test function put '/** @test UT-00n @verifies USPEC-...-.. */' "
              "with the UT id its CHECKs print and the unit specification items (workproducts/SWE.3/unit_"
              "specifications.md) it verifies. Every USPEC item must be verified by a passing test (UT:* issues).",
        "tt": "OWNER TRACE RULES: start each target test file with '/** @file <file name> @verifies IF-01 IF-02 */' "
              "naming the architecture interfaces (IF ids of workproducts/SWE.2/architecture_static.puml) it exercises.",
        "it": "OWNER TRACE RULES: directly above each integration test function put '/** @test IT-00n @verifies IF-01 "
              f"{swc} */' (interface ids and SWCs of workproducts/SWE.2/architecture_static.puml); the CHECK ids it "
              "prints start with that IT id. Every interface must be verified by a passing integration or target test "
              "(IT:* issues; matrix 5).",
        "vt": "OWNER TRACE RULES: every Robot test keeps its SWR tag; every SWR needs a passing test (VT:* issues; "
              "matrix 6).",
    }
    return [rules[kind]]


def triage_prompt(k: int) -> str:
    """ADR-0008 L12: the upstream owner judges routed defects in a small, edit-free step before any fix."""
    steps = [f"Call use_skill with skill_name swe{k}-author.",
             f"This step only TRIAGES defects routed to SWE.{k}; use at most 8 tool calls and do NOT write or edit any "
             "file (a later step fixes accepted defects).",
             f"glob .forge-run/defects/DEF-*.json and read every defect with target_phase SWE.{k} and status IN_FIX.",
             f"read_file {TRIAGE_READ[k].replace('software/hal/stm32n6xx_hal_rcc.h', 'software/ll/stm32n6xx_ll_rcc.h') if _layer() == 'LL' else TRIAGE_READ[k]}.",
             "For each defect: if the requirement AS WRITTEN demands what the defect asks and your phase's work product "
             "does not provide it, ACCEPT it (do nothing). Otherwise - the requirement does not demand it, contradicts "
             "it, or the downstream test calls something the requirement never asked for - call "
             "mcp__forge_evidence_mcp__reject_defect with defect_id and a reason that quotes the requirement.",
             'Finish with ONLY this JSON: {"status":"PASS","artifacts":[],"issues":["DEF-nnn ACCEPTED|REJECTED"],'
             '"next_action":"next"}']
    return " ".join(f"{i}) {s}" for i, s in enumerate(steps, 1))


def fix3_author_prompt() -> str:
    """SWE.3 fix step (rework entry): make the code compile on both profiles and pass the deterministic checks."""
    steps = ["Call use_skill with skill_name swe3-author.", READ, small(), FIX.format(p="SWE.3"),
             FIX_DEFECTS.format(p="SWE.3")] + (LL_FIX3_STEPS if _layer() == "LL" else FIX3_STEPS) + \
        ([HAL_ON_PROVIDED_LL] if _layer() == "HAL" else []) + trace_step("keep") + [REPLY]
    return " ".join(f"{i}) {s}" for i, s in enumerate(steps, 1))


def ll_author_prompt() -> str:
    """SWE.3 step 1 (fresh, small context): LL access functions on the generated register map; HAL comes next."""
    from ..inspection.regmap import FUNCTIONS_MARKER

    steps = ["Call use_skill with skill_name swe3-author.", READ, small()] + \
        [x.replace("{marker}", FUNCTIONS_MARKER) for x in (LL_LL_STEPS if _layer() == "LL" else LL_STEPS)] + \
        (trace_step("code") + [CONTRACT_SWE3] if _layer() == "LL" else []) + [REENTRY] + [REPLY]
    return " ".join(f"{i}) {s}" for i, s in enumerate(steps, 1))


def hal_author_prompt() -> str:
    """SWE.3 step 2 (fresh context): HAL header/source built incrementally in small edits against the LL header."""
    steps = ["Call use_skill with skill_name swe3-author.", READ, small()] + \
        [x.replace("{marker}", HAL_MARKER).replace("{hmarker}", HAL_H_MARKER).replace("{hal_example}", HAL_EXAMPLE)
         for x in HAL_STEPS] + ([HAL_ON_PROVIDED_LL] if _layer() == "HAL" else []) + trace_step("code") + \
        [CONTRACT_SWE3, REENTRY] + \
        [REPLY]
    return " ".join(f"{i}) {s}" for i, s in enumerate(steps, 1))


# owner decision 2026-10-19 (option B): the independent EASA oracle reads this contract, never the code
CONTRACT_SWE1 = (
    "write_file workproducts/SWE.1/register_effects.json (machine-readable register contract of your requirements; an "
    "independent oracle tests the code against it): {{\"schema\":\"forge-c/register-effects/1\",\"effects\":[...]}} "
    "with one entry per tested case of EVERY requirement that sets or clears a register bit - one entry per bit and "
    "per oscillator/peripheral/function (HSI enable and HSE enable are two entries), e.g. {example}. 'register' and "
    "'field' are the RM0486 names your requirement text uses; op is set, clear or no_write.{extra} Every case id is "
    "unique UPPER_CASE. Never add an entry the requirement text does not state.")
CONTRACT_SWE1_HAL = (
    " Oscillator enable: \"ready\":\"RCC_SR.<FLAG>RDY\" and status HAL_OK; ready timeout: op clear (the driver "
    "clears the enable bit it set), \"ready\":\"never\", status HAL_TIMEOUT; invalid parameter: one entry per invalid "
    "value (NULL pointer, unknown selector, timeout 0, timeout above HAL_RCC_TIMEOUT_VALUE) with op no_write and status "
    "HAL_ERROR (no register/field); reset (assert then release): op clear on the reset bit with status HAL_OK.")
CONTRACT_SWE1_LL = " LL functions return nothing: no status and no ready; reset assert is set, release is clear."
CONTRACT_SWE2 = (
    "write_file workproducts/SWE.2/api_calls.json: {{\"schema\":\"forge-c/api-calls/1\",\"calls\":{{\"<case>\":"
    "{{\"function\":\"<function>\",\"args\":[...]}}}}}} with one entry per case of "
    "workproducts/SWE.1/register_effects.json: function = one your allocation table allocates to that case's SWR; args "
    "= C argument expressions using only the interface types and constants you define in Interfaces{example} - no "
    "function calls, no ';'. SWE.3 must implement the interface so that these calls compile.")
CONTRACT_SWE3 = ("Implement the interface exactly as workproducts/SWE.2/api_calls.json calls it (names, types, "
                 "constants): the gate compiles those calls against your header.")


def contract_step(phase: str) -> list[str]:
    hal = _layer() != "LL"
    if phase == "SWE.1":
        ex = ('{\"case\":\"HSE_ENABLE\",\"swr\":\"SWR-002\",\"register\":\"RCC_CR\",\"field\":\"HSEON\",'
              '\"op\":\"set\",\"ready\":\"RCC_SR.HSERDY\",\"status\":\"HAL_OK\"}' if hal else
              '{\"case\":\"HSI_ENABLE\",\"swr\":\"SWR-001\",\"register\":\"RCC_CR\",\"field\":\"HSION\",'
              '\"op\":\"set\"}')
        return [CONTRACT_SWE1.format(example=ex, extra=CONTRACT_SWE1_HAL if hal else CONTRACT_SWE1_LL)]
    if phase == "SWE.2":
        ex = (', e.g. \"&(const hal_rcc_osc_config_t){ .oscillator = HAL_RCC_OSC_HSE }\" and \"{timeout}\" where '
              'the caller passes the timeout; invalid cases pass the invalid value (NULL, 0U, HAL_RCC_TIMEOUT_VALUE + 1U, '
              'an unknown selector)' if hal else ' (LL functions take no arguments: args [])')
        return [CONTRACT_SWE2.format(example=ex)]
    if phase == "SWE.3":
        return [CONTRACT_SWE3]
    return []


def author_prompt(phase: str) -> str:
    n = phase[-1]
    fills = {"s1": sec("14.10.1", "14.10.2", "14.10.79", "14.10.64")}
    table = LL_AUTHOR_STEPS if _layer() == "LL" else AUTHOR_STEPS
    body = [x.format(**fills) if "{s" in x else x for x in table[phase]]
    if _layer() == "HAL" and phase == "SWE.2":  # ADR-0009: the HAL is designed on the PROVIDED, frozen LL
        body = [x.replace("Read workproducts/SWE.1/software_requirements.md and",
                          "Read workproducts/SWE.1/software_requirements.md, software/ll/stm32n6xx_ll_rcc.h (PROVIDED "
                          "LL, frozen) and")
                 .replace("Components (LL header-only stm32n6xx_ll_rcc.h, HAL stm32n6xx_hal_rcc.c/.h)",
                          "Components (PROVIDED LL header-only stm32n6xx_ll_rcc.h from the verified LL work order - the "
                          "HAL calls only the LL_RCC_ functions it declares; HAL stm32n6xx_hal_rcc.c/.h)")
                 for x in body]
    manifest = [] if phase in ("SWE.3", "SWE.4") else ["read_file .forge-run/manifest.json."]  # saves turn budget
    extra = [FIX_DEFECTS.format(p=phase)] if phase in ("SWE.1", "SWE.2") else \
        [DEFECT_RULE] if phase in ("SWE.4", "SWE.5", "SWE.6") else []
    tr = {"SWE.2": "swe2", "SWE.3": "swe3", "SWE.4": "ut", "SWE.5": "it", "SWE.6": "vt"}.get(phase)
    if tr and trace_step(tr):  # owner trace rules go before the final 'gate freezes the baseline' step
        body = body[:-1] + trace_step(tr) + body[-1:]
    if contract_step(phase):  # owner decision 2026-10-19 (B), also before the final step
        body = body[:-1] + contract_step(phase) + body[-1:]
    steps = [f"Call use_skill with skill_name swe{n}-author.", READ] + manifest + [FIX.format(p=phase)] + extra + body \
        + [REPLY]
    return " ".join(f"{i}) {s}" for i, s in enumerate(steps, 1))


def inspector_prompt(phase: str) -> str:
    n = phase[-1]
    items = "; ".join(f"{c['id']}: {c['criterion'][:70]}" for c in load_checklist(phase)["checks"])
    example = "; ".join(f"{c['id']}=PASS" for c in load_checklist(phase)["checks"][:2])
    steps = [f"Call use_skill with skill_name swe{n}-inspector.",
             f"glob configuration/baselines/{phase}/BL-*.json and read the newest one: note its baseline_id and files.",
             "read_file each listed workproduct (use offset/limit for long files). Never edit any file. You have at most 20 "
             "tool calls: do not re-run analyzers or validators (items with a deterministic_check are recomputed "
             "automatically; their reports are in verification/static/ and inspection/<phase>/deterministic/), and call "
             "check_inspection no later than your 15th tool call.",
             f"read_file .forge-run/checklists/{phase}.json once (the full checklist; it is NOT elsewhere, do not "
             f"search for it). Judge each checklist item: {items}.",
             *([INSPECT_DEFECT] if phase != "SWE.1" else [OWNER_SCOPE_NOTE]),
             *([GATE_DECLARED_CHECK.format(p=phase)] if phase in ("SWE.4", "SWE.5", "SWE.6") else []),
             *([WORK_ORDER_SCOPE_NOTE] if phase in ("SWE.4", "SWE.5", "SWE.6") else []),
             f"Call mcp__forge_evidence_mcp__check_inspection with phase {phase}, baseline_id <id>, and verdicts as ONE plain "
             f"string covering EVERY item, e.g. \"{example}; ...\" and for a failed item ID=FAIL:<short finding>. "
             "Items decided by deterministic tools are recomputed automatically.",
             'Finish with ONLY JSON: {"status":"PASS" or "REWORK","artifacts":["inspection/' + phase +
             '/<INS id>.json"],"issues":["<item id: finding>"],"next_action":"next" or "rework"}']
    return " ".join(f"{i}) {s}" for i, s in enumerate(steps, 1))
