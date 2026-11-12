# ADR-DA-009 — Stage-scoped admission replay for line-local soak observation

- Status: implementation candidate; live qualification NOT_RUN
- Scope: feature 014 DA-T052, DA-FR-052 and DA-AT-052; existing operational campaign and collector

## Context

The line adapter already freezes the local conductor, namespace health routes and
source revision, and the existing operational campaign calls its preflight. Its
placeholder unconditionally blocks live admission because the prerequisite replay
was not implemented. Source eligibility, a signed finite role experiment, and one
successful timer-recovery drill do not establish autonomous-stage completion.

The authored 24-hour smoke is followed by 72-hour and 168-hour observation. The
100-protocol and 30-product cohorts, role effectiveness, learning benefit, all 16
operational faults, real elapsed duration and post-window intake remain their
respective acceptance outcomes. They are not invented completed-cohort prerequisites
for starting the first operational observation window.

## Decision

Keep the existing campaign/collector/start/report paths and finite mission ledger.
Add a typed, bounded evidence index under schema
`forge-c/line-soak-prerequisites/1`. Freeze the index and its selected operational
CRE policy as normal `manifest.inputs`; freeze its hash-bound reference in the
observer plan's `prerequisites_ref`. The index has exactly:

```text
schema, source_revision, profile_sha256, intent_epoch,
jobs, recovery_policy_ref, claims
```

`jobs` has the same finite keys as the campaign bindings. Each value references
an actual registered job projection or a prospective
`forge-c/line-soak-pending-order/1` descriptor with exactly:

```text
schema, order_id, attempt_seq, spec_ref, control_ref, line_origin
```

A prospective descriptor binds an actual QUEUED order and the normal immutable M3
spec, approved campaign, source/profile, signed line/AFO authority, effective finite
mission and next sequence. IDs use the existing `Store.admit` and product-job
identity rules. It is a preview only: no attempt, nonce, charge, request, mission
registration or inference lease is created. The default actual binding API still
requires a real admitted attempt. Normal future admission rechecks every guard;
a preview cannot be used as an execution or completion receipt. Unsubmitted
future orders are not represented as already existing queue rows.

For genuinely later authorized intake, the separate descriptor
`forge-c/line-soak-planned-intake/1` has exactly `schema, state, lineage, spec_ref,
control_ref, line_origin`; `state` is `NOT_SUBMITTED`. It supports an approved
independent first SWE.1 START only. Unknown future upstream/resume/provided facts
are unsupported and BLOCKED; this restriction does not alter the existing
registered or QUEUED phase 1–6 paths. Pure normal queue validation and M3
order/spec/envelope builders are shared with actual intake. The descriptor binds
normal submit **and** launch scope, recovery/control/trial authority, exact
campaign/source/profile/quality, canonical predicted order/attempt/job IDs and an
already registered finite mission with its original authorization and usage.
Every actual or orphan row/attempt/outbox/mission-link/job/execution/request/resource
footprint for those identities refuses the preview. Initial START rechecks that
absence. No proposed UTC is claimed as an observed future submission timestamp.
The eventual normal submit/admit/product preparation creates and charges work;
the preview cannot enter the ordinary actual-admitted binding API.

An optional `line_intake_identity` in the frozen job binding binds exactly the
payload digest, campaign SHA, profile ID and control SHA. Historical work capture
derives these from the persisted immutable envelope/spec/job control reference,
without requiring a then-current grant. The actual observation hash and existing
independent audit cover this field, and replay compares it to the frozen binding.
Omitting it retains the previous observation bytes/behavior. A descriptor alone
never satisfies later-intake or independent-work criteria: the normal baseline
must actually observe absence, then actual intake/native activity, independent
work verification and post-window continuity must still be collected.

Replay current jobs without discarding historical charges or interpreting provider
UNKNOWN as free capacity. Validate enabled planner/maintainer paths from actual
policy, locked Skills/MCP metadata, per-role profile reservations, independent role
capability envelopes or explicit finite trial authority, and measured native
transport. Unknown semantic objectives are not assigned a guessed size. A future
objective/request still needs normal measured admission; checking a prospective
class envelope is not execution qualification. Necessary native output/thinking
lower bounds use the correct helper reservation, not the product's larger budget.
A finite trial remains `qualification_only`; it does not become competence or a
whole-campaign fault/soak grant.

Optional prior claims are observations **at replay time**, not final-boundary
current qualification or future authority. Fault/work claims replay their existing
independent source validators. A maintainer claim requires the normal isolated
case/submission, nonce-bound quiescent native execution, append-only proposal and
exact independent CRE candidate decision. It proves offline candidate eligibility;
it infers no role competence, deployment or repair benefit, including when a
normal CHANGE decision has no causal reproducer. A lesson claim replays the existing
source-specific qualification and current stored state; it infers no application,
phase transfer or benefit. Actual retrieval/application must still satisfy the
existing phase/role/target/source/tool predicates at use. No lesson is required to
exist merely to start observation.

Do heavy immutable proof checks outside `Intent.lock`. The controller retains an
internal, non-persisted replay snapshot. Its JSON projection is never accepted as
authority. Before START append, and before the exact approved line-unit fault
kernel call, hold the existing intent lock and fence bounded cryptographic bytes
of the verified grant/signature/signers/revocation/policy/proof inputs, current UTC
expiry, executing source, current intent and fresh mission/lease accounting. A
same-stat byte change, new revocation file, unknown execution or imported unbounded
history refuses the effect. No historical PASS authorizes a new start.

The initial START must match the prepared intent epoch. A later explicit fault
invocation may observe a legitimately resumed RUNNING epoch; it takes its own
current snapshot and must retain that epoch through the effect. Fresh role/job
admission keeps its normal epoch checks. Observation continues after authority
expiry or a finite measurement window without stopping the service or renewing
anything. Generic campaigns retain their default route; a frozen typed line plan
is recognized even when a caller omits `--observer-plan`.

Resource limits are implementation observation limits, not acceptance sample
counts: at most 32 job bindings, 128 optional claims, 512 referenced files and
32 MiB per replay closure, 1 MiB per referenced file, and bounded read-only SQL.
Lesson historical evidence replay has optional entry/byte/file/time limits; the
legacy default stays unchanged. Exceeding any limit is BLOCKED/UNKNOWN, never an
empty training classification. Git tree identity uses the existing `git ls-tree`
byte hash with an explicit three-second observation timeout.

## Validation and remaining authority

Normal API CONTROL tests exercise real signed test-key policies/campaigns, queue
and mission bindings, isolated submissions and durable native/CRE protocols, plus
operator races, stale/forged evidence, exact unit identity, unknown leases,
resource limits and accounting preservation. Stub native/independent observations
and controlled clocks are not live role or duration qualification.

No policy, grant, model, unit, queue, mission limit or signed owner packet is changed
by this implementation. All real campaigns remain NOT_RUN/BLOCKED until their exact
qualified source/profile, current signed stage/job/fault authority, role receipts or
explicit finite trials, host setup and evidence actually pass. The existing report
still owns real duration, all faults, independent work and later authorized intake.
No feature task is marked live-complete by source tests or a CRE source decision.
