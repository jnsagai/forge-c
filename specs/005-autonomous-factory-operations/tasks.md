# Executable Tasks — Feature 005 Autonomous Factory Operations

**Source of truth:** `spec.md`, `plan.md`, `data-model.md`, `contracts/`, `acceptance-tests.md`. This is an implementation backlog **not a report of completed tasks**. Every item starts unchecked. Do not claim `PASS` based on design-only output.

**Dependencies:** 001–004 unchanged. 004 is still in PR `#1`, configured `OBSERVE_ONLY` at the observed baseline; AFO cannot silently promote CRE or change source-protection policy. Execute M0 before coding, then M1–M8 in order; `[P]` means independent after earlier task prerequisites are met.

**Done per task:** code + deterministic positive/negative tests + exact command/versions + evidence hashes + no protected safety regression. Maintain separate `IMPLEMENTED`, `PILOT_ELIGIBLE`, `ACTIVE_ELIGIBLE`, `SLO_DEMONSTRATED`. Source-only specs remain TODO.

## M0 — Baseline audit and authority

- [ ] **AFO-T001 [P0]** Audit exact 004 HEAD, run reproducible 001–004 baseline and freeze source/tool/host evidence.  
  Trace: AFO-FR-001, AFO-FR-005; acceptance: AT-065, AT-066.
- [ ] **AFO-T002 [P0]** Produce 005 capability matrix and ADR mapping existing 002/003/004 modules to AFO extensions.  
  Trace: AFO-FR-001; acceptance: AT-065, AT-066.
- [ ] **AFO-T003 [P0]** Validate constitutional and CRE authority intersection; define policy floor tests and no-auto-deploy invariants.  
  Trace: AFO-FR-002, AFO-FR-004; acceptance: AT-063, AT-064, AT-065.
- [ ] **AFO-T004 [P0]** Create AFO policy loader with schema and default DISABLED/OBSERVE_ONLY, mode auth and fail-closed semantics.  
  Trace: AFO-FR-002, AFO-FR-003, AFO-FR-004, AFO-FR-006; acceptance: AT-063, AT-064, AT-065, AT-066.
- [ ] **AFO-T005 [P0]** Create complete contracts, schema lint and traceability validator; pin dependencies/licenses.  
  Trace: AFO-FR-007; acceptance: AT-030, AT-045, AT-046.
- [ ] **AFO-T006 [P0]** Design and test signed owner authorization verification (scope/expiry/action/policy hash/revocation).  
  Trace: AFO-FR-003; acceptance: AT-063, AT-064.

## M1 — Boot-resilient headless services

- [ ] **AFO-T007 [P0]** Write safe systemd user unit templates for Ollama, gateway and Fabro, preserving current ports/data root.  
  Trace: AFO-FR-009, AFO-FR-013; acceptance: AT-001, AT-004, AT-005, AT-007.
- [ ] **AFO-T008 [P0]** Write safe systemd units for dashboard and Conductor; retain existing independent supervisor unit.  
  Trace: AFO-FR-009, AFO-FR-010, AFO-FR-013; acceptance: AT-001, AT-003, AT-004, AT-005, AT-007, AT-009.
- [ ] **AFO-T009 [P0]** Add service installation/status/stop scripts, dry-run rendering and compatibility wrapper for forge_services.sh.  
  Trace: AFO-FR-009; acceptance: AT-001, AT-004, AT-005, AT-007.
- [ ] **AFO-T010 [P0]** Implement persistent mount sentinel and read/write/UUID preflight with fail-closed absent-mount behavior.  
  Trace: AFO-FR-011; acceptance: AT-006.
- [ ] **AFO-T011 [P0]** Document operator-approved lingering and mount installation, and least-privilege environment credentials.  
  Trace: AFO-FR-012, AFO-FR-016; acceptance: AT-002, AT-008, AT-045, AT-046.
- [ ] **AFO-T012 [P0]** Implement Conductor heartbeat, sd_notify or simple watchdog correctly tied to actual service capabilities.  
  Trace: AFO-FR-010, AFO-FR-014; acceptance: AT-003, AT-009.
