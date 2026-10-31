# Software requirements

Software requirements of the CRC LL driver for this work order. Scope: Write and read the general-purpose 32-bit independent data register (CRC_IDR.IDR), using only LL_CRC_Write_IDR and LL_CRC_Read_IDR. Caller supplies a valid CRC peripheral instance with the register interface accessible; caller-owned clock, power, security and access setup is a precondition, not implemented or inferred by these LL functions. Within this slice no LL call occurs automatically at startup, no status-flag polling or error return is specified for valid accessible calls, and invalid pointers or inaccessible hardware are outside the supported invocation domain. Out of scope: CRC calculation/feed, polynomial configuration, initial CRC value, reversal, calculation-unit reset, DMA, HAL, other LL functions and autonomous factory modification.

- **SWR-001** When LL_CRC_Write_IDR is called with a valid accessible CRC peripheral instance and a 32-bit value, the CRC LL driver shall write the supplied 32-bit value to CRC_IDR.IDR.
  - Source: RM0486 p.1172
  - Verification: A host unit test passes when the register-array CRC_IDR.IDR equals the supplied 32-bit value after LL_CRC_Write_IDR is called.
- **SWR-002** When LL_CRC_Read_IDR is called with a valid accessible CRC peripheral instance, the CRC LL driver shall return the current 32-bit value of CRC_IDR.IDR.
  - Source: RM0486 p.1172
  - Verification: A host unit test passes when the return value of LL_CRC_Read_IDR equals the register-array CRC_IDR.IDR value.
- **SWR-003** While no LL function has been called after reset, the CRC LL driver shall not write any register.
  - Source: RM0486 p.1170
  - Verification: Reset/startup robot test passes when, after reset and before any LL function call, no CRC register write is observed.
- **SWR-004** When LL_CRC_Write_IDR or LL_CRC_Read_IDR is called with a valid accessible CRC peripheral instance, the CRC LL driver shall not wait on any status flag.
  - Source: RM0486 p.1170
  - Verification: Status-flag test passes when each function is called once with a valid accessible instance and neither call waits on a status flag before completing.
- **SWR-005** When LL_CRC_Read_IDR is called with a valid accessible CRC peripheral instance, the CRC LL driver shall not write any register.
  - Source: RM0486 p.1170
  - Verification: Read side-effect test passes when LL_CRC_Read_IDR is called with a valid accessible instance and no CRC register write is observed.
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
