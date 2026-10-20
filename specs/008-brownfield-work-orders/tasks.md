# Tasks: Brownfield Work Orders

**Input**: Design documents from `specs/008-brownfield-work-orders/` (spec.md, plan.md, research.md, data-model.md,
contracts/, quickstart.md)

**Tests**: required. The constitution (II) and CLAUDE.md say a task is complete only with verifiable test
evidence, so every story has its tests.

**Completion rule**: tick a box only after the named test or check has run and passed, with the evidence path
recorded. A task that could not run is recorded NOT_RUN with the reason, never ticked.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: the user story (US1–US6) a task belongs to
- Paths are relative to the repository root.

## Phase 1: Setup

- [X] BF-T001 Create the package `factory/python/forge_factory/brownfield/__init__.py`. It provides `is_brownfield(manifest)`, `code_mode(manifest)` and `delivered_paths(manifest)`, which return greenfield defaults (False / None / []) for manifests without `delivery` (FR-019).
- [X] BF-T002 [P] Add a contract validator in `factory/python/forge_factory/brownfield/delivery.py` that validates a delivery block against `specs/008-brownfield-work-orders/contracts/brownfield-workorder.schema.json`, plus a test in `factory/python/tests/test_brownfield_intake.py`.

## Phase 2: Foundational (blocking for all stories)

- [X] BF-T003 Implement the C function/macro index in `factory/python/forge_factory/brownfield/scope.py`: find definitions of functions, `static inline`/`__STATIC_INLINE` functions and function-like macros, with file and line. Comments and preprocessor-disabled code are ignored. Test it on the r170 LL header and on fixture snippets in the CMSIS style.
- [X] BF-T004 Implement the register-access extraction in `factory/python/forge_factory/brownfield/scope.py` (`register_effects(function_body, style)`):
  - forge style: `ll_rcc_regs[LL_RCC_<REG>_OFFSET / 4U]` with `|=`, `&= ~` and `=`;
  - CMSIS style: `WRITE_REG/SET_BIT/CLEAR_BIT/MODIFY_REG/READ_BIT(RCC->X, M)` and `RCC->X op= M`.

  Set/clear alias registers are mapped to their base register and bit. Test it with fixture functions.
- [X] BF-T005 Write fixtures in `factory/python/tests/brownfield_fixtures.py`: a delivery directory built from the r170 LL header (committed copy under `tests/fixtures/brownfield/rcc_ll_r170/`), a delivery spec builder, and mutators for the five seeded mismatch kinds.

## Phase 3: User Story 1 — Intake (P1) 🎯 MVP

**Goal**: a brownfield work order is validated, fingerprinted, scoped and build-checked before any agent runs; the delivery stays outside the workspace.

**Independent Test**: `prepare()` on example 0008a gives `intake.json` ACCEPTED with 16 functions and fingerprints, and no `software/` files in the workspace.

