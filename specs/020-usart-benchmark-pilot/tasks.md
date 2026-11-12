# Tasks: USART benchmark pilot - SWE.1 the benchmark way

**Input**: `specs/020-usart-benchmark-pilot/` (spec.md, plan.md, research.md, data-model.md, contracts/, quickstart.md)

**Tests**: requested (TDD). Every implementation task is preceded by its tests; each test must FAIL on the base
commit and PASS after the task (record both). Paths are relative to the repository root; Python code is under
`factory/python/forge_factory/` (F) and tests under `factory/python/tests/`.

**How to run** (Omniverse2, over ssh, in `/mnt/data/forge-c/repos/forge-c-020-usart`): Python
`/mnt/data/forge-c/repos/forge-c-capa195/.venv/bin/python`, from `factory/python`, env
`FORGE_DATA_ROOT=/mnt/data/forge-c PYTHONDONTWRITEBYTECODE=1`. Never run git over the sshfs mount, never
`git commit -a`; after each test run restore `docs/IMPLEMENTATION-STATUS-v0.4.md` and
`evidence/v0.4/implementation-status.json`. Never copy private inputs or benchmark content into the repository.
Hard limits: do not edit `llm_gateway.py`, `afo/product_job.py`, `afo/execution_lifecycle.py`, `fabro/client.py`,
`lrtx/stack.py`, `config/factory/profiles/*.yaml`, `factory/checklists/**`,
`config/factory/swe1-requirements-quality.yaml`.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency on an unfinished task)
- **[Story]**: US1 governance, US2 functional SWE.1, US3 comparison

---

## Phase 1: Setup

- [ ] T001 Rebase the feature onto the deployed campaign tip so the held SWE.3 commits (578df4d8, 751dc57f) do not ride along: create branch `feat/020-usart-benchmark-pilot-r` from `303b46ea` and cherry-pick the three spec/plan commits (c550d66f, 0094f18f, 851a5212 and this tasks commit); switch the worktree `/mnt/data/forge-c/repos/forge-c-020-usart` to it; copy the git-ignored example inputs as `/mnt/data/forge-c/model-service/swe3reg.sh` does; record the base in `specs/020-usart-benchmark-pilot/decision-log.md` (new row)
- [ ] T002 Create a clean base worktree `/mnt/data/forge-c/repos/forge-c-020-base` at `303b46ea` with the same ignored inputs, for fail-before runs and regression comparisons
- [ ] T003 [P] Create `config/factory/swe1-functional-template.yaml` (schema `forge-c/swe1-functional-template/1`): template id `swe1-functional-v1`, attribute list and enums exactly as `specs/020-usart-benchmark-pilot/contracts/functional-requirement.schema.json`, origin groups, fixed lane values (status draft, ASIL QM, CAL 0, allocation text "not applicable until SWE.2"), the level-rule term sources (RM register index + CMSIS header symbols, hex-address pattern)

---

## Phase 2: Foundational (blocks every story)

- [ ] T004 [P] Write `factory/python/tests/test_f020_level_setting.py`: a work order with `swe1: {level: functional, template: swe1-functional-v1}` yields manifest `swe1_level: functional`, no `register_contract`, and `SWE1_FUNCTIONAL_LATER_PHASES_NOT_YET` for `--stop-after` SWE.2+; a work order without the block yields a manifest byte-identical to the base (compare against a fixture manifest produced on `forge-c-020-base`); invalid block refused (validate against `contracts/workorder-swe1-block.schema.json`)
- [ ] T005 Implement `F/governance/__init__.py` and `F/governance/level.py` (`swe1_level(manifest) -> "functional"|"register"`, `template(manifest)`), the single source every other change reads
- [ ] T006 Implement the work-order handling in `F/workorder.py`: validate the `swe1`/`module`/`scope` blocks against `contracts/workorder-swe1-block.schema.json` (copy the schema to `config/schemas/workorder/swe1-block.schema.json`), stamp `swe1_level` and `swe1_template` only when set, skip the `register_contract` stamp for functional orders, refuse SWE.2+ for functional orders; add the new manifest keys to `CONTRACT_FIELDS` in `F/brownfield/resume.py` only when present (T004 must pass)
- [ ] T007 [P] Write `factory/python/tests/test_f020_identity.py`: for a register-level order, the SWE.1 graph (builder), prompts, gate step list and phase-1 packets are byte-identical to the base (golden captured from `forge-c-020-base` into `factory/python/tests/fixtures/f020/register_identity.json`); run the identity guard suites listed in research.md R1/R2 on both trees and assert no new failures (record the list in the test docstring)

**Checkpoint**: functional orders are recognised; register-level orders provably unchanged.

---

## Phase 3: User Story 1 - The factory prepares the module's inputs before any requirement (P1) 🎯 MVP

