# Tasks: SWE.1 output-first requirements pipeline

All tasks are initially unchecked. Complete one milestone at a time. First implementation delivery: **M0–M1 only**. Mark a task complete only with reproducible evidence; native execution remains NOT_RUN when the host is unavailable.

## M0 — Reconcile baseline and make evidence trustworthy

- [ ] T001 [US1] Inspect actual checkout, instructions, current SWE.1 path and selected author/inspector profiles; record base revision, existing implementation reuse and drift in this feature's implementation report. Do not reset the active checkout to the documentation branch.
- [ ] T002 [US1] Freeze a synthetic/local-private evaluation manifest following validation.md; identify at least 12 tasks, three behavior families, two driver families, a held-out case and independent expected properties.
- [ ] T003 [US2] Add failing regression cases for duplicate-prefix normalization, mistaken scope deletion and empty-array repair in `factory/python/tests/test_lrtx_swe1.py` (or its current equivalent).
- [ ] T004 [US2] Repair `lrtx/swe1.py` identifier classification and add atomic coverage-preservation guards; keep ambiguous identifiers unresolved.
- [ ] T005 [US2] Implement/reuse append-only call lifecycle events in `lrtx/structured.py`, gateway accounting and a cohesive ledger helper. Test failed, superseded, duplicate, cancelled and interrupted calls; preserve unknown usage.
- [ ] T006 [US2] Derive `lrtx/runmetrics.py` summaries from the ledger and verify exact reconciliation using synthetic fixtures, with separate cache/reasoning semantics and no raw reasoning capture.
- [ ] T007 [US1] Run focused and required legacy/design checks; record effective budget layers and baseline measurements before changing generation behavior.

## M1 — Probe actual author mode and deliver the first experiment

- [ ] T008 [US1] Extend/reuse `lrtx/modelprobe.py` and `lrtx/profile.py` to record role-specific model digest, backend/template/gateway identity and capability status keyed by the full serving identity.
- [ ] T009 [US1] Add explicit backend-neutral `off`/`bounded`/`baseline` policy mapping in the gateway/structured path; test unsupported or ignored settings and preserve existing defaults outside the experimental profile.
- [ ] T010 [US1] Verify answer/total-generation limits, timeout, stream cancellation and orphan-inference handling in gateway tests; document capability limitations without pretending prompt instructions enforce limits.
- [ ] T011 [US1] Implement/reuse a bounded paired experiment in `lrtx/modelcmp.py`; keep inspector and prompt/check settings fixed, include repeats, cold/warm effects and full repair cost.
- [ ] T012 [US1] Run native identity and capability probes on Omniverse through the actual gateway. If inaccessible, record NATIVE_NOT_RUN and leave this task unchecked.
- [ ] T013 [US1] Run native baseline-versus-author-off/bounded trials and assess validation.md gates. Do not disable inspector thinking in this experiment.
- [ ] T014 [US1] Deliver the M0–M1 report, recommended candidate/retained baseline, supported controls, exact rerun instructions and unresolved items. Do not launch a long campaign or promote production settings.

**Checkpoint:** first useful delivery. Continue below as the next incremental implementation scope, after the report establishes what was actually measured.

## M2 — Generic contract and deterministic requirement outputs

- [ ] T015 [US3] Implement versioned minimal contract/patch schemas from data-model.md in the existing schema mechanism; expose only applicable, undecided fields to the author.
- [ ] T016 [US3] Implement/reuse deterministic EARS/verification rendering and factory-owned IDs in `lrtx/swe1_contract.py` or existing equivalents, with no model calls for wording and no mandatory SafeC activation.
- [ ] T017 [US3] Add semantic-preservation fixtures for configuration, waiting and asynchronous behavior; test unresolved/not-applicable concerns, parameterized domains and unsupported renderer patterns.
- [ ] T018 [US3] Add bounded evidence selection and compact author packets in `lrtx/swe1.py`/`structured.py`; preserve necessary conditions and source provenance and reject rather than truncate oversized evidence.
- [ ] T019 [US3] Adapt contracts to existing SWE.1 requirements/trace formats and a versioned experimental profile. Test phase scope, stable IDs, existing selected-profile compatibility and planned-versus-executed verification labels.
- [ ] T020 [US3] Update applicable SWE.1 role instructions and record their hashes; keep full reasoning/planning out of responses and retained logs. Run focused/design regressions and report M2 evidence.

## M3 — Behavioral coverage and semantic review

- [ ] T021 [US4] Implement/reuse a versioned obligation inventory in `lrtx/swe1_coverage.py`; independently review scope coverage before drafting and track justified exclusions separately from unresolved gaps.
- [ ] T022 [US4] Check symbolic domains, required behaviors/values/states, exceptions and cross-contract shared decisions; prove that name coverage alone cannot pass.
- [ ] T023 [US4] Integrate compact evidence-backed inspector findings into existing review/reinspection paths, preserving independent role context and structure-versus-semantics status.
- [ ] T024 [US4] Enforce frozen/new/controlled-modification contract policy; add regressions for invented invalid-input behavior, false source support and implementation disagreements.
- [ ] T025 [US4] Execute the frozen seeded-defect/known-good suite. Evaluate any inspector-mode change independently, retain its baseline if detection quality regresses, and report M3 evidence.

## M4 — Bounded recovery, resume and complete SWE.1 experiment

- [ ] T026 [US5] Implement stable finding classification and deterministic routing in existing recovery logic or `lrtx/swe1_recovery.py`; permit only recorded changed-strategy retries within effective budgets.
- [ ] T027 [US5] Implement atomic base-hash patches, coverage regression checks and last-good-candidate retention; test concurrent/stale/irrelevant patches.
- [ ] T028 [US5] Bind checkpoints to source/scope/shared-decision/schema/validator/review dependencies and test selective invalidation, crash recovery and continuation without budget reset.
- [ ] T029 [US5] Report meaningful progress and continue independent obligations while blocked tasks remain explicit; prevent phase acceptance with mandatory gaps.
- [ ] T030 [US5] Run a complete SWE.1-only work order and held-out evaluation under the selected experimental profile; compare to a matched baseline using the frozen quality and cost protocol.
- [ ] T031 [US5] Run applicable legacy/design/integration checks, document migration/rollback and deliver the full feature evidence report. Keep production promotion and later SWE phases outside this implementation scope.

## Traceability

| Requirements | Tasks |
|---|---|
| FR-001, FR-024 | T001, T002, T019, T030, T031 |
| FR-002–FR-005 | T008–T014, T025 |
| FR-006–FR-008 | T005–T011, T020, T026, T028 |
| FR-009–FR-012 | T015–T017, T019, T024 |
| FR-013 | T003, T004 |
| FR-014, FR-015 | T002, T018, T021, T022 |
| FR-016, FR-019, FR-020 | T004, T026–T029 |
| FR-017, FR-018, FR-021 | T023–T025 |
| FR-022, FR-023 | T014, T019, T025, T030, T031 |

Do not check off design intent as implementation. No fixed task requires a specific model to pass; honest unsupported/failed results complete an experiment report, but do not satisfy native competence or promotion criteria.
