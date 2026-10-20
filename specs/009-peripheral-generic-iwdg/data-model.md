# Data Model: Peripheral profile

## `config/factory/peripherals/<id>.yaml` (contract: `contracts/peripheral-profile.schema.json`)

| Field | Example (IWDG) | Example (RCC, today's constants) |
|---|---|---|
| `id` | `iwdg` | `rcc` |
| `name` | Independent watchdog (IWDG) | Reset and clock control (RCC) |
| `register_prefix` | `IWDG` (RM names `IWDG_KR` ...) | `RCC` |
| `base_address` | `0x56004800` (secure) | `0x56028000` |
| `window_bytes` | `1024` | `4096` |
| `rm.doc` / `rm.chapter` | `RM0486` / `59` | `RM0486` / `14` |
| `rm.key_sections` | `["59.7.1", "59.7.2", "59.7.3", "59.7.4"]` | `["14.10.1", "14.10.2", "14.10.79", "14.10.64"]` |
| `ll.header` | `stm32n6xx_ll_iwdg.h` | `stm32n6xx_ll_rcc.h` |
| `ll.compile_unit` | `stm32n6xx_ll_iwdg.c` | `stm32n6xx_ll_rcc.c` |
| `ll.function_prefix` | `LL_IWDG_` | `LL_RCC_` |
| `ll.register_block` | `ll_iwdg_regs` | `ll_rcc_regs` |
| `ll.register_count` | `256` | `1024` |
| `hal.header` / `hal.source` / `hal.function_prefix` | `stm32n6xx_hal_iwdg.h/.c`, `HAL_IWDG_` | `stm32n6xx_hal_rcc.h/.c`, `HAL_RCC_` |
| `sim.model` / `sim.platform` | `iwdg_model.py` / `stm32n6_iwdg.repl` | `rcc_model.py` / `stm32n6_rcc.repl` |
| `system_name` | `IWDG LL driver` | `RCC LL driver` |

**Rules**:
- `id` matches the file name;
- the prefixes are upper-case identifiers;
- `base_address` is a hexadecimal string;
- `key_sections` exist in the converted chapter (checked at work-order preparation).

## Work order spec

The new optional field is `peripheral` (profile id, default `rcc`). The manifest records `peripheral` and the
profile's SHA-256.
