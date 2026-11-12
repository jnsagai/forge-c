# Simulation-only IDR requirements — draft for actual owner review

Status: **REVIEW_PENDING**. This preview is not a frozen or inspected SWE.1 baseline.
Candidate payload SHA-256: af48340bdc64510347f2aa236114b601f86ad24a0fbd062e82f07e4eed770463

Functional scope and the original ST/CMSIS delivery are unchanged. New allocations are simulation-only project targets; no hardware WCET, safety assurance or assessed ASPICE compliance is claimed.

- **SWR-001** When the caller invokes write-IDR with a value and a valid accessible CRC instance, the CRC LL driver shall write the supplied 32-bit value to CRC_IDR.IDR.
  - Source: RM0486 section26.4.2 p.1172
  - Verification: Host and target tests pass when zero, all ones and alternating values reach all 32 CRC_IDR.IDR bits without changing unrelated registers.
- **SWR-002** When the caller invokes read-IDR with a valid accessible CRC instance, the CRC LL driver shall return the current 32-bit value of CRC_IDR.IDR.
  - Source: RM0486 section26.4.2 p.1172
  - Verification: Independent read tests preset IDR without the write API and pass when all 32 bits are returned and no register changes.
- **SWR-003** While no LL function has been called after reset, the CRC LL driver shall not write any CRC register.
  - Source: RM0486 section26.4.2 p.1172
  - Verification: Target startup observation passes when no driver write occurs before an explicit IDR call.
- **SWR-004** When either scoped IDR function is invoked with a valid accessible CRC instance, the CRC LL driver shall complete without polling a status flag.
  - Source: RM0486 section26.4.2 p.1172
  - Verification: Source/control-flow review and bounded host/target execution pass when the IDR functions contain no status-polling loop.
- **SWR-005** The CRC LL driver shall occupy at most 4096 bytes of flash.
  - Source: work-order budget (owner development target)
  - Verification: SWE.6 Robot suite checks the target linker map, size-tool and stack-usage evidence of the driver image; passes when the driver flash usage is at most 4096 bytes.
- **SWR-006** The CRC LL driver shall use at most 64 bytes of static RAM.
  - Source: work-order budget (owner development target)
  - Verification: SWE.6 Robot suite checks the target linker map, size-tool and stack-usage evidence of the driver image; passes when the driver-owned data and BSS total at most 64 bytes, excluding the externally provided register array.
- **SWR-007** The CRC LL driver shall use at most 128 bytes of stack for any public API call.
  - Source: work-order budget (owner development target)
  - Verification: SWE.6 Robot suite checks the target linker map, size-tool and stack-usage evidence of the driver image; passes when the worst-case stack usage of every public API call chain is at most 128 bytes.
- **SWR-008** When a scoped API is measured in the pinned Renode profile at 100 MIPS without injected interrupts or bus stalls, the CRC LL driver shall complete each measured call within 64 executed target instructions.
  - Source: work-order simulation-only performance allocation; not a reference-manual or silicon timing claim
  - Verification: SWE.6 Robot checks the independent Renode entry/return instruction and virtual-time records for every scoped function; missing, incomplete or over-budget measurements fail. Run Target Scenario on the declared test, then Simulation Performance Should Meet Budget; no hardware WCET is established.
- **SWR-009** When a scoped API is measured in the pinned Renode profile at 100 MIPS without injected interrupts or bus stalls, the CRC LL driver shall complete each measured call within 100 microseconds of virtual time.
  - Source: work-order simulation-only performance allocation; not a reference-manual or silicon timing claim
  - Verification: SWE.6 Robot checks the independent Renode entry/return instruction and virtual-time records for every scoped function; missing, incomplete or over-budget measurements fail. Run Target Scenario on the declared test, then Simulation Performance Should Meet Budget; no hardware WCET is established.

The existing valid-accessible-instance/caller responsibilities and unsupported invalid-pointer/hardware-fault domain remain unchanged. Renode uses the pinned Cortex-M55 behavioural profile at100MIPS without injected interrupts/bus stalls; measured entry-to-return cost is simulation evidence only.

Adoption requires actual review of this complete updated payload. Runtime execution also requires host availability and a current source-bound grant. The old grant expired29Oct05:00UTC; it is not renewed here.
