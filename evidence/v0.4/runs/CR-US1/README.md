# CR-US1 evidence: live shop floor (feature 007, MVP)

Recorded 2026-10-19.

- **Tests.** `pytest-dashboard-and-controlroom.log` runs these suites, with the result "all passed, 1 skipped":
  - the Control Room tests: floor 13, windows 6, API 5;
  - the existing dashboard-related suites: AFO M6, CRE D6 views, EASA M7, M6 observability, KPI 003.
- **SSE latency.** In `test_stream_delivers_floor_changes_within_5_seconds`, 20 recorded station changes each
  reached the stream within 5 s, measured over a real loopback server. The 100-event run is CR-T044 evidence.
- **Live state.** Port 8766 against the real state directory, with the 8765 dashboard untouched.
  - Floor snapshot in 0.16 s for 168 workspaces.
  - It shows 0 units in progress and 31 units shipped in the last 24 h, all BLOCKED, each with its recorded
    cause. HAL r161–r164 are BLOCKED only on the owner-postponed safety documents.
- **Screenshots** (headless Firefox, isolated profile):
  - `cr-1440.png`: 1440 px wide;
  - `cr-390.png`: 390 px wide, with the station board collapsed to a list and no horizontal scroll.
