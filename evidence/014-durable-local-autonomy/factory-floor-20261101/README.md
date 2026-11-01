# Factory floor view (feature 007 addendum) — CHANGE gates

- f262931d (floor view: progress_api, floor_api, factory-floor.html, specs/007 addendum): pd-f4a43b9c114bb46e0a79 ELIGIBLE
  against 8ee683b7.
  - The golden duration changed from 8.6 s to 21.3 s. This is informational (n=1, not a gate), measured on a busy
    machine; the floor code is not on the golden path.
- 2a6f8c3c (native agent nodes from the Fabro run state, GPU station): pd-b888a80df29d5fa9f895 ELIGIBLE against f262931d.
  Targeted tests: test_factory_floor, test_gateway_live_tap, test_llm_gateway, test_think_profile_inspection_sources,
  24 passed.
- Owner 2026-11-01: "the mockup is great!! lets commit and push it and use it from now on for new runs".
- Deployed read-only on Omniverse2: user unit forge-c-floor-swe1.service, from the pinned worktree at 2a6f8c3c's content
  (f9b20cc5bc on change/floor-native). Reached at http://master.local:8788 through the loop10 tunnel unit.
- Eligible for OFFLINE review only. No merge to main.
