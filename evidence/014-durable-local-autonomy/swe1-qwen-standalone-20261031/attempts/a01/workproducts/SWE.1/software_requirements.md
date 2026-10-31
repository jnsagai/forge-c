# Software requirements

Software requirements of the CRC LL driver for this work order. Scope: Write and read the general-purpose 32-bit independent data register (CRC_IDR.IDR), using only LL_CRC_Write_IDR and LL_CRC_Read_IDR. Caller supplies a valid CRC peripheral instance with the register interface accessible; caller-owned clock, power, security and access setup is a precondition, not implemented or inferred by these LL functions. Within this slice no LL call occurs automatically at startup, no status-flag polling or error return is specified for valid accessible calls, and invalid pointers or inaccessible hardware are outside the supported invocation domain. Out of scope: CRC calculation/feed, polynomial configuration, initial CRC value, reversal, calculation-unit reset, DMA, HAL, other LL functions and autonomous factory modification.

- **SWR-001** When the caller invokes LL_CRC_Write_IDR on a valid CRC peripheral instance with a 32-bit data value, the CRC LL driver shall write the supplied 32-bit value to CRC_IDR.IDR.
  - Source: RM0486 p.1172
  - Verification: A host unit test invokes LL_CRC_Write_IDR with the 32-bit pattern 0xDEADBEEF on a valid CRC instance; the test passes when the CRC_IDR.IDR register array contains 0xDEADBEEF after the call.
- **SWR-002** When the caller invokes LL_CRC_Read_IDR on a valid CRC peripheral instance, the CRC LL driver shall return the current 32-bit value of CRC_IDR.IDR.
  - Source: RM0486 p.1172
  - Verification: A host unit test writes the 32-bit pattern 0x12345678 into the CRC_IDR.IDR register array, then invokes LL_CRC_Read_IDR on the valid CRC instance; the test passes when the returned value equals the pattern stored in the CRC_IDR.IDR register array.
- **SWR-003** While no LL function has been called after reset, the CRC LL driver shall not write any register.
  - Source: RM0486 p.1170
  - Verification: A target test resets the device, performs no LL function calls, reads CRC_IDR, and compares against the documented reset value; the test passes when CRC_IDR.IDR equals its reset value and no register write is observed after reset without an LL call.
- **SWR-004** When the caller invokes LL_CRC_Write_IDR or LL_CRC_Read_IDR on a valid CRC peripheral instance, the CRC LL driver shall complete the operation without polling any status flag.
  - Source: RM0486 p.1170
  - Verification: A host unit test calls LL_CRC_Write_IDR and LL_CRC_Read_IDR with a valid instance, instruments the code path for any loop or wait on a flag register, and asserts zero flag-poll iterations; the test passes when no status-flag polling loop executes in either function.
- **SWR-005** When the caller invokes LL_CRC_Write_IDR on a valid CRC peripheral instance, the CRC LL driver shall modify only the IDR field of CRC_IDR.
  - Source: RM0486 p.1170
  - Verification: A host unit test captures the memory address and bit mask used by LL_CRC_Write_IDR and asserts the address maps to CRC_IDR and the mask is limited to bits [31:0] of IDR; the test passes when the write operation targets only CRC_IDR.IDR and no other register address or bit range is written.
- **SWR-006** The CRC LL driver shall occupy at most 4096 bytes of flash.
  - Source: work-order budget (owner development target)
  - Verification: SWE.6 Robot suite checks the target linker map, size-tool and stack-usage evidence of the driver image; passes when the driver flash usage is at most 4096 bytes.
- **SWR-007** The CRC LL driver shall use at most 64 bytes of static RAM.
  - Source: work-order budget (owner development target)
  - Verification: SWE.6 Robot suite checks the target linker map, size-tool and stack-usage evidence of the driver image; passes when the driver-owned data and BSS total at most 64 bytes, excluding the externally provided register array.
- **SWR-008** The CRC LL driver shall use at most 128 bytes of stack for any public API call.
  - Source: work-order budget (owner development target)
  - Verification: SWE.6 Robot suite checks the target linker map, size-tool and stack-usage evidence of the driver image; passes when the worst-case stack usage of every public API call chain is at most 128 bytes.
- **SWR-009** When a scoped API is measured in the pinned Renode profile at 100 MIPS without injected interrupts or bus stalls, the CRC LL driver shall complete each measured call within 64 executed target instructions.
  - Source: work-order simulation-only performance allocation; not a reference-manual or silicon timing claim
  - Verification: SWE.6 Robot checks the independent Renode entry/return instruction and virtual-time records for every scoped function; missing, incomplete or over-budget measurements fail. Run Target Scenario on the declared test, then Simulation Performance Should Meet Budget; no hardware WCET is established.
- **SWR-010** When a scoped API is measured in the pinned Renode profile at 100 MIPS without injected interrupts or bus stalls, the CRC LL driver shall complete each measured call within 100 microseconds of virtual time.
  - Source: work-order simulation-only performance allocation; not a reference-manual or silicon timing claim
  - Verification: SWE.6 Robot checks the independent Renode entry/return instruction and virtual-time records for every scoped function; missing, incomplete or over-budget measurements fail. Run Target Scenario on the declared test, then Simulation Performance Should Meet Budget; no hardware WCET is established.

## Open points

- Upstream inputs (HSI contract, safety allocation, budgets): NOT_PROVIDED.
- Safety allocation as stated in the manifest: OUT_OF_SCOPE: QM development selected by the owner. No software safety requirements, allocated safety safe state or safety assurance are required. Functional requirements, startup/error behavior, resource constraints, traceability and verification remain required..
- Target silicon revision: UNSPECIFIED.
- Flash, static RAM and stack limits: development targets set by the work-order owner (2026-10-15), reused for the feature 015 benchmark set (2026-10-25).
