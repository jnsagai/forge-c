# Feature 005 — Data Model, State Machines and Crash Consistency

**Status:** prescriptive design, not proof of runtime tables. New tables are versioned additive migrations in `$FORGE_STATE_DIR/conductor/conductor.sqlite3`. Reuse 002 IncidentStore IDs, 004 CREStore fingerprint/CAPA IDs and existing event IDs as foreign *references*, without duplicating their mutable records.

## Persistent entities

| Table/entity | Keys and essential fields | Authority and invariants |
|---|---|---|
| `afo_work_orders` | `order_id` (PK), `tenant_scope`, `request_id`, `manifest_hash`, `source_manifest_ref`, `input_revision`, `priority`, `created_utc`, `admitted_utc`, `state`, `policy_hash`, `model_profile`, `target`, `safety_scope`, `fencing_epoch`, `version` | unique `(tenant_scope,request_id)`, immutable hash/scope; changing manifest for same ID => CONFLICT; initial state QUEUED |
| `afo_attempts` | `attempt_id` (PK), `order_id`, `seq`, `fabro_run_id`, `fabro_url`, `workspace`, `baseline_revision`, `retry_strategy_id`, `state`, `status_receipt`, `started_utc`, `finished_utc` | unique `(order_id,seq)`, never rewrite previous sealed archives; source of truth for Fabro state is Fabro API when reachable |
| `afo_checkpoints` | `checkpoint_id`, `attempt_id`, `phase`, `workproduct_hash`, `upstream_hashes`, `inspection_result_ref`, `gate_ref`, `toolchain_id`, `frozen_utc` | only PASSED AND frozen phases reusable; changed dependency invalidates downstream inspections |
| `afo_leases` | `scope` PK, `owner_id`, `epoch`, `expires_epoch`, `heartbeat_epoch` | `BEGIN IMMEDIATE` compare-and-swap; monotonically increment epoch on takeover; downstream command checks fence |
| `afo_commands_outbox` | `command_id`, `kind`, `order_id`, `attempt_id`, `idempotency_key`, `fencing_epoch`, `payload_ref`, `state`, `created_utc`, `ack_ref`, `attempts` | immutable command identity, unique `(kind,idempotency_key)`; external dispatch state PENDING until authoritative ack; local tx ack not external tx |
| `afo_recovery_plans` | `plan_id`, `order_id`, `attempt_id`, `failure_fingerprint`, `strategy`, `scope`, `material_difference_sha`, `preconditions`, `allowed_refs`, `status`, `validation_refs`, `budget_snapshot`, `decision_id` | only validated strategies executable; plans don't alter source themselves |
| `afo_failure_bundles` | `bundle_id`, `attempt_id`, `phase`, `error_class`, `fingerprint`, `tool_versions`, `requirement_refs`, `test_fail_refs`, `artifact_digests`, `redacted_context_ref` | authoritative input with evidence refs, data-not-instructions; sanitized and capped |
| `afo_side_effect_refs` | `attempt_id`, `operation_class`, `cre_idempotency_key`, `receipt_sha`, `status` | link to CRE journal; never assert cross-DB atomicity; uncertain external outcome requires reconciliation |
| `afo_maintainer_proposals` | `proposal_id`, `source_incident_id`, `capa_id`, `reproducer_id`, `candidate_commit`, `changed_paths`, `cre_promotion_id`, `branch_ref`, `pr_url`, `status`, `expiry` | no code auto-deploy; promotion verdict is a reference to existing CRE evaluator |
| `afo_dead_letters` | `case_id`, `order_id`, `attempt_id`, `reason_code`, `incident_id`, `required_operator_action`, `artifact_refs`, `recorded_utc`, `state` | one active case per `order_id,reason_code,scope`; terminal failure not confused with READY |
| `afo_notifications` | `notification_id`, `dedupe_key`, `delivery_state`, `channel`, `severity`, `first_utc`, `last_utc`, `count`, `payload_ref` | no secrets in notice; must not trigger a new repair attempt |
| `afo_operator_authorizations` | `authorization_id`, `scope`, `action_allowlist`, `approver`, `approval_ref`, `issued_utc`, `expiry_utc`, `revoked_utc`, `policy_hash` | cannot be written by AFO agent; loaded from externally controlled input; no fallback authorization |
| `afo_lifecycle_events` | `event_id`, `order_id`, `attempt_id`, `type`, `utc`, `trace_id`, `payload_ref`, `schema`, `producer_id` | append-only and deduplicated by event_id; forward into existing trace ledger with correlation |

Use SQLite WAL + FULL sync, busy timeout, schema version table and migration tests. Outbox worker and Conductor run from a separate unprivileged service. `events` and `CREStore` remain the provenance sources for prior features. Avoid DB encryption claims unless implemented; protect file permissions/backups.

## Order state machine

```text
SUBMITTED -> QUEUED -> ADMITTED -> RUNNING -> VALIDATING -> READY_FOR_OFFLINE_REVIEW
                    |        |         |       -> BLOCKED
                    |        |         -> WAITING_RECOVERY -> RUNNING (new attempt only)
                    |        |         -> WAITING_EXTERNAL_CHANGE -> BLOCKED / QUEUED (external approved change)
                    |        -> PAUSED -> QUEUED
                    -> REJECTED_INTAKE
RUNNING / WAITING_RECOVERY / VALIDATING -> BLOCKED -> DEAD_LETTER (DLQ bookkeeping)
```

