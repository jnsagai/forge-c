# Codex handoff: incremental local end-to-end delivery

**Owner decision:** 2026-10-28, following the Astra review and agreement to deliver small, reliable end-to-end increments.  
**Repository:** `jnsagai/forge-c`  
**Working line:** `feat/014-durable-local-autonomy`  
**Status:** implementation brief; the milestones below are NOT_RUN. This document does not claim deployment, product acceptance or runtime qualification.

## 1. Immediate objective

Produce one reproducible, local, input-assisted SWE.1–SWE.6 package for a deliberately small STM32N6 CRC LL work order:

- `LL_CRC_Write_IDR`
- `LL_CRC_Read_IDR`
- Only the setup, constraints, dependencies and verification needed for those functions.

Use the existing frozen ST delivery and reference-manual inputs. Supply a small, explicitly reviewed requirements set for the first integration run. Qwen performs the remaining applicable engineering work and inspections; all verdicts come from actual checks. Then remove the requirements-authoring assistance in the next increment.

The immediate engineering priority is a working delivery path. Autonomous product recovery, demonstrated learning benefit, broad driver coverage, MTP promotion and long-duration qualification are later milestones, not prerequisites for this first delivery. Existing model-free supervision and factual experience capture remain active.

Do not report a compiled snippet, a mocked pipeline, healthy services or a BLOCKED package containing mostly unexecuted phases as the successful end-to-end milestone.

## 2. Read first and reconcile the current checkout

Read applicable repository instructions and `.specify/memory/constitution.md`, then:

1. This handoff.
2. Feature 014 `spec.md`, `plan.md`, `tasks.md`, `acceptance-tests.md`, `local-model-design.md`, and the latest `HANDOVER-CODEX.md`.
3. The existing Feature 008 brownfield, Feature 012 resume and Feature 015 ST benchmark boundaries.
4. The source paths identified below and the three evidence packages linked here.

Historical references, not assertions about the current running machine:

| Reference | Established evidence |
|---|---|
| [Original terminal/MTP audit](../../evidence/014-durable-local-autonomy/mtp-and-terminal-audit-20261028/README.md), evidence commit `81a2c26329fa392658cd4289665a264ca8e5d576` | Seven locally valid author packets; SWE1-02/03 failed; no downstream product completion; diagnosis made zero calls; advisory resume failed before inference. |
| [Resume correction](../../evidence/014-durable-local-autonomy/aspice-resume-98d066d/README.md), evidence commit `d0a25f33c8e65ff48a1d9cdd459d0a02a733a009` | Candidate `98d066dfe519c5ea2b23cec7d8f9681aff1f71d0` includes coherent-obligation, author-input and versioned resume corrections. Recorded 71 local and 124 native fixture passes, zero Qwen calls; candidate was not deployed. |
| [Continuation readiness](../../evidence/014-durable-local-autonomy/continuation-readiness-20261028/README.md), evidence commit `9d3cbd64374f66766cb22f6f921402d1fa762911` | The actual diagnosis request was refused at admission: conservative input bound 69,182 plus effective output cap 34,816 = 103,998 against reservation 65,536. This was not a model diagnosis failure or a native tokenizer measurement. |

The last cited production snapshot used `fcb15cba0bbc1b5e6e7c91c86aba08db244b5c61`. Re-establish current source, profile and service state before live work. The engineering baseline is candidate `98d066d` or a verified descendant preserving its corrections. Do not reset a newer checkout or discard concurrent work to force the historical pin.

`main` did not contain the required stacked Feature 014 implementation when this brief was prepared. Work from the feature line, using an isolated worktree if needed.

## 3. Specification changes to implement

Amend the existing Feature 014 documents narrowly. Preserve authored requirements, history and final qualification objectives; do not replace them with a generic specification or start another architecture feature.

### 3.1 Introduce explicit delivery milestones

| Milestone | Required demonstration | Claim allowed |
|---|---|---|
| M1 — Assisted delivery | Reviewed requirements input, local engineering/inspection, real build and applicable unit/integration/target-simulation verification, complete scoped package | Input-assisted local end-to-end delivery of the IDR subset |
| M2 — Local requirements authorship | Same scope; Qwen derives requirements from the pinned primary sources, without the reference answers in its author context; three fresh accepted executions | Repeatability on this declared fixture, not broad qualification |
| M3 — Bounded product repair | Seed one independently detectable defect; the local workflow diagnoses, corrects and reverifies it with preserved accounting and evidence | Recovery of the specified defect class |
| M4 — Functional expansion | Add CRC operations in coherent increments, then another existing peripheral; rerun the earlier accepted cases | Measured coverage of each additional scope |
| M5 — Broader qualification | Reserved cohorts, measured learning benefit and operational campaigns under the existing Feature 014 criteria | Only the qualification claims actually demonstrated |

