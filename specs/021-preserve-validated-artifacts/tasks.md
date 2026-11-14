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

- [X] T007 [US1] Test: `tests/test_f021_partial_carry.py` - set-level failure rerun re-judges no item; rule change reworks only named items; INPUT_CHANGED carries nothing
- [X] T008 [US1] Generalise `lrtx/swe1_carry.py` into `forge_factory/lrtx/carry.py` on the store (SWE.1 functional unchanged, D36/D39/D40 tests green)
- [X] T009 [US1] Partial phase carry in `forge_factory/workorder.py` resume and `forge_factory/lrtx/visit.py` (keep valid items of a non-PASS phase, re-freeze, set checks once) - 196f443c: `visit.inherited_task` also takes the VALID author tasks of the earlier attempts of the order's line series by semantic key (every phase); `run_task` records the key; `tests/test_f021_partial_phase_carry.py` 8/8 (fail before); regression 189 files 37=37 NEW none (`model-service/reg021b.out`). The set checks run once on the re-frozen phase as before (no change needed).

## Phase 4: User Story 2 - carried items are auditable (P1)

- [X] T010 [P] [US2] Test: `tests/test_f021_carry_manifest.py` - every carried item listed with provenance; never labelled direct; altered source -> SOURCE_RECORD_CHANGED
- [X] T011 [US2] Carry manifest in the release packager (`forge_factory/release/`) and refusal reasons in `forge_factory/lrtx/carry.py`

## Phase 5: User Story 3 - every SWE phase (P2)

- [ ] T012 [US3] Test + implement SWE.2 units (interface function / design decision) with dependency sets in `forge_factory/lrtx/swe2.py` - DEFERRED 2026-11-14: SWE.2's two author tasks are monolithic; a per-function unit needs a kept-units merge like SWE.1's (a change of the SWE.2 authoring structure). SWE.2 does not run on the line now (pilots are SWE.1-only); T009 carries the whole task when its inputs are unchanged.
- [X] T013 [US3] Test + implement SWE.3 per-unit carry in `forge_factory/lrtx/swe3.py` - no code change needed: a SWE.3 task is one unit whose packet holds only its dependency set, so T009 carries every unchanged unit; `tests/test_f021_unit_carry.py` (a changed requirement changes the key of exactly its units).
- [ ] T014 [US3] Test + implement SWE.4 per-test carry with hash-bound run results in `forge_factory/lrtx/swe4.py` and `forge_factory/inspection/engine.py` (FR-007) - PARTIAL ab3fee3a: per-test author carry via T009 (`test:<UT>` tasks); verification tool results record `code_sha` and a PASS on the frozen code stays current (`tests/test_f021_tool_evidence_binding.py`, fail before). OPEN: per-test-id result binding (run_unit is per suite) and the tool-image hash.
- [ ] T015 [US3] Test + implement SWE.5 per-integration-test and SWE.6 per-requirement-scenario carry (`lrtx/swe5.py`, `lrtx/swe6.py`) - PARTIAL: SWE.6 tasks are per scenario topic and SWE.5 tasks per file kind, so T009 carries at that granularity. OPEN: splitting SWE.5 into per-integration-test tasks (authoring change; SWE.5 not on the line now).
- [ ] T016 [US3] Wire `forge_factory/assurance/impact.py` ImpactGraph into rerun planning (replace whole-phase `stale_reason` for carry orders) - DEFERRED 2026-11-14: `stale_reason` decides whether an inspection PASS still holds (`inspection/gate.py`, `engine.py`); an item-level impact walk there changes verdict validity and needs a reviewed design (never present an earlier revision's verdict as a new direct PASS).

## Phase 6: Polish

- [X] T017 [P] Quickstart `specs/021-preserve-validated-artifacts/quickstart.md` with the commands and results
- [ ] T018 Final regression on the deployed commit; mark tasks [X] only with recorded evidence

## Dependencies

Phase 2 before all stories; US1 before US2 (manifest lists what US1 carries); US3 after US1. T012-T015 parallel by file.
MVP: Phases 1-4 (SWE.1 functional on the generic store with manifest).
