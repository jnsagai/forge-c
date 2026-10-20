# Full regression on main 625ed02 (PRs #16, #17, #18 merged, 2026-10-20)

`run.sh` checks out 625ed02 in a frozen worktree and runs validate_design, the 005/006 spec validators, ruff and `assurance.regress --full`. Result: PASS (design-006, negatives x2, design-check-002, legacy-v0.1, factory-test).
