# Handoff to Codex: Feature 016, peripheral onboarding (2026-10-27)

From Claude Code (implementation engineer) to Codex. Read this, then `CLAUDE.md`, the constitution, `spec.md`,
`plan.md`, `research.md` (including the R1 amendment), `data-model.md` and `tasks.md` in this folder.

## 1. Where things are

| Item | Value |
|---|---|
| Feature branch | `feat/016-peripheral-onboarding` (pushed to origin), stacked on `feat/015-st-hal-benchmark` |
| Worktree | `/media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c/repos/forge-c-016-onboarding` |
| Test worktree | `repos/forge-c-016-test-64d6d61` (detached at 64d6d61): a clean full-suite run started there ~09:52Z, log `forge-c/logs/f016-64d6d61-full-tests.log`. Remove the worktree once read. |
| Main checkout | `~/forge-c` stays on `main`. Never check out feature branches there. |
| Deployed conductor | `repos/forge-c-afo-conductor-11482e3` (`feat/015-st-hal-benchmark` + SWE.3 fix; CRE pd-242d67ae9c43d821c156). **None of the feature 016 code is deployed.** |
| Owner | jnsagai (GitHub). The owner signs every authorization and approval in their own terminal. |

Environment for every command:

```bash
cd <worktree>; unset FORGE_REPO_ROOT; . scripts/forge-env.sh
export PATH=/media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c/toolchains/LLVM-19.1.7-Linux-X64/bin:$PATH
export PYTHONPATH=$PWD/factory/python   # needed for `python -m forge_factory...` from the repo root
```

The ST inputs are under `$FORGE_DATA_ROOT/inputs/st/`. A new worktree lacks the git-ignored example `.md` inputs:
copy them from `repos/forge-c-015` with `git ls-files --others --ignored --exclude-standard examples | grep .md$`,
then verify the 16 manifest hashes.

## 2. What feature 016 is

Onboarding a peripheral or driver delivery used to be manual work. Feature 016 makes it a factory stage, from the
owner inputs alone (datasheet, RM chapter and memory map, delivered code plus packages, scope):

1. **Deterministic derivation (no model call).** Facts are DERIVED, NOT_DERIVED or CONFLICT, with sources. Code:
   - `onboarding/identity.py`: instance, base address and memory-map page, prefix, RM register index, chapter, key
     sections, window, driver style, headers, API prefix;
   - `onboarding/behaviour.py`: file map and `hal_conf` modules (bounded build loop plus `gcc -M` include closure),
     time base, timeout constants, polling waits, undelivered externals (gc-sections link) and the registers they
     feed, which become test-environment assumptions, and instance comparisons with the host instance;
   - `onboarding/api.py`: prototypes, handle, `Init` fields, state reset constant.
2. **Generated texts.** `onboarding/texts.py` holds the ST classic HAL template set (`prompt`, `prompt_st_hal`,
   `replace`), filled from facts, the owner scope and the model's header description, with the origin of each value.
   `onboarding/leftovers.py` builds every SWE instruction with the real builder and flags foreign names.
3. **Model gate.** `onboarding/model_gate.py` checks RM reset values, read-only and rc_w0 access, and runs a
   delivered-code smoke image in Renode. An existing model is reused and re-gated; the package's `model` item caches
   the result.
4. **Owner approval.** `onboarding/approval.py` writes `summary.md` and `approval.template.json`. The owner signs
   with:

   ```
   ssh-keygen -Y sign -f ~/.ssh/id_ed25519 -n forge-onboarding-approval <state>/onboarding/<key>/onboarding/approval.json
   ```

   `verify` checks the signature against `config/factory/afo-allowed-signers`, plus the hash, completeness and
   invalidation.
5. **Wiring.**
   - `workorder.prepare` re-derives at every launch, then `admit` refuses without `APPROVAL_OK`. The manifest names
     `peripheral: onboarded:<key>` and carries an `onboarding` block.
   - `peripheral.load("onboarded:<key>")` returns the approved derived profile.
   - AFO `queue.submit` refuses an unapproved onboarding work order (`INTAKE_ONBOARDING_NOT_APPROVED`).
   - Baselines record `onboarding_sha256`.
   - Assurance states the model gate result instead of `SIMULATOR_MODEL_NOT_COMPARABLE`.
6. **Recovery planner rules (OB-T061, `afo/recovery.py frozen_issues`).** In a FROZEN delivery, plans are refused
   when they:
   - touch delivered code;
   - answer a gate demand for delivered code;
   - rework tests that reproduce escalated delivered-code defects.

CLI:

```
python -m forge_factory.onboarding derive <example> [key]
python -m forge_factory.onboarding {summary|verify|prompts} <key>
```

