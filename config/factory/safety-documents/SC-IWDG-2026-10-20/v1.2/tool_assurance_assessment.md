# Tool Assurance Assessment — Forge-C toolchain for the STM32N6 IWDG LL and HAL drivers

| Field | Value |
|---|---|
| Document | TAA-IWDG-001, version 1.2 |
| Status | **Approved with open findings** — signed by Jefferson Nascimento (owner), 2026-10-20 |
| Safety scope | SC-IWDG-2026-10-20, target ASIL B (owner decision 2026-10-20, OD-2026-10-20-04) |
| Product | IWDG LL driver (example `0009a-iwdg-ll`) and IWDG HAL driver on that LL (example `0009b-iwdg-hal`) |
| Basis | Work order inputs, source requirements hash `bfee8b2ee260d6e114e2cf92b77336da4c8534e11efd53cf3c2a7995910b9286`; toolchain as used by `WO-0009A-STM32N6-IWDG-LL-i003` (factory commit 83ee4c7) and by the HAL runs `WO-0009B-STM32N6-IWDG-HAL-h001` to `-h003` (factory commits 856c3fb, 029fd6e, 55e9532); (v1.2) HAL v2 runs `-h004` and `-h005` (factory commits 61a5f98, 2e59a38) |
| Drafted by | Claude Opus 5.5 (Claude Code), v1.0, v1.1 and v1.2 2026-10-20, from the factory records listed in section 8 |
| Responsible engineer | Jefferson Nascimento (owner) |

> Signed version 1.2 (owner decision OD-2026-10-20-08). It applies to IWDG work orders (LL and HAL v2)
> whose inputs match the basis above. Any edit to this file, or a change to the work order inputs, un-signs it
> until it is re-reviewed. It records the reviewer's engineering judgement; it is not a safety approval or
> certification. It supersedes version 1.1 (OD-2026-10-20-06, file `../v1.1/tool_assurance_assessment.md`, kept unchanged).

## Change log

| Version | Date | Change |
|---|---|---|
| 1.0 | 2026-10-20 | Signed (OD-2026-10-20-05): toolchain of the IWDG LL run i003. |
| 1.1 | 2026-10-20 | Signed (OD-2026-10-20-06). Owner request "adress all" (2026-10-20): the tools of the HAL runs h001–h003 are assessed. New: model use in the HAL runs and the Fabro run-title requests (section 3), T-21 to T-25 (section 4.3), updates to T-03, T-10, T-12, T-16 and T-20, TAA-IWDG-FND-07 to FND-10 and status of FND-01, -04, -05 (section 6), Q-06 to Q-09 (section 7). v1.0 rows otherwise unchanged. |
| 1.2 (draft) | 2026-10-20 | HAL v2 (owner "go", FND-07/FND-08 of SSA-IWDG-001): the tools of the HAL v2 runs h004 and h005 are assessed. New: model use in h004/h005 (section 3), T-26 to T-28 (section 4.4), updates to T-10, T-12, T-13, T-16, T-18 and T-20, status of FND-04 and FND-08, TAA-IWDG-FND-11 to FND-13 (section 6), Q-10 to Q-12 (section 7), section 11 (v1.2 signature). Everything else is unchanged from the signed v1.1. |

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
- **In the HAL runs h001–h003** (factory with CAPA-051): all 14 author nodes on Codex Sol 6.1 (codex 0.162.1,
  reasoning high) and all 7 inspector and Release Manager nodes on Claude Opus 5.5 (claude-agent-acp 0.85.1; the
  Claude Code version behind it NOT_VERIFIED); each run profile records "deepseek-flash (deepseek) is suspended
  (OD-2026-10-20-03); it serves no agent node in this run".
- **Outside the workflow graph** (v1.1 finding, CAPA-052): the Fabro server generates a title for every new run with
  its default run model (`deepseek-flash`), through the forge LLM gateway. The Fabro log shows such requests at
  2026-10-20T04:28:13Z (i003) and 06:53:12Z (h001); both failed at DeepSeek ("response_format type is unavailable"),
  with no tokens reported. What text the title request carried is NOT_VERIFIED (the gateway meters usage, not
  content). h002 (07:28:36Z): the gateway had been stopped, the request failed locally. h003 (08:09:50–52Z): the
  patched gateway refused three attempts before any network call (`upstream_called: false`).
