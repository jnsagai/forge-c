# Acceptance tests: Durable Local Autonomy

This document defines qualification work; it records no executed test or successful deployment. Every test is **NOT_RUN**. A test becomes PASS only when its listed evidence exists, matches the tested revision and configuration, and satisfies every expected result. Missing evidence is NOT_RUN or INCOMPLETE, never PASS.

The one-to-one mapping is DA-AT-NNN to DA-FR-NNN. Levels are `deterministic` (fixtures, replay or controlled fault injection without model inference), `real-native` (the actual selected Qwen, gateway, Fabro and MCP path), and `live` (an explicitly authorized Omniverse2 campaign or operational fault exercise). Real-native and live tests require a new bounded campaign under the existing authorization process. Historical exhausted orders, expenditures and attempts remain immutable; this document grants no runtime or promotion authority.

The historical v4 diagnosis ended without a submitted broker plan or valid compact reply. Its native stopping cause remains unresolved. Tests must not encode token exhaustion, context overflow, a tool-call limit, or any other unverified explanation as its expected cause. Published snapshots are evidence of observed state, not native execution-duration measurements.

Evidence must identify the requirement, case, tested source revision, effective model digest/profile where applicable, contract and oracle versions, authorization, timestamps, native run/job/nonce identities, outcome and immutable artifact hashes. Retain failed cases, retries, resource consumption and exclusions. Export redacted events, decisions and receipts; do not publish credentials, private vendor material or hidden model reasoning.

## DA-AT-001 — Historical provenance and native terminal evidence

- **Requirement:** DA-FR-001
- **Level:** deterministic (read-only reconstruction of recorded native evidence; no new inference)
- **Status:** NOT_RUN
- **Given:** Read-only copies of the five historical product receipts, four diagnosis records, deployed source identities, and all available native terminal events; original records have recorded hashes.
- **When:** Reconstruct the mission chronology and capture native start/end, terminal/stop reason, final-stage exit, usage and cancellation events without rewriting history. Exercise an explicit unavailable-event case.
- **Then:** Preserve original hashes and distinguish five unique product executions from 20 adopted attempt rows. Separate execution, package, order and service states. Record v4's cause as unresolved unless new native evidence establishes it; identify the evidence supporting any later conclusion.
- **Evidence:** Provenance manifest; before/after hashes; deduplicated native-ID ledger; redacted event export; unresolved-evidence inventory; reconstructed chronology.
- **Expected:** No mutated receipt, invented cause, duplicate execution count or latency inferred from polling intervals; every causal claim is supported or explicitly unresolved.

## DA-AT-002 — Complete typed finding inventory

- **Requirement:** DA-FR-002
- **Level:** deterministic
- **Status:** NOT_RUN
- **Given:** A sealed finding set containing decisive findings after character 300, after combined character 1,500, and across multiple page boundaries, with known IDs, types and artifact references.
- **When:** Build the diagnosis packet, enumerate every page, and retrieve each referenced finding; inject a missing or truncated backing artifact.
- **Then:** Every original finding remains identifiable and retrievable with its full relevant contents. Summary limits affect presentation only. Missing content produces explicit incompleteness and cannot be silently treated as a complete case.
- **Evidence:** Fixture manifest; packet and page hashes; retrieved-ID coverage comparison; missing-artifact diagnostics.
- **Expected:** 100% inventory coverage with no omitted or silently truncated decisive finding; incomplete cases are correctly classified.

## DA-AT-003 — Role and phase scoped retrieval

- **Requirement:** DA-FR-003
- **Level:** deterministic
- **Status:** NOT_RUN
- **Given:** Hash-bound artifacts assigned to distinct work orders, phases and roles, including downstream implementation unavailable to an upstream SWE.1 author, plus stale and substituted artifacts.
- **When:** Retrieve permitted evidence and attempt cross-order, cross-role, downstream-to-upstream, stale-hash and path-escape access through the actual retrieval boundary.
- **Then:** Return only evidence authorized for the caller's case, phase and role; verify bytes against the sealed hash. Reject unauthorized or changed content without exposing it.
- **Evidence:** Scope matrix; request/result audit; content-hash verification; negative-access receipts.
- **Expected:** All permitted references resolve correctly; every prohibited or hash-mismatched request is rejected; no downstream implementation leaks into upstream author context.

## DA-AT-004 — Measured prompt and coherent partitioning

- **Requirement:** DA-FR-004
- **Level:** real-native
- **Status:** NOT_RUN
- **Given:** Cases below, at and above the effective context allowance, including tool schemas, role instructions, evidence and required output capacity.
- **When:** Serialize and measure the complete request using the installed serving path, then assemble or partition the case by coherent obligations while reserving completion capacity.
- **Then:** Record measured input and applicable allowance before admission. Oversized cases are split with a coverage manifest or explicitly blocked; no evidence is silently dropped. Required cross-partition dependencies remain accessible and identified.
- **Evidence:** Redacted serialized-input manifest; token-measurement method and results; effective context settings; partition/dependency coverage; admission receipts.
- **Expected:** Every admitted request fits the qualified allowance and retains the required evidence and completion reserve; all overflow cases have explicit, complete disposition.

## DA-AT-005 — Bounded semantic proposal

- **Requirement:** DA-FR-005
- **Level:** real-native
- **Status:** NOT_RUN
- **Given:** Frozen recoverable, missing-evidence and legitimately blocked cases with a small proposal contract covering strategy, target obligation, causal hypothesis, evidence references, proposed change, predicted verification and impact scope.
- **When:** Qwen produces a proposal using the qualified local path, including negative cases with absent hypotheses, wrong semantic types, unsupported evidence and excessive field lengths.
- **Then:** Accept only well-formed semantic decisions supported by the case. Distinguish PROPOSE_REPAIR, NEEDS_EVIDENCE and CLOSE_BLOCKED; bound any correction exchange. Formatting alone does not establish a useful strategy.
- **Evidence:** Actual proposal schema; redacted proposals; independent semantic-validation results; correction counts and usage.
- **Expected:** Every accepted proposal satisfies its declared semantic outcome; malformed or unsupported proposals receive a truthful bounded failure or correction, never invented content.

