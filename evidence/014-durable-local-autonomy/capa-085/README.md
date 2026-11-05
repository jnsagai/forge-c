# CAPA-085 — a deterministic inspector refusal was re-inspected without bound

- Observed: Fabro SWE.1 run WO-F014-SWE1-IWDG-20261101-02 (01M6A9BAMW93JGYA9X91TS7RDW, Omniverse2, example 0009g with
  generated obligations, run branch 97e19c22). The SWE.1 baseline froze (15 SWR). The structured inspector then refused
  it before any model call: SOURCE_TOO_LARGE, because the generated obligations cited the 454 kB guideline. Nothing was
  recorded, so the route gate answered REINSPECT, and the high-allowance ladder granted rework 166 times in 4 minutes
  (with a model swap each cycle) until Fabro ended the run as failed.
- Fix 59d76925: Store.gate returns BLOCKED (INSPECTOR_REFUSED_REPEATEDLY:<issue>) when the last three inspector replies
  since the baseline froze are FAILED with zero calls and identical issues. step_route does not let the high-allowance
  ladder override it. Failures after model calls keep the existing re-inspection.
- The source cause (the generator citing the guideline) is fixed on the unpromoted run branch (run/gen3 8d1f110c): the
  generated file binds the guideline by hash only. IWDG-03 on that branch passed SWE.1.
- Reproducer RPR-084 runs: rr-58582cc06e26e6c0544b:5ac47d20:BASELINE:SYMPTOM_PRESENT rr-59ac0b1a0f84bdfc9cd2:59d76925:CANDIDATE:SYMPTOM_ABSENT rr-a10bfc4b7e6e6c88f7c4:5ac47d20:BASELINE:SYMPTOM_PRESENT rr-3039cddcb22600237f32:59d76925:CANDIDATE:SYMPTOM_ABSENT rr-8af0439b2ed0ccddbb1a:59d76925:PREVENTION:SYMPTOM_ABSENT
- CRE: pd-3568846eda79b2867894 ELIGIBLE (FIX, 7/7, promotion-gate.txt); CAPA-085 record in ../../cre/capa/capa-085.json.
- Regression (swap set plus test_inspector_refusal_bound.py) at candidate 59d76925 and baseline 5ac47d20: 1683 passed /
  7 failed and 1679 passed / 7 failed. The same 7 tests fail on both sides
  (../cre-backlog-20261101/regression-failures-both-sides.txt).
