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
               "the same test file: that withdraws your defect.")
INSPECT_DEFECT = ("If a finding is caused upstream (driver code, architecture or requirement - not in this phase's "
                  "work products), also record it with mcp__forge_evidence_mcp__report_defect (kind CODE, "
                  "ARCHITECTURE or REQUIREMENT, requirement_ids, summary; for CODE and ARCHITECTURE requirement_quote "
                  "= the clause copied verbatim) before check_inspection.")

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
        "the next lines under each requirement, and end the file with '## Open points' listing unresolved ambiguities "
        "(or 'none'). Add three measurable "
        "resource requirements from the .forge-run/manifest.json budgets, e.g. '- **SWR-0nn** The RCC driver shall occupy "
        "at most 4096 bytes of flash.' (likewise static RAM and stack), with '  - Source: work-order budget (owner "
        "development target)'. Add reset/startup requirements phrased as RCC driver behaviour with 'the RCC driver' as "
        "subject (e.g. '- **SWR-0nn** While no oscillator enable has been requested after reset, the RCC driver shall "
        "leave RCC_CR.HSEON at its reset value 0.'), one requirement per failure response (ready timeout -> the driver clears the "
        "enable bit it set (driver fallback state: oscillator/clock off) and returns HAL_TIMEOUT; invalid parameter -> "
        "HAL_ERROR without register writes), and one measurable timing "
        "requirement (every wait is bounded by HAL_RCC_TIMEOUT_VALUE = 1000 polling iterations).",
        "write_file safety/software_safety_requirements.md: if the manifest target safety_allocation is OUT_OF_SCOPE, state "
        "'QM development scope: no software safety requirements are allocated (work-order owner decision)' and list no "
        "safety items; otherwise list the safety-relevant SWR IDs.",
        "If inputs/upstream-inputs.yaml exists (human-approved HSI contract, safety allocation, budgets), read it and write "
        "one requirement per allocated software safety requirement with '  - Source: <SSR id>'. write_file "
        "traceability/upstream_gaps.md: '# Upstream coverage', (a) one row per upstream input from the manifest target "
        "(HSI contract, safety allocation, budgets): input | status as stated in the manifest | affected SWR IDs, and (b) "
        "a bidirectional trace table: upstream id (RM0486-<section number> or WO-BUDGET) | SWR IDs, plus for every SWR its "
        "upstream id. Never invent an allocation.",
        "write_file traceability/requirements_to_tests.csv with header requirement_id,test_id,test_file and one row per SWR "
        "(test_id UT-001.., test_file software/tests/unit/test_rcc.c).",
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
        "write_file traceability/requirements_to_tests.csv: header requirement_id,test_id,test_file and one row per SWR "
        "with a UT id that really appears in a CHECK of software/tests/unit/test_rcc.c (never cite an id that is not "
        "tested; add the missing test first). Then call mcp__forge_evidence_mcp__validate_trace and fix until PASS.",
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
        "silicon verification) and '## Open defects' (or 'none').",
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
    "timeout or config parameter, use it instead of HAL_RCC_TIMEOUT_VALUE and check pointer parameters for NULL first, "
    "returning HAL_ERROR): ```{hal_example}``` Disable functions wait until IsReady() == 0U the same "
    "way; peripheral clock enable/disable and reset functions call the LL function and return HAL_OK.",
    "Call mcp__forge_docs_mcp__validate_artifact with check swe3_all and fix what it reports (missing functions, guideline "
    "naming such as hal_ prefixed lower-case types ending _t) before replying.",
    "Reply with the list of HAL_RCC_ functions you implemented.",
]


UT_EXAMPLE = ("static void ut_hsi_enable(void)\n{\n    hal_status_t st;\n    ut_reset_regs();\n"
              "    ll_rcc_regs[LL_RCC_SR_OFFSET / 4U] = LL_RCC_SR_HSIRDY_MSK;\n    st = HAL_RCC_HSI_Enable();\n"
              "    CHECK(\"UT-001\", (st == HAL_OK) && ((ll_rcc_regs[LL_RCC_CR_OFFSET / 4U] & LL_RCC_CR_HSION_MSK) != 0U));\n"
              "    ut_reset_regs();\n    st = HAL_RCC_HSI_Enable();\n    CHECK(\"UT-002\", st == HAL_TIMEOUT);\n}")
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


