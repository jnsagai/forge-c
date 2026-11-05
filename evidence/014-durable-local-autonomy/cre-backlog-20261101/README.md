# CRE backlog 2026-11-01 — CAPA-080 to CAPA-084 and the CHANGE gate 4fcfa3a9..13edee4f

All five fixes come from Fabro SWE.1 runs on Omniverse2 (2026-10-31, CRC IDR 0014h/0014i, Ornith author / Qwen3.8 inspector).
Each gate compares the fix commit with its parent revision; the reproducer runs are in the CRE store (ids below).

| CAPA | Fix | Reproducer | Baseline run (SYMPTOM_PRESENT) | Candidate run (SYMPTOM_ABSENT) | Decision |
|---|---|---|---|---|---|
| CAPA-080 register-effect obligations are removed from the cross-cutting answer | 26fb5894 vs 4fcfa3a9 | RPR-079 | rr-78fe54cf8478c201bdbc | rr-38d1a18e88437c268fb4 | pd-4345c458e65cf1f6043e ELIGIBLE |
| CAPA-082 obligation ids are not copied into statements | f0c02663 vs 87e96ac3 | RPR-081 | rr-f6556e8278381f729c68 | rr-33c02e02782047ca0e69 | pd-18ce1675363a0b8d927b ELIGIBLE |
| CAPA-081 profile select waits for the model server | 89c4a2a9 vs efb15d55 | RPR-080 | rr-0828e00cf2a271a40241 | rr-1f947ab3135edf95d2f3 | pd-87dc89388201909c8d3f ELIGIBLE |
| CAPA-083 ASPICE-only safe-state note for SWE1-03 | 0651912b vs 89c4a2a9 | RPR-082 | rr-d155f890184a99c14342 | rr-6c17e7f8a419db4a9a7a | pd-611df54a4927dd6d309e ELIGIBLE |
| CAPA-084 repair stops on unchanged findings | 13edee4f vs 0651912b | RPR-085 | rr-f1ce06c545ff816921c5 | rr-43a226bc9f396a6e1a98 | pd-91d473082a1e4dc8a373 ELIGIBLE |

- **CAPA-084, first gate REJECTED** (pd-cd8be450a5cd0189b13c, BASELINE_NOT_REPRODUCED:ERROR). RPR-083 printed the call
  count after its signature (`SYMPTOM_PRESENT:<signature> (6 calls)`), so the runner did not match the frozen signature.
  The fix itself was not at fault. RPR-083 stays frozen as it was used. CAPA-084 went UNRESOLVED and was re-triaged
  (bounded, 1 of 3) with the new reproducer RPR-085: same scenario, exact signature line, count on stderr.
- **CHANGE gate** over the whole range 4fcfa3a9..13edee4f: pd-6c2cc442632ba3b43a2d ELIGIBLE (7/7 hard gates; reproducer
  not applicable for a CHANGE).
- **Regression** (regression-files.txt, 124 files) at candidate 13edee4f and baseline 4fcfa3a9: 1679 passed / 7 failed
  and 1674 passed / 7 failed; the same 7 tests fail on both sides (regression-failures-both-sides.txt: crash-reaping,
  provider-recovery, WAL-crash and frozen-fixture compatibility tests). They fail on the baseline as well; not
  investigated in this session.
- Eligible for OFFLINE review only. No deployment, no merge to main.
