# Delivery provenance (feature 008 validation example 0008a)

- Origin: the factory's own greenfield work order WO-0002A-STM32N6-RCC-LL-r170 (READY_FOR_OFFLINE_REVIEW,
  2026-10-20), review archive sha256 `ba2f86f5d00abd8e813309a4d65d81ab5310d55f80ccf8d2ca3e2c83e92e34cb`.
- Files copied unchanged from the r170 workspace:
  - `stm32n6xx_ll_rcc.h` sha256 `3fb34b4ed5105b7cb196d770476901875eb63d1d4efa84ed7d9ce4cc594e54be`
  - `stm32n6xx_ll_rcc.c` sha256 `99bc067588be3b09a9f1606e052319edce95ac0394c967b29f8a1892c7fb1e34`
- Licence: Apache-2.0 (the Forge-C repository licence).
- Purpose: the owner asked (2026-10-20) to test the brownfield code modes on the factory's own RCC code. The
  doxygen `@unit`/`@spec` tags in the header refer to r170's unit specifications; a brownfield work order does
  not use them (its trace map replaces code tags).