## DA-AT-006 — Deterministic authoritative plan binding

- **Requirement:** DA-FR-006
- **Level:** deterministic
- **Status:** NOT_RUN
- **Given:** Valid and invalid semantic proposals, authoritative case/mission state, and the unchanged recovery-plan validator, scope, authority and budget rules.
- **When:** Bind schema version, IDs, hashes, authorization, fingerprints and budget fields from controller state, including spoofed administrative fields and a proposal differing only by label or random seed.
- **Then:** Administrative binding is deterministic. The existing authoritative validator independently checks the bound plan. The binder neither supplies a missing hypothesis/evidence nor coerces invalid semantic values or manufactures material difference.
- **Evidence:** Input/output fixtures; reproducible bound-plan hashes; authoritative validator receipts; semantic-field comparison; rejected spoof/material-difference cases.
- **Expected:** Identical authoritative inputs produce identical bound plans; unsupported semantic content and administrative spoofing are rejected without weakening the existing contract.

## DA-AT-007 — Actual model-visible protocol contract

- **Requirement:** DA-FR-007
- **Level:** real-native
- **Status:** NOT_RUN
- **Given:** The installed MCP SDK, gateway, Fabro adapter and selected Qwen configuration, with a registered proposal contract and its expected types, enums and bounds.
- **When:** Capture the schema actually exposed across each boundary and exercise valid, wrong-type, overlong, malformed and ambiguous-encoding requests. Where constrained generation is selected, exercise that exact adapter mode separately from MCP structured tool results.
- **Then:** Required contract information reaches the model-visible boundary. Runtime validation preserves strict types and limits. Unsupported adapter features are detected rather than assumed from upstream documentation.
- **Evidence:** Registered and transmitted schema hashes/diffs; effective adapter settings; actual native call/result receipts; negative-case results.
- **Expected:** All required schema properties survive transmission and are enforced; no source-only annotation is mistaken for a transmitted constraint; no unqualified generation mode is admitted.

## DA-AT-008 — Durable receipt and truthful completion

- **Requirement:** DA-FR-008
- **Level:** deterministic
- **Status:** NOT_RUN
- **Given:** Broker cases for accepted repair, accepted CLOSE_BLOCKED, rejected proposal, wrong-case proposal and no proposal; final model output can be prose, malformed, absent or a fabricated success claim.
- **When:** Persist the broker decision and interrupt processing before/after the response or compact completion write, then resume and reconcile.
- **Then:** A durable receipt bound to plan, case, job, nonce and contract determines semantic completion. Deterministic code creates the final artifact. Acceptance survives lost responses; prose does not undo it; a model success claim cannot substitute for a matching admissible receipt.
- **Evidence:** Transaction records; receipt/artifact hashes; interruption/recovery traces; case-binding validation.
- **Expected:** Every completion reflects the broker's actual semantic decision; no false accepted plan, fabricated repair success or permanently lost accepted submission.

## DA-AT-009 — Idempotency, fencing and outbox recovery

- **Requirement:** DA-FR-009
- **Level:** deterministic
- **Status:** NOT_RUN
- **Given:** An accepted plan, a transactional dispatch outbox, stable effect identities, and competing or restarted workers.
- **When:** Inject crashes before/after intent commit, native launch, receipt persistence and acknowledgement; replay deliveries; attempt execution from a worker with an expired fencing token.
- **Then:** Reconcile effects by stable identity before retrying. Stale workers cannot commit new effects. Durable intent eventually reaches its recorded outcome without duplicate implementation, verification publication or release effects.
- **Evidence:** Fault matrix; transaction/outbox history; fencing rejections; native effect identities; reconciliation receipts.
- **Expected:** Exactly one effective action per authorized effect identity, no lost committed intent and no successful stale-worker commit; uncertain external effects remain explicit until reconciled.

## DA-AT-010 — Separate limits and completion capacity

- **Requirement:** DA-FR-010
- **Level:** real-native
- **Status:** NOT_RUN
- **Given:** Explicit model-request, tool-call, token and wall-time allowances, including the maximum permitted evidence procedure and configured completion reserve.
- **When:** Exercise boundary cases through the actual policy hook: multiple tools in one model response, pagination, skill loading, rejected calls, and a proposal submitted at the reserved completion boundary.
- **Then:** Each limit is counted according to its documented unit; the controller does not label tool-call counts as model turns. Ordinary evidence reads cannot silently consume the reserved completion path. Exhaustion produces a typed outcome with counted/denied events.
- **Evidence:** Effective limit configuration; model-request/tool-call counters; policy decisions; reserve consumption; native terminal and usage receipts.
- **Expected:** The permitted worst-case evidence procedure can complete within the qualified bounds, or is rejected at admission with an explicit reason; no unexplained loss of submission capacity or conflated counters.

## DA-AT-011 — Shared mission accounting across continuations

- **Requirement:** DA-FR-011
- **Level:** deterministic
- **Status:** NOT_RUN
- **Given:** A mission lineage with historical product attempts, consumed diagnosis calls, reservations, an overrun and terminal continuation orders.
- **When:** Restart the controller, adopt history, create an authorized continuation and attempt duplicate imports or a replacement order with fresh-looking counters.
- **Then:** Resolve each order to the same durable mission ledger. Preserve historical identities and consumed capacity; count adopted executions once. Any new grant is explicit and traceable rather than an implicit reset.
- **Evidence:** Ledger before/after restart and continuation; lineage links; deduplication receipts; grant and admission history.
- **Expected:** No attempt, diagnosis-call or token reset; no double charge from receipt adoption; exhausted inherited allowances remain exhausted absent an explicit new authorized budget.

## DA-AT-012 — Request admission and conservative usage reconciliation

