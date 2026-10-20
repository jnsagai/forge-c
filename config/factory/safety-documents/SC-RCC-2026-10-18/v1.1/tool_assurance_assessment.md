# Tool Assurance Assessment — Forge-C toolchain for the STM32N6 RCC drivers

| Field | Value |
|---|---|
| Document | TAA-RCC-001, version 1.1 |
| Status | **DRAFT v1.1 for owner review — not approved** (v1.0 signed 2026-10-19 stays in force for 0002a/0002b until v1.1 is signed) |
| Safety scope | SC-RCC-2026-10-18, target ASIL B (owner decision 2026-10-18) |
| Product | RCC LL driver (example `0002a-arm_55_rcc_ll`) and RCC HAL driver (example `0002b-arm_55_rcc_hal`); delivered RCC code (brownfield examples `0008a-rcc-ll-delivered`, `0008b-rcc-hal-delivered`, `0008c-st-cube-rcc`) |
| Basis | Work order inputs, source requirements hash `c62aa88ca3c53f3a58de023f1e6f164df97da8b053d5ddbcaa92cbd58121f7d4`; toolchain as used by LL `WO-0002A-STM32N6-RCC-LL-r168` (factory commit c9f836a); brownfield tools as used by b001, b004 and b005 (feature 008, merged b040c90); model routing as fixed by CAPA-051 (a76e957) |
| Drafted by | Claude Opus 5.5 (Claude Code), v1.0 2026-10-19, v1.1 2026-10-20, from the factory records listed in section 8 |
| Responsible engineer | Jefferson Nascimento (owner) |

> DRAFT v1.1 for owner review — not approved. Version 1.0 (signed, OD-2026-10-19-12, file
> `../tool_assurance_assessment.md`) is unchanged and remains the signed document for 0002a/0002b. This draft
> enters no work order until the owner signs it and its register entry is updated. It is a tool confidence
> assessment, not a tool qualification certificate, a safety approval or a certification.

## Change log v1.0 → v1.1

| Change | Where |
|---|---|
| T-03 corrected (CAPA-051): DeepSeek ran not only `swe4_test_author` but also `swe3_hal_author` (the HAL code author) in every LL+HAL run, and in HAL r164 every inspector and the Release Manager. DeepSeek is now suspended and refused by the factory (OD-2026-10-20-03). | T-03, T-07, TAA-FND-03, TAA-FND-08, Q-05 |
| Q-05 answered by owner decision OD-2026-10-20-03 ("stop using deepseek at all, just resume when I say so"; "replace deepseek by other model, claude or codex by now"). | Q-05 |
| Brownfield (delivered-code) tools added: T-20 to T-27; arm-none-eabi-gcc also used for the CMSIS build check. | Section 4.3, T-01 |
| Scope extended to the delivered RCC code (0008a, 0008b, 0008c); same basis hash (verified 2026-10-20). | Header |
| Section 9 left blank for the v1.1 signature; the v1.0 signature record is kept in the v1.0 file. | Section 9 |

## 1. Purpose and scope

For every tool that produces or verifies the RCC work products, this document states how the tool is used, whether a
malfunction of the tool could introduce an error into the driver or fail to detect one (**tool impact**), how likely
another independent measure is to catch that error (**error detection**), and the resulting **tool confidence
level**. Where the confidence level is above the lowest, it names the measure needed to justify using the tool.

The assessment covers the tools for one use case each, as configured for the RCC work orders. A change of tool
version, configuration or use case invalidates the affected rows.

## 2. Classification scheme (summary in the drafter's words)

- **Tool impact.** TI1: a malfunction cannot introduce an error into the work product or cause an error to go
  unnoticed. TI2: it can.
- **Error detection.** TD1: an error caused by the tool is very likely to be prevented or detected by another,
  independent measure. TD2: it is fairly likely. TD3: otherwise.
