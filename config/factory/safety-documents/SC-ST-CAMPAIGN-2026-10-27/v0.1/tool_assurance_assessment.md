# Tool Assurance Assessment — Forge-C local toolchain on Omniverse2 for the campaign drivers (WWDG, RNG, LPTIM1)

| Field | Value |
|---|---|
| Document | TAA-STC-001, version 0.1 |
| Status | **DRAFT — for the owner's review, not reviewed, not approved** |
| Safety scopes | SC-WWDG-2026-10-27, SC-RNG-2026-10-27, SC-LPTIM-2026-10-27; target ASIL B for each (owner decision OD-2026-10-27-01) |
| Product | ST STM32CubeN6 v1.4.0 LL code delivered FROZEN (Feature 014 operation-24 campaign): WWDG `0016c-st-cube-wwdg`, RNG `0017c-st-cube-rng`, LPTIM1 `0018c-st-cube-lptim` |
| Basis | Work order inputs, source requirements hash per scope: WWDG `30ec84e960beee4bfff8515ee813ec6dffbdff3aedc22ba9d73faa1f37af1801`, RNG `fe6e9312cd4c04d9846170b9af1ca228d0c79c3c12da988a66f00a89578e3b96`, LPTIM1 `062a1ad94ec1edf8b880dc920b1351f6b5ff81ac7ab5ed9a9d57857b6c0d3012`; toolchain as it will be staged for the campaign on Omniverse2 from the Feature 014 branch (factory revision recorded per run) |
| Drafted by | Claude Opus 5.5 (Claude Code), 2026-10-27, from the factory records listed in section 8 |
| Responsible engineer | Jefferson Nascimento (owner) |

> Draft. It counts for a work order only after the owner reviews and signs it and its register entry is completed
> (config/factory/safety-documents/README.md). Any edit after signing, or a change to the work order inputs, un-signs
> it until it is re-reviewed. It records the drafter's assessment; it is not a tool qualification or certification.

## 1. Purpose and scope

For every tool that produces or verifies the campaign work products, this document states how the tool is used,
whether a malfunction could introduce an error into the work products or let an error go unnoticed (**tool impact**),
how likely an independent measure is to catch it (**error detection**), and the resulting **tool confidence level**.
The work orders deliver ST's code FROZEN: no tool writes the delivered driver code, so for the code itself every tool
is a verification tool. The tools do author the requirements, architecture, design descriptions and tests around it.

The main difference from TAA-STB-001 v1.0 is the **model routing**: these work orders run on Omniverse2 under the
Feature 014 local profile with **local Qwen models** for authors and inspectors, not Codex and Claude. A change of tool
version, configuration, model or use case invalidates the affected rows.

## 2. Classification scheme (summary in the drafter's words)

As in TAA-RCC-001 v1.1: **TI1** a malfunction cannot introduce or hide an error, **TI2** it can; **TD1** an error
is very likely caught by an independent measure, **TD2** fairly likely, **TD3** otherwise; **TCL1** for TI1 or
TI2+TD1, **TCL2** for TI2+TD2, **TCL3** for TI2+TD3 (TCL2/TCL3 need an additional measure for ASIL B).

## 3. AI models — approach

Unchanged principle from TAA-RCC-001 v1.1 section 3: the AI models are not relied on. Every AI-authored work product is
the output of an untrusted developer and must pass the deterministic gates, the host and simulator tests, the inspection
and human review of the safety-relevant work products.

For these runs the planned model routing is: **every agent node on a local model served by Ollama 0.34.0 on
Omniverse2** under the profile family `local-rtx-v2-omniverse2` (no cloud provider, no network egress for agents);
this draft assumes `qwen3.6:35b-a3b` for authors and inspectors. The base profile's default model is
`qwen3-coder:30b`; the exact model per role is frozen in the signed campaign manifest and recorded in each work
order's `.forge-run/model-profile.json` (TAA-FND-12). The SWE.1 inspector is the Feature 014 stepwise semantic
inspector in **advisory** mode (DA-FR-054): its findings are registered as gaps for human review, they do not stop the
run. Its measured rates are known issue KI-014-003: on the held-out Feature 015 GPIOA and CRC baselines it flagged 12/12
seeded defects but falsely rejected 2/2 clean baselines (calibration at 9300475); later rule changes are unmeasured on
held-out data.