- **Requirement:** DA-FR-012
- **Level:** real-native
- **Status:** NOT_RUN
- **Given:** Shared remaining capacity, measured complete inputs and supported generation limits, with concurrent admission, delayed/missing usage and observed overshoot scenarios.
- **When:** Reserve capacity transactionally before each request, enforce supported generation bounds, reconcile reported usage and exercise adapter cancellation under a bounded qualification budget.
- **Then:** Distinguish input, cached input, output and unknown usage where observable. Missing usage retains the conservative reservation. Late usage/overshoot is charged and blocks later admission when needed; supported clamps are verified rather than equated with a perfect hard cap.
- **Evidence:** Request reservations/admission transactions; provider usage semantics; native usage events; cancellation latency and overshoot measurements; final ledger.
- **Expected:** No concurrent over-admission or released unknown usage; all measured consumption and overshoot reconciles; no polling threshold is misreported as a hard token guarantee.

## DA-AT-013 — Cancellation and late native adoption

- **Requirement:** DA-FR-013
- **Level:** real-native
- **Status:** NOT_RUN
- **Given:** Running and identity-uncertain native jobs, an inference lease, and cases where cancellation fails, times out, is accepted while work continues, or precedes late native run adoption.
- **When:** Revoke admission or expire the job, request cancellation, restart supervision and reconcile by stable nonce/run identity.
- **Then:** Separate terminal business outcome from execution liveness. Continue bounded reconciliation until quiescence or explicit unresolved state is established; preserve accounting and the occupied inference lease while execution may continue. A late run is adopted and cancelled under the original identity.
- **Evidence:** Revocation and cancel request/ack timestamps; native liveness observations; nonce/adoption history; lease and ledger transitions.
- **Expected:** No new inference admitted against the revoked authorization, no abandoned live job and no prematurely released lease/reservation; unresolved quiescence remains visible and blocks unsafe overlap.

## DA-AT-014 — Verifier dispatch and lease recovery

- **Requirement:** DA-FR-014
- **Level:** deterministic
- **Status:** NOT_RUN
- **Given:** A proposal awaiting independent verification with a durable dispatch intent, verifier identity, lease and heartbeat.
- **When:** Kill the controller before/after dispatch-state persistence and worker spawn; kill the verifier during execution; restart and deliver duplicate completion events.
- **Then:** Recover by adopting a demonstrably live worker or fencing and redispatching an expired one. A nonempty DISPATCHED field alone cannot suppress recovery. Publish at most one effective verification result for the proposal identity.
- **Evidence:** Dispatch/outbox transactions; worker lease/heartbeat history; crash points; adoption/redispatch decisions; result publication identities.
- **Expected:** No permanently stranded verification and no duplicate effective publication; every interrupted case reaches a truthful verified, failed or explicit blocked outcome.

## DA-AT-015 — Typed protocol incidents and bounded remedies

- **Requirement:** DA-FR-015
- **Level:** deterministic
- **Status:** NOT_RUN
- **Given:** Distinct failures for missing output, invalid contract, unavailable evidence, infrastructure outage, exhausted budget and a semantically admissible CLOSE_BLOCKED decision.
- **When:** Process each failure through recovery and attempt approved remedy selection, including repeat incidents and an unsupported remedy.
- **Then:** Emit the correct typed incident and preserve its evidence. Select only a policy-approved operational remedy or permitted isolated candidate lane, bounded by lineage budgets and anti-loop rules. A protocol failure does not assert that useful engineering strategies are absent.
- **Evidence:** Incident classification table; remedy-policy decisions; retry/anti-loop counters; final order and incident records.
- **Expected:** Correct distinct classifications, no disguised CLOSE_BLOCKED success, no blind retry or unauthorized remedy, and explicit termination when the remedy allowance is exhausted.

## DA-AT-016 — Model-free operational recovery

- **Requirement:** DA-FR-016
- **Level:** live
- **Status:** NOT_RUN
- **Given:** An authorized fault campaign and qualified restart, stale-lease reconciliation, model reload and rollback recipes; the watchdog and last-known-good bootstrap are independent of the failed model service.
- **When:** Inject approved gateway/model/service failures, then exercise a failed recovery and unavailable-prerequisite case.
- **Then:** Detect and execute applicable recipes without asking Qwen to repair its unavailable serving process. Preserve the ledger and evidence, bound restart attempts, verify recovery health and block explicitly when prerequisites or rollback are unavailable.
- **Evidence:** Fault schedule; watchdog/recipe events; model-request counter; health and quiescence checks; recovery timings; failed-recipe disposition.
- **Expected:** Zero model calls required for the operational recipes; observed recovery or explicit bounded dependency block for every fault; no uncontrolled restart loop, history loss or unverified rollback success.

## DA-AT-017 — Isolation and resource admission

- **Requirement:** DA-FR-017
- **Level:** live
- **Status:** NOT_RUN
- **Given:** The qualified Omniverse2 resource and isolation profile, an inference lease, bounded verification workers and a download-only side job where explicitly authorized.
- **When:** Submit concurrent work, exceed CPU/memory/disk/thermal prerequisites, test sandbox access boundaries and external inference routing, and introduce download contention under approved limits.
- **Then:** Admit only permitted local inference and verification workloads. Enforce the selected model identity, role filesystem/tool scope and resource limits; queue, throttle or explicitly block according to policy. Download authorization cannot authorize inference or inspector promotion.
- **Evidence:** Admission/queue receipts; effective sandbox/model/profile hashes; blocked-access and routing checks; resource traces; download throttling decisions.
- **Expected:** No competing unauthorized inference, external fallback or isolation escape; bounded verification and explicit pressure outcomes; no silently admitted workload exceeding qualified prerequisites.

## DA-AT-018 — Private telemetry and truthful progress

- **Requirement:** DA-FR-018
- **Level:** real-native
- **Status:** NOT_RUN
- **Given:** Runs with useful engineering progress, healthy idle supervision, stalled inference, failed diagnosis, unknown usage and stale side-job status.
- **When:** Collect redacted events and render status from heartbeat, execution liveness, stage transitions, evidence coverage, accepted plans, independent defect closure and resource measurements.
- **Then:** Report these dimensions separately with observation timestamps and defined denominators. An idle heartbeat cannot imply engineering progress; a polling interval cannot imply inference duration; stale download state cannot imply active transfer. Exclude hidden reasoning, secrets and restricted source material.
- **Evidence:** Telemetry schema; redacted event/status exports; fixture-to-dashboard assertions; privacy scan; stage timing and freshness records.
- **Expected:** Every displayed claim is supported by the appropriate fresh evidence; no false progress, latency or usage claim and no prohibited data disclosure.