PROVIDED = ("forge_target_test.h (TCHECK, FORGE_TEST_BEGIN/END, mailbox) and the Robot library ForgeTarget are provided by "
            "the factory build and run tools: do not search for them.")

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
    steps = ["Call use_skill with skill_name swe6-author.", READ, small()] + ROBOT_STEPS + [DEFECT_RULE] + [REPLY]
    return " ".join(f"{i}) {s}" for i, s in enumerate(steps, 1))


def target_test_author_prompt() -> str:
    """SWE.5 step 1 (fresh context): Renode target tests written and made to pass before the integration author."""
    steps = ["Call use_skill with skill_name swe5-author.", READ, small()] + TARGET_STEPS + [DEFECT_RULE] + [REPLY]
    return " ".join(f"{i}) {s}" for i, s in enumerate(steps, 1))


def unit_test_author_prompt() -> str:
    """SWE.4 step 1 (fresh context): unit tests inserted into the generated harness in small edits."""
    from .scaffold import TEST_CALLS_MARKER, TEST_CASES_MARKER

    steps = ["Call use_skill with skill_name swe4-author.", READ, small()] + \
        [x.replace("{cases}", TEST_CASES_MARKER).replace("{calls}", TEST_CALLS_MARKER).replace("{example}", UT_EXAMPLE)
         for x in UT_STEPS] + [DEFECT_RULE, REPLY]
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


def triage_prompt(k: int) -> str:
    """ADR-0008 L12: the upstream owner judges routed defects in a small, edit-free step before any fix."""
    steps = [f"Call use_skill with skill_name swe{k}-author.",
             f"This step only TRIAGES defects routed to SWE.{k}; use at most 8 tool calls and do NOT write or edit any "
             "file (a later step fixes accepted defects).",
             f"glob .forge-run/defects/DEF-*.json and read every defect with target_phase SWE.{k} and status IN_FIX.",
             f"read_file {TRIAGE_READ[k]}.",
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
             FIX_DEFECTS.format(p="SWE.3")] + FIX3_STEPS + [REPLY]
    return " ".join(f"{i}) {s}" for i, s in enumerate(steps, 1))


def ll_author_prompt() -> str:
    """SWE.3 step 1 (fresh, small context): LL access functions on the generated register map; HAL comes next."""
    from ..inspection.regmap import FUNCTIONS_MARKER

    steps = ["Call use_skill with skill_name swe3-author.", READ, small()] + \
        [x.replace("{marker}", FUNCTIONS_MARKER) for x in LL_STEPS] + [REENTRY] + [REPLY]
    return " ".join(f"{i}) {s}" for i, s in enumerate(steps, 1))


def hal_author_prompt() -> str:
    """SWE.3 step 2 (fresh context): HAL header/source built incrementally in small edits against the LL header."""
    steps = ["Call use_skill with skill_name swe3-author.", READ, small()] + \
        [x.replace("{marker}", HAL_MARKER).replace("{hmarker}", HAL_H_MARKER).replace("{hal_example}", HAL_EXAMPLE)
         for x in HAL_STEPS] + [REENTRY] + [REPLY]
    return " ".join(f"{i}) {s}" for i, s in enumerate(steps, 1))


def author_prompt(phase: str) -> str:
    n = phase[-1]
    fills = {"s1": sec("14.10.1", "14.10.2", "14.10.79", "14.10.64")}
    body = [x.format(**fills) if "{s" in x else x for x in AUTHOR_STEPS[phase]]
    manifest = [] if phase in ("SWE.3", "SWE.4") else ["read_file .forge-run/manifest.json."]  # saves turn budget
    extra = [FIX_DEFECTS.format(p=phase)] if phase in ("SWE.1", "SWE.2") else \
        [DEFECT_RULE] if phase in ("SWE.4", "SWE.5", "SWE.6") else []
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
             *([INSPECT_DEFECT] if phase != "SWE.1" else []),
             *([GATE_DECLARED_CHECK.format(p=phase)] if phase in ("SWE.4", "SWE.5", "SWE.6") else []),
             f"Call mcp__forge_evidence_mcp__check_inspection with phase {phase}, baseline_id <id>, and verdicts as ONE plain "
             f"string covering EVERY item, e.g. \"{example}; ...\" and for a failed item ID=FAIL:<short finding>. "
             "Items decided by deterministic tools are recomputed automatically.",
             'Finish with ONLY JSON: {"status":"PASS" or "REWORK","artifacts":["inspection/' + phase +
             '/<INS id>.json"],"issues":["<item id: finding>"],"next_action":"next" or "rework"}']
    return " ".join(f"{i}) {s}" for i, s in enumerate(steps, 1))
