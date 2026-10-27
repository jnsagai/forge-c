# Implementation Plan: Peripheral onboarding as a factory pipeline stage

**Branch**: `feat/016-peripheral-onboarding` (stacked on `feat/015-st-hal-benchmark`) | **Date**: 2026-10-27 |
**Spec**: [spec.md](spec.md)

## Summary

Onboarding runs in three steps between delivery intake and SWE.1:

1. **Derive** (Python, no model). The work order's owner inputs produce the package facts: instance, base address,
   register index, driver style, time base, undelivered externals, instance comparisons, and the file map with the
   framework modules. Each fact carries its source.
2. **Author** (a separate Fabro run, only when needed). Gated and inspected roles author the simulation model and the
   domain texts that cannot be derived.
3. **Approve** (between runs). The owner signs the package hash, the conflict resolutions and the test-environment
   assumptions. AFO admits the SWE.1–SWE.6 run only after a verified approval.

The package contains a **derived profile** in the feature 009 profile format. When a work order names an approved
package, `peripheral.of_ws` returns that profile, so every existing consumer works unchanged. The prompt keys come
from a template generator per driver style plus the authored texts, never from hand-written profile texts. A
leftover check gates every built instruction.

Existing hand-onboarded peripherals keep their profiles, and serve as the regression oracle for the derivation.

## Technical Context

- **Language/Version**: Python 3.13 (factory); C11 delivered code; Renode 1.17 Python peripherals (IronPython 2.7
  compatible, a feature 015 lesson).
- **Primary Dependencies**: existing only.
  - `forge_factory.brownfield` (delivery intake, `configure_hal_conf`, scope extraction, conformance, cmsis host
    device);
  - `forge_factory.peripheral`, `layer`;
  - `inspection.regmap` and `assurance.hardware` (RM parsers);
  - `docs.pdf2md`;
  - `forge-sim-mcp` (Renode);
  - `workflow.builder`/`prompts`;
  - `registry.skillgen` (role SKILL.md rendering from `config/factory/agents.yaml`);
  - AFO conductor, queue and authz;
  - `ssh-keygen -Y verify`.

  No new third-party packages.
- **Storage**: files. The package lives under `$FORGE_STATE_DIR/workorders/<WO>/onboarding/`. Signed approvals live
  with it and are copied to `evidence/easa/owner-decisions/` in owner-decision commits. The AFO queue's SQLite store
  gains two order states.
- **Testing**: pytest. The tests cover:
  - the derivation units;
  - the regression oracle over existing examples;
  - the text generator and leftover check;
  - the model gate on the existing models;
  - the approval verification;
  - the AFO state transitions.

  Plus Fabro graph validation for the onboarding run, then live acceptance runs on loop10.
- **Target Platform**: loop10 (factory host, Fabro, Renode, Codex and Claude logins). The derivation also runs on
  omniverse2; the local-model onboarding run is NOT_RUN.
- **Project Type**: factory library plus CLI stage inside an existing workflow system.
- **Performance Goals**: the deterministic derivation takes under 10 minutes per work order (SC-004). The link and
  build iterations dominate.
- **Constraints**:
  - zero model calls in derivation;
  - deterministic package hash;
  - hand-onboarded work orders produce byte-identical workflows;
  - no change to protected paths (checklists, release policies, safety policies);
  - FROZEN delivered code is never written.
- **Scale/Scope**: 4 acceptance drivers, 8 regression-oracle combinations, 1 held-out model authoring (CRC).

## Constitution Check

| Principle | Compliance | Status |
|---|---|---|
| I. Safety and correctness | Hardware facts come from the RM and the vendor headers with sources. Authored models are gated against the RM reset values and access types. Unknowns are NOT_DERIVED, never defaulted. | PASS |
| II. Evidence | Each fact records its method and source. Gates record tool invocations and hashes. Approval binds the package hash. Every SWE work product records the package hash. | PASS |
| III. Unattended run, external authority | No human node inside any Fabro run. The owner gate sits between the onboarding run and the SWE run, signed by the owner. AFO bounds the wait with a TTL and finalizes BLOCKED. | PASS |
| IV. Versioned skills | Four new roles (model author/inspector, text author/inspector) in `agents.yaml`, each with a rendered SKILL.md. Authors and inspectors are distinct identities. | PASS |
| V. MCP only | Authored items use `forge-docs-mcp` and `forge-sim-mcp` (new `check_model` op) and `write_file` restricted by authz prefixes. Derivation is a non-AI factory step (native APIs allowed). | PASS |
| VI. Model-free supervision | No supervisor change. The new AFO states are deterministic and TTL-bounded. | PASS |
| VII. Evidence-based knowledge | Not affected: no lessons are created from onboarding. | PASS |
| VIII. Traces | The stage emits factory events in the existing schema. Raw prompts stay OFF. | PASS |
| IX. Minimal model cost | Derivation is model-free. Authoring runs only for items that cannot be derived, with role budgets. | PASS |
| X. Open source | No new dependency. The RM PDFs stay local; only hash manifests are tracked. | PASS |
| Governance | Gates are added, none weakened. Checklists, release policies and protected paths are not changed. The `SIMULATOR_MODEL_NOT_COMPARABLE` limitation is replaced only when a gated model result exists. Every factory change goes through the CRE gate (FR-023). | PASS |

