# Tasks: Preserve validated artifacts across runs

**Input**: [spec.md](spec.md), [plan.md](plan.md), [granularity-analysis.md](granularity-analysis.md)
**Tests**: TDD - every task writes its test first (fail before / pass after); behaviour changes go through CRE
(registry -> CAPA -> reproducer -> promotion gate). Paths relative to `factory/python/`.

## Phase 1: Setup

- [X] T001 Create branch `feat/021-preserve-validated-artifacts` from the campaign tip in a new worktree `repos/forge-c-021-preserve`
- [X] T002 Baseline: run the f020 regression scope and the register-level identity guards; record failing set in `specs/021-preserve-validated-artifacts/baseline.md`

## Phase 2: Foundational (blocks all stories)

- [X] T003 [P] Test: `tests/test_f021_semantic_key.py` - same semantic content under two work-order ids gives the same key; register-level packets byte-identical
- [X] T004 Implement `semantic_key` beside `input_hash` in `forge_factory/lrtx/structured.py` (QM scope without work_order_id in the key only)
- [X] T005 [P] Test: `tests/test_f021_carry_store.py` - put/get by (phase, item_key, content_sha, dep_sha), provenance, intact-source check
- [X] T006 Implement `forge_factory/lrtx/carry_store.py` (sqlite index in the line state dir)

## Phase 3: User Story 1 - a rerun keeps every validated item (P1)

- [ ] T007 [US1] Test: `tests/test_f021_partial_carry.py` - set-level failure rerun re-judges no item; rule change reworks only named items; INPUT_CHANGED carries nothing
- [ ] T008 [US1] Generalise `lrtx/swe1_carry.py` into `forge_factory/lrtx/carry.py` on the store (SWE.1 functional unchanged, D36/D39/D40 tests green)
- [ ] T009 [US1] Partial phase carry in `forge_factory/workorder.py` resume and `forge_factory/lrtx/visit.py` (keep valid items of a non-PASS phase, re-freeze, set checks once)

## Phase 4: User Story 2 - carried items are auditable (P1)

- [ ] T010 [P] [US2] Test: `tests/test_f021_carry_manifest.py` - every carried item listed with provenance; never labelled direct; altered source -> SOURCE_RECORD_CHANGED
- [ ] T011 [US2] Carry manifest in the release packager (`forge_factory/release/`) and refusal reasons in `forge_factory/lrtx/carry.py`

## Phase 5: User Story 3 - every SWE phase (P2)

- [ ] T012 [US3] Test + implement SWE.2 units (interface function / design decision) with dependency sets in `forge_factory/lrtx/swe2.py`
- [ ] T013 [US3] Test + implement SWE.3 per-unit carry in `forge_factory/lrtx/swe3.py`
- [ ] T014 [US3] Test + implement SWE.4 per-test carry with hash-bound run results in `forge_factory/lrtx/swe4.py` and `forge_factory/inspection/engine.py` (FR-007)
- [ ] T015 [US3] Test + implement SWE.5 per-integration-test and SWE.6 per-requirement-scenario carry (`lrtx/swe5.py`, `lrtx/swe6.py`)
- [ ] T016 [US3] Wire `forge_factory/assurance/impact.py` ImpactGraph into rerun planning (replace whole-phase `stale_reason` for carry orders)

## Phase 6: Polish

- [ ] T017 [P] Quickstart `specs/021-preserve-validated-artifacts/quickstart.md` with the commands and results
- [ ] T018 Final regression on the deployed commit; mark tasks [X] only with recorded evidence

## Dependencies

Phase 2 before all stories; US1 before US2 (manifest lists what US1 carries); US3 after US1. T012-T015 parallel by file.
MVP: Phases 1-4 (SWE.1 functional on the generic store with manifest).
