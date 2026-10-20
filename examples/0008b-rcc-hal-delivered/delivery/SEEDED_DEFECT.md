# Seeded defect (feature 008 FIX_ALLOWED validation, example 0008b)

- Base: `software/hal/stm32n6xx_hal_rcc.c` of WO-0002B-STM32N6-RCC-HAL-r164 (sha256
  `53b5a8bcdd1d6250bbbe1c467042be8e5e20d4ab054ec4c65277e3e6975d477f`), header unchanged (sha256 `670366c1605b0894ea721e8cdb5fff05687d2a0ab43ec951c4170a48d5bf5f94`).
- Seeded change: in `HAL_RCC_HSE_Enable`, the ready-timeout branch no longer calls `LL_RCC_HSE_Disable()`, so a
  failed HSE start leaves HSEON set while the function reports HAL_TIMEOUT.
- Delivered `stm32n6xx_hal_rcc.c` sha256: `a4b259a463a5a1bfec8d3bdbf2e1d5adcddcb06c66324b72f44a1c1434f30271`.
- Expected factory behaviour: the requirement-derived tests fail on the timeout case, a CODE defect is filed against
  the delivered file, the fix author restores the disable call (smallest change), the tests pass again, and the
  package's change report links the corrected file to that defect. The header stays byte-identical.
- Not told to the agents: this file is not a delivered file and is not copied into the workspace.