## DA-AT-019 — Counterexample-guided product repair

- **Requirement:** DA-FR-019
- **Level:** real-native
- **Status:** NOT_RUN
- **Given:** A sealed product case with a classified root defect, a smallest meaningful failing counterexample/test, authoritative evidence and an explicit dependency/impact set.
- **When:** Qwen proposes a materially different scoped repair, the authorized implementation executes, and an independent verifier evaluates the defect and impacted obligations.
- **Then:** Preserve the baseline failure and changed artifacts. Feed back concrete remaining defects within bounds. Claim repair only for independently closed obligations; retain failed attempts and regressions rather than selecting only a passing run.
- **Evidence:** Baseline counterexample; proposal/receipt; patch and artifact hashes; impact manifest; independent before/after checks; attempt and resource ledger.
- **Expected:** A real implementation is dispatched and at least the target root defect is independently closed without regressing required impacted obligations; formatting a plan alone does not pass.

## DA-AT-020 — Brownfield provenance and phase validity

- **Requirement:** DA-FR-020
- **Level:** deterministic
- **Status:** NOT_RUN
- **Given:** Historical artifacts with valid same-identity resume evidence, missing resume identity, changed factory revision, changed authoritative inputs and stale phase acceptance.
- **When:** Attempt reuse or recovery from each case, including the legacy factory revision with no validated resume identity.
- **Then:** Reuse content or accepted state only where the existing provenance/resume rules permit. Where a fresh cross-revision execution is required, regenerate and independently revalidate every phase; imported receipts do not import old passes or fabricate a new execution.
- **Evidence:** Provenance/resume validation receipts; input/revision hashes; reuse decisions; fresh-phase execution manifest; rejected copied-baseline cases.
- **Expected:** Every reused artifact/state has valid authority and identity; every required fresh phase is executed and verified; no inherited PASS based solely on historical adoption.

## DA-AT-021 — Independent verification and unchanged release gates

- **Requirement:** DA-FR-021
- **Level:** real-native
- **Status:** NOT_RUN
- **Given:** Separate author and inspector roles, immutable gate/oracle definitions, seeded critical defects and valid controls, including cases where author output falsely asserts success.
- **When:** Run the actual repair and inspection path and attempt author modification of acceptance evidence, oracle definitions or inspector verdicts.
- **Then:** The author cannot approve its own repair or change the oracle. Independently evaluate applicable gates and preserve exact verdicts. Deterministic checks and semantic inspector results are distinguishable; a second session of the same model is not assumed to have independent errors.
- **Evidence:** Role/access configuration; seeded-case manifest; independent verdicts; rejected modification attempts; oracle and gate hashes; false-accept/reject counts.
- **Expected:** Every seeded critical defect is detected in this qualification set, no author-forged acceptance is effective, and no existing gate is weakened or bypassed.

## DA-AT-022 — Isolated maintainer and external promotion boundary

- **Requirement:** DA-FR-022
- **Level:** deterministic
- **Status:** NOT_RUN
- **Given:** The current maintainer allowlist and AFO-FR-053 authority boundary, an allowed candidate patch, forbidden AFO/CRE/skill/policy edits and a candidate eligible for offline review.
- **When:** Execute candidate preparation/qualification in isolation and attempt forbidden edits, automatic merge, production source activation and use of eligibility as deployment authority.
- **Then:** Permit only the existing allowed candidate operations; reject protected-scope changes. Preserve the independent reproducer/evaluation evidence and stage qualified proposals for external promotion. Neither ELIGIBLE nor this feature grants automatic persistent source deployment.
- **Evidence:** Scope/authority decisions; isolated candidate diff; baseline/candidate evaluation; staging receipt; denied deployment attempts; unchanged production hashes.
- **Expected:** No protected edit or automatic persistent promotion under current policy; an allowed passing candidate remains a reviewable proposal with complete evidence.

## DA-AT-023 — Verified lessons and invalidation

- **Requirement:** DA-FR-023
- **Level:** deterministic
- **Status:** NOT_RUN
- **Given:** Repair lessons with provenance, failure class, component versions, applicability checks, verified outcomes, negative results and explicit invalidation conditions.
- **When:** Retrieve lessons for matching and mismatching cases, change a relevant version/oracle, invalidate a lesson and attempt retrieval from the final held-out acceptance set.
- **Then:** Apply lessons only when their conditions hold. Preserve negative history and record why a lesson was selected or rejected. Invalidation prevents further automatic reuse; final holdout evidence cannot become tuning/training material.
- **Evidence:** Lesson records and hashes; matching/invalidation decisions; version-change tests; holdout separation/access audit.
- **Expected:** No stale, unverified or inapplicable recipe is automatically reused; all lesson decisions are traceable; final holdout remains isolated from improvement data.

## DA-AT-024 — Repeated real protocol qualification

- **Requirement:** DA-FR-024
- **Level:** real-native
- **Status:** NOT_RUN
- **Given:** Twenty frozen mixed protocol cases, each repeated five times through the actual selected Qwen/gateway/Fabro/MCP path, with expected outcome classes, designated recoverable cases, legitimate blocks and negative cases fixed before execution.
- **When:** Execute all 100 trials under the bounded campaign and retain every terminal outcome, invalid proposal, retry and cost; do not replace failures with additional favorable trials.
- **Then:** Every trial reaches its correct observable outcome. Every designated recoverable trial must produce an independently admissible plan; blanket CLOSE_BLOCKED responses fail. Distinguish valid blocking from repair success and report useful-plan rate separately.
- **Evidence:** Frozen case/oracle manifest; 100 native run identities and complete results; expected/observed matrix; plan receipts; cost/retry ledger.
- **Expected:** 100/100 correctly classified terminal outcomes; every designated recoverable trial reaches an admissible plan; zero false success, duplicate dispatch or authority escape. This pilot is not proof of 99% production reliability.

