# Qwen reasoning-speed comparison: native high rejection and prepared medium pilot

Owner's latest instruction supersedes the brief stop request: **finish the current run,
then benchmark reasoning/MTP settings**, retaining Q8 and262144 context. No stop command
was issued; production remains RUNNING epoch72. No model benchmark competes with this run.

## What the installed model actually supports

The real Omniverse2 provider's pinned Qwen3.8 Q8 template is8952bytes, SHA256
c3cf9e34abf4f9e36c2d72165aa9c132d3e2a725b6c2586aaa3a8af9d7a81041.
Native **POST /apply-template**, with explicit effort and enable_thinking=true:

| Requested effort | Native result | Meaning |
| --- | --- | --- |
| xhigh | HTTP200; explicit xhigh instruction present | Supported |
| medium | HTTP200; no xhigh/low instruction | Supported |
| high | HTTP500; Unexpected reasoning effort high | **UNSUPPORTED** |
| low | HTTP200; explicit low instruction present | Supported; not selected for inference comparison |

[Actual native preflight](native-template-preflight.json) binds model digest and template/rendered hashes.
It rendered only a fixed synthetic probe: **zero inference**, request ledger **650→650**.
No raw prompt, rendered prompt or hidden reasoning is stored. The loaded model/runtime was unchanged.

Earlier advice to compare high was premature. The installed template explicitly supports xhigh,
medium and low; a generic runtime flag accepting “high” does not establish model support.
High is recorded with speed=null, model_requests=0 and silently_mapped=false, never renamed to medium.
These modes condition the model's prompt; the token reserve remains fixed. Medium is not guaranteed faster.

## Implemented executable preparation — source94b5a68

[reasoning_comparison.py](../../../factory/python/forge_factory/lrtx/reasoning_comparison.py)
extends existing Feature014 qualification input preparation, frozen manifests,
configuration comparisons and reference fixtures. It creates no scheduler, authority or memory store.

Only an opt-in **medium-trial** profile is added. Q8 weights/digest, f16 KV, MTP3,262144 context,
sampling, batch settings, one inference and existing gates remain fixed. Both native default and
gateway effort are bound to medium. Tests prove that setting only the client request to high/medium
does not override the existing xhigh gateway policy. The active xhigh profile is unchanged.

The first pilot is **recovery diagnosis only**, four seeded cases ×two repeats =eight cases per setting,
fresh xhigh baseline then medium. Cases cover a late decisive finding, register counterexample,
upstream ownership and missing primary evidence. The existing compiled260-input checker gives194 failures
for the seeded implementation and zero for its fixed reference. Holdout classification and unchanged
semantic broker remain. No fabricated product incident or lessons are created.

This pilot does **not** qualify authors/inspectors or show a complete pipeline speedup. The requested
mixed pipeline remains a subsequent experiment: the installed model permits **medium authors with
xhigh review/repair**; high authors are unsupported. No mixed routing was silently activated.

Six common controls and all complete serialized request measurements are frozen before execution.
The comparison preserves failed attempts, token costs and learning overhead. The report now labels
**end_to_end_output_tokens_per_second** separately from backend decode throughput; missing native decode
timing remains null. Native backend timings must be correlated separately, not inferred from visible
answer chunks after hidden reasoning has been removed. MTP is a **subsequent separate factor**;
do not change reasoning and MTP together and attribute the result to one.

The clean exact-source CLI at **94b5a68d22e88c010a04ca5d4356422551790a52** ran locally and prepared
eight cases/configuration, unsigned manifests and an honest NOT_RUN report, with source_dirty=false,
zero model requests and no authoritative queue/job/mission.
[CLI result](clean-source-local-cli.json). Preparation does not install or activate the profile.

## Verification

- Local regression **96PASS,0failures/errors/skips**: [JUnit](regression-local.xml).
- After the reporting-rate addition, final affected cohort **31PASS,0failures/errors/skips**:
  [JUnit](final-delta-local.xml). The broader cohort is not claimed rerun after that addition.