**Goal**: governance inventory (deterministic, in prepare) + governance package (model step) + coverage check.

**Independent Test**: prepare the UART order without a model; inventory valid; removing a function from all scope
groups → INPUT_GAP naming it; with a fake model answer the coverage check passes, and dropping an in-scope function
from all use cases → COVERAGE_FAIL naming it, SWE.1 author not started.

### Tests for User Story 1

- [ ] T008 [P] [US1] Write `factory/python/tests/test_f020_governance_inventory.py`: synthetic module fixture (two components, LL header + HAL source with a handful of public functions, two inputs) → inventory validates against `contracts/governance-inventory.schema.json`; delivered files only as `implementation_under_analysis`; every function classified by the scope rule (exact names and `prefix*` patterns); unmatched function and empty pattern refused with INPUT_GAP and the name; the same code prepares a second, different synthetic module (SC-009)
- [ ] T009 [P] [US1] Write `factory/python/tests/test_f020_governance_package.py`: packet built from the inventory only (no delivered code bodies); model answer validated against `contracts/governance-package.schema.json`; coverage computed deterministically (uncovered functions, uncovered RM features, unused use cases); COVERAGE_FAIL stops before the author; owner use cases merged with `origin: owner`; `package_version` = sha256 of the canonical package; Markdown rendering lists actors, use cases, assumptions, open points
- [ ] T010 [P] [US1] Write `factory/python/tests/test_f020_governance_graph.py`: for a functional order the SWE.1 graph starts with `swe1_governance` → `swe1_governance_check` → the functional author, with time-box continuation like other structured nodes; register-level graphs have no governance nodes (identity with T007 golden)

### Implementation for User Story 1

- [ ] T011 [US1] Implement `F/governance/inventory.py`: input register from the manifest inputs (ids `IN-NN`, name, revision from the inputs manifest, sha256, bytes, role, RM sections from the existing section split), delivered public API inventory (HAL from the delivery scope written by `F/brownfield/delivery.py`; LL inline functions parsed from the delivered header with the existing CMSIS/LL parser), RM feature list from the order's scope groups, scope classification; write `inputs/governance-inventory.json` as a listed, fingerprinted input in `F/workorder.py` (pattern of `inputs/delivered-interface.json`, workorder.py:367-373); raise INPUT_GAP on unclassified items (T008 must pass)
- [ ] T012 [US1] Implement `F/governance/package.py`: structured task packet (inventory, input register, RM section index - not the chapter text), answer schema, validation, deterministic coverage, owner use-case merge, JSON + Markdown output to `workproducts/SWE.1/governance/governance-package.json|.md`, version fingerprint recorded in the run (T009 must pass)
- [ ] T013 [US1] Wire the governance step into the structured runner and graph: runner steps `governance` and `governance-check` in `F/lrtx/runner.py`; nodes `swe1_governance`/`swe1_governance_check` before the functional author in `F/workflow/builder.py`, only when `swe1_level == functional` (T010 must pass)
- [ ] T014 [US1] Update the swe1-author skill text through the registry generator (`F/registry/skillgen.py`) so the role description covers the governance task and the functional template; regenerate `.fabro/skills/swe1-author/SKILL.md`; keep the register-level text unchanged

**Checkpoint**: the UART order prepares with a valid inventory; the governance step and coverage check work on fixtures.

---

## Phase 4: User Story 2 - SWE.1 written and inspected at the functional level (P1)

**Goal**: functional author, validators, assembly with attributes, ReqIF, gate checks, two-phase inspection.

**Independent Test**: on fixtures, a valid functional answer assembles into the template with all attributes and
links and passes the gate; each rule violation is rejected with the requirement id and rule; register-level orders
unchanged.

### Tests for User Story 2

- [ ] T015 [P] [US2] Write `factory/python/tests/test_f020_functional_author.py`: task plan (one task per use case group, one HAL design-constraint task from the guideline input, one state-behaviour task, one task per LL service group), packet contents bounded (no chapter text, no code bodies), answer schema = `contracts/functional-requirement.schema.json`, validators: missing attribute, wrong group/link consistency, unknown `input_id`, link to the delivered code, register/field/address/reset-value term in a statement (terms from the RM index and the CMSIS header, hex pattern), non-EARS statement, design constraint not by inspection - each rejected with key and rule
- [ ] T016 [P] [US2] Write `factory/python/tests/test_f020_assembly.py`: assembly writes `workproducts/SWE.1/software_requirements.md` with `**SWR-NNN**`, `Source:` (locators), `Verification:` (method + criterion) and then the attribute lines; `requirement_attributes.json`; `requirements_to_tests.csv`; `.forge-run/lrtx/SWE.1/assembly.json` in the shape `F/lrtx/swe1_quality.py` reads; existing parsers (`review.py:309`, `swtrace.py`, `register_contract.py:30`) parse the new file without error
- [ ] T017 [P] [US2] Write `factory/python/tests/test_f020_reqif.py`: for a functional order the ReqIF has the new attribute definitions and values and `traces-to`/`derived-from` relations to input SPEC-OBJECTs; for a register-level order the ReqIF is byte-identical to the base
- [ ] T018 [P] [US2] Write `factory/python/tests/test_f020_gate.py`: SWE.1 `step_author` for a functional order runs the functional checks (template, groups, links, level rule, no code source) and not the register contract; rejection texts carry requirement id and rule; register-level order runs exactly today's checks
- [ ] T019 [P] [US2] Write `factory/python/tests/test_f020_two_phase.py`: phase-1 packets for a functional order use the functional wording, schema and validators and the unchanged criteria file (sha check); rework splices only the flagged requirement (others byte-identical) and re-validates with the functional validators; phase-1 packets for a register-level order byte-identical to the base