Packages live in `$FORGE_STATE_DIR/onboarding/<key>/onboarding/`. The key defaults to the example name.

## 3. Status (evidence-based)

**Done, tests pass.** The onboarding tests (about 90) and the AFO tests pass. Evidence records under
`evidence/v0.4/runs/OB-T0xx/` (latest.json PASS): OB-T001, T003, T005, T007, T011, T016, T018, T023, T026, T034,
T040, T061.

**OB-T020, the oracle:**
- The first evidence run FAILED. The model-gate smoke crashed on LL examples, which have no prototypes.
- The fix is in the worktree: `model_gate.smoke` skips the smoke step when there are no prototypes. It is
  **uncommitted**.
- An evidence re-run was started; its result goes to
  `/tmp/claude-1000/-home-jefferson-forge-c/1c0d4aec-d691-4be5-9acf-29be01f58966/scratchpad/ob-t020.txt` and
  `evidence/v0.4/runs/OB-T020/`.

**Uncommitted in the worktree:**
- that fix;
- `docs/adr/ADR-0016-peripheral-onboarding-stage.md`;
- this handoff;
- the new evidence files.

Commit them after checking the OB-T020 result.

Tick tasks with `scripts/mark_task.py specs/016-peripheral-onboarding/tasks.md <OB-Tnnn>
<evidence-name>`, only for tasks whose evidence PASSED. Map:

| Evidence | Tasks |
|---|---|
| OB-T001 | T001, T017 |
| OB-T003 | T003 |
| OB-T005 | T004, T005 |
| OB-T007 | T006, T007 |
| OB-T011 | T008, T009, T010, T011 |
| OB-T016 | T012, T013, T014, T015, T016 |
| OB-T018 | T018 |
| OB-T020 | T002, T019, T020 (after it passes) |
| OB-T023 | T021, T022, T023, T027, T028, T029, T030 |
| OB-T026 | T024, T025, T026 |
| OB-T034 | T031, T032, T033, T034, T044 |
| OB-T040 | T038, T039, T040, T042 |
| OB-T061 | T061 |

**Full suite:**
- At HEAD 64d6d61 a clean run was in progress (see the test worktree above).
- An earlier contaminated run showed the 3 known baseline failures (`test_cre_d7_e2e` latest_local_qwen,
  `test_kpi_003` t012 and t020) plus 3 now-fixed ones.
- The CAPA-048 optimisation test was adapted: its undefined reference now sits in an executed HAL function, because
  the F015-T065 `--gc-sections` would otherwise drop it. The test intent is unchanged.
- Confirm the result shows only the 3 baseline failures. Note it does not include the uncommitted LL smoke fix.

**Derived acceptance packages:**
- All four (`examples/0010e`–`0013e`, owner inputs only) derive READY_FOR_OWNER and pass the leftover check with 0
  findings.
- GPIO, SPI and TIM have no gaps.
- USART has one blocking gap: `ASM-HAL-RCCEX-GETPERIPHCLKFREQ`, the kernel clock value the owner must confirm.
- These were derived in a scratch state; not yet in the real state dir.

**Model fixes found by the gate:** GPIO `SECCFGR`/`PRIVCFGR` reset `0x0000FFFF`; SPI `TXCRC`/`RXCRC` read-only.

**CRC HAL baseline (hand-onboarded, feature 015):**
- `BENCH-CRC-ST-HAL-R2`, order afo-071ffed673bf5df5, ended BLOCKED at SWE.4. Its BLOCKED gap packages are sealed
  (a1 archive 72e9b89c…, a2 0aa4c0e0…).
- Cause: real defects in ST's frozen CRC HAL, recorded as escalated CODE defects:
  - DEF-003: `HAL_CRCEx_Polynomial_Set` never tests bit 31 (`while ((msb-- > 0U) && …)`);
  - DEF-002: the reversal setters' masks omit RTYPE;
  - DEF-004: DeInit leaves a BUSY handle.
- These need the owner's disposition. The earlier R1 order (afo-a52297345f08e79d) ended BLOCKED on the SWE.3
  LL-header gate defect, since fixed.

**Full-suite result (clean worktree at 64d6d61, log `forge-c/logs/f016-64d6d61-full-tests.log`):** 1395 passed,
27 skipped, 7 failed. Of the 7, three are the known baseline failures (`test_cre_d7_e2e` latest_local_qwen,
`test_kpi_003` t012, t020). The other four are `test_onboarding_oracle[0008c, 0010c, 0012c, 0014c]`: the LL smoke
crash, fixed in f1dba7d, where OB-T020's oracle evidence PASSES. Re-run the full suite on the current HEAD before the
CRE gate. The test worktree has been removed.

