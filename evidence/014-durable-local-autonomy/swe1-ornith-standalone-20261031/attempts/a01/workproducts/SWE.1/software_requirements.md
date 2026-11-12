# Software requirements

Software requirements of the CRC LL driver for this work order. Scope: Write and read the general-purpose 32-bit independent data register (CRC_IDR.IDR), using only LL_CRC_Write_IDR and LL_CRC_Read_IDR. Caller supplies a valid CRC peripheral instance with the register interface accessible; caller-owned clock, power, security and access setup is a precondition, not implemented or inferred by these LL functions. Within this slice no LL call occurs automatically at startup, no status-flag polling or error return is specified for valid accessible calls, and invalid pointers or inaccessible hardware are outside the supported invocation domain. Out of scope: CRC calculation/feed, polynomial configuration, initial CRC value, reversal, calculation-unit reset, DMA, HAL, other LL functions and autonomous factory modification.

- **SWR-001** When the caller invokes LL_CRC_Write_IDR with a valid CRC peripheral instance, the CRC LL driver shall write the supplied 32-bit value to the IDR field of CRC_IDR.
  - Source: RM0486 p.1172
  - Verification: The test passes when LL_CRC_Write_IDR called with a supplied 32-bit value writes that value to CRC_IDR.IDR as read back from the register array, and no other register is accessed.
- **SWR-002** While the caller invokes LL_CRC_Read_IDR with a valid CRC peripheral instance, the CRC LL driver shall read the CRC_IDR register and return the current 32-bit value stored in the IDR field of CRC_IDR.
  - Source: RM0486 p.1172
  - Verification: The test passes when LL_CRC_Read_IDR called after LL_CRC_Write_IDR returns the 32-bit value previously written to CRC_IDR.IDR, matching the register array read of the IDR field.
- **SWR-003** While no LL function has been called after reset, the CRC LL driver shall not write any register.
  - Source: RM0486 p.1170
  - Verification: The test resets the CRC peripheral to its startup state and observes its registers; the test passes when no write to any register occurs during the observed window before any LL function is called.
- **SWR-004** When the caller invokes LL_CRC_Read_IDR with a valid CRC peripheral instance, the CRC LL driver shall not wait on any status flag of the CRC peripheral.
  - Source: RM0486 p.1170
  - Verification: The test invokes LL_CRC_Read_IDR with a valid peripheral instance and times the call; the test passes when the call returns without blocking on a status flag.
- **SWR-005** When the caller invokes LL_CRC_Read_IDR with a valid CRC peripheral instance, the CRC LL driver shall not return an error code for the valid accessible call.
  - Source: RM0486 p.1170
  - Verification: The test invokes LL_CRC_Read_IDR with a valid peripheral instance and a readable register state; the test passes when no error value is returned.
- **SWR-006** When the caller invokes LL_CRC_Write_IDR with a valid CRC peripheral instance, the CRC LL driver shall change only the IDR field of CRC_IDR and no other field of the register.
  - Source: RM0486 p.1170
  - Verification: The test invokes LL_CRC_Write_IDR with a known 32-bit argument; the test passes when only the IDR field of CRC_IDR is modified and no other register field changes.
- **SWR-007** The CRC LL driver shall occupy at most 4096 bytes of flash.
  - Source: work-order budget (owner development target)
  - Verification: SWE.6 Robot suite checks the target linker map, size-tool and stack-usage evidence of the driver image; passes when the driver flash usage is at most 4096 bytes.
- **SWR-008** The CRC LL driver shall use at most 64 bytes of static RAM.
  - Source: work-order budget (owner development target)
  - Verification: SWE.6 Robot suite checks the target linker map, size-tool and stack-usage evidence of the driver image; passes when the driver-owned data and BSS total at most 64 bytes, excluding the externally provided register array.
- **SWR-009** The CRC LL driver shall use at most 128 bytes of stack for any public API call.
  - Source: work-order budget (owner development target)
  - Verification: SWE.6 Robot suite checks the target linker map, size-tool and stack-usage evidence of the driver image; passes when the worst-case stack usage of every public API call chain is at most 128 bytes.
- **SWR-010** When a scoped API is measured in the pinned Renode profile at 100 MIPS without injected interrupts or bus stalls, the CRC LL driver shall complete each measured call within 64 executed target instructions.
  - Source: work-order simulation-only performance allocation; not a reference-manual or silicon timing claim
  - Verification: SWE.6 Robot checks the independent Renode entry/return instruction and virtual-time records for every scoped function; missing, incomplete or over-budget measurements fail. Run Target Scenario on the declared test, then Simulation Performance Should Meet Budget; no hardware WCET is established.
- **SWR-011** When a scoped API is measured in the pinned Renode profile at 100 MIPS without injected interrupts or bus stalls, the CRC LL driver shall complete each measured call within 100 microseconds of virtual time.
  - Source: work-order simulation-only performance allocation; not a reference-manual or silicon timing claim
  - Verification: SWE.6 Robot checks the independent Renode entry/return instruction and virtual-time records for every scoped function; missing, incomplete or over-budget measurements fail. Run Target Scenario on the declared test, then Simulation Performance Should Meet Budget; no hardware WCET is established.

## Open points

- **OP-2e788f3a39f26b77** (input scope: CRC_IDR; source section 26.4.2): The RM0486 source does not specify whether LL_CRC_Write_IDR returns any value or status, so the return-value contract of the write function is unresolved.
- **OP-5ebd70d5104715fa** (input scope: CRC_IDR; source section 26.4.2): The RM0486 source does not specify whether LL_CRC_Read_IDR returns the value directly or via an out-parameter, so the read return mechanism is unresolved.
- **OP-ac98837b08aa9fb4** (input scope: cross-cutting requirements): The source does not document any status-flag mechanism for the IDR access path, so no polling bound or error-return contract is specified beyond the absence of waiting.
- **OP-bd0ba872695d0794** (input scope: cross-cutting requirements): The RM0486 section does not indicate whether CRC_IDR is readable during a halted CPU state, so whether the read-back verification applies while the CPU is halted is left open.
- Upstream inputs (HSI contract, safety allocation, budgets): NOT_PROVIDED.
- Safety allocation as stated in the manifest: OUT_OF_SCOPE: QM development selected by the owner. No software safety requirements, allocated safety safe state or safety assurance are required. Functional requirements, startup/error behavior, resource constraints, traceability and verification remain required..
- Target silicon revision: UNSPECIFIED.
- Flash, static RAM and stack limits: development targets set by the work-order owner (2026-10-15), reused for the feature 015 benchmark set (2026-10-25).
