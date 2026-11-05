# CAPA-087 — the same checklist item failing again and again was reworked without bound

- Observed: Fabro run WO-F014-SWE2-IWDG-20261101-01 (01M6AHMG3GCVVHHNS2ZTM45NCE, Omniverse2, IWDG LL 0009h,
  high-allowance policy, --stop-after SWE.2). The SWE.1 inspector failed SWE1-04 (CPU constraint; the order had no CPU
  budget) in five consecutive inspections, each with reworded findings, plus SWE1-05 once. Stuck detection compares exact
  findings, so the 1000-pass ladder kept granting rework, and the run was cancelled by hand.
- Owner 2026-11-01: "N can be 3". Fix 22a2ba06: gate.repeated_failed_item: when the last 3 inspections of the phase in
  the budget epoch share a failed checklist item, the high-allowance route answers BLOCKED with
  STUCK: SAME_ITEM_FAILED_3X:<item>.
- The cause in the order (no CPU budget) was handled separately: the owner approved a simulation_performance budget for
  the IWDG orders (run branch, examples 0009g/0009h).
- Reproducer RPR-087 runs: rr-8cea3dd33ce0fa0696eb:e03eb022:BASELINE:SYMPTOM_PRESENT rr-e07faa453a31cdab3c40:22a2ba06:CANDIDATE:SYMPTOM_ABSENT rr-0dcde4ba5e9b06411025:e03eb022:BASELINE:SYMPTOM_PRESENT rr-8918d321d84c8488a5be:22a2ba06:CANDIDATE:SYMPTOM_ABSENT rr-9bfbaa38c7e84b0fd715:22a2ba06:PREVENTION:SYMPTOM_ABSENT
- CRE: pd-2d58f7421f5daf07c3c2 ELIGIBLE (FIX, 7/7, promotion-gate.txt); CAPA-087 in ../../cre/capa/capa-087.json.
- Regression (swap set plus test_same_item_stuck.py) at candidate 22a2ba06 and baseline e03eb022: 1682 passed /
  7 failed and 1679 passed / 7 failed. The same 7 tests fail on both sides
  (../cre-backlog-20261101/regression-failures-both-sides.txt).
