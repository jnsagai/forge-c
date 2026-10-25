# Tool Assurance Assessment — Forge-C toolchain for the STM32N6 ST LL benchmark drivers (CRC, SPI, USART, GPIO, TIM)

| Field | Value |
|---|---|
| Document | TAA-STB-001, version 1.0 |
| Status | **DRAFT — for the owner's review, not reviewed, not approved** |
| Safety scopes | SC-CRC-2026-10-25, SC-SPI-2026-10-25, SC-USART-2026-10-25, SC-GPIO-2026-10-25, SC-TIM-2026-10-25; target ASIL B for each (owner decision OD-2026-10-25-02) |
| Product | ST STM32CubeN6 v1.4.0 LL code delivered FROZEN (feature 015 benchmark): CRC `0014c-st-cube-crc`, SPI1 `0011c-st-cube-spi`, USART1 `0012c-st-cube-usart`, GPIOA `0010c-st-cube-gpio`, TIM2 `0013c-st-cube-tim` |
| Basis | Work order inputs, source requirements hash per scope: CRC `76d9347ef9a5d9e0e2f49a9c6c41f0fa0cbf52e8fe953ab433274f5ee1ba372a`, SPI `0700c04fa15af5fcdd4539d4de951da186d7d2e15f67bfa88819558b5a4949af`, USART `8a172ad502f3d75bcc0fcff7ac25ad586cc9e3bb0fd7f71df0a278cd28cecfc1`, GPIO `068be9376a6832b0da92eadd900f0db0a1ee5796520dcd263c5970c9b68e4d4e`, TIM `771f73af66c754cc43e54a35b761624cd389b640b123b0be233520d40b8f0283`; toolchain as used by the AFO benchmark runs on factory commits ed40ee4 to 710c56a |
| Drafted by | Claude Opus 5.5 (Claude Code), 2026-10-25, from the factory records listed in section 8 |
| Responsible engineer | Jefferson Nascimento (owner) |

> Draft for the owner's review (OD-2026-10-19-11). It counts for a work order only after the owner signs it and its
> register entries are completed; any later edit, or a change to the work order inputs, un-signs it. It records the
> reviewer's engineering judgement; it is not a tool qualification, a safety approval or a certification. It builds on
> the signed RCC assessment TAA-RCC-001 v1.1 (same factory, same tools) and states only what differs or is new.

## 1. Purpose and scope

For every tool that produces or verifies the benchmark work products, this document states how the tool is used,
whether a malfunction could introduce an error into the work products or let an error go unnoticed (**tool
impact**), how likely an independent measure is to catch it (**error detection**), and the resulting **tool
confidence level**. The work orders deliver ST's code FROZEN: no tool writes the delivered driver code, so for the
code itself every tool is a verification tool. The tools do author the requirements, architecture, design
descriptions and tests around it.

A change of tool version, configuration or use case invalidates the affected rows.

## 2. Classification scheme (summary in the drafter's words)

As in TAA-RCC-001 v1.1: **TI1** a malfunction cannot introduce or hide an error, **TI2** it can; **TD1** an error
is very likely caught by an independent measure, **TD2** fairly likely, **TD3** otherwise; **TCL1** for TI1 or
TI2+TD1, **TCL2** for TI2+TD2, **TCL3** for TI2+TD3 (TCL2/TCL3 need an additional measure for ASIL B).

## 3. AI models — approach

Unchanged from TAA-RCC-001 v1.1 section 3: the AI models are not relied on. Every AI-authored work product is the
output of an untrusted developer and must pass the deterministic gates, the host and simulator tests, the
inspection by a different model family and human review of the safety-relevant work products.

For these runs the model routing is: **every authoring node on Codex** (Codex CLI 0.162.1 via the forge ACP proxy,
model `gpt-6.1-sol`, reasoning high; owner ChatGPT login) and **every inspector and the Release Manager on Claude**
(claude-agent-acp 0.85.1, model `claude-opus-5-5`; owner Claude account). DeepSeek is suspended (OD-2026-10-20-03)
and serves no node: `deepseek-flash` is only the nominal Fabro run-model field; since b2e2722 the AFO admission does
not need the DeepSeek gateway and the gateway is stopped (owner 2026-10-25), so Fabro's per-run title generation
fails without reaching any provider. No local model is used.

## 4. Tool classification

### 4.1 Tools whose output goes into the released work products

