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

## Addendum (2026-10-15): Robot Framework for SWE.6 (owner request)
SWE.6 requirement-based verification uses **Robot Framework 6.1** (Apache-2.0, the version Renode 1.17.0 pins,
hash-locked in `requirements/forge-factory.lock`).
- **Suite:** the SWE.6 author writes one suite `software/tests/software/test_rcc_requirements.robot` with one test
  per SWR (`[Tags] SWR-nnn`), plus small C scenario files.
- **Keywords:** the deterministic `ForgeTarget` library (`factory/sim/stm32n6/ForgeTarget.py`) provides
  `Run Target Scenario` (build + run on the Renode model, `scenario=never_ready` for timeouts),
  `Target Check Should Pass`, `All Target Checks Should Pass`, and `Driver Flash Size / Static RAM Should Be At
  Most` (measured from target objects).
- **Execution:** `forge-tests-mcp.run_robot` (v0.5 overlay op, granted to the SWE.6 author and inspector) runs the
  suites and parses `output.xml`. It passes only if every test passes and every SWE.1 requirement is the tag of a
  passing test. `log.html`, `report.html` and `output.xml` stay as evidence.
- **Gating:** the SWE.6 gate requires that PASS before freeze, and the release check `software_verification`
  includes it.
- **Scope:** the same simulated-target limits as above apply; this is not silicon verification.
