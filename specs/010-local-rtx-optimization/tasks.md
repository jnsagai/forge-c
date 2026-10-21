# Feature 010 tasks

Status (2026-10-21): P0 and P1 delivered; structured SWE.1-SWE.6 (LL) authors and inspectors implemented and tested
with scripted models; T010 and T012 recorded. Local trials lrtx1-lrtx7 are BLOCKED at SWE.1 (T016 open). lrtx7 froze
SWE.1 on its first visit; the inspector defects it showed are fixed. Still pending: seeded-defect evaluation (T021),
model comparison (T023), the campaign (T024) and the offline review package (T025). A checked task requires its own evidence. A
written specification or passing static check is not a completed local model trial.

## P0 — preservation

- [x] LRTX-T001 Record the existing main SHA and existing RC1/rc4 evidence, preserving the limitations of that evidence. Reference: `baseline.json` and ADR-0013.
- [x] LRTX-T002 Create `baseline/codex-claude-2026-10-21` and `feat/010-local-rtx-optimization` from `86f1f40c030bc721e7e5125a572d69647c4ac041`. Verify remote references before reporting completion.
- [X] LRTX-T003 Capture the actual working host revision, dirty changes, effective configuration and installed tool/model versions; preserve external archives and verify a read-only restore. Run on the owner host 2026-10-21; the backup stays outside the repository. ✅ Evidence: `evidence/v0.4/runs/LRTX-T003/latest.json`
- [X] LRTX-T004 Freeze executable compatibility fixtures for the existing workflow/provider combinations before editing shared runtime paths. ✅ Evidence: `evidence/v0.4/runs/LRTX-T004/latest.json`

## P1 — isolated explicit profile and measurement

- [X] LRTX-T005 Implement versioned explicit local-profile selection; no-selection behavior unchanged; reject conflicting ACP/provider flags before launch. ✅ Evidence: `evidence/v0.4/runs/LRTX-T005/latest.json`
- [X] LRTX-T006 Enforce separate resolved data/state/archive/config/storage roots and service/port identities, including inherited environment and symlink overlap tests. ✅ Evidence: `evidence/v0.4/runs/LRTX-T006/latest.json`
- [X] LRTX-T007 Record effective profile, model digest/quantization, runtime configuration and enforcement status in run provenance without secrets. ✅ Evidence: `evidence/v0.4/runs/LRTX-T007/latest.json`
- [X] LRTX-T008 Enforce local endpoints and absent cloud fallback; prove offline dependency availability and external-network denial on the host. ✅ Evidence: `evidence/v0.4/runs/LRTX-T008/latest.json`
- [X] LRTX-T009 Add single-request admission with bounded waiting, cancellation and queue metrics while preserving safe empty-response retry behavior. ✅ Evidence: `evidence/v0.4/runs/LRTX-T009/latest.json`
- [X] LRTX-T010 Separate queue/load/prefill/decode/tool measurements; capture GPU residency and memory pressure, label unsupported fields UNKNOWN. ✅ Evidence: `evidence/v0.4/runs/LRTX-T010/latest.json` (tests); live records `LRTX-TRIAL/lrtx6|lrtx7/metrics.json` (GPU energy at 100 % sample coverage; wall energy UNKNOWN on this host)

## P2 — SWE.1/SWE.2 coherent tasks

- [X] LRTX-T011 Build versioned source-backed context packets and complete-prompt accounting; no silent truncation; retain output reserve. ✅ Evidence: `evidence/v0.4/runs/LRTX-T011/latest.json`
- [X] LRTX-T012 Add typed intermediate contracts and runtime capability probes for structured responses. ✅ Evidence: `evidence/v0.4/runs/LRTX-T012/latest.json` (tests); live probe `LRTX-T012/capabilities-qwen3-coder-30b.json` (json_schema honoured)
- [X] LRTX-T013 Implement requirement-group, register-effect and verification-mapping tasks with a complete source coverage inventory. ✅ Evidence: `evidence/v0.4/runs/LRTX-T013/latest.json`
- [X] LRTX-T014 Implement allocation/interface tasks including resource and reset invariants, stable IDs and existing final artifact formats. ✅ Evidence: `evidence/v0.4/runs/LRTX-T014/latest.json`
- [X] LRTX-T015 Render repetitive tables/diagrams deterministically; retain semantic author decisions and complete phase-level consistency gates. ✅ Evidence: `evidence/v0.4/runs/LRTX-T015/latest.json`
- [ ] LRTX-T016 Replay observed RCC/IWDG rejections and perform fresh local SWE.1/SWE.2 trials; distinguish fixed factory defects from model quality.

## P3 — localized repair and inspection

- [X] LRTX-T017 Add validated checkpoints and dependency invalidation; local repair preserves unaffected content. ✅ Evidence: `evidence/v0.4/runs/LRTX-T017/latest.json`
- [X] LRTX-T018 Route missing inspection directly to inspection only when the current frozen baseline remains valid. ✅ Evidence: `evidence/v0.4/runs/LRTX-T018/latest.json`
- [X] LRTX-T019 Split coherent inspection criteria with full primary evidence and independent contexts; aggregate only complete matching-baseline verdicts. ✅ Evidence: `evidence/v0.4/runs/LRTX-T019/latest.json`
- [X] LRTX-T020 Prove shared phase accounting and existing stuck/rework limits across subtasks; no reset through task decomposition. ✅ Evidence: `evidence/v0.4/runs/LRTX-T020/latest.json`
- [ ] LRTX-T021 Evaluate seeded semantic defects and cross-artifact contradictions with independent frozen holdouts.

## P4/P5 — full process and qualification

- [X] LRTX-T022 Extend existing SWE.3-SWE.6 scaffolds and tasks without weakening complete phase gates or deriving test oracles from generated code. ✅ Evidence: `evidence/v0.4/runs/LRTX-T022/latest.json` (LL work orders, scripted models against the real tools, Renode, Robot and the unchanged gates; HAL keeps the agent nodes; no local-model run has reached SWE.3 yet)
- [ ] LRTX-T023 Compare smaller models per task with 30B, including switching and retry costs; preserve inspector qualification as a separate decision.
- [ ] LRTX-T024 Execute the frozen 30-case local-only campaign and publish full provenance, quality/detection results, duration, tokens, resource use and uncertainty.
- [ ] LRTX-T025 Verify the existing deployment remains usable and complete host rollback/isolation evidence; package results for offline review. No automatic promotion.

## Initial validation record

See `validation.md`. Source/reference verification and static design validation are distinct from host runtime
verification. Preserve NOT_RUN for model inference, deployed-service checks, archive restoration and all optimized
workflow behavior until those actions actually occur.
