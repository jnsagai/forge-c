# ADR DA-023 — Native inventory completeness before lifecycle effects

Status: implementation candidate; runtime and product acceptance remain separate.

L90C on source c1dcea9a failed before native submission: the SDK returned a
100-row first page of a 149-row terminal history, and the lifecycle guard
correctly refused to infer quiescence from the truncated catalog. The actual
first page contained 93 succeeded and 7 failed runs; the full authenticated
inventory contained 129 succeeded and 20 failed runs, with no removing runs.
C remains charged and blocked; this repair does not replay it or renew capacity.

Keep the existing `FabroClient.list_runs` API unchanged. Add explicit bounded
`RunInventory` observations, and have the lifecycle adapter require their
completeness and freshness before quiescence or own-native handoff. An empty
complete inventory differs from unknown, malformed, partial, stale or failed
observation. Only kernel-proven initial ECONNREFUSED retains the existing
no-current-Fabro-process allowance; it never applies to a partial response.

The pinned 0.362 OpenAPI describes offset pagination with mandatory `has_more`
and optional `total`. Validate page metadata, identity uniqueness, count and
progress, then require two agreeing complete observations of run identities,
status, source directory and labels. Ignore harmless ordering differences;
disappearing, duplicated, rebound or newly appearing identities refuse. This is
not a server transaction or a promise about work submitted afterward: existing
Intent, authority, lease, one-placer and effect fences remain necessary.

The installed binary's actual API was independently exercised with all eleven
lifecycle states, archived copies of each, and retained terminal history. Default
unfiltered queries hide removing records; include_archived alone is insufficient.
A six-column unsafe query also hides archived active records. The verified
all-nine BoardColumn query covers the full universe. The verified seven-column
safety query is pending/runnable/initializing/running/blocked/archived/removing:
it retains every unsafe lifecycle and excludes unarchived terminal history.
Source proof references the pinned OpenAPI SHA
b375681cbc2bf857beb7e4a9b74e66027d49995c06eadd6bc8cc313e6cafb666
and actual mapping report SHA
708798e3423a2c69a64394c2ecdd76a27ec046a3b58fcc8cd0b44e50f2068171.

Use all-nine for generic complete inventory, and seven-column for lifecycle,
M2 live checks and M3 live-run observation. Bind the exact filter, archive scope,
observer subject and freshness at each consumer; a complete running-only page
cannot stand in for a complete safety inventory. Strict lifecycle classification
still treats paused/blocked/removing as unsafe and unknown as UNKNOWN.

Bounds are 100 rows/page, 64 pages and 6,400 rows per pass, a shared five-second
MONOTONIC/BOOTTIME deadline, four MiB/page, and sixteen MiB wire bytes across both
passes. Async raw streaming stops before retaining an oversized body; stdlib asyncio cancellation bounds the whole network operation, including slow headers and slow body trickles. Byte-bounded JSON work is followed by clock checks. This is not a hard realtime scheduling or interpreter-CPU preemption guarantee. Completed observations
bind boot and network namespace and both clocks; suspend, observer or boot change
invalidates freshness. Hitting a bound produces UNKNOWN rather than truncation.
The safety query avoids ever-growing ordinary unarchived terminal history;
archived summaries retain their original lifecycle and must still be scanned.
The archived-history ceiling is an honest remaining scale limitation, not closure
of full continuous-operation/native-retention acceptance.

No policies, grants, original mission charges, native histories or release
criteria are changed, and no new inference is authorized by inventory evidence.

Validation uses HTTP transport, bounded streamed bodies, metadata/race/error
controls, actual normal private order/claim/lease/Intent fixtures and own-native
adoption. Harmless transport fixtures do not establish model or product competence.

The new synchronous inventory API refuses an already-running event loop rather
than starting an unbounded helper thread or silently changing transports. Its
internal async client preserves the same endpoint/authentication/observer and
accepts an injected transport only when it supports the async protocol; it never
falls through from an unsupported test transport to real networking. Existing
synchronous admission/lifecycle/stack CLI consumers remain synchronous.

Admission and M2 live checks conservatively treat every unsafe run on the
canonical server as occupied, including foreign or missing source directories.
Exact own-run labels/source/nonce are still mandatory at model handoff. Private
normal-Placer/TEST-signature controls verify no attempt/outbox/order/mission
counter changes when a foreign unsafe run prevents admission.
