# Feature 014 handover to Codex — 2026-10-27

The owner asked Claude to finish the work in flight, stop, and hand over to Codex. Continue
implementation, evidence and qualification from here; do not produce another plan or recreate the
specification. Feature 014 is still INCOMPLETE: **30/58 tasks** are ticked from passing evidence records.
No completion, product-success, learning-benefit or 24/7 claim is justified.

## Start here

- Repository https://github.com/jnsagai/forge-c, branch `feat/014-durable-local-autonomy`, OPEN DRAFT PR
  https://github.com/jnsagai/forge-c/pull/42 (never merge; merge to main only after the owner accepts, as a merge
  commit).
- Branch head at transfer: see `git log -1 origin/feat/014-durable-local-autonomy` (this handover is its last commit).
  Main (`38e2740`, Feature 015) is merged INTO the branch at `247562c`.
- Read first: `CLAUDE.md` (project contract), `.specify/memory/constitution.md`, then in this folder `spec.md`,
  `tasks.md`, `acceptance-tests.md`, `validation.md` (the dated sections at the end are the session log),
  `implementation-status.csv`, and `evidence/014-durable-local-autonomy/known-issues.md`.
- The previous transfer note (`HANDOVER-CLAUDE.md`, 2026-10-25) still holds for the protocol campaign
  machinery and the owner signing path; this file supersedes it where they differ.

## Owner decisions in force (do not ask again)

| Date | Decision | Effect |
|---|---|---|
| 2026-10-25 | "I do, I approve all" | Feature 014 live qualification approved (bounded). Not a production activation, merge or promotion. |
| 2026-10-26 | "95/100 is good enough!!! … report the known issues to be solved by a Human." | Protocol gate passes at 95/100 (DA-AT-024 `PASS_OWNER_ACCEPTED_95_OF_100`). Keep the known-issues register current. |
| 2026-10-26 | "Known issues only" | Live work stopped on DA-T004/005/007/010/012/013/018/019/021/031–036/040/041; each is KI-014-012..028. Re-check them against later campaign evidence, do not schedule them separately. |
| 2026-10-26 | Feature 015 split (seed 20261026) | Learning set 3 = SPI1+USART1; held-out test set 2 = GPIOA+CRC (now SPENT, see below). TIM excluded pending owner review. |
| 2026-10-27 | Recommendation accepted ("I approve") | DA-T029 fix-or-waiver (done: fixed); **freeze inspector development** after job 040; campaigns cheapest first; owner reviews PR #42 in parallel. |
| 2026-10-27 | Option (b) then "Drivers first" | Durable-AFO activation for an operation-24 campaign was authorized, but a no-reboot operation-24 cannot PASS by the factory's own rules (missing faults), so: run the three new drivers as normal local work orders first; formal campaign later with a reboot/mount window and an independent fault observer. |
| 2026-10-27 | Peripherals "RNG, LPTIM, WWDG"; merge main into feat/014 "Yes, merge now" | Done (see below). |
| 2026-10-27 | OD-2026-10-27-01 "ASIL B for all three" | Scopes SC-WWDG/SC-RNG/SC-LPTIM-2026-10-27 in `config/factory/safety-scope.yaml` (protected path; owner-decision commit `de54734`). |

Standing rules from the owner and earlier handovers:
- ALL Qwen tests run on remote **Omniverse2** (`ssh omniverse2@100.118.28.92`, key auth; RTX 6000 Ada 48 GB, shared,
  no sudo). All new local files, caches, logs and worktrees go on **loop10**
  (`/media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0`). Preserve `/home/jefferson/forge-c`.
- Never touch Feature 015's worktrees/services (`repos/forge-c-015*`, the AFO conductor on loop10) except reading
  pushed git objects or copying their git-ignored ST inputs; never touch x-verse_fabric, `/mnt/data/forge-c/lrtx-v2`
  or the shared Conductor/Fabro/gateway/Ollama services; never kill the other generic Ollama; no unrelated GPU work.
- Never read/copy private keys. AFO qualification grants are signed with
  `ssh-keygen -Y sign -U -f $FC014_OPS/qualification-owner/owner.pub -n forge-afo-authorization <msg>` (agent key).
  Review dispositions (`forge-review-disposition`), patch bundles (`forge-patch-bundle`) and **safety documents are
  owner acts: never sign them for the owner.**