### Implementation for User Story 2

- [ ] T020 [US2] Implement `F/lrtx/swe1_functional.py`: task plan, packets, answer schema from the template config, validators (T015), assembly (T016), `replace_requirement` splice for phase 1; select it in `F/lrtx/runner.py` when `swe1_level == functional` and make SWE.1 a structured phase for such orders regardless of the profile's `phases_by_layer` (code-side rule in `F/workorder.py`, profile untouched)
- [ ] T021 [US2] Implement `F/assurance/swe1_functional_checks.py` and call it from `F/inspection/gate.py` `step_author` for functional SWE.1 orders; keep the presence gate in `F/inspection/engine.py` from requiring `register_effects.json` when the register contract is absent (T018 must pass)
- [ ] T022 [US2] Extend `F/inspection/reqif_export.py` for functional orders: attribute definitions/values from `requirement_attributes.json`, input SPEC-OBJECTs from the governance input register, relation types `traces-to` and `derived-from` (T017 must pass)
- [ ] T023 [US2] Make `F/lrtx/swe1_quality.py` level-aware: functional packet wording, schema and validators from `swe1_functional.py`; criteria file untouched; register-level code path unchanged (T019 must pass)
- [ ] T024 [US2] Run all US1/US2 tests plus the identity suite (T007) and a regression of every test file matching `swe1|swe1_quality|review|reqif|gate|builder|workorder|brownfield|governance|fingerprint|owner_supervised|derived_campaign` on the feature tree and on `forge-c-020-base`; NEW failures must be none; record the result in `specs/020-usart-benchmark-pilot/decision-log.md` (evidence column of D5/D11/D12)

**Checkpoint**: functional SWE.1 works end to end on fixtures; register-level unchanged.

---

## Phase 5: Pilot launch (US1 + US2 on the real module)

- [ ] T025 [US2] Extract the USART/UART interrupt mapping from `/mnt/data/forge-c/inputs/stm32n6/rm0486.txt` (and the datasheet if needed) with the existing converter into `RM0486-rev4-interrupts-usart.md`; store the body in the line inputs cache (`/mnt/data/forge-c/line/inputs-cache/sha256/<hex>`), add only its manifest entry (doc, pages, sha256, converter) to `examples/0012-usart-st/inputs/inputs-manifest.json`; if the table cannot be found, record an open point instead (spec assumption)
- [ ] T026 [US2] Create `examples/0012u-st-cube-uart-module/workorder.json`: layer `LL+HAL`, FROZEN cmsis delivery of the four HAL UART files and the LL USART header (as 0012c/0012d), inputs (RM ch65, memory map, interrupt mapping, datasheet, register conventions, HAL driver guideline, CMSIS device header), `swe1: {level: functional, template: swe1-functional-v1}`, `module` (components HAL_UART and LL_USART, `uses: []` for both), `scope.in/out/not_delivered` per spec FR-009..FR-012 written with function names/patterns from the delivered headers (no benchmark wording), budgets/system_names/target as 0012d
- [ ] T027 [US2] Write `factory/python/tests/test_f020_uart_order.py`: the 0012u order prepares (with the inputs cache materialised as `/mnt/data/forge-c/model-service/matinputs.py` does) and its inventory classifies every delivered public function; out-of-scope and not-delivered lists match the spec; no INPUT_GAP
- [ ] T028 [US2] Add the lineage `uart-module` (tag `UARTM`, example `0012u-st-cube-uart-module`, driver class `STM32N6_UART_MODULE_ST`) to `LINEAGES` and a generic `PILOTS = {"uart-module": ["SWE.1"]}` option to `derived_campaign()` in `F/afo/owner_supervised_development.py` (ACTIVE, own phases, no `after` chaining, ladder untouched); tests in `factory/python/tests/test_f020_pilot_lineage.py` (campaign validates with `F/afo/line_campaign.py`; ladder lineages unchanged; existing lineage order names unchanged)
- [ ] T029 [US2] Check whether the new driver class/lineage needs a policy grant or allowance entry (owner allowance generator, PILOT grant `driver_classes`); if it only needs generated (unsigned) data, add it with a test; if it needs owner-signed material, stop and report an input gap - never edit signed controls
- [ ] T030 CRE: open a CHANGE record for the feature in the owner CRE store (next free id checked right before registering; refuse if taken), merge the feature branch with the live campaign tip (merge commit), push to `/mnt/data/forge-c/owner-autodeploy/repo.git` branch `feat/owner-lane-campaign-v21-20261107`; the deployer gates the exact commit and deploys only when ELIGIBLE; on REJECTED, diagnose (reproducer races like RPR-155 are re-run, never waved through)
- [ ] T031 Watch the pilot SWE.1 run on the line (floor + gate log); a failure follows the normal path (line retry, observer CAPA, maintainer route; hand fixes only via CRE and logged as interventions); record every new rule or finding in `specs/020-usart-benchmark-pilot/decision-log.md`