- [X] BF-T006 [US1] Implement intake in `factory/python/forge_factory/brownfield/delivery.py`:
  - resolve `source` (directory or archive);
  - copy `files` and `dependencies` to the content-addressed store `state/workorders/<wo>/delivered/`, read-only;
  - fingerprint every file;
  - resolve the scope (BF-T003);
  - refuse a missing licence/origin, a FIX_ALLOWED + no-modification combination, a missing scope function and a path escape;
  - run the build check (host clang `-fsyntax-only` per delivered `.c`/`.h` in a scratch dir, with the delivery's defines and dependency includes);
  - write `intake.json` and `scope.json`.
- [X] BF-T007 [US1] Hook intake into `factory/python/forge_factory/workorder.py` `prepare()`:
  - when the spec has `delivery`, record `delivery`, `code_mode`, `delivered` and `scope_resolution` in the manifest;
  - raise `ValueError("DELIVERY_BLOCKED:...")` (work order BLOCKED before any agent) when intake fails;
  - add `--intake-only` to the CLI;
  - make `resume_from` refuse a delivered-fingerprint mismatch.
- [X] BF-T008 [P] [US1] Create `examples/0008a-rcc-ll-delivered/`: `workorder.json` (copy of 0002a with a `delivery` block, FROZEN, the 16 LL functions) and `upstream/`. Point the delivery source at the committed fixture copy of the r170 LL code.
- [X] BF-T009 [US1] Tests in `factory/python/tests/test_brownfield_intake.py`: ACCEPTED intake for 0008a; each refusal (missing function, missing licence, missing origin, FIX_ALLOWED with no modification, build failure, path escape); excluded-function listing; no delivered file inside the workspace after prepare; greenfield prepare unchanged (manifest has no `delivery`).

## Phase 4: User Story 2 — Independent requirements, traced to the code (P1)

**Goal**: SWE.1 is written without the code; the code enters only after SWE.1 is frozen; conformance findings are computed.

**Independent Test**: the delivery_inject step refuses to run before SWE.1 PASS; after injection, `injection.json` names the frozen SWE.1 baseline; the five seeded mismatches each give the right finding.

- [X] BF-T010 [US2] Implement `factory/python/forge_factory/brownfield/inject.py` (`inject(ws)`):
  - require the SWE.1 inspection gate PASS and a frozen SWE.1 baseline;
  - re-hash the store;
  - write the files 0444 into the workspace (code and `inputs/vendor/include/` dependencies);
  - commit;
  - write `injection.json`;
  - log a gate-log row `step: delivery_inject`.
- [X] BF-T011 [US2] Add the `delivery_inject` deterministic node to `factory/python/forge_factory/workflow/builder.py`, between `swe1_inspect_gate` PASS and the SWE.2 entry, for brownfield manifests only. Add the CLI step (`python -m forge_factory.inspection.gate --step delivery_inject`) in `inspection/gate.py`.
- [X] BF-T012 [US2] Read deny in `factory/python/forge_factory/policy/authz.py`: in brownfield manifests, `swe1-author` (and the SWE.1 triage node) may not read the delivered paths or `.forge-run/delivery/**`. Filter grep/glob/list results for denied paths in `factory/python/forge_factory/acp/gate.py`.
- [X] BF-T013 [US2] Implement conformance in `factory/python/forge_factory/brownfield/conformance.py`:
  - inputs: the SWE.2 allocation (SWR → functions), the SWE.1 `register_effects.json` and the delivered code;
  - finding kinds: `NO_CODE`, `NO_REQUIREMENT` and `CONTRADICTION` (register effects differ; cites the RM reference from the effects file);
  - write `.forge-run/delivery/conformance.json`.

  Run it at the SWE.2 author gate and at SWE.3 verify (brownfield only).
- [X] BF-T014 [US2] Tests in `factory/python/tests/test_brownfield_conformance.py`:
  - the five seeded mismatch kinds (wrong mask, missing function, extra function, wrong register, overwritten unrelated bit), each with exactly one expected finding;
  - an unmodified delivery gives no findings;
  - inject refuses before SWE.1 PASS and records the baseline after it;
  - SWE.1 read deny, including grep root filtering.

## Phase 5: User Story 3 — Remaining work products for FROZEN code (P1)

**Goal**: SWE.2–SWE.6 and the package around unchanged delivered code.

**Independent Test**: on a prepared 0008a workspace with injected code, the brownfield SWE.3 checks pass on a correct trace map and fail on a wrong one; a write to delivered code is refused; a CODE defect is escalated; the package carries the delivery record.

- [X] BF-T015 [US3] Protection in `factory/python/forge_factory/policy/authz.py`: delivered paths are protected for every role in FROZEN mode, and the refusal is logged with code `DELIVERED_CODE_FROZEN`.
- [X] BF-T016 [US3] Implement `factory/python/forge_factory/brownfield/verify.py` (`verify_delivery(ws, step)`): compare the delivered fingerprints, write `verification-<step>.json`, and return MISMATCH issues. Call it from SWE.3 verify, at the start of SWE.4, and from `release/finalize.py`.
- [X] BF-T017 [US3] Implement the code trace map in `factory/python/forge_factory/brownfield/trace.py`: `seed(ws)`, which writes `workproducts/SWE.3/code_trace_map.seed.json` with the scope functions, files and fingerprints, and `check(ws)`, which validates the contract rules from data-model.md.
- [X] BF-T018 [US3] Brownfield hooks in the inspection code:
  - `inspection/swtrace.py`: code trace from the trace map;
  - `inspection/implementation.py`: scope functions exist and fingerprints match;
  - `inspection/regmap.py`: no generation, check-only;
  - `inspection/engine.py`: select checklist `v0.4-brownfield` for brownfield manifests.
- [X] BF-T019 [US3] Add `factory/checklists/v0.4-brownfield/` (protected path → owner-decision commit with OD record): a copy of v0.4 with the SWE.3 items remapped as in research R8.
- [X] BF-T020 [US3] Brownfield SWE.3 chain in `factory/python/forge_factory/workflow/builder.py`: drop regmap and the LL/HAL authors; `delivery_check` → `swe3_author` (recovered design) → verify; FIX_ALLOWED keeps `swe3_fix_author`. Brownfield prompt variants for SWE.2/SWE.3 in `workflow/prompts.py`: describe the delivered code, the trace map, no code edits. SKILL.md brownfield sections for the swe2/swe3 authors, re-pinned in `config/factory/skills.lock.json`.
- [X] BF-T021 [US3] FROZEN defect routing in `factory/python/forge_factory/inspection/defects.py`:
  - CODE defects (filed and auto) against delivered code become `ESCALATED` with `target_kind: DELIVERED_CODE`, with no rework loop;
  - the owner disposition settles them;
  - `gaps()` lists them.
- [X] BF-T022 [US3] Packaging in `factory/python/forge_factory/release/finalize.py`:
  - `configuration/delivery.json` (origin, licence, mode, fingerprints, scope, excluded count);
  - conformance findings and delivery verification in `known_limitations.md`;
  - OPEN findings and MISMATCH are gaps.
- [X] BF-T023 [US3] Tests in `factory/python/tests/test_brownfield_frozen.py`:
  - protection refusal;
  - verify UNCHANGED and MISMATCH;
  - trace map pass and fail cases;
  - brownfield checklist selection;
  - the SWE.3 chain contains no code generator;
  - FROZEN CODE-defect escalation and disposition;
  - package delivery record and gaps;
  - greenfield chain and checklists unchanged.

## Phase 6: User Story 4 — FIX_ALLOWED (P2)

**Goal**: delivered code changes only to fix a filed defect, with a change report.

**Independent Test**: with a seeded HAL defect, an IN_FIX CODE defect opens the write window; the change report links the diff to the defect; untouched files stay identical; out-of-scope edits are refused.

- [X] BF-T024 [US4] FIX_ALLOWED write window in `factory/python/forge_factory/policy/authz.py`: `swe3-author` may write a delivered in-scope file only while a CODE defect is `IN_FIX`. Otherwise the write is refused with `DELIVERED_CODE_NO_DEFECT`.
- [X] BF-T025 [US4] Change report in `factory/python/forge_factory/brownfield/verify.py`: each changed file maps to a FIXED/VERIFIED CODE defect, with the unified diff against the store and the original and corrected SHA-256. An unmapped change is MISMATCH.
- [X] BF-T026 [P] [US4] Create `examples/0008b-rcc-hal-delivered/`: the r164 HAL with a seeded rollback defect (committed fixture copy and the seed's description), FIX_ALLOWED, on the provided LL.
- [X] BF-T027 [US4] Tests in `factory/python/tests/test_brownfield_fix.py`: write refused without IN_FIX; allowed during IN_FIX; change report content; out-of-scope file refused; unmapped change is MISMATCH and a gap.

## Phase 7: User Story 5 — Safety drafts (P2)

- [X] BF-T028 [US5] Add the `safety_draft` author node (brownfield, safety-scoped only), after SWE.6 and before the release manager. Its deterministic gate checks:
  - the draft marker;
  - `claim_text_findings` clean;
  - the delivered fingerprints cited;
  - files written only under `safety/drafts/`.

  Uses the `swe2-author` role with a new write prefix `safety/drafts/` (brownfield only).
- [X] BF-T029 [US5] Tests in `factory/python/tests/test_brownfield_safety_drafts.py`: the gate accepts a correct draft and rejects a missing marker, a compliance claim and a write outside `safety/drafts/`. Drafts never satisfy the signed-document register.

## Phase 8: Validation runs

- [X] BF-T030 Live FROZEN run of 0008a (Codex authors, Claude inspectors). Record SC-001, SC-004 and SC-007 evidence in `evidence/v0.4/runs/BF-T030/`.
- [X] BF-T031 Live FIX_ALLOWED run of 0008b. Record SC-003 evidence in `evidence/v0.4/runs/BF-T031/`.

## Phase 9: User Story 6 — ST pilot (P3)

- [X] BF-T032 [US6] Download and fingerprint the vendor dependencies (cmsis-device-n6 v1.4.0, CMSIS 6 core v6.x headers) with provenance, as for the HAL driver. Write the HAL configuration (RCC only) and `stm32_assert.h` from the templates as declared inputs.
- [ ] BF-T033 [US6] CMSIS adapter in `factory/python/forge_factory/brownfield/cmsis.py`, used by the build/tests/sim servers for `build.style: cmsis`:
  - a host device shim (RCC in RAM) and a tick stub;
  - manifest include dirs and defines;
  - warnings recorded instead of `-Werror` for delivered files.
- [ ] BF-T034 [US6] Simulator: RCC window 8 KB, and CSR/CCR plus AHB1ENSR/ENCR/RSTSR/RSTCR set/clear semantics in `factory/sim/stm32n6/rcc_model.py` (greenfield behaviour unchanged). Robot policy accepts `RCC_<REG>_<FIELD>` tokens.
- [X] BF-T035 [US6] Create `examples/0008c-st-cube-rcc/` (FROZEN, LL style cmsis, 11 scope functions) and tests for its intake.
- [X] BF-T036 [US6] Live pilot run. Record SC-006 evidence in `evidence/v0.4/runs/BF-T036/`.

## Phase 10: Polish and release

- [X] BF-T037 Documentation: `docs/BROWNFIELD-WORK-ORDERS.md` (how to bring a delivery, modes, what the package contains, limits).
- [X] BF-T038 Full regression (`assurance.regress --full`) on the final tree (SC-008).
- [X] BF-T039 CRE CHANGE promotion (baseline main + owner decisions; candidate + factory changes), with the oracle commit.
- [ ] BF-T040 PR with evidence; merge only after the owner accepts.

## Dependencies

- Setup and Foundational (T001–T005) come before everything else.
- US1 (T006–T009) comes before US2 and US3.
- US2 (T010–T014) comes before US3's conformance use.
- US3 (T015–T023) comes before US4, US5, the validation runs and US6.
- The ST pilot (T032–T036) depends on US3. Of US4, it needs only the shared verify step.

## Implementation strategy

MVP = US1 + US2 + US3 on the factory's own LL code (0008a), validated by a live FROZEN run. Then FIX_ALLOWED,
safety drafts, the ST pilot, and release.

## Status and evidence (2026-10-20, overnight session)

**Ticked tasks:**
- **Tests:** `factory/python/tests/test_brownfield_{intake,conformance,frozen,fix,hal,pilot}.py`. All pass (48), and
  the full factory suite passes.
- **Live runs:**
  - `evidence/v0.4/runs/BF-T030` (b001, 0008a FROZEN): SWE.1–SWE.6 PASS, code injected after the frozen SWE.1,
    0 conformance findings, about 31 min. It also found a finalize defect, now fixed (see `latest.json`).
  - `evidence/v0.4/runs/BF-T031` (b002, 0008b FIX_ALLOWED): BLOCKED at SWE.3. It found three factory defects
    (defect routing for delivered code, provided-file resolution in conformance, static no-write cases), all
    fixed. The re-run is b004.

**Not done or partial (not ticked):**
- **BF-T018 and BF-T019, done 2026-10-20** (owner decision OD-2026-10-20-02, CRE `pd-5c45faab3e615e227181`):
  - `factory/checklists/v0.4-brownfield/SWE.3.yaml`;
  - the engine selects it for delivery manifests;
  - the delivered-code checks live in `brownfield/checks.py` rather than in `implementation.py`/`regmap.py`, so the
    greenfield modules stay unchanged;
  - tests: `test_brownfield_checklist.py`. On the ST pilot inputs, 14 CMSIS probes match RM0486, and a seeded vendor
    mismatch is found.
- **BF-T028, deviation:** the safety drafts are generated deterministically from the run's records (no model node),
  which is cheaper and cannot invent content. The spec's "AI-drafted" wording is met as "factory-drafted".
- **BF-T031:** pending the b004 result.
- **BF-T033, partial:**
  - done: the CMSIS build check (arm-none-eabi-gcc, secure), the contract compile against the vendor headers,
    and CMSIS register-effect extraction;
  - not done: the host device shim and tick stub for tests.
- **BF-T034, NOT_DONE:** Renode set/clear registers and the 8 KB window.
- **BF-T036:** pending the pilot run.
- **BF-T038–BF-T040:** pending the final tree.
