# EASA-M0: baseline and retrospective audit of sealed r101 / r102

Status: **PARTIAL**. This is the first retrospective audit for Feature 006 (spec `specs/006-enhanced-ai-software-assurance`).
It is evidence input for EASA-T003 and EASA-T064; it does not close those tasks by itself.

This is engineering evidence only. It makes no ISO 26262 or Automotive SPICE compliance or capability claim.

## What was done (read-only on the sealed archives)

The sealed review zips were verified against their recorded sha256. They were then extracted to a scratch
directory and every check ran on those copies. The archives and their hashes are unchanged.

| Check | Result |
|---|---|
| Archive hash, `SHA256SUMS.txt`, content-addressed raw logs | PASS (r101 37/37 raw, r102 43/43 raw) |
| Independent rebuild and rerun of the sealed unit tests | PASS: identical to the sealed raw logs (51/51, 26/26 checks) |
| Register map vs RM0486 rev4 (baselined, sha e3cf9752…), with an independent parser (`tools/regcheck.py`) | PASS 48/48 per package; seeded faults detected 2/2 |
| Coverage re-measured with gcov | PASS: matches the sealed claim (100 % lines and branches) |
| Trace links resolve to sources and to executed output | PASS (21/21 and 18/18 SWR) |
| Hardware-fidelity labelling | PASS: Renode marked simulated, `silicon_verified=false` |
| Independent RM/SWR-derived oracle (`oracle/`) on the sealed code | PASS: 41/41 assertions, 0 false positives |

## Measured defect detection (mutation analysis, a project engineering measure)

107 non-equivalent mutants were tested; 12 were excluded as equivalent (unused macros).

| | Sealed factory tests | Independent oracle |
|---|---|---|
| All mutants killed | 92/107 | 104/107 |
| Register-definition mutants killed | 1/12 | 12/12 |

The 3 residual mutants are in LL functions that the r102 HAL never calls. The r101 LL oracle kills them.

## Baseline (commit 52fe2b5)

| Suite | Result |
|---|---|
| `make factory-test` | 429 passed, 8 skipped |
| `make design-check` | 14 tests OK |
| `make test` (v0.1 legacy) | 16 tests OK |
| `specs/006-…/validate_spec.py` | PASS DESIGN ONLY |

## Findings

All findings are listed in `audit-record.json`.

| Finding | Code | Severity | Verdict |
|---|---|---|---|
| F-01 | TEST_ORACLE_SHARED_SOURCE | MEDIUM | CONFIRMED |
| F-02 | REGMAP_CHECK_SHARES_GENERATOR_PARSER | MEDIUM | CONFIRMED (common cause; no defect resulted) |
| F-03 | POLL_BOUND_BOUNDARY_UNTESTED | LOW | CONFIRMED |
| F-04 | SWR013_PRESET_ON_OSCILLATOR_CLEARED | MEDIUM | PLAUSIBLE; needs reviewer disposition |
| F-05 | UNIT_SUMMARY_COUNTS_EXECUTABLES | LOW | CONFIRMED |
| F-06 | MODEL_PER_ROLE_NOT_RECORDED | MEDIUM | CONFIRMED (correlated-AI threat) |
| F-07 | RMW_INSTEAD_OF_SET_CLEAR_REGISTERS | LOW | CONFIRMED |
| F-08 | HOST_MODEL_RESET_VALUE_DIVERGES | LOW | CONFIRMED |

**Not verifiable:**
- The model used by each agent role cannot be read from the package contents.
- The fidelity of the Renode behavioural RCC model cannot be checked against silicon: there is no HIL, the
  silicon revision is UNSPECIFIED, and the errata aren't baselined.

## Reproduce

Extract a sealed zip to a scratch directory, then run the following against `<copy>/evidence/software`:

```sh
python3 -I tools/regcheck.py <RM0486-rev4-ch14-rcc.md> <copy>/evidence/software/ll/stm32n6xx_ll_rcc.h
python3 -I tools/mutate.py <sw> src/stm32n6xx_hal_rcc.c <sw>/tests/unit/test_rcc.c
python3 -I tools/mutate_oracle.py <sw> src/stm32n6xx_hal_rcc.c oracle oracle/it_hal.c
```
