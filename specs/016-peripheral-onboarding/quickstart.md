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
python -m forge_factory.onboarding derive ../../examples/0012e-st-cube-usart-hal-ob
```

**Expected**
- `$FORGE_STATE_DIR/onboarding/0012e-st-cube-usart-hal-ob/onboarding/package.json` validates against
  `contracts/onboarding-package.schema.json`.
- The facts include `instance=USART1`, `base_address=0x52001000`, `time_base=HAL_GetTick`, an
  `undelivered_externals` entry `HAL_RCCEx_GetPeriphCLKFreq` feeding `USART_BRR`, and `host_instance=USART1`, plus
  `framework_modules` includes UART and RCC. Modules come from the required header closure; an unused DMA module
  is not added. Each fact has sources.
- Before owner approval, `ASM-HAL-RCCEX-GETPERIPHCLKFREQ` is unconfirmed and a blocking
  `ASSUMPTION_UNCONFIRMED` gap exists. The acceptance owner subsequently confirmed 64,000,000 Hz in OA-2026-10-27-03.
- The run takes under 10 minutes. The factory event log shows 0 model calls for the work order.
- Running again gives an identical `sha256`.

## 2. Regression oracle (US1, FR-020, SC-002)

```bash
python -m pytest -q tests/test_onboarding_oracle.py
```

**Expected**: every derivable field of the hand-written profiles and work orders (`0008c`, `0010c`–`0014c`,
`0010d`–`0014d`) is reproduced. Each difference is listed in
`config/factory/onboarding/oracle-exceptions.yaml` with its explanation. An unlisted difference fails.

## 3. Approval gate (US2)

1. Run `python -m forge_factory.onboarding summary 0012e-st-cube-usart-hal-ob`. It writes `onboarding/summary.md`, the owner
   review page.
2. The owner writes `approval.json` (see `contracts/onboarding-approval.example.json`) and signs it in their own
   terminal:
   `ssh-keygen -Y sign -f ~/.ssh/id_ed25519 -n forge-onboarding-approval onboarding/approval.json`.
3. Run `python -m forge_factory.onboarding verify 0012e-st-cube-usart-hal-ob`.

**Expected**
- `APPROVAL_OK` with the package hash.
- An approval whose hash is stale, or that leaves a conflict or assumption open, is refused with the reason.
- After `touch`-editing a delivered file and running derive again, the approval is void.
- With no verified approval, launching SWE.1 is refused: `ONBOARDING_NOT_APPROVED`.

## 4. Generated instructions (US3, SC-006)

```bash
python -m forge_factory.onboarding prompts 0012e-st-cube-usart-hal-ob --check
```

**Expected**: every SWE.1–SWE.6 node's built instruction passes the leftover check with 0 findings. No text comes
from `config/factory/peripherals/usart.yaml` `prompt*` keys. Each text's `from` is a template id or an authored item.

## 5. Model gate (US4)

```bash
python - <<'PY'
import json
from forge_factory.onboarding import onboarding_dir
from forge_factory.onboarding.approval import verify
from forge_factory.onboarding.facts import read_package
from forge_factory.onboarding.model_gate import check

key = "0012e-st-cube-usart-hal-ob"
root = onboarding_dir(key)
decision = verify(root)
assert decision["code"] == "APPROVAL_OK", decision["code"]
package = read_package(root)
confirmed = {item["id"]: item["value"] for item in decision["approval"]["assumption_confirmations"]}
values = {item["symbol"]: confirmed[item["id"]] for item in package["assumptions"]}
result = check(key, confirmed=values, pkg=package)
print(json.dumps(result, indent=2))
assert result["verdict"] == "PASS"
PY
```

**Expected**: load PASS, reset values PASS (or unmodelled registers listed as limits), access types PASS, smoke PASS
on the delivered UART HAL image.

The same gate is available as `python -m forge_factory.onboarding check-model <package-key>`.

When no factory model exists, CLI `derive` uses the separate Codex author → deterministic gate → Claude inspector
run, with at most three attempts. Use `--no-author` to derive facts without launching that run. Programmatic
`derive` and SWE launch re-derivation are model-free by default and can reuse a previously accepted authored bundle.
The two model roles are opt-in overlays; the existing 20-role registry and SWE graph remain intact. Authored models
execute in an offline namespace containing the Renode distribution and scratch files, with a restricted source
language, bounded output and a timeout. Inspectors accept an exact model hash. Accepted model/platform bundles are
content-addressed and their bytes are checked again before target execution.

For SC-007, the operator command (from the repository root) is:

```bash
python -m forge_factory.onboarding derive examples/0014c-st-cube-crc --hide-model crc
```

The hidden-model option is test-only and becomes
part of the hashed package profile. A failed authoring case remains a named gap; it does not fall back to the hand
model. The held-out model run is **NOT_RUN** in `evidence/v0.4/runs/OB-T043/latest.json` because the owner reported
Claude quota exhaustion. The deterministic tests do not establish SC-007 or an independent inspection PASS.

## 6. Acceptance (US5, SC-001/005)

For each of `0010e`–`0013e`:
1. Derive the package and its summary (`derive`, `summary`).
2. The owner signs the approval.
3. AFO submit with request id `BENCH-<P>-ST-HAL-OB` (intake refuses it without a verified approval).
4. The SWE run ends READY_FOR_OFFLINE_REVIEW, or BLOCKED with its gaps.

The record goes to `evidence/v0.4/benchmark/st-drivers-hal-ob/record.{json,md}`. A `git log` audit of
`config/factory/peripherals/` and the four examples is preserved under `OB-SC001-HISTORY`. Its strict literal
result is FAIL because an unused legacy GPIO model-description string changed; the active-input audit
`OB-SC001-PREPARATION` passes. Owner adjudication remains pending, and the historical failure is not relabeled.
