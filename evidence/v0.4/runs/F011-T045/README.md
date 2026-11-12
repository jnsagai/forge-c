# F011-T045 — promotion trials of IL-001..004 (learning set, omniverse2)

Status: **OPEN — no lesson promoted.** All four lessons stay PROPOSED.

Both trials ran `forge_factory.lrtx.seeded` with seven holdouts (the learning set) and every SWE.1 case of
lrtx-seeded-2 (BASELINE, S1-OMIT, S1-QM, S1-EFFECT, S1-NOSTART, S1-GAPROW, S1-NOBUDGET; 49 evaluations), using
qwen3.6:35b-a3b with thinking (reasoning high, 16384 extra output tokens), the semantic inspector, and `--lessons-trial`,
so the PROPOSED lessons reached the packet. The holdout trees were unchanged; the list digest is 72d670c2… (same as
runs 4–7 of F011-T029). Trial 1 has no after-digest because its script was stopped after the qwen part.

| Trial | Settings | Commit | Record |
|---|---|---|---|
| m8 | no sampling, no coverage questions | 254a7af | `../F011-T045-trial-qwen3-6-35b-a3b/` |
| m9 | T048 sampling (temperature 0.6, top_p 0.95, seed 1) and T049 coverage questions | 1d0ee6b | `../F011-T045-trial2-qwen3-6-35b-a3b/` |

| Case (7 each) | m8 | m9 |
|---|---|---|
| BASELINE | 6 pass, 1 false rejection | 6 pass, 1 false rejection |
| S1-QM | 7 deterministic gate | 7 deterministic gate |
| S1-EFFECT | 0 on target, 7 missed | 0 on target, 1 off target, 6 missed |
| S1-NOSTART | 3 on target, 1 deterministic, 1 off target, 2 missed | 2 on target, 1 deterministic, 1 off target, 2 missed, 1 no inspection |
| S1-GAPROW | 2 on target, 5 missed | 3 on target, 3 missed, 1 no inspection |
| S1-NOBUDGET | 2 on target, 1 off target, 4 missed | 2 on target, 5 missed |
| S1-OMIT | 1 on target, 1 off target, 5 missed | 1 on target, 1 off target, 4 missed, 1 no inspection |

- The false rejection is the same in both trials: WO-0008B, SWE1-04 "other" on Safety allocation. The model reads the
  recorded pending reaction-time allocation as a budget defect.
- m9 "no inspection" (3): the reply was FAILED. The seeded report keeps only the reply, so the cause is not recorded;
  the run log shows repeated invalid answers on coverage and item tasks. The seeded harness now records the reply
  issues.
- Per-lesson check (`promotion-check.json`, `knowledge.inspection.promotion_issues`): every lesson has
  PAIRED_DEFECT_NOT_DETECTED in both trials; IL-004 also has FALSE_REJECTION_IN_SCOPE. Decision: none promoted.
- Wall time: m8 about 70 min; m9 2 h 24 min (coverage adds 3–4 calls per evaluation).

Conclusion: lessons, sampling and coverage questions did not raise detection on the learning set. S1-EFFECT is never
caught (0/14) and S1-NOBUDGET mostly missed (4/14). The next step targets these with per-entry questions (F011-T054).
F011-T047 (frozen test set) is held: it measures "with the validated lessons", none is validated, and a test-set run of
a candidate that already fails the learning set would spend the only independent measure.
