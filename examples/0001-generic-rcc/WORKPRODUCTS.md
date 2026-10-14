# Generic RCC example — draft workproducts (NOT ASIL B)

**Baseline:** `OSS-V0.1-DEMO`, **Safety allocation:** not available, **MCU:** fictional generic RCC-style device, **Review state:** not approved. These are educational example items only; use `templates/` for a real project.

## SWE.1 software requirements (demonstration)

| ID | Text | Acceptance criterion |
|---|---|---|
| DEMO-SR-001 | Invalid context/register pointers shall cause an error return with no MMIO access. | null-pointer negative tests pass |
| DEMO-SR-002 | A zero mask or any bit outside the permitted mask shall be rejected with no MMIO access. | invalid-mask tests pass |
| DEMO-SR-003 | Clock enable shall preserve unrelated register bits. | bitmask merge tests pass |
| DEMO-SR-004 | Reset pulse shall write selected bitmask to assert then release registers. | final host register values; ordering not proven |

## SWE.2 architecture

A single C module (`forge_rcc_demo`) operates on one caller-owned context and an injected memory-mapped register structure. No driver-owned global state, recursion, dynamic memory allocation or background execution. Hardware interaction consists of one read-modify-write of `clock_enable`, or two sequential writes of `reset_assert` and `reset_release`. HSI limits: exclusive access and no concurrent writers; approved real hardware contract is missing.

## SWE.3 detailed design / implementation

- `forge_rcc_demo_init`: validates pointers and nonzero mask; stores register pointer + allowed bits.
- `forge_rcc_demo_enable_clock`: validates bits; read-modify-writes enable register.
- `forge_rcc_demo_reset_pulse`: validates bits; writes assert and release registers.

Implementation: `drivers/demo_rcc/include/forge_rcc_demo.h` and `drivers/demo_rcc/src/forge_rcc_demo.c`.

## SWE.4 unit verification

`tests/c/test_forge_rcc_demo.c` performs native C assertion tests with compiler `-UNDEBUG`; `./scripts/run_oss_demo.sh` runs CTest with Clang/LLVM instrumentation and creates a hashed log. The report may achieve 100% region, branch and MC/DC **for this small demo** but is not target MC/DC evidence.

## SWE.5 / SWE.6

**OPEN:** no actual external component integration, silicon driver behavior, HIL, or independent software requirements verification. A host test of a fake register layout is not an integration test with a real clock/reset peripheral.

## ISO 26262 / ASIL B

**OPEN:** allocated safety requirements, safe state, hazard analysis, dependency/FFI analysis, hardware contract, tool-confidence evaluation, approved coding standard assessment and independence/signoff. No ASIL claim is made.

## Minimal trace (draft, to be reviewed)

| Requirement | C interface | Native test group | Coverage source |
|---|---|---|---|
| DEMO-SR-001 | `forge_rcc_demo_init`, both operations | `test_init_and_invalid_args`, `test_reset_pulse_and_invalid_context` | host LLVM log |
| DEMO-SR-002 | all operations | `test_clock_enable_masks`, `test_reset_pulse_and_invalid_context` | host LLVM log |
| DEMO-SR-003 | `forge_rcc_demo_enable_clock` | `test_clock_enable_masks` | host LLVM log |
| DEMO-SR-004 | `forge_rcc_demo_reset_pulse` | `test_reset_pulse_and_invalid_context` | **only last values; bus ordering missing** |