- [ ] **AFO-T013 [P0]** Add external systemd watchdog alerts and bounded Restart/StartLimit, no restart storms.  
  Trace: AFO-FR-010, AFO-FR-014, AFO-FR-015; acceptance: AT-003, AT-005, AT-007, AT-009.
- [ ] **AFO-T014 [P0]** Run isolated SIGTERM/SIGKILL/logout/restart tests with recovery logs for each managed service.  
  Trace: AFO-FR-009; acceptance: AT-001, AT-004, AT-005, AT-007.
- [ ] **AFO-T015 [P0]** Perform authorized real reboot/mount-removal drill and preserve logs/unknowns; mark BLOCKED if not permitted.  
  Trace: AFO-FR-012; acceptance: AT-002, AT-008.

## M2 — Durable queue and scheduler

- [ ] **AFO-T016 [P0]** Implement conductor DB migrations/WAL schema for work orders, attempts, leases, commands and events.  
  Trace: AFO-FR-019, AFO-FR-022; acceptance: AT-011, AT-013, AT-015.
- [ ] **AFO-T017 [P0]** Implement work-order envelope validation, approved-manifest pinning, idempotent submit and duplicate-conflict detection.  
  Trace: AFO-FR-017, AFO-FR-018; acceptance: AT-010, AT-011, AT-012, AT-013.
- [ ] **AFO-T018 [P0]** Implement event ledger bridge and transactional outbox (idempotent replay, stable event IDs).  
  Trace: AFO-FR-006, AFO-FR-019; acceptance: AT-011, AT-013, AT-015, AT-066.
- [ ] **AFO-T019 [P0]** Implement leadership/worker leases with fencing epochs and transactionally guarded state transitions.  
  Trace: AFO-FR-022, AFO-FR-023; acceptance: AT-011, AT-013, AT-021.
- [ ] **AFO-T020 [P0]** Implement deterministic scheduler loop: FIFO + priority aging, one worker, no unapproved synthetic work.  
  Trace: AFO-FR-020, AFO-FR-024, AFO-FR-025; acceptance: AT-014, AT-015, AT-016.
- [ ] **AFO-T021 [P0]** Implement preflight admission guard: mounted storage, service health, allowed models, MCP roles, budgets.  
  Trace: AFO-FR-013, AFO-FR-015, AFO-FR-021, AFO-FR-024; acceptance: AT-004, AT-005, AT-007, AT-010, AT-014, AT-015.
- [ ] **AFO-T022 [P0]** Implement bounded backlog, admission limits, per-order quota and unavailable-dependency defer/backoff.  
  Trace: AFO-FR-017, AFO-FR-020, AFO-FR-021; acceptance: AT-010, AT-012, AT-014.
- [ ] **AFO-T023 [P0]** Add CLI `forge_factory.conductor` commands submit/status/list/pause/drain/resume with authenticated controls.  
  Trace: AFO-FR-018, AFO-FR-026; acceptance: AT-011, AT-012, AT-013, AT-014, AT-053, AT-054.
- [ ] **AFO-T024 [P0]** Test concurrently duplicated submit, workers/race takeover, priority starvation and idle zero LLM tokens.  
  Trace: AFO-FR-023, AFO-FR-025; acceptance: AT-013, AT-016, AT-021.
- [ ] **AFO-T025 [P0]** Implement queue backup/restore with SQLite integrity checks and repeatable replay after restart.  
  Trace: AFO-FR-036; acceptance: AT-021, AT-041.

## M3 — Launch/restart reconciliation

- [ ] **AFO-T026 [P0]** Audit Fabro 0.362 run CLI/API label/creation receipt and implement adapter with unique attempt nonce.  
  Trace: AFO-FR-028; acceptance: AT-018, AT-019.
- [ ] **AFO-T027 [P0]** Create side-effect/attempt-scoped key migration ADR compatible with CRE existing `workorder_launch:<wo>`.  
  Trace: AFO-FR-027, AFO-FR-028, AFO-FR-033; acceptance: AT-017, AT-018, AT-019, AT-025.
- [ ] **AFO-T028 [P0]** Implement transactional launch intent, authority lookup and ambiguity/quarantine reconciliation.  
  Trace: AFO-FR-027, AFO-FR-028, AFO-FR-029, AFO-FR-033; acceptance: AT-017, AT-018, AT-019, AT-020, AT-025.
