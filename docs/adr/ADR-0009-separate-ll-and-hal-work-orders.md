# ADR-0009: Separate LL and HAL work orders (LL first, HAL on the verified LL)

- **Status:** Accepted (2026-10-16, owner decision: "separate HAL and LL, do first LL and after HAL in different runs
  for simplification") · **Scope:** work-order spec, workflow builder, node prompts, SWE.3/SWE.4 scaffolds and
  deterministic checks, coverage tool · **Builds on:** ADR-0005 (small node procedures), ADR-0008 (loopbacks)

## Context
WO-0002 built the RCC LL header and the HAL on top of it in one run. That meant one requirement set, one
architecture and one test campaign for both layers. The SWE.3 chain was regmap → LL author → HAL author → fix
author. Most rework loops (r61–r76) were HAL issues: timeouts, parameter checks, status codes. Those failures sat
on top of LL code that had not yet been tested on its own.

## Decision
A work order declares `"layer"` in `workorder.json`. The value is copied into `.forge-run/manifest.json`, which is
where every tool reads it (`forge_factory/layer.py`):

| | `LL` (example `0002a-arm_55_rcc_ll`) | `HAL` (example `0002b-arm_55_rcc_hal`) | `LL+HAL` (legacy, no field) |
|---|---|---|---|
| SWE.1 | LL requirements ("RCC LL driver"): bit set/clear, flag queries, bit preservation, no waiting | HAL requirements (unchanged texts) | unchanged |
| SWE.2 | LL interfaces only (`LL_RCC_<Name>_Enable/Disable/IsReady/IsEnabled/ForceReset/ReleaseReset`), caller-bounded polling | HAL on the PROVIDED LL | unchanged |
| SWE.3 chain | regmap → LL author → fix author → author | HAL author → fix author → author (no regmap: the provided header is frozen) | regmap → LL → HAL → fix → author |
| Compile unit | generated `software/src/stm32n6xx_ll_rcc.c` (include only) | HAL sources | HAL sources |
| SWE.3 implementation check | every allocated `LL_RCC_` function is a `static inline` definition | as before **plus** the provided LL header's sha256 is unchanged | as before |
| SWE.4–6 tests | call the LL API; coverage includes the LL header | call the HAL API | unchanged |

**Provided LL.** A HAL work order needs `--provided-from <LL work order>`. That LL work order must be layer `LL`
and must have a gate PASS for all six phases. Its header is copied into the HAL workspace and set to read-only
(0444). Its provenance (source work order, package reference, sha256) is recorded under `provided` in the manifest.
A HAL work order without a verified LL stops at prepare with `HAL_LAYER_NEEDS_PROVIDED_LL`,
`PROVIDED_LL_NOT_VERIFIED` or `PROVIDED_LL_NOT_FROM_LL_WORK_ORDER`.

**Unchanged.** Checklists stay one set. The SWE2-08 and SWE3-09 criterion texts now name the layer-specific
expectation, and their deterministic checks read the layer. Budgets are the owner's values: an LL work order keeps
the same flash and stack upper bounds and adds that static RAM is 0, because the LL keeps no state. The combined
`0002-arm_55_rcc_st` example and all earlier evidence are untouched.

## Consequences
- Each run is smaller: fewer requirements, one API layer and one SWE.3 author node. An LL failure can no longer hide
  behind a HAL failure, and HAL rework cannot change the verified LL.
- The HAL run depends on an LL run that fully passed. Until one exists, HAL work orders are refused, not degraded.
- Header-only LL code has no footprint of its own. Size and stack are measured on the compile unit and accounted at
  call sites; the SWE.3 detailed design says so.

## Evidence
`factory/python/tests/test_layer_split.py` covers:
- graph per layer;
- LL prompts free of HAL work;
- HAL prompts carrying the provided-LL rule;
- scaffold and guideline layout;
- LL implementation check;
- provided-LL tamper detection;
- prepare refusals;
- real compile (host and target), unit test and coverage, and the Renode target on an LL-only workspace.