| ID | Tool, version | Use case | TI | Detection | TD | TCL | Needed measure / note |
|---|---|---|---|---|---|---|---|
| T-01 | arm-none-eabi-gcc 10.3.1 (Ubuntu 10.3-2021.07-4), binutils 2.38 | Intake `-fsyntax-only` build check of the CMSIS delivery; target objects for the Renode tests, size and stack figures | TI2 | Renode target and Robot tests run gcc-built images (rebuilt, TAA-FND-01); host tests use clang | TD3 | **TCL3** | As TAA-RCC-001 T-01 (TAA-FND-01, TAA-FND-02). The delivered code is not changed by any tool; the compiler only builds it for verification. |
| T-02 | Codex CLI 0.162.1, model `gpt-6.1-sol` | Authors requirements (from RM0486 and the scope, before the code enters the work order), architecture, design descriptions, unit/integration/target/qualification tests | TI2 | Freeze gates (EARS, architecture, trace, register-map, conformance against the delivered code), cppcheck, clang analyzer, host and Renode tests, Robot, Claude inspector, human review | TD2 | **TCL2** | Untrusted output (section 3). |
| T-03 | Peripheral profiles `config/factory/peripherals/{crc,spi,usart,gpio,tim}.yaml` (factory, feature 009 mechanism; written by Claude Code) | Prompt texts that tell the authors the scope, the effect-encoding rules and the test conventions per peripheral | TI2 (a wrong instruction can bias requirements or tests) | Requirements come from RM0486 sections, inspected by Claude; conformance against the delivered code; tests | TD2 | **TCL2** | Hardware facts are kept in the RM inputs, not in the profiles (profile header). Reviewed through CRE (pd-a18956d3..., pd-3775c590..., pd-99012d49...). |
| T-04 | `docs.pdf2md` (factory) with poppler `pdftotext -layout` | Converts the RM0486 chapters 15, 26, 54, 65, 67, the memory map excerpts and p.156 into the Markdown inputs | TI2 (a converted value differs from the PDF) | Requirements, register contract, conformance, Renode models and tests all use the same converted text (common cause) | TD3 | **TCL3** | Independent check of the register tables used against the original PDF (TAA-FND-06). PDF and Markdown SHA-256 are recorded in each `inputs-manifest.json`. |
| T-05 | `inspection.regmap` (factory; multi-instance parsing added in fb682a8) | Register offsets, reset values and fields from the RM sections (register contract, field lookup) | TI2 | Delivered CMSIS headers (ST) used first for field masks in conformance; tests; inspectors | TD2 | **TCL2** | RCC, IWDG, CRC, SPI, USART results byte-identical across the change (all sections compared). GPIO per-port reset values: port A only. |
| T-06 | git 2.34.1 | Workspace version control, baselines | TI2 | Packaged files listed with SHA-256; archives hash-checked | TD1 | TCL1 | — |

### 4.2 Verification tools