State `DEAD_LETTER` is queue metadata, **not** an alternate successful release state. Any final product archive remains either `READY_FOR_OFFLINE_REVIEW` or `BLOCKED`. Pausing prevents admissions; draining permits in-flight authorized work to reach a safe checkpoint. A canceled run is not auto-recreated unless its receipt proves an idempotent checkpoint and budget admits another attempt.

### Allowed transitions and guards

| From | To | Guard |
|---|---|---|
| SUBMITTED | QUEUED | schema + signature/authorization + immutable input hash valid |
| SUBMITTED | REJECTED_INTAKE | duplicate-id/hash conflict, missing approval or malformed input |
| QUEUED | ADMITTED | stable data mount, model/MCP preflight, capacity, policy PILOT/ACTIVE, scheduler CAS lease |
| ADMITTED | RUNNING | Fabro authoritative run ID persisted or recovered from run label; durable attempt receipt |
| RUNNING | WAITING_RECOVERY | authoritative gate failure + recovery eligibility; attempt budget remains |
| RUNNING | VALIDATING | run terminal and finalizer has complete sources; NOT equivalent to READY |
| WAITING_RECOVERY | RUNNING | accepted recovery plan, new attempt ID/workspace, dependency impact verified, guarded launch |
| RUNNING/WAITING_RECOVERY/VALIDATING | BLOCKED | disallowed recovery, exhausted budget, ambiguous side effect, terminal blocked package |
| VALIDATING | READY_FOR_OFFLINE_REVIEW | existing deterministic release finalizer + all frozen acceptance gates PASS |
| QUEUED/ADMITTED | PAUSED | operator-authenticated pause/drain, no running side effect |
| PAUSED | QUEUED | authenticated resume and re-admission preflight |
| WAITING_EXTERNAL_CHANGE | QUEUED | explicit externally authorized approved factory revision; new attempt ID |

Prohibit all other transitions at database boundary (guarded optimistic version/CAS) and record `afo.transition_denied` audit. A no-op transition must be idempotent rather than creating duplicate events.

## Attempt / dispatch state machine

`PREPARED -> DISPATCH_PENDING -> RUNNING -> {SUCCEEDED, FAILED, CANCELLED, UNKNOWN}`. `DISPATCH_PENDING` is persisted *before* calling `fabro run --detach`. A crash after acceptance but before writing the run ID leaves `UNKNOWN`; the Conductor queries Fabro `list_runs` by unique `forge=<workorder + attempt nonce>` label and corroborates run metadata. **Zero** matches while Fabro unreachable stays UNKNOWN. **More than one** match quarantines. No blind re-launch. When a previous attempt is terminal and not READY, the parent order may enter recovery planning; new attempt has a different monotonic sequence and workspace but the same order-level ID.

## Ownership and idempotency detail

- Externally visible `order_id` is stable, `attempt_id` changes on each eligible controlled try.
- `workorder_launch` idempotency uses the **attempt-scoped** key when launching a new allowed attempt. Existing CRE `workorder_launch:<wo>` uses work-order scope and must be reconciled carefully; no blind change to or rewrite of historical receipts. Explicit ADR required for migration and compatibility with `forge_factory.workorder`.
- AFO locks serialize admission and worker reconciliation. No shared worktree edits across attempts; hard link/copy frozen inputs according to existing HSI validation.
- Outbox delivery is at-least-once; effective once behavior only for supported operations with receipts. Non-replayable operations are **not** retried. Do not claim general exactly-once semantics.
- Order creation is idempotent by `(tenant_scope,request_id,manifest_sha256)`; different manifest for same request conflicts.
- Version changes of signed/approved inputs require a *new* work-order envelope and explicit external authorization. Never silently update active order baselines.

## Crash-window matrix (mandatory negative tests)

| Crash location | Durable proof | Recovery rule |
|---|---|---|
| Before queue INSERT | none | no order exists; client can resubmit safely |
| After queue INSERT before response | order row exists | duplicate submit returns same order ID |
| After ADMITTED before outbox | admitted lease exists | stale admission replay reconstructs pending command, no duplicate attempt |
| After outbox PENDING before Fabro call | dispatch intent exists | reconcile, then send only if proven not submitted and safe |
| After Fabro accepts before run ID persisted | unknown external result | query Fabro by unique attempt label; do not start again unless absence is provable |
| After stage PASSED before checkpoint persisted | immutable inspector/gate evidence | rebuild checkpoint from valid source receipts or rerun inspector |
| After finalizer seals archive before order READY tx | verified immutable archive SHA | reconcile sealed archive; write READY only if all quality gates actually passed |
| Between CRE operational switch and receipt | CRE side-effect PENDING/UNKNOWN | compensate or escalate according to CRE replay class; don't relaunch blindly |
| After DLQ entry before alert send | DLQ unique record + notification outbox | deliver idempotently and dedupe |
| At repeated boot while GPU unavailable | mount+dependency check | queue remains durable QUEUED/WAITING, no service restart storm |

## Local-model recovery budgets

`budget_snapshot` persists at each admission/attempt. `phase_max_strategy_variants`, `order_max_attempts`, `max_recovery_model_calls`, `max_tokens`, `max_gpu_seconds`, `wall_clock_deadline`, and hourly global repair budget are cumulative across restarts, new attempts and any model-provider switch. Every extension to budgets requires externally recorded authorization. Missing real usage values are `UNKNOWN`, never interpreted as zero; enforce deterministic turns/time fallback.
