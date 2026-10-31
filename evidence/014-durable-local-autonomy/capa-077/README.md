# CAPA-077 — SWE.1 baseline omitting owner obligations was frozen

- Observed: standalone SWE.1 inspector omission test (../swe1-inspector-omission-20261031/README.md, PROPOSAL-completeness.md options 3 and 1; owner 2026-10-31: global mechanism).
- Reproducer RPR-076 (tests/reliability/reproducers/rpr076_owner_obligation_omitted.py): rr-83fa6c87893365dfafe3 SYMPTOM_PRESENT at 15218323, rr-499a87b4b43688474e53 SYMPTOM_ABSENT at 220bb9d8.
- Failed-before: before-fix.txt. Change (candidate 220bb9d8): opt-in owner_obligations input, coverage findings in swe1.self_check and the SWE.1 author gate, obligation-aware structured author, obligations as SWE.1 inspector sources. Design: docs/designs/swe1-owner-obligation-coverage.md (84c1cb3d).
- Regression: REGRESSION.md (0 candidate-only failures). CRE: pd-f729f5be16ba802f13c9 ELIGIBLE_FOR_OFFLINE_REVIEW, 7/7 hard gates (promotion-gate.txt); CAPA-077 EFFECTIVENESS_OBSERVING (../../cre/capa/capa-077.json).
- Known limitation: the semantic SWE.1 author and the native agent author are not obligation-aware; with obligations declared they fail closed at the gate.
