# Claude handoff — Feature 014 — 31 October 2026

The owner asked Codex to finish its current increment, stop and leave this
handoff. **Do not automatically start a model run, activate a deployment or
extend a grant from this document.** The broader goal is incomplete and is
being paused at the owner's request. Resume work when the owner directs Claude
to continue; live work additionally needs a current, correctly scoped execution
window/reference. The earlier question about that window remains unanswered.

## Start here

- Repository: https://github.com/jnsagai/forge-c
- Integration branch: `feat/014-durable-local-autonomy`; existing draft PR
  [#42](https://github.com/jnsagai/forge-c/pull/42), stacked on #41. Do not merge.
- Last implementation: `b8ecd2695b832c4905c5f538fda5b2c2193f8650`.
- [Typed-interface evidence](../../evidence/014-durable-local-autonomy/typed-register-interface-b8ecd269/README.md)
  records exact-revision tests and executable reproduction.
- Read the current `CLAUDE.md`, applicable `AGENTS.md`, constitution,
  [DELIVERY-FIRST-E2E.md](DELIVERY-FIRST-E2E.md), Feature 014 authored specification,
  plan, tasks, acceptance cases and contracts before editing.
- [Earlier detailed history and prioritized backlog](HANDOVER-CODEX.md) remains
  useful; this document supersedes its statement that the typed adapter is only
  a parked test draft. Historical evidence is unchanged.

Use the latest remote branch; preserve other Claude/Feature 015 work. The
original `/home/jefferson/forge-c` checkout is not this isolated implementation
worktree. Do not reset it or remove somebody else's worktrees.

```bash
git fetch origin feat/014-durable-local-autonomy
git log -5 --oneline origin/feat/014-durable-local-autonomy
git status --short
```

For isolation, choose an unused worktree path on loop10 and create it from
`origin/feat/014-durable-local-autonomy`. The existing Codex worktree is detached;
push reviewed commits with `git push origin HEAD:feat/014-durable-local-autonomy`.
If the remote moved, reconcile it without force-pushing or discarding changes.

## Completed at this handoff

The latest increment resolves a real declared-contract mismatch: the existing
SWE.3 implementation/regmap checks demanded a singleton register array and
invented numeric defines, whereas the two-function Delivery-First input requires
a typed device pointer and immutable device header.

An explicit `delivery_first.register_interface` opt-in now uses the existing
SWE.3 verifier, compiler profiles, frozen inputs and artifact store. It validates
offsets against a declared primary manual, member width/volatility and compiled
API signatures. It checks numeric register defines when present. No hardware
facts are hardcoded in the adapter. Existing allocation, inline/function,
no-wait, no-extra-unit and behavioral checks remain. Unselected orders retain
the legacy interface checks. This is a typed-layout check, not functional,
process or release acceptance.

Changes: `inspection/typed_registers.py`, existing `inspection/regmap.py`,
`inspection/implementation.py`, `delivery_first.py`, the example's input
manifest/README and declaration-only `IDR-API.h`; tests are
`test_typed_register_interface.py`. Inputs and candidate hashes bind the proof
at `verification/static/typed_register_layout.json` and its artifact reference.

The new example input changes future intakes from **14 to 15 frozen inputs**.
Its declarations express the existing IDR contract, supplying no implementation.
Create a new baseline/cohort for native evaluation. Do not edit historical
workspaces, change frozen grants in place or count a new trial as the old third
trial. Local tests use explicitly synthetic C; no Qwen C was executed locally.

The focused suite passes 24 cases. The ten-file inherited cohort passes
141 cases with 3 missing-manual skips and no failures; exact source receipts
are in the linked evidence. Ruff, 14 static design checks, specification and
contract validators pass. Static validation is not runtime qualification.
No original DA task is newly closed by this increment.

Other tested fixes available on this branch but **not activated remotely**:
- `a4bc71d1`: durable source lifecycle snapshot for shutdown-order projections.
- `c0777ead`: fenced, durable shutdown outcome projection to the bound order.
- `6a4721ec`: complete CHECK-ID duplicate scan and metadata-only repair guidance.
- Earlier gateway bounded admission, tool-schema defaults, GPU-capacity retry,
  declared device/API author inputs and cohort reporting fixes are documented
  with their exact tests in HANDOVER-CODEX.md and evidence.

The Astra overnight report is already on main, report-only commit
`45190ebca727d28225e9ee61e0908fd0ffdae166`:
[ASTRA-OVERNIGHT-REVIEW-20261030-31.md](https://github.com/jnsagai/forge-c/blob/45190ebca727d28225e9ee61e0908fd0ffdae166/docs/reports/ASTRA-OVERNIGHT-REVIEW-20261030-31.md).
Implementation remains on the feature branch.

## Remote state and authorization boundary

Last retained read-only state: Omniverse2 factory intent **STOPPED, epoch 7,
effective_stop=true**; no inference holder, held execution or nonquiescent
request. Original ten-hour window ended 31 October **07:57:59 UTC**. Physical
settlement was verified at **07:57:19 external UTC**. All eight configured grants
expired. Existing signing delegation was limited to that window; do not silently
renew it. Host clock lagged external UTC by about a minute.

Remote experiment:
`/mnt/data/forge-c/delivery-first-afo-014-20261030-v1`.
Intent: `control/operations.json`; environment: `control/runtime-env-v6.json`.
Its source is still the old `0e342eef` producer, not the latest tested branch.
Use existing operator-intent, admission, quiescence and activation mechanisms;
do not bypass STOPPED or replace ledgers. Recheck current state read-only before
an authorized continuation; this handoff records the last observation.

Original mission `mission-feature014-delivery-first-20261030` remains at
7 attempts, 1,470 requests, 2,583 tools, 0 corrections and 467,140,608
charged/reserved tokens, with usage uncertainty retained. A new order/window
must not reset this history or an exhausted allowance.

The separately requested Ornith benchmark is complete:
[raw results and interpretation](../../evidence/014-durable-local-autonomy/ornith-reasoning-speed-20261031/README.md),
commit `361756837c202bd23612243a31c731eb7592b9e6`. Its server was terminated,
endpoint closed and GPU process absent. That request did not restart the factory.

## Actual product/model status

- Original DA ledger: **30/58 complete**, unchanged. Parked tasks remain parked
  unless reopened; do not tick them for documentation or fixture coverage alone.
- DF-T001–DF-T009: completed only within the recorded two-function CRC scope.
- DF-T010: **NOT_COMPLETE**. Original fresh cohort is **2/3**, not a repeatability
  pass. Do not drop the interrupted third case from the denominator.
- Trials 06/07 independently passed 630 host and 351 simulated checks, but their
  strict release packages stayed BLOCKED with 16/35 findings respectively.
- Trial 08 initially passed those checks, then stopped in SWE.3 inspection under
  owner shutdown. Native FAILED; no final verification or native package.
  Old audits remain unchanged.
- Full LL/HAL, generic embedded-C delivery, production readiness, learning
  benefit, local autonomous self-healing and 24/72/168-hour availability are
  **not proven**.

Ornith: 36 serial trials on Omniverse2, three cases × three seeds × four settings.
Decode medians: off 148.9, 512-budget 154.7, 2048-budget 153.9, default-on 153.3
tokens/s. Full-contract passes: 1/9, 0/9, 2/9, 4/9. The 2048 semantic total is
3/9 (one format failure); default includes one 8,192-token truncation. Named
low/medium/high/xhigh render identically in its actual template; measured
thinking budgets are the meaningful comparison. MTP was off in that controlled
study. This is a small pilot, not a qualification or authorization to switch the
factory model. Existing official Qwen selection remains unchanged.

## Next smallest work, in order

1. **Reproduce and review the committed increment locally.** Use the evidence
   directory's `reproduce.sh` and source hashes. Review compiler proof and
   negative controls. Keep local tests synthetic and keep the old strict path.
   The three skipped tests need copyrighted GPIO/TIM manual inputs; record
   missing prerequisites, never fabricate manuals.
2. **Resolve live prerequisites before activation.** Obtain the owner's current
   execution scope/reference and UTC cutoff through the existing grant workflow.
   Fetch current source/state; reconcile other agents' work. Confirm loop10,
   mounts, free storage, native liveness and STOPPED intent. Deploy/activate only
   within actual scope and the existing intent fence. No model or generated-C
   execution on the local machine.
3. **Qualify the cumulative fixes on Omniverse2 with a new frozen intake.**
   Prepare the 15-input typed-contract order with source/model/runtime/oracle
   hashes. Preserve original mission accounting and failed history. One admitted
   inference at a time. First prove the typed check via native MCP and preserved
   target compiler output; then follow the same native six-phase graph. Record
   genuinely authored code and independent initial/final verification separately.
   Do not infer live success from the local fixtures.
4. **Fix only the next reproduced framework defect.** Retain failing-before and
   passing-after evidence. Check gateway drain/admission, capacity retry,
   current tool signatures, duplicate CHECK-ID metadata repairs and declared
   API input use. These fixes have not yet proved live benefit. Do not invent a
   second scheduler, authority, memory store or universal hardcoded driver.
5. **Finish truthful phase/package evidence.** Known remaining gaps include
   allocated-name/interface traces, USPEC/Doxygen/test matrices, ordinary build
   ELF evidence and trial 07's missing SWE.6 verification report/Robot. Diagnose
   actual new findings; do not rewrite sealed historical packages, replace
   predicates with trivial checks or label advisory failures as strict PASS.
6. **Complete the declared repeatability cohort before expansion.** Preserve
   source/input/oracle identity and all denominators/costs. Then follow DF-T011
   LL→HAL/another peripheral ordering, using explicit device/API inputs and
   independent checks rather than specializing for CRC.
7. **Return to the broader autonomy backlog only after the blocking delivery
   path.** Interrupted-job final JOB/phase learning disposition remains missing.
   Native recovery/capability qualification, fault observer, RCC, 30-product
   benchmark, comparable learning benefit and 24/72/168-hour campaigns remain
   separate evidence obligations. See the existing prioritized backlog.

Known inherited issues: RCC graph-golden mismatch and scheduler import-order lint
findings were not repaired or silently waived. This increment ran the named
ten-file cohort, not every repository test. Full runtime model/tool recovery,
production activation and long campaigns were not run. No grant was signed and
no new native factory attempt was started at this handoff.

## Storage and inspection locations

Use **loop10 for all local project storage and test output**:
`B=/media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c`.

- Existing isolated checkout:
  `B/operations/feature014/recovery-after-overnight-20261028`.
- Local test scratch/evidence originals:
  `B/operations/feature014/incremental-m1-followup-20261029`.
- Copied Qwen packages/partial outcomes:
  `B/inspection/feature014/2026-10-30-qwen/overnight-afo-delivery/`;
  start at `START-HERE-20261031.md`. Trial 08 is partial (87 files), not a sealed
  full package.
- Complete local Ornith archive:
  `B/operations/feature014/incremental-m1-followup-20261029/ornith-speed-20261031.tar.gz`,
  SHA256 `bdbff40dda6f64cc9493ce145889abdfa9c2b2d3623fa51cfa86df7f879fb00d`.
  Remote benchmark: `/mnt/data/forge-c/benchmarks/ornith-speed-20261031`.
  Do not execute the copied remote binaries locally.
