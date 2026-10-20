# Regression campaign rc1 (2026-10-20, owner "propose something and do it")

All seven example work orders on main e66de22 from one frozen worktree (`/home/jefferson/forge-c-run-rc1`), Codex
authors, Claude inspectors, no DeepSeek.

| Work order | Result |
|---|---|
| WO-0002A-STM32N6-RCC-LL-rc1 | READY_FOR_OFFLINE_REVIEW, 0 gaps |
| WO-0002B-STM32N6-RCC-HAL-rc1 | READY_FOR_OFFLINE_REVIEW, 0 gaps |
| WO-0008A-STM32N6-RCC-LL-rc1 | SWE.1-SWE.6 PASS; BLOCKED on escalated DEF-003 (FACTORY): regression of the RCC model's set/clear reads -> CAPA-065 |
| (remaining) | see later commits |
