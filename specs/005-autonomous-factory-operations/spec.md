# Feature Specification: 005 — Autonomous Factory Operations (AFO)

**Feature branch:** `feat/005-autonomous-factory-operations`  
**Created:** 2026-10-17  
**Status:** PROPOSED — SPECIFICATION ONLY; no feature-005 runtime is claimed implemented  
**Baseline:** `feat/004-continuous-reliability-engineering` at `c03c0da9e771eddfdfb24b02d8ec336dfa847dfa` (audit actual HEAD before implementation)  
**Product:** Forge-C — autonomous embedded C HAL/LLD engineering, SWE.1–SWE.6, independent inspections, ASIL B-oriented evidence for *offline* human review  
**Implementation engineer:** Claude Code using existing GitHub Spec Kit; **runtime:** existing Fabro 0.362, locally hosted Qwen/Ollama by default, existing MCP and CRE.

## 1. Problem and measurable objective

The existing Forge-C can run unattended until it produces a deterministic `READY_FOR_OFFLINE_REVIEW` or `BLOCKED` archive. However, a BLOCKED SWE stage commonly requires the owner to prompt Claude to diagnose the factory defect, implement another patch, and start another attempt. The independent supervisor handles *infrastructure incidents*; CRE observes recurring failures but is `OBSERVE_ONLY`. `scripts/forge_services.sh` starts services with `nohup`; work-order submission is primarily a one-shot CLI; Fabro-native crash resume has not been proven. The historical local Qwen E2E assessment marked a **valid BLOCKED package** as E2E `PASS`; that must never be represented as production-success yield.

**Outcome:** Run a continuously available on-premise factory that accepts *pre-approved* work orders, schedules them from a durable queue, autonomously triages recoverable SWE failures, chooses a *materially different* bounded next strategy, resumes at safe baseline checkpoints, and finishes with valid evidence. Separately, propose fixes to Forge-C itself in isolated candidate branches, validate them with existing CRE independent gates, and present proposals for *external change control*. Run without new operator prompts for routine, pre-authorized actions. After exhausting available safe paths, finish `BLOCKED`, preserve evidence, place a support case in a dead-letter queue, and continue with unrelated jobs.

**Autonomy ≠ guaranteed success.** No engineering system can guarantee solution of arbitrary failures, 100% availability, or 100% product correctness. 24/7 means continuously managed services and queue processing when there is approved work, with safe, bounded failure handling and no silent success claims. Idle with an empty queue is healthy.

## 2. User Scenarios and independent acceptance

### US-01 (P0): Headless 24/7 control plane

As the factory owner, I want Ollama, gateway, Fabro, dashboard, Conductor and the existing supervisor to start after boot without interactive login, recover after process crashes, and preserve data on a stable persistent mount. Given a system reboot while a work order runs, when services restart, then the Conductor reconciles the existing work order and Fabro run without duplicating non-idempotent effects. **Test:** AT-001..AT-009, AT-046.

### US-02 (P0): Durable intake and continuous scheduling

As an owner, I submit an immutable approved input manifest once; the Conductor queues it and runs the work order automatically when capacity and dependencies are ready. Given two requests with one worker slot, the second remains QUEUED and is admitted fairly after the first; duplicate submission returns the original order ID rather than launching an extra work order. **Test:** AT-010..AT-016.

### US-03 (P0): Promptless recovery from transient failures

Given a model-gateway timeout, Fabro crash, or unavailable MCP tool, the Conductor uses existing CRE breaker/admission rules, restarts eligible services, reconciles side effects and retries replayable operations only. Budget exhaustion transitions to a stable exception state, not an infinite loop. **Test:** AT-017..AT-025.

### US-04 (P0): Autonomous SWE recovery and replanning

Given a deterministic SWE.1–SWE.6 gate failure or inspector finding, an authorized recovery planner receives a *bounded, typed failure bundle*. It proposes a scoped workproduct repair, a return to the owning upstream phase, or a strategy variant without changing requirements/acceptance or protected evidence. A deterministic validator and independent inspector decide acceptance. When a strategy has the same canonical failure fingerprint with no material change, reject it and choose another allowed strategy or stop. **Test:** AT-026..AT-036.

