# Acceptance and Fault Injection — Forge-C CRE 004

**Test evidence contract:** every test writes machine-verifiable `{test_id, test_version, input_hash, test_command, tool_version, exit_code, start_utc, end_utc, result, evidence_refs, artifact_hashes}`. For fault-injection/E2E also capture attempts, total elapsed, state transitions, model-token counts, safety/policy verification and impacted baseline hashes. Tests are **not executed merely because this specification exists**. Missing physical tools or installed runtimes => `NOT_RUN/BLOCKED`, never PASS.

## 1. Minimum test harness

- `unit`: deterministic state transitions, config validation, schemas, metrics math, classification, fingerprint and policy evaluations. Prefer pure Python/pytest or existing project test framework.
- `contract`: existing 002 incident/lesson/event/MCP APIs; 003 KPI output; release manager manifests and migration/replay; reject incompatible signatures.
- `integration`: real supervisor, event DB, independent worktree, repair worker and tools when installed. Use injected fake failures at process/network boundaries, not mock verdicts.
- `end-to-end`: one real RCC work order through supported SWE workproducts, independent inspection, toolchain, packager and CRE with actual Fabro/local Qwen. Fail or BLOCKED if unavailable.
- `chaos/security`: repeated fault injection, restart, denied writes, invalid signatures, poisoned text, corrupt test fixtures, rollback; verify immutable hashes before/after.

## 2. Acceptance scenarios — normative

### Configuration, schema and provenance

- **AT-001 (P0):** Given default policy, when service starts, then mode=`OBSERVE_ONLY`, no persistent-code auto promotion or model-based healthy polls. An attempted config `max_attempts=-1`, disabling audit capture or enabling auto safety-gate edits is rejected before execution.
- **AT-002 (P0):** Given typed events including absent optional fields, when validated and stored, then permitted fields pass; invalid statuses, timestamps/IDs or missing provenance fail with explicit issue code. Existing 002 event IDs remain unchanged.
- **AT-003 (P0):** Given an event stream with duplicate deliveries, restart/replay and reordered noncausal events, when reduced, then incident count, CAPA state and KPI aggregates equal a canonical single-delivery replay. A dispatched side effect executes at most once per idempotency key.
- **AT-004 (P0):** Given invalid embedded C source producing a deterministic compiler error, when classified, then it is `PRODUCT_QUALITY` and routed to SWE author/reviewer rework, not fabric-repair. Transient MCP outage is a separate class.
- **AT-005 (P0):** Given repeated errors with distinct timestamps, PIDs, temporary workspace paths but the same normalized signature, then one normalized incident is created. Given distinct compiler error codes/root scopes, they are not silently merged; collision mapping is auditable.
- **AT-006 (P0):** Given old/migrated incident without direct reproduction, root-cause status is UNKNOWN or HYPOTHESIS; not VERIFIED; no historical immutable record is modified.
- **AT-007 (P0):** Given ERROR/WARN/INFO trace permutations and secret-bearing tool failure output, events preserve minimum audit/security evidence, redact credentials, omit hidden reasoning, respect payload size and link raw artifact by hash; dashboard display filters cannot alter capture.

### Bounded operational recovery

- **AT-008 (P0):** Given persistent 429/timeouts, configured max attempts and a forced supervisor restart, total attempts across process lifetimes remain bounded; terminal disposition has an explicit issue code and prior evidence.
- **AT-009 (P0):** Given sustained dependency failure, when breaker opens, then no new calls occur during cooldown; HALF_OPEN permits bounded probes only. No simultaneous repair storm or duplicated costly agent calls.
- **AT-010 (P0):** Given two concurrent supervisor ticks seeing one fault, exactly one active scoped repair lease exists. Given Fabro process crash, external 002 worker can dispatch according to policy without depending on Fabro API.
- **AT-011 (P0):** Given a crash immediately after side effect but before acknowledgement, restart cannot duplicate a `NON_REPLAYABLE` approval/flash/release action. Retry-safe operations may continue only after durable checkpoint validation.
- **AT-012 (P0):** Given 100 healthy polls, observed inference calls/tokens == 0. Given a permanent unfixable fault, deterministic FSM eventually marks REQUIRES_OFFLINE_ATTENTION/BLOCKED under the configured fairness and observation assumptions.
- **AT-013 (P0):** Generate valid and invalid transition sequences, lost heartbeat, full disk, DB unavailable and supervisor killed/restarted; verify state remains recoverable or explicitly degraded/BLOCKED and invariant breaches never produce READY.

