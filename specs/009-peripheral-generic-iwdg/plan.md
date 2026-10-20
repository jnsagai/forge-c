# Implementation Plan: Peripheral-generic factory (IWDG pilot)

**Branch**: `feat/009-peripheral-generic-iwdg` (stacked on `feat/008-brownfield-work-orders`) | **Date**: 2026-10-20 |
**Spec**: [spec.md](spec.md)

## Summary

The peripheral becomes a **profile**: `config/factory/peripherals/<id>.yaml`. It defines the RM register prefix, the
secure base address, the RM chapter and key sections, the file names, the API prefixes, the register-block name and
the simulator model.

The work order names its peripheral (`"peripheral": "iwdg"`; RCC when absent). `layer.py` answers every
peripheral-specific question from the profile, and the duplicated RCC literals across the factory are replaced by
calls to it.

On top of that:
- the RM field parser learns multi-bit fields;
- the register contract learns value writes;
- the simulator selects the model from the profile.

The RCC profile reproduces today's constants exactly, so RCC work orders produce the same workflows (FR-002, tested
by comparing generated graphs and scaffolds before and after).

## Technical Context

- **Language/Version**: Python 3.13 (factory); C11 drivers; Renode 1.17 Python peripherals.
- **Primary Dependencies**: existing only. The input is RM0486 chapter 59 (pages 2979–2994), converted by
  `forge_factory.docs.pdf2md`, plus the memory-map line for IWDG (p. ~176 region, `0x56004800`).
- **Testing**: pytest (parser, profile, contract, oracle, RCC equivalence); Fabro graph validation; one live IWDG LL
  run when the slices are complete.
- **Constraints**: RCC behaviour unchanged; no ISO text; deterministic gates.

## Constitution Check

| Principle | Compliance | Status |
|---|---|---|
| I. Safety and correctness | Hardware facts still come only from the converted RM chapter; the profile names sections, it does not restate register facts | PASS |
| II. Evidence | Each slice has tests; the RCC equivalence test proves no regression | PASS |
| III. External authority | No owner decision is changed; IWDG has no safety scope until the owner records one | PASS |
| IV/V. Skills and MCP | No new role or tool; skills are re-rendered only if their generated text changes | PASS |
| VI–IX | Unchanged | PASS |
| X. Open source | No new dependency | PASS |
| Governance | The profile files live under `config/factory/peripherals/`, which is not a protected path; checklists and release policies are not changed | PASS |

## Slices (in order)

| Slice | Content | Stories |
|---|---|---|
| A | Multi-bit RM field parsing (`inspection/regmap.py`, `assurance/hardware.py`) with tests on the IWDG chapter | US2 |
| B | Profile loader, RCC and IWDG profiles, `layer.py` identity API, work-order `peripheral` field, RCC equivalence test | US1 |
| C | Migrate the RCC literals to the identity API (regmap generation, scaffold harness, implementation check, swtrace, register-contract regexes, prompts' key sections) | US1 |
| D | Register contract `write` op (field value), oracle support | US2 |
| E | IWDG Renode model and profile-driven simulator selection | US3 |
| F | IWDG prompt profile, example 0009a, live run | US4 |

## Project Structure

```text
config/factory/peripherals/rcc.yaml, iwdg.yaml        # NEW profiles
factory/python/forge_factory/peripheral.py            # NEW profile loader (validated)
factory/python/forge_factory/layer.py                 # identity API driven by the profile
factory/python/forge_factory/inspection/regmap.py     # multi-bit fields; prefix/array from the profile
factory/python/forge_factory/assurance/hardware.py    # multi-bit fields
examples/0009-iwdg-st/inputs/                         # converted RM0486 ch.59 + memory-map excerpt + manifest
examples/0009a-iwdg-ll/workorder.json                 # IWDG LL work order
factory/sim/stm32n6/iwdg_model.py, stm32n6_iwdg.repl  # slice E
factory/python/tests/test_peripheral_*.py
```