- Initial preparation cohort11PASS; selected Ruff E9/F and git diff checksPASS.
- Exact clean-source CLI preparationPASS at94b5a68; no local Qwen inference.
- Prepared verifier fence **5PASS** against real owned local child processes: normal completion,
  timeout, operator resume, operator stop and unreadable intent. [Tests](test_qualifier_fence.py), [JUnit](qualifier-fence-local.xml).
- Native qualification **NOT_RUN**. Actual check-only refused because the production execution
  is still live and operator mode RUNNING: [record](native-precondition-check-NOT-RUN.json).
  This is a correct precondition refusal, not a failed test or deployment.

[Exact commands and tested-source distinctions](commands-and-results.json).
No task checkbox changed; formal Feature01430/58 remains.

## Current product execution and actual feedback transfer

Runtime **899865d5f256e3c2fbdd836ba8696ef9cdb6fa8f**, RUNNING72,
LL afo-f3ad027406784ef7, native01M65TR9K7DRDTM8AX8ZTP445G.
At 2026-10-30T08:23:09.635825Z: nativeRUNNING / LIVE / HELD, 22 completed requests
and one SENT. [Actual observation](current-native-observation.json).

First complete review: four model criteriaPASS, SWE1-02FAIL/six findings,
SWE1-04FAIL/one missing CPU-allocation finding. The ordinary author loop automatically
returned once (durable phase_reworks=1). All **seven complete findings** are present in
the author visit, including text beyond the200-character display summary.
[Full published findings and exact transfer audit](first-review-to-author-feedback.json).
This proves feedback transfer and automatic author return; it does not prove the correction
succeeds, independent model correctness or full unattended factory-code self-healing.
Do not invent a CPU allocation. Same mission/history/counters/uncertainty and existing
**2026-10-30T13:52:52Z** deadline remain. HAL is not submitted.

## Concrete next native execution

Prepared files already on Omniverse2 under /mnt/data/forge-c/production-local-014/deployment/:
- qualify-native-reasoning-comparison-94b5a68.py
- qualify-reasoning-comparison-maintenance-window.py
- reasoning-comparison-94b5a68.bundle (delta from deployed899865d)

Reviewable copies: [native worker](qualify-native.py), [fenced window](qualify-fenced-window.py).
The worker now cancels its own verifier process group if operator intent changes during execution,
not merely checking before/after. It records its own source hash. The window also stops and verifies its owned verifier scope before resuming inference,
including after worker failure; a660-second systemd scope limit bounds orphaned work.
The maintenance window requires
RUNNING72 and actual native/resource quiescence; pauses73 and resumes74 only if that exact pause
still owns intent. A newer operator stop/resume wins. One verifier/four CPUs/8GiB RAM/finite bounds,
no GPU/network/owner identity/SSH agent, zero model calls. No source activation by qualification.

After the **current full LL finishes**, collect its archive and verify native quiescence/released
leases. Run the fenced native qualification window. If96 native checks pass, prepare exact finite,
source/profile-bound benchmark grants under the existing owner signing delegation, then activate
the explicitly scoped comparison. The current RCC xhigh grant does not authorize medium requests.
Do not renew the RCC mission or reset its counters. Native input preparation command after exact
source/profile qualification:

    python -m forge_factory.lrtx.reasoning_comparison \
      --out <new-native-deployment-directory> \
      --compiler /mnt/data/forge-c/production-local-014/toolchains/LLVM-19.1.7-Linux-X64/bin/clang \
      --capabilities <fresh-matching-native-template-preflight.json>

Then use the existing forge_factory.afo.qualification freeze/enroll/provision/step/report and
configuration_comparison commands on the exact generated campaign files, with signed finite
missions, policy and independent audits. Those live steps are **not yet run**.
Qualify baseline and medium serially. Preserve all failures and report unsupported high explicitly.
MTP comparison and complete mixed pipeline remain pending; no automatic model/config deployment
is authorized by a measured pilot report alone.

Do not submit the old hard-coded899 HAL intake while the newly requested benchmark is pending.
After comparison, bind the dependent HAL to its actual sealed LL and the then-qualified source/profile
under the same RCC lineage/remaining allowance. Strict imports/gates remain separate from the provisional
QM demonstration. Full LL/HAL product success, learning benefit and24/72/168h operation remain UNPROVEN.
