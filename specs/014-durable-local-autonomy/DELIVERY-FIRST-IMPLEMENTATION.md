# Delivery-First implementation and evidence ledger

Latest execution: [ten-hour AFO qualification](../../evidence/014-durable-local-autonomy/afo-delivery-overnight-20261030/README.md).
Clean sourcea34fdd85 now runs through real AFO admission/accounting. Native
01M67ETTPXS1Q73QPMQ98DNJX0 passed the preregistered full functional slice at
22:31:19UTC, correction0, and continues its six-phase journey. Terminal DF-M1
remains pending; this supersedes the earlier standalone-only checkpoint below.

This is the bounded implementation amendment to [DELIVERY-FIRST-E2E.md](DELIVERY-FIRST-E2E.md).
It does not replace the original 58-task Feature 014 ledger or close its runtime
qualification tasks. Source and native execution are separate: the first real
job uses `beb48b49`; the integrated verifier/correction-bound implementation is
`58ef89b7c798b7fdeb05aef08813f1b26a24a6a9`.
Actual commands, failed counterexamples, native qualification results and limits
are in [the independent evidence record](../../evidence/014-durable-local-autonomy/delivery-first-independent-20261030/README.md).

## Existing-engine implementation map

| Boundary | Existing implementation / smallest extension |
|---|---|
| Frozen new scope | `workorder.prepare`, `delivery_first.contract/preflight`; `examples/0014g-st-crc-idr-qwen-delivery` declares two APIs, authoritative inputs, excluded operations, compiler profiles and simulator adapter. No implementation header is supplied. |
| Intake/authority | Existing `afo/queue`, `runtime`, `product_job`, mission/request ledgers and operations intent remain authoritative. `afo/product_role_trial.preflight` now passes the actual development execution policy to the shared graph builder. The current standalone trial is **not** proof of AFO admission. |
| Native execution | `workflow/builder.py` invokes the opt-in `delivery_first.workflow`; three author/check visits at most, then the existing six SWE author/inspector paths and existing finalizer. The inherited extra SWE.3 fix author is removed only in this lane. |
| Mutation boundary | Existing `policy/authz.py` allows declared candidate edits only during eligible `df_author_0..2` visits, before their verifier intent. Later documentation/test authors cannot introduce hidden implementation corrections. No extra driver file or oracle edits are allowed. |
| Context/provider | Existing `llm_gateway`, `lrtx/request_measurement` and versioned Qwen profile measure complete serialized/template/control context. The 64K hypothesis failed on measured requests; profile v3 explicitly retains the already allocated 262144 capacity, without truncating evidence. |
| Functional tools | Existing allowlisted build profiles and host oracle; existing Renode and `simulation_performance` tools run the immutable target oracle in a separate verification snapshot. Both required APIs, complete input hashes, object footprint and maximum-frame limits are checked. No physical WCET or whole-program stack claim. |
| Final bytes | `delivery_first.verify(..., "final")` rechecks after all downstream work, without another model correction. Earlier failed candidates/receipts remain. A changed candidate or corrupted simulation proof cannot reuse PASS. |
| Evidence/package | Existing `release/finalize.py` includes JSON report, one-page `SCORECARD.md`, native event/usage metadata, six-phase file hashes, immutable attempt records and verifier inputs. Existing strict gates still determine release; functional PASS can coexist with BLOCKED release. |
| Learning/recovery | Existing factual experience, knowledge, reconciliation and supervisor mechanisms remain; neither lesson promotion nor an operational campaign is a prerequisite for this slice. No new scheduler, database or release authority. |

## Baseline triage

The cloud control r4 (`WO-F014-CC-20261030-LL-r4`, native
`01M66YMZK9JTMZCF2PNV4JRGCY`) was not a Qwen failure. The retained SWE.3
`measure_elf` results report **11216 bytes**, versus the unchanged 4096-byte
allocation. The generated per-function measurement object contributes 11216;
the include-only object contributes zero. This is an object-level measurement,
not linked firmware. The real capacity/gate failure, rather than an empty
routing defects array, explains the resource block. Other package gaps remain
separate. No budget or oracle was relaxed to make this control pass.