- **(v1.2) In the HAL v2 runs h004 and h005**: the same model use as h001–h003 — 14 author nodes on Codex Sol 6.1, 7
  inspector and Release Manager nodes on Claude Opus 5.5, no agent node on the run model (each run profile records the
  DeepSeek suspension). The Fabro run-title requests were refused by the gateway before any network call: h004
  2026-10-20T13:25:46–47Z (2 attempts), h005 14:46:33–34Z (3 attempts) (`refused: MODEL_SUSPENDED:deepseek:OD-2026-10-20-03`,
  `upstream_called: false`). The last request that reached DeepSeek is still h001's (06:53:12Z).

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

**v1.1 updates of the rows above for the HAL runs:**

- T-03: no agent node ran on DeepSeek in h001–h003; the row stays for i003 (LL) only.
- T-10: h003 reports line, branch and MC/DC 100 % on the host (HAL unit tests on the LL test double).
- T-12: h003 ran 11 target checks on the same behavioural IWDG model (2 images); the limits of TAA-IWDG-FND-02 apply
  unchanged; the run summary now names the IWDG model (FND-05 resolved, feature 009 PG-T018).
- T-16: the HAL path of two factory checks was defective and produced **false FAILs** (no false PASS was observed),
  each detected and escalated by the authors as a FACTORY defect: the SWE.3 implementation check read the SWE.2
  allocation with the RCC prefix (h001, CAPA-053, decision pd-4f8c9ac73ee2b54221ef), and the SWE.4 skill named a
  packager-generated file the policy forbids (h002, CAPA-054, pd-85ae8648f1096332915d).
- T-20: the helpers are peripheral-generic since feature 009 phase 8 (PG-T018, pd-646b5ed9fb3970231fe2). h003: SWE.4
  oracle 24/24 contract cases PASS, mutation 14/14 killed, API execution PASS, negative/boundary cases NOT_SUPPORTED
  (no boundary derivable for this peripheral), fault injection partly NOT_RUN/NOT_SUPPORTED (no clock tree in the
  model); SWE.1 still reports REQ_SOURCE_MISMATCH for requirements that cite several pages (a verifier defect that
  affects RCC too) and REQ_NOT_TESTABLE for SWR-007.

**v1.2 updates for the HAL v2 runs (h004, h005):**

- T-10: h005 line, branch and MC/DC 100 % on the host (HAL v2 unit tests on the LL test double with the harness time
  base, T-28).
- T-12: h005 18 target checks on the behavioural IWDG model, including scenario `never_ready` for the timeout and
  write-protect path (SWR-006) and deadline/wraparound checks (SWR-008); the limits of TAA-IWDG-FND-02 apply; the
  model's write-protect behaviour is written from the same RM0486 text (TAA-IWDG-FND-03).
- T-13: h005 Robot 14/14 tests, 14/14 requirements; the reset invariant SWR-010 runs as a target scenario (CAPA-059,
  T-27); the stack requirement SWR-013 is measured with the reference leaf time base and the assumption is written to
  the Robot log (`ASSUMPTION: external time base HAL_GetTick() measured as a reference leaf ...`, CAPA-063, T-26).
- T-16: h004 found one more factory gap with the HAL v2: the stack call-graph measurement rejected the external time
  base (false FAIL, escalated by the authors as DEF-003, CAPA-063, decision `pd-c172fd820a312af0785a`). The HAL v2
  change itself passed the CRE gate (`pd-ea6e2bd4c0229a31aac7`).
- T-18: h005 text 212 B, data 0, bss 0, max frame 24 B (`hal_iwdg_wait_ready`).
- T-20: h005 SWE.1 SOURCE_CONTRADICTION_CHECK and TESTABILITY_CHECK PASS (CAPA-055); SWE.4 oracle 23 cases PASS
  (including INIT_TIMEOUT_PVU/RVU with the time-base stub), mutation PASS, API execution PASS, negative/boundary
  NOT_SUPPORTED; SWE.2 FLOW_SCHEDULING_ANALYSIS UNKNOWN; SWE.5 BOUNDARY_INTEGRATION FAIL (no boundary category in the
  integration tests; SSA-IWDG-FND-13).

### 4.3 Tools new for the HAL (v1.1)

