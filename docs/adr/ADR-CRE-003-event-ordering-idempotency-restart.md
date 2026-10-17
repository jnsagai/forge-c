# ADR-CRE-003: Event ordering, idempotency and restart semantics

Status: accepted (2026-10-16) · Tasks: CRE-T005, CRE-T006, CRE-T011..T016

* **Content-addressed IDs.** A CRE event ID is `cre-` + SHA-256 of `(type, idempotency key)`; an observation's key
  is its source record identity (workspace, file, line/sequence). Redelivery, replay and reordering cannot create a
  second record (`INSERT OR IGNORE`); the mirrored 002 envelope uses the derived ID `fx-cre-…`, so the 002 store
  also deduplicates.
* **Reduction is a pure function** of the event set ordered by `(ts_utc, event_id)`: incident/CAPA state and metrics
  computed by full replay equal incremental reduction (AT-003, AT-030).
* **Restart-safe budgets.** Retry attempts, breaker state and recovery state live in SQLite (WAL,
  `synchronous=FULL`) — never in process memory — so a restart cannot reset a budget (AT-008). Backoff deadlines
  are stored as UTC epochs; on restart an earlier deadline is honoured conservatively (no retry before it).
* **Jitter is deterministic**: derived from the SHA-256 of `(operation key, attempt)`, reproducible in tests.
* **Replay classes** for every state-changing action: `REPLAY_SAFE`, `REPLAY_WITH_IDEMPOTENCY_KEY`, `COMPENSATABLE`,
  `NON_REPLAYABLE`. A `NON_REPLAYABLE` action is journaled `PENDING` before it runs and `DONE` after; a `PENDING`
  entry found after a crash is never re-executed — it becomes `REQUIRES_OFFLINE_ATTENTION` (AT-011). The policy's
  mandatory set (hardware flash, safety approval, baselined evidence mutation, release signing) is always
  `NON_REPLAYABLE`.
* **Leases**: one active repair per incident scope via the 002 store lease (owner + expiry); CRE adds a scope lease
  table for non-incident operations with the same compare-and-set semantics.
