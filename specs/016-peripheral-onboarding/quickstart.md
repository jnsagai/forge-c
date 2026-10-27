# Quickstart: validating peripheral onboarding

**Prerequisites**
- loop10, a factory worktree of `feat/016-peripheral-onboarding`, and
  `unset FORGE_REPO_ROOT; . scripts/forge-env.sh`.
- The ST inputs are present under `$FORGE_DATA_ROOT/inputs/st/`.
- The RM0486 chapter conversions are present: git-ignored, with their manifests tracked.
- Arm GNU and LLVM toolchains, and Renode 1.17.

The package and approval formats are in [contracts/](contracts/), and the entities in
[data-model.md](data-model.md).

## 1. Deterministic derivation (US1, SC-004)

```bash
cd factory/python
python -m forge_factory.onboarding derive ../../examples/0012e-st-cube-usart-hal-ob WO-OB-USART --no-author
```

**Expected**
- `$FORGE_STATE_DIR/workorders/WO-OB-USART/onboarding/package.json` validates against
  `contracts/onboarding-package.schema.json`.
- The facts include `instance=USART1`, `base_address=0x52001000`, `time_base=HAL_GetTick`, an
  `undelivered_externals` entry `HAL_RCCEx_GetPeriphCLKFreq` feeding `USART_BRR`, and `host_instance=USART1`, plus
  `framework_modules` ⊇ {UART, DMA, RCC}. Each has sources.
- The assumption `ASM-CLOCK-USART1` is unconfirmed, and a blocking gap `ASSUMPTION_UNCONFIRMED` exists.
- The run takes under 10 minutes. The factory event log shows 0 model calls for the work order.
- Running again gives an identical `sha256`.

## 2. Regression oracle (US1, FR-020, SC-002)

```bash
python -m pytest -q tests/test_onboarding_oracle.py
```

**Expected**: every derivable field of the hand-written profiles and work orders (`0008c`, `0009-iwdg-st`,
`0010c`–`0014c`, `0014d`) is reproduced. Each difference is listed in
`config/factory/onboarding/oracle-exceptions.yaml` with its explanation. An unlisted difference fails.

## 3. Approval gate (US2)

1. Run `python -m forge_factory.onboarding summary WO-OB-USART`. It writes `onboarding/summary.md`, the owner
   review page.
2. The owner writes `approval.json` (see `contracts/onboarding-approval.example.json`) and signs it in their own
   terminal:
   `ssh-keygen -Y sign -f ~/.ssh/id_ed25519 -n forge-onboarding-approval onboarding/approval.json`.
3. Run `python -m forge_factory.onboarding verify WO-OB-USART`.

**Expected**
- `APPROVAL_OK` with the package hash.
- An approval whose hash is stale, or that leaves a conflict or assumption open, is refused with the reason.
- After `touch`-editing a delivered file and running derive again, the approval is void.
- With no verified approval, launching SWE.1 is refused: `ONBOARDING_NOT_APPROVED`.

## 4. Generated instructions (US3, SC-006)

```bash
python -m forge_factory.onboarding prompts WO-OB-USART --check
```

**Expected**: every SWE.1–SWE.6 node's built instruction passes the leftover check with 0 findings. No text comes
from `config/factory/peripherals/usart.yaml` `prompt*` keys. Each text's `from` is a template id or an authored item.

## 5. Model gate (US4)

```bash
python -m forge_factory.onboarding check-model usart     # existing model, re-gated
```

**Expected**: load PASS, reset values PASS (or unmodelled registers listed as limits), access types PASS, smoke PASS
on the delivered UART HAL image.

For SC-007, the held-out authoring of the CRC model runs through the onboarding Fabro run with the hand model hidden
from the author. The existing `0014c` target tests then pass on the authored model.

## 6. Acceptance (US5, SC-001/005)

For each of `0010e`–`0013e`:
1. AFO submit with request id `BENCH-<P>-ST-HAL-OB`.
2. The order reaches `WAITING_OWNER_APPROVAL`.
3. The owner signs.
4. The SWE run ends READY_FOR_OFFLINE_REVIEW, or BLOCKED with its gaps.

The record goes to `evidence/v0.4/benchmark/st-drivers-hal-ob/record.{json,md}`. A `git log` audit of
`config/factory/peripherals/` and the four examples shows no per-driver text added for these drivers.