### US-05 (P0): Safe terminal behavior and release truthfulness

A valid `BLOCKED` package is operational completion but not engineering success. If an issue is out of scope, unresolvable within budget, or depends on human approval, the Conductor seals a BLOCKED package, registers a unique dead-letter incident, emits a useful alert and continues remaining work. **Test:** AT-037..AT-042.

### US-06 (P1): Factory-source maintainer (isolated proposals)

Given verified evidence of a defect in Forge-C's own agent skills, workflow builder, MCP adapter, prompts or source code, a dedicated Factory Maintainer agent can formulate and implement a candidate fix in a constrained worktree, add a reproducer and independent tests, submit to the existing CRE promotion runner, and create a reviewable branch/PR. It **cannot** merge, deploy or modify constitutional/safety/protection policies, signed release artifacts, frozen fixtures or holdout oracles. **Test:** AT-043..AT-051.

### US-07 (P1): Operating envelope and feedback

An operator can query status, failures, queues, user-visible traces, per-agent costs and readiness in the current dashboard and set an authenticated pause/drain/resume for the *Conductor*. Display filters never change audit capture. Capability policies are externally authorized. **Test:** AT-052..AT-056.

### US-08 (P1): Unattended soak and operational readiness

A staged pilot (observe → limited pilot → eligible active operating envelope) measures service availability, autonomous recovery, engineering yield and operator intervention on *homogeneous frozen cohorts*, culminating in a real, supervised 168-hour non-interactive soak. The gate must report `NOT_DEMONSTRATED` until evidence exists. **Test:** AT-057..AT-063.

### US-09 (P2): Optional capacity/fairness expansion

Multiple workers may operate on different isolated workspaces subject to CPU/GPU/VRAM and model-server capacity limits; no starvation, duplicate dispatch or collision of shared tools. Begin with **one** worker by default. **Test:** AT-064..AT-066.

## 3. Hard invariants (policy precedence)

