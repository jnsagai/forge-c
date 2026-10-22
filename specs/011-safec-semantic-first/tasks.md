# Implementation tasks — Feature 011

**Status:** ALL TASKS PENDING. No checkbox is satisfied by authoring this plan. Claude Code is the implementation engineer; no cloud LLM may be a dependency of local factory execution.

**Sources:** `spec.md`, `plan.md`, `research.md`, `data-model.md`, `contracts/*.schema.json`, `acceptance-tests.md`; constitution and existing feature 010 baselines.

Each closed task MUST record test command, exit, relevant SHA/digest, limitations and evidence artifact. A genuine negative result is BLOCKED/NOT_PASS, never checkbox complete on narrative assertion.

## M0 — Establish reproducible, non-destructive base (F011-AT-001..005)

- [ ] **F011-T001 [US1]** Audit Forge-C `main`/Feature 010 and pinned Claude/Codex baseline; record actual current Git state, host deployment/profiles and existing archive preservation in `specs/011-safec-semantic-first/validation.md` before editing runtime.
- [ ] **F011-T002 [US1]** Create independent SafeC feature branch from observed private main, record actual SHA and confirm licensing/access. Do not add private contents to public Forge-C.
- [ ] **F011-T003 [P] [US1]** Capture `scripts/lrtx_compat_check.sh` plus ACP/default and v1 frozen graph fixtures, all current safety policy hashes and representative live/package baselines; record stdout/stderr/versions.
- [ ] **F011-T004 [P] [US1]** On the owner Linux host, probe pinned SafeC Rust build/CLI and installed formal backends; validate real binary SHA, paths, memory/CPU constraints and current capability vs experimental/unavailable. Record BLOCKED if host/tool inaccessible.
- [ ] **F011-T005 [US1]** Implement schema/spec/static validation fixture and public/private provenance leak checks. Validate all documentation references; no installed dependency or new CLI capability may be claimed from prose.

**M0 exit:** baseline safe, source digests recorded, no production changes and observable Linux compatibility. If SafeC Linux does not work, build the pure Rust parser bridge first; formal backend remains UNSUPPORTED.

## M1 — SafeC bridge protocol (F011-AT-006..010)

- [ ] **F011-T006 [US1]** In Forge-C implement `factory/python/forge_factory/safec_bridge/contracts.py` and `client.py` parsing the two frozen JSON schemas and rejecting unknown/oversized/stale/duplicate-key/UTF-8-invalid messages.
- [ ] **F011-T007 [US1]** Implement strict, bounded subprocess invocation, cancellation and resource/result capture; no shell expansion; hash-verified SafeC binary and version handshake.
- [ ] **F011-T008 [US1]** In SafeC private repo implement an explicit versioned bridge CLI command (or a thin separate binary reusing Rust libs) that understands proposed request/result envelopes; it MUST reject unimplemented operations as UNSUPPORTED, not nominal PASS.
- [ ] **F011-T009 [US1]** Add request/result provenance, input snapshot/source/policy digest matching and evidence revalidation; do not accept reported PASS without validating the referenced artifact content and exact property set.
- [ ] **F011-T010 [P] [US1]** Add Forge-C pytest contract/adversarial fixtures in `factory/python/tests/test_safec_bridge.py` (schema errors, stale, forged success, timeout, cancellation, tool identity, privacy). Add corresponding SafeC Rust tests.
- [ ] **F011-T011 [US1]** Provide a narrow, policy-authorized MCP wrapper for any **AI agent** permitted to invoke the bridge; deterministic orchestration may call the CLI directly. Confirm Fabro command node integration does not weaken authorization.

**M1 exit:** F011-AT-006..010 PASS plus no ACP/default behavioral difference.

## M2 — New source-anchored register semantic domain (F011-AT-011..016)

