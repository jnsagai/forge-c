# Feature 005 — Executable Acceptance Test Catalogue

**Test status:** scenarios are defined, NOT executed. Each result must be stored as a versioned machine-readable record with real tool versions, commands, stdout/stderr artifact digest and outcomes `PASS|FAIL|BLOCKED|NOT_RUN`; never fabricate live-host evidence. All state-mutating fault injections must occur in an isolated fixture or within owner-authorized maintenance windows.

## Test harness and fixtures

- Use Python pytest + synthetic clock for unit state-machine tests, controlled subprocess crash harness for integration and real systemd/Fabro/Ollama/Python services for live checks.
- Keep frozen baseline/holdout fixtures unchanged; a candidate worktree never sees protected holdout source to write it.
- Use one valid generic RCC example, real STM32N6 RCC, deliberately faulty HSI/specification, and proposed GPIO/UART fixture only after 004 CRE-T046 exists.
- Every test logs host/mount/profile, before/after DB hashes, original work-order ID vs attempts, Fabro run IDs, gate results, model costs and notification dedup.
- Mandatory invariants: no fake READY; no double non-replayable side effects; zero protected writes; no agent credentials; no unlimited retry; no escalation of model/data access.

## Scenarios

### G0: Constitution, policy and scope

- **AT-064 — constitution invariants:** Attempt to enable forbidden source auto-deploy or safety approval via AFO policy => validation fails. **Evidence:** command/host/tool refs, captured state transitions and assertion result. **Status:** NOT_RUN.
- **AT-065 — legacy regressions:** 001–004 test suites, design checker, contracts and hard gates still pass unchanged. **Evidence:** command/host/tool refs, captured state transitions and assertion result. **Status:** NOT_RUN.
- **AT-066 — implementation traceability:** Every functional requirement mapped to task and test, every completed task has executed evidence hash, no invented PASS. **Evidence:** command/host/tool refs, captured state transitions and assertion result. **Status:** NOT_RUN.

### G1: Host 24/7 and services

- **AT-001 — systemd dry-run render:** Unit files parse without starting services, credentials remain external, service names and port configuration match pinned runtime. **Evidence:** command/host/tool refs, captured state transitions and assertion result. **Status:** NOT_RUN.
- **AT-002 — headless logout:** With linger explicitly configured by operator, user session logout does not stop supervised runtime services. **Evidence:** command/host/tool refs, captured state transitions and assertion result. **Status:** NOT_RUN.
- **AT-003 — supervisor Conductor crash:** SIGKILL Conductor during idle; independent watchdog/systemd restarts it; queue DB consistent, no LLM health calls. **Evidence:** command/host/tool refs, captured state transitions and assertion result. **Status:** NOT_RUN.
- **AT-004 — Fabro service crash:** Kill idle Fabro; restart under systemd; existing 002 incident and CRE classification preserved. **Evidence:** command/host/tool refs, captured state transitions and assertion result. **Status:** NOT_RUN.
- **AT-005 — model server crash:** Kill Ollama/gateway; dependent admission pauses while unhealthy and resumes only after readiness restoration. **Evidence:** command/host/tool refs, captured state transitions and assertion result. **Status:** NOT_RUN.
- **AT-006 — absent mount:** Remove/unmount data volume in approved test; no writes to shadow directory and work admission fails closed. **Evidence:** command/host/tool refs, captured state transitions and assertion result. **Status:** NOT_RUN.
- **AT-007 — service start storm:** Force repeated crash; StartLimit/backoff protects host, incidents recorded, no retry storm. **Evidence:** command/host/tool refs, captured state transitions and assertion result. **Status:** NOT_RUN.
- **AT-008 — boot without login:** Authorized host reboot without GUI login reactivates services, waiting queue persisted. **Evidence:** command/host/tool refs, captured state transitions and assertion result. **Status:** NOT_RUN.
- **AT-009 — watchdog stalled Conductor:** Block Conductor heartbeat without killing process; independent watchdog notices and recovers/alerts. **Evidence:** command/host/tool refs, captured state transitions and assertion result. **Status:** NOT_RUN.
- **AT-046 — unprivileged credentials:** Verify verifier/repair/account boundaries: no access to unrelated credentials, source/evidence immutable. **Evidence:** command/host/tool refs, captured state transitions and assertion result. **Status:** NOT_RUN.

### G2: Durable intake and scheduling