Post-design re-check: PASS. The design adds no human node, no paid service and no protected-path change.

## Slices (in order)

| Slice | Content | Stories | FRs |
|---|---|---|---|
| A | Package and fact model, schema, writer, deterministic hash. Work-order schema: `target.instance`, optional file map and modules, PDF RM input. | US1 | FR-001, 005, 006, 015 |
| B | Derivation of identity facts: instance, base address with memory-map page, prefix, register index, driver style, headers, prefixes. | US1 | FR-004 |
| C | Derivation of behaviour facts: time base, timeout constants, waits, undelivered externals via link, instance comparisons, file map and modules via the bounded build loop, assumptions proposed. | US1 | FR-004, 007 |
| D | Regression oracle over `0008c`, `0009-iwdg-st`, `0010c`–`0014c`, `0014d`, with a reviewed exceptions file. | US1 | FR-020 |
| E | Derived profile, `peripheral.of_ws` preference, manifest `onboarding` block, package hash in work-product evidence. | US2, US3 | FR-014, 018, 019 |
| F | Owner approval: summary page, approval schema, signature verification (namespace `forge-onboarding-approval`), CONFLICT and assumption rules, invalidation on hash change. | US2 | FR-016, 017 |
| G | AFO integration: states `ONBOARDING` and `WAITING_OWNER_APPROVAL` (TTL), dispatch of the SWE run after verified approval, refusal otherwise. | US2 | FR-016, 021 |
| H | Text generator per driver style, authored-text slots, package-only `peripheralize` path, leftover check. | US3 | FR-010, 012, 013 |
| I | Model gate (`forge-sim-mcp check_model`): load, reset values, access types, smoke. Run on the existing models; their results recorded. | US4 | FR-011 |
| J | Onboarding Fabro run: graph, four role skills, authz prefixes, bounded loops, gaps. | US3, US4 | FR-008, 009, 022 |
| K | Held-out model authoring (CRC) and SC-007 check. | US4 | SC-007 |
| L | Acceptance: GPIO, SPI, USART and TIM ST HAL onboarded, approved by the owner, run SWE.1–SWE.6. Record frozen; feature 015 T065 closed by reference. | US5 | SC-001, 005, 006 |

Each slice ends with its tests, the full suite, `tests/spec/validate_design.py` and a CRE decision before any
deploy.

## Project Structure

### Documentation (this feature)

```text
specs/016-peripheral-onboarding/
├── spec.md
├── plan.md                      # this file
├── research.md                  # R1-R12 decisions
├── data-model.md                # package, fact, authored item, assumption, gap, approval
├── quickstart.md                # validation scenarios
├── contracts/
│   ├── onboarding-package.schema.json
│   ├── onboarding-package.example.json
│   ├── onboarding-approval.schema.json
│   └── onboarding-approval.example.json
├── checklists/requirements.md
└── tasks.md                     # /speckit-tasks
```

### Source Code (repository root)

```text
factory/python/forge_factory/
├── onboarding/                    # NEW package
│   ├── __init__.py                # stage entry: derive -> (author run) -> package; `python -m forge_factory.onboarding`
│   ├── facts.py                   # Fact model, statuses, sources, package writer + canonical hash
│   ├── identity.py                # slice B (device header, memory map, RM index, driver style)
│   ├── behaviour.py               # slice C (time base, waits, link externals, instance compares, build loop)
│   ├── profile.py                 # derived profile (feature 009 schema) from facts + approved assumptions
│   ├── texts.py                   # slice H template generator per driver style + authored slots
│   ├── leftovers.py               # FR-013 leftover check over built instructions
│   ├── approval.py                # summary.md, approval verification, invalidation
│   └── oracle.py                  # slice D regression comparison helpers
├── peripheral.py                  # of_ws: approved package profile first
├── workorder.py                   # prepare(): derivation; manifest onboarding block; SWE refused without approval
├── workflow/builder.py            # onboarding graph (slice J); SWE graph unchanged
├── workflow/prompts.py            # package-only key source for package-driven work orders
├── mcp/servers/sim.py             # check_model operation
├── policy/authz.py                # onboard-* role write prefixes
├── afo/queue.py, dispatch.py, conductor.py   # ONBOARDING / WAITING_OWNER_APPROVAL
└── assurance/hardware.py          # simulator limitation from the model gate result when present
config/factory/agents.yaml         # onboard-model-author|inspector, onboard-text-author|inspector (SKILL.md rendered
                                   # into .fabro/skills by registry.skillgen)
config/factory/onboarding/oracle-exceptions.yaml   # reviewed regression differences
specs/008-brownfield-work-orders/contracts/brownfield-workorder.schema.json   # target.instance, optional derived fields
factory/python/tests/test_onboarding_*.py
examples/0010e-st-cube-gpio-hal-ob/ … 0013e-st-cube-tim-hal-ob/   # acceptance work orders: owner inputs only
```

**Structure Decision.** Onboarding is a new package inside the existing factory library, beside `brownfield/`. It is
wired into the existing preparation, prompt, simulator, authz, skills and AFO modules at the points listed.
Acceptance work orders are new examples with owner inputs only. The feature 015 `0010d`–`0013d` examples keep their
hand-written maps and become oracle cases.

## Complexity Tracking

No constitution violations to justify.
