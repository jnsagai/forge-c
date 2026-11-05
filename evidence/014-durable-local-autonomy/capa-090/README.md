# CAPA-090 — a resume dropped the structured checkpoints of the passed phases

- Observed: Fabro runs WO-F014-SWE3-IWDG-20261101-01 and WO-F014-SWE3-OBL-20261101-01 (Omniverse2) were greenfield
  resumes for SWE.3. The structured SWE.3 author refused within seconds (LRTX_SWE3_NEEDS_STRUCTURED_SWE2_INTERFACE):
  resume_from copied the frozen work products and gate records, but not the validated SWE.2 interface task.
- Owner 2026-11-01: "Fresh runs now + fix resume"; later "run just the target swe process using only the artifacts
  produced in previous swe runs".
- Fix e1292cb3: resume_from carries, for the carried phases, the VALID task packets and the assembly, inventory and
  generated-header records. The source's run state (visit state, repair budget, locks, visit logs) is not carried.
  - Effective in use: WO-F014-SWE3-IWDG-20261101-L1, resumed from SWE2-IWDG-02 on the run branch with this fix, passed
    SWE.3.
- Reproducer RPR-090 runs: rr-dc6f77d36b1f3221f5ac:815c52c8:BASELINE:SYMPTOM_PRESENT rr-e2f9d7eb9f1464231399:e1292cb3:CANDIDATE:SYMPTOM_ABSENT rr-d7b62cd0fc0c0898e6a0:815c52c8:BASELINE:SYMPTOM_PRESENT rr-35c00edc1f6d8a2ee1ce:e1292cb3:CANDIDATE:SYMPTOM_ABSENT rr-13841d16dbe53d14f12f:e1292cb3:PREVENTION:SYMPTOM_ABSENT rr-a26b760e0023e35b294a:fc6848bb:PREVENTION:SYMPTOM_ABSENT rr-4982b677fe66dacb783e:103a938e:PREVENTION:SYMPTOM_ABSENT
- CRE: pd-06cec20cfe07e60f8a0c ELIGIBLE (FIX, 7/7); CAPA-090 in ../../cre/capa/capa-090.json.
- Regression (swap set plus resume, floor and CAPA-089 tests) at e1292cb3 and at baseline b9ff12cc: 1744 passed /
  7 failed and 1740 passed / 7 failed. The same 7 tests fail on both sides.
