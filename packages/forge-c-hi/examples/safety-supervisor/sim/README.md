# Simulator platform of the Safety Supervisor demo

A combined Cortex-M55 platform for Renode 1.17: `run_sim.sh <program.c>` builds one target program with the product
sources and runs it. Self-tests: `selftest/test_platform.c` (watchdogs, reset flags), `test_interrupts.c` (TIM2 and
USART1 interrupts, received characters), `test_rearm.c` (two TIM2 compare channels re-armed independently), `test_image.c` (image layout and stored
references), `test_levels.c` (software-pended exceptions and their nesting).

For the author of a test program:
- `main()` is yours and stands for the boot code and the application (the product is all of `src/`); `startup.c` gives the vector table. Define `TIM2_IRQHandler`, `USART1_IRQHandler`,
  `SysTick_Handler`, `PendSV_Handler`, `SVC_Handler`, `SPARE0_IRQHandler` or `SPARE1_IRQHandler` to receive that
  exception (interrupts 116, 159, and 117 and 118, which only software pends; CON-SUP-188); any other exception stops the program. A reset starts `main()` again with `.noinit` data kept, so one program can check the
  boots before and after a reset.
- Print `HI-TEST <case id> PASS` or `HI-TEST <case id> FAIL <reason>` on USART1. The run lasts `SIM_SECONDS` (default 5).
- Optional `<program>.uart` next to the program: lines of `<microseconds> <text>`; after that much more simulated time
  the text and a line feed are received by USART1 at 115200 baud.
- Linker symbols: `__app_start`, `__app_end`, `__app_crc`, `__cfg_start`, `__cfg_end`, `__cfg_crc`, `__task_table`,
  `__noinit_start`, `__noinit_end` (4096 bytes for the supervisor's retained data, CON-SUP-193).
  Put configuration data in section `.cfg`, the task table in `.task_table`, a test's own retained data in `.noinit`. The stored
  references are filled in after linking (CRC-32/MPEG-2). Code and configuration are in RAM here, so a test can corrupt them.

| Part | Model | Secure base |
|---|---|---|
| IWDG, WWDG, RCC reset flags (RCC_RSR), TIM2 | `HiStm32n6Watchdogs.cs`, written for this demo from the register behaviour in the reference manual. TIM2 is a free-running counter with compare flags only | 0x56004800, 0x50002C00, 0x56028000, 0x50000000 |
| USART1, GPIOA, CRC | Renode's own STM32 F7/F0-family models, not STM32N6 models | 0x52001000, 0x56020000, 0x56024C00 |
| RAM | code 0x34000000, data 0x34100000, retained `.noinit` 0x34200000 (AXISRAM3, CON-SUP-194) | |

Limits, to be stated with every result:
- It is not the silicon: no clock tree (fixed 200 MHz timer and USART clock, 50 MHz WWDG clock, 32 kHz IWDG clock), no
  oscillator tolerance, no security filtering, no early-wakeup interrupts, register updates take effect at once.
- It is **not cycle accurate**. Every instruction takes the same virtual time: 50 million per second, i.e. an assumed 4
  clock cycles per instruction at 200 MHz. Times measured on it are exact instruction counts under that assumption
  (CON-SUP-167), which nobody has confirmed on hardware.
- There is no board: pins are logical levels only. Memory holds the code in RAM, not in flash.
- RAM content is kept over every simulated reset; whether a region is retained on the device is not shown.
