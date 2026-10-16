# Forge-C CRE (feature 004) — operator runbook

CRE is an additive reliability layer on the 002 control plane (supervisor, incident DB, event ledger, repair,
lessons, dashboard, finalizer) and the 003 KPIs. It is deterministic and model-free. The configured mode is
**OBSERVE_ONLY**: CRE records, classifies, measures, verifies and proposes; it never deploys code or changes a
policy. Nothing here grants a safety approval; packages stay `READY_FOR_OFFLINE_REVIEW` / `BLOCKED`.

## 1. Reproducible setup (Ubuntu 22.04/24.04, as used on the reference host)

1. Toolchain and services as in `docs/` 002 setup (`scripts/forge_services.sh start`, systemd user unit
   `forge-supervisor`). Versions are pinned in `evidence/cre/baseline/baseline-latest.json` (`tool_versions`).
2. `. scripts/forge-env.sh` (venv, `FORGE_STATE_DIR`, `FORGE_DATA_ROOT`).
3. Baseline check: `python -m forge_factory.reliability.baseline` (all suites; restores regenerated evidence).
4. Capability audit: `python -m forge_factory.reliability.audit` → `docs/cre-capability-matrix.md`.
5. CRE tables are created by versioned additive migrations in `state/supervisor/incidents.sqlite3` on first use
   (`cre_schema_version`); 002 tables are never altered.

## 2. Routine operation (all commands from `factory/python`)

| Purpose | Command | Output |
|---|---|---|
| Import failure observations (all work orders + incidents) | `python -m forge_factory.reliability.observe` | failure registry, recurring modes |
| CAPA cycle on the frozen reproducers | `python -m forge_factory.reliability.history` | CAPA states, lessons |
| Reliability metrics (CRE-R01..R10, reused K16/K17) | `python -m forge_factory.reliability.metrics` | `evidence/cre/metrics/` |
| Benchmark golden + holdout on a revision | `python -m forge_factory.reliability.benchmark HEAD` | per-case PASS/FAIL |
| Evaluate a factory candidate (offline review only) | `python -m forge_factory.reliability.promotion <cand> <base> [--kind FIX --reproducer RPR-00x]` | decision record |
| Fault-injection campaign | `python -m forge_factory.reliability.faults` | `evidence/cre/faults/` |
| Local-model E2E evidence | `python -m forge_factory.reliability.e2e` | `evidence/cre/e2e/` |
| Traceability matrix | `python -m forge_factory.reliability.trace` | `specs/004-…/traceability.csv` |
| Readiness assessment | `python -m forge_factory.reliability.readiness` | `evidence/cre/readiness-assessment.json` |

The dashboard (`python -m forge_factory.dashboard.app --port 8765`) shows the read-only **Reliability** section;
`/api/v1/reliability/*` endpoints never write. Security denials are visible to the auditor role only.

## 3. Restart

* Supervisor: `systemctl --user restart forge-supervisor`. The CRE hook runs inside each poll; any CRE error is
  contained (`cre hook degraded` WARN event) and supervision continues. A corrupted `checkpoint.json` is quarantined
  (`checkpoint.corrupt-<epoch>.json`) and counting restarts; the audit channel records it.
* Budgets survive restarts: retry attempts, breaker state, recovery FSM and leases live in SQLite (WAL,
  synchronous=FULL); a `NON_REPLAYABLE` action found `PENDING` after a crash is never re-executed.
* Locked/unavailable CRE DB: operations fail closed after `FORGE_CRE_DB_TIMEOUT_S` (default 30 s).

## 4. Rollback

* Reversible operational actions (`restart_dashboard`, `restart_mcp_server`, `restart_llm_gateway`, `drain_queue`,
  `restart_collector`) run only in `ACTIVE` mode with an `authorization` block in
  `config/factory/reliability-policy.yaml`. They switch the infra runtime repo atomically (CAS) and roll back to the
  last good commit on degraded health; linked lessons are retracted; released archives are hash-checked unchanged.
* Factory source changes are never rolled forward automatically. A rejected or reverted candidate leaves `main`
  untouched; the decision record stays in `cre_promotion_decisions` (append-only).

## 5. Escalation (offline attention)

| Signal | Meaning | Owner action |
|---|---|---|
| incident `REQUIRES_OFFLINE_ATTENTION` | budget exhausted or fault outside automatic scope (disk, RAM, policy) | fix the environment; recurrence opens a new linked incident |
| CAPA `REOPENED` | a recurrence after a verified fix (same error code + operation) | re-triage: new reproducer + fix, or reject with reason |
| CAPA `CAPA_ATTEMPTS_EXHAUSTED` | three unresolved verifications | offline root-cause analysis |
| promotion `INCONCLUSIVE` | a required gate could not run (e.g. no reproducer for a FIX) | supply the missing evidence |
| `cre.security_denial` | protected path change by a candidate/action | review the candidate; never weaken the policy |
| `cre.spc_signal` | diagnostic only (needs a frozen calibration) | investigate; gates are never auto-tuned |

## 6. Approval restrictions

* Mode changes to `PILOT`/`ACTIVE` require the policy `authorization` block (runbook reference, approver, date);
  invalid or weakened policies are rejected and the last good policy stays active.
* Protected paths (policies, checklists, release manager, evidence, specs 001–003, 004 contracts,
  `tests/reliability/**`) are denied to candidates and actions (OS read-only in sandboxes, git-diff veto).
* No AI or CRE component signs off safety, ASPICE capability or production release.

## 7. Data-quality audit notes

* Observations are append-only; a classifier change (`CLASSIFIER_VERSION`) retracts superseded records with an audit
  row (two such corrections happened live: cre-rules-1.1, 1.2).
* Historical attempts lack a recorded factory revision: it is ESTIMATED as the last commit before launch; new work
  orders record `factory_revision` exactly.
* Cloud token usage is attributed to attempts by time window (ESTIMATED); local compute cost is UNKNOWN.
* Attempts are not independent and the factory changed between most of them: intervals are descriptive, cohorts are
  never pooled across model/provider/mode.