- **AT-010 — valid approved order:** Submit a signed/approved manifest; exactly one QUEUED record and stable ID. **Evidence:** command/host/tool refs, captured state transitions and assertion result. **Status:** NOT_RUN.
- **AT-011 — same request replay:** Retry exact submit after a simulated lost response; same order ID, no new attempt or dispatch. **Evidence:** command/host/tool refs, captured state transitions and assertion result. **Status:** NOT_RUN.
- **AT-012 — hash conflict:** Reuse request ID with different manifest hash; deterministic conflict, no overwrite. **Evidence:** command/host/tool refs, captured state transitions and assertion result. **Status:** NOT_RUN.
- **AT-013 — parallel submit:** Two concurrent submitters use same key; one persistent order only. **Evidence:** command/host/tool refs, captured state transitions and assertion result. **Status:** NOT_RUN.
- **AT-014 — worker capacity:** Two jobs and capacity one; only one admitted, second queued; next starts after capacity releases. **Evidence:** command/host/tool refs, captured state transitions and assertion result. **Status:** NOT_RUN.
- **AT-015 — idle zero models:** Empty queue 100 control cycles produces zero inference calls/tokens; healthy does not mean RUNNING. **Evidence:** command/host/tool refs, captured state transitions and assertion result. **Status:** NOT_RUN.
- **AT-016 — queue starvation/fairness:** Mixed priorities; eligible lower priority eventually scheduled within configured aging bound. **Evidence:** command/host/tool refs, captured state transitions and assertion result. **Status:** NOT_RUN.

### G3: Reconciliation and exactly-once logical accounting

- **AT-017 — launch-before-call crash:** Persist outbox, crash before Fabro call; restarted conductor invokes once only with fresh fence. **Evidence:** command/host/tool refs, captured state transitions and assertion result. **Status:** NOT_RUN.
- **AT-018 — launch-after-accept crash:** Fabro accepts run, process dies before run ID stored; reconcile by attempt nonce instead of launching second. **Evidence:** command/host/tool refs, captured state transitions and assertion result. **Status:** NOT_RUN.
- **AT-019 — Fabro unreachable and unknown:** No authoritative answer; state UNKNOWN/REQUIRES_OFFLINE_ATTENTION, no blind repeat. **Evidence:** command/host/tool refs, captured state transitions and assertion result. **Status:** NOT_RUN.
- **AT-020 — duplicate Fabro run label:** Two runs match same nonce; quarantine/escalate and preserve both histories. **Evidence:** command/host/tool refs, captured state transitions and assertion result. **Status:** NOT_RUN.
- **AT-021 — lease takeover:** Two conductor processes race and first worker restarts; only current fence may act; no duplicate dispatch. **Evidence:** command/host/tool refs, captured state transitions and assertion result. **Status:** NOT_RUN.
- **AT-022 — reboot mid SWE phase:** Reconcile active stage or terminate safely, use only verified work-order checkpoint, preserve prior evidence. **Evidence:** command/host/tool refs, captured state transitions and assertion result. **Status:** NOT_RUN.
- **AT-023 — downstream invalidation:** Change SWE.2 frozen hash; downstream previously passed verdicts no longer accepted without reinspection. **Evidence:** command/host/tool refs, captured state transitions and assertion result. **Status:** NOT_RUN.
- **AT-024 — archive-before-status crash:** Sealed READY/BLOCKED archive exists before queue tx; restart checks hash and gates, writes correct outcome once. **Evidence:** command/host/tool refs, captured state transitions and assertion result. **Status:** NOT_RUN.
- **AT-025 — non-replayable effect:** Journal indicates PENDING flashing or approval; no automatic replay in any mode. **Evidence:** command/host/tool refs, captured state transitions and assertion result. **Status:** NOT_RUN.

### G4: Autonomous SWE diagnosis and replanning

