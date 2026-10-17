# Feature 004 — Continuous Reliability Engineering (CRE)

**Feature:** `004-continuous-reliability-engineering`  
**Baseline:** Forge-C v0.5 (features 001, 002, 003)  
**Status:** proposed specification / implementation work outstanding  
**Implementation engineer:** Claude Code, following existing project Spec Kit conventions  
**Runtime:** Fabro-orchestrated, local Qwen; deterministic control plane  
**Target:** reliable dark operation for low-footprint embedded C HAL/LLD, SWE.1–SWE.6, independent inspections and evidence targeting an ISO 26262 ASIL B lifecycle; offline approval only.

## 1. Motivation and goals

Current retry/rework cycles can complete while preserving an underlying recurring defect. Forge-C must distinguish short-term recovery from durable improvement, avoid retry storms, quantify reliability growth, prevent regression, and provide credible evidence for production operational readiness.

CRE combines (a) MAPE-K/autonomic control, (b) CAPA/Test–Analyze–and–Fix, (c) bounded self-stabilizing workflow state machines, (d) Statistical Process Control and reliability-growth diagnostics, and (e) controlled promotion of factory versions. **None of these alone establishes 100% reliability in an open probabilistic system.**

G1. Bound all retries, repairs and recovery paths, including partial failures and restarts.
G2. Record distinct failure modes and verified root causes; convert successful repairs into tested prevention rules/lessons.
G3. Measure baseline versus candidate under comparable, version-pinned workloads.
G4. Admit a candidate only if mandatory safety/security/quality gates pass and no known protected benchmark regresses.
G5. Make reliability evolution observable in the existing dashboard, 003 KPIs and offline evidence package.
G6. Keep healthy supervision model-free and minimize tokens per accepted package.

## 2. Integration and explicit non-goals

- **MUST extend 002**, not clone its model-less supervisor, incident DB, repair worker, knowledge service, trace collector, release gates or dashboard. **MUST extend 003** without renumbering K01–K20 or rewriting past KPI definitions. Schema changes are versioned and migrated.
- Preserve the v0.5 process baseline: SWE.1–SWE.6, inspector independence, frozen artifact hashes, MISRA coverage limitations, tests, safe release states and ASIL B-target evidence; no automatic safety certification.
- Existing factory agent skills remain Fabro runtime `.fabro/skills/...`; Claude/Spec Kit agent instructions remain separate. New AI roles are justified only if no existing role can safely perform the function. Every agent-invoked tool MUST be a restricted MCP operation, while deterministic daemon internals may use native APIs.
- **Non-goals:** guarantee universal 100% stability; redesign all six SWE author/reviewer loops; build a replacement orchestration engine; require paid/cloud LLM services; automatic approval of factory production use or driver safety release; alter the approved Automotive SPICE process-model version as a side effect of CRE.

## 3. Global invariants (never compensable by KPIs)

- INV-01: healthy supervisor polling invokes zero LLM/API inference; supervisor can observe Fabro-down conditions independently.
- INV-02: finite configured attempts, timeouts and cost budgets; on exhaustion a stable terminal `REQUIRES_OFFLINE_ATTENTION`/`BLOCKED` outcome is reached, not an unbounded loop.
- INV-03: every state-changing operation is authorized, auditable and idempotent at its designated checkpoint, or explicitly classified non-replayable.
- INV-04: historical event records, originally failed inspections, released archives, approved product baselines and safety evidence are never rewritten by repair.
- INV-05: no repair, candidate or lesson can weaken safety, MISRA, evidence completeness, reviewer separation, MCP scope, token-limit enforcement or policy integrity.
- INV-06: agent assertions are never the sole verification of root cause, test pass, promotion, rollback, or SLO attainment.
- INV-07: observability displays distinguish `OBSERVED`, `HYPOTHESIS`, `VERIFIED`, `UNKNOWN`, `ESTIMATED` and `NOT_COMPUTABLE`; missing telemetry never means success or zero.
- INV-08: no KPI can compensate for an invariant violation; release state remains `READY_FOR_OFFLINE_REVIEW`/`BLOCKED`; no model may claim ASIL approval.
- INV-09: safety-critical config/policy changes are always blocked from automatic promotion; offline authorized review is separate from unattended production workflows.
- INV-10: only sanitized, validated, versioned lessons are retrievable across workflows; untrusted incident text cannot command privileged operations.
- INV-11: metrics and dashboards are derived from durable typed events; replay is idempotent, and event provenance is retrievable.
- INV-12: all accepted CRE behavior remains operable without Claude as a production runtime dependency.