- [ ] **AFO-T029 [P0]** Implement run-state reconciler for active, absent, dead, completed and unreachable Fabro runs.  
  Trace: AFO-FR-029, AFO-FR-030; acceptance: AT-018, AT-019, AT-020, AT-022.
- [ ] **AFO-T030 [P0]** Implement immutable accepted SWE checkpoint refs with upstream dependency-hash impact mapping.  
  Trace: AFO-FR-031, AFO-FR-032; acceptance: AT-022, AT-023.
- [ ] **AFO-T031 [P0]** Build safe new-attempt recovery from work-order-level validated checkpoints and frozen workspace.  
  Trace: AFO-FR-031, AFO-FR-032, AFO-FR-035; acceptance: AT-022, AT-023, AT-024.
- [ ] **AFO-T032 [P0]** Guard finalizer and READY state with independent release archive validation, not Fabro exit status.  
  Trace: AFO-FR-008, AFO-FR-034; acceptance: AT-024, AT-037, AT-057.
- [ ] **AFO-T033 [P0]** Test crash windows before/after launch and after archive write; no duplicate logical side effects.  
  Trace: AFO-FR-033, AFO-FR-034, AFO-FR-035; acceptance: AT-017, AT-022, AT-024, AT-025, AT-037, AT-057.
- [ ] **AFO-T034 [P0]** Test actual machine reboot with in-flight Fabro run if operator authorized; record BLOCKED otherwise.  
  Trace: AFO-FR-030, AFO-FR-036; acceptance: AT-019, AT-021, AT-022, AT-041.

## M4 — Autonomous SWE recovery

- [ ] **AFO-T035 [P0]** Implement gate/MCP/Fabro evidence ingestion into typed FailureBundle with version and redaction.  
  Trace: AFO-FR-037, AFO-FR-038, AFO-FR-046; acceptance: AT-026, AT-027, AT-035, AT-036, AT-043.
- [ ] **AFO-T036 [P0]** Add product-vs-factory-vs-infrastructure failure taxonomy and stable cross-attempt fingerprints.  
  Trace: AFO-FR-038, AFO-FR-039, AFO-FR-044; acceptance: AT-026, AT-028, AT-033, AT-035, AT-043.
- [ ] **AFO-T037 [P0]** Implement validated-lesson/known deterministic remedy selector; no LLM when rule is sufficient.  
  Trace: AFO-FR-040; acceptance: AT-029.
- [ ] **AFO-T038 [P0]** Create `afo-recovery-planner` SKILL, role manifest/MCP least-privilege and typed bounded output parser.  
  Trace: AFO-FR-007, AFO-FR-041, AFO-FR-048; acceptance: AT-030, AT-036, AT-045, AT-046.
- [ ] **AFO-T039 [P0]** Build deterministic strategy policy (scope/permissions/material-difference/plan fingerprint).  
  Trace: AFO-FR-042, AFO-FR-046, AFO-FR-048; acceptance: AT-031, AT-032, AT-033, AT-035, AT-036.
- [ ] **AFO-T040 [P0]** Implement independent owner-phase impact mapping and safe local/upstream SWE rework plan executor.  
  Trace: AFO-FR-042, AFO-FR-043, AFO-FR-047; acceptance: AT-023, AT-031, AT-032, AT-033.
- [ ] **AFO-T041 [P0]** Implement cumulative order/phase/strategy/time/token/GPU cost budgets persisted across attempts.  
  Trace: AFO-FR-045; acceptance: AT-034.
- [ ] **AFO-T042 [P0]** Implement duplicate strategy avoidance and explicit anti-loop termination; never repeat same patch unchanged.  
  Trace: AFO-FR-039, AFO-FR-044, AFO-FR-045; acceptance: AT-028, AT-033, AT-034.
- [ ] **AFO-T043 [P0]** Integrate Conductor recovery plan execution with Fabro, checkpoints and independent reinspection.  
  Trace: AFO-FR-043, AFO-FR-047; acceptance: AT-023, AT-031, AT-032.
- [ ] **AFO-T044 [P0]** Test real failing SWE.1/3/4/5/6 gates, conflicting HSI, alternate plan, blocked and READY discrimination.  
  Trace: AFO-FR-046, AFO-FR-048; acceptance: AT-035, AT-036.

