# Operator shutdown: reconcile the product order under the intent fence

Exact implementation: `c0777eadb595e25ac993ff2fa5f4b10e27299636`.
Parent: `51a5042d`. Runtime activation and live benefit: **NOT_RUN**.

The real overnight08 execution was cancelled and its inference ownership settled,
but its AFO order still said RUNNING. The Conductor exits after an effective
operator stop, so the next normal dispatch reconciliation never occurred. An
external administrative queue projection was required; that historical action
and its receipt remain unchanged in
[the window-end evidence](../overnight-window-end-20261031/README.md).

The existing shutdown path now projects only the bound current product
execution's known BLOCKED/OPERATOR_SHUTDOWN business outcome to its active order.
It runs under the existing STOPPED intent lock, with the queue transition and
source-binding event in one existing durable queue transaction. Released
executions are included so a crash after physical settlement does not lose the
projection. An older execution cannot block a newer attempt. Native/attempt
status, resource ownership, requests, budgets, packages and product acceptance
are not inferred from that business transition.

The existing native reconciler alone settles physical liveness. In the RUNNING
native fixture, the order becomes BLOCKED while the inference lease stays HELD
and effective stop remains false. Native FAILED can settle the lease through
the existing proof path. A newer RUNNING operator intent refuses stale shutdown.
A product nonce/mission mismatch is explicitly pending without touching its
order. Metadata storage failure leaves the physical stop effective and records
order_projection=PENDING; it does not certify metadata completion or delay stop.
Projection is bounded to eight eligible orders per call, with pending_more
visible. This does not establish automatic cleanup of every pending metadata
error or close the stopped-job learning-disposition gap.

## Verification

- First fixture attempt: 6 setup failures from PREPARED -> RUNNING without the
  required DISPATCH_PENDING transition. Corrected before implementation; this
  receipt is retained as fixture error, not evidence of a product defect.
- Corrected six-case counterexample: **4 FAIL / 2 PASS**. Three cases reproduce
  the stale order (live, terminal and crash-after-release); the fourth establishes
  absent metadata-failure reporting.
- Final exact source: **152 PASS / 0 SKIP / 0 failures / 0 errors**, 21.929 s,
  across nine files. Includes eight new cases plus inherited product outcomes,
  protocol/integration, managed-provider recovery, intent, operations facts and
  Conductor/operator regressions. Native responses are deterministic fixtures;
  inherited provider tests use local kernel fixtures, no GPU or Qwen inference.
- Changed-source/new-test Ruff PASS.
- Static mapping58, contracts6/fixtures38, design14 PASS. Static consistency
  does not qualify a native runtime or operational availability.
- Historical RCC graph-golden and scheduler import-order findings remain open;
  this is not a full repository regression claim.

Exact commands/environment, JUnit, hashes and static outputs are attached.
Original failing XML bytes are stored as deterministic gzip with decoded hashes.
Counts overlap prior cohorts and must not be summed. Trace: supports DA-T013,
DA-T045/050 and DF-FR-011/016. No original DA task is newly closed.

A subsequent read-only Omniverse metadata check observed STOPPED epoch7,
effective_stop=true, no inference holder, zero held executions and zero
nonquiescent requests. The configured authority directory contained eight
records, all expired at 31 October07:57:59UTC. This metadata observation is not a
new kernel proof, signature qualification, grant renewal or model execution.

Next live work needs a current bounded authorization and the existing signed
mission-deadline extension path; preserve the 7 prior attempts, charges and
uncertainty. Do not reset the mission, replace the old third trial, deploy under
the expired grant or claim complete LL/HAL from the scoped2/3 result.
