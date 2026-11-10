# Tasks: Factory-prepared run inputs

**Input**: Design documents from `specs/019-factory-prepared-inputs/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/driver-ladder.md, quickstart.md

**Tests**: required (CLAUDE.md: tests before code; a task is checked only with run evidence). Paths are relative to
`factory/python/` unless they start with `specs/` or name the deployer package.

**Organization**: by user story (spec.md). US1 and US2 are P1; US3 and US4 are P2.

## Format: `[ID] [P?] [Story] Description`

## Phase 1: Setup

- [X] T001 Record the baseline: run `tests/test_owner_supervised_hal_lineage.py tests/test_owner_supervised_development.py tests/test_owner_development_allowance.py tests/test_wwdg_simplest_lineage.py` and the campaign/planner suites (`tests/*campaign*.py tests/*line_orders*.py`) on `58b2fcda`; save the failing-test list to `specs/019-factory-prepared-inputs/evidence/baseline-failures.txt`

---

## Phase 2: Foundational (blocking)

**Purpose**: the campaign key `after` and the HAL lineages in the allowance table, needed by every story.

- [X] T002 [P] Write failing tests for `after` in `tests/test_f019_campaign_after.py`: accepted shape; refused unknown lineage, self reference, non-PASS verdict, malformed (`FIELD_INVALID:after`); cycle over depends_on+after (`DEPENDENCY_CYCLE`)
- [X] T003 Add `after` to `LINEAGE_KEYS`, the `Lineage` dataclass, `parse` and `validate` (cycle check over `depends_on` and `after`) in `forge_factory/afo/line_campaign.py`; T002 passes
- [X] T004 [P] Add `after` (object: lineage, phase, verdict PASS) to `specs/014-durable-local-autonomy/contracts/line-campaign.schema.json`; `line_campaign.contract_errors` accepts a document using it
- [X] T005 Add `spi-hal` (SPIH, 20261109-L46, `0011m-spi-hal`, STM32N6_SPI_HAL, depends_on spi-ll) and `tim-hal` (TIMH, 20261109-L47, `0013m-tim-hal`, STM32N6_TIM_HAL, depends_on tim-ll) to `LINEAGES` in `forge_factory/afo/owner_supervised_development.py`; update the pinned lists in `tests/test_owner_development_allowance.py`, `tests/test_owner_supervised_development.py` and extend `tests/test_owner_supervised_hal_lineage.py` (each HAL only on its own LL SWE.6)

**Checkpoint**: campaign files may use `after`; the allowance knows all ladder lineages.

---

## Phase 3: User Story 1 - The ladder is factory source (P1) MVP

**Goal**: every deploy builds the campaign from `LADDER` in source; no hand-edited package template is used.
**Independent test**: `derived_campaign()` validates, lists the ladder in order with the right statuses, priorities,
`depends_on`/`after`; the generator uses it and records `campaign_source: DERIVED`.

- [X] T006 [P] [US1] Write failing tests in `tests/test_f019_derived_campaign.py`: `LADDER` ids are in `LINEAGES`, unique, each HAL after its LL; `derived_campaign()` deterministic, validates with `line_campaign.validate` after `@SOURCE@` substitution, ladder steps ACTIVE with descending priority from 50, off-ladder ON_HOLD (30), step k>0 has `depends_on` (HAL on own LL SWE.6) or `after` (previous step SWE.6), quality digest == `QUALITY_SHA`, phases SWE.1..SWE.6
- [X] T007 [US1] Implement `LADDER` and `derived_campaign()` in `forge_factory/afo/owner_supervised_development.py` (campaign id `CAMPAIGN`, line `local`, prefix `WO-F014`, profile/run_model constants); T006 passes
- [X] T008 [US1] Edit the deployer generator `generate-development-inputs.py` in the live package `/mnt/data/forge-c/owner-autodeploy/ops/owner-allowance-main-auto-<live>/` (backup `*.bak-f019`): use `D.derived_campaign()` when the source has it, else the template (rollback); report `campaign_source` and `template_sha256_ignored`; keep the unknown-lineage drop and the `CAMPAIGN_SCOPE_CHANGED` check
- [X] T009 [US1] Dry-run the edited generator against the feature source into a scratch directory; check the emitted campaign equals `derived_campaign()` with the source commit and the report says `DERIVED`; save the output listing to `specs/019-factory-prepared-inputs/evidence/generator-dry-run.txt`

**Checkpoint**: US1 complete - the campaign comes from source.

---

## Phase 4: User Story 2 - The line walks the ladder (P1)

**Goal**: the Planner starts the next ladder step only when the previous one passed SWE.6; HAL builds on its LL;
a growing phase list continues from the last passed phase.
**Independent test**: Planner on a fake record set with two/three steps places exactly the expected next order.

- [X] T010 [P] [US2] Write failing Planner tests in `tests/test_f019_ladder_walk.py` (reuse the record fakes of the existing line_orders tests): (a) `after` lineage WAITING `AFTER:<id>:SWE.6:PASS` and no order while the previous step runs; (b) once the previous SWE.6 passed, the LL step gets a START order with `provided_from` None; (c) HAL gets START with `provided_from` = the newest passing LL SWE.6 order; (d) a lineage whose SWE.1 passed under a one-phase campaign gets CHAIN SWE.2 `resume_from` that order (L44F case); (e) never two ladder steps placed in one plan
- [X] T011 [US2] Implement the `after` wait in `Planner.decide` in `forge_factory/afo/line_orders.py` (no `provided_from`); T010 passes
- [X] T012 [US2] Run the existing planner/recovery suites (`tests/*line_orders*.py tests/*line_recovery*.py tests/*campaign*.py`) and compare with the T001 baseline; record in `specs/019-factory-prepared-inputs/evidence/regression-us2.txt`

**Checkpoint**: US1+US2 = the owner's ladder runs unattended.

---

## Phase 5: User Story 3 - Missing input is a visible gap (P2)

**Goal**: a step without its work-order spec is held as `INPUT_GAP` and blocks later steps; the floor shows the ladder.
**Independent test**: Planner with a step whose example has no `workorder.json` -> WAITING `INPUT_GAP:WORKORDER_SPEC:<example>`;
the floor panel returns the ladder from an audit row.

- [X] T013 [P] [US3] Write failing tests in `tests/test_f019_input_gap.py`: missing `examples/<example>/workorder.json` -> WAITING `INPUT_GAP:WORKORDER_SPEC:<example>`, no order; later `after` step stays WAITING; the gap clears when the spec exists (no other change)
- [X] T014 [US3] Implement the input-gap hold in `Planner.decide` (`forge_factory/afo/line_orders.py`) after dependencies are satisfied and before a lineage's first order; T013 passes
- [X] T015 [P] [US3] Write failing tests in `tests/test_f019_floor_ladder.py`: `owner_lane_panel` reads the last row of the newest `*.audit.jsonl` (bounded tail) and returns `ladder[]` (lineage, state, reason, phase, wo) in priority order; missing/malformed file -> no ladder, panel still available; codes/ids only
- [X] T016 [US3] Implement the ladder view in `forge_factory/lrtx/owner_lane_panel.py` and the ladder strip (done / running / waiting for / input gap) in `forge_factory/dashboard/static/factory-floor.html`; T015 passes; page script parses with node 20

**Checkpoint**: gaps are visible; nothing is hand-written.

---

## Phase 6: User Story 4 - Allowance follows the ladder (P2)

**Goal**: admission accepts every ladder order and refuses a HAL on anything but its own LL SWE.6 order; a rollback
drops unknown lineages.
**Independent test**: validate_order for HAL/LL shapes; generator on an older source drops the HAL lineages.

- [X] T017 [P] [US4] Extend `tests/test_owner_supervised_hal_lineage.py`: for `spi-hal`/`tim-hal` accept own-LL SWE.6, refuse WWDG LL SWE.6 and other phases; a `derived_campaign()` lineage set equals `LINEAGES`
- [X] T018 [US4] Generator rollback check: run the edited generator against `ecec42e9` (no `derived_campaign`, no HAL lineages) -> `campaign_source: TEMPLATE`, unknown lineages dropped; save to `specs/019-factory-prepared-inputs/evidence/generator-rollback.txt`

---

## Phase 7: Polish & delivery

- [X] T019 Run all `tests/test_f019_*.py`, the allowance suites and `python3 tests/spec/validate_design.py`; compare with the T001 baseline; save to `specs/019-factory-prepared-inputs/evidence/final-tests.txt` (2026-11-10: 80 passed, design check PASS)
- [X] T020 Register the change in the CRE registry (CAPA-204: manual campaign inputs; owner 2026-11-09) with the commit and tests (CAPA-204 TRIAGED in the host CRE store)
- [X] T021 Merge the feature branch into `feat/owner-lane-campaign-v21-20261107` (merge commit), push to the host repo; the deployer timer gates (CRE) and deploys unattended - do not start a manual gate (`c052a38c` ELIGIBLE pd-d12da294; deployed with `9bb2c981` 2026-11-09 13:48Z, stage `55b0530a` ELIGIBLE pd-ec99e2d8 deployed 14:31Z)
- [ ] T022 Native acceptance after deploy: deploy record `campaign_source: DERIVED`; guardian audit shows `wwdg-ll` at SWE.2 with `resume_from` the passed L44 SWE.1 order (or still SWE.1 if L44F failed), `wwdg-hal` WAITING `DEPENDS_ON:wwdg-ll:SWE.6:PASS`, `spi-ll` WAITING `AFTER:wwdg-hal:SWE.6:PASS`; floor ladder strip matches; save to `specs/019-factory-prepared-inputs/evidence/native-acceptance.md` - SUPERSEDED by the Phase 8 owner amendment (SWE.1 stage: the SWE.2/SWE.6 states named here no longer apply); acceptance moves to T025

## Phase 8: Owner amendment - SWE.1 stage (2026-11-09 ~14:00)

- [X] T023 [US1] `LADDER = (wwdg-ll, wwdg-hal, spi-ll, tim-ll)`, `LADDER_PHASES = ("SWE.1",)`, `PROVIDED_LL` (WWDG LL L29, checked by `workorder.provided_ll`: six gates PASS, frozen ST header) and `derived_campaign()` per stage in `forge_factory/afo/owner_supervised_development.py`; tests `tests/test_f019_derived_campaign.py` (rewritten), `tests/test_owner_supervised_hal_lineage.py`, `tests/test_f019_ladder_walk.py` (stage walk)
- [X] T024 [US1] Generator dry run with the stage source from the live package `owner-allowance-main-auto-9bb2c981`: `evidence/generator-dry-run-swe1-stage.txt` (DERIVED; ladder steps SWE.1 only)
- [ ] T025 Native acceptance of the stage: WWDG HAL SWE.1 `WO-F014-SWE1-WWDGH-20261109-L45` starts by itself with `--provided-from` L29; SPI LL SWE.1 follows its pass; TIM LL SWE.1 after SPI; `evidence/native-acceptance.md` - 2026-11-10: WWDG HAL and SPI LL steps proven; TIM LL order created by the line, run pending (see evidence)

## Dependencies & execution order

- T001 -> Phase 2 (T002->T003, T004 parallel, T005) -> US1 (T006->T007->T008->T009) and US2 (T010->T011->T012)
  -> US3 (T013->T014; T015->T016) and US4 (T017, T018 after T008) -> T019 -> T020 -> T021 -> T022.
- US2 depends on T003 (`after`); US1 depends on T003 and T005; US3's floor part (T015-T016) is independent of the
  Planner part; US4 T018 needs T008.

## Parallel examples

- Phase 2: T002 and T004 together (different files).
- After Phase 2: T006 (US1 tests), T010 (US2 tests), T013 and T015 (US3 tests) together.

## Implementation strategy

MVP = Phase 2 + US1 + US2 (the ladder is source and the line walks it). US3 and US4 harden it before the deploy
(T021); nothing is deployed before T019 passes and the CRE gate rates the merge ELIGIBLE.

## Progress (2026-11-09)

- T001: `evidence/baseline-failures.txt` (127 environment-bound FAILED/ERROR on 58b2fcda: durable volume, GPU lock).
- T002-T007, T010-T011, T013-T014, T017: 34 feature tests in `tests/test_f019_*.py` and
  `tests/test_owner_supervised_hal_lineage.py`; they failed before the code (17 failures) and pass after it. The
  phase-growth test passed before the code too (existing Planner behaviour; kept as a regression guard).
- T012: `evidence/after-us1-us2-us3.txt` + `evidence/regression-diff.txt`: the FAILED/ERROR list equals the baseline.
- T008: deployer generator in `ops/owner-allowance-main-auto-ecec42e9/` (backup `*.bak-f019`): `source_campaign()`.
- T009 / T018: `evidence/generator-dry-run.txt` (feature source: DERIVED, template ignored) and
  `evidence/generator-rollback.txt` (ecec42e9: TEMPLATE, today's campaign).
- T015-T016: floor monitor line `floor-sup-bc868918` (the floor runs from its monitor copy, not from this branch):
  `tests/test_f019_floor_ladder.py` 3 pass (2 failed before the code); page script parses (node 20); live
  `/floor.json` owner_lane.ladder available at guardian cycle 110.
