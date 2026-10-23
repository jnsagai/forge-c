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
| 4 (omniverse2, 48 GB) | same rules, tree b2a1f92 | gpt-oss:120b (reasoning high) | IWDG-LL: false rejection (SWE1-03) | 0 (S1-OMIT off target) | partial, NOT_QUALIFIED |
| 4 (omniverse2, 48 GB) | same | gpt-oss:20b (reasoning high) | 2 false rejections of 2 seen (SWE1-03 on both) | 1 of 2 on target (RCC-LL), 1 off target | NOT_QUALIFIED; UNSEEN not run (rule) |

S1-QM (QM safety scope) is caught by the unchanged deterministic SWE.1 gate in every run.

**What the reports show:**
- Every family fails the IWDG-LL rc1 baseline on SWE1-03 (failure handling or safe state), or on a missing safety
  allocation. Whether that baseline is clean for SWE1-03 is an owner decision (validation.md, M4).
- Several "no inspection" rows are failed visits on RCC packets. phi4:14b, for example, has a 16 k context and RCC
  prompts are about 20 k tokens. The fixed harness counts them as NO_INSPECTION, never as passes.

Files: `run1/`, `run2/`, `run3/` hold the `forge-c/lrtx-seeded/1` reports, model probes and holdout hashes. Evidence
records: `F011-T029-<model>-{SEEN,UNSEEN}/`. The killed mistral and gpt-oss runs left no records.

## Run 4 — omniverse2 (2026-10-23)

Same seeded catalogue (`lrtx-seeded-1`, sha256 03bdc7c7…) and rules. The holdouts are sha256-checked copies of the
loop10 work orders (owner-approved transfer); their hashes before the run are in `run4-omniverse2/holdouts-before.sha256`.
Profile local-rtx-v2-omniverse2, gpt-oss:120b pinned by digest 714d8695… (CRE pd-8fece5b75d3e5345875f), reasoning
`high`, Ollama 0.34.0 with the model partly in CPU memory (65 GB on a 48 GB GPU).

- **gpt-oss:120b: NOT_QUALIFIED.** On the clean IWDG-LL rc1 baseline it raised SWE1-03 (failure handling missing,
  safety allocation pending). The owner ruled that baseline clean for SWE1-03 on 2026-10-23, so this is a false
  rejection, the disqualifying row. S1-OMIT was flagged off target (SWE1-03/SWE1-04, not the omitted SWR-001); S1-QM was
  caught by the unchanged deterministic gate. The SEEN record ended at the evidence runner's 1800 s limit during the
  RCC-LL rows (exit 124, report written up to the IWDG rows: `run4-omniverse2/gpt-oss-120b-seen.json`). The UNSEEN
  run was stopped after the disqualifying row (exit -15; record kept).
- Every inspection item took 60–135 s with the model partly offloaded.
- **gpt-oss:20b (reasoning high, now allowed by the gateway exception): NOT_QUALIFIED.** Both seen baselines were
  rejected on SWE1-03 (failure handling; plus a SWE1-04 note on CPU/timing limits): 2 false rejections. S1-OMIT was
  found on target in RCC-LL (SWR-017 references the removed SWR-001) and off target in IWDG-LL. The unseen run was not
  started, by the rule. Holdout hashes after the runs equal those before (`run4-omniverse2/holdouts-after.sha256`).
- Pattern across every family measured (qwen3-coder, glm4, phi4, mistral-small3.2, granite3.3, gpt-oss 20b and 120b):
  the LL baselines are rejected on SWE1-03, which the owner ruled clean for these work orders.
