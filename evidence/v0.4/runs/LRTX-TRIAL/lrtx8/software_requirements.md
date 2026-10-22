# Software requirements

Software requirements of the IWDG LL driver for this work order. Scope: LL (header-only, static inline): read/write IWDG registers through the generated register-block array ll_iwdg_regs (extern; placed at the IWDG base by the linker, defined in RAM by host tests), indexed by the generated LL_IWDG_<REG>_OFFSET / 4U Start the watchdog and refresh the counter by writing the documented keys to IWDG_KR; enable and disable write access to IWDG_PR, IWDG_RLR and IWDG_WINR with the documented keys Set the prescaler (IWDG_PR.PR) and the reload value (IWDG_RLR.RL); query the update flags in IWDG_SR (PVU, RVU) and the watchdog enable status (ONF) (no waiting: the caller bounds its polling) Out of scope: HAL API, window option (IWDG_WINR), early wake-up interrupt (IWDG_EWCR, IWDG_ICR), hardware watchdog option bytes, low-power freeze, debug freeze

- **SWR-001** When the IWDG LL driver is to start the watchdog, the IWDG LL driver shall write the value 0xCCCC to IWDG_KR.KEY.
  - Source: RM0486 p.2989
  - Verification: The test passes when the IWDG_KR.KEY field in the ll_iwdg_regs array is set to 0xCCCC after calling the start function.
- **SWR-002** When the IWDG LL driver is to refresh the watchdog counter, the IWDG LL driver shall write the value 0xAAAA to IWDG_KR.KEY.
  - Source: RM0486 p.2989
  - Verification: The test passes when the IWDG_KR.KEY field in the ll_iwdg_regs array is set to 0xAAAA after calling the refresh function.
- **SWR-003** When the IWDG LL driver is to enable write access to IWDG_PR and IWDG_RLR, the IWDG LL driver shall write the value 0x5555 to IWDG_KR.KEY.
  - Source: RM0486 p.2989
  - Verification: The test passes when the IWDG_KR.KEY field in the ll_iwdg_regs array is set to 0x5555 after calling the enable write access function.
- **SWR-004** When the IWDG LL driver is to disable write access to IWDG_PR and IWDG_RLR, the IWDG LL driver shall write any value other than 0x5555 to IWDG_KR.KEY.
  - Source: RM0486 p.2989
  - Verification: The test passes when the IWDG_KR.KEY field in the ll_iwdg_regs array is set to a value other than 0x5555 after calling the disable write access function.
- **SWR-005** The IWDG LL driver shall set IWDG_PR.PR to the requested prescaler value, which is within the 4-bit range 0x0 to 0xF.
  - Source: RM0486 p.2990
  - Verification: The test passes when the function writes the caller-supplied prescaler value to IWDG_PR.PR, and the actual value read back from IWDG_PR.PR matches the requested value.
- **SWR-006** The IWDG LL driver shall write the caller-supplied reload value to IWDG_RLR.RL, which is within the 12-bit range.
  - Source: RM0486 p.2990
  - Verification: The host unit test passes when the function writes the expected reload value to the IWDG_RLR register and the value is correctly represented in the ll_iwdg_regs array at index IWDG_RLR_OFFSET / 4U.
- **SWR-007** The IWDG LL driver shall ensure that the value written to IWDG_RLR.RL is not less than 2.
  - Source: RM0486 p.2990
  - Verification: The host unit test passes when the API function fails or asserts an error if the caller supplies a reload value less than 2 during a write operation to IWDG_RLR.RL.
- **SWR-008** When the IWDG LL driver reads the IWDG_SR.EWIF field, the IWDG LL driver shall return 1U if the EWIF bit is set in IWDG_SR register, else 0U.
  - Source: RM0486 p.2991
  - Verification: The host unit test passes when the IWDG_SR.EWIF bit is set and the function returns 1U, or when the IWDG_SR.EWIF bit is clear and the function returns 0U.
- **SWR-009** When the IWDG LL driver reads the IWDG_SR.ONF field, the IWDG LL driver shall return 1U if the ONF bit is set in IWDG_SR register, else 0U.
  - Source: RM0486 p.2991
  - Verification: The host unit test passes when the IWDG_SR.ONF bit is set and the function returns 1U, or when the IWDG_SR.ONF bit is clear and the function returns 0U.
- **SWR-010** When the IWDG LL driver reads the IWDG_SR.EWU field, the IWDG LL driver shall return 1U if the EWU bit is set in IWDG_SR register, else 0U.
  - Source: RM0486 p.2991
  - Verification: The host unit test passes when the IWDG_SR.EWU bit is set and the function returns 1U, or when the IWDG_SR.EWU bit is clear and the function returns 0U.
- **SWR-011** The IWDG LL driver shall return 0U when the IWDG_SR.WVU field is clear, or 1U when it is set.
  - Source: RM0486 p.2994
  - Verification: The host unit test passes when the function returns 0U when WVU bit is clear in IWDG_SR and 1U when it is set.
- **SWR-012** The IWDG LL driver shall return 0U when the IWDG_SR.RVU field is clear, or 1U when it is set.
  - Source: RM0486 p.2994
  - Verification: The host unit test passes when the function returns 0U when RVU bit is clear in IWDG_SR and 1U when it is set.
- **SWR-013** The IWDG LL driver shall return 0U when the IWDG_SR.PVU field is clear, or 1U when it is set.
  - Source: RM0486 p.2994
  - Verification: The host unit test passes when the function returns 0U when PVU bit is clear in IWDG_SR and 1U when it is set.
- **SWR-014** While no LL function has been called after reset, the IWDG LL driver shall not write any IWDG register.
  - Source: RM0486 p.2980
  - Verification: target_robot_test passes when no writes to IWDG registers occur before any LL function call
- **SWR-015** The IWDG LL driver shall ensure that a write operation to any register field modifies only the named bits, and does not alter other fields.
  - Source: RM0486 p.2980
  - Verification: host_unit_test passes when write operations affect only intended bits in the target register
- **SWR-016** The IWDG LL driver shall occupy at most 4096 bytes of flash.
  - Source: work-order budget (owner development target)
  - Verification: SWE.6 Robot suite checks the target linker map, size-tool and stack-usage evidence of the driver image; passes when the driver flash usage is at most 4096 bytes.
- **SWR-017** The IWDG LL driver shall use at most 64 bytes of static RAM.
  - Source: work-order budget (owner development target)
  - Verification: SWE.6 Robot suite checks the target linker map, size-tool and stack-usage evidence of the driver image; passes when the driver-owned data and BSS total at most 64 bytes, excluding the externally provided register array.
- **SWR-018** The IWDG LL driver shall use at most 128 bytes of stack for any public API call.
  - Source: work-order budget (owner development target)
  - Verification: SWE.6 Robot suite checks the target linker map, size-tool and stack-usage evidence of the driver image; passes when the worst-case stack usage of every public API call chain is at most 128 bytes.

## Open points

- Upstream inputs (HSI contract, safety allocation, budgets): NOT_PROVIDED.
- Safety allocation as stated in the manifest: ASIL B (SC-IWDG-2026-10-20, approved by Jefferson Nascimento on 2026-10-20); software safety allocation PENDING owner allocation review.
- Target silicon revision: UNSPECIFIED.
- Flash, static RAM and stack limits: development targets set by the work-order owner (2026-10-15).