## M5 — Factory Maintainer proposals

- [ ] **AFO-T045 [P1]** Create dedicated `afo-factory-maintainer` SKILL and typed proposal/grants distinct from infra fabric-repair.  
  Trace: AFO-FR-007, AFO-FR-016, AFO-FR-049, AFO-FR-050; acceptance: AT-030, AT-043, AT-045, AT-046.
- [ ] **AFO-T046 [P1]** Build isolated repair source worktree and allowlist with OS confinement/credential separation.  
  Trace: AFO-FR-049, AFO-FR-050; acceptance: AT-043, AT-045, AT-046.
- [ ] **AFO-T047 [P1]** Implement baseline-failing reproducer creation and pre-candidate triage with 004 CAPA linkage.  
  Trace: AFO-FR-051; acceptance: AT-044.
- [ ] **AFO-T048 [P1]** Integrate existing CRE independent promotion gates and append-only candidate records.  
  Trace: AFO-FR-052, AFO-FR-053; acceptance: AT-045, AT-047, AT-048, AT-049.
- [ ] **AFO-T049 [P1]** Implement deterministic broker for proposal branch/PR without giving agents GitHub credentials.  
  Trace: AFO-FR-054; acceptance: AT-049.
- [ ] **AFO-T050 [P0]** Prevent candidate auto merge/deploy, frozen oracle modifications and policy changes by OS and git-diff veto.  
  Trace: AFO-FR-053, AFO-FR-055; acceptance: AT-045, AT-047, AT-048, AT-049, AT-051.
- [ ] **AFO-T051 [P1]** Implement WAITING_EXTERNAL_CHANGE TTL and continued scheduling of unrelated approved orders.  
  Trace: AFO-FR-052, AFO-FR-056, AFO-FR-057; acceptance: AT-039, AT-047, AT-048, AT-050.
- [ ] **AFO-T052 [P1]** Test malicious maintainer patch, failed holdout, unapproved PR, credential exfiltration and safe proposal.  
  Trace: AFO-FR-055; acceptance: AT-048, AT-051.
- [ ] **AFO-T053 [P1]** Test source change validated but human approval pending; queue continues and original order handled safely.  
  Trace: AFO-FR-056, AFO-FR-057; acceptance: AT-039, AT-050.

## M6 — DLQ/dashboard/alerts/release evidence

- [ ] **AFO-T054 [P0]** Implement idempotent immutable dead-letter case creation after safe BLOCKED finalization.  
  Trace: AFO-FR-058, AFO-FR-059; acceptance: AT-037, AT-038, AT-039, AT-040.
- [ ] **AFO-T055 [P0]** Implement alert outbox, rate-limited dedup notification and local fallback.  
  Trace: AFO-FR-059, AFO-FR-060; acceptance: AT-037, AT-038, AT-040, AT-042.
- [ ] **AFO-T056 [P0]** Extend existing FastAPI read-only endpoints for queue/events/recovery/operations, with pagination/auth.  
  Trace: AFO-FR-061, AFO-FR-062; acceptance: AT-052, AT-053, AT-054, AT-055.
- [ ] **AFO-T057 [P0]** Add mobile/desktop existing dashboard Autonomy view and live read-only trace drilldown.  
  Trace: AFO-FR-061, AFO-FR-063; acceptance: AT-042, AT-052, AT-055.
- [ ] **AFO-T058 [P0]** Implement authenticated operator pause/drain/resume (CSRF or CLI guard), separate from agent MCP.  
  Trace: AFO-FR-026, AFO-FR-062; acceptance: AT-014, AT-053, AT-054.
- [ ] **AFO-T059 [P0]** Extend existing deterministic Release Manager inventory with AFO evidence files and hashes.  
  Trace: AFO-FR-064; acceptance: AT-037, AT-056.
- [ ] **AFO-T060 [P0]** Test queue isolation and per-order terminality with mixed failed/healthy workloads.  
  Trace: AFO-FR-058; acceptance: AT-037, AT-038, AT-039.
- [ ] **AFO-T061 [P0]** Test PII/credential redaction, forged events, unauthorized dashboard writes and audit preservation.  
  Trace: AFO-FR-063; acceptance: AT-042, AT-055.