## DA-AT-025 — Genuine RCC acceptance and GPIO release conditions

- **Requirement:** DA-FR-025
- **Level:** live
- **Status:** NOT_RUN
- **Given:** A new authorized RCC implementation attempt and separate GPIO prerequisites: genuine RCC acceptance, qualified peripheral profile, authoritative GPIO inputs and frozen intake.
- **When:** Run RCC through all independent SWE gates and verify its sealed package/archive; exercise GPIO dispatch with each prerequisite absent and with all prerequisites satisfied within explicit authorization.
- **Then:** RCC succeeds only when SWE.1–SWE.6 all PASS and the native sealed READY manifest/archive hash is valid. Fabro success, healthy service state or exhaustion is insufficient. GPIO remains blocked until every prerequisite and its own admission authority are present.
- **Evidence:** Six native gate verdicts; sealed manifest/archive verification; RCC receipt; GPIO prerequisite matrix; blocked/admitted dispatch receipts.
- **Expected:** Genuine RCC READY_FOR_OFFLINE_REVIEW with intact native archive; zero premature or substituted GPIO launches; authorized GPIO dispatch only in the fully qualified case.

## DA-AT-026 — Authorized unattended fault soak

- **Requirement:** DA-FR-026
- **Level:** live
- **Status:** NOT_RUN
- **Given:** A declared operating envelope, bounded authorized real work, approved fault schedule, recovery/rollback recipes and preserved mission ledger.
- **When:** Complete a 24-hour smoke, then 72-hour pilot, then 168-hour unattended soak, injecting declared service/gateway, lease, restart/reboot and resource faults and testing restore paths within authorization.
- **Then:** Measure actual fault exposure, admitted work, recovery times, interventions and product outcomes. Required in-envelope recovery proceeds without an operator; out-of-envelope dependencies are explicit blocks. Idle observation alone cannot satisfy the work/fault campaign.
- **Evidence:** Campaign authorization and envelope; continuous event/ledger exports; fault and recovery receipts; admitted-work outcomes; restore results; intervention register; complete duration evidence.
- **Expected:** All three campaigns complete their declared workload/fault coverage with zero operator interventions for eligible in-envelope recovery, zero false READY and no lost/duplicated effects or ledger resets; any qualifying failure fails that stage.

## DA-AT-027 — Existing end-to-end quality and efficiency benchmark

- **Requirement:** DA-FR-027
- **Level:** live
- **Status:** NOT_RUN
- **Given:** A frozen representative 30-trial Omniverse2 cohort preserving Feature 010 quality criteria, seeded critical defects, a comparable frozen prompt baseline, and predeclared structured-response and cost denominators.
- **When:** Execute the complete local pipeline, retaining all failures and retries, independently verify packages and defect detection, and compare full prompt input against the baseline without dropping required evidence.
- **Then:** Report READY yield, honest BLOCKED outcomes, critical-defect detection, false READY, invalid structured responses and median prompt input with cohort/configuration identities. Deterministic and semantic inspection metrics remain separate.
- **Evidence:** Frozen cohort/baseline/oracle manifests; all native run/package receipts; defect-detection matrix; structured-response numerator/denominator; full-input measurements; evidence-coverage comparison.
- **Expected:** At least 27/30 trials reach verified READY_FOR_OFFLINE_REVIEW; every seeded critical defect is caught; no known false READY; other outcomes are honest BLOCKED; invalid structured responses are below 1%; median prompt input falls at least 50% versus the comparable baseline without required-evidence loss.

## DA-AT-028 — Controlled model and configuration comparisons

- **Requirement:** DA-FR-028
- **Level:** real-native
- **Status:** NOT_RUN
- **Given:** Qualified deterministic evidence/contract/completion/accounting fixes and a measured, unchanged selected-model baseline; separately authorized candidate model/context/quantization configurations and frozen development/validation cases.
- **When:** Compare one declared factor at a time while keeping prompts, oracles, workload, admission and measurement rules comparable; include unsuccessful plans and attempts in cost and outcome denominators.
- **Then:** Measure useful plans, independently closed defects, false acceptance/rejection, latency and tokens per accepted work order. Record compatibility and effective settings. Do not attribute the historical v4 failure to model size/context without evidence, and do not treat a download as inference qualification.
- **Evidence:** Baseline qualification and results; experiment preregistration; model/profile hashes; complete native results and costs; independent comparison report.
- **Expected:** Each recommendation follows measured comparable evidence with unchanged quality gates. Genuine RCC success is not a prerequisite to beginning these bounded comparisons once deterministic fixes and the measured baseline are qualified.

## DA-AT-029 — Legacy regression and compatibility

- **Requirement:** DA-FR-029
- **Level:** deterministic
- **Status:** NOT_RUN
- **Given:** The repository's required regression suites, legacy product workspace behavior, persisted pre-feature records and supported recovery-plan encodings.
- **When:** Run relevant existing suites plus compatibility cases for old state adoption, product role defaults, authoritative plan validation, scope/authority enforcement and ambiguous legacy/new encodings.
- **Then:** Preserve existing supported behavior and negative protections. New diagnosis-role scoping does not alter unrelated product defaults. Reject ambiguous encodings; do not reinterpret old success receipts as verified product acceptance.
- **Evidence:** Exact tested revision; command/environment log; complete test reports including skips; compatibility fixture hashes; old/new validation comparisons.
- **Expected:** All required relevant regressions and compatibility cases pass; skips retain their actual reasons and cannot stand in for live qualification; no weakened validator, changed legacy semantics or accidental product-context regression.

## DA-AT-030 — Readiness evidence and future-policy separation