Keep existing Feature 014 completion criteria, including cohort and availability targets, separate. A completed milestone does not automatically tick an unrelated DA-T task or complete the feature.

### 3.2 Make DA-FR-054 execution policy explicit

Retain the existing full escalation ladder for existing profiles. Add a versioned, opt-in development execution policy that is pinned in the prepared work order and covered by the applicable execution scope.

For this development policy:

1. Run an initial engineering attempt.
2. Permit at most one bounded repair pass for each failed phase, shared across that phase's tasks and re-entry. Technical retries also consume the declared overall budgets; hidden nested retry loops must not multiply the allowance.
3. Record the actual outcome. Continue only where a coherent, valid frozen artifact can support downstream diagnostic work.
4. General autonomous diagnosis, advisory relaunch and factory maintenance are not prerequisites for finishing this development attempt.

Adapt existing routing rather than introducing another workflow engine. Do not impersonate an exhausted recovery ladder: record steps as executed, unavailable, or deferred by the declared development policy, with their real reasons.

Execution completion and product acceptance are distinct:

- A provisional downstream result remains linked to the unresolved upstream finding/assumption.
- Missing, contradictory or unsupported behavior blocks dependent work. Independence of another task must be demonstrated before it proceeds.
- Malformed contracts, stale/tampered evidence, failed executable checks and authority/resource failures must never become PASS through this policy.
- Unresolved required findings keep the final product BLOCKED. The existing release policy remains authoritative.
- Diagnostic continuation helps reveal downstream problems; it is not M1 acceptance.

If the existing advisory path can safely express this policy, extend it compatibly. The policy must not alter historical packages or silently change other profiles.

### 3.3 Scope safety claims accurately

Use the existing ASPICE-only development purpose. Safety assurance remains NOT_ASSESSED; this does not reclassify the work as QM.

Startup behavior, error handling and caller responsibilities must be concrete and supported by the actual work-order scope and sources. Never invent a safe state, safety allocation, register behavior or failure-handling contract to satisfy a generic checklist phrase. Missing required information remains an explicit input gap.

Update `spec.md`, `plan.md`, `acceptance-tests.md`, `tasks.md` and relevant traceability/status records together. Link this handoff from the normal Feature 014 entry point. Keep milestone acceptance distinct from final feature acceptance.

## 4. M1 scope and assisted-input contract

Create a separately identified work-order fixture derived from `examples/0014c-st-cube-crc/workorder.json`. Use the existing peripheral/profile mechanism; prefer a work-order-specific operation subset over altering shared CRC defaults.

### Included

- The two IDR functions and their actual signatures from the pinned ST delivery.
- The relevant primary-source semantics, allowed inputs, read/write effects, dependencies and necessary setup.
- Requirements-to-design-to-function-to-test traceability.
- Real compilation against the declared target/toolchain, host verification and applicable target-simulation verification.
- A complete offline package with source identities, executed evidence and explicit limitations.

### Excluded from this first scope

Polynomial configuration, CRC calculation/feed operations, input/output reversal, DMA, HAL, general peripheral onboarding and autonomous factory modification. Their exclusion is a prospective scope decision for this new development objective, never a repair of or retroactive scope reduction in the failed full-CRC mission.

Do not remove necessary dependencies to make the slice appear smaller. Verify the precise register semantics from the local pinned primary references; this document does not supply hardware values.

Keep delivered ST code FROZEN. This is an engineering-artifact and verification workflow around supplied code, not a claim of newly generated driver implementation. Preserve the existing rule that requirements are derived independently of delivered implementation code.

### Reviewed requirements input

Use the existing provided-artifact/input mechanism where adequate. Otherwise add the smallest generic import boundary, including:

- Full content hash, primary-source references and scope identity.
- A clear origin such as externally prepared requirements, with the actual preparation/review provenance.
- Normal structural, scope, traceability and semantic checks before freezing/using the artifact.
- Explicit reporting that SWE.1 authorship was assisted; no fabricated Qwen author receipt, inspection result or human approval.
- Tamper/staleness detection and downstream invalidation through existing mechanisms.

Codex may prepare the source-backed candidate requirements and validate them. It must not invent a completed human review. Reuse existing legitimate review evidence when applicable; record a missing review precisely and continue independent harness/source preparation.

All SWE phases must be represented with substantive artifacts appropriate to this small scope. Reuse deterministic rendering for structure, IDs and trace tables. Avoid padding documents with unrelated functions or boilerplate requirements.