- **AFO-INV-01 Safety:** no autonomous safety sign-off, deviation acceptance, production release, target flashing or ASIL/ASPICE capability claim. `READY_FOR_OFFLINE_REVIEW` remains for human review only.
- **AFO-INV-02 No weakening:** AFO cannot alter/bypass SWE.1–SWE.6 independent inspections, frozen requirements, HSI, safety requirements, accepted static-analysis/MISRA limitations, release policies, CRE guards, MCP permissions, protected tests/holdouts, trace minimums or the Forge-C constitution.
- **AFO-INV-03 Boundedness:** finite attempts, strategy variants, tokens, wall time, cost, per-workorder horizon, retries, global quota and rate limits. Terminal outcomes are always recorded; no repeated identical prompts.
- **AFO-INV-04 Authority:** policy validation is deterministic; effective permission is the intersection of constitution, 002/003 policies, CRE 004 policy, host OS confinement and AFO policy. An AFO mode **never** implicitly enables CRE `PILOT`/`ACTIVE` or authorizes code deployment.
- **AFO-INV-05 Model-free control:** health polling, queue state machines, locks, classification rules, budgets, side-effect replay decisions, gate verdict ingestion, alerts and metrics are deterministic. LLM calls only for explicit approved engineering diagnosis or code synthesis; zero model tokens for empty healthy queue.
- **AFO-INV-06 MCP and SKILL:** each new AI role has versioned SKILL/role registration, smallest MCP tool grants, bounded structured result. No general unrestricted shell, arbitrary Git push or unrestricted filesystem to agents.
- **AFO-INV-07 Distinct duties:** SWE author ≠ SWE inspector; Maintainer author ≠ CRE promotion runner; neither can rewrite their own verdicts, proofs or locked oracles.
- **AFO-INV-08 Persistence:** append-only auditable events; transactional queue and outbox; monotonic fencing tokens and idempotency keys. No duplicate *logical* work-order admission or non-replayable side effects across restart, even though worker delivery is at least once.
- **AFO-INV-09 Ambiguous side effects:** if state is `PENDING` with unknown external outcome, reconcile an authoritative receipt; if impossible, fail closed to `REQUIRES_OFFLINE_ATTENTION` and do not blindly replay.
- **AFO-INV-10 No credential leakage:** subprocess environments and repair worktrees have scoped credentials, no network by default for verifier, protected source/evidence read-only in sandbox, no secrets or hidden chain-of-thought in logs.
- **AFO-INV-11 Runtime vs evolution:** automatic reversible *operational* action only if pre-authorized by CRE; changes to persistent Forge-C source/skills/prompts/workflows remain staged for external change control, never autonomously merged or activated.
- **AFO-INV-12 Service availability ≠ delivered software:** `TERMINAL_PACKAGE_CREATED` does not equal engineering pass. Historical BLOCKED and first-pass outcomes are preserved.
- **AFO-INV-13 No undesired productivity:** the Conductor cannot invent work orders or change their approved scope to keep the GPU busy; idle without work is healthy.
- **AFO-INV-14 Network and storage:** persist under `FORGE_DATA_ROOT` on a verified mounted filesystem; fail closed when the mount is absent or not writable; no fallback to ephemeral/home paths.
- **AFO-INV-15 No agent-driven policy mutation:** attempted privilege escalation, prompt injection in failure bundles, and proposed changes to protected paths are denied, audited, and quarantined.
- **AFO-INV-16 Recovery safety:** no automatic retry of hardware flash, safety approval, immutable baseline overwrite, release signing, or any non-replayable operation. Any uncertain operation is treated as non-replayable.
- **AFO-INV-17 Observable uncertainty:** `UNKNOWN`, `NOT_RUN`, `BLOCKED`, `NOT_COMPUTABLE`, and estimated token/cost must remain distinguishable from PASS/MEASURED.
- **AFO-INV-18 Isolation and restore:** infrastructure health checks/OS restart never require Fabro to be alive; no single Conductor subprocess must own credentials of independent verifier or protected holdout.

## 4. Functional requirements

The normative list below is mirrored in `requirements.csv` with priorities, owners, acceptance tests and implementation tasks. Every P0 shall be traceable to at least one negative test as well as a positive or replay scenario.

### Constitution, policy and scope

- **AFO-FR-001 [P0]** AFO MUST audit current 001–004 source/evidence/installed tools and record IMPLEMENTED/PARTIAL/MISSING without inventing a capability.
- **AFO-FR-002 [P0]** AFO MUST fail closed under a versioned schema-validated policy; current constitutional, 002/003/004 and OS restrictions take precedence.
- **AFO-FR-003 [P0]** AFO MUST start DISABLED or OBSERVE_ONLY; enabling PILOT/ACTIVE requires external authorization bound to scope, expiry and policy hash.
- **AFO-FR-004 [P0]** AFO MUST NOT modify existing CRE configuration or enable CRE ACTIVE implicitly; authorization intersection decides every action.
- **AFO-FR-005 [P0]** AFO MUST preserve pinned versions, the approved ASPICE process baseline, safety evidence and all 001–004 regression gates.
- **AFO-FR-006 [P0]** AFO MUST maintain a non-LLM deterministic decision record for every admission, retry, plan approval, stop and operator control.
- **AFO-FR-007 [P0]** AFO MUST use separate service/account permissions and explicit MCP/SKILL contracts for any newly introduced AI role.
- **AFO-FR-008 [P0]** AFO MUST never claim that an E2E BLOCKED archive is an accepted engineering package.

### Host 24/7 and services