- **Requirement:** DA-FR-030
- **Level:** deterministic
- **Status:** NOT_RUN
- **Given:** The implementation candidate, all test statuses and evidence manifests, unresolved native evidence, the current promotion policy and any proposed future automatic-worker-promotion amendment.
- **When:** Assemble the readiness/handoff report and independently reconcile claims against evidence, including NOT_RUN tests, failures, external dependencies and unauthorized/unqualified future capabilities.
- **Then:** Publish an accurate requirement-to-test-to-evidence mapping, effective versions, bounded operating envelope, residual risks, restore/runbook instructions and external promotion needs. Label future-policy proposals as unapproved designs; current eligibility never activates source automatically.
- **Evidence:** Readiness report; traceability matrix; artifact-hash manifest; unresolved/NOT_RUN register; operating/recovery runbook; independent review; policy-diff proposal if present.
- **Expected:** No unsupported autonomous-repair/readiness claim and no automatic source promotion; every readiness claim is backed by applicable completed evidence, while unexecuted runtime tests remain explicitly NOT_RUN and future authority remains separate.

## DA-AT-031 — Measured Qwen capability by role

- **Requirement:** DA-FR-031
- **Level:** real-native
- **Status:** NOT_RUN
- **Given:** Frozen representative and negative cases for each proposed role, including planning, scoped implementation and inspection; the actual Qwen digest, quantization, reasoning settings, gateway/adapter, tool contract and context configuration are pinned.
- **When:** Qualify each role through its actual native path, using independent expected outcomes and complete failure/cost denominators. Change one configuration identity to exercise invalidation of the prior qualification.
- **Then:** Record supported task classes, observed failure modes, bounded task/context sizes, useful-output rate, verification coverage and unsupported judgments for each role. A role's results cannot qualify arbitrary engineering tasks, another role or the model's ability to judge its own correctness. A changed configuration requires applicable requalification.
- **Evidence:** Role/case matrix; effective configuration hashes; native results and usage; independent verdicts; per-role capability profile; configuration-invalidation receipts.
- **Expected:** Every admitted role/task is covered by a current measured capability profile; unsupported tasks and changed unqualified configurations are explicitly rejected or routed to an authorized qualification process, with no assumed general competence or self-verification authority.

## DA-AT-032 — Short-horizon work with global obligation coverage

- **Requirement:** DA-FR-032
- **Level:** real-native
- **Status:** NOT_RUN
- **Given:** A product task exceeding a role's measured reliable horizon, with a complete obligation/dependency graph and smaller independently verifiable units, all under one mission's original shared budget.
- **When:** Decompose the task by meaningful obligations, execute bounded units in dependency order, and inject an omitted obligation, an incompatible interface and a locally passing change that violates a global constraint.
- **Then:** Diagnose excessive task scope and partition it instead of forcing a giant prompt. Carry global constraints and required dependencies into each unit; reconcile coverage and integration independently before accepting the assembled result. Partitioning neither creates extra budget nor imports unverified local passes as global acceptance.
- **Evidence:** Original obligation inventory; decomposition/dependency manifest; per-unit cases and native receipts; global coverage/integration checks; shared budget ledger; negative-case verdicts.
- **Expected:** Every required obligation is covered, dependency/interface violations are detected and all work respects the original allowance; locally correct fragments cannot produce a false global PASS, and tasks without a sound bounded decomposition remain explicitly blocked.

## DA-AT-033 — Evidence-indexed memory and effective context limits

- **Requirement:** DA-FR-033
- **Level:** real-native
- **Status:** NOT_RUN
- **Given:** A multi-step case whose full history exceeds the measured effective context envelope, compact checkpoints referencing complete mandatory evidence, and verified lesson records; inject stale, misleading and wrong-version memory plus a missing evidence reference.
- **When:** Resume from checkpoints, retrieve evidence by sealed identity, validate lesson applicability and test context sizes against observed task reliability rather than only the configured window size.
- **Then:** Keep required source evidence retrievable without loss; a checkpoint summary is an index, not replacement authority. Compare memory against authoritative artifacts and invalidate stale or unsupported lessons. Missing mandatory evidence prevents a fabricated conclusion. Record the empirically qualified context envelope separately from configured capacity.
- **Evidence:** Checkpoint/evidence hash manifests; mandatory-evidence retrieval coverage; memory selection/invalidation receipts; native context-size trials and independent verdicts; missing-reference disposition.
- **Expected:** No required evidence is silently lost or replaced by an inaccurate summary; all injected stale/misleading memory is rejected or corrected from authoritative evidence; requests stay within a qualified effective envelope or receive explicit partition/block outcomes.

## DA-AT-034 — Bounded candidate search and verifier-directed stopping

- **Requirement:** DA-FR-034
- **Level:** real-native
- **Status:** NOT_RUN
- **Given:** A repair case permitting several substantively distinct engineering hypotheses, a predeclared search allowance inside the original mission budget, one admitted inference request at a time, and independent deterministic checks with explicit ranking and stopping rules.
- **When:** Generate and verify bounded candidates, including equivalent patches with changed labels/seeds, a confident invalid proposal, a repeated failing hypothesis and candidates that cease making measurable progress.
- **Then:** Count every candidate and its cost. Distinguish hypotheses by causal approach and predicted effect; do not count label changes as new strategies. Rank by independent verification and actual obligation progress, not model confidence or majority vote. Stop on acceptance, exhausted allowance, repeated failure or the declared stall condition.
- **Evidence:** Candidate/hypothesis manifest; native inference-lease trace; independent verifier results; ranking/progress history; rejection/stopping receipts; complete shared budget ledger.
- **Expected:** Search stays within the original allowance and single-inference admission; no unverified winner or concealed retry; equivalent/stalled candidates terminate according to the declared rule, and any selected candidate satisfies its independent acceptance criteria.

## DA-AT-035 — Inspector correlated-error qualification