## 4. User stories and acceptance outcomes

**US-C01 (P0) — Bounded recovery:** As owner, I want a stalled or repeatedly failing stage to exit with an explicit reason, without indefinite token consumption. The same fault cannot create parallel competing repair workers. Proven by deterministic failure injections and restart tests.

**US-C02 (P0) — Verified CAPA:** As owner, I want every recurring significant incident linked to a reproducer, evidence-supported cause, correction, prevention check, regression test and disposition. A lesson from an unverified fix is not shared.

**US-C03 (P0) — Comparability and trustworthy metrics:** As owner, I want accurate first-pass/recurrence/recovery/yield measurements on like-for-like embedded workloads, with numerator, denominator, timeframe, tool/model/MCU profile and confidence limitations.

**US-C04 (P0) — Independent promotion:** As owner, I want an isolated candidate evaluated against a frozen baseline and independent checks. A malicious or faulty patch cannot change safety thresholds or its own evaluation outcomes.

**US-C05 (P0) — Operational proof:** As owner, I want objective demonstration that workflow termination, rollback, deduplication, recovery and policy integrity hold under injected failures; no model-driven interpretation substitutes for test evidence.

**US-C06 (P1) — Continuous detection:** As owner, I want calibrated control charts and cohort trends that surface meaningful degradation without confusing changes in driver class/complexity or sample size with regressions.

**US-C07 (P1) — CRE dashboard:** As owner, I want an integrated read-only Reliability view with incident Pareto, failure fingerprints, FPY, recurrence, MTTR, recovery cost, candidate decision and test-evidence drilldown. Existing trace capture/view separation remains intact.

**US-C08 (P1) — Readiness decision:** As offline reviewer, I want complete hashed CRE reports, explicit known limitations and a phase-gated readiness statement; `NOT_DEMONSTRATED` must never be rendered `PASS`.

## 5. Functional requirements

