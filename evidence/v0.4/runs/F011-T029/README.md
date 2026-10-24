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
| 5 (omniverse2) | SWE1-03 rules d07102b (CRE pd-3246c9d4c13746b3041e) | gpt-oss:120b (reasoning high) | seen 0 of 2; unseen 1 / 0 / 4 of 5 (WO-0008C, SWE1-04 budget fact defect) | 1 of 2 (RCC-LL on target, IWDG-LL missed) | NOT_QUALIFIED (IWDG S1-OMIT missed) |
| 5 (omniverse2) | rules d07102b, pin d9f2374 (CRE pd-da8294942a40c170643e) | qwen3.6:35b-a3b (reasoning off) | seen 1 of 2 (IWDG-LL: SWE1-04/05/06 claims) | 0 (2 off target) | NOT_QUALIFIED; UNSEEN not run (rule) |
| 6 (omniverse2) | + budget fact fix 2fcf40c (CRE pd-2c10d694071b23e63dde) | gpt-oss:120b (reasoning high) | unseen 2 / 0 / 3 of 5 (WO-0002B, WO-0009B: register_effects final-state misread) | — (unseen only) | NOT_QUALIFIED |

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

## Runs 5 and 6 — the SWE1-03 diagnostic (omniverse2, 2026-10-24)

Owner 2026-10-24: "run the SWE1-03 diagnostic" and "we need to find a way to overcome this blocking point".

**Diagnostic.** Every SWE1-03 rejection of the clean LL baselines was a `failure_handling_missing` or
`safe_state_missing` claim. The adjudicator had no rule for either assertion, so such a claim always stood. On IWDG-LL,
gpt-oss:120b's only standing claim (run 4) was `failure_handling_missing` aimed at the recorded Safety allocation gap.
Fixed rules added (d07102b, `factory/python/forge_factory/lrtx/review_semantic.py`, tests in
`factory/python/tests/test_lrtx_v2_review.py`):
- a document-level `failure_handling_missing` on a layer-LL work order is REFUTED by ADR-0009 (no waiting; timeouts,
  parameter checks and status codes belong to the HAL work order);
- a document-level `safe_state_missing`, or `failure_handling_missing` aimed at the Safety allocation input, follows the
  recorded-gap rule (F011-AT-020);
- a claim about one requirement, HAL failure handling, an unrecorded allocation and a missing mandatory ASIL input
  still stand (F011-AT-023).

Run 5 then showed a second rule defect: the SWE1-04 budget fact recognised only "at most N bytes of static RAM", while
the baselines say "0 bytes of [persistent] static RAM ... within the 64-byte static RAM budget". Static RAM was false on
all seven holdouts, so the existing `budget_missing` refutation never applied (fixed in 2fcf40c).

**Results.**
- gpt-oss:120b, run 5 seen: both clean baselines pass (0 false rejections). S1-OMIT on target in RCC-LL (SWR-017 refers
  to the removed SWR-001); **missed** in IWDG-LL. In run 4 that row was "off target" only through the claims now refuted.
- gpt-oss:120b, run 5 unseen: 4 of 5 pass; WO-0008C rejected on SWE1-04 `budget_missing` (the budget fact defect).
- gpt-oss:120b, run 6 unseen (budget fix): 3 of 5 pass; WO-0008C now passes, but WO-0002B and WO-0009B, which passed in
  run 5, are rejected. Both claims read `workproducts/SWE.1/register_effects.json` as contradicting the requirement
  (SWR-006 assert-then-release recorded as `clear`; the IWDG start sequence recorded with its final key 0xAAAA). The
  effects contract records the final register state of each case, so both are false rejections.
- qwen3.6:35b-a3b (reasoning off), run 5 seen: IWDG-LL rejected (SWE1-04 `budget_not_measurable` on the Budgets input,
  SWE1-05 and SWE1-06 claims on the recorded safety gap); S1-OMIT off target on both baselines. 1–5 s per item.
- The holdout hash lists before and after every run equal the run 4 list (`run5-omniverse2/holdout-lists.sha256`,
  `run6-omniverse2/holdout-lists.sha256`).

**What this means.** gpt-oss:120b stays NOT_QUALIFIED (IWDG S1-OMIT missed; the owner chose "Inspector only", so no
deterministic coverage gate). Its verdicts on the same inputs differ between runs, so one passing run is not evidence.
All seven holdouts and the seeded catalogue have now been used to find rule gaps: they are a learning set, not an
unseen test. The owner chose an inspector knowledge base with a frozen test set (F011-T043..T047, spec addendum
2026-10-24). A qwen3.6 run with thinking (owner "Measure with thinking", CRE pd-5179d881d5209880c1f5) is in progress.
