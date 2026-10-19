# ADR-AFO-002: launch identity, idempotency keys and run reconciliation

- Status: accepted for implementation (Feature 005, M3: AFO-T026/T027)
- Date: 2026-10-19

## Audit of Fabro 0.362 (observed, 2026-10-19)

- **Launch.** `fabro run <toml> --detach --auto-approve --environment local --label KEY=VALUE` (the label is
  repeatable) prints the run id. The CLI has no server-side idempotency key, so a launch that crashes before the id
  is persisted has an unknown outcome.
- **Run records.** `GET /api/v1/runs` returns `{data, meta}`. Each run carries:
  - `labels` (a dict), e.g. `{"forge": "WO-0002B-STM32N6-RCC-HAL-r164"}`;
  - `lifecycle.status.kind`, with `runnable` (queued; the cloud server runs one at a time), `running` and
    `succeeded` (reason `completed`) seen on the live server;
  - `timestamps.created_at` and `timestamps.completed_at`.
- **`succeeded` is not a quality verdict.** A run that ends in a BLOCKED package also ends `succeeded`. READY comes
  only from the sealed package (AFO-T032), never from the Fabro run status.

## Decision

1. **Attempt identity.**
   - Each AFO attempt launches its own factory work order, named `WO-AFO-<order hash>-a<seq>`, in its own
     workspace.
   - Labels: `forge=<that name>`, `afo_attempt=<attempt_id>` and `afo_nonce=<random 16 hex>`. The nonce is persisted
     in the attempt record before the CLI is called.
2. **CRE compatibility.**
   - The existing CRE journal key `workorder_launch:<wo>` stays unchanged. Because each attempt has its own work-order
     name, that key is attempt-scoped by construction, so no historical receipt is migrated or rewritten.
   - The AFO outbox key is `launch:<attempt_id>`.
3. **Launch protocol.** All in one transaction, before calling Fabro: outbox command `PENDING → IN_FLIGHT`, attempt
   `PREPARED → DISPATCH_PENDING`, and the nonce and dispatch time recorded. Then the launch. Then, in a second
   transaction: attempt `RUNNING` with `fabro_run_id`, command `ACKED`, order `ADMITTED → RUNNING`.
4. **Reconciliation after a crash** (a command `IN_FLIGHT` with no run id): list Fabro runs and match
   `afo_attempt` plus `afo_nonce`.
   - **Exactly one match:** adopt it.
   - **More than one:** the command is QUARANTINED and the order BLOCKED (no guess).
   - **None, Fabro reachable and the dispatch older than the grace period (180 s):** proven not submitted. The command
     returns to PENDING for one more launch.
   - **None, but Fabro unreachable or still inside the grace period:** UNKNOWN. Nothing is relaunched.
5. **Run-state reconciler.**
   - `runnable` or `running` → still RUNNING.
   - `succeeded`, `failed` or `cancelled` → attempt SUCCEEDED/FAILED/CANCELLED. The order goes to VALIDATING, where
     the package decides READY or BLOCKED.
   - Run absent on a reachable server → attempt UNKNOWN, then BLOCKED, never relaunched blindly.
   - Server unreachable → no change.
6. **Effectively-once, not exactly-once.** The outbox is at-least-once. Duplicate launches are prevented by the
   persisted nonce and the reconciliation above. No exactly-once execution is claimed.

## Consequences

- `workorder.run` gains an optional `labels` argument. Existing callers are unchanged.
- Recovery (M4) always creates a new attempt, so never a second launch of the same attempt.
- A reboot with a run in flight (AFO-T034) needs an owner-authorized maintenance window and stays BLOCKED until then.