- **AFO-FR-009 [P0]** AFO MUST manage each runtime dependency through systemd, rather than relying on nohup; failures get bounded automatic restarts and probes.
- **AFO-FR-010 [P0]** AFO MUST have its own headless Conductor systemd service; the current supervisor continues independently, including Fabro-down monitoring.
- **AFO-FR-011 [P0]** AFO MUST verify a persistent mounted FORGE_DATA_ROOT before writing and refuse ephemeral fallback.
- **AFO-FR-012 [P0]** AFO MUST document and test operator-approved systemd lingering/boot-session behavior and stable mount dependencies.
- **AFO-FR-013 [P0]** AFO MUST propagate readiness/health states for Ollama, gateway, Fabro, dashboard, supervisor, data store and Conductor.
- **AFO-FR-014 [P0]** AFO MUST provide independent watchdog/heartbeat of the Conductor, detecting hang, repeated restart and missed polls.
- **AFO-FR-015 [P0]** AFO MUST prevent service restart storms and avoid starting workloads while mandatory dependencies are unhealthy or UNKNOWN.
- **AFO-FR-016 [P1]** AFO SHOULD run runtime processes with least privilege and scoped credentials, including separation of repair/verifier identities where supported.

### Durable intake and scheduling

- **AFO-FR-017 [P0]** AFO MUST accept only schema-validated explicitly approved work-order envelopes with immutable input manifests and provenance hashes.
- **AFO-FR-018 [P0]** AFO MUST deduplicate `(tenant_scope,request_id)` atomically and reject the same ID with a different manifest hash.
- **AFO-FR-019 [P0]** AFO MUST store work-order, attempt, event, lease and outbox state durably before external side effects.
- **AFO-FR-020 [P0]** AFO MUST expose queue admission and worker concurrency limits, starting with one worker by default.
- **AFO-FR-021 [P0]** AFO MUST require healthy storage, model, MCP capability and authorization preflight before admitting work.
- **AFO-FR-022 [P0]** AFO MUST retain stable order identity across all retries; attempts SHALL have unique monotonically ordered identities.
- **AFO-FR-023 [P0]** AFO MUST implement lease fencing and atomic compare-and-swap admission so two Conductor instances cannot dispatch one work item.
- **AFO-FR-024 [P0]** AFO MUST schedule a finite approved backlog continuously when capacity is available and remain healthy without generating work when idle.
- **AFO-FR-025 [P1]** AFO SHOULD support priority classes and aging/fairness with proof of no starvation for permanently eligible work.
- **AFO-FR-026 [P1]** AFO SHOULD support pause, drain and resume as authenticated, audit-logged operations that do not mutate accepted work products.

### Reconciliation and exactly-once logical accounting

- **AFO-FR-027 [P0]** AFO MUST use an append-only transaction outbox for each launch/recovery/finalize command with stable idempotency key and fencing token.
- **AFO-FR-028 [P0]** AFO MUST treat Fabro CLI launch as potentially ambiguous until an authoritative run receipt is reconciled.
- **AFO-FR-029 [P0]** AFO MUST correlate attempts to actual Fabro run labels/metadata and quarantine zero/duplicate/unknown matches as specified in the crash matrix.
- **AFO-FR-030 [P0]** AFO MUST reconcile in-progress, terminal, missing and unreachable Fabro runs across Conductor restart and machine reboot.
- **AFO-FR-031 [P0]** AFO MUST persist checkpoint hashes from independently accepted SWE phases and invalidate downstream evidence when an upstream dependency changes.
- **AFO-FR-032 [P0]** AFO MUST use verified work-order-level resume, not invent unproven Fabro-native checkpoint APIs.
- **AFO-FR-033 [P0]** AFO MUST guard side effects using existing CRE replay classes; uncertain non-replayable actions SHALL NOT execute a second time.
- **AFO-FR-034 [P0]** AFO MUST distinguish terminal Fabro state, valid sealed package, BLOCKED engineering outcome and READY quality outcome.
- **AFO-FR-035 [P0]** AFO MUST use unique immutable workspaces and release archives per attempt without overwriting previous evidence.
- **AFO-FR-036 [P1]** AFO SHOULD provide transactional backup/restore and replay-deterministic projections for queue and outbox state.

