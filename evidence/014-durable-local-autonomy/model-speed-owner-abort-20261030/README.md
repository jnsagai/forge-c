# Owner abort and controlled Qwen speed pilot — 30 October 2026

The owner superseded “finish LL first”: **abort the product run, save all results,
focus on model-speed benchmarks**. HAL must not be submitted or LL retried.

## Product run saved and stopped

Runtime source `899865d5f256e3c2fbdd836ba8696ef9cdb6fa8f`, order
`afo-f3ad027406784ef7`, job `afo-product-09d5a51e57adaa5a6a71589e`, native
`01M65TR9K7DRDTM8AX8ZTP445G`. STOPPED epoch 73 was settled at 09:07 UTC.
The provider namespace ended; native execution became FAILED after the owner stop;
job execution is QUIESCENT/RELEASED, outcome BLOCKED/OPERATOR_SHUTDOWN, all 36
requests QUIESCENT. Known reported tokens were 614206; unknown usage and conservative
charges remain in the original mission ledger. This is an owner abort, not evidence
of an autonomous model failure. No mission allowance, deadline or failed history reset.

[Finalization](aborted-package-finalization.json): ordinary reconciliation and
finalization produced a sealed **BLOCKED** review ZIP with 49 gaps. Archive integrity
PASS, SHA256 `a9d94406e768259955c501fc6d33fed0354b8c48fe3837124707f2986db5e8c0`.
The order is terminal BLOCKED. Zero model calls were used to stop, finalize or export.

Private copies on local loop10:

- Review package: `inspection/feature014/2026-10-30-qwen/full-pipeline-qm-launch-ready/afo-product-09d5a51e57adaa5a6a71589e/`.
- Complete engineering snapshot: `operations/feature014/incremental-m1-followup-20261029/owner-aborted-full-engineering.tar.gz`
  and extracted sibling `owner-aborted-full-engineering/`.
- The latter includes the whole workspace, Git history, `.forge-run` packets,
  author visits, inspection findings, relevant cumulative ledger rows and stop receipts.
  All **835 members** were safely extracted and their manifest hashes verified.
  [Transfer receipt](private-local-transfer-verification.json), archive SHA256
  `651d7ffe666ea7615d6295dca01e5dc6970caf686cedc03dada5558b0b289f9c`.

Only SWE.1 executed. Seven original author groups validated; automatic returns
reused unaffected valid groups. SWE1-02 findings decreased 6 → 3 → 1 across successive
reviews. The final baseline `ad64dceaa4f94435` was under review when interrupted.
Its remaining reported conflict concerns `(void)` parameters versus a value return;
the authoritative CPU allocation is also unresolved. Findings remain recorded.
No complete pipeline, independent repair correctness or learning benefit is claimed.

## Exact-source native checks

Benchmark runtime source **`37c0c354629312a70eb6a199989477036bb674d9`**:

- [Reasoning/gateway JUnit](reasoning-native-junit.xml): **96 PASS**, no skips/errors/failures,
  22.05 s pytest; [command, limits and source provenance](reasoning-native-provenance.json).
- [Context/workflow JUnit](context-native-junit.xml): **92 PASS**, no skips/errors/failures,
  21.02 s pytest, including native Fabro parsing; [provenance](context-native-provenance.json).
- Cohorts overlap; they are not 188 distinct tests.
- One verifier at a time, bubblewrap UID 2001, no network/GPU/owner identity/SSH agent,
  four CPUs, 8 GiB physical RAM, no swap. Temporary fixtures use cgroup-bounded RAM;
  real JUnit/log/provenance files persist under the project deployment directory.
- STOPPED73 remained unchanged through both checks. No automatic resume or deployment.
- The initial disk-backed run was explicitly cancelled while waiting on ext4 journal
  commits. [Cancellation](superseded-disk-check-cancelled.json) is retained, not relabelled PASS.
  The subsequent RAM run executed all original assertions. This tests software and native
  tool compatibility; it is not a deployment-storage durability campaign.