### CAPA and prevention knowledge

- **AT-014 (P0):** Given CAPA in OPEN or UNRESOLVED, invalid transition directly to EFFECTIVE is rejected; prior attempts remain recorded; unverified root cause stays nonverified.
- **AT-015 (P0):** Given an AI diagnosis claiming "fixed" but no reproducer in a pinned baseline, CAPA cannot move to CAUSE_VERIFIED; incident may stay open.
- **AT-016 (P0):** Given agent-supplied `PASS` text with failing/absent deterministic test logs, independent validator rejects promotion and CAUSE_VERIFIED status.
- **AT-017 (P0):** Given repair candidate modifying protected safety policy, immutable evidence or benchmark holdout, OS and runner prevent it; no release or historical data is altered. Audit includes attempted path and denial, without secrets.
- **AT-018 (P0):** Given prevention test passes then same fingerprint recurs under eligible window, CAPA transitions to REOPENED, earlier resolution history remains visible and lesson is marked re-evaluate/retract.
- **AT-019 (P0):** Given unverified or poisoned lesson containing privileged instructions, retrieval ignores it; validated bounded top-K lessons include their sources/tests and cannot override hardware manuals or policy.

### Candidate evaluation and regression

- **AT-020 (P0):** Given `OBSERVE_ONLY`, a repair patch can generate candidate/evaluation evidence but cannot be installed as persistent production code; ACTIVE is rejected without authorized runbook/policy prerequisites.
- **AT-021 (P0):** Given benchmark entry with missing MCU, source SHA, tool/version/flags or oracle, runner marks INCOMPLETE/NOT_RUN; it does not substitute an arbitrary compiler/model to manufacture a PASS.
- **AT-022 (P0):** Given golden and holdout fixtures, a candidate cannot edit either without test harness detecting changes. Test results include immutable fixture revisions and sample counts.
- **AT-023 (P0):** Given patch that fixes the reproducer but introduces another regression, independent runner records the new failing gate and returns REJECTED, despite improvement on original incident.
- **AT-024 (P0):** Given candidate with lower token cost/higher throughput but a weakened or bypassed MISRA/traceability/coverage/safety gate, promotion is REJECTED; no weighted KPI can overturn the veto.
- **AT-025 (P0):** Given authorized reversible process/config action that subsequently degrades health, rollback restores last known good policy/binary/config and records a candidate rollback plus affected-lesson retraction. Previously issued archive bytes/hashes remain identical.
- **AT-026 (P0):** Given candidate with forged evidence file, malicious test-oracle edit, path escape, or suppressed negative result, independent verification fails; incident/trace contains explicit security denial.

### Reliability statistics and data quality

- **AT-027 (P0):** Given work order WO-1 fails first SWE.3 inspection then passes after three retries and WO-2 passes immediately, SWE.3 first-pass numerator remains one (not two) of two; unique READY package count never counts retries as new deliveries.
- **AT-028 (P0):** Given 5/5 successes, Wilson 95% interval lower bound is < 1.0 and dashboard shows n=5 and uncertainty; no 100%-reliability claim. Given 0 failures among ~300 independent comparable trials, annotate upper 95% failure probability approximately 1% under assumed independence, not zero.
- **AT-029 (P1):** Given class with missing or mixed calibration baseline, p-chart and EWMA show NOT_COMPUTABLE / INSUFFICIENT_BASELINE; no adaptive threshold auto-tuning or safety gate relaxation.
- **AT-030 (P0):** Given identical typed event ledger and policy hash, full batch replay and incremental aggregation yield identical CRE metrics/003 K16-K17; missing token telemetry yields UNKNOWN or estimated-with-method, not zero.
- **AT-031 (P1):** Given results for GCC O0 / MCU-A versus Clang O2 / MCU-B, historical comparison refuses homogeneous pooling without declared normalization and evidence; filters update numerator/denominator together.