### Autonomous SWE diagnosis and replanning

- **AFO-FR-037 [P0]** AFO MUST ingest structured, authoritative SWE gate/inspection/compile/test failures, not only service-level health or AI summaries.
- **AFO-FR-038 [P0]** AFO MUST classify PRODUCT_QUALITY, INFRASTRUCTURE, TRANSIENT_DEPENDENCY, FACTORY_CODE_DEFECT, SPECIFICATION_GAP, SECURITY and UNKNOWN distinctly.
- **AFO-FR-039 [P0]** AFO MUST compute canonical cross-attempt failure signatures while preserving relevant phase/check/tool provenance and removing volatile identifiers.
- **AFO-FR-040 [P0]** AFO MUST try deterministic known remediation and validated CRE lessons before calling a diagnosis model.
- **AFO-FR-041 [P0]** AFO MUST provide a scoped, bounded SKILL-governed Recovery Planner agent that emits a schema-valid plan and never executes privileged operations.
- **AFO-FR-042 [P0]** AFO MUST validate strategy admissibility, scope, change-impact mapping and material difference independently of model output.
- **AFO-FR-043 [P0]** AFO MUST allow scoped product-draft repair or upstream phase rework only within the approved work order and preserve inspector independence.
- **AFO-FR-044 [P0]** AFO MUST prevent identical plan/fingerprint retry storms across stages, restarts and attempt IDs.
- **AFO-FR-045 [P0]** AFO MUST enforce cumulative token/turn/CPU-GPU/wall-clock/attempt/strategy budgets, including local Qwen runs.
- **AFO-FR-046 [P0]** AFO MUST block or escalate immediately on missing authoritative HSI, requested safety/acceptance modification or unknown non-replayable effects.
- **AFO-FR-047 [P0]** AFO MUST produce a new attempt with proper downstream reinspection when an admissible recovery plan changes a baseline.
- **AFO-FR-048 [P1]** AFO SHOULD switch among pre-authorized model profiles only when doing so is materially justified and never add a paid endpoint implicitly.

### Maintainer proposals and protected factory evolution

- **AFO-FR-049 [P0]** AFO MUST distinguish factory-source defects from product defects and never grant general source editing to infrastructure fabric-repair.
- **AFO-FR-050 [P1]** AFO SHOULD provide a dedicated Factory Maintainer SKILL/agent for proposing narrowly scoped non-protected patches in isolated worktrees.
- **AFO-FR-051 [P1]** AFO SHOULD require a reproducer that fails on baseline and passes on candidate before accepting a source-defect root cause.
- **AFO-FR-052 [P1]** AFO SHOULD run 004 independent promotion gate with frozen negative/golden/holdout tests, policy integrity and security before any proposal is eligible.
- **AFO-FR-053 [P0]** AFO MUST prohibit automatic persistent factory source, skill, prompt, workflow, test-oracle or safety-policy deployment, even if CRE reports ELIGIBLE.
- **AFO-FR-054 [P1]** AFO SHOULD produce a traceable staged branch/pull request with link to 004 CAPA, reproducible tests and a human-review decision.
- **AFO-FR-055 [P1]** AFO SHOULD quarantine rejected, unsafe or non-reproducible proposed changes and preserve all prior evidence.
- **AFO-FR-056 [P0]** AFO MUST keep unrelated approved work orders running on the last approved factory revision during a pending source change.
- **AFO-FR-057 [P1]** AFO SHOULD add a bounded WAITING_EXTERNAL_CHANGE TTL and finalize pending order BLOCKED when no approved change arrives.

### Dead letters, notifications, dashboard and evidence

