# ADR-CRE-001: Reuse points for feature 004 and storage migration

Status: accepted (2026-10-16) · Feature: 004-continuous-reliability-engineering · Task: CRE-T003

## Context
The CRE-T001 audit (`docs/cre-capability-matrix.md`) found the 002 control plane implemented and live: supervisor
(1,760 model-free polls), incident store, router, Fabro-independent repair dispatch, lessons store, event ledger,
KPI engine (K01–K20), dashboard and finalizer. Missing: a cross-run failure registry, CAPA, benchmark/holdout,
independent promotion of factory changes, reliability statistics and a replay classification of side effects.

## Decision
CRE is one additive package, `factory/python/forge_factory/reliability/`, that extends existing components:

| Need | Reuses | Extension (no parallel component) |
|---|---|---|
| Durable state | `state/supervisor/incidents.sqlite3` (002 incident DB) | New tables created by a versioned migration (`cre_schema_version`); 002 tables untouched; history tables append-only by trigger |
| Events | 002 event ledger (`events.emit` → JSONL → collector → `events.sqlite3`) | Typed CRE payloads stored append-only (`cre_events`), mirrored as 002-envelope events with `payload_ref: cre-event:<id>`; the 002 contract (`schema_version` 0.4, closed) is not changed |
| Monitoring | supervisor poll loop, router, store, leases | Supervisor records CRE observations for its incidents; router gains CRE fingerprints (cross-run) and jitter; breaker/retry admission are CRE modules the router consults |
| Work-order failures | per-workspace gate log, defect register, tool results, package gaps (read-only) | Deterministic importer → failure observations (no workspace is modified) |
| Repair candidates | `repair/promotion.py` worktrees, protected-path checks, CAS switch/rollback | CRE promotion gate adds reproducer, regression, holdout and decision record for *factory source* candidates |
| Lessons | `knowledge/store.py` (VALIDATED-only retrieval, retraction) | Additive metadata: `capa_id`, `reproducer_id`, `prevention_test_id`, `root_cause_status`, `affected_versions` |
| Metrics | KPI source events (`kpi/sources.py`), K16/K17 unchanged | CRE-R01..R08 namespace with Wilson intervals and data status |
| Release | `release/finalize.py` | `reliability/` bundle in READY and BLOCKED packages |
| UI | `dashboard/app.py` | Read-only `/api/v1/reliability/*` + Reliability page |

Migration rule: additive only (new tables/columns with defaults); imported historical records enter as
`OBSERVED` with root cause `UNKNOWN`; nothing is back-dated to `VERIFIED` (AT-006).

## Consequences
One database, one ledger, one supervisor, one packager. CRE can be disabled by policy mode without schema rollback.
Dependency limits recorded in the matrix (C02 Fabro-native crash resume; C05 repair scope = runtime config) bound
what D2/D7 can show on real infrastructure.

## Review of 002 changes made during CRE (CRE-T054, 2026-10-16)
Two 002 behaviours were changed because CRE tests found defects in them; both keep the 002 contracts:

| Change | Finding | Why it is consistent with 002 | Regression coverage |
|---|---|---|---|
| `supervisor/router.py`: fingerprints whose incident went to `REQUIRES_OFFLINE_ATTENTION` are *held* while the fault is unbroken | a permanent non-repairable fault (disk full) opened a new incident on every poll after the first went terminal | 002 T019 says a *recurrence* opens a new linked incident; an unbroken fault is not a recurrence. A recurrence after `stable_polls_for_recovery` healthy polls still opens a new incident linked by `previous_incident_id` | `test_cre_d2_recovery.py::test_unbroken_fault_is_one_incident…`, `test_m3_supervisor.py` (unchanged, passing) |
| `supervisor/service.py`: a corrupted `checkpoint.json` is quarantined and counting restarts | the supervisor crashed at start on a corrupted checkpoint (fault campaign F08) | 002 T024 requires watchdog/reboot resume; crash-looping on bad state violates it. The event is audited (`audit` WARN) | fault campaign F08, `test_t024_systemd.py` |
| `supervisor/service.py`: `FORGE_SUPERVISOR_NO_DISPATCH=1` in the unit environment suspends repair dispatch (same effect as the existing `--no-dispatch` flag) | the owner-authorized live drill (CRE-T048) must not start the model-based repair agent, and the systemd unit has no per-run arguments | detection, triage, incident lifecycle and zero-model-call health checks are unchanged; only dispatch is skipped, reversibly | `test_cre_d7_drill.py` (live record: incident detected and RESOLVED, 0 model calls) |

Also changed for testability without behaviour change: `test_t009_inspection.py` copies checklists into a writable
temp tree (the hardened promotion sandbox exposed that `copytree` preserved read-only bits).
