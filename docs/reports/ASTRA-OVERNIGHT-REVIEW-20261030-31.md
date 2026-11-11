# Astra review: Forge-C local-Qwen overnight mission, 30–31 October 2026

**Assessment:** Qwen produced three fresh, independently tested C candidates for
the same small CRC IDR scope. Two reached audited terminal functional packages;
the third was stopped at the owner's deadline during SWE.3. This is useful
functional evidence, but it does **not** establish a clean full LL/HAL pipeline,
production readiness, autonomous factory self-healing, learning benefit or 24/7
availability.

**Final fresh cohort: 2/3 qualified; third case retained, not replaced.** The
earlier qualifying baseline is excluded from that denominator. Strict release
remains blocked. The original Feature 014 ledger remains **30/58**; no original
DA qualification task was closed by these experiments.

This report is published on `main` at the owner's explicit request. The
publication adds documentation only. Implementation and detailed evidence remain
on `feat/014-durable-local-autonomy`, draft PR [#42](https://github.com/jnsagai/forge-c/pull/42),
stacked on PR #41. No implementation merge or deployment is authorized by this
report. Report publication base: `bf3f1eb9625f552dee92d5e688c1d1f186b40e71`;
the intervening main updates were preserved. Feature 015's PR #43 merge
`38e2740bbc991c020cf49d0d8be33931e07f73a0` is an ancestor of the tested
implementation revision below. The full Feature 015 benchmark regression was
not rerun here.

## 1. Mission, scope and final runtime state

The owner authorized a ten-hour overnight continuation from
**2026-10-30 21:57:59 UTC to 2026-10-31 07:57:59 UTC**. Actual local-Qwen inference
and execution of its generated C stayed on Omniverse2. Local files, synthetic
framework tests and transferred artifacts stayed on `/dev/loop10`.

The declared engineering increment was only two STM32N6 CRC IDR functions,
`LL_CRC_Write_IDR` and `LL_CRC_Read_IDR`, against frozen inputs and an independent
oracle. It was a QM Delivery-First development experiment. No vendor
implementation was substituted. It was not a complete CRC driver, LL→HAL chain,
arbitrary-peripheral qualification, safety release or assessed ASPICE claim.

| Axis | Final evidence/status |
|---|---|
| Runtime implementation | Generic fixes committed and tested; latest implementation revision `60619be076d36d50f42aef0c1b467aa2c2c14e76`, inactive on the remote comparison instance |
| Actual remote producer | `0e342eef3c68786d29e5b9843606892c4ab68b60`, unchanged across fresh 06/07/08 |
| Local-model capability | Fresh initial independent C checks passed 3/3 for this small scope; general authoring, diagnosis, inspection and maintenance capability are not thereby qualified |
| Terminal functional delivery | Fresh 06 and 07 scoped milestone PASS; 08 NOT_PROVEN, operator-stopped |
| Process/release | 06 BLOCKED with 16 gaps; 07 BLOCKED with 35 gaps; 08 incomplete with no final review package |
| Learning | Ordinary facts/dispositions observed; zero qualified lessons/transfers at the reported checks; no measured benefit |
| Operational availability | Serving/native/request shutdown verified before expiry; unattended handoffs required external administrative retries; no 24/72/168-hour campaign qualification |

The frozen profile was Qwen3.8-27B Q8, f16 KV, **medium reasoning**, MTP draft3,
one 262144-token slot, one admitted inference. Profile SHA256:
`823942772335b7ef500f9f11926732405ac12dbff0dcc7f0ab39e345db3358e7`.
Actual model digest:
`8f5fb6b71ea00052cbe8545738c55ce61112c4e571cb60ca4dad00b131766039`.
The recorded model digest matched and network isolation was
`DENIED_VERIFIED`. This was not an xhigh comparison. Provider-reported reasoning
zero does not measure zero hidden reasoning; the breakdown remains UNKNOWN.

The source auditor was separately pinned to
`30371da548bad2790a9f3c21dafc8964047ce06d`; it reconstructed native source writes
and accepted edits without executing the candidate or modifying the workspace.

## 2. Actual runs and measurable outcomes

All native timestamps in detailed receipts use the remote service clock, which
trailed the external clock by approximately 57 seconds near shutdown. Elapsed
durations below come from native timing counters. Critical deadline enforcement
is separately bound to the external clock, not inferred from the remote clock.

| Case | Native run ID | Independent verification | Phase files SWE.1→6 | Strict outcome | Reported output tokens | Native wall time |
|---|---|---|---|---|---:|---:|
| Baseline05, excluded from fresh cohort | `01M67R1HNE9TKPWCYJ2SVKEPJS` | Initial/final PASS; scoped M1 PASS | 3/8/9/3/3/3 | BLOCKED25 | 339976 | 7597.950s |
| Fresh06 | `01M67ZJWDYS7H33828MPTK6E6D` | Initial/final PASS; terminal audit PASS | 3/8/11/3/3/3 | BLOCKED16 | 239538 | 5509.388s |
| Fresh07 | `01M6855WHNYHGCV6PFB5HPHAVH` | Initial/final PASS; terminal audit PASS | 3/8/9/3/5/2 | BLOCKED35 | 321796 | 7532.944s |
| Fresh08 | `01M68CMQAZNN7QGRZSX5DGRMYY` | Initial PASS only; final NOT_RUN; terminal audit NOT_PROVEN | 3/8/9/0/0/0 | Native FAILED during operator stop; order BLOCKED/OPERATOR_SHUTDOWN | 121357 reported; interrupted generation UNKNOWN | 2811.756s |

The independent checks covered the complete declared two-function scope:
host and target compilation, **630 host assertions**, **351 simulated target
assertions**, simulation call-cost checks and declared object/frame resource
limits. These are separate from model-authored tests and same-model inspections;
their counts must not be added to authored-test totals.

The timing contract was simulation-only: 64 target instructions and 100µs per
call at the pinned 100MIPS model setting. The resource evidence is object-level
and maximum frame, not a linked full-firmware or call-graph worst-case budget.
No physical-hardware timing/WCET or HIL claim follows.

Fresh workspaces initially lacked candidate C. Their distinct candidate hashes
were bound to native writes, frozen inputs and the independent checks:

| Case | Candidate header SHA256 |
|---|---|
| Baseline05 | `9aa11db10b4547cc4f440f91e3d4e513f006906b83a1c1a77e26fbf9ebedf76e` |
| Fresh06 | `e52e3763dd46d25d8732613c953293dbacce6de907cfb1f808b7b0c3157d89f2` |
| Fresh07 | `70d5558762d299a8ce664dc0aa589b42c77425e969ec365e5430badbbaced689` |
| Fresh08 | `c0851300b39ff6a8b782887ffd51a13a45190e3bbf8320765718de95b9aa9535` |

The exact four generated headers are included in the
[final evidence directory](https://github.com/jnsagai/forge-c/tree/dce7ad273e6cb31d6bcca1060f1e4e54eadd2acf/evidence/014-durable-local-autonomy/overnight-window-end-20261031),
copied from the actual sealed archives or final private partial snapshot and
hash-verified. No candidate C was executed locally during this review.

Fresh06 and 07 sealed packages contain byte-exact final verifier receipts and
their report entries; candidate, all14frozen inputs and phase-file hashes match.
Local transfers were verified. Archive hashes:

- 06: `3aced187a1d34d938f08e85d1b40160b0afe4f4c07b3adece51d4808f45174ef`.
- 07: `8a02a83573cf5d47c8c6078af9e2322c3d5dbd7a5483345d389f162b3280e103`.

07's scoped PASS does **not** mean complete phase delivery: SWE.6 has trace
files only, no verification report or executed Robot verification. Its
SWE.5 inspection record is missing after timeout. The frozen milestone permits
failed/missing phase outcomes when all attempts are recorded and available
artifacts plus explicit gaps are packaged. Its C artifact-delivery status is
explicitly candidate-files-only. The 35 gaps remain blocking for strict release.

08 reached SWE.3 inspection, with unchanged initially verified C, but never
reached SWE.4–6, final independent recheck or sealed packaging. It stays in the
denominator. The final summary SHA256 is
`71b8773faed8ce85660446d7a08cc821b6daf43378dfeea2923b377fe795fcb5`:
**2/3, all_frozen_trials_qualified=false**. No unfavorable case was replaced.

## 3. Generic factory defects identified and fixed

These are framework/protocol issues, not exclusively defects in the CRC example.
The four fixes A–D remained **inactive** during the frozen comparison.

Earlier in this window, producer
`0e342eef3c68786d29e5b9843606892c4ab68b60` corrected premature package sealing:
the release-manager MCP visit inventories the development candidate, while
sealing waits for the final graph-verifier receipt. Two regressions failed
before; exact68PASS. Baseline05 and fresh06/07 then provided actual native
archives with the missing receipt correctly inside. Native03's old archive was
left unchanged and remains NOT_PROVEN. This packaging fix was activated only
after the preceding run settled; later comparison members stayed pinned to0e.

Separately tested provenance revisions added bounded successful native write/edit
replay (`13d734afb64da594d9694b72ba5ce4ac0e906360`, exact85PASS) and the read-only
CLI (`30371da548bad2790a9f3c21dafc8964047ce06d`, exact88PASS). Wrong roles,
pending/ambiguous edits, changed bytes and incomplete coverage remain unverified.
The baseline05 producer's internal UNVERIFIED_EDIT_CHAIN/NOT_PROVEN was not
rewritten; the external pinned auditor reconstructed its actual accepted chain
and bound the archived bytes. Earlier supporting fixes preserved imported
cumulative request/tool/correction counts, bound the initial native author,
made diagram diagnostics bounded/canonical, exported protected test history and
corrected opt-in Robot/include-flag guidance. These external engineering changes
are not autonomous Qwen repairs or additional product qualifications.

### A. Normal GPU contention accumulated an hour-long handoff delay

`scheduler.cycle` applied the normal exponential dependency cooldown to sole
`NATIVE_INFERENCE_CAPACITY_HELD`. After a completed job had proven
QUIESCENT/RELEASED, the next order could still be ineligible for up to3600s.
Conductor was alive; inference capacity was not incorrectly released.

Fix `d2e083e322aeb3286e6d94bd0d51e532f7d66fb7` uses the existing Store/scheduler
with a constant15s eligibility retry only for that sole issue. Mixed/dependency
failures keep60..3600s backoff. No new scheduler, history clear, budget reset or
forced lease release. A regression failed before with3600vs15s; exact117PASS.
The bound is eligibility retry, not a guaranteed15s dispatch SLA.

Both overnight handoffs used disclosed existing-Store administrative reprobes
after independently proven quiescence. 07 retained defer history7→8; 08 retained
9→10. Source, model, manifests, limits and mission expenditure stayed unchanged.
Ordinary Conductor then launched the order. This is **not qualified unattended
handoff or factory self-healing**.

### B. MCP-injected defaults invalidated valid authorization tickets

The native MCP SDK materializes optional factory defaults such as `defines=[]`
and `evidence_refs=[]`. Old argument normalization compared
`FieldInfo.default` (Undefined for a factory) instead of these empty container
defaults. The hook authorized an omitted argument, but the server hashed a
different expanded call and returned `NO_AUTHORIZATION_TICKET`.

Actual03/05/06 normal compile calls each had3such denials. 07 reproduces differing
runtime hashes on both compile and TEST-declaration paths. This can affect any
provider omitting optional containers, rather than only Qwen or this peripheral.
It helps explain missing normal objects/stack files; those are not observed
resource overflows or evidence that the C had syntax errors.

Fix `50a4813d8d66d6af31e61f78e7eb0678e2eb3e5d` normalizes builtin list/dict
defaults on both sides, retains single-use and nondefault argument binding, and
does not execute arbitrary/context-dependent factories while authenticating.
Four counterexamples failed before. Follow-up
`3788ace6b0c4dbfb6f3736e811998d5e900ca2fc` covers the actual-shaped missing
evidence_refs declaration. No incident or lesson was fabricated for the tests.

### C. A timed-out stage left a draining request ahead of fast429retries

07 SWE.5 inspection timed out after900000ms at06:48:29.810817 serviceUTC.
Its prior model request completed only at06:48:48.707, producing11569tokens and
175tool calls. Six requests from the next two author stages were correctly
refused `INFERENCE_REQUEST_BUSY`, with upstream_called=false, before it drained.
Both SWE.6 author stages exhausted rapid429retries and produced no verification
report. The preceding stage being terminal was correctly **not** treated as
provider quiescence.

Fix `60619be076d36d50f42aef0c1b467aa2c2c14e76` places the gateway's existing
bounded Admission queue before durable reservation/measurement. After waiting,
the existing ledger and authority/provider/operator checks still run before
generation. It does not replay a prior generation or free uncertain ownership.
Unknown provider outcomes remain blocking even if the in-process queue is free.

Five actual ASGI/HTTP/ledger fixture scenarios failed before and passed after:
completed drain, operator stop while queued, execution revocation, unknown
provider outcome and bounded queue timeout. Peak upstream concurrency stayed1,
the execution lease stayed held, and historical charges were retained.
**Native effectiveness of this fix is NOT_RUN.** It prevents the demonstrated
cascade in fixtures; it does not claim to solve the original inspection timeout.

### D. Target author guidance required an undeclared legacy interface

Old guidance explicitly required `ll_crc_regs`/offset names despite the supplied
typed device-pointer contract. Authored target tests initially failed to build.
Inactive `d0090099c2961c71aa28623b53eda03e790e3ea2` uses the declared API/target
contract instead. Failed-before regression and exact95PASS; five strict graph
hashes unchanged. No measured live improvement yet.

## 4. What Qwen repaired, and what it did not

06/07 host unit executables initially reported no assertion failures, but duplicate
UT IDs caused metadata FAIL. Qwen regrouped predicates to satisfy unique IDs.
In07, quoted CHECK calls changed27→9 and distinct IDs10→9. Pattern order,
short-circuit evaluation and failure localization changed. In06, additional
instance checks and changed ordering were also observed. These are **not**
described as ID-only or proven assertion-preserving repairs. Protected before/
after sources and failed results are preserved.

07 target tests were different: after an initial legacy-interface build failure,
13simulated assertions passed and3failed. Qwen added `volatile` to its authored
MMIO extern in both target/performance tests; the two protected diffs otherwise
only change a comment, leaving assertions textually unchanged.16assertions then
executed without failures. Overall MCP status remainedFAIL for undeclared test
change because TEST-declaration calls hit defectB above.

That is concrete autonomous **test-harness editing**, not a driver-code repair,
factory-source self-healing or independently measured learning gain. The generic
SDK/scheduler/gateway fixes were made externally by Codex. The independent
immutable oracle remained separate and unchanged.

## 5. Deadline enforcement, accounting and learning gaps

At external07:56:35UTC, the existing operator-intent path requested STOPPED epoch7.
The already-running guard retired only the captured private provider namespace,
then reconciled actual native/request ownership. Kernel provider quiet was
observed by07:56:58; all six settlement predicates were true by07:57:19:
STOPPED, effective_stop, kernel provider quiet, no held execution, no inference
holder and no nonquiescent request. No grant was renewed or deployment activated.

08 native FAILED during that stop; execution reason is OPERATOR_SHUTDOWN.
After physical settlement the AFO order still readRUNNING. A disclosed model-free
existing-dispatch reconciliation, with recovery=None, projected its terminal
attempt and order to BLOCKED/OPERATOR_SHUTDOWN. No native launch, artifact edit,
capacity release or budget change was performed by this administrative backstop.
The stop/finalization path therefore still needs unattended end-to-end coverage.

Final cumulative mission, unchanged lineage and ceilings:

| Counter | Recorded value |
|---|---:|
| Attempts / unique executions | 7 / 7 |
| Requests | 1470 |
| Tools | 2583 |
| Implementation corrections | 0 |
| Conservatively charged/reserved tokens | 467140608 |
| Historical usage uncertainty | TRUE |

Reservations are **not** measurements of generated tokens. Interrupted output
and historical expenditure uncertainty remain; nothing was reset/refunded to
make a continuation appear cheaper. New orders/grants must not forget this
mission's history. Post-deadline actions were model-free metadata projection,
copying/hashing, read-only observation and report publication, not new inference
or execution of verification C.

An earlier read-only learning observation confirmed completed03/05/06 JOB/all6
phase facts and durable dispositions:33NO_NEW_LESSON/39DEFERRED_BUDGET at that
observation, zero qualified lessons/transfers. These are timestamped observations,
not current all-run totals or extra jobs. Default zero synthesis allowance is
separate from engineering mission exhaustion. No learning benefit evaluation
including overhead has run.

Critically, the stopped08 store check at08:09:24externalUTC found only SWE.1/2PASS
facts, **no final JOB/interrupted SWE.3 learning disposition yet**, still zero
qualified lessons/transfers. It was not backfilled and presented as automation.
This is a concrete remaining gap in finalization after operator stop.

## 6. Exact validation and preserved limits

| Tested revision | Result and scope |
|---|---|
| `0e342eef3c68786d29e5b9843606892c4ab68b60` | 68PASS, failed-before packaging regressions; actual subsequent native archives bind final receipts |
| `30371da548bad2790a9f3c21dafc8964047ce06d` | 88PASS, read-only source-audit CLI and negative controls |
| `d2e083e322aeb3286e6d94bd0d51e532f7d66fb7` | 117PASS, queue/mission/native-liveness regressions |
| `50a4813d8d66d6af31e61f78e7eb0678e2eb3e5d` | 77PASS/2disabled-live-FabroSKIP, MCP default fix |
| `3788ace6b0c4dbfb6f3736e811998d5e900ca2fc` | 79PASS/2disabled-live-FabroSKIP, declaration follow-up |
| `8c7fb8e1d84e99f5018bc26072333673c066c651` | 18PASS, offline frozen-cohort reporting; not a new independent audit |
| `d49cf1ee` (full SHA in receipt) | 171PASS/2disabled-live-FabroSKIP across173unique combined cases |
| `60619be076d36d50f42aef0c1b467aa2c2c14e76` | 79PASS/zero errors/failures/skips; separate inherited gateway/full-request-measurement22PASS |

Cohorts overlap; **do not add their counts**. Supplied synthetic fixtures are
not fresh Qwen products. Real MCP registration, ASGI transport, ledger and
authority paths were exercised in fixtures; native post-fix qualification remains
unrun. Exact environment, commands, failed-before results and raw JUnit hashes:
[gateway qualification](https://github.com/jnsagai/forge-c/blob/dce7ad273e6cb31d6bcca1060f1e4e54eadd2acf/evidence/014-durable-local-autonomy/gateway-queue-60619be0/commands-results.json),
[MCP declaration qualification](https://github.com/jnsagai/forge-c/blob/dce7ad273e6cb31d6bcca1060f1e4e54eadd2acf/evidence/014-durable-local-autonomy/native-repair-ticket-3788ace6/commands-results.json),
[combined qualification](https://github.com/jnsagai/forge-c/blob/dce7ad273e6cb31d6bcca1060f1e4e54eadd2acf/evidence/014-durable-local-autonomy/combined-regression-d49cf1ee/commands-results.json).

Changed gateway/SDK/new-test Ruff checks passed. Two inherited scheduler import
ordering findings remain. The inherited RCC graph-golden mismatch was not
rewritten, waived or described as passing. Static58requirement/task/acceptance
mappings,6schemas/38fixtures and14design checks are separate from runtime proof.

Earlier native03 remains M1NOT_PROVEN: its final receipt was outside prematurely
sealed archive2cbfa28a... . It was not repacked. Other admission/role/guard setup
failures, expenditures and uncertainty remain in historical evidence. No safety,
review-disposition, patch-bundle, production or model-capability signature was
invented. No EGM runtime, replacement scheduler/memory store or extra release
authority was introduced.

## 7. Evidence index and artifacts

All links below pin the final feature evidence revision, not a mutable status:

- [Window end, all three fresh outcomes, shutdown/clock/accounting proof, actual headers](https://github.com/jnsagai/forge-c/tree/dce7ad273e6cb31d6bcca1060f1e4e54eadd2acf/evidence/014-durable-local-autonomy/overnight-window-end-20261031).
- [Fresh07 terminal audit and35gaps](https://github.com/jnsagai/forge-c/tree/dce7ad273e6cb31d6bcca1060f1e4e54eadd2acf/evidence/014-durable-local-autonomy/fresh07-terminal-20261031).
- [Fresh06 terminal audit and16gaps](https://github.com/jnsagai/forge-c/tree/dce7ad273e6cb31d6bcca1060f1e4e54eadd2acf/evidence/014-durable-local-autonomy/fresh06-terminal-20261031).
- [Native timeout/drain timeline and gateway fix](https://github.com/jnsagai/forge-c/tree/dce7ad273e6cb31d6bcca1060f1e4e54eadd2acf/evidence/014-durable-local-autonomy/gateway-queue-60619be0).
- [Target harness repair blocked by factory ticket defaults](https://github.com/jnsagai/forge-c/tree/dce7ad273e6cb31d6bcca1060f1e4e54eadd2acf/evidence/014-durable-local-autonomy/native-repair-ticket-3788ace6).
- [Protected unit rewrite history](https://github.com/jnsagai/forge-c/tree/dce7ad273e6cb31d6bcca1060f1e4e54eadd2acf/evidence/014-durable-local-autonomy/fresh07-unit-history-20261031).
- [Delivery task ledger](https://github.com/jnsagai/forge-c/blob/dce7ad273e6cb31d6bcca1060f1e4e54eadd2acf/specs/014-durable-local-autonomy/DELIVERY-FIRST-IMPLEMENTATION.md) and [handover](https://github.com/jnsagai/forge-c/blob/dce7ad273e6cb31d6bcca1060f1e4e54eadd2acf/specs/014-durable-local-autonomy/HANDOVER-CODEX.md).

Private local inspection root, on loop10:
`/media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c/inspection/feature014/2026-10-30-qwen/overnight-afo-delivery/`.
Sealed earlier packages are preserved.08has an active76file snapshot and a
final87file partial snapshot, all captured file hashes and transfer ZIPs verified.
Final partial-copy SHA256:
`c2037d61215b9040c14c3a2b148068a2cd1cec1cb8a20c8f53088fd92d280e63`.
It is explicitly **not** a sealed native review package or final verification.
Full private ZIPs and manuals are not published in Git. Raw JSON gzip/pretty-view
hash bindings are explicit; decompress before comparing original receipt hashes.

## 8. Questions and next execution priorities for Astra

1. Review the three small generic fixes against their failed-before/native
   evidence. Qualify the composed source in a new explicit finite window,
   especially MCP optional-container calls and timeout→drain→next-stage handoff.
   Do not silently renew the expired grant or reset the cumulative mission.
2. Integrate bounded terminal queue projection and factual-learning disposition
   draining into the existing stop/reconciliation path. Require proof that no
   new inference starts and every stopped job's actual outcome is captured.
3. Diagnose the original900s inspection overrun and late175-tool-call response.
   Measure serialized context, useful obligations, duplicate tool work and time
   budgets. The queue fix handles the cascade, not that underlying workload.
4. Separate legacy array/define checker assumptions from genuine missing author
   metadata. Use the declared API/target adapter and stable predeclared unit IDs;
   retain strict quality findings rather than fabricating register arrays or
   retrospectively supplying missing evidence.
5. Preserve this2/3cohort. Define any corrected-source comparison prospectively,
   retain all attempts/interruptions/charges, and close DF-T010 only with its
   required three fresh terminal functional products. Then expand LL→HAL/another
   peripheral with independent checks; do not generalize from two CRC functions.
6. Qualify diagnosis, authoring, inspection and maintenance separately. Same-model
   agreement does not replace independent correctness. Keep capability-limited
   jobs scoped/blocked while model-free factory operation continues.
7. Treat the30-product benchmark, RCC qualification, overhead-inclusive learning
   benefit and24/72/168-hour workload/fault campaigns as **NOT_RUN/unproven** here.
   Specification validation and a bounded overnight run do not substitute for them.

The immediate evidence supports fixing protocol and lifecycle defects before
assuming that larger hardware, broader memory, EGM or a different model will
solve the demonstrated failures. It does not establish that the prepared fixes
will make the full factory reliable until native qualification measures them.