| ID | Tool, version | Use case | TI | Detection | TD | TCL | Needed measure / note |
|---|---|---|---|---|---|---|---|
| T-21 | Fabro server run-title generation (Fabro 0.362.0-nightly, default run model) | Generates a display title for each run | TI1 (no work product; a title is never evidence) | — | — | TCL1 | Data-flow concern rather than tool confidence: it sent requests to a suspended provider (i003, h001). Now refused by the gateway (CAPA-052, pd-b80c0915a73b8ef70bb6); TAA-IWDG-FND-07. |
| T-22 | LL test double generator (`workflow.ll_fake`, CAPA-038, made peripheral-generic in feature 009 phase 8) | HAL unit tests (SWE.4) observe the HAL only through the provided LL API: call log, call order, scripted flag values | TI2 (a wrong double can let a HAL error pass) | Generated from the provided LL header (no hand-written behaviour); `run_unit` regenerates it and fails when it was edited; integration tests use the real LL; Renode target tests; SWE.4 inspector | TD2 | **TCL2** | No hardware behaviour (no update latency, no write protection): see SSA-IWDG-FND-12. |
| T-23 | Register contract with the `busy` option and the independent oracle (`assurance.register_contract`, `assurance.oracle_gen`, feature 009 phase 8) | SWE.1 contract of the register effects; SWE.4 oracle compiled from the contract and the RM0486 constants, run against the HAL on a RAM register array (h003: 24 cases, 4 with a status flag held set) | TI2 (false PASS) | Unit tests (call order), Renode target tests, inspectors; the factory tests seed two faulty HALs (no final refresh; ignored update flags) that the oracle must fail | TD2 | **TCL2** | The oracle sees only the final register values: the key order and the wait's time bound are not checked by it (TAA-IWDG-FND-08). |
| T-24 | Provided-LL handover (`workorder.provided_ll`) | Gives the HAL work order the verified LL header of i003, read-only and hash-pinned (SHA-256 5996e7e6…) | TI2 (a wrong LL would be built on) | The source work order must have passed all six gates and be of the same peripheral; the implementation check fails on any change (`PROVIDED_COMPONENT_CHANGED`); the hash is in the manifest and the package | TD1 | TCL1 | None. |
| T-25 | Forge LLM gateway with provider suspension (`forge_factory.llm_gateway`, CAPA-052) | Refuses every request to a suspended provider before any network call; meters the refusal | TI1 (no work product) | Gateway meter (`upstream_called: false`); `workorder.run` refuses native agent nodes on a suspended model (CAPA-051) | — | TCL1 | Enforces OD-2026-10-20-03; verified in h003. |

### 4.4 Tools new or changed for the HAL v2 (v1.2)

| ID | Tool, version | Use case | TI | Detection | TD | TCL | Needed measure / note |
|---|---|---|---|---|---|---|---|
| T-26 | Robot stack measurement with a reference leaf time base (`factory/sim/stm32n6/ForgeTarget.py`, CAPA-063) | Bounds the driver stack (SWR-013) when the HAL calls the external `HAL_GetTick`; the reference is a free-running counter compiled into the stack call graph only | TI2 (a deeper real time base would make the bound optimistic) | The assumption is written to the Robot log; nothing checks the system's real `HAL_GetTick` | TD3 | **TCL3** | Integrator obligation AOU-13 (SSA-IWDG-001); review the product's time base against it. |
| T-27 | SWE.1 gate check `STARTUP_INVARIANT_ON_HOST_TEST` (`inspection/test_mapping.py`, CAPA-059) | Refuses a reset/startup invariant mapped to a host unit test; such requirements go to the Robot suite | TI2 (a missed mapping leaves a tautological host test) | SWE.4 inspector (it found the b006 case) | TD2 | **TCL2** | None beyond the CRE regression. |
| T-28 | Time-base stubs: `HAL_GetTick` in the generated unit-test harness (`workflow/scaffold.py`, +1 ms per call, reset by `ut_reset`) and in the contract oracle (`assurance/oracle_gen.py`), profile `hal.time_base` (feature 009 PG-T021) | Lets host tests and the oracle exercise the time-bounded wait | TI2 (a stub that does not behave like the real time base can let a timing error pass) | Renode/Robot target scenarios use author-written counters, also not a real clock | TD3 (no real-time reference anywhere in the evidence) | **TCL3** | Silicon measurement of `HAL_IWDG_Init` with the product's time base (SSA-IWDG-FND-14). |

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

**Status of the v1.0 findings for the HAL (v1.1):** FND-01 applies to i003 (LL) only — no agent node of h001–h003 ran
on DeepSeek. FND-04: MC/DC measured (100 %) and the oracle and mutation evidence accepted for the HAL (h003); still
open for i003. FND-05: resolved (the run summary names the IWDG model since PG-T018). FND-02, FND-03 and FND-06 are
unchanged and apply to the HAL runs.

