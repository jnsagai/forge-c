# Implementation Plan: USART benchmark pilot - SWE.1 the benchmark way

**Branch**: `feat/020-usart-benchmark-pilot` | **Date**: 2026-11-12 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/020-usart-benchmark-pilot/spec.md`

## Summary

Make SWE.1 work the way the benchmark does - a governance package first, then functional/API-level requirements
with a full attribute template, origin groups and trace/derive links - as a **module-agnostic** Forge-C mechanism
selected per work order, and use it first on one brownfield module: ST's frozen HAL_UART + LL_USART. Technical
approach (research.md): a deterministic governance inventory in `prepare`, a model governance step and coverage check
as the first SWE.1 node, a new structured functional SWE.1 author with deterministic validators, the feature 018
two-phase inspection with level-aware packets, attribute-aware assembly and ReqIF, a generic pilot-lineage option in
the derived campaign, and a metrics-only benchmark comparison plus decision log and way-of-working proposal. Existing
(register-level) orders stay byte-identical.

## Technical Context

**Language/Version**: Python 3.13 (factory venv on Omniverse2), as the rest of `factory/python`

**Primary Dependencies**: existing factory stack only - Fabro 0.362 workflow graph, the structured runner
(`lrtx/runner.py`, `lrtx/structured.py`, `lrtx/visit.py`), jsonschema, PyYAML; no new third-party dependency

**Storage**: files in the work-order workspace (`workproducts/SWE.1/...`, `.forge-run/...`), the line inputs cache
for private inputs, a private directory outside the repository for benchmark metrics

**Testing**: pytest (`factory/python/tests`), the existing frozen graph fingerprints and golden fixtures, the CRE
reproducer/gate flow for the deploy

**Target Platform**: Omniverse2 owner lane (Linux, local models via the owner-lane gateway)

**Project Type**: factory feature inside the existing single Python project

**Performance Goals**: the pilot SWE.1 completes within the normal SWE.1 time and rework budgets of the owner lane;
no request beyond the gateway's input bound (bounded packets per use case / group, as today)

**Constraints**: frozen delivered code; pinned adapters, signed controls, production Line Conductor untouched; owner
profile and checklist bases hash-pinned (not edited); register-level orders byte-identical; no benchmark content in the
repository; CRE gate before deploy; one GPU run at a time; ladder SWE.3 held

**Scale/Scope**: one module (HAL_UART with about 30 in-scope public functions incl. callbacks, LL_USART in-scope subset
of the 249 inline functions), expected 50-90 requirements; the mechanism must also prepare a second, synthetic module
in tests with zero code change

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design (below).*

| Principle | Check | Status |
|---|---|---|
| I. Safety and correctness precede optimization; HW semantics only from baselined manuals | Requirements trace only to the input register (RM0486, datasheet, guideline, CMSIS header); the delivered code is never a source (FR-003, R4) | PASS |
| II. Evidence driven | Every check deterministic and recorded in the gate log; comparison reproducible from files; tests fail-before/pass-after; CRE gate | PASS |
| III. Unattended, external release authority | No human gate inside the run (owner revoked sign-offs); blocked states are explicit (governance coverage refusal, later-phase refusal) | PASS |
| IV. Versioned SKILLs, author ≠ inspector | The functional author and governance step run under the existing swe1-author role/skill (skill text updated through the registry generator); the inspector stays the independent swe1-inspector | PASS (skill update is a task) |
| V. MCP for production AI tool calls | Structured runner calls only, as the existing SWE.1 author; no new agent tool surface | PASS |
| VI. Model-free supervision | Unchanged | PASS |
| VII. Evidence-based lessons | No lessons changed | PASS |
| VIII. Privacy-preserving traces | Benchmark content never stored; private inputs stay in the cache; no prompts stored | PASS |
| IX. Minimal model cost | Bounded per-use-case packets; budgets enforced as today | PASS |
| X. Open-source-first | No new dependency | PASS |
| Governance: changes to release gates/assurance criteria need authorization | New deterministic SWE.1 checks apply only to functional-level orders, authorised by the owner's 2026-11-12 decisions; register-level gates and the IQ/SQ criteria file unchanged | PASS (owner-authorised) |

Post-design re-check: no violations introduced by the data model or contracts; Complexity Tracking empty.

## Project Structure

### Documentation (this feature)

```text
specs/020-usart-benchmark-pilot/
├── plan.md                         # this file
├── research.md                     # Phase 0
├── data-model.md                   # Phase 1
├── quickstart.md                   # Phase 1
├── contracts/
│   ├── workorder-swe1-block.schema.json
│   ├── governance-inventory.schema.json
│   ├── governance-package.schema.json
│   ├── functional-requirement.schema.json
│   └── benchmark-metrics.schema.json
├── decision-log.md                 # FR-028, appended during the pilot
├── way-of-working-proposal.md      # FR-029, generated at the end
└── tasks.md                        # Phase 2 (/speckit-tasks)
```

### Source Code (repository root)

```text
factory/python/forge_factory/
├── governance/                     # NEW, module-agnostic
│   ├── inventory.py                #   deterministic: input register, delivered API inventory, scope classification
│   ├── package.py                  #   model step packet/validation + deterministic coverage check, rendering
│   └── level.py                    #   reads the SWE.1 level setting from the manifest (single source)
├── lrtx/
│   ├── swe1_functional.py          # NEW structured functional SWE.1 author (tasks, schema, validators, assembly)
│   ├── swe1_quality.py             # level-aware packets/schema/validators (register level byte-identical)
│   └── runner.py                   # selects the functional author for functional orders
├── assurance/
│   └── swe1_functional_checks.py   # NEW deterministic gate checks (template, groups, links, level rule, no code source)
├── inspection/
│   ├── gate.py                     # SWE.1 step_author: functional checks for functional orders
│   └── reqif_export.py             # attributes + traces-to/derived-from relations for functional orders
├── workflow/builder.py             # governance node + coverage check before swe1 author (functional orders only)
├── workorder.py                    # swe1 block → manifest swe1_level (only when set); inventory in prepare;
│                                   #   no register_contract stamp; SWE.2+ refusal for functional orders
├── afo/owner_supervised_development.py  # lineage uart-module + generic PILOTS option in derived_campaign
└── benchmark/
    ├── compare.py                  # NEW comparison report (metrics only)
    └── proposal.py                 # NEW way-of-working proposal from decision log + metrics