- **Requirement:** DA-FR-035
- **Level:** real-native
- **Status:** NOT_RUN
- **Given:** Independently maintained hidden mutants, metamorphic relations and reference checks covering the inspector's claimed properties, plus semantically plausible defects and a property lacking an adequate independent oracle.
- **When:** Evaluate the actual author/inspector configuration, including separate sessions or roles of the same Qwen, against those controls and classify deterministic checks, semantic judgments, false acceptance and false rejection separately.
- **Then:** Measure shared misses and limitations instead of treating role separation as proof of independent error behavior. Keep the author unable to change the controls. Where a required semantic property lacks adequate qualified verification, record the unsupported property and block the relevant acceptance claim.
- **Evidence:** Protected mutant/metamorphic/reference manifests; paired author/inspector results; independent oracle verdicts; shared-miss and false-accept/reject report; unsupported-property block receipt.
- **Expected:** All seeded critical defects in the declared qualification set are caught, reference/metamorphic violations cannot receive acceptance, and unsupported required properties block release; no claim of statistical independence follows solely from separate same-model sessions or passing this finite suite.

## DA-AT-036 — Capability-ceiling disposition without uncontrolled escalation

- **Requirement:** DA-FR-036
- **Level:** real-native
- **Status:** NOT_RUN
- **Given:** Cases beyond a qualified role's capability, cases missing authoritative evidence, an allowed repartition, and both qualified-authorized and unqualified/unauthorized local adapter/model alternatives; the current budget and authority remain fixed.
- **When:** Detect the limit, evaluate permitted alternatives and exercise repeated-limit outcomes, depleted budget and unavailable local alternatives.
- **Then:** Repartition only where coverage remains sound, or select a qualified local alternative only within current authorization and remaining capacity. Otherwise emit typed CAPABILITY_LIMIT or MISSING_EVIDENCE with supporting observations and preserved history. Do not substitute missing facts with guessed content or relabel the same failed strategy as progress.
- **Evidence:** Capability/admission decisions; repartition coverage; alternative configuration qualification/authorization checks; inference-route audit; final typed outcomes; unchanged budget, model-weight and authority records.
- **Expected:** Every limit case receives a justified bounded remedy or explicit block; no endless retries, cloud fallback, autonomous weight training, automatic budget increase or unqualified model/adapter activation occurs.

## DA-AT-037 — Factual experience from every execution

- **Requirement:** DA-FR-037
- **Level:** deterministic
- **Status:** NOT_RUN
- **Given:** Jobs and phase outcomes across multiple drivers and features, including success, failure, BLOCKED, cancellation and interrupted execution; original archives and execution identities are immutable.
- **When:** Capture factual experience on each outcome, interrupt capture before/after persistence, replay terminal events and adopt the same native execution through another order.
- **Then:** Link experience to stable execution, phase, driver, feature, source revision and evidence identities. Reconcile interrupted capture and deduplicate replay/adoption without hiding distinct phase outcomes. Preserve actual observations, unknowns and costs; capture does not itself assert a lesson, root cause or successful remedy.
- **Evidence:** Expected-execution/outcome inventory; experience records and source hashes; crash/replay reconciliation traces; deduplication results; unchanged original archive hashes.
- **Expected:** Every executed job and phase outcome has a factual, traceable experience record or an explicit recoverable capture-pending state that reconciles after restart; no duplicated execution, fabricated inference or mutation of original evidence.

## DA-AT-038 — Bounded asynchronous learning disposition

- **Requirement:** DA-FR-038
- **Level:** deterministic
- **Status:** NOT_RUN
- **Given:** A durable queue of captured experiences, bounded consolidation capacity, shared mission budgets and cases with no novel lesson, unavailable consolidation capacity or unavailable model allowance.
- **When:** Consolidate asynchronously, restart before/after candidate/disposition persistence, replay queue messages and continue normal admitted jobs while consolidation is deferred.
- **Then:** Record a durable learning disposition for every job, including candidate created, no new lesson or deferred with a reason and reconciliation identity. Consolidation cannot block the controller indefinitely, force a lesson from every run, mint fresh budget or invoke Qwen merely because the machine is healthy and idle.
- **Evidence:** Queue/disposition ledger; idempotency and restart traces; bounded scheduling/admission results; mission accounting; model-request counts during idle and exhausted-budget cases.
- **Expected:** All jobs retain a truthful durable disposition; repeated processing creates no duplicate effective candidate; denied/deferred consolidation preserves work and budget. Healthy-idle monitoring makes zero model calls; separately admitted, budgeted learning work is accounted as work rather than idle monitoring.

## DA-AT-039 — Extend the existing knowledge path compatibly

- **Requirement:** DA-FR-039
- **Level:** deterministic
- **Status:** NOT_RUN
- **Given:** Existing LessonStore records, forge-knowledge-mcp operations and deterministic curator checks, including valid and invalid legacy PROMOTED repair lessons; proposed versioned source kinds for ordinary success and verified negative observations.
- **When:** Migrate/read legacy records and submit each source kind through the extended existing store, MCP contract and curator, including unknown versions, unverifiable sources and attempts to bypass legacy repair promotion.
- **Then:** Validate each explicit version/source kind under its own qualified evidence contract. Preserve existing PROMOTED-and-tests-PASS requirements for legacy repair lessons. Ordinary success or negative observation requires genuine source evidence, not a fabricated incident/repair identity. No parallel knowledge engine becomes a competing authority.
- **Evidence:** Versioned schema/operation contracts; migration and compatibility fixtures; legacy/new curator verdicts; source resolution receipts; knowledge-path architecture and storage audit.
- **Expected:** Existing valid repair lessons remain valid and existing invalid repairs remain rejected; new source kinds use the same controlled lifecycle without fake incident records, unknown-version acceptance or a weakened legacy validation path.

## DA-AT-040 — Applicable lessons before the next job or phase

