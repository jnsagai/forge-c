# F011-T029 — local SWE.1 inspector qualification (seeded defects and clean holdouts)

**Result: no local candidate qualifies as the SWE.1 inspector.** Inspector promotion is refused (F011-T030 integrates
nothing). Every run is kept, the void and partial ones included.

**Rule** (validation.md, M4): no false rejection on any clean holdout, and the SWE.1 seeded defects found on target.
- Seen holdouts: WO-0009A IWDG-LL rc1 and WO-0002A RCC-LL rc1, with the S1-OMIT and S1-QM seeded cases.
- Unseen clean holdouts: WO-0002B, WO-0008A, WO-0008B, WO-0008C and WO-0009B.
- The holdout trees are hashed before and after each run; all runs left them unchanged.

| Run | Rules / harness | Candidate | Clean baselines (false rejection / no inspection / pass) | Seeded on target | Status |
|---|---|---|---|---|---|
| 1 | 7786d60 rules | qwen3-coder:30b | IWDG-LL: false rejection | 0 (S1-OMIT off target) | partial, NOT_QUALIFIED |
| 2 | 4f9abde rules | qwen3-coder:30b | IWDG-LL: false rejection | — | partial (stopped at the disqualifying row), NOT_QUALIFIED |
| 2 | 4f9abde rules | gpt-oss:20b | empty output on every item | — | VOID: gateway forces `reasoning_effort=none` (F011-T028C). Its "none" row came from the stale-record harness defect |
| 3 | 4f9abde rules, harness b627861, tree 366db72 | glm4:9b | 3 / 1 / 3 of 7 | 0 (1 off target, 1 missed) | NOT_QUALIFIED |
| 3 | same | phi4:14b | 6 / 1 / 0 of 7 | 0 (2 off target) | NOT_QUALIFIED |
| 3 | same | mistral-small3.2:24b | IWDG-LL: false rejection | — | partial (stopped at the disqualifying row; 3.4 tok/s with CPU offload), NOT_QUALIFIED |
| 3 | same | granite3.3:8b | 3 / 4 / 0 of 7 | 0 (1 off target, 1 missed) | NOT_QUALIFIED |

S1-QM (QM safety scope) is caught by the unchanged deterministic SWE.1 gate in every run.

**What the reports show:**
- Every family fails the IWDG-LL rc1 baseline on SWE1-03 (failure handling or safe state), or on a missing safety
  allocation. Whether that baseline is clean for SWE1-03 is an owner decision (validation.md, M4).
- Several "no inspection" rows are failed visits on RCC packets. phi4:14b, for example, has a 16 k context and RCC
  prompts are about 20 k tokens. The fixed harness counts them as NO_INSPECTION, never as passes.

Files: `run1/`, `run2/`, `run3/` hold the `forge-c/lrtx-seeded/1` reports, model probes and holdout hashes. Evidence
records: `F011-T029-<model>-{SEEN,UNSEEN}/`. The killed mistral and gpt-oss runs left no records.