examples/0012u-st-cube-uart-module/workorder.json   # NEW: one module, LL+HAL FROZEN, scope rule, swe1 block, inputs
examples/0012-usart-st/inputs/inputs-manifest.json  # + interrupt-mapping extract entry (body in the inputs cache)
config/factory/swe1-functional-template.yaml        # NEW: template version, groups, attribute enums, level rule terms
factory/python/tests/test_f020_*.py                 # NEW tests (one file per area)
```

**Structure Decision**: one new package `governance/` (module-agnostic, reusable by every future module) and one new
author module next to the existing `swe1.py`; every other change is a guarded branch keyed by the manifest's
`swe1_level`, so register-level code paths stay untouched.

## Phasing (delivery order)

1. **Foundation**: SWE.1 level setting (work order → manifest, only when set), template config, `governance.level`,
   identity tests proving register-level orders unchanged.
2. **US1 governance**: inventory in `prepare`, model step + coverage check node, outputs, INPUT_GAP refusal.
3. **US2 functional SWE.1**: author, validators, assembly + attributes, ReqIF, gate checks, two-phase inspection
   level-awareness, later-phase refusal.
4. **Pilot launch**: example 0012u, interrupt-mapping input, lineage + PILOTS option, allowance/driver-class check,
   decision log started; CRE gate; deploy; run SWE.1 on the line.
5. **US3 comparison**: private metrics extraction (outside the repo), compare tool, privacy scan, proposal generator.

## Risks

- **Model output quality at a new level**: the functional author is new; the two-phase inspection and deterministic
  checks bound it; expect CAPAs during the pilot (normal CRE flow).
- **Context bound**: about 30 HAL functions plus the LL subset; packets are per use case / group with bounded inputs
  (index of the RM chapter, not the whole chapter), following CAPA-242/243.
- **Allowance / driver class**: a new lineage may need a policy grant (UNVERIFIED) - checked first in the pilot launch
  phase; if it needs owner-signed material, the factory reports an input gap rather than editing signed controls.

## Complexity Tracking

No constitution violations; nothing to justify.
