# Generic RCC-style Register Driver — Educational Technical Slice

**This is an invented peripheral register model, NOT an STM32N6 register map or hardware driver.** No MCU addresses/bit meanings or silicon errata are asserted. Its purpose is to exercise a real code-to-test-to-coverage pipeline with the least dependencies.

## Proposed demonstration requirements (not approved safety requirements)

| ID | Requirement | Verification |
|---|---|---|
| DEMO-SR-001 | Initialize only for non-null register and context pointers | native assertion tests |
| DEMO-SR-002 | Reject zero/unapproved mask without modifying registers | native assertion tests |
| DEMO-SR-003 | Enable selected clock bits without changing unrelated bits | native assertion tests |
| DEMO-SR-004 | Write a selected reset bitmask to assert and release registers | native assertion tests (values only) |
| DEMO-SR-005 | No heap allocation or global mutable driver state | source review + target analysis planned |

## HSI assumptions (illustrative only)

- `clock_enable` supports read-modify-write. A single writer owns updates, or caller provides externally audited mutual exclusion.
- `reset_assert` and `reset_release` are write-one-action registers with deterministic write ordering.
- Register data width is 32-bit, naturally aligned, with device-defined semantics. The **real MCU device** must independently confirm semantics, ordering barriers, reset read-back and clock propagation requirements.
- The fake host struct cannot prove bus ordering, transient reset pulse width, clock stabilization, DMA interaction, interrupt preemption, brownout or safe-state handling.
- Architectural safety allocations, freedom from interference and fault handling remain **unassigned**.

## Data and interfaces

`drivers/demo_rcc/include/forge_rcc_demo.h` holds the header; C implementation under `src/`. The caller owns the driver context, so no driver `.bss` or heap allocation is needed. The active context does occupy caller-owned RAM (pointer plus mask and alignment), which must be budgeted for the actual ABI. The masks are validated before register writes. There are no loops or dynamic allocations.

## Proof of readiness and what is missing

`./scripts/run_oss_demo.sh` establishes that a host Clang build, test runner, and LLVM structural coverage pipeline work. The demonstration cannot be reused as supplier-side evidence for ASIL B until the peripheral HSI is replaced with an approved MCU contract, unit/integration/software verification is updated, physical measurements are produced and qualified/justified safety tools and reviewers are assigned.

**Test oracle caveat:** the fake register struct only checks the final values of reset writes. To prove actual `ASSERT -> RELEASE` ordering on the bus, use a register-access capture layer, HwSim bus logger, Renode peripheral model, or real target bus trace.
