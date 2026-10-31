# Software requirements

Software requirements of the CRC LL driver for this work order. Scope: Write and read the general-purpose 32-bit independent data register (CRC_IDR.IDR), using only LL_CRC_Write_IDR and LL_CRC_Read_IDR. Caller supplies a valid CRC peripheral instance with the register interface accessible; caller-owned clock, power, security and access setup is a precondition, not implemented or inferred by these LL functions. Within this slice no LL call occurs automatically at startup, no status-flag polling or error return is specified for valid accessible calls, and invalid pointers or inaccessible hardware are outside the supported invocation domain. Out of scope: CRC calculation/feed, polynomial configuration, initial CRC value, reversal, calculation-unit reset, DMA, HAL, other LL functions and autonomous factory modification.

- **SWR-001** When the caller invokes LL_CRC_Write_IDR with a valid CRC peripheral instance, the CRC LL driver shall write the supplied 32-bit value to CRC_IDR.IDR.
  - Source: RM0486 p.1172
  - Verification: The test calls LL_CRC_Write_IDR with a 32-bit value on a valid accessible CRC instance and passes when CRC_IDR.IDR reads back the supplied value.
- **SWR-002** When the caller invokes LL_CRC_Read_IDR on a valid CRC peripheral instance, the CRC LL driver shall read the current 32-bit value of CRC_IDR.IDR and return it.
  - Source: RM0486 p.1172
  - Verification: The test invokes LL_CRC_Read_IDR on a valid accessible CRC instance and passes when the returned value equals the current value of CRC_IDR.IDR.
- **SWR-003** While no LL function has been called after reset, the CRC LL driver shall not write any register.
  - Source: RM0486 p.1170
  - Verification: No LL call is invoked at startup; the test passes when no register write to any CRC register occurs before the first explicit function call.
- **SWR-004** The CRC LL driver shall occupy at most 4096 bytes of flash.
  - Source: work-order budget (owner development target)
  - Verification: SWE.6 Robot suite checks the target linker map, size-tool and stack-usage evidence of the driver image; passes when the driver flash usage is at most 4096 bytes.
- **SWR-005** The CRC LL driver shall use at most 64 bytes of static RAM.
  - Source: work-order budget (owner development target)
  - Verification: SWE.6 Robot suite checks the target linker map, size-tool and stack-usage evidence of the driver image; passes when the driver-owned data and BSS total at most 64 bytes, excluding the externally provided register array.
- **SWR-006** The CRC LL driver shall use at most 128 bytes of stack for any public API call.
  - Source: work-order budget (owner development target)
  - Verification: SWE.6 Robot suite checks the target linker map, size-tool and stack-usage evidence of the driver image; passes when the worst-case stack usage of every public API call chain is at most 128 bytes.
- **SWR-007** When a scoped API is measured in the pinned Renode profile at 100 MIPS without injected interrupts or bus stalls, the CRC LL driver shall complete each measured call within 64 executed target instructions.
  - Source: work-order simulation-only performance allocation; not a reference-manual or silicon timing claim
  - Verification: SWE.6 Robot checks the independent Renode entry/return instruction and virtual-time records for every scoped function; missing, incomplete or over-budget measurements fail. Run Target Scenario on the declared test, then Simulation Performance Should Meet Budget; no hardware WCET is established.
- **SWR-008** When a scoped API is measured in the pinned Renode profile at 100 MIPS without injected interrupts or bus stalls, the CRC LL driver shall complete each measured call within 100 microseconds of virtual time.
  - Source: work-order simulation-only performance allocation; not a reference-manual or silicon timing claim
  - Verification: SWE.6 Robot checks the independent Renode entry/return instruction and virtual-time records for every scoped function; missing, incomplete or over-budget measurements fail. Run Target Scenario on the declared test, then Simulation Performance Should Meet Budget; no hardware WCET is established.

## Open points

- **OP-33d78b12ee1af8ba** (input scope: CRC_IDR; source section 26.4.2): The source specifies CRC_IDR.IDR as bits 31:0 with reset value 0x0000 0000 but does not require any requirement for the reset value within this write/read slice, so no reset/startup requirement is generated here.
- **OP-b911bc936110a35f** (input scope: cross-cutting requirements): No failure-handling or error-return contract is specified, as invalid pointers and inaccessible hardware fall outside the supported invocation domain defined by the work order.
- **OP-ab553c2573d3e2ee** (input scope: cross-cutting requirements): Caller-owned clock, power, security and register-access setup is a precondition and is not specified or verified by these LL functions.
- **OP-c93b0603aa6dc8da** (input scope: cross-cutting requirements): The write and read of CRC_IDR.IDR are covered by the CRC_IDR task and are outside the scope of this cross-cutting work order slice.
- Upstream inputs (HSI contract, safety allocation, budgets): NOT_PROVIDED.
- Safety allocation as stated in the manifest: OUT_OF_SCOPE: QM development selected by the owner. No software safety requirements, allocated safety safe state or safety assurance are required. Functional requirements, startup/error behavior, resource constraints, traceability and verification remain required..
- Target silicon revision: UNSPECIFIED.
- Flash, static RAM and stack limits: development targets set by the work-order owner (2026-10-15), reused for the feature 015 benchmark set (2026-10-25).