### Dashboard, release package, security

- **AT-032 (P1):** Given selected trace channels/human filters, UI includes current run/incident/CAPA/recovery/promotions and sample-count drilldown; clearing a display channel does not delete its stored events or required audit record.
- **AT-033 (P1):** Given an SPC out-of-control alert but no verified infrastructure incident, no repair is dispatched and no mandatory safety/inspection threshold changes.
- **AT-034 (P0):** Given a failing SWE.3 quality gate and partial telemetry, resulting package is `BLOCKED` with CRE evidence present, gap manifest and stable hashes; not silently READY; authorized offline review alone determines subsequent disposition.
- **AT-035 (P0):** Given prompt injection in an incident log, malicious MCP path, fake role grants or a secret string, privileged action fails and sensitive data are absent from persisted user-visible traces. Keep denial evidence.
- **AT-036 (P0):** Run repeatable batch covering Fabro crash, MCP timeout, locked DB, full disk, stalled agent, duplicate dispatcher, invalid patch, lesson poisoning and store restoration. Every case is PASS/FAIL/NOT_RUN with executable command, terminal state or justified unresolved state, timeline, hash and bounded cost.
- **AT-037 (P0):** With real Fabro, local Qwen and installed MCPs, execute one RCC driver end-to-end. Confirm real independent SWE reviews and evidence packaging, not a mock. If unavailable, mark real E2E BLOCKED with missing-capability report.
- **AT-038 (P0):** For every CRE-FR-001..040, trace to tasks, tests and machine evidence; any unmet P0 remains BLOCKED. Reproduce in fresh pinned environment and document rollback/restart operations.
- **AT-039 (P0):** Run all available contract/regression/CRE tests and Spec Kit converge; resolve appended tasks or explicitly preserve BLOCKED gaps. `readiness-assessment.json` cannot claim PILOT/ACTIVE without required real validation; no safety or ASPICE level attestation.

## 3. Minimal demo experiment (should produce mixed positive and negative evidence)

Run these trials using the **same pinned RCC demonstration environment**:

1. Baseline healthy run: observable standard behavior, supervisor zero tokens on 100 idle polls.
2. Inject MCP transient timeout: circuit opens; limited retry, successful resume or clear terminal BLOCKED outcome.
3. Inject deterministic compiler error: no repeated blind retry; SWE author/reviewer route receives issue.
4. Inject forced Fabro process exit: independent supervisor records and (if authorized) attempts bounded recovery.
5. Propose candidate A fixing reproducible timeout policy without touching holdout; independent test may mark ELIGIBLE_FOR_OFFLINE_REVIEW.
6. Propose candidate B that disables coverage/MISRA gate or modifies holdout; mandatory REJECTED even if faster.
7. Re-run candidate A with fault recurrence: CAPA reopens/retraction; report does not claim permanent resolution.
8. Finalize package and export metrics and bounded failure history. Cross-check baseline project files unchanged.

**Important:** This experiment demonstrates engineering controls, not a statistically sufficient operational reliability level. Real statistical calibration requires comparable production-like runs over a defined observation window.

## 4. Readiness gates / evidence disposition

- **OBSERVE_ONLY:** schema and baseline audit accepted; no state-changing CRE actions; metrics may remain uncalibrated.
- **PILOT_ELIGIBLE:** operational state/retry/rollback/CAPA/independent benchmark faults pass with instrumented and real integration where feasible; any missing mandatory real dependency blocks eligibility.
- **ACTIVE_ELIGIBLE:** PILOT criteria + explicitly authorized reversible-action list, signed/reviewed operator runbook and operational monitoring; no autonomous persistent-code promotions or safety signoffs.
- **NOT_DEMONSTRATED:** any mandatory unexecuted test, missing evidence, insufficient comparable data for a specific reliability SLO, or unresolved P0.

The mode used for execution and the confidence/status of any reliability claim are **separate fields**: the system may function in OBSERVE_ONLY while reliability SLO evidence remains NOT_DEMONSTRATED.