Consequence for independence: author and inspector are expected to be the **same model family** (Qwen), unlike
TAA-STB-001 (Codex authors, Claude inspectors). An AI inspection is therefore weaker evidence here (TAA-FND-13).

## 4. Tool classification

### 4.1 Tools whose output goes into the released work products

| ID | Tool, version | Use case | TI | Detection | TD | TCL | Needed measure / note |
|---|---|---|---|---|---|---|---|
| T-01 | arm-none-eabi-gcc (version as staged on Omniverse2; 10.3.1 on loop10) | Intake `-fsyntax-only` build check of the CMSIS delivery; target objects for the Renode tests, size and stack figures | TI2 | Renode target and Robot tests run gcc-built images; host tests use clang | TD3 | **TCL3** | As TAA-RCC-001 T-01 (TAA-FND-01, TAA-FND-02). The delivered code is not changed by any tool. |
| T-02 | Local author model (`qwen3.6:35b-a3b` assumed) via Ollama 0.34.0 | Authors requirements (from RM0486 and the scope, before the code enters the work order), architecture, design descriptions, unit/integration/target/qualification tests | TI2 | Freeze gates (EARS, architecture, trace, register-map, conformance against the delivered code), cppcheck, clang analyzer, host and Renode tests, Robot, inspector, human review | TD2 | **TCL2** | Untrusted output (section 3). Its capability for full SWE.1–SWE.6 driver work is not qualified (Feature 014 role capability NOT_RUN for authors). |
| T-03 | Peripheral profiles `config/factory/peripherals/{wwdg,rng,lptim}.yaml` (factory, feature 009 mechanism; written by Claude Code) | Prompt texts that tell the authors the scope, the RM write constraints, the effect-encoding rules and the test conventions per peripheral | TI2 (a wrong instruction can bias requirements or tests) | Requirements come from RM0486 sections; inspector; conformance against the delivered code; tests | TD2 | **TCL2** | Hardware facts are kept in the RM inputs; profiles cite RM sections. Not yet reviewed through a CRE promotion decision (TAA-FND-14). |
| T-04 | `docs.pdf2md` (factory) with poppler `pdftotext -layout` | Converts RM0486 chapters 47, 58, 60 and the memory-map pages 177/181 into the Markdown inputs | TI2 (a converted value differs from the PDF) | Requirements, register contract, conformance, Renode models and tests all use the same converted text (common cause) | TD3 | **TCL3** | Independent check of the register tables used against the original PDF (TAA-FND-06). PDF and Markdown SHA-256 are recorded in each `inputs-manifest.json` (PDF 83cb7e9c…). |
| T-05 | `inspection.regmap` (factory) | Register offsets, reset values and fields from the RM sections | TI2 | Delivered CMSIS headers used first for field masks in conformance; the independent second parser `assurance.hardware`; tests; inspectors | TD2 | **TCL2** | Both parsers read every in-scope register of the three chapters with fields and access types (onboarding check 2026-10-27). |
| T-06 | git | Workspace version control, baselines | TI2 | Packaged files listed with SHA-256; archives hash-checked | TD1 | TCL1 | — |

### 4.2 Verification tools

