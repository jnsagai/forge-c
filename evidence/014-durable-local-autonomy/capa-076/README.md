# CAPA-076 — inspector findings withdrawn in a localized repair were not recorded

- Observed: standalone SWE.1 run (../swe1-ornith-standalone-20261031/FINDINGS.md item 2); owner option A, record only (../swe1-ornith-standalone-20261031/PROPOSAL-inspector-repair.md).
- Reproducer RPR-075 (tests/reliability/reproducers/rpr075_inspector_repair_drops_findings.py): rr-cc03f0bd2f5da4c7f694 SYMPTOM_PRESENT at d18e454a, rr-7b22e1c7861920a9766b SYMPTOM_ABSENT at 51a9138d.
- Failed-before: before-fix.txt. Fix (candidate 51a9138d): visit.run_task keeps rejected_findings of inspector attempts; lrtx.review reports withdrawn_in_repair and LRTX_INSPECTOR_FINDING_WITHDRAWN_IN_REPAIR notes. Verdict and gate unchanged.
- Regression: REGRESSION.md (0 candidate-only failures). CRE: pd-5b09a4c8c20df6109845 ELIGIBLE_FOR_OFFLINE_REVIEW, 7/7 hard gates (promotion-gate.txt); CAPA-076 EFFECTIVENESS_OBSERVING (../../cre/capa/capa-076.json).