| ID | Tool, version | Use case | TI | Detection | TD | TCL | Needed measure / note |
|---|---|---|---|---|---|---|---|
| T-07 | Claude Opus 5.5 via claude-agent-acp 0.85.1 | Inspections SWE.1–SWE.6, Release Manager | TI2 (false PASS) | Deterministic gates run regardless; the EASA gate does not count an AI PASS as independent evidence; human review | TD2 | **TCL2** | Untrusted (section 3). |
| T-08 | clang / LLVM 19.1.7 (official release, SHA-256 verified) | Host builds of unit and integration tests | TI2 | Target tests built with gcc | TD2 | **TCL2** | Before 164f11f the AFO units put the host clang 12 on PATH, so the AFO CRC run of ed40ee4 had no coverage (DEF-003); fixed, CRC-R3 ran on 19.1.7. |
| T-09 | llvm-profdata / llvm-cov 19.1.7 | Coverage | TI2 (over-reported coverage) | Inspector review of the report, observe-only mutation | TD2 | **TCL2** | CRC-R3: scope functions 100 % regions, branch and MC/DC reported null (straight-line code), whole-file line 31.8 % (out-of-scope functions) — recorded as deviations COV-01/COV-02 (TAA-FND-07). |
| T-10 | Generated host harness (`CHECK`, `forge_host_device.h` mapping the instance to a RAM struct) | Host unit and integration tests of the delivered code | TI2 | Renode and Robot tests | TD2 | **TCL2** | The RAM struct does not model register access types: write-only registers keep stale values, read-only and rc_w0 bits are plain memory (TAA-FND-09). |
| T-11 | Renode 1.17.0 with the factory's behavioural models `crc_model.py`, `spi_model.py`, `usart_model.py`, `gpio_model.py`, `tim_model.py` | Target tests SWE.5–SWE.6 on a simulated Cortex-M55 | TI2 | No silicon or HIL tests; the models are written (by Claude Code) from the same RM0486 text | TD3 | **TCL3** | Model validation against silicon, or tests on silicon (TAA-FND-06, TAA-FND-10). Labelled not silicon-verified. TIM time advances per register read (deterministic, not real time). |
| T-12 | Robot Framework 6.1 with `ForgeTarget.py` | SWE.6 test per software requirement on Renode | TI2 | Trace gate (each requirement tags a passing test), inspector | TD2 | **TCL2** | Same simulator limits as T-11. |
| T-13 | Cppcheck 2.7 with the MISRA addon | Static analysis of the delivered code | TI2 | Clang analyzer, guideline check, inspector | TD2 | **TCL2** | No MISRA compliance claimed. |
| T-14 | Clang static analyzer 19.1.7 | Static analysis | TI2 | Cppcheck | TD2 | **TCL2** | — |
| T-15 | Factory deterministic checkers (EARS, architecture, trace gate, implementation completeness, defects, finalizer, packager v0.5) | Freeze and inspect gates, packaging | TI2 (false PASS) | AI inspector, human review; factory code under CRE regression | TD2 | **TCL2** | Guideline check: automatable subset of the ST Cube2 HAL guideline; GL-ARG-01 on the five headers dispositioned by the owner (OD-2026-10-25-01). |
| T-16 | Fabro 0.362.0-nightly (a192bce) | Workflow graph, loops, hooks | TI2 (a step skipped) | Finalizer re-derives the outcome from gate logs; package policy requires every work product | TD1 | TCL1 | — |
| T-17 | binutils `size`, gcc `-fstack-usage` | Object size and per-function stack | TI2 | None independent; object-level, not a linked image | TD3 | **TCL3** | As TAA-RCC-001 T-17 (indicative figures only). |

### 4.3 Brownfield (delivered-code) tools

T-20 (intake), T-21 (intake build check), T-24 (fingerprint verification), T-26 (delivery injection) and T-27
(safety drafts, package records) are used as classified in TAA-RCC-001 v1.1 section 4.3 (TCL1). Changed or new:

| ID | Tool, version | Use case | TI | Detection | TD | TCL | Needed measure / note |
|---|---|---|---|---|---|---|---|
| T-22 | Scope resolution and register-effect extraction (`brownfield.scope`; generic peripheral prefix 411e02b; ST idioms 164f11f and fb682a8: MODIFY_REG clear mask, ATOMIC_* forms, POSITION_VAL folding, AFR[n] naming) | Register effects of each scope function for conformance and the trace map | TI2 (a missed or wrong effect hides a disagreement) | Requirement-based tests SWE.4–SWE.6 on the delivered code; inspectors; the rules were checked offline on ST's headers and against all earlier packages before use | TD2 | **TCL2** | Each rule has a regression test showing a real disagreement is still reported (TAA-FND-11). |
| T-23 | Conformance check (`brownfield.conformance`) | NO_CODE, NO_REQUIREMENT, CONTRADICTION between requirements, API calls and the delivered code; DEFERRED_TO_TESTS for values the code computes; rc_w0 clear idiom | TI2 (false CONFORMANT) | Requirement-based tests; inspectors | TD2 | **TCL2** | Deferred cases (USART baud rate, GPIO toggle) are decided by tests only and listed in each package (TAA-FND-11). |
| T-25 | Trace map (`brownfield.trace`) | Code trace map for the delivered code | TI2 | swtrace gate, SWE.3 inspector | TD2 | **TCL2** | — |

### 4.4 Operation tools (feature 005, feature 015)

| ID | Tool, version | Use case | TI | Detection | TD | TCL | Needed measure / note |
|---|---|---|---|---|---|---|---|
| T-28 | AFO Conductor (factory, PILOT under AUTH-AFO-PILOT-20261025) | Admits, launches, reconciles and dead-letters the benchmark orders; one at a time | TI1 (it never edits a work product or decides an outcome; the gates and packager do) | — | — | TCL1 | A wrong admission or retry costs a run, it cannot make a package READY. |
| T-29 | `benchmark.record`, `benchmark.queue` (factory) | Record the benchmark outcomes from the evidence; legacy queue runner | TI1 (reporting only) | — | — | TCL1 | — |

