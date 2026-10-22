# LRTX-T024: campaign c1, stopped by the owner after 13 of 30 cases

Status: **STOPPED_BY_OWNER (partial, 13/30 cases run, 0 READY)**. T024 is not ticked. There is no `latest.json`
evidence-run record, because the evidence_run wrapper was stopped before it could write one.

## What ran

- Campaign: `specs/010-local-rtx-optimization/campaign.yaml`, sha256 `deb7f43d...e6c` (`campaign.sha256`).
- Factory revision: `4f0a2e8` (clean), executed from the dedicated worktree `forge-c-run-t024`.
- Command: `stack exec -- python -m forge_factory.evidence_run --task LRTX-T024 --timeout 259200 -- python -m
  forge_factory.lrtx.campaign --campaign specs/010-local-rtx-optimization/campaign.yaml --out $S/campaign/c1`.
- Profile `local-rtx-v1`, all-local:
  - Author: qwen3-coder:30b (owner decision 2026-10-21, "ok, coder only").
  - Inspector: structured qwen3-coder:30b, still NOT_QUALIFIED (owner decision 2026-10-21, "local qwen as inspector").
- Started 2026-10-21T22:15Z. The last finished case ended 2026-10-22T06:39:59Z.
- Owner instruction 2026-10-22: "stop now all the runs". The campaign process, the run worker of case 14
  (RCC-LL-c104, mid SWE.1) and its author step were stopped by PID, and the models were unloaded (keep_alive 0). The
  partial case 14 is not counted.

## Result (`summary.json`, `cases.jsonl`, copied unchanged from `$S/campaign/c1`)

| Case set | Run | READY | Blocked phase | Reasons |
|---|---|---|---|---|
| IWDG-LL | 10/10 | 0 | SWE.1 (10) | 5 x rework budget exhausted (3 failed inspection cycles); 5 x stopped on the failed inspection INS-SWE.1-003 |
| RCC-LL | 3/10 | 0 | SWE.1 (3) | STUCK: the same deterministic rejection twice, stopped early (see below) |
| IWDG-HAL | 0/5 | - | - | not run |
| RCC-HAL | 0/5 | - | - | not run |

- READY_FOR_OFFLINE_REVIEW: **0 of 13**. The Wilson 95 % interval is [0.000, 0.228].
- The target (>= 27/30) can no longer be reached by this configuration in any meaningful sense, but the campaign is
  formally incomplete.
- Every case was packaged BLOCKED, with 49-56 gaps.
- Per-case verification PASS on all 13:
  - local providers only, ACP rejected;
  - network denial observed;
  - model digest matched;
  - roots isolated;
  - package sealed.
- Totals over the 13 cases:
  - 8.41 h wall time;
  - 640 model calls;
  - 3,190,255 prompt tokens and 321,498 output tokens;
  - GPU board energy 204.0 Wh (nvidia-smi, coverage 1.0; no wall-power meter).
- Per accepted work order: NO_ACCEPTED_WORK_ORDER.

## Triage (observed, not fixed during the run)

- **IWDG-LL:** the authored requirements passed the deterministic author gate. The local inspector then failed them
  repeatedly (INS-SWE.1-003 and preceding cycles) until the rework budget ran out. This matches T021, where the qwen
  inspector made 2/2 false rejections of Claude-passed holdouts and showed unstable verdicts. The inspector, not the
  deterministic gates, is the limiting component.
- **RCC-LL:** the author never produced a valid per-register task:
  - It wrote register-effect values as masks, not field values (for example `0x20` for the 1-bit field
    `RCC_AHB1ENR.ADC12EN`), and did not name the field in the statement.
  - The crosscutting task also produced an `EARS_UNKNOWN_SYMBOL`.
  - So `workproducts/SWE.1/register_effects.json` was never assembled. The validator findings name the exact fix,
    but qwen3-coder:30b repeated the same answer, and the STUCK rule stopped the case.
  - This is an author-model quality limit, not a factory defect.
- No new factory defect was identified. No CRE change was made during or after the campaign.

## Provenance

| File | sha256 |
|---|---|
| `cases.jsonl` | `512ca4331953f46b4f578c568b8a2782b1a6796664c1619df3042800b32e097f` |
| `summary.json` | `85b978c3a1507ffcff8dd02d792f70c9a9379995359fbb036e9d265574c5d11f` |
| `campaign.sha256` | `5c66e3c28c44cddaa5e0d2eb7c98c78717da040fda253cecbbec940c4b078e2d` |

Run workspaces and packages stay outside the repository under the profile root (`state/workorders/<case>-c1NN`,
`archives/<case>-c1NN`). The campaign is resumable from `cases.jsonl` if the owner decides to continue it.

Pilot operational evidence only. This is not a reliability proof, a qualification or a compliance claim.
