# Prepared repeatability cohort and live test-history observation

Checkpoint: 31 October 2026, 02:35 UTC. This directory records preparation and
read-only observations, not a completed repeatability experiment.

The active native run is `01M67R1HNE9TKPWCYJ2SVKEPJS`, order
`afo-ee4282b25001a15d`, producer `0e342eef3c68786d29e5b9843606892c4ab68b60`.
It reached SWE.4 inspection after its initial independent functional PASS.
Its frozen candidate remains `9aa11db10b4547cc4f440f91e3d4e513f006906b83a1c1a77e26fbf9ebedf76e`.
Terminal packaging and all nine DF-M1 conditions remain pending. No active-job
source, model, input, candidate or steering change was made by this observer.

## Three fresh trials: PREPARED_NOT_SUBMITTED

`prepared-cohort/cohort.json` freezes orders 06/07/08, identical launch payloads,
input/oracle hashes, runtime source/profile and separately pinned source auditor.
Its SHA256 is `a14bfe74a0365a47360a630e09cdaec0338b10385ecb8be7a1b4d3389d18e759`.
All three launch payloads have SHA256
`3d0db25cf2c139b22cd72b8c70e24269930db75e198020a60807824e8dc68607`.
`preparation-result.json` records zero submitted jobs and zero model calls.

Admission requires a separate immutable binding to a qualifying terminal DF-M1
packet. These files do not establish that prerequisite. Submit through existing
AFO intake/Conductor only, one inference at a time, retaining the same mission,
historical expenditure and original 07:57:59 UTC deadline. Include every failed,
blocked, cancelled or unfinished cohort member; never replace a bad outcome.
Earlier retry 05 and prelaunch block 04 are not fresh trials.

`functional-verifier-identity.json` is a source-identity comparison, not execution
evidence. The producer and external observer retain identical functional
verification functions and underlying simulation/build modules. This separates
the source-provenance observer change from the frozen functional oracle.
Unpinned sampling and shared-host load preclude causal speed/learning claims.

## Actual SWE.4 test repair: mixed coverage

`unit-tool-observations.json` records the real FAIL and subsequent PASS results.
The first executable assertions passed, but duplicate UT IDs caused a metadata
failure; the trace check also lacked UT007. Qwen then rewrote the unit suite.
Protected snapshots are preserved as `failed-unit-test.c` and
`passed-unit-test.c`, with original hashes in `unit-refactor-observation.json`.
These files were copied/read/hashed locally; candidate C was not executed here.

This is **not an assertion-preserving ID rename**. Static CHECK calls changed
45 to 7, while walking-one/walking-zero loops and grouped predicates added other
coverage. Qwen added an explicit no-self-setup case and moved the startup check
before fixture reset. It removed separate zero-read register-preservation checks
and the check that writing another instance preserves the primary instance.
Static call counts do not measure dynamic assertions or total test adequacy.
The observed result is mixed coverage, with no measured adequacy or learning
benefit. LLVM host coverage reported line/function/region 100%; branch and MC/DC
were null, and target coverage was false. Do not present it as target MC/DC.

The product source hash did not change. Its preregistered independent host/target
oracle remains separate and passed earlier. No human test fixes or active-job
steering were supplied, and no historical result was relabeled. Final review
must retain this process finding alongside the independent functional evidence.

No DA task is closed by this checkpoint: DA remains 30/58, DF-M1 pending,
DF-T010 NOT_RUN, full LL/HAL delivery and 24/7 availability unproven.