- Tick tasks ONLY with `scripts/mark_task.py <tasks.md> <TASK> <evidence-name>` on a PASS record with exit 0. Never
  fake; record BLOCKED/NOT_RUN explicitly.
- One worktree per live run; kill processes by exact pid (never `pgrep -f` waiters).

## Locations and commit flow

```bash
B=/media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c
FC014_OPS=$B/operations/feature014                       # ops scripts, run outputs, replay records
FC014_REPO=$B/repos/forge-c-014-implementation           # owns the branch (checked out), push from here
W=$FC014_OPS/qualification-enrollment-followup           # work worktree, detached at the branch head
```

- Commit flow used all session: commit in `$W` (detached), `git -C $FC014_REPO cherry-pick -x <sha>`, push from
  `$FC014_REPO`, then `git -C $W checkout --detach <new head>`.
- Local tests: `source scripts/forge-env.sh` (it unsets PYTHONPATH), then `FORGE_DATA_ROOT=$B
  PYTHONPATH=$W/factory/python $B/venv/bin/python -m pytest ...`. Use a private `FORGE_STATE_DIR` for anything that
  writes state.
- Git-ignored ST/RM inputs (`examples/*/inputs/*.md`, `examples/0002-arm_55_rcc_st/hal_driver_guideline.md`): a new
  worktree lacks them. Copy from `$W` and verify each against the tracked `inputs-manifest.json` hashes (20 files at
  transfer). Without them many peripheral/brownfield tests skip or fail.
- Regression runners (operations dir): `run_full_inherited.py <worktree> <outdir>` (whole suite, one process and private
  state per file), `run_provider_regression.py` (core + release; run from a CLEAN worktree), `run_auxiliary_current.py`
  (stage dry-runs, history replay, systemd semantics, independent CRE). Run them on a clean dedicated worktree
  (`git -C $FC014_REPO worktree add --detach $B/repos/forge-c-014-regress-<rev> <rev>`), copy the ignored inputs in,
  and restore `docs/IMPLEMENTATION-STATUS-v0.4.md` + `evidence/v0.4/implementation-status.json` between runners
  (`test_t050_t051_docs_status` rewrites their timestamp line; content is otherwise identical).

## Status (30/58)

Ticked: DA-T001–003, 006, 008, 009, 011, 014, 015, 020, 022–024, 029, 030, 037–039, 043–045, 047, 048, 051, 053–058.

| Group | Tasks | What closes them |
|---|---|---|
| Known issues (owner "Known issues only") | T004, 005, 007, 010, 012, 013, 018, 019, 021, 031–036, 040, 041 | Live evidence only; KI-014-012..028. Re-check against campaign/product-run evidence. |
| Campaigns | T016, 017, 025, 026, 027, 028, 042, 046, 049, 050, 052 | Owner-authorized GPU windows; T025/T026 need separate authorization; T046/T049 need a reboot and authoritative-mount-loss fixture (no sudo on Omniverse2); T026/T052 need all fault classes and an independent fault observer (does not exist yet: `afo/operational_campaign.py` only injects crash/hang/clean-exit). |

Ledger rules (`evidence/014-durable-local-autonomy/verify_handoff.py` asserts them): 58 rows, every row keeps the ledger
`source_revision` (`e8e7fb6`; the evidence record carries its own `git_head`), ticked rows use a status in `PASSED`,
`implementation-status.csv` keeps **CRLF** line endings and must equal the JSON rows, `local_model_capability` stays
PARTIAL, product/learning/availability stay NOT_RUN, deployment NOT_ACTIVATED.

## What happened in the Claude continuation (2026-10-26/27)

- Stepwise SWE.1 inspector: learning set 1 49/49, set 2 63/63, set 3 14/14 at `9300475`; registered held-out test set 2
  (GPIOA, CRC) measured in 3 identical runs: 12/12 seeded defects flagged (11 on target), **2/2 clean baselines falsely
  rejected** (DA-T055 ticked on the protocol, rates published as KI-014-003, OPEN). Test set 2 then became learning
  set 4 (`41e12e0`); its rules are in `e0c020d` (indexed field families, requested/argument writes, colon budget rows,
  `<method>: <outcome>` criteria). GPU job 040 measured sets 1–4 on `e0c020d` — results: see "Last results" below.
  The owner froze inspector development after job 040; re-measure only on >= 4 new frozen held-out baselines.
  Known limitation: GPIOA S1-OMIT (one MODER value removed while other requirements cover the field) is undetectable
  without an encoding-completeness check (not built: false-rejection risk).
