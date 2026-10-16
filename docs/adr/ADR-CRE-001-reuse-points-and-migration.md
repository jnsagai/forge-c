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