- **AT-026 — real compiler rejection:** SWE.3 compile failure parsed from authoritative MCP receipt into PRODUCT_QUALITY; not routed to infra repair. **Evidence:** command/host/tool refs, captured state transitions and assertion result. **Status:** NOT_RUN.
- **AT-027 — independent inspection failure:** Author says PASS but inspector gate FAIL; no READY and typed defect bundle created. **Evidence:** command/host/tool refs, captured state transitions and assertion result. **Status:** NOT_RUN.
- **AT-028 — same fingerprint cross-attempt:** Different UUIDs/timestamps but same phase/check/tool produce one canonical recurring failure mode. **Evidence:** command/host/tool refs, captured state transitions and assertion result. **Status:** NOT_RUN.
- **AT-029 — validated lesson first:** Eligible known signature selects verified deterministic rule, no planning LLM request. **Evidence:** command/host/tool refs, captured state transitions and assertion result. **Status:** NOT_RUN.
- **AT-030 — recovery planner output schema:** Invalid tool grants/plan schema are rejected; sanitized incident text cannot override system policy. **Evidence:** command/host/tool refs, captured state transitions and assertion result. **Status:** NOT_RUN.
- **AT-031 — scoped local rework:** Planner proposes local product draft change; new attempt and unchanged safety baseline; inspector runs independently. **Evidence:** command/host/tool refs, captured state transitions and assertion result. **Status:** NOT_RUN.
- **AT-032 — upstream rework mapping:** Downstream finding routed to owner SWE.1/2; all impacted downstream gates re-run. **Evidence:** command/host/tool refs, captured state transitions and assertion result. **Status:** NOT_RUN.
- **AT-033 — identical strategy:** Two plans with same artifact diffs/signature cannot be repeated indefinitely; terminate or choose different admitted plan. **Evidence:** command/host/tool refs, captured state transitions and assertion result. **Status:** NOT_RUN.
- **AT-034 — cumulative budget and reboot:** After model/time cap reached, restart does not reset budget or attempt count; correct blocked state. **Evidence:** command/host/tool refs, captured state transitions and assertion result. **Status:** NOT_RUN.
- **AT-035 — missing authoritative HSI:** No speculative register behavior; immediate BLOCKED and external review reference. **Evidence:** command/host/tool refs, captured state transitions and assertion result. **Status:** NOT_RUN.
- **AT-036 — model profile authorization:** Planner proposes paid/unapproved model; deny, audit, no external request or new scope. **Evidence:** command/host/tool refs, captured state transitions and assertion result. **Status:** NOT_RUN.

### G5: Maintainer proposals and protected factory evolution

- **AT-043 — source-defect routing:** Factory code bug classified FACTORY_CODE_DEFECT, not product-edit or unrestricted infrastructure repair. **Evidence:** command/host/tool refs, captured state transitions and assertion result. **Status:** NOT_RUN.
- **AT-044 — maintainer reproducer:** Baseline-failing candidate-passing reproducer with tool version/hash accepted; unsupported claim rejected. **Evidence:** command/host/tool refs, captured state transitions and assertion result. **Status:** NOT_RUN.
- **AT-045 — protected-path denial:** Agent tries to edit constitution/CRE policy/holdout/safety/archive: kernel/MCP and diff checks prevent change. **Evidence:** command/host/tool refs, captured state transitions and assertion result. **Status:** NOT_RUN.
- **AT-047 — CRE independent promotion:** Candidate passes independent reproducible tests and can only reach ELIGIBLE_FOR_OFFLINE_REVIEW. **Evidence:** command/host/tool refs, captured state transitions and assertion result. **Status:** NOT_RUN.
- **AT-048 — holdout regression:** Candidate reintroduces solved defect; CRE gate rejects and incumbent stays deployed. **Evidence:** command/host/tool refs, captured state transitions and assertion result. **Status:** NOT_RUN.
- **AT-049 — proposal PR only:** Deterministic broker creates reviewable branch/PR, no merge, no credential exposure to agent. **Evidence:** command/host/tool refs, captured state transitions and assertion result. **Status:** NOT_RUN.
- **AT-050 — human approval pending:** Conductor processes unrelated orders while proposal pending; affected order TTL bounded. **Evidence:** command/host/tool refs, captured state transitions and assertion result. **Status:** NOT_RUN.
- **AT-051 — rejected candidate:** Failed or malicious candidate is quarantined and cannot be retrieved as an approved lesson. **Evidence:** command/host/tool refs, captured state transitions and assertion result. **Status:** NOT_RUN.

### G6: Dead letters, notifications, dashboard and evidence

