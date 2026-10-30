# Forge-C — Delivery-First End-to-End Vertical Slice

**Implementation specification + execution plan (Codex handoff)**  
**Date:** 2026-10-30  
**Status:** DEVELOPMENT_IMPLEMENTED / AFO_NATIVE_TRIAL_RUNNING / DF-M1_NOT_PROVEN
**Repository:** [`jnsagai/forge-c`](https://github.com/jnsagai/forge-c)  
**Target integration line:** `feat/014-durable-local-autonomy` (stacked Feature 014 / PR #42; verify current HEAD and PR state before coding)  
**Proposed repository destination:** `specs/014-durable-local-autonomy/DELIVERY-FIRST-E2E.md`  
**Scope:** An opt-in, strictly local/offline, QM *development* mode of the existing Forge-C engine; **not** a new factory, release process, or full replacement for Feature 014.

> **Decision:** Good, real, measured software delivery beats perfect-looking incomplete process execution. Finish one small Qwen-authored, compiled, independently tested, fully packaged software increment before expanding architecture, autonomous self-repair, learning, or qualification campaigns. **Never convert a failing test, missing source, or absent inspection into a PASS.**

Current source/evidence and per-task limits are recorded in
[DELIVERY-FIRST-IMPLEMENTATION.md](DELIVERY-FIRST-IMPLEMENTATION.md). The original
motivation below is a dated baseline; a new candidate PASS is not a retrospective
change to earlier failed jobs or a claim that DF-M1 is complete.

## 0. Read this first — implementation contract

This document supersedes **only the immediate implementation priority** of earlier Feature 014 development handoffs. It does **not** retrospectively change historical scopes, verdicts, model usage, budgets, receipts, packages, operator decisions, or existing strict release obligations.

1. Read repository instructions, `.specify/memory/constitution.md`, and Feature 014 `spec.md`, `plan.md`, `tasks.md`, `acceptance-tests.md`, `validation.md`, `HANDOVER-CODEX.md`, `IMPLEMENTATION-INCREMENTAL-E2E.md`, and `GENERIC-EMBEDDED-C.md` at the **current target checkout**.
2. Read the [28–30 October engineering report](https://github.com/jnsagai/forge-c/blob/main/specs/014-durable-local-autonomy/ASTRA-REVIEW-20261028-30.md) and its source-pinned evidence. The report's reviewed source `c221b65e` and the running Qwen source `451038c4` were **different**. Treat these as dated references, not as today's installed runtime.
3. Preserve and extend the existing `qm-pipeline-demonstration-v1` opt-in policy (section 12 of `IMPLEMENTATION-INCREMENTAL-E2E.md`) and existing AFO/Fabro, inspection, checkpoint, packaging, knowledge, and verification services. Do not duplicate their state or install a parallel scheduler.
4. The first target is **not** the entire RCC LL/HAL scope. Use a **new, explicitly scoped** CRC LL work order covering `LL_CRC_Write_IDR` and `LL_CRC_Read_IDR`, their declared dependencies, and independent tests. The existing nine reviewed functional requirements and source-backed fixture are the starting point. **Do not narrow the existing failed RCC job, overwrite it, or attribute its obligations to this CRC deliverable.**
5. **Qwen must author actual candidate C code** for the functional-delivery milestone. A workflow that injects frozen ST implementation code or uses substituted fixture responses is only a plumbing demonstration. It cannot satisfy the Qwen-authorship milestone.
6. Work exclusively in a clean, isolated checkout/worktree; inspect current branch, live service, existing work orders, lease and provider ownership. Do not stop/restart an active GPU job or change installed source without deliberate, authorized handoff and reconciled quiescence.
7. Make the smallest change that produces the next piece of end-to-end evidence. Do **not** add EGM, another agent swarm, another knowledge store, another workflow engine, or another framework-wide abstraction.

## 1. Evidence-based motivation

The report's read-only cutoff (2026-10-30 ~18:33 UTC) found:

- Feature 014 at **30/58 checked tasks**, not 58/58; 185 source-history entries in three calendar work days do not demonstrate product yield.
- Qwen RCC LL was **RUNNING**, with **62 valid author packets**, **637 assembled requirements**, and four valid `PASS` criterion-level inspection packets; no complete phase/product verdict yet.
- Cloud Codex/Claude control r4 passed SWE.1 and SWE.2, then finished **BLOCKED at SWE.3 with 30 package gaps**. Root cause required artifact/gate-level triage; routing output alone did not establish it.
- A real Qwen-authored maintenance candidate passed seven CRE hard gates **after disclosed external runner/administrative fixes**. A separate scoped AFO product repair ran without intervention. Neither establishes complete unattended factory healing.
- Qwen3.8-27B Q8/f16/MTP3 with 262,144 context used roughly **46.6 GiB** of GPU memory in one observed RTX 6000 Ada 48-GB allocation. The measured small-task MTP study improved decode 28.61 → 83.00 tokens/s, but did **not** qualify full-pipeline throughput.
- The **native Qwen QM six-phase graph** had been prepared at `c221b65e` but **NOT_STARTED** at the report cutoff.
- The existing demonstration mode can visit downstream phases with findings, but it does **not** yet prove an autonomously delivered, functionally verified Qwen-authored driver.

**Architectural diagnosis:** Product generation, gate acceptance, administrative admission, and release qualification are overly coupled for the first useful delivery milestone. Local-model ability is unproven for the complete product, but many observed failures occurred before inference or inside framework/tool contracts. Model replacement, a larger context, and more inspectors are not the first remedies.

### Evidence hygiene

Treat reports and the source refs above as **dated**; capture live head, configured runtime, model digest, profile hashes, work-order source, native execution, GPU lease, and package status **before** any new trial. Do not present prior frozen-code benchmarks as Qwen-generated driver results, and do not treat a successful test-fixture simulation as a real model execution.

## 2. Goals, non-goals, and operating principles

### Goals (in priority order)

**G1 — Real first delivery:** One local Qwen-authored C increment exists, compiles against the declared environment, passes independently specified applicable behavioral tests, and reaches terminal packaging **without human intervention after authorized launch**.

**G2 — Honest complete process traversal:** All six applicable SWE.1–SWE.6 stages are attempted, with substantive artifacts where produced, a phase outcome for each, explicit `NOT_RUN`/`BLOCKED` where appropriate, evidence links, and an immutable gap register. A completed *journey* is distinct from accepted engineering work products.

**G3 — Incremental repeatability:** Reproduce G1 in **three fresh, clean-state runs** with comparable work-order criteria, then expand to a larger CRC scope and a provisional LL→HAL chain.

**G4 — Minimal integration:** Reuse Feature 014/AFO/Fabro and the current deterministic toolchain; keep the existing strict quality/release path unchanged by default.

**G5 — Learn later from actual delivery:** Capture outcome and corrections using the existing experience/knowledge mechanisms. Do not require autonomous learning, automatic lesson promotion, a 30-driver benchmark, or 24/72/168-hour reliability campaigns to complete G1.

### Explicit non-goals for the initial milestone

- No ISO 26262 / ASIL claim, ASPICE compliance claim, production release, hardware WCET claim, or generic MCU/toolchain qualification.
- No full RCC owner scope, full STM32N6 driver portfolio, arbitrary embedded-C generality proof, automatic safety argument, or multi-GPU concurrency.
- No new EGM runtime, Elephant/Goldfish agents, heavy specification-review pipeline, new service/scheduler, or separate database.
- No automatic modification or deployment of protected factory control-plane code by Qwen.
- No hidden cloud inference or fallback; the first accepted functional run must be genuinely **local**.

### Invariants that remain non-negotiable

- Operator stop/revocation, approved model/provider identity, sandbox/tool permissions, integrity of authoritative manuals/inputs, and single-GPU ownership remain binding.
- No fabrication of artifacts, tests, traces, tool results, requirements, source-backed hardware semantics, or PASS verdicts.
- A failed executable functional check cannot be reported as functional success.
- An unresolved essential input or contradictory hardware contract blocks claims of correctness; unrelated stages may still run diagnostically with explicit provisional dependencies.
- Existing strict acceptance and `READY_FOR_OFFLINE_REVIEW` semantics remain authoritative. Demonstration outputs are never automatically released or promoted.
- Existing mission expenditures, failures, source hashes, and audit history cannot be silently reset, rewritten, or relabeled.

## 3. Architectural decision: two loops, one factory

**Fast loop — deliver:** Declared functional scope → minimal source-backed contract → Qwen generates implementation → compiler/tests/simulation → at most two bounded implementation corrections → completed artifact/evidence package.

**Slow loop — improve and qualify:** Independent semantic inspection → gap register → traceability/design/test improvements → strict independent qualification → qualified reusable lessons. This loop should run only when it contributes to the declared work-order goal or a separate authorized qualification.

Keep the same AFO job, evidence store, manifest, and native execution underneath both loops. Do not require the slow loop to PASS before producing or packaging the fast-loop candidate. Do not confuse this with permitting release without gates.

### Outcome dimensions, not misleading new terminal states

Record separate dimensions **in the package/report** (mapping to existing data contracts; do not introduce a new competing order lifecycle):

| Dimension | Values (recommended report schema) | Meaning |
|---|---|---|
| `execution` | `COMPLETED`, `PARTIAL`, `FAILED`, `CANCELLED` | Which permitted execution steps actually ran |
| `artifact_delivery` | `COMPLETE`, `PARTIAL`, `NONE` | Declared deliverables physically present and hash-bound |
| `functional_verification` | `PASS`, `FAIL`, `NOT_RUN`, `INCONCLUSIVE` | Compiler and independent executable results for full declared scope |
| `process_qualification` | `PASS`, `GAPS`, `NOT_RUN` | Required semantic and traceability/review verdicts |
| `release_eligibility` | `BLOCKED`, `READY_FOR_OFFLINE_REVIEW` | Existing strict release decision only |
| `mode` | `QM_DELIVERY_FIRST_DEMO` | Explicit development intent, always visible |

The three milestone labels **`DELIVERED_WITH_GAPS`**, **`FUNCTIONALLY_VERIFIED`**, and **`READY_FOR_OFFLINE_REVIEW`** are report-level claims, **not** new database order states; adopt only if the repository already has compatible status extensions. `FUNCTIONALLY_VERIFIED` requires complete declared scope and independently reproducible tool checks, not just successful compilation. If an existing release gate remains blocked, `release_eligibility=BLOCKED` even when functional verification is `PASS`.

### Minimal execution sketch

```text
Existing AFO work order + reviewed target manifest
   |
   +-- preflight authoritative input, target, toolchain and permissions
   |
   +-- Qwen authors the minimal code + requirement/design drafts for the small scope
   |
   +-- deterministic compile + independent tests
   |       |-- failure? provide concise diagnostics and retry (max 2 corrections)
   |       `-- record actual PASS/FAIL/NOT_RUN
   |
   +-- SWE.1..SWE.6 artifacts/inspections (advisory for process findings)
   |       `-- never invent an artifact or PASS for a skipped/broken step
   |
   +-- existing package finalizer; evidence + findings + independent results
   |
   `-- terminal report: delivery / function / process / release axes
```

Preserve six-phase provenance even if implementation and executable verification are performed earlier in the *experimental engineering sequence*: recorded phases must describe the **actual** order of work and whether their expected evidence was backfilled, generated, provisional or independently accepted. Never recast retrospective requirements as if approved before the code was written.

## 4. Detailed functional requirements

### DF-FR-001 — One versioned, opt-in development profile

Add a profile/configuration selection (proposed name `qm-delivery-first-v1`) that **extends** the existing `qm-pipeline-demonstration-v1` policy. Only explicitly selected, appropriately authorized **new** QM development work orders use it. Existing strict/QM/brownfield/ST benchmark work orders are unchanged; configuration is frozen in the work order and package. Do not add a global environment toggle that silently changes active jobs.

### DF-FR-002 — Tiny honest work-order scope

Provide a separately identified CRC IDR work order derived from `examples/0014c-st-cube-crc/workorder.json` and the nine existing reviewed requirements. Initial functions: `LL_CRC_Write_IDR`, `LL_CRC_Read_IDR`, plus proven dependencies only. Include primary-source references, API signatures, effect semantics, target/compiler/simulator configuration, independent test oracle, coverage manifest, and excluded operations. Record actual target restrictions; do not invent a register behavior or target performance allocation. The full RCC/full-CRC jobs remain intact.

### DF-FR-003 — Genuine Qwen C authorship

The accepted functional milestone requires Qwen to create/modify source candidate(s) in an isolated work area. Store authorship provenance: model digest, profile, role, request/response identifiers or accepted artifact hashes, generated-file hashes, and revision. Existing frozen ST code may be used as a **declared reference/comparison fixture** where licensing permits, but cannot be silently substituted for the Qwen-authored deliverable. A frozen-code-only first-stage run is explicitly `PLUMBING_ONLY`.

### DF-FR-004 — Minimal source-backed engineering context

Assemble each author request from the current validated work-order contract plus the **relevant** manual/header/driver sections. Prefer small coherent function groups and bounded retrieval over dumping the complete manual or all 637 RCC requirements. Measure the full serialized request with real model-template overhead and output reserve. Begin with **64K context as a hypothesis**, not an unconditional promise; if measured context cannot fit, partition or record a transparent scope/context block. Do not truncate mandatory evidence or pretend 262K is inherently more accurate.

### DF-FR-005 — Practical authoring/inspection split

Use Qwen at medium reasoning for implementation and bounded repair initially. Make semantic inspections **non-blocking for workflow traversal** in this profile, but retain their exact findings/status. The deterministic compiler, static checks where applicable, independent test oracle and actual simulation are the functional success authority. Same-model inspection is useful evidence, not independent proof. Avoid an xhigh inspector on every step unless a measured improvement justifies it.

### DF-FR-006 — Bounded test-driven correction

Run real compilation and independent unit/behavioral tests on the candidate. On failure, pass actual diagnostic excerpts and relevant source context to the author and allow **at most two substantive implementation correction passes** for the current slice. No hidden nested retries. Preserve every failed candidate and its outcome/usage. If tests remain failing, still finalize a truthful `PARTIAL`/`FAIL` package, but never report functional success.

### DF-FR-007 — Advisory process gates; hard integrity gates

Within the opt-in profile only, a missing/non-PASS *semantic quality review* may be recorded as an advisory gap and allow downstream phase attempts. Source integrity, invalid protocol, missing essential hardware facts, untrusted/tampered inputs, unsafe tool authority, inability to freeze/provenance an artifact, and failed executable verification are **not** turned into PASS. A hard fault may prevent the dependent task; the coordinator must attempt genuinely independent remaining work and package an honest terminal result. Do not manufacture a pass through a parser shortcut.

### DF-FR-008 — Genuine SWE.1–SWE.6 journey

Attempt all six stages under the existing workflow integration, whether through the current native QM graph or a small compatible evolution of it. Every stage must produce a recorded attempted/produced/blocked/missing result. If an upstream source/contract defect affects downstream validity, mark downstream work provisional or blocked and preserve the dependency in the final evidence. No count of six graph nodes visited is itself evidence of functional delivery or qualification.

### DF-FR-009 — Provisional LL→HAL dependency (later increment)

For a **separate new HAL experiment**, allow a pinned LL package that is fully source/integrity-verified, actually compiled, and passed the declared independent LL functional tests to become a **provisional development dependency**, without asserting `READY_FOR_OFFLINE_REVIEW`. Record its manifest/hash and known gaps. This is a versioned dependency type selected only by the Delivery-First development policy; it must **not** silently weaken the strict AFO scheduler condition `ORDER_DEPENDENCY_NOT_READY` for normal work orders. HAL release remains blocked until its normal LL/HAL release prerequisites are independently satisfied.

### DF-FR-010 — Truthful packaging and status

Reuse existing finalizer/package integrity mechanisms. Export candidate sources/headers, source and model/config revisions, work-order scope, requirements/design/test evidence, actual tool logs and exit codes, phase coverage table, gap list, complete functional verdict, unexecuted checks, human interventions and final release block. A `DEMONSTRATION_ONLY` package can be a successful **delivery demonstration** without being a qualified/released software package.

### DF-FR-011 — Durability, identity, and no parallel scheduler

Reuse existing checkpoints and AFO native job/lease/reconciliation. Compatible candidate artifacts may be reused only after hash+current-contract+tool validation, retaining original provenance; do not reuse an inspector PASS across incompatible baselines. Preserve one admitted GPU inference, finite resource ceilings and operator stop behavior. A terminal failure is recorded; independent queued work can proceed. No unlimited retry or fake 24/7 availability claim.

### DF-FR-012 — Shared-engine / target-adapter boundary

Do not hardcode RCC, Cortex-M55, RM0486, ST LL/HAL, or a special CRC rule into shared scheduling, policy, gate, packaging, or measurement code. Put device facts and compiler/simulator API in the declared target/project adapter/work-order inputs. The first CRC experiment establishes **one supported fixture**, not generic embedded-C qualification.

### DF-FR-013 — Evidence-first metrics

Record: `attempted_products`, `functionally_verified_products`, `end_to_end_yield`, wall-clock to first functional result, total model requests/tokens (unknown labeled `UNKNOWN`), Qwen authoring tokens, correction count, real compiler/test pass/fail counts, phase artifacts generated, non-trivial scope coverage, human interventions, archived gaps, and strict release status. Compare cohorts on identical declared scope and oracles. Do not sum overlapping test cohorts or call reused packets "learning."

### DF-FR-014 — Low-friction operation without bypassing authority

For the new development lane, minimize redundant role approvals, signed role handshakes, heavyweight inspection loops, and administrative re-proofs **within existing authorized scope**. Keep operator authority, model allowlist, source integrity, inference lease, bounded finite job budgets and reliable usage records. A legitimately new experiment may use its own authorized work-order allocation; do not disguise an expired mission as renewed or erase old charges. Distinguish per-request context limits from cumulative mission allowances.

### DF-FR-015 — Recovery/learning deferred, evidence retained

General autonomous factory-source maintenance, self-learning, and long reliability campaigns are **non-blocking dependencies** for the functional milestone. Keep factual experience capture and known working recovery paths, but do not make a CAPA/CRE lesson qualification or model self-repair demonstration mandatory before packaging the first Qwen driver. Do not claim fresh model-weight learning.

### DF-FR-016 — Strict path regression and rollback

Version and pin the new mode. With the new profile disabled, existing strict and current demonstration work orders must reproduce their prior behavior. Exercise rollback to the previous configuration without rewriting historical packages. Fail closed on a wrong model digest, corrupt source, invalid target/toolchain, or unowned GPU lease.

## 5. Configuration illustration (NOT a claim of current schema)

Do not add these keys literally until mapping them onto the **existing** Forge-C YAML/JSON schema and versioned configuration hooks. The intent is a single profile selection, not a new policy engine.

```yaml
# Illustrative desired behavior — map to existing profile/policy keys.
id: qm-delivery-first-v1
purpose: QM
extends: qm-pipeline-demonstration-v1
provider: local-qwen-existing-profile
model_role: author-medium
max_concurrent_inference: 1
execution:
  declared_scope_only: true
  attempt_all_swe_phases: true
  semantic_reviews: advisory
  executable_checks: authoritative
  max_implementation_corrections: 2
  allow_provisional_downstream_artifacts: true
  release_policy: unchanged_strict
context:
  starting_window_tokens: 65536
  require_serialized_measurement: true
  overflow: repartition_or_block
reporting:
  preserve_findings: true
  separate_delivery_function_process_release: true
  never_infer_pass: true
```

MTP3 is a reasonable initial runtime choice based on a *small* measured study; benchmark it against a same-workload non-MTP control before declaring pipeline speed improvements. The installed model's accepted context and actual free GPU memory take precedence over the sample value above.

## 6. Implementation plan: smallest vertical slice first

### Phase 0 — One-day-equivalent inventory, not a new research program

**Purpose:** Determine the current implementation state, identify minimal edits, and avoid re-solving already fixed bugs. This is an ordering label, **not** a guaranteed elapsed-time estimate.

- Check current Git refs, PR #41/#42 stack, installed Omniverse runtime/model/profile/digest and live GPU lease; do not assume report cutoffs remain current.
- Audit the final cloud r4 SWE.3 failure using retained **artifact and gate logs**, not its empty routing `defects` array. Classify: source/input, contract/tool, author result, inspector, or resource/admission.
- Map current `qm-pipeline-demonstration-v1` selection, Fabro six-phase graph, native-Qwen profile, gate routing, author-work freeze, verifier, AFO scheduler dependencies, and final packaging. Produce a one-page *implementation map* with real code paths.
- Confirm existing CRC IDR work-order fixture and independent oracle. Identify whether prior fixture uses frozen source or Qwen-authored source.
- If a relevant functionality already exists, **test/reuse it rather than reimplementing it**.

**Exit:** exact minimal edit list; one executable golden fixture with trustworthy test criteria; no production source change required by discovery alone.

### Phase 1 — Reuse the already prepared six-phase native QM path

- In an isolated development checkout, fix only the verified launcher/auth/config defects that prevent the existing native Qwen QM graph from launching. Preserve the current source/role/lease ownership rules.
- Run one dry integration with **substituted provider responses**, through real preparation, phase transition, evidence handling and finalizer. Explicitly label `FIXTURE_ONLY`.
- Run one authorized **real Qwen** trial of the *small CRC IDR scope* through all stages. The immediate Phase 1 acceptance is **execution traversal** with truthful missing/failed evidence; this may still be `DEMONSTRATION_ONLY` / functional `FAIL`.
- If that native graph is still bound to RCC only, make the smallest **generalized work-order/target-selector** adjustment; do not fake RCC source coverage for CRC.

**Exit:** proven terminal packaging path with Qwen inference, or an exact failure report naming the one stage/tool that prevented it. Never announce E2E functional success based on phase traversal alone.

### Phase 2 — Genuine Qwen-authored function delivery (first principal milestone)

- Extend the same opt-in policy with authoring of actual `LL_CRC_Write_IDR` and `LL_CRC_Read_IDR` candidate source, not vendor-code injection. Requirements/design drafts may be preliminary; mark original reviewed inputs vs newly model-derived outputs accurately.
- Use **small coherent prompts** with source-backed constraints, no unnecessary whole-manual dump, serialized context sizing, a persistent artifact checkpoint, and medium reasoning.
- Run declared compilation and independent behavioral oracle. Feed compiler/test diagnostics into a maximum of **two** bounded implementation corrections.
- Then emit or complete the substantive SWE.1–SWE.6 artifacts and inspect them in advisory mode. Flag any retrospective documentation and source-backed semantic disagreements.
- Use the existing package finalizer. Produce a machine-readable manifest and a short human-readable scorecard with separate delivery/functional/process/release outcomes.
- Implement focused regressions for strict profile unchanged, false PASS prevention, and unsupported/missing manual sections.

**Exit / MILESTONE DF-M1:** one terminal real local Qwen-authoring run with compiled C, independent behavior `PASS` for the entire declared two-function scope, no post-launch human intervention, a truthful packaged six-stage record and `release_eligibility=BLOCKED` unless existing strict release qualification **actually** passed. If this cannot be achieved, deliver the exact unsuccessful package and a ranked defect list, without calling the milestone complete.

### Phase 3 — Repeatability without scope cheating

- Execute **three new, clean-state** Qwen-authoring runs against the same preregistered declared contract/oracle and comparable machine/profile configurations. Do not count resuming one historical attempt as a fresh run.
- Publish complete wall-clock, requests/tokens, corrections, tool outcomes and failure taxonomy for each trial; treat missing telemetry as unknown.
- Compare medium vs xhigh or 64K vs larger context **only as a separately controlled experiment**, one variable at a time, after the baseline works. No automatic profile change on anecdotal improvement.

**Exit / DF-M2:** 3/3 independent functional deliveries of the declared scope; no claim about generic targets or 24/7 reliability.

### Phase 4 — LL→HAL and generality, not before the first green slice

- Expand CRC LL operations by coherent unit and test; then run one new HAL experiment against a provisionally functionally verified pinned LL, retaining blocked strict release.
- Add one **different existing peripheral** under a distinct target/project manifest; run independent tests. Check for leaked RCC assumptions and hardcoded manual selection.
- Measure whether qualified knowledge retrieval improves a *later* run against a controlled comparator, without claiming model-weight adaptation.

**Exit / DF-M3:** observed LL→HAL development dependency and at least one different peripheral; explicitly name target/simulator scope and any unsupported configurations.

### Phase 5 — Return stronger controls by measured value

Only after a functional baseline: restore stricter independent inspections, traceability, ASPICE review, recovery qualification, model-role holdouts and long-running operational campaigns incrementally. Document the impact of each restored gate on error detection, first-pass yield and delivery latency. A control remains strict in the existing release profile regardless of whether it is advisory in Delivery-First.

## 7. Acceptance tests (specification and contract)

| Test ID | Scenario / oracle | Expected result |
|---|---|---|
| DF-AT-001 | New profile absent on ordinary strict work order | Existing gate routing, release and admission unchanged |
| DF-AT-002 | Opt-in profile with inspector FAIL and valid downstream material | SWE stages may be attempted; failed finding remains in gap register; release still BLOCKED |
| DF-AT-003 | Missing mandatory source-backed register semantics | Required dependent work blocks; no fabricated assumptions or functional PASS |
| DF-AT-004 | Real Qwen two-function IDR work order | Generated-file provenance proves model authorship; no frozen-ST implementation substituted |
| DF-AT-005 | Invalid C candidate, compiler diagnostic | Repair request sees genuine diagnostic; max two corrections; original failed evidence retained |
| DF-AT-006 | Code compiles but independent behavioral oracle fails | `functional_verification=FAIL`, irrespective of inspection or phase traversal |
| DF-AT-007 | Correct code passes declared independent tests | `functional_verification=PASS` only with full scope coverage and reproducible tool evidence |
| DF-AT-008 | Six phase nodes visited but artifacts/verification absent | `execution=COMPLETED/PARTIAL`, artifacts/functional status NOT falsely elevated |
| DF-AT-009 | Tampered source hash, stale cached artifact, invalid receipt | No artifact reuse, forged PASS, unverified dependency or release |
| DF-AT-010 | Two development jobs contend for one 48-GB GPU | One admitted inference; second deferred; terminal/restart reconciles lease correctly |
| DF-AT-011 | Stop/revocation during author or correction | No new inference after reconciled stop; preserve artifacts, ledger and truthful terminal state |
| DF-AT-012 | HAL depends on functionally verified but unqualified LL | Provisional **experimental** dependency admitted only in explicit profile; strict HAL remains blocked |
| DF-AT-013 | Work order selects a different manual and target | Correct declared source selected; fail on unsupported target rather than assuming RCC/RM0486 |
| DF-AT-014 | Three fresh clean-state runs | Three independently verified products, full attempts counted, comparable metrics |
| DF-AT-015 | Revert profile/change | Strict and prior QM demonstration behavior unchanged; old artifacts/receipts immutable |
| DF-AT-016 | Static fixture answers or frozen vendor implementation | `PLUMBING_ONLY`, never counted as local Qwen-generated functional milestone |
| DF-AT-017 | Optional source-backed doc requirement missing | Explicit document/gap or proportional blocked status; not an invented source assertion |

**Test tiers:**

1. **Offline deterministic unit/integration** — real schemas, existing gate/finalizer, compiler-test harness and negative controls; provider responses can be fixtures **only** when labeled as such.
2. **Real local inference** — actual Qwen calls, produced C, actual tool results, one source-pinned terminal package; cannot be replaced by unit-test counts.
3. **Fresh-run evidence** — actual clean-state repeated runs, no imported prior model outputs or manufactured success.
4. **Optional target simulation/HIL** — only where the declared target adapter, instrumented tests and validated environment exist. Mark `NOT_RUN` rather than claiming real hardware verification.

## 8. KPI scoreboard and success/failure taxonomy

The primary KPI is **functional E2E yield**:

```text
Functional E2E yield =
  count(new work orders delivering full declared scope with independent functional PASS)
  / count(new attempted work orders in the preregistered cohort)
```

Also report median/p95 time to accepted functional package, cost/request, token totals (or `UNKNOWN`), model-call count, implementation corrections, independent tests executed/passed, scope obligations covered, manual interventions, non-blocking quality gaps, and release eligibility. Store each attempt and its original status so the denominator cannot exclude failures.

**Failure categories:**

- `INPUT_SCOPE`: essential missing/conflicting source, invalid target contract, out-of-scope function.
- `AUTHOR_MODEL`: content/implementation/contract quality failure after an admitted real model call.
- `TOOL_INTEGRATION`: MCP/Fabro/tool path/schema/compilation adapter/diagram tool failure.
- `INFRA_ADMISSION`: model unavailable, GPU lease, authorization, context limit, watchdog, storage/mount/SQLite contention.
- `VERIFICATION`: compile, unit test, behavioral oracle, simulator or target evidence failure.
- `PROCESS_QUALITY`: inspection/traceability gap that may remain advisory during the experiment.
- `OPERATOR`: explicit stop/supersession; not mislabeled model failure.

Classify with source/evidence and leave root cause `UNKNOWN` when the logs cannot support a causal diagnosis. Do not treat a `native=SUCCEEDED` transport as a successful product or a `package=BLOCKED` as evidence that no useful code was generated.

## 9. Target implementation surfaces (verify paths at current HEAD)

| Existing subsystem / observed file | Minimal intended change |
|---|---|
| `specs/014-durable-local-autonomy/IMPLEMENTATION-INCREMENTAL-E2E.md` | Cross-reference this decision and distinguish earlier frozen-code vs new Qwen-code milestones |
| Feature 014 `spec.md`, `plan.md`, `tasks.md`, `acceptance-tests.md` | Add a bounded Delivery-First amendment and DF test traceability without rewriting 58-task ledger |
| `factory/python/forge_factory/inspection/gate.py` | Reuse advisory routing; ensure quality gaps cannot masquerade as functional/pass/release verdicts |
| Existing Fabro graph/profile/workflow builder (discover actual paths) | Select new opt-in profile, try all six phases, add real function-first compiler/test feedback using existing nodes |
| `factory/python/forge_factory/afo/conductor.py` | Reuse existing reconciliation and execution; **do not add a second scheduler** |
| `factory/python/forge_factory/afo/scheduler.py` | Later: explicit provisional LL→HAL dependency **only** under development policy; strict dependency stays as-is |
| Existing AFO package/validation/manifest modules (discover actual paths) | Report independent execution/delivery/functional/process/release axes; retain native release status |
| Existing target input / examples folder | New separate CRC IDR work-order fixture and source-backed oracle |
| Existing `knowledge/experience.py`, `knowledge/store.py` | Reuse factual outcome capture only; no new lesson pipeline necessary for DF-M1 |

The paths `inspection/gate.py`, `afo/conductor.py`, and `afo/scheduler.py` were verified on the Feature 014 branch during preparation. **Other paths must be discovered in the current checkout rather than guessed.** In particular, identify where the current QM demonstration graph routes nodes and where final release verdicts are computed before editing them.

## 10. Minimal task backlog with dependencies

| Task | Scope | Dependency | Acceptance |
|---|---|---|---|
| DF-T001 | Current checkout/runtime/lease inventory and r4 SWE.3 artifact triage | None | Evidence-backed minimal path map |
| DF-T002 | Confirm two-function CRC input + independent negative/positive oracle | DF-T001 | Correct scope, source hashes, honest exclusions |
| DF-T003 | Reuse native six-phase Qwen QM graph in a clean fixture | DF-T001 | `FIXTURE_ONLY` terminal evidence; no false claims |
| DF-T004 | Add opt-in Delivery-First policy via existing profile resolution | DF-T001 | Strict profile regression and mode pin |
| DF-T005 | Qwen-authored C candidate, small scope/serialized context | DF-T002, DF-T004 | Real model artifact and traceable hashes |
| DF-T006 | Compile + independent tests + at most two corrections | DF-T005 | Genuine independent functional PASS/FAIL |
| DF-T007 | Process advisory findings + six-stage truthful record | DF-T003, DF-T006 | All phases attempted; missing evidence not PASS |
| DF-T008 | Multi-axis package/report and no-release assertions | DF-T007 | Reproducible terminal package; strict release intact |
| DF-T009 | Real local Qwen DF-M1 execution + negative controls | DF-T008 | One full declared-scope functional PASS or truthful failure record |
| DF-T010 | Three fresh trials, metrics and cohort comparison | DF-T009 PASS | Repeatability evidence, no hidden reused model output |
| DF-T011 | Provisional LL→HAL and another peripheral | DF-T010 | Development-only dependencies, independent functional checks |
| DF-T012 | Restore/qualify stronger controls by measured value | DF-T010 | Controlled comparison, original strict paths unaffected |

**Scope discipline:** Do not implement DF-T011/012 while DF-T009 remains unproven. A failing DF-T009 triggers diagnosis of the **specific failing step**, not broad architecture rework. Require at least one explicit before/after failing test for each framework defect fixed.

## 11. Definition of Done and reporting

### DF-M1 is DONE only if all conditions hold

- [ ] A new, authorized, source-pinned work order declares exactly the intended CRC IDR function scope, dependencies and independent oracle.
- [ ] Genuine local Qwen inference produced the implementation files; source provenance rules out frozen/vendor code substitution as the delivered candidate.
- [ ] The generated C compiles with the declared toolchain and passes all preregistered applicable independent behavioral checks for the **entire** declared scope.
- [ ] Actual SWE.1–SWE.6 execution attempts and their outcomes are recorded; substantive available artifacts are packaged, and missing/failed ones are explicitly identified.
- [ ] No operator/assistant code or manual intervention was needed **between authorized launch and terminal package**. Pre-run environment setup and external engineering fixes must be disclosed and are not called autonomous healing.
- [ ] The terminal package is integrity-checked, source/model/config pinned, and contains complete gap/verifier evidence.
- [ ] A separate process/release verdict is preserved; unless the strict qualification actually passed, release remains **BLOCKED** / **DEMONSTRATION_ONLY**.
- [ ] Independent negative controls establish that compilation failure, behavioral mismatch, absent evidence and tampered provenance are **not** accepted as functional PASS.
- [ ] The report provides exact run IDs, relevant SHAs, executed commands, timestamps, and measured requests/time; unknown data is labeled unknown.

### Standard completion report (one page, generated from evidence)

```text
Forge-C Delivery-First Experiment — [work-order ID]
Git/source revision: ... | model/profile/digest: ... | declared scope: ...
Execution: ... | Artifact delivery: ... | Functional verification: ...
Process qualification: ... | Release eligibility: ...
Produced: C source/header ...; SWE.1..SWE.6 evidence ...
Compiler: ... | Independent unit tests: ... | Simulation: ...
Attempts/model calls/tokens/time: ... | Operator interventions: ...
Gaps (critical vs advisory): ... | Root causes supported by: ...
Conclusion: FUNCTIONAL_MILESTONE_PASS / FAILED / INCONCLUSIVE
Claims NOT established: production release, ASPICE compliance, safety, generic targets, 24/7, model learning
```

## 12. Stop rules and escalation

Stop **the affected task/job**, not the entire factory, when a real essential source is absent, the output cannot be compiled after the bounded correction attempts, independent tests fail, an active GPU lease is unresolved, the operator has stopped/revoked authority, or persistent infrastructure integrity fails. Persist the reason and package what exists when safe. Other independent authorized work may continue through the existing scheduler.

If a diagnostic control (Codex/Claude) fails the same source/contract boundary as Qwen, prioritize a shared-engine fix. If Codex/Claude succeeds but Qwen fails on identical oracle/work scope, isolate role and model protocol competence with a controlled test; do not infer results from non-equivalent prompt/task decomposition.

Do not spend another full development cycle on multi-agent review, extensive new specifications, GPU upgrades, or 24/7 qualification unless the current failing evidence specifically justifies it. A single fresh-context architecture critique may be requested **once**, as an optional review of scope and integrity, not a release or implementation gate.

## 13. Codex execution directive (paste into a new Codex task)

> You are implementing **Forge-C Feature 014 Delivery-First**. Read the repository's current instructions, constitution, Feature 014 documentation, the 28–30 October review and `specs/014-durable-local-autonomy/DELIVERY-FIRST-E2E.md` before editing. Work on the existing Feature 014 integration line in a clean isolated worktree; respect current remote/branch/runtime state and do not affect any active native Qwen job without an authorized, quiescent handoff. Reuse the current `qm-pipeline-demonstration-v1` execution path, AFO/Fabro scheduler, source-validated checkpoints, inspection gates, deterministic verification and packaging. Do not build a parallel workflow framework or introduce EGM. Your first milestone is **one genuinely Qwen-authored two-function STM32N6 CRC IDR C deliverable**, compiled, independently behavior-tested and packaged after attempting SWE.1–SWE.6. Change semantic quality gates to advisory **only** in the explicitly selected development policy; retain all hard integrity, operator, input, runtime-resource and release restrictions. Run no more than two implementation correction passes. Distinguish fixture-only, frozen-ST-code, partial traversal, and real local Qwen functional success. Do not report `READY_FOR_OFFLINE_REVIEW` unless the existing strict criteria independently pass. Implement DF-T001 through DF-T009 in dependency order; do not start LL→HAL, general learning, long campaigns, or unrelated architecture expansion until DF-M1 has real recorded evidence. For every change, provide exact modified files, focused regression commands/results, actual run IDs/source/model hashes, phase/functional/release outcome, critical gaps, and the next smallest blocking defect. Preserve historical receipts and old work orders unchanged. If the live environment cannot be safely/legitimately accessed, complete deterministic work in isolation, report REAL_RUN_NOT_EXECUTED, and do not manufacture progress.

---

## References / source anchors

- [Three-day review, 28–30 Oct 2026](https://github.com/jnsagai/forge-c/blob/main/specs/014-durable-local-autonomy/ASTRA-REVIEW-20261028-30.md)
- [Existing incremental E2E handoff and QM demonstration policy](https://github.com/jnsagai/forge-c/blob/feat/014-durable-local-autonomy/specs/014-durable-local-autonomy/IMPLEMENTATION-INCREMENTAL-E2E.md)
- [Feature 014 specification](https://github.com/jnsagai/forge-c/blob/feat/014-durable-local-autonomy/specs/014-durable-local-autonomy/spec.md)
- [Generic embedded-C applicability boundary](https://github.com/jnsagai/forge-c/blob/feat/014-durable-local-autonomy/specs/014-durable-local-autonomy/GENERIC-EMBEDDED-C.md)
- [Recorded Codex/Claude r4 snapshot](https://github.com/jnsagai/forge-c/blob/feat/014-durable-local-autonomy/evidence/014-durable-local-autonomy/three-day-review-20261030/codex-claude-r4-terminal-snapshot.json)
- [Recorded Qwen snapshot](https://github.com/jnsagai/forge-c/blob/feat/014-durable-local-autonomy/evidence/014-durable-local-autonomy/three-day-review-20261030/qwen-live-snapshot.json)

**Publication note:** This is a versioned development specification. Its publication
and implementation are distinct from deployed source and measured qualification;
the implementation ledger records those statuses separately.
