# CAPA-078 — critical owner obligation recorded as an obligation gap was frozen

- Observed: Fabro SWE.1 run WO-F014-SWE1-OBL-20261031-02 (01M69RYT6NP8Y8ZXB3MB173SDP, Omniverse2, Qwen3.8 medium): critical OBL-preserve-other-registers recorded as a gap with a false reason; author gate FROZEN, inspection PASS 6/6.
- Owner 2026-10-31: "critical obligations can never be gaps".
- Reproducer RPR-077: rr-e3ebf1e3ee3a02809d1c SYMPTOM_PRESENT at 06914b8b, rr-d4a9b2574b51ab5aa6d5 SYMPTOM_ABSENT at 8d6841bd. Failed-before: before-fix.txt.
- CRE: pd-d07d5b621a1fb617d019 ELIGIBLE (FIX, 7/7, promotion-gate.txt); CAPA-078 EFFECTIVENESS_OBSERVING (../../cre/capa/capa-078.json).
- Regression: REGRESSION.md.
