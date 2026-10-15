# ADR-0007: Renode target simulation for the STM32N6 RCC driver

- **Status:** Accepted (2026-10-15, user-requested) · **Tasks:** 002 T015 (forge-sim-mcp), 001 T-014 (partial)
- **Tool:** Renode 1.17.0, MIT licence. Portable Linux build `renode-1.17.0.linux-portable.tar.gz`, sha256
  `4ba7c68b…5a5f` (GitHub release digest, verified). Installed without sudo at
  `$FORGE_DATA_ROOT/toolchains/renode/renode_1.17.0-portable`.

## Context
Packages were BLOCKED on `target_verification`, and no STM32N6 board is available. Renode 1.17.0 ships no
STM32N6 platform. Its `CPU.CortexM` model accepts `cpuType: "cortex-m55"` (verified).

## Decision
`factory/sim/stm32n6/` provides a deliberately minimal, explicit platform:
- **Hardware model:** a Cortex-M55 CPU, NVIC, AXISRAM at 0x34000000, and a *behavioural* RCC Python peripheral
  at the RM0486 base 0x56028000.
  - In the default scenario, each `RCC_SR` ready flag follows its `RCC_CR` enable bit (HSI/HSE/MSI/LSE/LSI and
    PLL1–4, same bit positions).
  - In the `never_ready` scenario, the ready flags stay 0, so timeout paths are exercised.
  - All other registers are plain storage.
- **Test images:** a RAM-resident image (startup, linker script that places `ll_rcc_regs` at the RCC base) plus
  a mailbox harness (`TCHECK`, results at 0x341F0000).
- **Execution:** `forge-sim-mcp run_renode` builds every `software/tests/target/test_*.c` with the driver for
  Cortex-M55. Files named `*_timeout.c` run under the never-ready model. The operation runs Renode headless,
  reads the mailbox, and passes only if every image completes with checks passed and 0 failed.
- **Sandbox settings for .NET:** `DOTNET_EnableWriteXorExecute=0` (the W^X double-map file trips
  RLIMIT_FSIZE) and `DOTNET_GCHeapHardLimit=0x60000000` (keeps the GC reservation within RLIMIT_AS).
- **Evidence labels:** results are marked `target_evidence: simulated` and `silicon_verified: false`.

## Limitations (honest scope)
- The RCC model reproduces register semantics *as this ADR states them*, not the silicon. It has no clock-tree
  timing, no security/privilege filtering, no set/clear registers and no errata.
- It is evidence that the driver logic behaves correctly on the target ISA against the modelled register
  contract. It does **not** replace hardware verification on a representative board (001 T-014 stays open).
