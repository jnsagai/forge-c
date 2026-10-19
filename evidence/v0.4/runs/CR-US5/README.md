# CR-US5 evidence: alerts and attention list (feature 007)

Recorded 2026-10-19.

- **Tests.** `test_controlroom_alerts.py` has 6 tests:
  - STATION_BLOCKED carries the recorded reason and is critical.
  - REWORK_BUDGET_NEAR uses the gate's own `max_rework_cycles` (2 of 3 used).
  - LEAD_TIME_OVER_LIMIT and FEED_STALE are raised.
  - An alert keeps a stable id while its condition persists, so it is updated rather than duplicated.
  - SAFETY_PROCESS_VIOLATION (K20 > 0) is critical, `filterable: false`, listed first, and forces the factory
    status to VIOLATION.
  - YIELD_BELOW_THRESHOLD comes from measured K02. YIELD_OUT_OF_CONTROL fires only when the latest p-chart point
    breaks a rule.
  - No acknowledgement route exists on the server.
- **Acknowledgement** is stored only in the viewer's browser (`localStorage`). A safety/process violation stays
  visible even when acknowledged. Browser notifications are opt-in, for new critical alerts.
- **Live, port 8766.** No open alerts: nothing is in progress and K20 = 0 today. The floor snapshot with alerts
  answers in under 0.1 s (scorecard and quality inputs cached for 30 s and 60 s).