- DA-T029: the two inherited failures were harness-isolation artifacts (fixed test-only, `1e2fd46`); the `targeted`
  stage now refuses to freeze without its catalogue (`20650af`); regression at `20650af`: 215 files / 1,840 tests /
  0 failures, core 645, release 13/13, independent CRE REJECTED/PROTECTED_PATH_CHANGE retained (KI-014-010).
- Merge of main (`247562c`): 16 hunks in 10 AFO/policy files resolved (the merge commit message lists each). **Owner
  review item:** AFO recovery of delivered (brownfield) code now resumes validated phases (Feature 012) instead of
  main's fresh-work-order workaround. Runtime launch profiles follow main (`codex-claude` only).
- New ST LL drivers onboarded for local work orders (Feature 009/015 mechanism, ST code FROZEN): WWDG `74c3aa4`
  (12 functions), RNG `60fccfd` (17), LPTIM1 `4b71e6f` (21). Examples `0016c/0017c/0018c-st-cube-*`, inputs
  `0016/0017/0018-*-st` (RM0486 converted with `forge_factory.docs.pdf2md` from `$B/inputs/stm32n6/rm0486.pdf`, hash
  manifests tracked). All three Renode models were smoke-tested in real Renode 1.17 (IronPython 2.7). Both RM parsers
  read every in-scope register.
- Safety: OD-2026-10-27-01 scopes (ASIL B); drafts **SSA-STC-001 / TAA-STC-001 v0.1** under
  `config/factory/safety-documents/SC-ST-CAMPAIGN-2026-10-27/v0.1/` — UNSIGNED, UNREGISTERED. Basis hashes: WWDG
  `30ec84e9…`, RNG `fe6e9312…`, LPTIM `062a1ad9…` (computed as `workorder.prepare` does; the method reproduces the
  registered CRC basis). Owner open questions: RNG safety relevance (SSA Q-07), model per role (TAA Q-04).

## Last results before transfer

- GPU job 040 (`e0c020d`, done 08:13 UTC): learning sets 1–4 = 49/49, 63/63, 14/14, 13/14 (set 4: both clean
  baselines accepted, GPIOA S1-OMIT off target). Record: `evidence/014-durable-local-autonomy/stepwise-inspector-20261026/
  learning-round-e0c020d.json`. Inspector development is frozen (owner).
- GPU job 050 started 08:13 UTC: deploy OK (`9a88fbc`), inputs VERIFIED, peripheral tests 12 passed, campaign running.

## In flight at transfer: GPU job 050 (st3 driver runs)

- Omniverse2 GPU queue: runner `$Q/runs/gpuq-runner.sh` (flock), `Q=/mnt/data/forge-c/inspector-014-b309039`. Jobs are
  scripts in `$Q/gpuq/pending/` run in name order; results in `$Q/gpuq/done|failed/<job>.{log,status}`; status with
  `bash $Q/runs/gpuq-status.sh`; stop after the current job with `touch $Q/gpuq/STOP`.
- `050-st3-9a88fbc.sh`: deploys `9a88fbc` into `$Q/repo-b309039` (git bundle in `$Q/runs/`), copies the ignored inputs
  from `$Q/runs/st3-inputs` (hash-verified), runs the three peripheral test files, then
  `lrtx.campaign --campaign specs/014-durable-local-autonomy/st-drivers-campaign.yaml --out $Q/runs/st3` inside the
  stack (qwen3.6:35b-a3b, profile `local-rtx-v2-omniverse2-q36-noreason`, one attempt per driver, 12 h bound).
- Expected: packages BLOCKED at least on the unsigned SSA/TAA; local Qwen has never authored a full ST LL SWE.1–6
  work order, so earlier BLOCKED phases are likely and are the evidence. Record every attempt honestly.
- Collect: `$Q/runs/st3.log`, `$Q/runs/st3/` (campaign records), work orders under the stack state
  `$Q/lrtx/state/workorders/WO-*`. Publish a sanitized summary (no prompts/raw vendor text) under
  `evidence/014-durable-local-autonomy/st3-driver-runs/` and a `validation.md` entry; update the known issues.
- Inside the stack `FORGE_DATA_ROOT` is the isolated root `$Q/lrtx`; its `inputs` and `toolchains` are symlinks to
  `/mnt/data/forge-c` (that is how delivery finds the ST sources and Renode).