**Ticked:** 40 of 64 tasks, through `mark_task` with evidence (cfd2548). The 24 open tasks are listed in §4.

## 4. Next steps, in order

1. Check the OB-T020 re-run and the clean full suite. Commit the fix, ADR, handoff and evidence; tick tasks per the
   map; push.
2. **CRE gate** on the 016 HEAD against the deployed revision:

   ```
   cd factory/python && python -m forge_factory.reliability.promotion <016 HEAD> 11482e3 --kind CHANGE --repo ../..
   ```

   Copy `state/reliability/decisions/<pd>.json` to `evidence/cre/decisions/` and commit it as
   "CRE oracle: decision …". Fix anything it flags first.
3. **Deploy** only after CRE ELIGIBLE and when no order is RUNNING:
   - new worktree `repos/forge-c-afo-conductor-<H>`;
   - copy and verify the ignored inputs;
   - back up the units to `logs/unit-backup-…`;
   - `python -m forge_factory.afo.services install`;
   - `systemctl --user disable forge-llm-gateway-cloud`;
   - `systemctl --user restart forge-conductor`;
   - verify the conductor runs from the new worktree.
4. **Acceptance packages** (OB-T045–T057), with the real state:
   - `derive` and `summary` for each of `0010e`–`0013e`;
   - add AFO launch manifests `config/factory/benchmark/afo/<p>-st-hal-ob.json` and queue items. Check that the
     owner's AUTH-AFO-PILOT-20261027 covers the driver classes (`STM32N6_<P>_HAL_ST`). If not, prepare an UNSIGNED
     authorization for the owner; **never sign it**;
   - hand the owner the four `summary.md` paths and the signing command. USART needs their kernel-clock value;
   - **wait for the owner's signatures** (OB-T047/T050/T053/T056);
   - `verify`, then commit the signed copies to `evidence/easa/owner-decisions/` in owner-decision commits;
   - submit `BENCH-<P>-ST-HAL-OB` one at a time (`max_concurrent_runs` = 1). Retries get new request ids `-R<n>`.
5. **Remaining tasks:**
   - OB-T035–T037: text-author roles. Not needed for ST HAL, because all texts are generated. Leave them open with
     a note, or close them by owner decision. Do not tick without evidence;
   - OB-T041/T043: model author role and held-out CRC authoring (SC-007);
   - OB-T058–T060: the record, the SC-001 audit, owner review;
   - OB-T062: write the local-model NOT_RUN record;
   - OB-T064: the PR.
6. **PR to main:** no merge without the owner's explicit acceptance; merge commits only.

## 5. Standing rules (binding)

- **Never sign for the owner**: no AFO authorization, no onboarding approval, no safety document. Owner-only files
  (`config/factory/safety-scope.yaml`, `verification-dispositions.yaml`, the safety-document registers) change only
  in owner-decision commits.
- **Never start `forge-llm-gateway-cloud` (DeepSeek)**; keep it disabled on every deploy. No DeepSeek or local-model
  workloads. Don't touch `x-verse_fabric`, omniverse2 or feature 014 work.
- **CRE gate before deploying any factory commit**, with the decision frozen in an oracle commit.
- **One worktree per live run**, never re-checked-out. Worktrees go under `forge-c/repos/`.
- **Never mark READY manually.** Tick tasks only through `mark_task.py` with evidence.
- **Retries get new request ids.** Don't silently renew authority.
- Don't wait with `pgrep -f` loops; wait on a job notification or a marker file.
- Pytest prints no summary line here; count the progress characters, or grep `^FAILED|^ERROR`.
- `gh pr edit` fails because of the Projects-classic deprecation. Use
  `gh api -X PATCH repos/jnsagai/forge-c/pulls/<n> -F body=@file`.
- **Pending owner decision, not in this feature:** the HAL safety documents v1.1 (SSA-STB-001/TAA-STB-001 extended
  for the ST HAL; owner chose "Extend + v1.1 docs"). Do not add HAL examples to the safety scopes before the owner
  signs v1.1.

## 6. Known limits and open points

- Only the ST classic HAL (HAL_STANDALONE) has a text template set. LL and factory-HAL work orders cannot use the
  package-driven path yet.
- No AI-authored model exists yet (US4 authoring). Peripherals without a model get `PROFILE_MODEL_MISSING`.
- On the host, an assumption confirmed in the approval becomes `hal.clock_stub.hz`. The model smoke step uses a
  placeholder value 1 before approval.
- The CRC HAL defects DEF-002/003/004 are owner findings in ST's code. The feature 015 HAL record still has to be
  written with both BLOCKED attempts.