**Status for the HAL v2 (v1.2):** FND-04 as for h003 (MC/DC 100 %, oracle and mutation PASS in h005). FND-07 unchanged
(closed by CAPA-052; h004/h005 requests refused). FND-08: the oracle still checks final register values only; for the
HAL v2 the time bound and the key order are verified by the unit tests with the harness time base, the Robot
deadline/wraparound checks and the Renode model (T-28 limits apply). FND-09: one more HAL-path factory gap (CAPA-063)
failed safe the same way. FND-02, FND-03, FND-06 and FND-10 unchanged.

**New findings (v1.1):**

| ID | Finding | Proposed measure |
|---|---|---|
| TAA-IWDG-FND-07 | The Fabro server's run-title generation (T-21) sent requests to DeepSeek outside the workflow graph (i003 04:28:13Z, h001 06:53:12Z), after the owner had restricted model use; the content of those requests is NOT_VERIFIED. | Fixed by CAPA-052 (gateway refusal, verified in h003). Optionally give the Fabro server a non-network default model or disable title generation if a later Fabro version allows it. |
| TAA-IWDG-FND-08 | The register-contract oracle (T-23) checks only final register values; the key sequence order and the time bound of the update wait are verified only by the unit tests on the LL test double and by the Renode model. | Accept as a known limit, or extend the oracle with an access trace (ordered register writes). |
| TAA-IWDG-FND-09 | The HAL paths of two factory checks were new and defective (CAPA-053, CAPA-054); both failed safe (false FAIL, escalated by the authors), neither produced a false PASS. | Keep the CRE regression; add HAL-on-non-RCC fixtures to the golden benchmark. |
| TAA-IWDG-FND-10 | The LL test double (T-22) has no hardware timing or protection behaviour (see SSA-IWDG-FND-12). | Extend the Renode IWDG model (TAA-IWDG-FND-02) and test on silicon. |

**New findings (v1.2):**

| ID | Finding | Proposed measure |
|---|---|---|
| TAA-IWDG-FND-11 | The HAL v2 time behaviour is verified only against counter stubs (T-28) and the behavioural model (T-12): no real clock, no LSI, no silicon. | Silicon measurement with the product's time base (SSA-IWDG-FND-14). |
| TAA-IWDG-FND-12 | The SWR-013 stack bound depends on the assumption that the system's `HAL_GetTick` is a leaf no deeper than the reference (T-26). | Integrator review against AOU-13; or link the product's time base into the measurement. |
| TAA-IWDG-FND-13 | The observe-only SWE.5 BOUNDARY_INTEGRATION verifier FAILs h005 (no boundary category in the integration tests); it decides nothing (T-20, TI1). | Add boundary integration cases in a next HAL work order (SSA-IWDG-FND-13). |

## 7. Open questions for the reviewer

| ID | Question |
|---|---|
| Q-01 | Do you accept the AI-model approach of section 3 for this product, as for RCC? |
| Q-02 | Do you accept the proposed TI, TD and TCL per tool, in particular TCL3 for T-01, T-04, T-12 and T-18, and TCL2 for the peripheral profile (T-05)? |
| Q-03 | Which measure do you choose for each TCL2 and TCL3 tool, and by when? |
| Q-04 | Should the i003 evidence be replaced by a re-run without DeepSeek before signing (TAA-IWDG-FND-01)? |
| Q-05 | Should the findings be fixed before signing, or accepted as open items listed in the package limitations? |
| Q-06 | (v1.1) Do you accept the proposed TI, TD and TCL of T-21 to T-25, in particular TCL2 for the LL test double (T-22) and the contract oracle (T-23)? |
| Q-07 | (v1.1) Do you accept the AI-model approach of section 3 for the HAL, with the HAL evidence from h003 (no DeepSeek agent node)? |
| Q-08 | (v1.1) Is the Fabro run-title traffic (TAA-IWDG-FND-07) acceptable as closed by CAPA-052, or do you require the Fabro default model to be changed as well? |
| Q-09 | (v1.1) Should the oracle be extended to check the order of register writes (TAA-IWDG-FND-08)? |
| Q-10 | (v1.2) Do you accept the proposed TI, TD and TCL of T-26 to T-28, in particular TCL3 for the stack measurement with the reference time base (T-26) and for the time-base stubs (T-28)? |
| Q-11 | (v1.2) Do you accept the AI-model approach of section 3 for the HAL v2, with the evidence from h005 (no DeepSeek agent node; run-title requests refused)? |
| Q-12 | (v1.2) Which measure do you choose for TCL3 tools T-26 and T-28 (silicon measurement, integrator review of the time base), and by when? |

## 8. Sources

