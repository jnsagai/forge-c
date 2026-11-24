# Simulator platform of the Safety Supervisor demo

A combined Cortex-M55 platform for Renode 1.17: `run_sim.sh <program.c>` builds one target program with the product
sources and runs it; `selftest/test_platform.c` checks the watchdogs and reset flags.

| Part | Model | Secure base |
|---|---|---|
| IWDG, WWDG, RCC reset flags (RCC_RSR) | `HiStm32n6Watchdogs.cs`, written for this demo from the register behaviour in the reference manual | 0x56004800, 0x50002C00, 0x56028000 |
| USART1, GPIOA, TIM2, CRC | Renode's own STM32 F7/F0-family models, not STM32N6 models | 0x52001000, 0x56020000, 0x50000000, 0x56024C00 |
| RAM | code 0x34000000, data 0x34100000, retained `.noinit` 0x341F0000 | |

Limits, to be stated with every result:
- It is not the silicon: no clock tree (fixed 200 MHz timer and USART clock, 50 MHz WWDG clock, 32 kHz IWDG clock), no
  oscillator tolerance, no security filtering, no early-wakeup interrupts, register updates take effect at once.
- It is **not cycle accurate**: instruction timing, wait states, execution-time limits and processor load cannot be shown.
- There is no board: pins are logical levels only. Memory holds the code in RAM, not in flash.
- RAM content is kept over every simulated reset; whether a region is retained on the device is not shown.
