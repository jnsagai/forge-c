# Scoped first Qwen functional delivery: DF-M1 PASS

The external [nine-condition audit](external-m1-audit.json) establishes
**FUNCTIONAL_MILESTONE_PASS** for the preregistered CRC IDR increment only:
`LL_CRC_Write_IDR` and `LL_CRC_Read_IDR`. All six SWE phases were attempted.
This is not full LL/HAL delivery, clean process qualification or production.
Strict release remains **BLOCKED with25gaps**. Original DA ledger remains30/58.

| Binding | Actual value |
|---|---|
| Native | `01M67R1HNE9TKPWCYJ2SVKEPJS` |
| Order / job | `afo-ee4282b25001a15d` / `afo-product-0fbf506c5889f9f7faa87f04` |
| Producer source | `0e342eef3c68786d29e5b9843606892c4ab68b60` |
| External source auditor | `30371da548bad2790a9f3c21dafc8964047ce06d` |
| Candidate header | `9aa11db10b4547cc4f440f91e3d4e513f006906b83a1c1a77e26fbf9ebedf76e` |
| Sealed ZIP | `4a20153d88fed3dea1c9499ce071e4230c1a3f54a484833d19f691c4a1703a79` |
| External M1 audit raw SHA | `9ffc4f5651d779cf831f22f436fb454e48c17c7c681f261f1b39e9621139af89` |
| Terminal facts raw SHA | `c28b073a2ecf93a71e4778bfeaddcb8ecb82fb79e912b83acebf671299047ec4` |
| Terminal source audit raw SHA | `6f9453c9ba5e481350e9798b2b0deb44df08b5fcf57defe43886b516698a56e5` |
| Runtime | Qwen3.8-27B Q8, f16KV, MTP3, medium, one262144-token slot |
| Model digest / profile SHA | `8f5fb6b71ea00052cbe8545738c55ce61112c4e571cb60ca4dad00b131766039` / `823942772335b7ef500f9f11926732405ac12dbff0dcc7f0ab39e345db3358e7` |

## What passed and what did not

Launch01:09:04UTC, initial independentPASS01:15:07UTC, final independentPASS
03:15:35UTC, nativeSUCCEEDED03:15:42UTC on31October. Final host-Clang/target-GCC
compilation,630host assertions and351simulated assertions passed for unchanged
candidate bytes. Independent target simulation/cost and object/frame resource
checks passed. The measured object total is16flash bytes/0static RAM bytes,
maximum observed frame0bytes. This is not linked firmware or call-graph stack
qualification. Simulation performance samples remain in the pinned100MIPS
Renode model, not silicon/WCET evidence. No numbered implementation correction
round was needed; ordinary first-author edits occurred.

The final receipt is **inside the original sealed ZIP**, byte-equal to its live
file and represented in the archived report. All14frozen input bytes match the
copies in the archived final independent-verification workspace. Available phase
files3/8/9/3/3/3 also match their archive hashes. The separately pinned303auditor
replays the native source write plus six accepted edits to the same archived
candidate. Actual model digestMATCH, isolated loopback-only network and profile
are recorded. Candidate was initially absent; no vendor implementation or
substituted responses were supplied. Both whole writes and all edits were
[preserved earlier](../native-edit-provenance-20261031/README.md).

SWE.1 and SWE.6 gatesPASS; SWE.2–5REWORK. Gate-node failures, missing annotation/
trace/normal-build-package evidence, legacy array/static-guideline findings and
all25release gaps remain in [terminal facts](terminal-facts.json). The old
`run_not_completed:INCOMPLETE` release finding is retained; native transport and
six-phase traversal completion are separate dimensions. No failed gate becomes
PASS. Current authored Robot results12/12 and target33checks are separate from
the preregistered independent oracle; their counts are not added. The actual
[unit mixed-coverage rewrite](../repeatability-preregistration-20261031/README.md)
and [target harness repair](../target-api-prompt-20261031/README.md) stay visible.

The original producer report still saysUNVERIFIED_EDIT_CHAIN/NOT_PROVEN and
UNKNOWN_REQUIRES_EXTERNAL_OBSERVER for interventions. It was not rewritten.
The bound external audit supplies source proof, terminal facts and zero observed
post-launch job interventions. Read-only observers and local unactivated source
work changed no job input, candidate, test, model or runtime. Prelaunch source/
role/provider/guard engineering fixes are disclosed in the earlier handoff and
are not autonomous healing. Observation is session-scoped, not a general
tamper-proof detector of every possible human action.