`config/factory/safety-documents/SC-RCC-2026-10-18/tool_assurance_assessment.md` (TAA-RCC-001 v1.0), the i003
workspace (`.forge-run/model-profile.json`, `.forge-run/manifest.json`, `evidence/tool-results.jsonl`,
`.forge-run/assurance/gate-log.jsonl`), `evidence/v0.4/runs/PG-T012/`, `config/factory/peripherals/iwdg.yaml`,
`factory/sim/stm32n6/iwdg_model.py`, `evidence/cre/capa/i003-capas.json`, `config/factory/model-suspensions.yaml`,
`evidence/easa/owner-decisions/OD-2026-10-20-03-deepseek-suspended.json`; tool versions from the provenance of each
i003 tool result and from `arm-none-eabi-gcc --version` and `fabro --version` on the factory host (2026-10-20).
(v1.1) `evidence/v0.4/runs/PG-T019/` (h001–h003); the h003 workspace (`.forge-run/model-profile.json`,
`evidence/tool-results.jsonl`, `.forge-run/assurance/gate-log.jsonl` and `reports/SWE.4/`); the Fabro cloud server log
(`run_title_generation` warnings) and the gateway meter `state/llm-gateway/usage-cloud-deepseek.jsonl` (read
2026-10-20); `evidence/cre/capa/h001-capa-052.json`, `h001-capa-053.json`, `h002-capa-054.json`;
`factory/python/forge_factory/workflow/ll_fake.py`, `assurance/register_contract.py`, `assurance/oracle_gen.py`,
`llm_gateway.py`.
(v1.2) `evidence/v0.4/runs/PG-T021/` (h004, h005; h005 Robot `output.xml` with the ASSUMPTION line); the h005 workspace
(`.forge-run/model-profile.json`, `.forge-run/manifest.json`, `evidence/tool-results.jsonl`,
`.forge-run/assurance/gate-log.jsonl`, `.forge-run/assurance/reports/`); the gateway meter refusals (read 2026-10-20);
`evidence/cre/capa/capa-059.json`, `capa-063.json`; decisions `pd-ea6e2bd4c0229a31aac7`, `pd-c172fd820a312af0785a`;
`factory/sim/stm32n6/ForgeTarget.py`, `factory/python/forge_factory/inspection/test_mapping.py`,
`workflow/scaffold.py`, `assurance/oracle_gen.py`, `config/factory/peripherals/iwdg.yaml`.

## 9. Review and signature (v1.0, as signed)

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

## 10. Review and signature (v1.1, as signed)

| Field | Value |
|---|---|
| Reviewed by (name, role) | Jefferson Nascimento, owner and responsible engineer |
| Reviewer's statement | "sign pr 22" (2026-10-20, with "I accept PR 23") |
| Answers to Q-01 to Q-09 | Q-01, Q-02, Q-06 and Q-07: the AI-model approach (LL and HAL) and the proposed TI, TD and TCL (T-01 to T-25) accepted as drafted. Q-05: the findings stay open. Q-03, Q-04, Q-08 and Q-09: not answered at signing; they remain open. |
| Changes made during review | None to the analysis; status and this section completed on signing |
| Decision | ☐ Approved ☒ Approved with open findings (listed in the package limitations) ☐ Rejected |
| Date | 2026-10-20 |

Signing records the reviewer's engineering judgement on the confidence in these tools for the stated use cases. It
is not a tool qualification certificate, a safety approval or a certification.

## 11. Review and signature (v1.2)

| Field | Value |
|---|---|
| Reviewed by (name, role) | Jefferson Nascimento, owner and responsible engineer |
| Reviewer's statement | "I sign" (2026-10-20), in reply to the v1.2 drafts sent with their SHA-256 (SSA 1c5163f7..., TAA 3e94d71d...) |
| Answers to Q-01 to Q-12 | Q-01, Q-02, Q-06 and Q-07: accepted (v1.1). Q-10 and Q-11: the TI, TD and TCL of T-26 to T-28 and the AI-model approach for the HAL v2 accepted as drafted. Q-05: the findings stay open. Q-03, Q-04, Q-08, Q-09 and Q-12: not answered at signing; they remain open. |
| Changes made during review | None to the analysis; status and this section completed on signing |
| Decision | ☐ Approved ☒ Approved with open findings (listed in the package limitations) ☐ Rejected |
| Date | 2026-10-20 |

Signing records the reviewer's engineering judgement on the confidence in these tools for the stated use cases. It
is not a tool qualification certificate, a safety approval or a certification.
