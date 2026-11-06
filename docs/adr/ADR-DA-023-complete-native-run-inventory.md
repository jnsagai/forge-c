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

V1 deliberately uses full enumeration until an independently measured exhaustive
nonterminal filter is available. Bounds are 100 rows/page, 64 pages and 6,400 rows
per pass, a shared five-second MONOTONIC/BOOTTIME deadline, four MiB/page, and
sixteen MiB wire bytes across both passes. Streaming stops before retaining an
oversized body. Completed observations bind boot identity and both clocks; suspend
or a boot change invalidates freshness. Hitting a bound produces UNKNOWN rather
than a truncated success. These ceilings are real remaining scale limitations;
this component does not close continuous-operation/native-retention acceptance.

The separate installed-server filter audit determines whether terminal history
can be excluded safely. No comma-separated status or lifecycle-to-board mapping
is assumed. Archived, removing, active and unknown cases require explicit tests.
No policies, grants, original mission charges, native histories or release
criteria are changed, and no new inference is authorized by inventory evidence.

Validation uses HTTP transport, bounded streamed bodies, metadata/race/error
controls, actual normal private order/claim/lease/Intent fixtures and own-native
adoption. Harmless transport fixtures do not establish model or product competence.