| ID | Tool, version | Use case | TI | Detection | TD | TCL | Needed measure / note |
|---|---|---|---|---|---|---|---|
| T-07 | Local inspector model (same family as T-02) incl. the stepwise SWE.1 inspector, advisory | Inspections SWE.1–SWE.6, Release Manager | TI2 (false PASS, or false gaps) | Deterministic gates run regardless; the EASA gate does not count an AI PASS as independent evidence; human review of every registered gap | TD2 (lower than TAA-STB-001: same family) | **TCL2** | Untrusted (section 3); KI-014-003 rates; TAA-FND-13. |
| T-08 | clang / LLVM 19.1.7 (as on loop10; Omniverse2 version as staged) | Host builds of unit and integration tests | TI2 | Target tests built with gcc | TD2 | **TCL2** | — |
| T-09 | llvm-profdata / llvm-cov 19.1.7 | Coverage | TI2 (over-reported coverage) | Inspector review of the report, observe-only mutation | TD2 | **TCL2** | Straight-line LL functions: branch and MC/DC are reported null (TAA-FND-07). |
| T-10 | Generated host harness (`CHECK`, `forge_host_device.h` mapping the instance to a RAM struct) | Host unit and integration tests of the delivered code | TI2 | Renode and Robot tests | TD2 | **TCL2** | The RAM struct does not model access types: LPTIM_ICR (w) keeps stale values, rc_w0 bits (WWDG_SR, RNG_SR) and set-only bits (WDGA, EWI) are plain memory (TAA-FND-09). |
| T-11 | Renode 1.17.0 with the factory's behavioural models `wwdg_model.py`, `rng_model.py`, `lptim_model.py` | Target tests SWE.5–SWE.6 on a simulated Cortex-M55 | TI2 | No silicon or HIL tests; the models are written by AI agents (Claude Code) from the same RM0486 text | TD3 | **TCL3** | Model validation or tests on silicon (TAA-FND-06, TAA-FND-10). Model limits stated in the profiles: no WWDG reset, deterministic RNG sequence (not entropy, no clock/seed errors unless scripted), no LPTIM enable/APB-to-kernel/COUNTRST latency; time advances per register read. |
| T-12 | Robot Framework with `ForgeTarget.py` | SWE.6 test per software requirement on Renode | TI2 | Trace gate (each requirement tags a passing test), inspector | TD2 | **TCL2** | Same simulator limits as T-11. |
| T-13 | Cppcheck with the MISRA addon | Static analysis of the delivered code | TI2 | Clang analyzer, guideline check, inspector | TD2 | **TCL2** | No MISRA compliance claimed. |
| T-14 | Clang static analyzer 19.1.7 | Static analysis | TI2 | Cppcheck | TD2 | **TCL2** | — |
| T-15 | Factory deterministic checkers (EARS, architecture, trace gate, implementation completeness, defects, finalizer, packager) | Freeze and inspect gates, packaging | TI2 (false PASS) | Inspector, human review; factory code under regression tests | TD2 | **TCL2** | Feature 014 branch adds the advisory gap route (DA-FR-054): a phase can continue with registered gaps; the package lists them. |
| T-16 | Fabro (version as staged in the Omniverse2 runtime) | Workflow graph, loops, hooks | TI2 (a step skipped) | Finalizer re-derives the outcome from gate logs; package policy requires every work product | TD1 | TCL1 | — |
| T-17 | binutils `size`, gcc `-fstack-usage` | Object size and per-function stack | TI2 | None independent; object-level, not a linked image | TD3 | **TCL3** | As TAA-RCC-001 T-17 (indicative figures only). |

### 4.3 Brownfield (delivered-code) tools

T-20 (intake), T-21 (intake build check), T-24 (fingerprint verification), T-26 (delivery injection) and T-27 (safety
drafts, package records) are used as classified in TAA-RCC-001 v1.1 section 4.3 (TCL1). T-22 (scope resolution and
register-effect extraction), T-23 (conformance) and T-25 (trace map) are used as in TAA-STB-001 v1.0 (TCL2); the
extraction of the three new headers was checked against ST's real code in the peripheral tests (WWDG `~EWIF`, RNG
`~CEIS`/`~SEIS` and the CED/CONDRST pair, LPTIM `SET_BIT` on the write-only ICR).

### 4.4 Operation tools (Feature 014)

| ID | Tool, version | Use case | TI | Detection | TD | TCL | Needed measure / note |
|---|---|---|---|---|---|---|---|
| T-28 | AFO Conductor with Feature 014 durable autonomy (operation-24 campaign, signed manifest) | Admits, launches, reconciles, recovers (local diagnosis agent) and dead-letters the campaign orders while faults are injected | TI1 for the work products (it never edits a work product or decides an outcome; the gates and packager do) | — | — | TCL1 | Recovery may launch a new attempt with a material difference (lessons, resume of validated phases); every attempt passes the same gates. Fault injection can end attempts BLOCKED; that costs runs, it cannot make a package READY. |
| T-29 | Ollama 0.34.0 serving the local models; LLM gateway (factory) | Model serving, admission and usage accounting | TI2 (a different model or quantisation served) | Model identity pinned by digest in the profile and checked at launch; recorded per run | TD1 | TCL1 | Usage may be UNKNOWN (KI-014-002); never read as zero. |

