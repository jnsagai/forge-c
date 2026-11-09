# Tasks: Two-phase SWE.1 inspection

**Input**: [plan.md](plan.md), [spec.md](spec.md), [data-model.md](data-model.md), [contracts/](contracts/)
**Tests**: required (owner lane; CRE gate needs contrast tests). Paths are under `factory/python/` unless noted.

## Phase 1: Setup

- [X] T001 Pin the guideline: `docs/SWE1-REQUIREMENTS-QUALITY-GUIDELINE.md` (copy of main 248e423a) and create
  `factory/checklists/v0.4/SWE.1-quality.yaml` (IQ-01..12, SQ-01..10, severities, `phase1.rounds: 3`, guideline
  sha256); loader `forge_factory/lrtx/swe1_quality.py:quality_checklist()`; test
  `tests/test_f018_quality_checklist.py` re-derives the IDs/properties from the guideline tables and checks the sha.

## Phase 2: Foundational

- [X] T002 Requirement references: `swe1_quality.requirements(ws)` from `assembly.json` + task checkpoints ->
  `(swr, task, key, obj, sha256)`; budget/performance requirements flagged `code_generated`; test with a fixture
  assembly in `tests/test_f018_phase1.py`.
- [X] T003 Single-requirement splice in `lrtx/swe1.py`: `replace_requirement(ws, task, key, new_obj)` validates with
  `validate_group` (or the crosscutting validator), rewrites the task checkpoint (same base_hash, `phase1_rework`
  provenance) and re-assembles from existing records; refuses when any other requirement's hash changes
  (`REFUSED_OTHER_CHANGED`) or the key changes; test (byte-identical others; refusal cases).

## Phase 3: User Story 1 - per-requirement inspection and rework (P1)

- [X] T004 [US1] Inspector packet + validation: `swe1_quality.iq_packet(ws, ref, model)` (role swe1-inspector,
  inspector sampling, schema `contracts/individual-verdict.schema.json`, sources: requirement, same-task requirements,
  cited RM section, scope, out-of-context note, IQ criteria); `validate_iq(doc, ref, sources)`; tests (shape, N/A
  reason, quote check, request shape matches the trial roles).
- [X] T005 [US1] `iq_inspect(ws, model, budget)`: pending selection by content hash and rounds, `visit.run_task`
  checkpoints (`iq:<task>:<key>:<sha12>`), verdict JSONL, summary, reply `iq-inspect-reply.json`, time-box CONTINUE;
  skip when the author reply is not PASS; tests (resume repeats nothing, only changed requirements re-judged).
- [X] T006 [US1] Author packet for one requirement + `iq_rework(ws, model, budget)`: findings needing rework,
  splice (T003), stop rules UNCHANGED/INVALID/ROUNDS -> CARRIED, code-generated -> CARRIED, reply
  `iq-rework-reply.json`; tests.
- [X] T007 [US1] `iq_check(ws)` exit code (0 = rework pending re-judgement) and runner steps `iq-inspect`,
  `iq-rework`, `iq-check` in `lrtx/runner.py` (choices, dispatch, reply files, continue-check support); tests.
- [X] T008 [US1] Graph: `workflow/builder.py` inserts `swe1_iq_inspect -> swe1_iq_check -> swe1_iq_rework` between
  `swe1_author` and `swe1_author_gate` when two-phase is on; continuation wraps both; `serve_swaps` classifies the new
  steps; max_visits = CONTINUATION_MAX_VISITS; re-record the golden after checking the diff is only the insertion;
  tests (edges, model per node, off-switch keeps the old graph byte-identical).
- [X] T009 [US1] Switch: `structured.two_phase_inspection` (default on for SWE.1, code-side pin for the live trial
  profile) carried from profile -> workorder structured block -> builder; test.

## Phase 4: User Story 2 - set inspection with SQ (P1)

- [X] T010 [US2] `review.py`: SQ-01..10 items after SWE1-01..06 with the existing packet/verdict machinery, plus
  `phase1/summary.json` carried findings as a source; recorded as non-gating items; tests.
- [X] T011 [US2] Routing: actionable SQ findings and phase-1 carried findings reach the SWE1 item they belong to
  (`review.SQ_ITEMS`); a holding finding fails that item -> existing rework; gate decision stays SWE1-01..08; tests
  (route, recorded-only severities, carried -> SWE1-02, resume, unchanged without two-phase).

## Phase 5: User Story 3 - evidence (P2)

- [X] T012 [US3] `.forge-run/lrtx/SWE.1/quality-report.md` + summary JSON (per requirement rounds/final/open findings,
  per item verdict); no prompts or reasoning; test.

## Phase 6: Polish and rollout

- [X] T013 Regression: full suite on the branch vs its base (`de42bc29`), design check; record results.
- [ ] T014 CRE: register the change (CHANGE gate) and merge into `feat/owner-lane-campaign-v21-20261107` (merge
  commit); deployer gates and deploys.
- [ ] T015 Native acceptance: WWDG SWE.1 order evidence (phase1 summary, swaps per round, quality report, gate
  verdict); record in `specs/018-swe1-two-phase-inspection/implementation-report.md`; tick only with evidence.

## Dependencies

T001 -> T002 -> T003 -> (T004 -> T005) & T006 -> T007 -> T008 -> T009; T010 -> T011 (after T005 for the summary);
T012 after T005/T010; T013 after all code tasks; T014 -> T015.
Parallel: T004 and T003; T010 with T006-T008 (different files).

## Evidence (2026-11-09)

T001-T012: `tests/test_f018_quality_checklist.py` (2), `tests/test_f018_phase1.py` (9), `tests/test_f018_phase2.py` (6)
pass on `d87326fc`; they import modules and behaviour that do not exist on the base `de42bc29`.
T013: full suite `factory/python/tests` on the branch (536 failing/erroring, all environment-bound on this host) vs a
clean base worktree of `de42bc29` with the same private inputs and venv: every one of the 49 tests that failed only in
the first branch-vs-old-clone comparison fails identically on the clean base (logs `/mnt/data/forge-c/f018-eval/`);
no new failure. Design check `tests/spec/validate_design.py`: PASS (14 static tests). T014-T015 open.
