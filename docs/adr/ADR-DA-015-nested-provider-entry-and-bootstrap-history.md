# ADR-DA-015: Nested provider entry and durable failed-start history

Status: proposed for offline engineering review. Outputs remain UNACCEPTED.

The owner's existing directive, “for now go on without needing signatures”,
continues to authorize the bounded owner-supervised development channel. This
change adds no production authority, role, model, service action, allowance or
deadline. Production signed ACT and all original mission accounting stay intact.

## Measured namespace failure

The failed887 startup reached the existing strict worker capture after backend
`nsenter` processes had exited with network-namespace EPERM. A real private kernel
control reproduces this: development bwrap creates a child user/mount/PID
namespace while inheriting the outer holder's network namespace. Entering the
child user namespace before the ancestor-owned network namespace loses the
required capability. Re-entering an already-current user namespace separately
fails with EINVAL.

Enter the outer holder USER/NET first, omitting namespaces already current, then
enter the differing provider USER and its MNT/PID. Verify the captured init's
boot/start/PID namespace/NSpid and network equality. Mapped UID translation is
valid only for the exact outer holder user namespace with its kernel one-UID
mapping and captured observer identity. Keep worker argv, ancestry, private-PID
namespace and pidfd proofs strict. An exited nsenter waiter is never a worker.

The supported calling contexts are the initial OS owner and the outer mapped
Fabro context. The latter hosts native graph script nodes and model swaps.
`line_launcher.py` smoke and `line_recovery_runtime.py` execute `stack exec`,
which enters that outer holder. `workflow/builder.py:serve_swaps` emits native
Fabro script nodes; `line_stack_lifecycle.py:serve` fences them and invokes
`stack._serve_model`. `_start` launches Fabro outside the private serving PID
namespace, while only model backends and gateway enter it. Gateway routes
requests and checks served-model identity; it does not call stack serve.
Untrusted MCP executable artifacts use `mcp/sdk.py` and
`owner_supervised_development.contained_argv` confinement and have no stack
lifecycle authority. Direct entry from an arbitrary provider-private user/PID
context is not an additional supported owner control path; unreadable ancestor
identity remains a refusal.

## Durable historical acknowledgement

Revalidating an old accepted cleanup file as fresh authority fails on a later
startup and would encourage refreshing old evidence. Instead, keep each original
UNKNOWN and reconciliation unchanged. A fresh pending failure still requires
independent whole-stack cleanup, current owner authority, current Intent, complete
history conservation and both expiry clocks.

New consumption writes an explicit content-bound consumed receipt in the same
SQLite transaction as its following bootstrap INTENT/2. Historical validation
checks the exact old failure, acknowledgement, authenticated canonical issuing
record, Store/mission/caps/roles/control scope and successor INTENT. It grants no
current effect authority and never extends or refreshes old evidence timestamps.

Legacy887 INTENT/1 did not record a consumed receipt. Its compatibility path
requires the exact immutable Git blob fingerprints of the audited coordinator,
reconciliation and guardian producer formats for every declared source revision,
plus the same complete canonical chain. Missing objects, changed formats,
unconsumed acknowledgements, tampered records and ambiguous chains refuse. No
machine-specific record or revision allowlist is introduced.

## Validation limits

Private tests exercise kernel topology, harmless CPU health servers, original
SQLite receipts and transaction rollback. They do not prove model competence,
human MISRA review, installed recovery drills, actual fault clearance or live
mission qualification. Actual failed starts and all prior OPS versions remain
immutable evidence. Runtime changes require separate review and qualification.
