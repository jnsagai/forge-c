# T057: one demo project, three standard profiles (US3, SC-007)

`APM=<apm> sh run_profiles.sh <ready-project> <work> <example-project-json>` writes `profiles.txt`. The base is the
sealed run 6 project. Each profile gets a fresh copy, `hi init --force` with that profile and level, both stage gates
and a seal. No model is involved, and nothing in the workproducts changes.

| Profile, level | Level name in reports | Stage names in `gates.md` (sys-req / sw-req) | Gates | Seal | Skills diff |
|---|---|---|---|---|---|
| generic HI-2 | HI-2 | System requirements / Software requirements | all PASS | READY, 0 gaps | empty |
| iso26262 HI-2 | ASIL B | Technical safety requirements / Software safety requirements | all PASS | READY, 0 gaps | empty |
| iec61508 HI-2 | SIL 2 | E/E/PE system design requirements specification / Software safety requirements specification | all PASS | READY, 0 gaps | empty |

**What this run does not show:**
- At HI-2 the three shipped profiles require the same gates and the same independence (separate session), so here
  only the vocabulary and the level names change.
- Rigor differences show at other levels and are covered by tests: separate model families from HI-3, MC/DC at HI-4,
  and the ASPICE process-only levels (`PKG/tests/test_profiles.py`, `test_profile_switch.py`).
- The profiles' rigor values are Forge-C defaults, not readings of the standards' tables.