## 5. Tool use restrictions relied on

As TAA-RCC-001 v1.1 section 5 and TAA-STB-001 v1.0 section 5: the SWE.1 roles cannot read the delivered code
(requirements are written before injection), and FROZEN delivered files are read-only in every work order. In
addition: agents on Omniverse2 have no network route (local-only profile); production agents use only role-approved
MCP operations with versioned skills.

## 6. Findings

TAA-FND-01, -02, -04, -05 and -06 of TAA-RCC-001 v1.1 and TAA-FND-07, -09, -10 and -11 of TAA-STB-001 v1.0 apply to
these work orders. New:

| ID | Finding | Proposed measure |
|---|---|---|
| TAA-FND-12 | The exact local model per role and the tool versions on Omniverse2 (gcc, LLVM, Renode, Fabro) are not yet recorded for the campaign; this draft assumes `qwen3.6:35b-a3b` and the loop10 versions. | Freeze them in the signed campaign manifest; re-check this document against the first run's `model-profile.json` and `evidence/tool-results.jsonl`. |
| TAA-FND-13 | Author and inspector are expected to be the same model family (Qwen); the stepwise inspector falsely rejected 2/2 clean held-out baselines (KI-014-003) and runs in advisory mode. | Human review of every registered gap and of the SWE.1 requirements; or a different inspector family for safety-relevant work products. |
| TAA-FND-14 | The three peripheral profiles and Renode models were written on the Feature 014 branch without a CRE promotion decision (the branch is rejected for promotion as a whole, KI-014-010). | Review them with PR #42, or run the CRE promotion gate on them separately. |
| TAA-FND-15 | The local author's capability for full SWE.1–SWE.6 driver work is unqualified; runs may stop BLOCKED or produce weaker work products than the Codex/Claude line. | Treat campaign packages as evidence of operation, not of product quality, until qualified; compare against the Feature 015 baselines. |

## 7. Open questions for the reviewer

| ID | Question |
|---|---|
| Q-01 | Do you accept that TAA-RCC-001 v1.1 and TAA-STB-001 v1.0 carry over for the unchanged tools and that this document states only the differences? |
| Q-02 | Do you accept the proposed TI, TD and TCL, in particular TCL2 for the same-family inspector T-07 and TCL3 for T-01, T-04, T-11 and T-17? |
| Q-03 | Which measure do you choose for each TCL2 and TCL3 tool, and by when? |
| Q-04 | Do you confirm `qwen3.6:35b-a3b` for authors and inspectors (TAA-FND-12), or another allowed local model? |
| Q-05 | Should TAA-FND-12 to TAA-FND-15 be fixed before signing, or accepted as open items listed in the package limitations? |

## 8. Sources

TAA-RCC-001 v1.1, TAA-STB-001 v1.0 and their sources; `config/factory/peripherals/{wwdg,rng,lptim}.yaml`;
`factory/sim/stm32n6/{wwdg,rng,lptim}_model.py` and `stm32n6_{wwdg,rng,lptim}.repl`;
`examples/001{6,7,8}-*/inputs/inputs-manifest.json`; `config/factory/profiles/local-rtx-v2-omniverse2*.yaml`;
`evidence/014-durable-local-autonomy/known-issues.md` (KI-014-002, -003, -010) and
`evidence/014-durable-local-autonomy/stepwise-inspector-20261026/README.md`; OD-2026-10-27-01.

## 9. Review and signature (to be completed by the owner)

| Field | Value |
|---|---|
| Reviewed by (name, role) | |
| Reviewer's statement | |
| Answers to Q-01 to Q-05 | |
| Changes made during review | |
| Decision | ☐ Approved ☐ Approved with open findings (listed in the package limitations) ☐ Rejected |
| Date | |

Signing records the reviewer's engineering judgement on the confidence in these tools for the stated use cases. It
is not a tool qualification certificate, a safety approval or a certification.