## Measurements and limits

Actual native API wall time7597.950seconds; ledger297request entries, all
QUIESCENT at terminal. Provider reports982904input,339976output and11534747cache-
read tokens. Author-role output219684 includes documentation/test authoring;
it is not a C-only token measurement. The reported reasoning counter is0but the
reasoning breakdown remains**UNKNOWN**. Time from preflight to first complete
functional result363.188seconds. Cumulative mission at cohort intake retains
4attempts,875requests,1493tools and265814016conservatively charged/reserved tokens;
these reservations are not actual generated-token totals. Historical uncertainty
and failure remain; no limits, charges or deadlines were reset.

Negative controls are indexed from actual303framework JUnit execution, with
compiler failure, behavioral mutants, absent/changed evidence and tampered
provenance cases. They use supplied synthetic fixtures and are not live-model
capability trials. Functional verifier source identity matches producer0e and
auditor303. Exact88tests and the later inactive prompt95-test cohort overlap and
must not be added. The inherited RCC graph-golden mismatch remains open.

## Three fresh trials admitted, no repeatability claim yet

The [preregistered cohort](../repeatability-preregistration-20261031/prepared-cohort/cohort.json)
SHAa14bfe74... was bound to this M1audit/archive by immutable
[admission binding](cohort-admission-binding.json), rawSHA
`8fa0c1667d6e84555f57981e069c5bf7c8128fa74153479ac4ffdd4b3d587bc4`.
Identical launch payloadSHA3d0db25c... is unchanged. Existing AFO intake created
06/07/08, one inference at a time; source0e/profile3/auditor303/frozen inputs and
oracles remain constant. Same cumulative mission, expiry07:57:59UTC.

06orderafo-7f71565db57f0a76 started native01M67ZJWDYS7H33828MPTK6E6D at03:20UTC,
candidate initially absent. It subsequently produced a new e52e3763... header
and initial independentPASS; terminal qualification is still pending.
07afo-f83452175591716f and08afo-48b5f7eb60495e69 were queued. All three, including
failures, cancellations and unfinished members, remain in denominator3. No old
retry, frozen candidate or copied response counts as a fresh success. Sampling
is unpinned/stochastic; shared load/cache state prevents causal speed/learning
claims. No new scheduler or grant renewal was introduced.

The first helper incorrectly checked role binding before Store.submit and was
refused before any new order/native/charge. Both versions and
[exact failure](intake-helper-failure-v1.json) are retained. Version2 follows the
existing intake sequence under the intent fence. Two post-terminal observer
assumptions were also corrected: the source-audit record wrapper needed a host
import path, and full manual inputs reside in the archived verification snapshot
rather than all appearing at the top-level inputs directory. Neither changed a
job, model or archive. No false M1 packet was produced by those failed checks.

## Reproduction and local inspection

On Omniverse, useE/venv/bin/python with the retained case05 terminal recorder.
The source-audit wrapper invokes the pinned303CLI inside the actual holder
namespace and records outside the job. `audit-native05-m1.py` checks the
transferred ZIP and receipts locally without executing candidate C.
`observe-fresh-cohort.py` reads AFO/Fabro facts only. The two intake scripts are
one-shot qualification tooling, not a scheduler. They cannot renew authority,
change source/model/configuration or bypass normal AFO admission/release.
Use the exact paths/commands in the scripts and raw receipt references;E is
`/mnt/data/forge-c/delivery-first-afo-014-20261030-v1`.

The private local package is under
`B/inspection/feature014/2026-10-30-qwen/overnight-afo-delivery/native-01M67R1HNE9TKPWCYJ2SVKEPJS/`
onloop10, withreview.zip/review-package/START-HERE.md/transfer-verification.json.
Its SHA matches the remote sealed original. No full manual/private ZIP is
published here. Readable JSON views and deterministic rawgzip are explicitly
mapped in [receipt representations](receipt-representations.json).

Completed scoped tasks:DF-T001–009. DF-T010RUNNING; DF-T011/012deferred.
Full RCC/LL/HAL, clean assessed ASPICE, production, safety, generic-driver
qualification, learned benefit and24/7operation remain unproven. The goal is
still active; the original owner window is not extended.
