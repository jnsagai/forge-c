# CAPA-075 — scoped write in a workspace copy touched the source workspace

- Observed: standalone Ornith SWE.1 run (../swe1-ornith-standalone-20261031/FINDINGS.md item 1).
- Reproducer RPR-074 (tests/reliability/reproducers/rpr074_scoped_write_foreign_workspace.py): rr-ff13b995de8605815980 SYMPTOM_PRESENT at 7490b6d8, rr-238ed70983265d1accd0 SYMPTOM_ABSENT at 2f2aefa0.
- Failed-before: before-fix.txt. Fix: lrtx/visit.write_scoped re-roots the binding at the written workspace (candidate 2f2aefa0).
- Regression: REGRESSION.md (140 files, 0 new failures). CRE: pd-27fa43ef4598a153fccb ELIGIBLE_FOR_OFFLINE_REVIEW, 7/7 hard gates (promotion-gate.txt); CAPA-075 EFFECTIVENESS_OBSERVING (../../cre/capa/capa-075.json).
- Follow-up (not fixed): copied durable-binding.json still binds a copy to the source AFO job.
