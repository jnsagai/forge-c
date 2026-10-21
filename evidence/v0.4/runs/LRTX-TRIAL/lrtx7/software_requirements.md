# Software requirements

Software requirements of the IWDG LL driver for this work order. Scope: LL (header-only, static inline): read/write IWDG registers through the generated register-block array ll_iwdg_regs (extern; placed at the IWDG base by the linker, defined in RAM by host tests), indexed by the generated LL_IWDG_<REG>_OFFSET / 4U Start the watchdog and refresh the counter by writing the documented keys to IWDG_KR; enable and disable write access to IWDG_PR, IWDG_RLR and IWDG_WINR with the documented keys Set the prescaler (IWDG_PR.PR) and the reload value (IWDG_RLR.RL); query the update flags in IWDG_SR (PVU, RVU) and the watchdog enable status (ONF) (no waiting: the caller bounds its polling) Out of scope: HAL API, window option (IWDG_WINR), early wake-up interrupt (IWDG_EWCR, IWDG_ICR), hardware watchdog option bytes, low-power freeze, debug freeze

- **SWR-001** When the IWDG LL driver starts the watchdog, the IWDG LL driver shall write the start key 0x0000CCCC to IWDG_KR.KEY.
  - Source: RM0486 p.2989
  - Verification: The test passes when the IWDG_KR.KEY field is written with value 0xCCCC.
- **SWR-002** When the IWDG LL driver refreshes the watchdog counter, the IWDG LL driver shall write the refresh key 0x0000AAAA to IWDG_KR.KEY.
  - Source: RM0486 p.2989
  - Verification: The test passes when the IWDG_KR.KEY field is written with value 0xAAAA.
- **SWR-003** When the IWDG LL driver enables write access to IWDG_PR and IWDG_RLR, the IWDG LL driver shall write the enable key 0x00005555 to IWDG_KR.KEY.
  - Source: RM0486 p.2989
  - Verification: The test passes when the IWDG_KR.KEY field is written with value 0x5555.
- **SWR-004** When the IWDG LL driver disables write access to IWDG_PR and IWDG_RLR, the IWDG LL driver shall write a key value other than 0x5555 to IWDG_KR.KEY.
  - Source: RM0486 p.2989
  - Verification: The test passes when the IWDG_KR.KEY field is written with a value different from 0x5555 (e.g., 0x00000000).
- **SWR-005** The IWDG LL driver shall write a prescaler value to the IWDG_PR.PR field, where the value is within the 4-bit range of 0x0 to 0xF.
  - Source: RM0486 p.2990
  - Verification: The test passes when the IWDG_PR.PR register field is written with a valid prescaler divider value from 0x0 to 0xF in the ll_iwdg_regs array.
- **SWR-006** The IWDG LL driver shall read the prescaler divider value from the IWDG_PR.PR field.
  - Source: RM0486 p.2990
  - Verification: The test passes when the value returned by a function reading IWDG_PR.PR matches with the value set in the ll_iwdg_regs array.
- **SWR-007** The IWDG LL driver shall write the requested value to IWDG_RLR.RL when the function that sets the watchdog reload value is called.
  - Source: RM0486 p.2990
  - Verification: A host unit test passes when the IWDG_RLR register in the ll_iwdg_regs array contains the value written by the function, and the function returns without error.
- **SWR-008** The IWDG LL driver shall not write to IWDG_RLR.RL if write access is not previously enabled by writing 0x5555 to IWDG_KR.KEY.
  - Source: RM0486 p.2990
  - Verification: A host unit test passes when attempting to write without enabling access results in no change to IWDG_RLR.RL and an appropriate error code returned.
- **SWR-009** The IWDG LL driver shall return 1U when the IWDG_SR.EWIF field is set, else 0U.
  - Source: RM0486 p.2991
  - Verification: The host unit test passes when the IWDG_SR.EWIF bit is set in the ll_iwdg_regs array and the function returns 1U, or when the bit is cleared and the function returns 0U.
- **SWR-010** The IWDG LL driver shall return 1U when the IWDG_SR.ONF field is set, else 0U.
  - Source: RM0486 p.2991
  - Verification: The host unit test passes when the IWDG_SR.ONF bit is set in the ll_iwdg_regs array and the function returns 1U, or when the bit is cleared and the function returns 0U.
- **SWR-011** The IWDG LL driver shall return 1U when the IWDG_SR.EWU field is set, else 0U.
  - Source: RM0486 p.2991
  - Verification: The host unit test passes when the IWDG_SR.EWU bit is set in the ll_iwdg_regs array and the function returns 1U, or when the bit is cleared and the function returns 0U.
- **SWR-012** The IWDG LL driver shall set the IWDG_SR.WVU bit when a window value update operation is initiated.
  - Source: RM0486 p.2994
  - Verification: The test passes when the IWDG_SR.WVU bit is set after initiating a window value update operation through the IWDG_WINR register.
- **SWR-013** The IWDG LL driver shall set the IWDG_SR.RVU bit when a reload value update operation is initiated.
  - Source: RM0486 p.2994
  - Verification: The test passes when the IWDG_SR.RVU bit is set after initiating a reload value update operation through the IWDG_RLR register.
- **SWR-014** The IWDG LL driver shall set the IWDG_SR.PVU bit when a prescaler value update operation is initiated.
  - Source: RM0486 p.2994
  - Verification: The test passes when the IWDG_SR.PVU bit is set after initiating a prescaler value update operation through the IWDG_PR register.
- **SWR-015** While no LL function has been called after reset, the IWDG LL driver shall not write any IWDG register.
  - Source: RM0486 p.2980
  - Verification: target_robot_test passes when no IWDG register writes occur before any LL function call
- **SWR-016** The IWDG LL driver shall ensure that a write operation affects only the named bits within a register.
  - Source: RM0486 p.2980
  - Verification: host_unit_test passes when write operations modify only specified bits in target registers
- **SWR-017** The IWDG LL driver shall occupy at most 4096 bytes of flash.
  - Source: work-order budget (owner development target)
  - Verification: SWE.6 Robot suite checks the target linker map, size-tool and stack-usage evidence of the driver image; passes when the driver flash usage is at most 4096 bytes.
- **SWR-018** The IWDG LL driver shall use at most 64 bytes of static RAM.
  - Source: work-order budget (owner development target)
  - Verification: SWE.6 Robot suite checks the target linker map, size-tool and stack-usage evidence of the driver image; passes when the driver-owned data and BSS total at most 64 bytes, excluding the externally provided register array.
- **SWR-019** The IWDG LL driver shall use at most 128 bytes of stack for any public API call.
  - Source: work-order budget (owner development target)
  - Verification: SWE.6 Robot suite checks the target linker map, size-tool and stack-usage evidence of the driver image; passes when the worst-case stack usage of every public API call chain is at most 128 bytes.

## Open points

- HSI contract is NOT_PROVIDED in the manifest, creating a gap in traceability as per upstream_gaps.md.
- Upstream inputs (HSI contract, safety allocation, budgets): NOT_PROVIDED.
- Safety allocation as stated in the manifest: ASIL B (SC-IWDG-2026-10-20, approved by Jefferson Nascimento on 2026-10-20); software safety allocation PENDING owner allocation review.
- Target silicon revision: UNSPECIFIED.
- Flash, static RAM and stack limits: development targets set by the work-order owner (2026-10-15).
