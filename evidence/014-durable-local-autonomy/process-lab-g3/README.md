# G3 — identity-correct structured packet hash (CAPA-074)

Process-first design (`docs/designs/forge-c-process-first-ornith-qwen.md`, G3; owner decisions D9 global, D10 without
`adapter_revision`). Candidate `dc1dd059` (`lrtx/structured.py` `packet_identity`, `lrtx/visit.py` schema mode,
`factory/python/tests/test_lrtx_packet_identity.py`).

- Failed-before: [before-fix.txt](before-fix.txt) (9 of 11 new tests fail at 876d75f code).
- Regression: [REGRESSION.md](REGRESSION.md) — 94 related test files; no failure or error beyond the baseline's.
- CRE: reproducer RPR-073 (`tests/reliability/reproducers/rpr073_packet_identity_alias.py`), runner contrast
  `rr-331ac2f892a6be5a6498` (876d75f, SYMPTOM_PRESENT) vs `rr-a050aa2227d99188e7bb` (dc1dd059, SYMPTOM_ABSENT);
  CAPA-074 → EFFECTIVENESS_OBSERVING ([record](../../cre/capa/capa-074.json)); promotion decision
  `pd-31192ca1b8707be07d17` ELIGIBLE_FOR_OFFLINE_REVIEW, 7/7 hard gates PASS ([decision](../../cre/decisions/pd-31192ca1b8707be07d17.json),
  [gate output](promotion-gate.txt)).
- Native: NATIVE_NOT_RUN. Effect on live checkpoints: non-lab structured checkpoints recompute once after deployment.
