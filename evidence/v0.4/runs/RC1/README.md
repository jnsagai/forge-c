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

## Follow-up

- WO-0008A-STM32N6-RCC-LL-rc1b (main 2a7dae9, CAPA-065 merged): **READY_FOR_OFFLINE_REVIEW, 0 gaps** - no factory
  defect escalated (3 TEST defects corrected by the authors). CAPA-065 effective. Campaign: 6/7 READY after one fix.

## IWDG HAL reruns after PRs #29-#31 (main ffd3097, 2026-10-21; Codex Sol 6.1 authors, Claude Opus 5.5 inspectors, LL from i003)

| Run | Result | Cause |
|---|---|---|
| WO-0009B-STM32N6-IWDG-HAL-rc2 | BLOCKED at SWE.1 (3 cycles, 11 min) | model variance: register effects missing on the first and third author attempts, and a major inspection finding (SWR-002 bundles start/unlock/refresh); no factory change touched SWE.1 |
| WO-0009B-STM32N6-IWDG-HAL-rc3 | BLOCKED STUCK at SWE.4 (24 min) | SWE.1-SWE.3 PASS; no UT:UNKNOWN_SPEC_REF (CAPA-066 effective for its symptom); factory defect CAPA-067: only the first @test of a Doxygen block was traced, so seven USPECs tagged by passing tests were reported UT:SPEC_NOT_VERIFIED |

On a copy of the rc3 workspace the CAPA-067 candidate reduces the SWE.4 findings from 7 to 0. Next: rc4 after CAPA-067 is merged.

## IWDG HAL rc4 after CAPA-067 (main c595a7e, 2026-10-21 08:14-08:52 UTC)

WO-0009B-STM32N6-IWDG-HAL-rc4: **READY_FOR_OFFLINE_REVIEW, 0 gaps**; SWE.1-SWE.6 inspections PASS (one rework each in
SWE.1 - register effects - and SWE.3 - diagram syntax/Doxygen); SWE.4 frozen on the first attempt with no
UT:UNKNOWN_SPEC_REF (CAPA-066) and no UT:SPEC_NOT_VERIFIED. Its test_iwdg.c again documents several tests in one
Doxygen block (9 tests, 1 multi-test block), the input that blocked rc3 before CAPA-067. Archive hash in
WO-0009B-STM32N6-IWDG-HAL-rc4/. With rc1b (0008a), the campaign's seven work orders now each have a READY run;
the rc4 package is an offline review candidate only, not a safety approval or release.