- **Requirement:** DA-FR-040
- **Level:** real-native
- **Status:** NOT_RUN
- **Given:** Validated and unvalidated lessons spanning different MCUs, tool/source versions, phases, roles and repair scopes; a pending next job/phase; author judgments and separately qualified inspection lessons; primary evidence with a deliberately missing required source.
- **When:** Retrieve through the existing knowledge path before context assembly, enforce its bounded top-K and configured token allowances, then measure the complete serialized reference block including provenance and wrappers against its admission cap. Resolve the authorized stored artifact or assemble the full bounded lesson into the packet; include a decisive exclusion/warning after character 120 and a lesson that cannot fit completely.
- **Then:** Apply MCU/version/phase/role/scope filters and return only applicable validated references, with top-K no greater than three. Deliver the complete bounded statement/remedy, constraints, exclusions and provenance to the consuming role; the warning after character 120 remains visible. Explicitly omit/defer an unfit lesson instead of supplying a misleading partial remedy. Preserve primary evidence priority; missing authoritative input remains missing. Do not inject retrieved author judgments into inspector context or let ordinary lessons bypass inspection-lesson qualification. An empty applicable result is valid.
- **Evidence:** Retrieval/filter matrix; selected lesson IDs/versions/hashes and consumer records; actual serialized token measurements; context manifests; rejected cross-scope/role cases; missing-primary-source outcome.
- **Expected:** Every admitted reference is applicable, validated and within both retrieval and measured serialization budgets; no author-to-inspector judgment leakage, missing-source substitution or assumption that character estimates alone prove token compliance.

## DA-AT-041 — Independent lesson qualification by claim and scope

- **Requirement:** DA-FR-041
- **Level:** real-native
- **Status:** NOT_RUN
- **Given:** Candidates derived from a successful run, a verified failure/limit, a promoted repair and a coincidental success pattern, each with explicit scope and claim; independent positive and negative cases; the separate IL inspection-lesson promotion rules.
- **When:** Qualify each candidate's actual claim using source verification and scoped positive/negative checks, including counterexamples to an overgeneralized success and an attempt to describe a failed remedy as successful.
- **Then:** Distinguish a reproducible useful lesson from mere correlation. A failure may support a bounded observed limitation without proving a remedy or universal incapability. The candidate author cannot self-validate. Ordinary LessonStore validation cannot confer IL promotion; generic inspection lessons retain their separate source, paired-defect and CRE requirements.
- **Evidence:** Candidate claim/scope/source manifests; independent positive/negative results; rejected overclaims; curator decisions; separate IL qualification/promotion receipts where applicable.
- **Expected:** Only independently supported scoped claims become validated lessons; correlated or unsupported remedies are quarantined/rejected, verified negative observations remain accurately labeled, and no ordinary success lesson bypasses the protected inspection-lesson path.

## DA-AT-042 — Measured lesson use and benefit

- **Requirement:** DA-FR-042
- **Level:** real-native
- **Status:** NOT_RUN
- **Given:** Per-lesson usage identities and frozen comparable replay or validation cohorts with predeclared configurations, independent oracles and with/without-lesson conditions; final acceptance holdouts are separately protected.
- **When:** Evaluate lesson impact within authorized budgets, retaining every run, failure, retry and the costs of capture, consolidation, retrieval, generation and verification.
- **Then:** Measure quality, false READY, critical-defect detection, first-pass yield, recurrent findings and total cost with explicit denominators. Prioritize quality constraints over efficiency gains. Record demonstrated benefit, no measured benefit, regression or insufficient evidence without promising improvement on every job; do not tune on final holdout outcomes.
- **Evidence:** Lesson-to-consumer usage ledger; frozen cohort/configuration/oracle manifests; comparative results and uncertainty limits; complete cost ledger; final-holdout access/separation audit.
- **Expected:** Every benefit claim has a comparable independent measurement; no false READY or missed critical defect is excused by lower cost, no unfavorable result is omitted, and no per-job improvement guarantee or final-holdout contamination is introduced.

## DA-AT-043 — Scoped deduplication and durable invalidation

- **Requirement:** DA-FR-043
- **Level:** deterministic
- **Status:** NOT_RUN
- **Given:** Duplicate lessons with the same scoped source identity, similar wording describing distinct MCU facts, conflicting candidates, expired/retracted lessons and tool/source-version changes affecting previously consumed lessons.
- **When:** Deduplicate, validate conflicts, invalidate stale applicability and retract affected lessons, including restart/replay during lifecycle transitions and retrieval concurrent with invalidation.
- **Then:** Use scope and source hashes in identity decisions; do not collapse different MCU/version facts merely because symptoms/remedy text matches. Exclude invalid, conflicting-unresolved, expired or retracted content from subsequent retrieval. Persist previous lifecycle history and identify affected consumer runs for follow-up without rewriting their original results.
- **Evidence:** Scoped identity/dedup matrix; conflict and invalidation decisions; before/after retrieval results; durable lifecycle history; affected-consumer list; restart/race traces.
- **Expected:** True duplicates create no duplicate effective lesson, distinct scoped facts remain distinct, invalidation prevents later retrieval, and prior history plus affected consumers survive restart without silently changing past execution verdicts.

## DA-AT-044 — Integrate measured learning with CAPA, CRE and maintainer work

- **Requirement:** DA-FR-044
- **Level:** deterministic
- **Status:** NOT_RUN
- **Given:** Measured recurring issues, verified success patterns and lesson-impact records, together with existing CAPA/CRE and maintainer workflows, current edit allowlists and external promotion authority.
- **When:** Aggregate evidence into deduplicated improvement hypotheses and route eligible candidates through those existing workflows; attempt protected-scope edits or automatic production promotion, and generate readiness metrics from mixed successful/failed learning outcomes.
- **Then:** Preserve hypothesis-to-experience/lesson evidence links and apply the correct existing evaluation lane: defect repairs retain baseline-failing reproducers/CAPA; success-derived optimizations use measured-baseline CHANGE evaluation and external engineering when outside the maintainer grant, without fabricated incidents. Preserve independent evaluation and promotion rules. A pattern alone is not a proven cause or authorized deployment. Report experience coverage, qualified lessons, demonstrated benefits and improvement candidates as distinct metrics, separate from product gate success and operational readiness.
- **Evidence:** Experience/lesson-to-CAPA/CRE/proposal traceability; workflow and allowlist decisions; candidate evaluation; denied promotion receipts; metric definitions, denominators and readiness reconciliation.
- **Expected:** Learning feeds the existing improvement system without a parallel promotion authority; no protected edit or automatic source activation occurs, and captured experience, validated lessons or staged candidates cannot falsely satisfy product PASS or readiness gates.