## Owner actions pending (ask once, then act)

1. Review and sign SSA-STC-001 / TAA-STC-001 (answer Q-07, Q-04). On the owner's instruction, register them under the
   three scopes (path, basis, sha256, approved_by/at, decision) in an "Owner decision" commit; then re-run the drivers
   for READY packages.
2. Review PR #42: the brownfield-resume behaviour change, the CRE REJECTED/PROTECTED_PATH_CHANGE (KI-014-010), and the
   unsigned drafts.
3. A reboot / authoritative-mount window on Omniverse2 (host admin) before the formal operation-24 campaign.
4. Feature 015 TIM review (frees TIM for a refreshed inspector held-out set); further frozen baselines (>= 4) before
   any new inspector measurement.

## Next implementation work (in order)

1. Collect and publish job 050 (above). Do not tick anything from it unless an acceptance test's exact evidence
   exists (likely none: these are pilot product runs).
2. Independent fault observer for `operation-24` (DA-T052 scope): records per FAULTS class (`afo/qualification.py`) with
   `independently_restored`, `restoration_seconds`, `unexpected_interventions`, `ledger_reset`, `duplicate_effects`,
   `false_ready`, bound to the manifest sha (see `afo/operational_campaign.report`). Then a signed operation-24
   manifest with the three drivers as product job bindings, and the campaign when the owner gives the window.