- **Tool confidence level.** TCL1 when TI1, or TI2 with TD1: no further measure needed. TCL2 for TI2 with TD2 and
  TCL3 for TI2 with TD3: the tool needs an additional measure for ASIL B (for example, increased confidence from
  use, an evaluation of the tool's development process, or validation of the tool for this use case).

## 3. AI models — approach

The AI models cannot be validated like a conventional tool: their output is not deterministic (no seed, provider
default temperature) and the model version is controlled by the provider. The proposed approach is therefore
**not to rely on the AI models at all**: every AI-authored work product is treated as the output of an untrusted
developer and must pass the same verification as hand-written work (deterministic gates, tests on the host and on
the simulator, independent inspection by a different model family, and human review of the safety-relevant
work products). The AI rows below are classified on that basis. The reviewer must decide whether that is acceptable
(question Q-01).

## 4. Tool classification

Abbreviations: WP = work product. "Detection" names the independent measures that would catch an error caused by
the tool.

### 4.1 Tools whose output goes into the released work products

| ID | Tool, version | Use case | TI | Detection | TD | TCL | Needed measure / note |
|---|---|---|---|---|---|---|---|
| T-01 | arm-none-eabi-gcc 10.3.1 (Ubuntu package 10.3-2021.07-4) with binutils 2.38 | Compiles the target objects (`-mcpu=cortex-m55 -Os -Werror`), SWE.3–SWE.5; object size and stack figures; (v1.1) `-fsyntax-only` build check of CMSIS-style deliveries at intake (`-mcpu=cortex-m55 -mthumb [-mcmse]`) | TI2 | Renode target tests and Robot SWE.6 suites run gcc-built images, but those images are rebuilt with different flags and a different link (TAA-FND-01); host tests use clang | TD3 | **TCL3** | Run the target tests on the released object code (TAA-FND-01), then reassess as TD2; pin the compiler by hash (TAA-FND-02); choose a measure (increased confidence from use of this compiler version, or a validation suite for the used options). |
| T-02 | Codex CLI 0.162.1 via codex-acp 2.1.1, model Codex Sol 6.1 (`gpt-6.1-sol`, reasoning high) | Authors requirements, architecture, design, C code and tests (SWE.1–SWE.6) | TI2 | Deterministic freeze gates (EARS, architecture, guideline, register-map conformance, implementation completeness, trace), cppcheck and clang analyzer, host and Renode tests, Robot suite, Claude inspector, human review | TD2 | **TCL2** | Treated as untrusted output (section 3). Human review of the safety-relevant work products is the measure; the Codex adversarial probe referenced in ADR-0011 has no evidence path (TAA-FND-05). |
| T-03 | DeepSeek `deepseek-flash` (Fabro native nodes; **historical, suspended**) | Until CAPA-051: `swe4_test_author` (unit test bodies, SWE.4) in every run; `swe3_hal_author` (HAL C code, SWE.3) in every LL+HAL run (HAL r164, whose code is also the 0008b delivery); in HAL r164 also every inspector and the Release Manager | TI2 (wrong code; a weak test can let a code error pass) | For the HAL r164 code: deterministic gates, host and Renode tests, Robot; **no different-family inspector** (the r164 inspectors were DeepSeek too) | TD2 for tests; TD3 for the r164 HAL code (no model diversity) | **TCL2**, **TCL3** for the r164 HAL code | Outside the owner's model decisions. Suspended and refused by the factory since CAPA-051 / OD-2026-10-20-03. Existing evidence produced by it needs a measure (TAA-FND-03, TAA-FND-08). |
| T-04 | `inspection.regmap` (factory, commit c9f836a) | Generates the LL register offsets and masks from the RM0486 section files and checks them | TI2 | Register contract and oracle, Renode RCC model, unit tests, SWE.3 inspector — all derived from the same converted RM0486 text | TD3 (common source) | **TCL3** | Independent review of the generated register cells against the original RM0486 PDF (TAA-FND-06); then reassess. |
| T-05 | Factory scaffold generators (`inspection.unit_scaffold`, `workflow.scaffold`) | Unit specification and design skeleton (SWE.3) | TI2 | SWE.3 inspector, implementation completeness gate, tests | TD2 | **TCL2** | Covered by CRE regression (frozen reproducers, golden benchmark) for the factory code; reviewer to decide whether that is sufficient. |
| T-06 | git 2.34.1 | Version control of each work order workspace; baselines | TI2 | Every packaged file is listed with its SHA-256; the package and archives are hash-checked | TD1 | TCL1 | — |

### 4.2 Verification tools (a malfunction can only cause an error to go unnoticed)

| ID | Tool, version | Use case | TI | Detection | TD | TCL | Needed measure / note |
|---|---|---|---|---|---|---|---|
| T-07 | Claude Code 2.1.286 via claude-agent-acp 0.85.1, model Claude Opus 5.5 (`claude-opus-5-5`) | Inspections SWE.1–SWE.6; Release Manager builds the package (v1.1: not in HAL r164, which ran without Claude inspectors) | TI2 (false PASS) | Gate decisions use the recorded inspection plus deterministic gates that run regardless; the EASA gate does not count AI PASS as independent evidence; human review | TD2 | **TCL2** | Treated as untrusted (section 3). In r168, SWE.2 and SWE.5 inspector replies failed to parse while the recorded inspection passed; reviewer to note. |
| T-08 | clang / LLVM 19.1.7 (official release, SHA-256 verified) | Host builds of unit and integration tests (`-O0`) | TI2 | Target tests built with gcc | TD2 | **TCL2** | — |
| T-09 | llvm-profdata / llvm-cov 19.1.7 | Coverage (line, branch, MC/DC) on the host | TI2 (over-reported coverage) | Mutation campaign (observe-only), inspector review of the coverage report | TD2 | **TCL2** | LL r168 reports MC/DC as not measured (null); HAL r164 100 % (TAA-FND-07). |
| T-10 | Generated host test harness (`CHECK` macros, LL test double `workflow.ll_fake`) | Runs unit and integration tests on the host | TI2 | Renode and Robot tests, mutation campaign | TD2 | **TCL2** | — |
| T-11 | Renode 1.17.0 (portable, SHA-256 verified) with the factory's behavioural RCC model | Target tests on a simulated Cortex-M55, SWE.5–SWE.6 | TI2 | No silicon or HIL tests; the RCC model is written from the same RM0486 text | TD3 | **TCL3** | Tests on silicon, or a model validation against silicon (TAA-FND-06). Labelled `silicon_verified: false`; no clock timing, bus faults, security filtering, errata or concurrency. |
| T-12 | Robot Framework 6.1 (hash-locked) with `ForgeTarget.py` | SWE.6 test per software requirement, on Renode | TI2 | Trace gate (each requirement must tag a passing test), inspector | TD2 | **TCL2** | Same simulator limits as T-11. |
| T-13 | Cppcheck 2.7 with the MISRA addon (distro package) | Static analysis and the automatable coding-guideline subset, SWE.3–SWE.6 | TI2 | Clang static analyzer (overlapping checks), guideline check, inspector | TD2 | **TCL2** | 130 of 158 MISRA rules automated, no directives; no MISRA compliance is claimed. Pin by hash (TAA-FND-02). |
| T-14 | Clang static analyzer 19.1.7 | Static analysis | TI2 | Cppcheck | TD2 | **TCL2** | `clang-tidy` is implemented but not granted to any role, so it does not run. |
| T-15 | Factory deterministic checkers (EARS, architecture, guideline, SWE.3 checks, trace gate, implementation completeness, defects, reverify, finalizer, packager v0.4) | Freeze and inspect gates, packaging | TI2 (false PASS) | AI inspector, human review; the factory code itself is under CRE regression (frozen reproducers, golden benchmark, holdout) | TD2 | **TCL2** | The guideline check covers only the automatable subset of the ST Cube2 HAL guideline. |
| T-16 | Fabro 0.362.0-nightly (a192bce) | Runs the workflow graph, loops and hooks | TI2 (a step skipped) | The finalizer re-derives the outcome from the gate logs; the package policy requires every work product; Fabro's own run status is not trusted (ADR-0002) | TD1 | TCL1 | Nightly build, not upgraded. |
| T-17 | binutils `size` / `objdump` 2.38, gcc `-fstack-usage` | Flash, RAM and per-function stack figures | TI2 | None independent; figures are object-level, not a linked image | TD3 | **TCL3** | Measure the linked image and the call-graph worst-case stack (see SSA-FND-05), or accept the figures as indicative only. |
| T-18 | PlantUML 1.2026.8 (ASL jar) on OpenJDK 11 | Syntax check of the architecture views | TI1 | — | — | TCL1 | The tool record names the wrapper version (0.4.0), not the jar version (TAA-FND-04). |
| T-19 | EASA observe-only verifiers (mutation, oracle, target, independence); CBMC 6.11.0, Frama-C 33.0 | Observe-only reports; formal tools not used in r168 | TI1 (results do not decide anything today) | — | — | TCL1 | Reassess if they become enforcing. |

### 4.3 Brownfield (delivered-code) tools — added in v1.1

| ID | Tool, version | Use case | TI | Detection | TD | TCL | Needed measure / note |
|---|---|---|---|---|---|---|---|
| T-20 | Intake `brownfield.delivery` (factory, feature 008) | Validates the delivery contract (origin, licence, scope, mode), fingerprints every delivered file (SHA-256) and stores it read-only outside the workspace | TI2 (wrong or altered code accepted) | Fingerprints re-verified independently by T-24 at SWE.3 entry, SWE.3 verify and packaging; the package lists each file's SHA-256 and the origin/licence record | TD1 | TCL1 | Origin and licence are as declared in the work order; their truth is the owner's input (ST provenance recorded in `$FORGE_DATA_ROOT/inputs/st/*/provenance.json`). |
| T-21 | Intake build check (`delivery.build_check`: host clang 19.1.7 for factory style, arm-none-eabi-gcc 10.3.1 `-fsyntax-only` for CMSIS style) | Accepts only delivered code that compiles with its declared dependencies | TI2 (false PASS) | SWE.3–SWE.5 compiles and tests on the same code | TD1 | TCL1 | — |
| T-22 | Scope resolution and C index (`brownfield.scope`: function extents, constant macros, register-effect extraction, set/clear alias map CSR/CCR, *ENSR/*ENCR, *RSTSR/*RSTCR) | Selects the scope functions and extracts their register effects for conformance and the trace map | TI2 (a missed function or effect hides a disagreement) | Requirement-based tests SWE.4–SWE.6 on the delivered code, SWE.2/SWE.3 inspectors | TD2 | **TCL2** | Two extraction/parser defects found and fixed in b002 and b005; no SWE.4–SWE.6 evidence yet for the ST code (0008c). |
| T-23 | Conformance check (`brownfield.conformance`) | Reports NO_CODE, NO_REQUIREMENT and CONTRADICTION between the requirements, the architecture's API calls and the delivered code | TI2 (false CONFORMANT) | Requirement-based tests, inspectors | TD2 | **TCL2** | Static no-write cases without a register and start-up invariants are left to tests (not checked here). |
| T-24 | Fingerprint verification and FIX_ALLOWED write window (`brownfield.verify`, `policy.authz` delivered-write rules, change report) | Detects any change to delivered code; in FIX_ALLOWED allows writes only while a CODE defect is IN_FIX, inside scope functions, and reports each change against the original | TI2 (an unjustified change goes unnoticed) | Packaging recomputes the fingerprints and the diff independently of the write window; the change report names original and corrected SHA-256 | TD1 | TCL1 | Human review of every listed change (SSA AOU-10). |
| T-25 | Trace map (`brownfield.trace`) | Replaces the factory's code tags (`workproducts/SWE.3/code_trace_map.json`) | TI2 | swtrace gate (every requirement traced), SWE.3 inspector | TD2 | **TCL2** | — |
| T-26 | Delivery injection (`brownfield.inject`) | Copies the delivered code into the workspace only after the SWE.1 inspection passed; SWE.1 roles are denied reads of delivered paths | TI2 (requirements contaminated by the code, or the wrong code injected) | Fingerprint verification (T-24); the injection record names the SWE.1 baseline | TD1 | TCL1 | Independence of SWE.1 from the code rests on the policy hook (T-16/section 5). |
| T-27 | Brownfield safety drafts and package records (`brownfield.safety_drafts`, `brownfield.package`) | Writes deterministic drafts under `safety/drafts/` and the delivery records into the package | TI1 (drafts never count as signed documents; only owner-signed files do) | — | — | TCL1 | — |

## 5. Tool use restrictions relied on

The classifications assume the current restrictions on AI agents stay in place:

- Native Fabro nodes run behind a fail-closed `pre_tool_use` hook (role grants, path scopes, no shell, web or
  sub-agents). ACP nodes (Codex authors, Claude inspectors) have no file system or terminal access of their own;
  they reach only the factory's gate tools, each call checked and audited.
- Every MCP gate call carries a one-time ticket bound to role, node and arguments, with validated inputs and an
  allow-listed command line.
- Inspectors are read-only and only an inspector can record an inspection. Skills are pinned by SHA-256.

## 6. Findings

| ID | Finding | Proposed measure |
|---|---|---|
| TAA-FND-01 | The Renode target images are rebuilt with different flags and link than the released target objects, so no test runs the released object code. | Build the test images from the released objects with the released options. |
| TAA-FND-02 | gcc 10.3.1, binutils, cppcheck 2.7, cmake and ninja are unpinned distro packages; only LLVM, Renode, the formal tools, Codex and the Claude adapter have recorded hashes. | Pin and record every tool by version and SHA-256 in the package. |
| TAA-FND-03 | (v1.1) `swe4_test_author` and `swe3_hal_author` ran on DeepSeek in every run before CAPA-051, outside the owner's model decisions; DeepSeek is not recorded under `evidence/easa/tools`. **For future runs closed** by CAPA-051 (all agent nodes on Codex or Claude; DeepSeek refused, OD-2026-10-20-03). **Open for existing evidence** (RCC runs r164, r168, r170, b001, b004, b005). | Re-run the affected work orders on a factory revision with CAPA-051, or review the DeepSeek-written code and tests by hand. |
| TAA-FND-04 | Stale tool records ship in the package: `toolchain_versions.json` is the 2026-10-14 inventory (lists `qwen3:8b`, shows Renode and the formal tools as missing, omits Codex, Claude, DeepSeek, Renode 1.17 and PlantUML); `known_limitations.md` lists Renode as disabled although it ran; some docstrings say CBMC, Frama-C and PlantUML are not installed; `agents.yaml` still names `qwen3:8b`. | Generate the package tool records from the run's actual tool results. |
| TAA-FND-05 | The Codex adversarial probe described in ADR-0011 has no evidence in the repository. | Re-run and record it, or remove the claim. |
| TAA-FND-06 | Register header, register contract, oracle and Renode model all derive from the same converted RM0486 text (common cause, T-04, T-11). | Independent review against the original PDF; tests on silicon. |
| TAA-FND-07 | MC/DC coverage is not reported for the LL (r168); the LL mutation campaign left 3 survivors. | Report MC/DC for the LL; analyse the survivors. |
| TAA-FND-08 | (v1.1) HAL r164 ran without Claude inspectors: its HAL code was authored (`swe3_hal_author`) and inspected by DeepSeek, so v1.0's statement that inspectors run on a different model family does not hold for it. The 0008b delivery is that code plus a seeded defect. | Human review of the HAL code, or regenerate the HAL on a factory revision with CAPA-051 and Claude inspectors. |

## 7. Open questions for the reviewer

| ID | Question |
|---|---|
| Q-01 | Do you accept the approach for the AI models (section 3): no reliance on the model, full verification of its output plus human review? |
| Q-02 | Do you accept the proposed TI, TD and TCL for each tool, in particular TCL3 for T-01, T-04, T-11 and T-17? |
| Q-03 | Which measure do you choose for each TCL2 and TCL3 tool, and by when? |
| Q-04 | Should the findings be fixed before signing, or accepted as open items listed in the package limitations? |
| Q-05 | DeepSeek for `swe4_test_author`: move to Codex, or keep it with a recorded decision (TAA-FND-03)? **Answered** by OD-2026-10-20-03: no DeepSeek; Codex or Claude instead. |
| Q-06 | (v1.1) Do you accept the proposed classification of the brownfield tools T-20 to T-27? |
| Q-07 | (v1.1) Which measure for the evidence produced on DeepSeek (TAA-FND-03, TAA-FND-08): re-run, or human review? |

## 8. Sources

`docs/TOOLCHAIN.md`, `docs/COMPLIANCE-MATRIX.md`, ADR-0001, ADR-0002, ADR-0007, ADR-0011, ADR-0012,
`evidence/easa/tools/*.json`, `evidence/easa/tools/formal-smoke/result.json`,
`evidence/v0.4/inventory/tool-inventory.json`, `requirements/forge-factory.lock`, `config/factory/agents.yaml`,
`config/factory/skills.lock.json`; LL r168 `.forge-run/{workflow.fabro, workflow.toml, model-profile.json,
manifest.json, gates/gate-log.jsonl, assurance/}` and `evidence/tool-results.jsonl`;
`verification/static/misra_coverage_matrix.md`, `verification/coverage/coverage_summary.json`. v1.1: `factory/python/forge_factory/brownfield/`,
`docs/BROWNFIELD-WORK-ORDERS.md`, `evidence/v0.4/runs/BF-T030`, `BF-T031`, `BF-T036`, `BF-T039`; the model profiles of r164,
r168, r170, b001, b004 and b005; `evidence/cre/capa/i003-capas.json` (CAPA-051); OD-2026-10-20-03.

## 9. Review and signature (v1.1)

| Field | Value |
|---|---|
| Reviewed by (name, role) | |
| Reviewer's statement | |
| Answers to Q-01 to Q-07 | (v1.0 answers: Q-01 and Q-02 accepted; Q-03 and Q-04 open; Q-05 now answered by OD-2026-10-20-03) |
| Changes made during review | |
| Decision | ☐ Approved ☐ Approved with open findings (listed in the package limitations) ☐ Rejected |
| Date | |

Signing records the reviewer's engineering judgement on the confidence in these tools for the stated use cases. It
is not a tool qualification certificate, a safety approval or a certification.