## 5. Architecture and model constraints

Keep AFO/Fabro, versioned roles, MCP boundaries, current stores, deterministic verification, release packaging and supervision. No new orchestrator, agent hierarchy, memory store or dashboard is required.

For M1:

- Keep the selected local Qwen model and existing Ollama backend fixed. MTP is a separate later comparison.
  **Superseding owner decision, 2026-10-28:** "no, go with MTP" selects the
  single-slot Qwen3.8-27B Q8_0 MTP3/xhigh profile prospectively. The earlier
  Ollama-only instruction is historical. Backend smoke, complete role qualification
  and product acceptance remain separate; all other bounds below still apply.
- Maintain one admitted inference request at a time and bounded verification resources.
- Use small coherent engineering packets and self-contained instructions.
- Keep author and inspector roles separated, and use independent executable/reference checks to address common-model errors.
- Keep operational service recovery, operator controls and factual experience/disposition capture. Product diagnosis/maintenance and learning-benefit evaluation may be deferred under the explicit development policy.
- Existing applicable validated lessons may still be retrieved within their boundaries; do not automatically promote new lessons or persistent source changes.

### Admission preflight

Before a live trial, check the exact serialized requests for every role needed by that trial, including the release role and all reasoning/output allowances added by the gateway. Verify the applicable capability receipt or existing bounded qualification mechanism for the exact source/profile/model.

The newer diagnosis measurement exposes a real design problem: a 30,605-byte administrative manifest was part of the selected evidence and effective output included 32,768 reasoning tokens. Fix relevant request composition through bounded semantic evidence views, explicit deterministic administrative binding and externally retained hash-bound source records. Do not truncate decisive evidence or claim that a byte bound is an actual token count.

Do not expand all role budgets, disable admission, change reasoning settings or introduce a tokenizer merely to make this one case pass. Any such later change needs a separate measured comparison and correct identity binding.

M1 need not qualify a general recovery planner that it will not invoke. General diagnosis preflight and repair qualification belong to M3. Other M1 roles still need valid admission.

## 6. Tests and acceptance evidence

Use a small set of meaningful integration tests as the development anchor. Keep relevant inherited regressions; do not add tests that only assert prompt wording or duplicate constants.

### A. Fast integration fixture

Exercise real preparation, artifact validation, phase transitions, evidence storage, compilation/test execution and packaging boundaries. Provider responses may be deterministic fixtures for this test only; label every substitution. It proves plumbing, not Qwen capability.

Include focused checks for:

- Assisted requirements provenance, validation and tamper invalidation.
- The exact two-function scope and full coverage of its obligations.
- Development retry bounds and explicit deferred ladder steps.
- Dependency-safe provisional continuation and blocked release when required findings remain.
- Compatibility of existing profiles and historical behavior.

Do not build a generic replay platform to obtain this fixture. Reuse existing test helpers.

### B. Live local M1 run

Execute the same scoped work through the real local model roles and tool protocol. Record:

- Prepared scope, input/source/profile/model identities and assisted content.
- Outcome and actual evidence for every SWE phase.
- Build and verification commands, tool identities, exit codes and coverage applicable to this scope.
- Requirements/function/test mappings.
- Reported usage separately from conservative charges/reservations; missing usage stays UNKNOWN.
- Wall time, attempts, repairs and all unresolved findings.
- Final package path/hash and independently recomputable package verdict.

### C. Negative control

Introduce a defect that an independent check must detect, such as a deliberately wrong IDR readback implementation in an isolated mutant fixture or a broken required trace.

The production frozen delivery remains untouched. The negative control must fail its check and prevent acceptance; a model claiming PASS must not override it.

### D. Resume regression, independently of M1 success

Preserve candidate `98d066d` tests. Add the exact failed incident route: ASPICE SWE.1 failure → diagnosis admission refusal → advisory attempt → resume at SWE.1, with unresolved findings and exhaustion state propagated correctly.

Verify no failed inspection becomes PASS, accounting remains cumulative, incompatible identities refuse before copy/reservation where applicable, and required unresolved findings still block release. Keep this small deterministic regression separate from live recovery qualification. Do not make a new live autonomous-recovery success a prerequisite for M1.

### M1 acceptance checklist

- [ ] Both declared functions and their necessary dependencies are covered.
- [ ] Assisted requirements are legitimate, hash-bound and clearly attributed.
- [ ] All six SWE phases have substantive scoped artifacts and real recorded checks.
- [ ] Compilation and applicable unit/integration/target-simulation checks pass.
- [ ] Required traceability and independent inspection/release checks pass.
- [ ] The negative control is detected and rejected.
- [ ] The package is reproducible and `READY_FOR_OFFLINE_REVIEW` under the applicable existing policy.
- [ ] The report names the assisted boundary and the narrow supported scope.

