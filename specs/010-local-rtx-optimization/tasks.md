# Feature 010 tasks

Status: source separation delivered; optimization and host qualification pending. A checked task requires its
own evidence. A written specification or passing static check is not a completed local model trial.

## P0 — preservation

- [x] LRTX-T001 Record the existing main SHA and existing RC1/rc4 evidence, preserving the limitations of that evidence. Reference: `baseline.json` and ADR-0013.
- [x] LRTX-T002 Create `baseline/codex-claude-2026-10-21` and `feat/010-local-rtx-optimization` from `86f1f40c030bc721e7e5125a572d69647c4ac041`. Verify remote references before reporting completion.
- [ ] LRTX-T003 Capture the actual working host revision, dirty changes, effective configuration and installed tool/model versions; preserve external archives and verify a read-only restore. NOT_RUN: owner host unavailable here.
- [ ] LRTX-T004 Freeze executable compatibility fixtures for the existing workflow/provider combinations before editing shared runtime paths.

## P1 — isolated explicit profile and measurement

- [ ] LRTX-T005 Implement versioned explicit local-profile selection; no-selection behavior unchanged; reject conflicting ACP/provider flags before launch.
- [ ] LRTX-T006 Enforce separate resolved data/state/archive/config/storage roots and service/port identities, including inherited environment and symlink overlap tests.
- [ ] LRTX-T007 Record effective profile, model digest/quantization, runtime configuration and enforcement status in run provenance without secrets.
- [ ] LRTX-T008 Enforce local endpoints and absent cloud fallback; prove offline dependency availability and external-network denial on the host.
- [ ] LRTX-T009 Add single-request admission with bounded waiting, cancellation and queue metrics while preserving safe empty-response retry behavior.
- [ ] LRTX-T010 Separate queue/load/prefill/decode/tool measurements; capture GPU residency and memory pressure, label unsupported fields UNKNOWN.

## P2 — SWE.1/SWE.2 coherent tasks

- [ ] LRTX-T011 Build versioned source-backed context packets and complete-prompt accounting; no silent truncation; retain output reserve.
- [ ] LRTX-T012 Add typed intermediate contracts and runtime capability probes for structured responses.
- [ ] LRTX-T013 Implement requirement-group, register-effect and verification-mapping tasks with a complete source coverage inventory.
- [ ] LRTX-T014 Implement allocation/interface tasks including resource and reset invariants, stable IDs and existing final artifact formats.
- [ ] LRTX-T015 Render repetitive tables/diagrams deterministically; retain semantic author decisions and complete phase-level consistency gates.
- [ ] LRTX-T016 Replay observed RCC/IWDG rejections and perform fresh local SWE.1/SWE.2 trials; distinguish fixed factory defects from model quality.

## P3 — localized repair and inspection

- [ ] LRTX-T017 Add validated checkpoints and dependency invalidation; local repair preserves unaffected content.
- [ ] LRTX-T018 Route missing inspection directly to inspection only when the current frozen baseline remains valid.
- [ ] LRTX-T019 Split coherent inspection criteria with full primary evidence and independent contexts; aggregate only complete matching-baseline verdicts.
- [ ] LRTX-T020 Prove shared phase accounting and existing stuck/rework limits across subtasks; no reset through task decomposition.
- [ ] LRTX-T021 Evaluate seeded semantic defects and cross-artifact contradictions with independent frozen holdouts.

## P4/P5 — full process and qualification

- [ ] LRTX-T022 Extend existing SWE.3-SWE.6 scaffolds and tasks without weakening complete phase gates or deriving test oracles from generated code.
- [ ] LRTX-T023 Compare smaller models per task with 30B, including switching and retry costs; preserve inspector qualification as a separate decision.
- [ ] LRTX-T024 Execute the frozen 30-case local-only campaign and publish full provenance, quality/detection results, duration, tokens, resource use and uncertainty.
- [ ] LRTX-T025 Verify the existing deployment remains usable and complete host rollback/isolation evidence; package results for offline review. No automatic promotion.

## Initial validation record

See `validation.md`. Source/reference verification and static design validation are distinct from host runtime
verification. Preserve NOT_RUN for model inference, deployed-service checks, archive restoration and all optimized
workflow behavior until those actions actually occur.
