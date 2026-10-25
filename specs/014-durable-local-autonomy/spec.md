# Feature Specification: Durable local autonomy and recovery

**Feature Branch**: `feat/014-durable-local-autonomy`  
**Created**: 2026-10-25  
**Status**: SPECIFIED — implementation and live qualification NOT_RUN  
**Implementation base**: `f6ff873d5b4f3e9e46956ef26766181aaec2289d` (PR #41, evidence head; runtime `36ed0fc70bd8765f0cc90a45b21bbf02924b0269`)  
**Input**: Owner request to turn the reviewed Omniverse2 Qwen autonomy plan into a repository Spec Kit package for Codex implementation.

## Outcome and scope

Make local recovery progress from complete engineering evidence to a bounded semantic decision, a durable broker receipt, one effective implementation dispatch, and independent verification. Extend the existing AFO/Fabro implementation; do not replace it with an unrelated orchestration framework.

Core scope includes operational self-healing, resource self-management, product repair, and candidate-only factory improvement. Current policy governs all activation. Codex is the external implementation engineer; authoring protected AFO fixes through this reviewed engineering change does not grant a production agent permission to edit or deploy those files.

**Owner clarification:** the design MUST explicitly accommodate local Qwen limitations. Operationally correct orchestration does not imply adequate model capability. Tasks, memory, verification and fallback must fit measured local competence; larger context, more agents or repeated prompting are not assumed solutions. See [local-model-design.md](local-model-design.md).

**Owner clarification — continuous improvement:** every run, driver and feature must contribute persistent experience that can improve future work. Integrate this with Forge-C's existing knowledge store, curator/MCP, inspection lessons, CAPA/CRE and KPI paths. Every-job learning is core scope, including successful ordinary work; it does not wait for future automatic source promotion. See [continuous-learning.md](continuous-learning.md).

**Owner clarification — continuous operation:** the factory MUST operate 24/7 with no autonomous global stop on job failure, empty queue, Qwen limitation or campaign completion. Extend existing AFO/systemd/supervisor capabilities with durable waiting, recovery and fair continuation. Service lifetime is independent of finite engineering budgets and job outcomes. Preserve authenticated operator shutdown and fail-closed admission. See [continuous-operation.md](continuous-operation.md).

Automatic persistent source/skill/prompt/workflow deployment is excluded under AFO-FR-053. [Future worker promotion](future-worker-promotion.md) is a proposal-only deliverable, not a core runtime capability or a prerequisite for completing this feature. No production release/safety approval is automated.

## Evidence baseline

The four diagnosis jobs consumed 54,704 reported tokens, 64,000 reserved and 64,856 conservatively accounted, with zero accepted model recovery plans and zero new implementation attempts. A deterministic RULE/CLOSE_BLOCKED plan is not a model recovery success. Five unique historical RCC executions were adopted into four orders, producing 20 attempt rows without 20 executions. The final RCC package passed SWE.1/SWE.2 and exhausted SWE.3 rework with 50 gaps.

All diagnoses were terminal by 2026-10-24 21:18:03.337692 UTC. The final state appears in 39 snapshots through 2026-10-25 06:43:45.067314 UTC. This is service monitoring, not 9.4 hours of engineering progress. V4's native stopping cause is unresolved; its 13,071 reported tokens do not establish context overflow, token exhaustion, weak model capability or a tool-turn-limit cause.

Source pins and native IDs are recorded in [evidence-baseline.md](evidence-baseline.md). The original records and exhausted authority remain immutable; no new order name may reset them.

## User Scenarios & Testing

### US1 — Obtain an actionable, durable diagnosis (Priority: P1)

As the factory owner, I need Qwen to receive the decisive evidence and commit an engineering decision without spending its allowance reproducing administrative metadata.

**Independent test:** replay complete/incomplete cases and malformed/valid outputs through the real registered MCP boundary and native completion adapter with deterministic provider fixtures. This demonstrates protocol behavior, not Qwen quality.

1. Given a decisive finding beyond the current 1,500-character summary, when the case is assembled, then the finding and its primary evidence remain accessible and completeness is explicit.
2. Given a submitted proposal and a lost response/crash, when the controller resumes, then it recovers the durable receipt without another effective implementation dispatch.
3. Given a compact success response without a matching proposal, then the outcome is FAILED_PROTOCOL rather than a proven absence of materially different strategies.

### US2 — Preserve limits and reconcile execution (Priority: P1)

As the operator, I need cancellation, late usage, continuation orders and crashes to preserve one mission's authority, expenditure and execution identity.

**Independent test:** deterministic concurrent admission, uncertain launch, cancellation and verifier-dispatch fault injection; assert ledger conservation and eventual reconciliation.

1. Given exhausted capacity, when a continuation is created or the controller restarts, then subsequent admission is refused without erasing history.
2. Given a terminal task whose native execution is still running, then cancellation remains supervised and its inference capacity is not released as if quiescent.

### US3 — Recover eligible operational faults without a model (Priority: P1)

As the operator, I need approved service recovery to work even when Qwen or Fabro is unavailable.

**Independent test:** kill/restart isolated test services, interrupt mounts and simulate resource pressure under deterministic recipes. Healthy monitoring uses zero model tokens.

1. Given an eligible unhealthy service, when its approved recipe runs, then the service is restored or an explicit dependency/uncertainty block is recorded within the bounded recovery window.
2. Given healthy idle services and exhausted engineering work, then health remains healthy while mission progress is reported exhausted, with no inference launched merely to keep the GPU busy.

### US4 — Repair a product obligation and verify it (Priority: P1)

As the engineering owner, I need a repair to change the implicated obligation and preserve every required gate and provenance boundary.

**Independent test:** a frozen, known defect with an independent counterexample reaches a scoped implementation and reinspection; live RCC remains a separate qualification campaign.

1. Given a failing SWE.3 obligation, when a materially different plan is admitted, then the author receives the scoped strategy and independent verification checks the changed obligation and impacted dependencies.
2. Given incompatible historical evidence, then a new execution cannot inherit old phase PASS results merely because those results once existed.

### US5 — Improve the factory within existing authority (Priority: P2)

As the owner, I need eligible defects to produce isolated, reproducible candidate improvements and reusable validated lessons.

**Independent test:** candidate passes its reproducer but fails an independent holdout; proposal is quarantined and nothing is promoted.

1. Given an allowlisted factory defect, then a candidate is independently evaluated and staged under current policy.
2. Given a protected AFO/CRE/skill/policy defect, then the runtime records the incident and external engineering need; it does not expand its own permissions.

### US6 — Demonstrate autonomy on fixed cohorts (Priority: P1)

As the owner, I need evidence distinguishing implementation, protocol competence, useful recovery, benchmark yield and operational reliability.

**Independent test:** score fixed synthetic results with recoverable, blocked, failed and timed-out outcomes; no denominator omission can turn them into a passing campaign. Real inference/soaks require valid campaign authorization.

### US7 — Preserve existing factory paths (Priority: P1)

As the owner, I need the existing Codex/Claude/native/ACP and historical packaging behavior preserved while local recovery evolves.

**Independent test:** inherited regression and offline package checks on the same candidate revision, with explicit limitations for unavailable live providers.

### US8 — Fit self-X work to measured local-model capability (Priority: P1)

As the owner, I need a factory that can work productively with a constrained local Qwen rather than assuming frontier-model reasoning, reliable self-review or unlimited usable context.

**Independent test:** the same frozen engineering obligations are evaluated as a large task and as short scoped tasks, with complete coverage checked independently and total cost charged to the same mission. Holdout defects test correlated author/inspector mistakes; stale memory and unanswerable tasks test honest capability limits.

1. Given a task exceeding the qualified role/context envelope, then the controller repartitions it or selects an already qualified authorized local path; otherwise it records a capability/dependency block.
2. Given repeated plausible but ineffective proposals, then a measured stall ends bounded search; model confidence or another same-model vote does not establish correctness.

### US9 — Learn from every job and reuse qualified experience (Priority: P1)

As the owner, I need every successful, failed or blocked driver/feature job to contribute factual experience, with useful lessons applied to subsequent work through the existing factory capabilities.

**Independent test:** job A completes ordinary engineering work without a repair incident; its recorded experience produces a scoped candidate, independent checks qualify it, and a later eligible job B retrieves the validated version and records independent outcomes. Replay, stale versions, cross-device transfer and adverse cases are tested separately.

1. Given any terminal job, when reconciliation completes, then exactly one effective experience/disposition exists for its source execution, including explicit deferred or no-new-evidence outcomes.
2. Given a successful source job, then a lesson cannot claim general effectiveness until independent applicable/adverse cases support it; no fake PROMOTED repair is created.
3. Given the next eligible job, then qualified, applicable lessons are retrieved within current bounds and role barriers, their use is traceable, and the product still passes all existing independent gates.
4. Given a harmful or stale lesson, then it leaves retrieval and its prior consumers remain auditable without rewriting historical packages.

### US10 — Keep the factory operating continuously (Priority: P0)

As the owner, I need the factory to remain managed and responsive 24 hours a day, every day, recover eligible failures without prompting me, and continue other eligible work when one job cannot proceed.

**Independent test:** finish, fail and exhaust the last job; keep the queue empty; remove and restore Qwen; trigger controller crash, hang and restart-limit exhaustion; then submit eligible work. The control plane remains active or restores itself within the declared recovery envelope, retains all accounting and admits the next eligible job without manual relaunch. An intentional operator stop remains respected.

1. Given a failed or capability-limited job, then only its affected work stops; unrelated eligible work progresses and missing dependencies have durable waiting/reprobe state.
2. Given the end of a campaign or depleted inference allowance, then model-free service continues without inventing work, renewing authority or resetting expenditure.
3. Given a transient dependency or process failure, then approved bounded recovery restores service and reconciles native effects; persistent faults remain visible without hot loops or false health.
4. Given shutdown or revoked authority from an authenticated operator, then all restart layers honor that intent; later authorized resume reconciles state before admission.

### Edge cases

Missing/stale artifacts; findings beyond page boundaries; malformed output; receipt replay; accepted proposal followed by prose; native success with no proposal; late native acceptance after revocation; cancellation errors; verifier death before/after publication; disk/mount loss; unknown token usage; concurrent continuation admission; exhausted authority; changed model digest; corrupted backup; wall-clock/DST jumps; failed candidate rollback; missing authoritative GPIO inputs.

## Requirements

All requirements below are **NOT_IMPLEMENTED** by this specification. Tests are mandatory for this feature. IDs map to tasks and acceptance cases in [traceability.csv](traceability.csv).

### Functional Requirements

- **DA-FR-001 [US1]**: Preserve the pinned historical evidence and native identities; collect redacted native stop/finish reasons, actual settings, counted/denied calls, recorder exits and per-request usage where available. Missing evidence MUST remain UNKNOWN and MUST NOT block independent deterministic implementation work.
- **DA-FR-002 [US1]**: Assemble immutable diagnosis packets with the complete typed finding inventory, primary artifact/evidence references, digests, completeness/truncation flags and prior strategy history. A summary MUST NOT be treated as exhaustive engineering input.
- **DA-FR-003 [US1]**: Provide bounded, read-only, hash-bound evidence access to the failed phase's relevant requirements, design, implementation and diagnostics. Preserve role isolation and prohibit downstream code in an upstream SWE.1 author context.
- **DA-FR-004 [US1]**: Measure the complete serialized model input including schemas and reserve generation capacity. Repartition oversized evidence by coherent obligations with a coverage manifest; never silently discard mandatory evidence.
- **DA-FR-005 [US1]**: Restrict model proposals to bounded semantic judgments and typed PROPOSE_REPAIR, NEEDS_EVIDENCE or CLOSE_BLOCKED outcomes. Any evidence request/correction loop MUST consume the same mission capacity and have a policy-bounded limit.
- **DA-FR-006 [US1]**: Bind administrative plan fields deterministically from authoritative state and preserve the existing recovery-plan contract and independent admissibility checks. Do not coerce wrong semantic types, fabricate evidence or manufacture material difference through labels/seeds.
- **DA-FR-007 [US1]**: Qualify the actual serialized MCP schema and installed gateway/native adapter. Use constrained proposal generation or a separately qualified narrow proposal tool; declared source annotations alone do not establish the model-visible contract.
- **DA-FR-008 [US1]**: Persist a case/job/nonce/contract-bound receipt and derive completion deterministically. Distinguish stored submission, rejected/admissible plan, execution and verified repair. Missing/mismatched proposals MUST be FAILED_PROTOCOL, not NO_MATERIALLY_DIFFERENT_STRATEGY.
- **DA-FR-009 [US1]**: Use stable idempotency identities, fencing and durable outbox reconciliation for proposal commit, implementation dispatch, verification and publication. A crash after an effect but before acknowledgment MUST NOT cause duplicate effective execution.
- **DA-FR-010 [US2]**: Define model-request, tool-call, input/output token, wall-time and correction limits separately. Guarantee a deterministic completion path; if model submission remains necessary, reserve submission/correction calls within the authored allowance.
- **DA-FR-011 [US2]**: Enforce shared durable mission/authorization-lineage budgets across continuations, siblings and restart, linked to existing product/resume accounting without double-counting imported attempts. Never reset exhausted expenditure or deadlines through a new order ID.
- **DA-FR-012 [US2]**: Admit each generation against measured input and supported output caps; account conservatively for unknown/late usage and overshoot, initially charging at least max(reserved,reported) per uncertain job. Characterize cancellation delay; a polling threshold MUST NOT be advertised as a hard cap.
- **DA-FR-013 [US2]**: Track task outcome independently of execution liveness. Reconcile late launch receipts by nonce after revocation and supervise cancellation until authoritative quiescence or explicit unresolved execution uncertainty. Do not release inference capacity while execution may still run.
- **DA-FR-014 [US2]**: Make independent verifier dispatch recoverable with durable intent, stable worker identity, lease, heartbeat and idempotent publication; recover crashes before/after spawn and before/after result recording.
- **DA-FR-015 [US3]**: Classify planner/protocol/transport faults separately from product-quality and no-strategy decisions. Apply only bounded, preapproved operational recipes or qualified adapters; otherwise preserve a typed incident and explicit block or candidate route.
- **DA-FR-016 [US3]**: Keep supervision model-free and independently survivable. Test approved restart/reload/reconciliation recipes, rate limits, backups/restores and clock behavior. A release rollback is eligible only when signed policy explicitly authorizes that exact transition; qualification alone grants no deployment authority.
- **DA-FR-017 [US3]**: Preserve the isolated local-only profile, pinned served model, namespace confinement, one admitted inference request and bounded CPU verification/backpressure. Check mounts, disk/resource pressure and external-route denial before admitting work.
- **DA-FR-018 [US3]**: Report service health, native execution liveness and engineering progress separately, with correlated receipts, stop reasons and cost/latency components. Keep raw hidden reasoning absent and raw prompts/completions OFF by default; redact retained data.
- **DA-FR-019 [US4]**: Diagnose the smallest reproducible failed obligation using actual counterexamples, classify root causes versus symptoms, record predicted repair effect and reverify impacted dependencies. A lower gap count alone is not convergence evidence.
- **DA-FR-020 [US4]**: Preserve Feature 012 provenance and valid-prefix compatibility. Historical incompatible revisions require the existing authorized fresh-attempt mechanism and all required phases; no copying of unverifiable PASS evidence or rewriting terminal records.
- **DA-FR-021 [US4]**: Preserve independent author/inspector roles, complete SWE.1–SWE.6 gates, frozen oracles/holdouts and sealed package integrity. Agent/native SUCCEEDED alone cannot establish READY or safety acceptance.
- **DA-FR-022 [US5]**: Restrict runtime maintainer edits to its existing allowlist, isolated candidate workspace and baseline-fail/candidate-pass reproducer plus independent CRE. Persistent source promotion remains external under AFO-FR-053; protected AFO/CRE changes are external engineering work.
- **DA-FR-023 [US5]**: Admit lessons from independently verified evidence through the existing knowledge lifecycle: preserve strict legacy promoted-repair checks and add source-specific validation for ordinary job outcomes under DA-FR-039–041. Keep source/version/applicability predicates, negative results, invalidation and retractability. Untrusted lessons never override requirements, policies or inspection evidence.
- **DA-FR-024 [US6]**: Freeze a mixed 20-case × 5-repeat native local protocol cohort before execution, with expected recoverable/block classes. Require 100/100 accurately classified terminal outcomes, zero false success/duplicate effects/authority escape, and admissible plans for all designated recoverable cases. Report syntactic and useful-plan outcomes separately; this is a pilot gate, not a reliability proof.
- **DA-FR-025 [US6]**: Demonstrate a newly authorized RCC recovery reaching real implementation and every independent native SWE gate plus intact sealed READY archive. Preserve old expenditure. GPIO remains blocked until RCC succeeds and its own profile, authoritative inputs and frozen intake are ready.
- **DA-FR-026 [US6]**: Qualify operational recovery through 24h smoke, 72h pilot and 168h unattended fault-injection soak with real admitted work, valid authorization, recorded fault exposure and zero intervention inside the declared eligible envelope. Idle monitoring alone is insufficient.
- **DA-FR-027 [US6]**: Retain Feature 010 quality criteria on a frozen Omniverse2 cohort: at least 27/30 representative end-to-end READY outcomes, every seeded critical defect detected, no known false READY, all remaining failures honestly BLOCKED, structured invalidity below 1%, and target 50% median prompt-input reduction against a comparable baseline without mandatory evidence loss. Include failures/retries and report uncertainty and inspector false rejections.
- **DA-FR-028 [US6]**: After deterministic defects are repaired and the unchanged profile is measured, allow bounded, authorized model/runtime comparisons on the same frozen cases, changing one factor at a time. RCC success is not a prerequisite; download permission is not inference qualification or an allowlist change.
- **DA-FR-029 [US7]**: Preserve the existing provider/default paths, historical artifacts, native gates and public work-order compatibility. Run relevant inherited tests on the candidate revision and disclose unavailable live checks; no runtime change is enabled merely by this spec's presence.
- **DA-FR-030 [US5]**: Publish readiness and evidence separately for specification, implementation, protocol, product and operational qualification. Document future narrow worker promotion only as a proposed policy change; do not implement an enabling flag/bypass or make policy approval a blocker for core recovery delivery.
- **DA-FR-031 [US8]**: Maintain measured capability profiles separately for diagnosis, authoring, inspection and maintainer proposals, bound to actual model digest, quantization, reasoning/sampling settings, adapter/schema versions and evidence/task complexity. Advertised context, model size or successful serialization MUST NOT qualify semantic competence.
- **DA-FR-032 [US8]**: Decompose engineering work into short-horizon, coherent obligations with explicit inputs, allowed edits and independent expected verification. Maintain global coverage and dependency checks, preserve phase order and share the original attempt/token/time limits across subtasks. Do not ask a single local-model call to resolve an unbounded package-wide failure set.
- **DA-FR-033 [US8]**: Keep authoritative evidence and progress in external indexed memory and compact versioned checkpoints. Retrieve only relevant primary evidence with completeness checks; validate/retract lessons and reject stale digests. Summaries and compressed checkpoints MUST NOT replace required source material, and configured context length MUST NOT be equated with measured effective context.
- **DA-FR-034 [US8]**: Use bounded sequential candidate search only within authorized capacity, requiring materially distinct hypotheses and independent verifier feedback. Rank candidates by obligation closure and regression evidence, not self-confidence, prose quality or majority vote. Stop the affected candidate search on exhaustion, repeated fingerprints or measured lack of progress; preserve one admitted inference request and continuous model-free factory operation under DA-FR-045–052.
- **DA-FR-035 [US8]**: Test correlated local-model author/inspector failures with independently maintained mutants, metamorphic/reference checks and applicable deterministic semantic tools. Separate contexts alone do not establish error independence. An unsupported semantic claim remains unverified and cannot become PASS through same-model agreement.
- **DA-FR-036 [US8]**: Define an explicit capability-limit route: repartition, request missing evidence or use an already qualified local adapter/model within current authority; otherwise return a typed CAPABILITY_LIMIT or MISSING_EVIDENCE block. No endless retries, implicit cloud fallback, self-increased budgets, online weight training or autonomous acceptance-threshold relaxation is introduced.
- **DA-FR-037 [US9]**: Capture factual experience for every driver/feature job and authoritative phase outcome, including success, failure, block, cancellation, timeout and uncertainty. Bind immutable evidence to unique execution identity; deduplicate adopted rows/replayed events and preserve original sealed packages. After bounded reconciliation, capture/disposition coverage MUST be complete or explicitly incomplete with pending work.
- **DA-FR-038 [US9]**: Reuse the event/outbox and existing curator path for bounded asynchronous consolidation. Each job receives a durable learning disposition, including NO_NEW_EVIDENCE, DUPLICATE_SUPPORT or DEFERRED_BUDGET when accurate. Learning inference/verification consumes explicit existing allocations and one-inference admission; healthy monitoring remains model-free.
- **DA-FR-039 [US9]**: Extend the existing LessonStore, lesson contract, knowledge MCP and curator with compatible versioned source kinds for verified ordinary outcomes and verified negative observations. Preserve legacy PROMOTED repair validation, IDs/history/usage and inspection-lesson governance. Do not fabricate repair incidents, create a competing knowledge authority or silently broaden runtime grants.
- **DA-FR-040 [US9]**: Retrieve applicable VALIDATED lessons before subsequent relevant jobs/phases through the existing bounded knowledge path; enforce phase, role, target/device/source/tool/configuration compatibility and fully serialized context limits. Deliver the complete bounded meaning, constraints, exclusions and provenance through authorized artifact resolution/packet assembly; a 120-character remedy snippet is not complete learning input. Explicitly omit/defer a lesson that cannot fit. Record version/hash exposure and verified application separately. No author judgment or forbidden downstream content may enter inspectors/upstream authors through memory.
- **DA-FR-041 [US9]**: Independently qualify candidate provenance, scope, applicability, positive/adverse cases and claimed benefit. Successful source work alone is not proof of general effectiveness; failed work may establish a checked negative observation but not an untested successful remedy. Keep generic inspector lessons on their existing recorded-source, paired-defect and CRE promotion path.
- **DA-FR-042 [US9]**: Measure learning benefit using existing comparable KPI cohorts, frozen baseline/memory-enabled comparisons and chronological cross-job evaluation. Include all learning overhead/retries; preserve critical-defect detection and no known false READY. Protect final holdouts and report insufficient evidence honestly; no novel lesson or monotonically higher score is required for every run.
- **DA-FR-043 [US9]**: Extend existing deduplication, version history, TTL, retraction and consumer tracking with applicability-aware identity and contradiction/invalidation handling. Reject stale/cross-scope matches; preserve historical uses and identify affected consumers. Narrowed or changed statements require qualified successor versions rather than mutation under an existing hash.
- **DA-FR-044 [US9]**: Route measured recurring failures and useful success patterns into the appropriate existing CAPA/CRE/maintainer or external-engineering improvement lane, with a predicted effect and independent qualification. Preserve repair reproducer requirements; evaluate success-derived optimizations against a measured baseline through existing CHANGE qualification without fabricating incidents or widening the maintainer grant. Publish capture coverage, qualified knowledge, observed use and demonstrated benefit separately through existing KPI/scorecard mechanisms. Knowledge cannot activate protected source/prompt/SKILL/workflow/policy changes.

- **DA-FR-045 [US10]**: Maintain continuous service intent independently of engineering authority and job outcomes through existing AFO/supervisor services. Production operation MUST have no finite cycle count, nightly expiry or autonomous global stop on success, failure, BLOCKED, capability limit, empty queue, exhausted budget or campaign completion. Continue model-free supervision, supported reconciliation, intake/status and eligible scheduling; never infer ACTIVE authority or product success from service liveness.
- **DA-FR-046 [US10]**: Extend existing systemd/Conductor/supervisor/watchdog paths for headless boot and recovery after crash, unexpected clean exit, hung cycle and start-rate-limit exhaustion. Use actual local-profile units, mounted durable state and installed-version-compatible directives. Preserve bounded restart bursts, persistent cooldown, independent slow recovery and operator intent. No cloud dependency, blind replay, recurrent rapid counter reset or disabling of rate limits is permitted.
- **DA-FR-047 [US10]**: Persist scoped waiting reasons, failure history, next-probe deadlines and material resumption predicates for unavailable dependencies, open breakers, resource pressure and missing authority. Bounded model-free probes continue after a recipe burst is exhausted; eligible transient recovery resumes automatically after verified restoration and valid authority. Never reopen exhausted terminal work, extend grants, reset mission accounting or release uncertain execution leases merely to keep running. Freeze finite probe/backoff/deadline bounds before qualification.
- **DA-FR-048 [US10]**: Isolate item-local faults/refused candidates through existing queue/backoff/quarantine/dead-letter mechanisms and schedule unrelated eligible work fairly. Prevent head-of-line poisoning by an unauthorized, malformed or repeatedly failing item; preserve real dependencies, shared-resource constraints and independent verification. Shared storage/integrity faults MUST close affected admission and remain explicitly degraded, not be swallowed as item-local errors. Bound each loop stage and item batch.
- **DA-FR-049 [US10]**: Support sustained operation with bounded log/temporary-data retention, referenced-evidence protection, WAL/backup maintenance, resource monitoring and reserved control-plane capacity through existing components. Enforce backpressure before model or learning work can starve supervision/cancellation. Missing/read-only/full mandatory storage blocks affected writes without ephemeral fallback, evidence deletion or database reset; independent monitoring reports degradation where possible. Restore only after verified identity/integrity checks and approved remediation.
- **DA-FR-050 [US10]**: Preserve authenticated, durable operator pause/drain/resume, revocation and shutdown semantics across all service restart/boot paths. Bind start/restart intents to a durable operations epoch; serialize control effects, reject stale dispatch and reconcile already in-flight effects against newer intent. Do not issue an effective-stop receipt until contrary pending starts and workers are settled under policy; unresolved cancellation stays explicit. Deliberate stop/disable/mask MUST NOT be undone by watchdogs or metrics-driven recovery. Unknown intent admits no new restart/work authority. An AI job result cannot authorize a global shutdown or override operator intent.
- **DA-FR-051 [US10]**: Report desired service mode, observed control-plane availability, worker/dependency readiness and engineering progress separately through existing events/status/KPI paths. Report next probes, overdue deadlines, restart/intervention counts, queue age, detection/restoration times and wait/outage intervals. Count missing telemetry as UNKNOWN/unavailable and preserve all outage causes, including maintenance and host power loss, in a gross 24/7 service-window denominator; scoped metrics must remain separately labeled. Keep existing 30-day availability/restoration objectives unproven until measured.
- **DA-FR-052 [US10]**: Extend DA-FR-026 qualification with deterministic and real systemd fault cases plus separately authorized 24h/72h/168h unattended workload campaigns covering DA-FR-045–051. Freeze workload, fault exposure, measurable deadlines and denominators before execution. Require no autonomous global abandonment, no operator intervention for eligible recovery, no duplicate effective execution and no budget/quality bypass; record every outage and unresolved fault. After each engineering campaign ends, verify continuing model-free service and later eligible intake without manual relaunch. Claim only the tested envelope, never physical zero-downtime from a single host.

### Key Entities

DiagnosisPacket, SemanticProposal, CompletionReceipt, MissionLedger, ExecutionLiveness, VerificationJob, RecoveryIncident, QualificationCampaign, JobExperience, LearningDisposition, versioned VerifiedLesson, OperationsIntent, DependencyWait and ServiceObservation. Extend existing subsystem ownership rather than creating competing authorities. See [data-model.md](data-model.md), [continuous-learning.md](continuous-learning.md), [continuous-operation.md](continuous-operation.md) and [contracts/README.md](contracts/README.md).

## Success Criteria

- **DA-SC-001**: Every deterministic protocol/crash/accounting acceptance case passes on the candidate, with zero false success, duplicate effective dispatch, lost accepted receipt or history reset.
- **DA-SC-002**: The frozen native protocol cohort satisfies DA-FR-024; useful plan rate is reported separately from correctly blocked cases.
- **DA-SC-003**: One genuine RCC recovery satisfies DA-FR-025; product acceptance still belongs to the existing gates and offline review authority.
- **DA-SC-004**: Operational campaigns satisfy DA-FR-026 and DA-FR-052. Existing 99% rolling-30-day availability and p95 transient restoration ≤10 minutes remain objectives until measured, not claims from a short soak.
- **DA-SC-005**: The representative product benchmark satisfies DA-FR-027 with fixed denominators and complete failure accounting.
- **DA-SC-006**: Core implementation can be completed without approving or activating autonomous worker-source promotion.
- **DA-SC-007**: Every unique terminal job has a factual experience and explicit learning disposition after reconciliation; ordinary successful jobs are included. Duplicate adoption/replay never inflates learning support.
- **DA-SC-008**: A chronological job-A-to-job-B qualification demonstrates applicable knowledge reuse and independently measured benefit on a predeclared comparable cohort, preserving quality/inspection criteria. Capture alone does not satisfy demonstrated improvement.
- **DA-SC-009**: All continuous-operation acceptance cases pass, including empty/exhausted campaigns, recovered restart-limit exhaustion, fair progress past a refused item and deliberate operator shutdown. The factory has no automatic end-of-service condition; finite engineering work never implicitly disables it.
- **DA-SC-010**: Fault campaigns record bounded unattended recovery within the declared eligible envelope and a complete service/worker/product timeline. Missing telemetry and physical outages cannot be counted as healthy; real 30-day availability remains separately evidenced.

## Assumptions and dependencies

- Build on PR #41 and Features 005/010/011/012/013, retaining current source/policy boundaries.
- Omniverse2 has the profile-recorded RTX 6000 Ada 48 GB and Core Ultra 9 285K, with approximately 125 GiB observed system RAM; this is not proof a particular model/context fits.
- Native detailed events and authoritative RCC artifacts may require read-only host access. Their absence does not justify fabricating evidence or halting unrelated implementation.
- This request authorizes specification delivery. Future deployment, model campaigns and source promotion follow their existing explicit authorization rules; the exhausted October 24 diagnosis grant is not renewed here.