- [ ] **F011-T012 [US2]** Define `register-io-0.1` grammar, scope and canonical representation in private SafeC (new schema/profile, never silent reinterpretation of sampled-latch CSRI); publish only public-safe wire types.
- [ ] **F011-T013 [US2]** Extend RM0486 source/excerpt parsing and provenance binding across existing Forge-C `lrtx/swe1.py` inventory and SafeC domain loader; require exact source authority, sections, pages and explicit missing/ambiguous handling.
- [ ] **F011-T014 [US2]** Implement Rust checked arithmetic for bit positions, widths, logical values, shifts, masks, reserved bits, byte ordering as applicable and field write restrictions; reject implicit truncation.
- [ ] **F011-T015 [US2]** Model supported RO/RW/WO, key sequences and specifically authorized side effects; unknown W1C/RC/self-clearing/timing/access behavior UNSUPPORTED; no assumed safe RMW.
- [ ] **F011-T016 [P] [US2]** Add positive/negative authoritative fixtures for RCC ADC12EN and IWDG KEY/PR/RLR/SR, including 0x20 mask-vs-value error, inverted keys, RO writes, reserved/out-of-scope fields, reset contradiction and semantically unknown rules.
- [ ] **F011-T017 [US2]** Implement cross-register/cross-intent consistency and scope inventory; preserve all uncovered fields and missing owner decisions with source-linked findings.
- [ ] **F011-T018 [US2]** Add Rust -> Forge-C typed validated contract materialization, canonical digests and deterministic reference expected operations; no model-produced numeric fact becomes trusted.
- [ ] **F011-T019 [US2]** Run independent golden/mutation regression on supported semantics in SafeC and Forge-C; record unsupported/unresolved obligations and prohibit promotion if any critical mismatch.

**M2 exit:** F011-AT-011..016 pass without weakening a single existing gate. No assumption that temporal Kind 2 or existing ACSL code verifies an RCC driver.

## M3 — Semantic-first SWE.1 generation (F011-AT-017..018 and 025 author)

- [ ] **F011-T020 [US2]** Introduce **new** `local-rtx-v2` profile/roots/ports/model allowlist, explicit opt-in, same local-only/network-denied gate and model admission as v1; block mixed ACP/cloud.
- [ ] **F011-T021 [US2]** Convert structured SWE.1 register packets to emit bounded source-fact-linked `SemanticIntent` JSON (not mask/field encodings). Keep role SKILL hash, full mandatory context, call budget and checkpoint identity.
- [ ] **F011-T022 [US2]** Render existing SWE.1 workproducts deterministically from verified contract + owner workorder: requirement numbering, EARS, register effects, verification map, trace and open points. Never generate missing source facts or missing safety approval.
- [ ] **F011-T023 [US4]** Implement local delta-based repair and STUCK if identical rejected contract/intent repeats. Preserve all original rework counts and source hash invalidation; measure repairs and calls.
- [ ] **F011-T024 [US2]** Run 3 real SWE.1 author-only frozen trials each on RCC-LL and IWDG-LL and preserve all first-visit, rework and failure evidence before touching inspector routing.

**M3 exit:** unchanged deterministic author gate accepts genuine tested results; no claim that the inspector or SWE.2 is qualified.

## M4 — Independent inspector and model qualification (F011-AT-019..023,030)

- [ ] **F011-T025 [US3]** Define atomic `InspectionClaim` schema, checklist-to-evidence mapping and local frozen-baseline packet construction. Keep author context/intent/outcome hidden from inspector unless it is the frozen inspected artifact.
- [ ] **F011-T026 [US3]** Add deterministic claim checker that validates exact target IDs, source facts, reported missing facts, scope policy and owner PENDING decisions; classify true blocker, contested/unsubstantiated and INCONCLUSIVE without a fuzzy string blacklist.
- [ ] **F011-T027 [US3]** Implement selective reinspection of impacted claims and bounded factual adjudication, preserving all original attempts and full unchanged inspector gate authority.
- [ ] **F011-T028 [P] [US3]** On exact target host, probe distinct local family candidates (e.g. GPT-OSS, GLM) one at a time. Record actual model digest, memory/VRAM, quantization, context, loading/switching, latency and failure behavior. No hardcoded assumed qualification.
- [ ] **F011-T029 [US3]** Run frozen T021 catalog plus new blind independent holdouts; tally on-target, off-target, miss, false rejection and inconclusive by source defect. Refuse inspector promotion if critical misses or known false clean rejections persist.
- [ ] **F011-T030 [US3]** Integrate ONLY evidence-qualified inspector under v2 experimental profile; if none qualifies, leave it NOT_QUALIFIED and stop live end-to-end execution; do not bypass inspector or silently use Claude at runtime.

