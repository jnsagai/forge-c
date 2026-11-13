# Baseline (T002)

Base: campaign 5f20c077 (020 round 3) + specs; f020 regression scope (model-service/f020reg2.sh, 108 files):
17 failing on base and feature alike (17 = 17, NEW none) - the same pre-existing set as every 020 round;
packet identity / golden / lrtx compat / f020 carry, template v2 and round 3 suites green on this branch after T004
(semantic_key is a pure function; packets unchanged).

## Regression after T007-T008 (1df07aa8)

f020 regression scope (model-service/f021reg.sh, 109 files) vs base: 108 NEW failures on the first run were all
environmental - the new worktree lacked the 11 git-ignored vendor inputs (RM0486/DS14791 excerpts, CMSIS header).
After copying them byte-identical from forge-c-020-usart, the 108 tests pass (rc=0): NEW none. GONE 3
(lrtx_compat fixtures, owner_obligation_coverage) also input-related on the base run.
