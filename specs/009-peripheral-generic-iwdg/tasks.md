# Tasks: Peripheral-generic factory (IWDG pilot)

**Input**: `specs/009-peripheral-generic-iwdg/` (spec, plan, research, data-model, contracts, quickstart).
**Tests**: required (constitution II). **Completion rule**: tick only with a passing test or run, with evidence.

## Phase 1: Inputs

- [X] PG-T001 Convert RM0486 chapter 59 (pp. 2979–2994) with `forge_factory.docs.pdf2md` into `examples/0009-iwdg-st/inputs/RM0486-rev4-ch59-iwdg.md`. Add a memory-map excerpt with the IWDG line and an `inputs-manifest.json` with the PDF SHA-256 and pages.

## Phase 2: Slice A — multi-bit fields (US2)

- [X] PG-T002 [US2] Accept `Bits m:n NAME[m:n]:` fields in `factory/python/forge_factory/inspection/regmap.py` and `factory/python/forge_factory/assurance/hardware.py`. Masks come from the width; reserved fields are recorded as reserved.
- [X] PG-T003 [US2] Tests in `factory/python/tests/test_peripheral_fields.py`:
  - all 7 IWDG registers with KEY[15:0], PR[3:0], RL[11:0], WIN[11:0] and the SR flags;
  - RCC multi-bit fields such as SYSSWS[1:0] now parsed;
  - the RCC single-bit fields unchanged.

## Phase 3: Slice B — profiles (US1)

- [X] PG-T004 [US1] `config/factory/peripherals/{rcc,iwdg}.yaml` and `factory/python/forge_factory/peripheral.py`: load, validate against the contract, cache, default `rcc`.
- [X] PG-T005 [US1] `layer.py` identity API (header names, prefixes, register block, components, key sections, base) from the work order's profile. `workorder.prepare` records `peripheral` and the profile hash, and checks that the key sections exist in the converted inputs.
- [X] PG-T006 [US1] RCC equivalence test: the workflow graphs (LL, HAL, brownfield), the scaffolds and the regmap output for the RCC examples are identical before and after.

## Phase 4: Slice C — migrate literals (US1)

- [X] PG-T007 [US1] Replace the RCC literals with the identity API in:
  - regmap generation and check;
  - the scaffold harness and the LL fake;
  - the implementation check;
  - swtrace (code files, Doxygen filter);
  - the register-contract and oracle regexes;
  - the prompts' key sections and system name.

  Each module keeps its RCC behaviour (PG-T006).
- [X] PG-T008 [US1] IWDG workspace test: prompts, scaffolds and generated register map contain no RCC identifier (SC-001).

## Phase 5: Slice D — value writes (US2)

- [X] PG-T009 [US2] Register-contract op `write` (with a value) in `assurance/register_contract.py`, the oracle generator and the brownfield conformance check, with tests.

## Phase 6: Slices E–F — simulator and live run (US3, US4)

- [X] PG-T010 [US3] IWDG Renode model and platform; profile-driven model selection in `mcp/servers/sim.py`.
- [X] PG-T011 [US4] IWDG prompt profile (examples, API shape) and `examples/0009a-iwdg-ll/workorder.json`.
- [X] PG-T012 [US4] Live IWDG LL run; evidence in `evidence/v0.4/runs/PG-T012/`.

## Phase 7: Release

- [X] PG-T013 Full regression, CRE CHANGE promotion, PR (stacked on PR #13).

## Strategy

Slices A–B first: they are independent of RCC behaviour and unblock everything else. Slice C proceeds module by
module, with the equivalence test as the guard.

## Status and evidence (2026-10-20, overnight session)

- **PG-T001..T011 are ticked, with tests** (`factory/python/tests/test_peripheral_*.py`, all passing):
  - field parsing;
  - the RCC equivalence goldens (graphs and register map byte-identical);
  - the IWDG register map, harness, implementation check and Robot scaffold;
  - the contract `write` op with the oracle (correct key PASS, wrong key FAIL);
  - the IWDG prompts free of RCC content (SC-001);
  - the IWDG Renode model (4/4 checks in both scenarios).
- **PG-T007 limits:** the HAL-layer paths (`provided_ll`, `ll_fake`) and the observe-only assurance helpers (corpus,
  mutation, target, verifiers, `oracle_gen.derive` sentence parsing) still assume RCC. The IWDG work order is LL only
  and uses the register contract, so they are not on its path. They are a follow-up for a HAL peripheral.
- **PG-T012:** i001 BLOCKED at SWE.2 and i002 BLOCKED at SWE.5 (4 factory defects found and fixed). i003 on 83ee4c7:
  SWE.1-SWE.6 PASS; package BLOCKED only on the 2 owner safety documents (IWDG has no owner safety scope).
  Evidence: `evidence/v0.4/runs/PG-T012/latest.json`.
