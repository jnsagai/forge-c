# ADR DA-024 — Local evidence escalation for controller launch refusals

Status: implementation candidate; no deployment or runtime qualification claim.

The owner asked why the local factory did not repair the failure itself. L90C
stopped before native submission with STACK_STOP_FAILED. Its authenticated
native inventory was incomplete; the retained first page did not prove quiescence.
The failure is an observation requiring engineering review, not automatically a
verified factory defect. C remains spent. The sole D allocation is not a budget
for diagnosing the factory.

The existing LaunchNotStarted boundary saves a proof, settles the execution,
blocks the job/order and quarantines the command. The owner-supervised Placer
captures factual learning but does not run the generic conductor's dead-letter
sweep. Maintainer repair intentionally denies afo/**. Neither that denial nor
the protected production policy is relaxed. auto_merge_source and
auto_promote_factory_code remain false; the report is no promotion authority.

Add controller_escalation.cycle to the existing owner loop after its placement
cycle. It receives the already-open existing-only canonical Store and the
current trusted record's original device/inode identity. Missing, rebound or
lookalike storage refuses; reporting never constructs or initializes a database.
No source/default production conductor heartbeat behavior changes. Liveness
still differs from completion progress and reporting makes zero model calls.

A bounded stream reader uses lifecycle seq, not creation time or a scan of all
terminal orders. Each poll handles at most32 existing events and one export.
A fixed schema/actor/key version2 telemetry pointer binds the last consumed
existing append-only source event by exact seq and SHA256. No cursor-marker
events are created. The pointer confers no authority. A future handover observer must
explicitly validate this telemetry alongside the existing learning cursor before
freezing all29 tables, rather than ignoring arbitrary controls. SQL VM and elapsed
budgets also bound queries and legacy helper work. A local FAILED event whose
settlement is not yet BLOCKED is left pending, not skipped. A timeout or unknown
native launch is never converted to a no-native fact or released by reporting.

The controller case binds the real job/order/attempt, hash-verified local launch
proof, original source/profile/model and point-in-time conserved mission counters.
The optional launcher transcript contributes only whitelisted metadata and its
primary digest. Missing, oversized, ambiguous or unsafe paths remain explicit
gaps. No prompts, reasoning, credentials, vendor text or whole canonical database
is exported. Raw exception prose cannot label a verified defect.

Keep product offline.export and its v1 schema byte-identical. A separate typed
controller exporter reuses its redaction and fixed-time archive primitives,
producing CASE.json, a detailed fenced-data REPORT.md, MANIFEST.json and
SHA256SUMS. It never fabricates a product workspace/manifest or native run.
Outputs are private immutable files beneath the existing configured archive_root
in controller-exports, outside reclaimable run/workorder trees. Lifecycle event,
notification and dead-letter references include physical paths and hashes for
retention closure. No source/job path becomes a new late reference.

Seal the case first; write/verify identical archive and report before a single
canonical transaction appends the receipt, advances the telemetry pointer and
queues its exact local notification in the existing outbox.
A crash before acknowledgment verifies the same immutable bytes on restart;
a divergent partial or foreign artifact refuses rather than being overwritten.
The existing local notification log supplies manual handoff refs. There is no
network sender, new product queue, repair job, model request, budget reset,
automatic order reopen or acceptance/release claim. Manual development repair
still needs its normal causal FIX, regression, protected-path review and rollback.

The parallel DA049 retirement catalog is not on this c1 base. Its future
require_available(c, refs) writer fence must be wired during qualified integration;
no unqualified SQL or optional import fallback is introduced here. Independent
archive containment already excludes these outputs from this component's job
reclamation roots. Full continuous-operation/retention acceptance remains separate.

Independent review controls preserved a real cursor defect in the first candidate:
a page of32 dead-letter events was ignored without advancing. The corrected reader
advances all consumed source events without creating cursor markers, and
verifies completed-artifact receipts as it advances. A separate retained
counterexample on1056 facts proves why even ignoring self-markers is insufficient.
A reporting failure becomes a bounded CAPTURE_FAILED record in the existing owner
audit and does not kill an otherwise healthy guardian. It supplies no placement
authority: current()/Intent and pinned storage guards remain unconditional before
every normal cycle. The direct strict cycle API retains errors for verification.

Writer acquisition uses an existing-only connection to the same pinned canonical
Store with a100ms busy bound and the shared SQL VM/elapsed budget in place before
BEGIN IMMEDIATE. There is no DB initialization, WAL conversion or replacement
Store. Committing files remains subject to normal filesystem scheduling; no hard
realtime fsync guarantee is claimed. Archive ancestry must be canonical and its
device must equal the pinned Store's data volume.

A transcript's stop log is derived from its exact attempt basename beneath the
configured launch root and must match the transcript's step_logs identity.
Bounded complete files get a whole-file digest and byte count. Only a finite
source-owned typed-code set is extracted; unknown text, tracebacks and bodies
remain excluded. Missing, oversize, unsafe or unrecognized logs are explicit gaps.
Recorded and not-recorded steps are distinct from proven reached/not-reached
execution boundaries: the local no-submit proof remains mandatory.

Local delivery is explicit, not inferred from enqueue. The existing alerts.deliver
API gains optional exact notification IDs, a finite limit, caller-supplied bounded
canonical transaction and expected immutable payload digest. Default callers keep
their prior behavior. This component always supplies one exact own notice,
adapters={}, and the same reporting SQL/time budget. It never configures external
senders or drains unrelated notifications. The version2 cursor also binds an
outstanding notification to its append-only export receipt, so cursor advancement
cannot hide a crash before delivery. A delivery error remains CAPTURE_FAILED and
retries only that local notice; it cannot duplicate an export or spend mission
capacity. The existing notice log and human event-ledger payload reference are
recorded only after the real outbox row acknowledges local delivery. As with the
existing outbox, a crash between append and acknowledgment can repeat a local
notice; this at-least-once delivery is not exactly-once external messaging.

A further real private control observed that the legacy event logger's blocking
flock can outlast reporting's SQL budget. Preserve that V6 evidence. The event
append API now has an optional finite nonnegative lock timeout; default callers
keep their old behavior. This component passes only the remaining shared
monotonic budget, uses nonblocking acquisition with bounded retry, and receives
typed EVENT_LOCK_TIMEOUT on contention. File publication occurs outside the
canonical manufacturing writer after immutable receipt/outbox validation; the
selected payload is checked again before acknowledgment. A held event lock
therefore cannot retain that writer. Restoration retries the exact pending local
notice without a new export, model call or mission debit. This bounds controllable
lock waits, not operating-system fsync latency or arbitrary scheduler stalls.