## 5. Tool use restrictions relied on

As TAA-RCC-001 v1.1 section 5. In addition: the SWE.1 roles cannot read the delivered code (requirements are written
before injection), and FROZEN delivered files are read-only in every work order.

## 6. Findings

TAA-FND-01, -02, -04, -05 and -06 of TAA-RCC-001 v1.1 apply unchanged to these work orders. TAA-FND-03 and -08 do
not apply (no DeepSeek node in any benchmark run). New:

| ID | Finding | Proposed measure |
|---|---|---|
| TAA-FND-07 | (as RCC, CRC data) Branch and MC/DC coverage are reported null for the straight-line LL functions; whole-file line coverage includes out-of-scope ST functions. | Accept with the recorded deviations, or report coverage on the scope functions only. |
| TAA-FND-09 | The host harness models registers as RAM: write-only registers keep stale values. In SPI-R2 this produced three false CODE defects (DEF-001/003/004) against ST's correct `SET_BIT(SPIx->IFCR, ...)`; fixed for later runs by adding RM0486 p.156 as an input and profile guidance (db6c68e), not by modelling the access types. | Model the access types (w, r, rc_w0, rc_w1) in the host harness, or keep the guidance and review each flag-clear test. |
| TAA-FND-10 | The five Renode peripheral models were written by an AI agent (Claude Code) from the converted RM0486 text and are tested only against that text; they are not validated against silicon. | Validate the models against silicon, or run the target tests on silicon. |
| TAA-FND-11 | Extraction and conformance rules for ST idioms were added during the benchmark (MODIFY_REG set/clear, ATOMIC_*, POSITION_VAL, AFR[n], computed writes deferred to tests, rc_w0 clear). A rule that is too wide could hide a disagreement. | Keep the regression tests (each shows a real disagreement still reported); review the deferred cases in each package. |

## 7. Open questions for the reviewer

| ID | Question |
|---|---|
| Q-01 | Do you accept that TAA-RCC-001 v1.1 carries over for the unchanged tools and that this document states only the differences? |
| Q-02 | Do you accept the proposed TI, TD and TCL, in particular TCL3 for T-01, T-04, T-11 and T-17? |
| Q-03 | Which measure do you choose for each TCL2 and TCL3 tool, and by when? |
| Q-04 | Should TAA-FND-09 to TAA-FND-11 be fixed before signing, or accepted as open items listed in the package limitations? |

## 8. Sources

TAA-RCC-001 v1.1 and its sources; `config/factory/peripherals/{crc,spi,usart,gpio,tim}.yaml`;
`factory/sim/stm32n6/{crc,spi,usart,gpio,tim}_model.py`; `examples/001{0,1,2,3,4}-*/inputs/inputs-manifest.json`,
`examples/0015-rm0486-conventions/inputs/RM0486-rev4-register-conventions-manifest.json`; `factory/python/forge_factory/
{brownfield,inspection/regmap.py,afo,benchmark}`; CRE decisions pd-7f820ff7..., pd-a18956d3..., pd-16b60ed6...,
pd-9f07f056..., pd-3775c590..., pd-99012d49..., pd-13c87c31...; the AFO work orders WO-AFO-7a6810a8baf9b9c4-a1 (SPI),
WO-AFO-707cd2711fc865be-a1 (CRC), WO-AFO-0756ac55b8ea81e6-a1 (SPI-R2), WO-AFO-eca972eb13bc60d1-a1 (CRC-R3):
`.forge-run/{model-profile.json, manifest.json, gates/gate-log.jsonl, defects/}`, `evidence/tool-results.jsonl`,
`workproducts/SWE.4-6/*`; OD-2026-10-20-03, OD-2026-10-25-01, OD-2026-10-25-02.

## 9. Review and signature (v1.0)

| Field | Value |
|---|---|
| Reviewed by (name, role) | |
| Reviewer's statement | |
| Answers to Q-01 to Q-04 | |
| Changes made during review | |
| Decision | ☐ Approved ☐ Approved with open findings (listed in the package limitations) ☐ Rejected |
| Date | |

Signing records the reviewer's engineering judgement on the confidence in these tools for the stated use cases. It
is not a tool qualification certificate, a safety approval or a certification.
