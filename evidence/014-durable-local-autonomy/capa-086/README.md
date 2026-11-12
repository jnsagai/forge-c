# CAPA-086 — the structured time box exceeded Fabro's stall watchdog

- Observed: Fabro SWE.1 run WO-F014-SWE1-RCC-20261101-02 (01M6AMZB126SW8SQY9CB4C80E1, Omniverse2, RCC LL 0002h, profile
  local-rtx-v2-omniverse2-ornith-think-author-q38-inspector). Nine register tasks were valid after 13 calls (1762 s of
  model time, longest call 448 s). Then Fabro's watchdog fired: 'stall watchdog: node "swe1_author" had no activity for
  1800s', and the run failed. A command node reports activity only when it exits. The profile asked for a 21600 s time
  box (visit_time_s), so the node never exited to continue.
- Fix 99132bb8: workorder.local_profile_structured caps visit_time_s at MAX_VISIT_TIME_S = 1200 (as local-rtx-v1 measured)
  and records the requested value (visit_time_requested_s). 1200 s + 448 s < 1800 s. The continuation node resumes the
  work, and its visits do not consume the rework budget.
- Reproducer RPR-086 runs: rr-ba5c3db0f644df2c4088:79a445da:BASELINE:SYMPTOM_PRESENT rr-6fd948bada2875e2f1d9:99132bb8:CANDIDATE:SYMPTOM_ABSENT rr-f50bfd5febe5d84b4693:79a445da:BASELINE:SYMPTOM_PRESENT rr-e5f10c92fa36981da3eb:99132bb8:CANDIDATE:SYMPTOM_ABSENT rr-c411ced38a305a0a660b:99132bb8:PREVENTION:SYMPTOM_ABSENT
- CRE: pd-226f88d993926c726dac ELIGIBLE (FIX, 7/7, promotion-gate.txt); CAPA-086 in ../../cre/capa/capa-086.json.
- Regression (swap set plus test_fabro_stall_time_box.py) at candidate 99132bb8 and baseline 79a445da: 1681 passed /
  7 failed and 1679 passed / 7 failed. The same 7 tests fail on both sides
  (../cre-backlog-20261101/regression-failures-both-sides.txt).
- Profiles q38-aspice-max-mtp and ornith-author-q38-inspector also request 21600 s; the cap applies to them as well.