| ID | Requirement | Priority |
|---|---|---|
| CRE-FR-001 | Audit the actual 001–003 implementation against specs; classify each dependency `IMPLEMENTED/PARTIAL/SPEC_ONLY/MISSING`. | P0 |
| CRE-FR-002 | Reuse and version existing 002 incident/event/lesson APIs, 003 KPI store and release packager. | P0 |
| CRE-FR-003 | Classify incidents by `INFRASTRUCTURE`, `TRANSIENT_DEPENDENCY`, `PRODUCT_QUALITY`, `POLICY_SECURITY`, `UNKNOWN` and never infer root cause from symptom alone. | P0 |
| CRE-FR-004 | Compute deterministic, normalized failure fingerprints with canonical fields and versioned algorithm. | P0 |
| CRE-FR-005 | Guarantee bounded retries with class-specific limits, timeout, backoff+jitter, repair leases and breaker. | P0 |
| CRE-FR-006 | Distinguish bounded workflow recovery from longer-term evolutionary candidate promotion. | P0 |
| CRE-FR-007 | Enforce idempotency/replay classification for checkpoints and external side effects. | P0 |
| CRE-FR-008 | Persist recovery/repair/candidate state and resume deterministically after crash or power loss. | P0 |
| CRE-FR-009 | Implement a versioned CAPA record lifecycle with direct links to incident, reproducer, evidence and prevention regression. | P0 |
| CRE-FR-010 | Mark root-cause verification only upon recorded, independent reproduction and causal evidence; allow unresolved classifications. | P0 |
| CRE-FR-011 | Persist each attempted fix, negative outcome and retraction as immutable historical fact. | P0 |
| CRE-FR-012 | Use existing 002 lessons store; only allow promotion of evidence-verified, sanitized and scoped lessons. | P0 |
| CRE-FR-013 | Build a fixed, versioned embedded-workload benchmark matrix plus an independent hidden/holdout regression set. | P0 |
| CRE-FR-014 | Pin workload, requirements, target MCU, compiler flags, model, tool versions, safety profile and seed when supported. | P0 |
| CRE-FR-015 | Prevent benchmark fixture manipulation by candidate/repair agents; run validators outside candidate privileges. | P0 |
| CRE-FR-016 | Derive FPY and package yield from first immutable inspections and unique work-order final states, not attempts/retries. | P0 |
| CRE-FR-017 | Reuse K16 autonomous repair effectiveness and K17 recurrence definitions without resetting historical windows. | P0 |
| CRE-FR-018 | Compute CRE-specific MTTR, retry amplification, repeat failures and candidate non-regression with denominators/provenance. | P0 |
| CRE-FR-019 | Handle `UNKNOWN/NOT_APPLICABLE/NOT_COMPUTABLE`, incomplete cohorts, right censoring and data quality. | P0 |
| CRE-FR-020 | Add configurable baseline windows and class-specific SPC detection (p-chart/EWMA when assumptions support it). | P1 |
| CRE-FR-021 | Report confidence intervals and sample sizes; never assert 100% reliability after finite tests. | P0 |
| CRE-FR-022 | Use reliability-growth fits (e.g., Duane/AMSAA) only as optional diagnostics after goodness-of-fit and assumptions review. | P2 |
| CRE-FR-023 | Evaluate patches in isolated worktrees and OS-enforced process/filesystem sandbox. | P0 |
| CRE-FR-024 | Block changes to protected policies, quality gates, released evidence, security boundaries and validation assets. | P0 |
| CRE-FR-025 | Use independent runner to reproduce original failure, check fix, run old+holdout regressions, threat tests and verify rollback. | P0 |
| CRE-FR-026 | Make promotion decisions deterministic, evidence-linked and separately authorized from patch-authoring agents. | P0 |
| CRE-FR-027 | Support `OBSERVE_ONLY`, `PILOT` and `ACTIVE` modes; initial default is `OBSERVE_ONLY`. | P0 |
| CRE-FR-028 | Refuse automatic persistent-code promotion in initial release; allow explicitly pre-authorized, bounded reversible operational actions only. | P0 |
| CRE-FR-029 | Revert atomically on degraded health/regression and retract affected lessons; preserve forensic evidence. | P0 |
| CRE-FR-030 | Protect against adversarial instructions in logs/lessons/prompts and forged `PASS` artifacts; enforce privileges outside LLM. | P0 |
| CRE-FR-031 | Log structured traces for incident/CAPA/bench/promotion, with existing redaction, correlation, retention and capture/view rules. | P0 |
| CRE-FR-032 | Extend 003 metrics/dashboard without changing K01–K20 identities/definitions. | P1 |
| CRE-FR-033 | Add offline CRE evidence inventory to deterministic Release Manager, both READY and BLOCKED. | P0 |
| CRE-FR-034 | Validate fault injection scenarios covering Fabro-down, MCP failures, stuck agents, disk/DB failure, restart, bad patch, poisoned lesson and security bypass. | P0 |
| CRE-FR-035 | Ensure positive and negative paths finish with stable, explainable machine outcomes and bounded resource usage. | P0 |
| CRE-FR-036 | Build a historical comparison/effectiveness report; do not conflate increased retries with reliability growth. | P1 |
| CRE-FR-037 | Preserve existing `SKILL.md` + least-privilege MCP contracts for every new AI role and engineering tool. | P0 |
| CRE-FR-038 | Minimize token cost via deterministic-first diagnosis, bounded evidence extracts and zero verbose reasoning/status emissions. | P0 |
| CRE-FR-039 | Record pinned versions/license provenance and an implementation test evidence report, with missing prerequisites explicit. | P0 |
| CRE-FR-040 | Maintain FR→task→test→evidence traceability; mark unmet P0 requirements BLOCKED. | P0 |

## 6. Preliminary operational SLOs (configurable proposals, NOT observed results)

These are **suggested candidate targets only**. Owners must approve final thresholds after observing comparable cohorts; no reliability claim may be inferred from a small sample:

- Safety/security/baseline violations: **0 tolerated**, independent of cohort size.
- Healthy supervisor model calls: **0 per healthy poll**; acceptance demonstration ≥100 mocked+instrumented cycles.
- Infinite/orphaned recovery loops: **0 tolerated** in bounded state-machine test suite.
- Known critical issue recurrence after correction: **0 observed in targeted regression suite** (not equivalent to zero future recurrence).
- For a mature, homogeneous class (and adequate observation): example FPY target ≥95%; package-yield and p95 recovery targets must be calibrated from actual baseline rather than invented.
- First delivery passes in `OBSERVE_ONLY` even if meaningful production reliability statistics are unavailable; it must label readiness **NOT_DEMONSTRATED** until evidence is adequate.

## 7. Definition of Done

All P0 requirements are backed by executed tests and versioned evidence; dependency readiness is explicit; negative fault-injection tests prove fail-closed behavior; schema/event replay and rollback tests pass; dashboards and package inventories display incomplete data truthfully. A no-regression validation candidate may be marked `ELIGIBLE_FOR_OFFLINE_REVIEW`; only the existing authorized process can promote production software. Final claim must be **engineering evidence available**, not universal convergence/ASIL certification.
