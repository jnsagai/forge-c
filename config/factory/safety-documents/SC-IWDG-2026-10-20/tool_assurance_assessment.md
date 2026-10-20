# Tool Assurance Assessment — Forge-C toolchain for the STM32N6 IWDG LL driver

| Field | Value |
|---|---|
| Document | TAA-IWDG-001, version 1.0 |
| Status | **Approved with open findings** — signed by Jefferson Nascimento (owner), 2026-10-20 |
| Safety scope | SC-IWDG-2026-10-20, target ASIL B (owner decision 2026-10-20, OD-2026-10-20-04) |
| Product | IWDG LL driver (example `0009a-iwdg-ll`) |
| Basis | Work order inputs, source requirements hash `bfee8b2ee260d6e114e2cf92b77336da4c8534e11efd53cf3c2a7995910b9286`; toolchain as used by `WO-0009A-STM32N6-IWDG-LL-i003` (factory commit 83ee4c7) |
| Drafted by | Claude Opus 5.5 (Claude Code), 2026-10-20, from the factory records listed in section 8 |
| Responsible engineer | Jefferson Nascimento (owner) |

> Signed version (owner decision OD-2026-10-20-05). It applies to IWDG work orders whose inputs match the basis
> above. Any edit to this file, or a change to the work order inputs, un-signs it until it is re-reviewed. It
> records the reviewer's engineering judgement; it is not a safety approval or certification.

## 1. Purpose and scope

Same purpose and method as TAA-RCC-001 (signed 2026-10-19): for every tool that produces or verifies the IWDG work
products, state the use case, the **tool impact** (TI), the **error detection** (TD) and the resulting **tool
confidence level** (TCL), and name the measure needed above TCL1. A change of tool version, configuration or use
case invalidates the affected rows. Rows that are unchanged from TAA-RCC-001 say so; their reasoning is not
repeated.

## 2. Classification scheme

As in TAA-RCC-001 section 2 (TI1/TI2; TD1/TD2/TD3; TCL1 for TI1 or TI2+TD1, TCL2 for TI2+TD2, TCL3 for TI2+TD3;
TCL2 and TCL3 tools need an additional measure for ASIL B).

## 3. AI models — approach

The approach accepted for RCC (TAA-RCC-001 Q-01) is proposed unchanged: the AI models are not relied on; every
AI-authored work product is treated as the output of an untrusted developer and passes the deterministic gates, the
host and simulator tests, an inspection by a different model family and human review. Model use for this product:

- **Now** (from factory revision a76e957, CAPA-051; OD-2026-10-20-03): authors on Codex Sol 6.1, inspectors and the
  Release Manager on Claude Opus 5.5; no agent node may run on DeepSeek (the work order is refused otherwise).
- **In i003** (the run analysed here): the same, except that `swe4_test_author` (the unit-test bodies) ran on
  DeepSeek `deepseek-flash`, because its multi-line prompt was skipped when author nodes were moved to Codex
  (CAPA-051). i003's `.forge-run/model-profile.json` lists the 13 Codex nodes and the 7 Claude nodes;
  `swe4_test_author` is in neither list.

## 4. Tool classification

### 4.1 Tools whose output goes into the released work products

| ID | Tool, version | Use case | TI | Detection | TD | TCL | Needed measure / note |
|---|---|---|---|---|---|---|---|
| T-01 | arm-none-eabi-gcc 10.3.1 (Ubuntu package 10.3-2021.07-4), binutils 2.38 | Target objects for size, stack and the Renode/Robot images | TI2 | Renode and Robot tests run gcc-built images; whether they are built from the released objects with the released options is NOT_VERIFIED for i003 (TAA-RCC-FND-01 applies to RCC) | TD3 | **TCL3** | As TAA-RCC-001 T-01. |
| T-02 | Codex CLI 0.162.1 via codex-acp 2.1.1, model Codex Sol 6.1 (`gpt-6.1-sol`, reasoning high) | Authors SWE.1–SWE.6 work products and the LL code | TI2 | Deterministic gates (EARS, register contract with the `write` op, register-map conformance, implementation completeness, trace), cppcheck and clang analyzer, host and Renode tests, Robot, Claude inspector, human review | TD2 | **TCL2** | Unchanged from TAA-RCC-001 T-02. |
| T-03 | DeepSeek `deepseek-flash` (Fabro native node `swe4_test_author`, **i003 only**) | Wrote the i003 unit-test bodies (SWE.4) | TI2 (a weak test can let a code error pass) | Coverage (line 100 %, branch 100 %, MC/DC not measured), SWE.4 inspector, Renode and Robot tests | TD2 | **TCL2** | Outside the owner's model decisions; DeepSeek is now suspended (OD-2026-10-20-03) and blocked by the factory (CAPA-051). Re-run SWE.4 with the Codex author (TAA-IWDG-FND-01). |
| T-04 | `inspection.regmap` (factory, commit 83ee4c7; multi-bit fields from feature 009) | Generates and checks the IWDG offsets, positions and masks from the RM0486 section files | TI2 | Register contract and oracle, Renode IWDG model, unit tests, SWE.3 inspector — all from the same converted RM0486 text | TD3 (common source) | **TCL3** | Independent review of the generated cells against the original RM0486 PDF (TAA-IWDG-FND-03). |
| T-05 | Peripheral profile `config/factory/peripherals/iwdg.yaml` and the profile-driven prompt filter (`workflow.prompts.peripheralize`), feature 009 | Names the headers, prefixes, register block, key sections, base address and the prompt texts for every phase | TI2 (a wrong base address, prefix or key section misleads authors and checks) | Schema validation and SHA-256 recorded in the manifest; the work order refuses key sections missing from the inputs; regmap and the register contract check offsets against RM0486; SC-001 test (no RCC content in IWDG prompts) | TD2 | **TCL2** | New tool for this product; reviewer to accept the profile content as reviewed configuration. |
| T-06 | Factory scaffold generators (unit specification and design skeleton, unit-test harness for IWDG) | SWE.3/SWE.4 skeletons | TI2 | SWE.3 inspector, implementation completeness, tests | TD2 | **TCL2** | As TAA-RCC-001 T-05. |
| T-07 | git 2.34.1 | Version control of the workspace; baselines | TI2 | Every packaged file listed with its SHA-256 | TD1 | TCL1 | Unchanged. |