A full run with remaining findings may be reported as diagnostic execution completed, product BLOCKED. It does not satisfy this checklist. A compiler-only or host-only result must retain that limitation and cannot be relabeled as target verification.

## 7. Implementation sequence and bounded working rhythm

1. Inspect current source/state and preserve uncommitted work. Reconcile this brief into the existing specification and add narrowly scoped tasks.
2. Prepare the two-function work order, supported requirements input and independent verification oracle. Freeze the fixture before measuring the candidate.
3. Implement only the import/routing/scope changes needed by M1. Run the fast integration fixture and negative controls.
4. Run the relevant inherited checks and the existing spec/handoff validators.
5. Prepare exact live commands, source/profile identities, per-role admission report, wall-time/token/attempt limits and evidence destination.
6. Execute the live trial when its actual authorization/prerequisites permit. Change one variable per experiment and record the question being tested.
7. If a phase fails, fix the smallest demonstrated cause and rerun the affected checks plus the end-to-end anchor. Do not turn every failure into a new architecture project.
8. Once M1 is accepted, implement M2 on the same scope. The reviewed answers become an external oracle unavailable to the requirements author; explicitly separate any author-training examples from reserved evaluation data.
9. After M2, implement the seeded repair demonstration, then expand function scope. Evaluate MTP separately against the accepted baseline.

Set bounded experiment budgets before execution using the measured role requests. Do not silently extend them. Repeated runs with unchanged inputs and the same failure signature need a new evidenced hypothesis before spending another attempt.

Keep the last accepted fixture as a regression anchor. Report progress by accepted supported functions, complete deliveries, repeatability, detected negative controls, duration and usage. Unit-test counts alone are not the delivery metric.

## 8. Execution authority, history and reporting

The owner has authorized this implementation direction and repository handoff. This document is not a signed runtime grant, a production deployment, an allowance reset or a completed review receipt.

The original `F014-E2E5H-20261028-CRC` mission remains exhausted. Its three attempts, 1.9m conservative charge, UNKNOWN aggregate actual usage and historical packages remain in cumulative reporting. The narrowly scoped development fixture must have an explicitly recorded objective and applicable prospective allowance; a renamed order cannot reset the old mission.

Do not infer live authority from the historical 2026-10-29 05:00Z production-grant expiry or the expired five-hour engineering window. Use valid current authority when it already covers the proposed action. If it does not, finish the concrete source, tests, commands and admission preparation, then report the exact missing prerequisite. Do not stop independent implementation work merely because live execution is unavailable.

Keep model-free supervision running through finite job/campaign completion and respect authenticated operator intent. Do not auto-merge runtime changes or deploy through this documentation task.

Persist evidence using existing repository conventions, with exact revisions, commands and truthful limits. Publish no hidden reasoning, credentials or restricted primary-reference text.

## 9. Deliverables for the implementing Codex

Deliver incremental commits containing:

1. Narrow Feature 014 specification/task/acceptance updates and a linked entry point.
2. The minimal scoped work order and legitimate assisted-requirements input mechanism.
3. Compatible development routing, only if required for the agreed policy.
4. The fast end-to-end fixture, independent negative control and incident-path resume regression.
5. A bounded live-run harness/runbook with per-role preflight.
6. Actual run evidence and package when execution is available, otherwise the precise remaining prerequisite with all independent preparation complete.

The implementation report must distinguish source implemented, deterministic checks passed, live local execution, product acceptance, assistance level and later unrun milestones.

**Start with M1. Finish one small delivery path before expanding the objective.**

## 10. Superseding owner allowance decision — 2026-10-28

The owner approved the actual requirements review and live M1 with “I approve, go”,
then explicitly requested: “increase all the limits to extraordinary high values,
after it is working we can define the limits”. This prospectively supersedes the
one-repair and unchanged-budget instructions above for a separately identified
ASPICE_ONLY development policy, `incremental-delivery-high-allowance-v2`.
Legacy `incremental-delivery-v1` and other profiles retain their existing bounds.

The opt-in policy allows 1,000 phase repairs and upstream loops, 1,001 calls per
author task, and 10,000 tool calls per visit/failed checks per operation. Counters
remain durable across re-entry. A repeated deterministic rejection still blocks
the affected job for external diagnosis under the owner's earlier stop-and-rethink
instruction; it does not stop model-free factory supervision.