- **AFO-FR-058 [P0]** AFO MUST create a single immutable BLOCKED package and deduplicated DLQ case on exhausted/out-of-scope attempts while processing unrelated work.
- **AFO-FR-059 [P0]** AFO MUST expose reason code, work-order and attempt IDs, phase, required human action, immutable artifact refs and uncertainty.
- **AFO-FR-060 [P0]** AFO MUST persist and deduplicate alerts with rate limit/backoff, without credentials, sensitive evidence or raw reasoning.
- **AFO-FR-061 [P1]** AFO SHOULD extend existing dashboard with queue, worker, errors, replan history, DLQ, service status and readiness using existing traces.
- **AFO-FR-062 [P1]** AFO SHOULD expose read-only versioned API for AFO status plus separately authenticated audited pause/drain/resume controls.
- **AFO-FR-063 [P0]** AFO MUST never let dashboard display filters delete events or disable mandatory security/audit capture.
- **AFO-FR-064 [P0]** AFO MUST attach AFO queue/recovery/exception evidence to the existing deterministic Release Manager archive.

### Measurement, readiness and verification

- **AFO-FR-065 [P0]** AFO MUST calculate separate service availability, autonomous eligible-recovery rate, READY yield, attempts per order, human prompts/interventions and escaped failures.
- **AFO-FR-066 [P0]** AFO MUST preserve numerators/denominators, event provenance, cohort/version metadata and confidence intervals rather than report universal 100% reliability.
- **AFO-FR-067 [P0]** AFO MUST pass positive and negative crash/reboot/side-effect/fault-injection tests before enabling real PILOT.
- **AFO-FR-068 [P0]** AFO MUST perform reproducible real on-prem model work-order trials including at least one accepted READY and one deliberately BLOCKED outcome for an engineering-success claim.
- **AFO-FR-069 [P1]** AFO SHOULD demonstrate 24h smoke, 72h pilot and 168h unattended soak under recorded maintenance authorization and report actual outage exposure.
- **AFO-FR-070 [P0]** AFO MUST separate IMPLEMENTED, PILOT_ELIGIBLE, ACTIVE_ELIGIBLE and SLO_DEMONSTRATED readiness from configured mode; missing data means NOT_DEMONSTRATED.
- **AFO-FR-071 [P0]** AFO MUST maintain FR→task→test→evidence traceability; no unchecked P0 or failed regression may be described as complete.
- **AFO-FR-072 [P0]** AFO MUST record an explicit signed owner authorization before enabling any privileged ACTIVE operational action; agents cannot forge approvals.


## 5. Non-functional requirements and defaults

- NFR-01 Availability: objective **99.0% over rolling 30 days** for the factory's *admitted-work control plane* during configured service windows, excluding declared maintenance and disk/power outages by separate accounting; this is a *proposed SLO*, not demonstrated reliability. Collect loss minutes and cause; do not silently exclude unplanned outages.
- NFR-02 Recovery: objective transient-service restore p95 <= 10 minutes when hardware/storage/model prerequisite survives; otherwise block/report. No universal guarantee.
- NFR-03 Control: startup reconciliation deterministically reaches a resolved state for all durable attempts or marks them `REQUIRES_OFFLINE_ATTENTION` within configured deadlines; no orphan work beyond 2 control intervals under healthy storage/service conditions (provisional target).
- NFR-04 Intake: max admitted concurrent work orders = 1 by default; backlog may be larger; scheduler CPU/GPU/memory admission verified before launch. Priority weights and bounded fairness defined in policy.
- NFR-05 Retry defaults: <=2 transient retries per operation; <=2 substantive strategy variants per SWE phase per work order; <=3 work-order attempts; 1h wall time per recovery attempt and 24h per order (provisional, calibrate with local model evidence). No unlimited local-token path in Conductor even if the workorder's manual mode currently permits it.
- NFR-06 Recovery cost: accounting tracks all retries, diagnostic inference, failed patches, context bytes, CPU/GPU seconds and actual/estimated inference usage; finite per-order cap in both local and cloud modes.
- NFR-07 Data: WAL, busy timeout, schema migration; all critical state persists before side effects; snapshot+replay must produce identical projections; backup/restore verification included.
- NFR-08 Soak: tests demonstrate 24-hour smoke, 72-hour pilot, then 168-hour real unattended run including induced failures during an authorized window; report elapsed time, failure exposure and no false READY.
- NFR-09 Scheduling: control plane uses monotonic deadlines where possible, survives DST/NTP jumps, and stores UTC provenance. Queue ordering is deterministic with aging; defaults never favor aggressive throughput over correctness.
- NFR-10 Privacy/security: no extra external SaaS mandatory; metrics/alerts do not expose credentials, safety evidence, or raw model reasoning. Reasoning summaries are optional bounded, redacted *output*, not hidden thought capture.
- NFR-11 Host: Ubuntu 22.04/24.04 deployment, `systemd --user` with `loginctl enable-linger` where permitted, persistent mount by UUID/`RequiresMountsFor`, independent systemd watchdog; document and test actual host before enabling.

