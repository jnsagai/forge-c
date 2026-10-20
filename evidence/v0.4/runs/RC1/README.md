# Regression campaign rc1 (2026-10-20, owner "propose something and do it")

All seven example work orders on main e66de22 (all PRs through #25 merged), one frozen worktree, Codex authors, Claude
inspectors, no DeepSeek. Launched 16:31Z, last package 20:22Z.

| Work order | Result |
|---|---|
| WO-0002A-STM32N6-RCC-LL-rc1 | READY_FOR_OFFLINE_REVIEW, 0 gaps |
| WO-0002B-STM32N6-RCC-HAL-rc1 | READY_FOR_OFFLINE_REVIEW, 0 gaps |
| WO-0008A-STM32N6-RCC-LL-rc1 | SWE.1-SWE.6 PASS; BLOCKED on escalated DEF-003 (FACTORY): RCC model returned the target register on reads of write-only set/clear registers - regression from PR #24 -> CAPA-065 (PR #28, merged); rerun rc1b pending |
| WO-0008B-STM32N6-RCC-HAL-rc1 | READY_FOR_OFFLINE_REVIEW, 0 gaps |
| WO-0008C-ST-RCC-LL-rc1 | READY_FOR_OFFLINE_REVIEW, 0 gaps |
| WO-0009A-STM32N6-IWDG-LL-rc1 | READY_FOR_OFFLINE_REVIEW, 0 gaps |
| WO-0009B-STM32N6-IWDG-HAL-rc1 | BLOCKED at SWE.4 (rework budget): UT:UNKNOWN_SPEC_REF (SWR/SWU ids in @verifies, recurring in h004/h005 -> CAPA-066), a valid inspection finding (delayed flag clearing, varied ticks - fixed by the authors as DEF-001/002), then an AGENT_OUTPUT_PROSE final reply (model variance, not a factory defect) |

Result: 5/7 READY on the first pass; 2 factory defects found and fixed (CAPA-065, CAPA-066); one model-variance event.
