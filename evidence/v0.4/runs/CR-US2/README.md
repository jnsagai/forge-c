# CR-US2 evidence: shift and day production scorecard (feature 007)

Recorded 2026-10-19.

- **Tests.** `test_controlroom_scorecard.py` has 7 tests: K01–K20 equal `kpi.engine.snapshot` for the same
  window and events (SC-003); READY and BLOCKED are kept separate; OEE is NOT_MEASURED without a baseline;
  cohorts stay apart; a replay is idempotent (`counts` de-duplicates replayed events); the previous window has
  equal length; the scorecard says WARMING_UP before its first data; and the API covers each window kind
  (custom with a bad range → 422, unknown cohort → 422).
  All Control Room tests plus `test_kpi_003.py` pass (54).
- **Live, port 8766, real state.**
  - The cache warms in about 40 s. After that the scorecard API answers in about 0.6 s, and K06 station cycle
    time is measured from Fabro stage events.
  - Today (all runs): 0 READY, 18 BLOCKED, 16 runs started for 2 driver orders.
  - OEE, READY lead time and today's first-pass yield are NOT MEASURED, each with the engine's reason.
- **Cohort.** The default is "all runs", labelled as including cloud-model runs (OD-2026-10-19-06/08). The
  feature-003 production cohort (local-only) is unchanged and selectable.
- **Screenshots:** `cr-1440.png` and `cr-390.png`.