## Task status

| Task | Evidence-backed status |
|---|---|
| DF-T001 | Inventory and implementation map complete; r4 resource failure triaged. Active source, profile and provider observations are timestamped in evidence. |
| DF-T002 | Separate CRC scope and immutable host/target fixtures implemented; positive and behavioral/cost negative controls executed. Target simulation oracle is preregistered for **future** runs; first-candidate simulation was explicitly external/post-hoc. |
| DF-T003 | FIXTURE_ONLY native `01M6785DZFM30CS67KYZ9JNVWR`: all six author/inspector attempts, terminal SUCCEEDED; product BLOCKED51, integrity PASS. Zero Qwen generations. |
| DF-T004 | Opt-in manifest/profile implemented; strict/demonstration/policy regressions exercised. No global behavior switch or production activation. |
| DF-T005 | Real Omniverse Qwen authored new headers in both the earlier standalone native and current AFO native `01M67ETTPXS1Q73QPMQ98DNJX0`. Current successful write and in-loop verified bytes share SHA256 `855f53a6b3f90d83e60e03aacba50e953e9e3a2827c3730d6ae6746fff46b173`; initial candidate was absent. |
| DF-T006 | Current AFO native passed the preregistered host/target compile, 630 host assertions, 351 target assertions, simulation cost and resource checks in-loop at 22:31:19UTC, correction0. Final-byte recheck remains pending. Earlier standalone post-hoc checks retain their original external status. |
| DF-T007 | Six-stage truthful recording complete for the first native job: all author/inspector attempts retained; phase files 6/3/3/3/0/6. SWE.5 produced no phase files and remains an explicit gap. |
| DF-T008 | Packaging implemented/tested and real terminal archive verified: native SUCCEEDED, product BLOCKED57, archive integrity PASS; legacy functional report INCONCLUSIVE. Updated-source JSON/scorecard verified separately on Omniverse. |
| DF-T009 | Earlier unsuccessful qualifications and negative controls retained. Current clean-source `a34fdd85` trial uses actual AFO admission and has a full in-loop functional PASS; **DF-M1 NOT_PROVEN** until all-six-phase terminal packaging, final-byte recheck, integrity and external intervention audit are observed. |
| DF-T010 | NOT_RUN; blocked on DF-M1, not satisfied by fixture calls, copied candidates or resumed jobs. |
| DF-T011 | DEFERRED by specification until DF-T010; no new provisional dependency implementation. |
| DF-T012 | DEFERRED by specification until DF-T010; strict release remains unchanged meanwhile. |

## Acceptance traceability and limits

- DF-AT-001/002/008/015/017: existing `test_pipeline_demonstration.py`,
  `test_demonstration_repair.py`, plus `test_delivery_first.py` graph/finalizer
  cases retain failed/missing reviews and release blocks.
- DF-AT-003/005/006/007/009/013: delivery tests exercise missing candidates,
  tampered immutable oracle, compiler failure, independently detected mutants,
  both successful APIs, final-byte changes, corrupt independent snapshots and
  unsupported target/compiler/simulator selection. Declared-header measurement
  regressions require the full API set and bind all declared inputs.
- DF-AT-004: actual native write evidence, not the deliberately supplied GOOD
  test fixture. Native-event tests reject failed writes, wrong roles and wrong
  content; events alone do not establish an approved local provider origin.
- DF-AT-010/011: existing execution/request lease and operator-intent paths
  remain binding. A new live Delivery-First contention/stop campaign is NOT_RUN;
  standalone native traversal does not qualify these authority boundaries.
- DF-AT-012/014: NOT_RUN and intentionally deferred. No repeatability claim.
- DF-AT-016: fixture-only native packages are visibly BLOCKED; deterministic
  functional PASS never establishes Qwen authorship or DF-M1. Metrics retain
  UNKNOWN for unverified local-model cohorts/interventions/request counts.

Reports must distinguish runtime implementation, native model capability,
functional product evidence, process/release eligibility and operational
availability. No full LL/HAL, ASPICE compliance, production, generic embedded-C,
learning-benefit or 24/7 claim follows from this increment.