The prospective M1 allowance is 100 million reserved tokens per native execution,
100 billion cumulative mission tokens, 100,000 requests, one million tool calls
and 1,000 execution attempts. These are finite ceilings, not estimated consumption.
The cumulative ceiling covers 1,000 conservative execution reservations; unknown
usage and historical charges are never refunded or reset. Existing grants are not
renewed: a new signed scope must name its own deadline within current authority.

The MTP profile v3 uses 131,072 context tokens, 16,384 answer tokens plus the
existing 32,768 xhigh reasoning reserve, one inference slot and f16 KV. Omniverse's
development profile uses the existing maximum timeout scale of 10 and six-hour
request/structured-visit ceilings, still subordinate to the signed mission deadline.
Omniverse's
allocation-only probe passed at this context, with roughly 9.7 GiB VRAM free.
That allocation is not a model-quality, role-capability or product-success result.
Larger experimental role identities require the exact profile hash and hash-bound
allocation proof, in addition to the existing signed qualification-only trial.

This owner-authorized change preserves functional resource requirements, source
coverage, independent checks, release gates, single inference, operator fencing,
old mission expenditure and explicit deferred diagnosis/maintenance. It authorizes
preparation and execution of the scoped M1 trial; it does not claim M1 acceptance.

## 11. Superseding owner QM decision — 2026-10-29

Owner instruction: **“Forget about safety now!!! implement as QM”**.
For prospective development runs this supersedes section3.3's prohibition on QM
classification and the earlier ASPICE_ONLY lane selection. Use explicit purpose
**QM** and the owner-bound QM development policy for any declared driver.
Preserve historical allocations, grants, failed runs, costs and packages unchanged.

Keep the functional/ASPICE engineering obligations: source-supported requirements,
startup/error behavior within the supported invocation domain, caller responsibilities,
architecture/dependencies, code correctness, coding rules/static analysis, finite
resource constraints, traceability, unit/integration/target-simulation/software tests,
independent checks and complete packaging. QM does not demand safety allocations,
allocated safety safe states, safety mechanisms, SSA/TAA or ISO safety assurance.

Tailor only the safety-specific clauses of the prospective QM checklists through
the versioned owner policy. Required flags, major/critical blocking, author/inspector
separation and all functional checks remain. Preserve old checklist semantics and
receipts for other purposes; a failed historical inspection cannot become PASS.
An explicitly source-supported absence of error signaling or startup calls is a
valid contract; missing required functional behavior remains a failure.

Keep Qwen3.8 Q8 MTP3/xhigh and its measured inference/context settings unchanged.
Use the existing same-M1 mission, normal serial AFO intake and current exact-source
authority. A new policy's current admission grant may authorize a continuation
without replacing the original mission grant, deadline, caps or spent counters.
No silent time extension, allowance refill or automatic source promotion.

The nine functional requirements remain unchanged. Preserve their original owner
review, and record the new explicit QM scope decision separately as a composite
review of unchanged functional content plus owner reclassification. Do not claim
a second full functional review. Current M1 still requires real six-phase execution
and independently recomputable READY_FOR_OFFLINE_REVIEW; M2–M5 remain subsequent.

## 12. Superseding owner demonstration decision — 2026-10-29

Owner instruction: “by now lets relax so much quality constraints, i just want to
see qwen running a full pipeline, let them do the quality improvements later on”.

The immediate execution objective is a QM demonstration through every applicable
SWE.1–SWE.6 author, inspector, build/test activity and final packaging stage.
Use opt-in execution policy qm-pipeline-demonstration-v1 and the explicit local
QM demonstration profile. Follow the existing workflow once; quality-gate failures
are recorded observations and do not branch into repair loops or stop the next
phase. Preserve actual failed/absent checks, provisional dependencies and artifacts.
Freeze available real workproducts as unqualified snapshots without inventing
missing artifacts or passing inspections. Frozen delivered code may enter after
the intact requirements snapshot despite failed/missing quality inspection; record
that provisional demonstration injection and retain original input/delivery hashes.

Keep current authorization, operator intent, one admitted inference, tool permissions,
source integrity, finite cumulative accounting and protocol boundaries. Technical
failures are visible, with no fabricated artifacts or claims. Missing work may cause
a role to report BLOCKED; the workflow still attempts the subsequent roles.

The result is DEMONSTRATION_ONLY with truthful findings and a blocked/unaccepted
product package. It cannot satisfy M1 acceptance, release production software,
qualify the model or claim self-healing/learning benefit. Improve quality after the
full demonstration. Later strict M1 and M2–M5 criteria remain separate and unproven.
This scope supersedes the unactivated 5b398d2 QM runtime packet; prepare new exact
source/profile execution records without resetting history or extending the window.