### 4.2 Verification tools (a malfunction can only cause an error to go unnoticed)

| ID | Tool, version | Use case | TI | Detection | TD | TCL | Needed measure / note |
|---|---|---|---|---|---|---|---|
| T-08 | Claude Opus 5.5 (`claude-opus-5-5`) via claude-agent-acp 0.85.1 (Claude Code version NOT_VERIFIED for i003) | Inspections SWE.1–SWE.6; Release Manager | TI2 (false PASS) | Deterministic gates run regardless; EASA gate does not count AI PASS as independent | TD2 | **TCL2** | Unchanged from TAA-RCC-001 T-07. |
| T-09 | clang / LLVM 19.1.7 | Host builds of unit and integration tests | TI2 | Target tests built with gcc | TD2 | **TCL2** | Unchanged. |
| T-10 | llvm-cov 19.1.7 | Host coverage | TI2 | Inspector review; the mutation evidence was not accepted by the EASA gate in i003 | TD2 | **TCL2** | MC/DC not measured in i003 (TAA-IWDG-FND-04). |
| T-11 | Generated host test harness for IWDG (`CHECK` macros, RAM-backed `ll_iwdg_regs`) | Runs unit and integration tests on the host | TI2 | Renode and Robot tests | TD2 | **TCL2** | New for IWDG (profile-driven harness, feature 009). |
| T-12 | Renode 1.17.0 with the factory's behavioural IWDG model (`factory/sim/stm32n6/iwdg_model.py`, written by the factory in feature 009) | Target tests on a simulated Cortex-M55, SWE.5–SWE.6 (i003: 31 checks, 2 images) | TI2 | No silicon or HIL tests; the model is written from the same RM0486 text | TD3 | **TCL3** | The model has no counter, LSI clock or reset, ignores no refresh, and accepts PR/RLR writes while an update is pending, so the watchdog's timeout and reset behaviour is not verified (TAA-IWDG-FND-02). The i003 tool summary labels the run "behavioural RCC model" although the IWDG model ran: a label defect (TAA-IWDG-FND-05). |
| T-13 | Robot Framework 6.1 with `ForgeTarget.py` | SWE.6 test per software requirement (i003: 16/16 tests, 16/16 requirements) | TI2 | Trace gate, inspector | TD2 | **TCL2** | Same simulator limits as T-12. |
| T-14 | Cppcheck 2.7 with the MISRA addon | Static analysis, automatable guideline subset (i003: 0 findings) | TI2 | Clang analyzer, guideline check, inspector | TD2 | **TCL2** | Unchanged; no MISRA compliance claimed. |
| T-15 | Clang static analyzer 19.1.7 | Static analysis (i003: 0 diagnostics) | TI2 | Cppcheck | TD2 | **TCL2** | Unchanged. |
| T-16 | Factory deterministic checkers (EARS, architecture, register contract and oracle with the `write` op, implementation completeness, swtrace, defects, finalizer, packager v0.4) | Freeze and inspect gates, packaging | TI2 (false PASS) | AI inspector, human review; CRE regression on the factory code (009 promotion pd-d548a41db6592b72cdc7, CAPA-051 promotion pd-11778a310f1f636ea8d1) | TD2 | **TCL2** | Unchanged in kind; the IWDG paths are new code (feature 009). |
| T-17 | Fabro 0.362.0-nightly (a192bce) | Workflow engine | TI2 (a step skipped) | Finalizer re-derives the outcome from the gate logs | TD1 | TCL1 | Unchanged. |
| T-18 | binutils `size` 2.38, gcc `-fstack-usage` | Flash, RAM and stack figures (i003: text 160 B, data 0, bss 0; max frame 0 B) | TI2 | None independent; object-level figures | TD3 | **TCL3** | As TAA-RCC-001 T-17. |
| T-19 | PlantUML (factory wrapper 0.4.0) | Syntax check of the architecture views | TI1 | — | — | TCL1 | Unchanged. |
| T-20 | EASA observe-only verifiers | Observe-only reports (i003 mode PILOT: FAIL/UNKNOWN items at SWE.1, SWE.2, SWE.4, SWE.5) | TI1 (results decide nothing) | — | — | TCL1 | Some helpers still assume RCC (feature 009 known limit); reassess if they become enforcing. |

