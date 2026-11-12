# Bounded retained kernel-event replay

Runtime implementation: b321a8766947fa5f5174bbb4f61f5d05720b22d6.
This extends the existing host-audit verifier and its protected segmented reader.
It does not install audit rules, activate a campaign, control a service, admit a
model request or provide a host-wide intervention verdict.

The existing `verify-segments` command opts into the new path only when a frozen
host plan contains `continuous_replay`. Plans still bind the exact host/parser,
segmented reader, observer and evidence-root configuration. An existing campaign
is never silently upgraded when source/configuration changes.

The optional object has exactly these fields:

| Field | Allowed range / binding |
|---|---|
| source_sha256 | SHA256 of afo/kernel_replay.py |
| max_source_bytes | strict integer, 1 through 2^40; includes final protected-anchor reads |
| max_records | strict integer, 1 through 10,000,000; includes duplicate input records |
| max_scratch_bytes | strict integer, 65,536 through 8 GiB; SQLite page allocation cap |
| max_output_bytes | strict integer, 16,384 through 1 GiB; cumulative factual page bytes |
| max_seconds | strict integer, 1 through 3,600; cooperative whole-verification wall allowance |
| max_cpu_seconds | strict integer, 1 through 3,600; cooperative CPU allowance |

`configuration()` validates the source and these finite allowances. Existing
per-read 16 MiB, per-line 64 KiB, per-event record/path rules and retained-source
checks remain. New replay accepts at most 50,000 successful capture references
and 128 MiB of their original serialized metadata, including whitespace. Failed
captures remain historical observations; they cannot advance a successful cursor.
Default legacy replay keeps its original aggregate limits and schema.

```sh
python -m forge_factory.afo.host_audit verify-segments \
  --manifest MANIFEST --observer-plan-ref OBSERVER_PLAN_REF \
  --host-plan-ref HOST_PLAN_REF --segment-refs CAPTURE_REFS --out REPLAY_RESULT
```

This is a command template, not authorization or an activated manifest. Use the
existing frozen qualification inputs and isolated evidence root. The command still
returns 2 for incomplete host coverage even when selected event facts replay.
Missing sources, wrong hashes, skipped history, changed anchors, bad rotations,
resource exhaustion or unsupported boot continuity cannot produce a host PASS.

The verifier starts at capture sequence zero on every invocation and re-reads all
original protected ranges. Byte/UTF8/compound-event boundaries may cross captures
and rotations. A disposable B-tree groups selected records by their exact event
identity; it retains late records and checks duplicates across the entire prefix.
Each grouped event is reconstructed by the existing EventReplay rules. No timeout,
page boundary or input EOF is invented as an event-completion boundary. Global
input records remain charged to the frozen allowance while per-event assembly is
bounded. Missing/pending/orphan facts stay explicit.

Scratch contains selected IDs, counters, record kinds, actor numbers and hashes;
raw audit bodies, command/argv/path fields and unselected rule keys are excluded.
Process-local integrity tags plus a counted multiset check reject changed, dropped
or duplicated scratch rows. These tags confer no authorization and are never
durable checkpoints. The B-tree is not a knowledge store, cache authority or ledger.

The existing qualification lock protects one reserved initialization slot. A
provenance marker identifies that discardable slot; an unowned, symlinked,
hard-linked, exposed or live slot is refused without truncation. After SQLite
opens the actual file and begins its transaction, the working file is unlinked.
Its storage is released when the last descriptor closes, including a hard kill.
An initializer crash leaves at most the single owned slot, which is cleared under
the lock on restart. Only the small ownership marker and existing-style lock file
remain between runs. Original sources and historical evidence are never reclaimed
by this scratch handling. A live initializer stuck in native I/O retains its lock.

The new result uses host-audit-segment-replay/2 and kernel-event-replay/2. Selected
facts are in bounded immutable kernel-event-facts-page/1 artifacts, chained by
previous-page reference and bound to manifest, plans and the complete capture-ref
digest. The summary includes their references, cumulative counts and original
input SHA256. It deliberately has `facts: null` instead of an incomplete inline
list. Rerun the existing verifier from original sources for independent replay;
neither existing page files nor a supplied cursor can replace earlier verification.
An interrupted/failed verification may retain factual pages but has no completed
summary that authorizes a campaign verdict.

Native audit loss, complete record/window interpretation, boot correlation,
authenticated actor/control/write/service attribution and all-channel coverage
remain separate qualification. `unexpected_interventions` is always unknown here.
Cooperative allowances cannot terminate uninterruptible kernel I/O; native callers
still need bounded worker supervision and must reconcile actual process liveness.
The hard-kill fixtures exercise owned test processes, not Conductor/RCC recovery.
No job readiness, learning benefit, self-healing or 24/72/168-hour availability is
implied. See the evidence checkpoint for exact tests and remaining prerequisites.