Reviewable [worker](qualify-native-ram.py), [stopped window](qualify-stopped-window.py),
[activation tool](activate-benchmark.py), [finite pilot driver](run-speed-pilot.py).
Local real-child controls passed for preserving STOPPED73 and cancelling on a newer intent.

## Benchmark scope and current limits of evidence

[Exact scope](scope.json) and [owner delegation binding](owner-approval.json): separate
new benchmark missions, eight frozen targeted diagnosis cases per effort, one inference,
Qwen3.8 Q8_0/f16 KV/MTP3/262144 context, temperature 0, compiled 260-input reference
oracle. Existing RCC mission/deadline/history are untouched. Both benchmark grants expire
at **13:52:52 UTC today**. The preparer's IDs retain the suffix `DRAFT`, but their actual
records were explicitly signed with the delegated SSH agent before activation; the name
does not substitute for signature verification.

The isolated runtime was activated only after both native checks passed. Xhigh baseline
comes first, medium follows serially after native/request/verifier quiescence. High is
**UNSUPPORTED** by the installed template (HTTP 500); it is not mapped to medium.
Kernel procfs observations verify actual native server flags and gateway reasoning policy.

Two initial xhigh cases failed **before any model request** because the external driver
called the polling/launching `qualification.step` from the host environment. Profile
isolation correctly rejected that context. Those terminal cases and charges remain.
The corrected driver only enrolls/provisions and records terminal facts; the existing
isolated Conductor exclusively dispatches/polls. It stops consuming further cases on a
new infrastructure refusal. The remaining cases continue under the same finite mission.

Native decode rate comes from correlated llama.cpp eval tokens/seconds, including
reasoning tokens; end-to-end throughput uses separately metered gateway latency.
Loading, job wall time, failures and unknown usage remain separate. This is a small
diagnosis speed pilot, **not author/inspector/product qualification**. The formal
controlled-comparison report requires additional independent measurements and may remain
INCOMPLETE. Two failed setup cases cannot disappear from the denominator.

First actual xhigh native job `01M6626QG8D2KVYX691Z3CTDWQ` completed: **6293 output
 tokens / 101.72667 native eval seconds = 61.86185 decode tokens/s**, 102.8787 gateway
seconds. [Measured record](xhigh-obligation-counterexample-0.json). Expected PROPOSE_REPAIR,
observed NEEDS_EVIDENCE; no successful diagnosis claim. Remaining baseline cases are running;
medium and MTP-factor results remain **NOT_RUN**. No speed/quality winner selected.
Formal Feature014 remains **30/58**, no task IDs newly completed. Clean LL/HAL, learning
benefit and 24/72/168-hour availability remain UNPROVEN/NOT_RUN.

## Durable continuation and local inspection

Xhigh observer: user unit forge-q38-speed-xhigh-driver-20261030-v2.service.
Finite [medium follow-up](continue-medium.py): user unit
forge-q38-speed-medium-followup-20261030-v2.service; no resource quotas on inherited
model processes, no duplicate dispatch, newer intent/expiry fenced. It waits for the
baseline completion and actual quiescence, then invokes the reviewed activation tool
and the same Conductor-owned pilot. The factory controller continues after the pilot.

[Read-only exporter](export-readonly.py), [local collector](collect-local.py) and
[descriptive reporter](report-speed.py) preserve all selected input/result/audit hashes
without collecting hidden reasoning. Local collector runs every30s through both
completion receipts (or bounded final collection grace); grants are never renewed.
Inspect B/inspection/feature014/2026-10-30-qwen/model-speed-pilot/SPEED-REPORT.md
and speed-summary.json. The report is regenerated after each verified snapshot.
Report helpers must be colocated using their operational names
collect-q38-speed-results.py and report-q38-speed.py; public names above are review copies.

Later baseline observations:65.06,63.14,63.08tok/s and76.46,91.91,112.67 gateway
seconds. All three additional complete-evidence cases also returned NEEDS_EVIDENCE
instead of expected PROPOSE_REPAIR. The missing-primary cases and medium are pending.