## 5. Tool use restrictions relied on

As TAA-RCC-001 section 5. In addition: `workorder.run` refuses any work order that would leave an agent node on a
suspended run model (CAPA-051, `config/factory/model-suspensions.yaml`).

## 6. Findings

| ID | Finding | Proposed measure |
|---|---|---|
| TAA-IWDG-FND-01 | i003's unit tests were written by DeepSeek (T-03), outside the owner's model decisions. | Re-run the work order on a factory revision with CAPA-051. |
| TAA-IWDG-FND-02 | The Renode IWDG model does not model the counter, reset, ignored refresh or write-ignored-while-pending (T-12). | Extend the model; test timeout and reset on silicon. |
| TAA-IWDG-FND-03 | Register header, contract, oracle and Renode model derive from the same converted RM0486 chapter 59 (T-04, T-12). | Independent review against the original PDF; silicon tests. |
| TAA-IWDG-FND-04 | MC/DC not measured; the EASA gate did not accept the oracle and mutation evidence (T-10, T-20). | Report MC/DC; make the observe-only helpers peripheral-generic. |
| TAA-IWDG-FND-05 | The `run_renode` result summary hard-codes "behavioural RCC model" (T-12). | Name the model from the peripheral profile. |
| TAA-IWDG-FND-06 | The TAA-RCC-001 findings on tool pinning and tool records (FND-02, FND-04) apply to this toolchain too. | As in TAA-RCC-001. |

## 7. Open questions for the reviewer

| ID | Question |
|---|---|
| Q-01 | Do you accept the AI-model approach of section 3 for this product, as for RCC? |
| Q-02 | Do you accept the proposed TI, TD and TCL per tool, in particular TCL3 for T-01, T-04, T-12 and T-18, and TCL2 for the peripheral profile (T-05)? |
| Q-03 | Which measure do you choose for each TCL2 and TCL3 tool, and by when? |
| Q-04 | Should the i003 evidence be replaced by a re-run without DeepSeek before signing (TAA-IWDG-FND-01)? |
| Q-05 | Should the findings be fixed before signing, or accepted as open items listed in the package limitations? |

## 8. Sources

`config/factory/safety-documents/SC-RCC-2026-10-18/tool_assurance_assessment.md` (TAA-RCC-001 v1.0), the i003
workspace (`.forge-run/model-profile.json`, `.forge-run/manifest.json`, `evidence/tool-results.jsonl`,
`.forge-run/assurance/gate-log.jsonl`), `evidence/v0.4/runs/PG-T012/`, `config/factory/peripherals/iwdg.yaml`,
`factory/sim/stm32n6/iwdg_model.py`, `evidence/cre/capa/i003-capas.json`, `config/factory/model-suspensions.yaml`,
`evidence/easa/owner-decisions/OD-2026-10-20-03-deepseek-suspended.json`; tool versions from the provenance of each
i003 tool result and from `arm-none-eabi-gcc --version` and `fabro --version` on the factory host (2026-10-20).

## 9. Review and signature

| Field | Value |
|---|---|
| Reviewed by (name, role) | Jefferson Nascimento, owner and responsible engineer |
| Reviewer's statement | "I approve all" (2026-10-20), in reply to "Sign the drafts in PR #16 when you're satisfied with them" |
| Answers to Q-01 to Q-05 | Q-01 and Q-02: the AI-model approach and the proposed TI, TD and TCL accepted as drafted. Q-05: the findings are not fixed before signing; they stay open. Q-03 and Q-04: not answered at signing; they remain open. |
| Changes made during review | None to the analysis; status, version and this section completed on signing |
| Decision | ☐ Approved ☒ Approved with open findings (listed in the package limitations) ☐ Rejected |
| Date | 2026-10-20 |

Signing records the reviewer's engineering judgement on the confidence in these tools for the stated use cases. It
is not a tool qualification certificate, a safety approval or a certification.
