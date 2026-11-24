# T068: the later V-model stages, once each (US4)

## Attempt 1 (`attempt1/`): no stage accepted; distorted by a package defect

| Stage | Outcome | Open findings | Raised by the conductor itself | Blocking open points |
|---|---|---|---|---|
| sys-arch | BLOCKED | 90 | 84 | 5 |
| sw-arch | BLOCKED | 119 | 114 | 3 |
| sw-design | BLOCKED (build and static-analysis FAIL) | 20 | 15 | 4 |
| unit-verif, sw-integ, sw-qual, sys-integ, sys-qual | author harness failed (exit 1); the cause was not recorded | - | - | - |

- **Defect (Claude's, T089):** the coverage matrix ran in every stage. Outside the requirement stages every "covered" row
  became a gap, and the conductor raised bogus SQ-01 findings that went to the author as rework. The coverage matrix is
  now limited to the requirement stages. The earlier accepted runs were requirement stages only and had no such rows.
- **Defect:** build and static-analysis issues were never sent to the author (fixed in d9873f59).
- **Real findings on the accepted run 6 requirements:**
  - `T_DIAG` may run for 20 ms in a 10 ms control cycle whose program flow is checked at its end (CON-SUP-101/103/104);
  - a burst of four fault reports behind an answer line can take 12.9 ms against the 10 ms limit (CON-SUP-143).
  Both come from Claude's fictional decisions, and both passed the requirement inspections of run 6.

A first try at attempt 2 (software design onward) was stopped after a few minutes when the coverage defect was found.