## M7 — Real pilot/soak/SLO

- [ ] **AFO-T062 [P0]** Add AFO-KPI provenance and separate service uptime, package READY yield and valid terminal metrics.  
  Trace: AFO-FR-008, AFO-FR-065, AFO-FR-066; acceptance: AT-037, AT-057, AT-058.
- [ ] **AFO-T063 [P0]** Implement homogeneous-cohort sampling, Wilson CI and UNKNOWN statuses via existing KPI/CRE services.  
  Trace: AFO-FR-065, AFO-FR-066; acceptance: AT-057, AT-058.
- [ ] **AFO-T064 [P0]** Create readiness state machine separating implementation, pilot eligibility, active eligibility and SLO evidence.  
  Trace: AFO-FR-067, AFO-FR-070; acceptance: AT-059, AT-062, AT-063.
- [ ] **AFO-T065 [P0]** Run negative fault campaign: model outage, Fabro death, MCP errors, DB lock, disk full, queue duplicate, poisoned plan.  
  Trace: AFO-FR-068; acceptance: AT-060, AT-061.
- [ ] **AFO-T066 [P0]** Run real approved local Qwen end-to-end READY + deliberately BLOCKED cases; mark NOT_DEMONSTRATED if not achieved.  
  Trace: AFO-FR-067; acceptance: AT-059, AT-063.
- [ ] **AFO-T067 [P0]** Implement opt-in soak runner and 24h/72h/168h log capture; never fake elapsed real hours.  
  Trace: AFO-FR-069; acceptance: AT-062.
- [ ] **AFO-T068 [P0]** Run operator-authorized 24h, 72h then 168h actual soak; if unavailable, status BLOCKED with instructions.  
  Trace: AFO-FR-069; acceptance: AT-062.
- [ ] **AFO-T069 [P0]** Create system recovery drill matrix and verify zero unreconciled outstanding jobs after tested restarts.  
  Trace: AFO-FR-070, AFO-FR-072; acceptance: AT-054, AT-059, AT-062, AT-063, AT-064.
- [ ] **AFO-T070 [P0]** Create signed human operator readiness review and authorization audit for any ACTIVE mode change.  
  Trace: AFO-FR-071, AFO-FR-072; acceptance: AT-054, AT-063, AT-064, AT-065, AT-066.

## M8 — Integration audit and delivery

- [ ] **AFO-T071 [P0]** Reconcile all implementation APIs/contracts; run spec design check, static checks and full existing 001–004 regression suites.  
  Trace: AFO-FR-002, AFO-FR-005; acceptance: AT-064, AT-065.
- [ ] **AFO-T072 [P0]** Run full 005 acceptance tests and generate FR-task-test-evidence report with honest BLOCKED/NOT_RUN.  
  Trace: AFO-FR-006, AFO-FR-071; acceptance: AT-065, AT-066.
- [ ] **AFO-T073 [P0]** Write headless install/backup/rollback/security/incident/maintenance/operator runbook for actual host.  
  Trace: AFO-FR-064; acceptance: AT-037, AT-056.
- [ ] **AFO-T074 [P0]** Record benchmark/safety limitations, SLO observation gap and immutable release evidence for READY/BLOCKED.  
  Trace: AFO-FR-070; acceptance: AT-059, AT-062, AT-063.
- [ ] **AFO-T075 [P0]** Check Spec Kit analyze + converge, commit/push verified increments, report commit refs and final readiness.  
  Trace: AFO-FR-001, AFO-FR-071; acceptance: AT-065, AT-066.

## Release gating and mandatory task behavior

- Never check a box without real tested evidence; mocks are unit-level only. Host reboot/real-model/168h soak must not be checked until executed.
- If a necessary real Fabro or host capability is unavailable, mark `BLOCKED` with precise code, preserve independent progress and avoid claiming the feature COMPLETE.
- Preserved safety/QA/release policies and independent inspections outrank all availability, cost, throughput or developer convenience goals.
- Agent output terse (`status, artifacts, issues, next_action`); complete reasons and proofs belong in ADRs and evidence.
- CI/PR success is not safety certification and a verified BLOCKED archive is not an accepted software delivery.