## 6. Failure handling decisions and error classes

| Failure domain | First allowed action | Next action after same signature | Stop condition |
|---|---|---|---|
| Transient Fabro/model/MCP/service outage | deterministic service repair or bounded replay, honoring CRE | health probe + breaker; alternate service only if configured | breaker OPEN, dependency unavailable, retry exhausted |
| SWE product defect (source, tests, traceability) | reopen owning SWE workproduct in isolated attempt, independent inspection | scoped diagnostic planner chooses **different** revision/strategy; return upstream only if impact mapping allows | identical fingerprint after no material change, strategy/workorder budget exhausted |
| Missing authoritative HSI, specification ambiguity, safety allocation | no speculative correction | preserve evidence, request external input | immediate BLOCKED/DLQ |
| Factory-source/skill/MCP implementation defect | create reproducer + sandbox candidate using Maintainer agent | independent CRE promotion decision + owner change request | protected path, failed gate, no replicable cause, budget |
| Disk full, inaccessible mounted data, DB corruption, runaway resource pressure | protect state and stop new admission; deterministic recovery if explicitly safe | backup restore only from verified source with authorization | unavailable authoritative storage, unverified restoration |
| Fault in gate oracle, frozen policy, required safety process | no autonomous mutation | BLOCKED, offline change-control proposal | immediate escalation |

## 7. Key entities

`ApprovedWorkOrder`, `Admission`, `WorkAttempt`, `StageCheckpoint`, `FailureBundle`, `StrategyDecision`, `RecoveryPlan`, `SideEffectReceipt`, `ServiceHealth`, `MaintenanceProposal`, `DeadLetterCase`, `OperatorAuthorization`, `OutboxEvent`, `AutonomyMetric`. See `data-model.md` and JSON schemas. Canonical 002 incidents and CRE CAPAs/lessons/promotion decisions remain their **existing** stores; AFO refers to their IDs, never mirrors or rewrites their authority.

## 8. Scope exclusions and decision authority

- Do not modify the approved process-model version or characterize Forge-C as ISO 26262-certified. No code for approval of production firmware by AI.
- Do not auto-merge/push to `main`, deploy factory source, rewrite golden or holdout oracles, change budgets upwards, edit safety policies or authorize own changes.
- No autonomous model selection that introduces paid/cloud providers or expands data disclosure beyond previously approved profiles.
- No blanket permissions to manipulate `systemctl`, filesystems, GitHub or host mounts via the agent MCP. Deterministic privileged actions are narrowly brokered and logged.
- Optional high-availability across machines, remote disaster recovery and live firmware flashing are explicitly out of scope for MVP.

## 9. Definition of Done (per milestone)

A task may be checked only after code + reproducible tests + artifact hash + relevant contract and safety gates; a mocking-only test does not establish real-host availability. Mandatory outcome: no manual prompts for any eligible *simulated* recovery path, verified real pilot where prerequisites exist, and honest unblocked/blocked classifications. Feature status `IMPLEMENTED` is distinct from `PILOT_ELIGIBLE`, `ACTIVE_ELIGIBLE` and statistically `SLO_DEMONSTRATED`. Hardware/software safety approval remains offline human authority.