- **AT-037 — terminal blocked archive:** BLOCKED package has valid evidence SHA and gaps; not counted as READY engineering success. **Evidence:** command/host/tool refs, captured state transitions and assertion result. **Status:** NOT_RUN.
- **AT-038 — DLQ exact once:** Repeated finalizer callback or restart produces one DLQ record and idempotent notifications. **Evidence:** command/host/tool refs, captured state transitions and assertion result. **Status:** NOT_RUN.
- **AT-039 — continue other work:** One order blocked on external approval; unrelated approved order continues and may become READY. **Evidence:** command/host/tool refs, captured state transitions and assertion result. **Status:** NOT_RUN.
- **AT-040 — unknown side-effect stop:** Unknown outcome creates readable case, does not claim successful recovery. **Evidence:** command/host/tool refs, captured state transitions and assertion result. **Status:** NOT_RUN.
- **AT-041 — queue event replay:** Outbox and event replay recreate same state, status and totals without duplicate processing. **Evidence:** command/host/tool refs, captured state transitions and assertion result. **Status:** NOT_RUN.
- **AT-042 — secrets and privacy:** Trace/notification/dashboard omit hidden reasoning, credentials and forbidden raw payloads. **Evidence:** command/host/tool refs, captured state transitions and assertion result. **Status:** NOT_RUN.
- **AT-052 — dashboard read-only:** Authorized reader sees status, queues, full attribution; cannot change capture or service policies. **Evidence:** command/host/tool refs, captured state transitions and assertion result. **Status:** NOT_RUN.
- **AT-053 — operator pause and drain:** Authorized action stops admissions but safely drains running work; audited and can resume. **Evidence:** command/host/tool refs, captured state transitions and assertion result. **Status:** NOT_RUN.
- **AT-054 — authorization negative:** Unauthenticated or forged pause/resume/retry or policy promotion denied with audit. **Evidence:** command/host/tool refs, captured state transitions and assertion result. **Status:** NOT_RUN.
- **AT-055 — capture vs display:** User hides audit trace in display; audit data still captured and only appropriate roles can query. **Evidence:** command/host/tool refs, captured state transitions and assertion result. **Status:** NOT_RUN.
- **AT-056 — packaged AFO evidence:** Both READY and BLOCKED archives include queue attempts, recovery plans, service/context versions and hashes. **Evidence:** command/host/tool refs, captured state transitions and assertion result. **Status:** NOT_RUN.

### G7: Measurement, readiness and verification

- **AT-057 — separate KPI semantics:** A valid BLOCKED archive increments terminal counter but not READY accepted yield; source refs included. **Evidence:** command/host/tool refs, captured state transitions and assertion result. **Status:** NOT_RUN.
- **AT-058 — denominator and CI:** Zero-success small cohort reports uncertainty, unknown usage never zero, one work order with many attempts not many orders. **Evidence:** command/host/tool refs, captured state transitions and assertion result. **Status:** NOT_RUN.
- **AT-059 — pilot readiness negative:** Missing host reboot/real READY/owner authorization yields NOT_DEMONSTRATED even when unit tests PASS. **Evidence:** command/host/tool refs, captured state transitions and assertion result. **Status:** NOT_RUN.
- **AT-060 — real model trial positive:** Real approved local Qwen run reaches READY with six independent phases and verified archive; otherwise BLOCKED evidence. **Evidence:** command/host/tool refs, captured state transitions and assertion result. **Status:** NOT_RUN.
- **AT-061 — real model negative:** Real intentionally bad input results in BLOCKED without false READY or endless retry. **Evidence:** command/host/tool refs, captured state transitions and assertion result. **Status:** NOT_RUN.
- **AT-062 — 168h actual soak:** Timestamped wall-clock intervals from real host demonstrate uninterrupted monitored period; shortened/fake-clock test not accepted. **Evidence:** command/host/tool refs, captured state transitions and assertion result. **Status:** NOT_RUN.
- **AT-063 — reliability operating envelope:** PILOT/ACTIVE mode only with external authorization, no CRE implicit switch, runbook accepted and SLO math sourced. **Evidence:** command/host/tool refs, captured state transitions and assertion result. **Status:** NOT_RUN.

## Release and readiness acceptance gates

1. Unit/contract/negative policy checks pass without mutable production state or service credentials.
2. 001–004 suites regress cleanly, including maintenance-policy guard and CRE promotion gate; no relaxed tests.
3. Real Fabro + model + MCP pilot proves *one genuine READY* and an intentionally BLOCKED package before claiming engineering-success readiness. Verified BLOCKED counts as terminal availability only.
4. Real boot/logout/mount/restart drills prove headless operation; if owner approval is missing, mark readiness NOT_DEMONSTRATED rather than silently executing the drill.
5. All P0 requirements have evidenced tests and code, no unresolved P0 gaps, operator acceptance authorizes any PILOT/ACTIVE mode; 168h is genuine elapsed time, not accelerated simulation.
6. AFO mode and readiness/SLO mode are separately visible: neither implies ISO 26262 approval or autonomous production release.
