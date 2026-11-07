# CAPA-177..180 — owner-lane fixes V17-V19, backfilled through CRE (2026-11-07)

The owner asked "are we using CRE and CAPA?". Every commit had been gated up to V16 b7d1013b (pd-c01faadb,
2026-11-06), but V17 5cba4795 and V18 a32c7c31 were committed and deployed, and V19 committed, without a CAPA or a
promotion decision. These four CAPAs close that gap. Each reproducer was frozen before its own gate (append-only
manifest, earlier gates first) and run by the CRE runner under bubblewrap.

| CAPA | RPR | baseline -> candidate | symptom | decision |
|---|---|---|---|---|
| CAPA-177 | RPR-177 | b7d1013b -> 5cba4795 | think-AFO Ornith author measured by byte count (CAPABILITY_LIMIT on 115-123 kB requests) | pd-194bdece ELIGIBLE 7/7 |
| CAPA-178 | RPR-178 | 5cba4795 -> a32c7c31 | a SWE.6 retry starts with none of the earlier attempt's tests (L90X 0/24 after L90W 15/24) | pd-6417a6a4 ELIGIBLE 7/7 |
| CAPA-179 | RPR-179 | a32c7c31 -> b13eeaf3 | the retry restores the attempt's last broken tests, not its best run (L90Z 24/24 at 09:56:59) | pd-ff48db3a ELIGIBLE 7/7 |
| CAPA-180 | RPR-180 | a32c7c31 -> b13eeaf3 | SWE.6 author budget still 35 calls (L90X TURN_BUDGET_EXHAUSTED); owner: raise all limits | pd-3ba2572e ELIGIBLE 7/7 |

- capa-177-decision.json is the same record as capa-177-decision-r2.json (the ELIGIBLE gate).
- The first CAPA-177 gate pd-601bdec8 was REJECTED (prevention: RPR-004/064/132). Cause: the gate shell lacked the
  factory toolchain on PATH, so host-clang resolved to clang 12 (no -fstack-usage). The same three were
  SYMPTOM_PRESENT/ERROR on b7d1013b too and SYMPTOM_ABSENT once toolchains/LLVM-19.1.7 was first on PATH. The driver
  (capa-run.py) now refuses to run without it.
- V19 b13eeaf3 (author 4096 calls: lrtx/visit.py refuses more than 4096) was deployed on 2026-11-07 13:50 UTC after
  its ELIGIBLE decisions. No decision deploys anything; all four CAPAs are EFFECTIVENESS_OBSERVING.