3. Keep `known-issues.{md,json}`, `validation.md`, the ledger and PR #42's body (`gh api --method PATCH
   repos/jnsagai/forge-c/pulls/42 --input <json>`; newest section on top) current after every milestone.

## Gotchas learned this session

- `verify_handoff.py` fails if a ledger row's `source_revision` changes or the CSV loses CRLF.
- `run_full_inherited.py` gives every file a private empty `FORGE_STATE_DIR`; tests that silently rely on the real data
  root fail only there (KI-014-005 pattern).
- A backgrounded `setsid sleep &` records the exiting `setsid` pid when setsid forks; use
  `subprocess.Popen(..., start_new_session=True)`.
- Renode Python peripherals are IronPython 2.7: no f-strings, `0x1_000`, `int.to_bytes`; platform files use
  `<PREFIX>_MODEL_PATH`; the host unit-test instance is `forge_host_<prefix lower>`.
- Feature 015 lesson: RM parsing exists twice on purpose (`inspection/regmap.py`, `assurance/hardware.py`); any RM
  parsing change must be made in both.
- Inspector work: replay recorded answers locally (`$FC014_OPS/q014-replay-all.py`, `q014-replay-items.py`) and run the
  truthful preflight (`q014-local-preflight.py`) on every learning baseline before spending GPU time.


## Codex follow-up — 2026-10-27 09:47 UTC

This section supplements the original transfer; owner decisions above still apply.
Latest source commit: **`c86d5773ff7238cb2195a2f1ec0484dbdfa24ec3`**. Follow-up
evidence/docs are later commits on the same branch; fetch it before continuing.

- Worktree: `$FC014_OPS/codex-resume-20261027`; original owner/main tree preserved.
- Exact clean regression tree: `$B/repos/forge-c-014-regress-c86d577`.
- New bounded capture/full-catalogue observer code: `afo/fault_observer.py`, new
  `afo/operational_facts.py`, strict operation manifest checks in qualification.py.
  Core 712 PASS / 11 SKIP / zero failures; release 13 PASS. Two skipped kernel
  permission checks separately PASS with private nonsecret sentinel. History and
  seven local isolated systemd cases PASS. Independent CRE still rejects protected
  paths. Source not deployed. Full inherited 1,840-test suite not repeated.
- Public evidence: `evidence/014-durable-local-autonomy/operational-observer-c86d577/`;
  task-style record `evidence/v0.4/runs/DA014-operational-observer-c86d577/latest.json`.
- Job 050 finished: 0/3 READY, all three BLOCKED at SWE.1; unsupported semantics and
  invalid model intents, not merely unsigned safety documents. KI-014-029 remains
  open. Public evidence `st3-driver-runs/`.
- Owner asked to use idle remote Qwen to advance work. GPU queue jobs 060/061 ran
  one external read-only engineering study, **three requests total** (original
  expenditure retained across context repartition). Two reference checks PASS;
  LPTIM invented a check ID and fails reference checking. Independent pinned
  SafeC rejects three selected WWDG/RNG suggestions; one isolated LPTIM read PASS
  does not establish driver correctness. Eight factual experiences/dispositions
  retained through existing LessonStore APIs, zero qualified lessons or measured
  benefit. No inspector tuning or native recovery qualification. Public evidence
  `st3-diagnosis-study/`; private scripts/results on both loop10 and Omniverse2
  `runs/qwen-st3-diagnosis-20261027`. Study's three-call budget is exhausted.
- Formal progress remains **30/58**, ledger source_revision/CRLF unchanged.

Next independent implementation: finish host-intervention audit integration and
independent READY/work/post-campaign verification. Current UNKNOWN fields must not
be replaced by handwritten success flags. Campaign reporting still requires that
independent evidence. Prepare authorized host fixtures after the admin window is
available; do not silently renew any grant or activate deployment. Full 24/72/168
campaigns, product success, learning benefit and 30-day SLO remain unproven.

For KI-014-029, independently reproduce unsupported access/RMW effects against the
frozen RM/domain and propose a scoped semantic-profile extension through its
external engineering boundary. Do not rerun a pilot simply with the rejected
suggestions or remove requirements. Keep inspector frozen and original failures.

## Codex follow-up — 2026-10-27 10:32 UTC

Latest source: **`08cc4326063074878b876c4aec36b9062fbde970`** (source increments
`8bd0108`, `ccd10f0`, `08cc432`). The final evidence/handover commit follows it.
Worktree remains `$FC014_OPS/codex-resume-20261027`; exact clean regression tree
`$B/repos/forge-c-014-regress-08cc432`. All local artifacts stay on loop10.

- Implemented `afo/operational_work.py`, reusing the existing product independent
  audit and externally captured native/mission/request facts. `fault_observer`
  provides executable `product` and `work` commands; CLI/configuration documented
  in `factory/qualification/014/README.md`. The plan freezes work/qualification-
  capture/queue-reader source hashes. No model, dispatch or service effect.
- `queue.ReadSnapshot` reuses Store reads in one bounded read-only SQLite snapshot;
  no migrations, missing-database creation or SQL writes. Actual concurrent writer
  tests, bounds, FIFO/path refusal and publication-deadline tests pass.
- Report consumes recomputed work/continuity evidence; handwritten success flags
  do not count. Unknown/contradictory clocks and probes stay UNKNOWN/unavailable.
  A new attempt or fresh observed native activity must establish real work during
  the campaign; recapturing a historical terminal job cannot inflate work counts.
  Native outcomes and product success remain separate, including zero-request work.
- Exact source: **235 affected PASS / 1 historical workspace SKIP / zero failures;
  release 13 PASS**. History replay and seven isolated local systemd cases PASS;
  independent CRE still **REJECTED / PROTECTED_PATH_CHANGE**. Static/handoff checks
  pass separately. No full core/1,840-test cohort claimed on this revision.
- Evidence: `evidence/014-durable-local-autonomy/operational-work-08cc432/`, with
  exact commands/JUnit/hashes; task-style record under
  `evidence/v0.4/runs/DA014-operational-work-08cc432/latest.json`. The earlier
  `operational-work-ccd10f0` record is historical; its timing-count limitation was
  fixed in `08cc432`. Formal count remains **30/58**, no ledger/CRLF rebaseline.
- No additional inference after the three-request remote study, no activation,
  inspector change or merge. Do not repeat that exhausted study as a new mission.

Next: implement/integrate a real independent host-intervention audit producer and
its source verification. It must establish coverage and derive interventions from
actual authoritative host events; do not replace current UNKNOWN with hand-entered
success/count flags. The product audit consumer now exists, but a genuine product
correctness oracle producer/evidence is still required for native qualification.
Prepare only authorized host reboot/mount-loss fixtures once prerequisites are
actually available. Keep the seventeen owner-accepted live omissions unscheduled,
all safety signing boundaries, CRE veto and inspector freeze. Native operational
campaigns, product success, learning benefit and 30-day SLO remain unproven.

## Codex follow-up — 2026-10-27 11:16 UTC

Source **`2928a9377c3ef96aab7cef7cf94355b96bdaa381`** adds `afo/host_audit.py`
and 38 new tests. It is a bounded **partial kernel-source adapter**, not a complete
host audit. The existing fault observer deliberately still leaves intervention
count UNKNOWN; do not turn kernel-only facts into a zero-intervention flag.

- Exact clean local tree `$B/repos/forge-c-014-regress-2928a93`: **273 affected
  PASS / 1 historical HAL-r154 workspace SKIP / zero failures; release 13 PASS**.
  Current CRE REJECTED/PROTECTED_PATH_CHANGE. Prior systemd/history and wider core
  cohorts remain distinct; not rerun for this unused-by-runtime leaf increment.
- Public evidence `evidence/014-durable-local-autonomy/host-audit-2928a93/`, with
  command/exit/JUnit/hashes and actual native prerequisite receipts. Task-style
  record `evidence/v0.4/runs/DA014-host-audit-2928a93/latest.json` is deterministic
  PASS only; native preflight is explicitly BLOCKED/exit 2.
- Native read-only preflight ran from an isolated, clean
  `/mnt/data/forge-c/inspector-014-b309039/host-audit-2928a93/repo`; output alongside
  it. It uses the existing LRTX venv, private cache/temp/state paths and no model.
  Actual host: auditctl/ausearch missing, auditd inactive, `sudo -n -l` exit 1.
  No installation, rule/counter/service mutation, deployment or grant change.
  Original source/services remain untouched. Raw audit/proctitle data was not
  collected or published; the kernel log is unavailable here.
- Parser/status/resource/privacy/compound-record tests pass. Root-protected regular
  source prefix bindings, exact approved-rule references and cumulative-loss/reset
  facts are implemented. Historical nonzero counters are not reset for green results.

Next source work: systemd-bus collection with actual visibility proof, authenticated
operator/control/actor correlation, segmented/rotation-safe continuous kernel
capture and full source-derived intervention verification. Current preflight keeps
these missing channels explicit; no kernel-only complete-host verdict exists.
Genuine independent product oracle production/evidence and the authorized host
reboot/mount-loss window remain required. Preserve the inspector freeze, seventeen
owner-accepted unscheduled live cases, finite/exhausted missions, protected CRE veto
and signing boundaries. Formal progress remains **30/58**, no task/ledger rebaseline.


## Codex follow-up — 2026-10-27 native bus source

Latest tested source **`fbd8bc89967b68ed4e99e4c63fe12784f135e62f`**. Worktree
`$FC014_OPS/codex-resume-20261027`; test commands ran clean there with private
state/events/temp, with no concurrent source edits. Evidence/docs commit follows.

- Added finite `bus_audit` source and `host_audit bus-preflight --bus user|system`;
  optional frozen `bus_scopes`/`bus_source_sha256` in host plans reuse capture.
  Native header-only profile retains exact replay bytes/hash, excludes bodies,
  and proves monitor activation plus two third-party query/reply boundaries.
  Manager/Unit calls are captured; actor, manager unit argument and effects remain
  UNKNOWN. No continuous coverage or global intervention count is inferred.
- **318 affected PASS, 1 historical HAL-r154 workspace SKIP, zero failures;
  release 13 PASS**. Includes actual isolated D-Bus traffic and malicious body
  text, clean exit/fallback/privacy/resource/source-freezing checks. Static
  spec/contracts/design/handoff/Ruff pass separately. CRE still
  REJECTED/PROTECTED_PATH_CHANGE. Broader cohorts are earlier revisions.
- Remote isolated clone `$Q/host-bus-fbd8bc8/repo` clean at source above, artifacts
  alongside: user-bus finite visibility **PASS exit 0**; system-bus monitor/fallback
  **BLOCKED exit 2**; kernel prerequisite **BLOCKED exit 2**. Public evidence
  `host-bus-fbd8bc8/`, private local copies `$FC014_OPS/host-bus-native-fbd8bc8/`.
  No new Qwen calls or changes to shared services, authority, counters or source
  deployment. GPU queue was empty at this turn's initial read.
- New KI-014-030 records host prerequisites and separate incomplete software.
  Formal **30/58** unchanged; do not tick from finite visibility alone.

Next: complete authenticated operator/control and actor correlation using the
existing CLI/dashboard/Intent/Store action/event paths, then continuous/segmented
rotation-safe source accounting and full observer verification. Header profiles
alone cannot identify manager-call unit arguments or prove effects; preserve those
unknowns until authoritative sources actually resolve them. Kernel audit/system
bus privilege and the approved host fault window remain unavailable, but do not
block independent software work. Product oracle production and elapsed native
campaigns remain required. Preserve all earlier owner freezes, finite/exhausted
missions, signing boundaries and the CRE veto; no automatic deployment or merge.