**M4 exit:** all required source-backed findings are correct on the independent frozen corpus; no false READY and no deceptive scope change. Mere JSON validity is insufficient.

## M5 — SWE.2 then downstream verification (F011-AT-024,026..029)

- [ ] **F011-T031 [US4]** Bind SWE.2 function/parameter/return names and allocation to exact accepted SWE.1 contracts; reject `LL_IWDG_IsActive`/`LL_IWDG_IsEnabled` drift and missing SWR allocation with actionable target.
- [ ] **F011-T032 [US4]** Run 3 fresh real SWE.2 author+inspector visits per RCC/IWDG pilot on frozen genuinely accepted SWE.1, with all existing design/inspection gates unchanged.
- [ ] **F011-T033 [US5]** Extend SafeC C11/ACSL/test lowering only for the newly supported register-io semantic domain; preserve temporal Wheel profile, and treat unsupported proof properties conservatively.
- [ ] **F011-T034 [US5]** Integrate independent requirement-derived oracles and mutations in SWE.3/4/5/6, including inverted key, absent write, vacuous test and false positive. Reuse existing Renode/Robot/gcc/cppcheck tool chain and role policy.
- [ ] **F011-T035 [US5]** Probe bound/assumptions and exact Linux backend (Frama-C/CBMC/Kind 2 if applicable). Never treat old Windows/WSL evidence or bounded BMC as generalized proof.
- [ ] **F011-T036 [US5]** Execute separate progressive end-to-end runs (one phase at a time) and archive exact PASS/FAIL/BLOCKED/NOT_RUN metrics and artifacts. HAL profile may not be claimed local-structured until tested.

## M6 — Regression, evaluation, and offline handoff (F011-AT-031..034)

- [ ] **F011-T037 [US1]** Independently fix the documented shared route-gate extension bug in its own candidate/PR under CRE protection; prove budgets/stuck and ACP/v1 regressions; do not absorb unrelated gate changes into 011.
- [ ] **F011-T038 [US4]** Freeze new unseen experiment cases, scripts, model digests, prompt hashes, comparable baseline and acceptance oracles **before** running any final campaign.
- [ ] **F011-T039 [US4]** If all previous gates pass, run the 30-case local campaign (10 RCC-LL, 10 IWDG-LL, 5 each HAL), publish Wilson or other declared statistical uncertainty, false accepts/rejects and independently measured success cost.
- [ ] **F011-T040 [US1]** Exercise v2-only shutdown and rollback (including interrupted semantic engine), preserve ACP/v1 services/archives, validate original read-only snapshot and protected paths.
- [ ] **F011-T041 [US5]** Create fully reproducible offline review package with independent evidence revalidation, exact hashes, unsupported obligations, incomplete ASIL evidence and no compliance claim; no auto-promotion.
- [ ] **F011-T042 [US1]** Deliver separate cross-repo PRs, diff review, tests, exit codes and residual risk register; every unchecked task remains visibly open; do not merge to main without explicit owner approval.

## Dependencies and implementation rule

`M0 -> M1 -> M2 -> M3 -> M4 -> M5 -> M6`. Only tasks marked [P] with isolated files may execute concurrently. An inspector not qualified at M4 blocks any final end-to-end run. A missing source or backend means a valid non-PASS outcome, not a gate downgrade. Use the exact test matrix in `acceptance-tests.md` and always record model-tool/source hashes and run revisions.