**Checkpoint**: the UART pilot's SWE.1 PASSes on the line with no owner input (SC-006).

---

## Phase 6: User Story 3 - Comparison with the benchmark (P2)

**Goal**: metrics-only comparison, privacy scan, way-of-working proposal.

**Independent Test**: comparison generated from a finished SWE.1 and a metrics file; all metrics both sides; no
benchmark names in the repository.

- [ ] T032 [P] [US3] Write `factory/python/tests/test_f020_compare.py`: pilot metrics computed from a fixture SWE.1 (count, by type, attribute completeness, by origin group, link kinds, verification methods, test levels, scope coverage) validate against `contracts/benchmark-metrics.schema.json`; report contains both sides for every metric; missing benchmark file → clear refusal
- [ ] T033 [P] [US3] Write `factory/python/tests/test_f020_privacy.py`: scan of tracked files for forbidden tokens given only as SHA-256 hashes in `factory/python/tests/fixtures/f020/forbidden-token-hashes.json` (tokens lower-cased, word-split); a planted token in a temp file is detected
- [ ] T034 [US3] Outside the repository: write `/mnt/data/forge-c/model-service/private-benchmark/extract_metrics.py` (chmod 700 dir) that reads the private export and writes `metrics.json` (numbers and generic categories only, schema-valid); run it; never commit either file
- [ ] T035 [US3] Implement `F/benchmark/__init__.py` and `F/benchmark/compare.py` (`python -m forge_factory.benchmark.compare --pilot <workspace> --benchmark <metrics.json> --out <dir>`), report Markdown + JSON (T032 must pass)
- [ ] T036 [US3] Implement `F/benchmark/proposal.py` (`--log decision-log.md --metrics <dir>`): `specs/020-usart-benchmark-pilot/way-of-working-proposal.md` with default rules, per-order settings and what the ladder drivers would need, every rule citing its decision-log entry (SC-010); test in `factory/python/tests/test_f020_proposal.py`
- [ ] T037 [US3] Generate the comparison and the proposal from the pilot's real SWE.1; add the forbidden-token hashes (computed locally from the private names, never written in clear) and run the privacy test

---

## Phase 7: Polish & cross-cutting

- [ ] T038 [P] Update `specs/020-usart-benchmark-pilot/quickstart.md` with the commands actually used and their results
- [ ] T039 [P] Memory/notes: record the outcome, the CRE ids and the open follow-ups (SWE.2/SWE.3 alignment feature) in `specs/020-usart-benchmark-pilot/decision-log.md`
- [ ] T040 Final regression (T024 scope) on the deployed commit; mark tasks `[X]` only with recorded evidence

---

## Dependencies & execution order

- Setup (T001-T003) → Foundational (T004-T007) → US1 (T008-T014) → US2 (T015-T024) → Pilot launch (T025-T031) → US3
  (T032-T037) → Polish (T038-T040).
- US1 and US2 tests can be written in parallel once T005-T006 exist; US2 implementation needs the governance input
  register (T011) for link validation.
- US3 needs a passed pilot SWE.1 for T037 only; T032-T036 can be built in parallel with Phase 5.

## Parallel examples

- After T006: T008, T009, T010, T015, T016, T017, T018, T019 (all test files, different paths).
- During Phase 5 waiting time: T032, T033, T034, T035, T036.

## Implementation strategy

- **MVP**: Phases 1-3 (functional orders recognised, register-level identity proven, governance inventory + package +
  coverage on fixtures and on the UART order) - demonstrates the new first step of the way of working.
- **Increment 2**: Phase 4 + Phase 5 - the pilot's functional SWE.1 passes on the line.
- **Increment 3**: Phase 6 - comparison and way-of-working proposal for the owner.
