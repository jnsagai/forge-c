# Software requirements

Software requirements of the IWDG LL driver for this work order. Scope: LL (header-only, static inline): read/write IWDG registers through the generated register-block array ll_iwdg_regs (extern; placed at the IWDG base by the linker, defined in RAM by host tests), indexed by the generated LL_IWDG_<REG>_OFFSET / 4U Start the watchdog and refresh the counter by writing the documented keys to IWDG_KR; enable and disable write access to IWDG_PR, IWDG_RLR and IWDG_WINR with the documented keys Set the prescaler (IWDG_PR.PR) and the reload value (IWDG_RLR.RL); query the update flags in IWDG_SR (PVU, RVU) and the watchdog enable status (ONF) (no waiting: the caller bounds its polling) Out of scope: HAL API, window option (IWDG_WINR), early wake-up interrupt (IWDG_EWCR, IWDG_ICR), hardware watchdog option bytes, low-power freeze, debug freeze

- **SWR-001** When the IWDG LL driver is started, the IWDG LL driver shall write the key value 0x0000AAAA to IWDG_KR.KEY to refresh the watchdog counter.
  - Source: RM0486 p.2989
  - Verification: The test passes when the register array element ll_iwdg_regs[IWDG_KR_OFFSET/4U] has the value 0x0000AAAA written to it.
- **SWR-002** When the IWDG LL driver enables write access to IWDG_PR and IWDG_RLR, the IWDG LL driver shall write the key value 0x00005555 to IWDG_KR.KEY.
  - Source: RM0486 p.2989
  - Verification: The test passes when the register array element ll_iwdg_regs[IWDG_KR_OFFSET/4U] has the value 0x00005555 written to it.
- **SWR-003** When the IWDG LL driver disables write access to IWDG_PR and IWDG_RLR, the IWDG LL driver shall write a key value different from 0x00005555 to IWDG_KR.KEY.
  - Source: RM0486 p.2989
  - Verification: The test passes when the register array element ll_iwdg_regs[IWDG_KR_OFFSET/4U] has any value other than 0x00005555 written to it.
- **SWR-004** When starting the watchdog, the IWDG LL driver shall write the key value 0x0000CCCC to IWDG_KR.KEY.
  - Source: RM0486 p.2989
  - Verification: The test passes when the register array element ll_iwdg_regs[IWDG_KR_OFFSET/4U] has the value 0x0000CCCC written to it.
- **SWR-005** The IWDG LL driver shall write the reload value to IWDG_RLR.RL when requested by the caller.
  - Source: RM0486 p.2990
  - Verification: The host unit test passes when the IWDG_RLR register is written with the value provided by the api_calls argument.
- **SWR-006** The IWDG LL driver shall read the reload value from IWDG_RLR.RL to support status queries.
  - Source: RM0486 p.2990
  - Verification: The host unit test passes when reading IWDG_RLR returns the expected reload value.
- **SWR-007** The IWDG LL driver shall read the EWIF bit of register IWDG_SR and return 1U if set, else 0U.
  - Source: RM0486 p.2991
  - Verification: A host unit test passes when the function returns 1U when IWDG_SR.EWIF is set, and 0U when it is cleared.
- **SWR-008** The IWDG LL driver shall read the ONF bit of register IWDG_SR and return 1U if set, else 0U.
  - Source: RM0486 p.2991
  - Verification: A host unit test passes when the function returns 1U when IWDG_SR.ONF is set, and 0U when it is cleared.
- **SWR-009** The IWDG LL driver shall read the EWU bit of register IWDG_SR and return 1U if set, else 0U.
  - Source: RM0486 p.2991
  - Verification: A host unit test passes when the function returns 1U when IWDG_SR.EWU is set, and 0U when it is cleared.
- **SWR-010** The IWDG LL driver shall read the IWDG_SR.WVU field and return 1U when set, else 0U.
  - Source: RM0486 p.2991
  - Verification: A host unit test passes when the function reading IWDG_SR.WVU returns 1U when WVU bit is set in the register array, and 0U otherwise.
- **SWR-011** The IWDG LL driver shall read the IWDG_SR.RVU field and return 1U when set, else 0U.
  - Source: RM0486 p.2991
  - Verification: A host unit test passes when the function reading IWDG_SR.RVU returns 1U when RVU bit is set in the register array, and 0U otherwise.
- **SWR-012** The IWDG LL driver shall read the IWDG_SR.PVU field and return 1U when set, else 0U.
  - Source: RM0486 p.2991
  - Verification: A host unit test passes when the function reading IWDG_SR.PVU returns 1U when PVU bit is set in the register array, and 0U otherwise.
- **SWR-013** While no LL function has been called after reset, the IWDG LL driver shall not write any IWDG register.
  - Source: RM0486 p.2980
  - Verification: target_robot_test passes when no writes to IWDG registers occur before any LL function call
- **SWR-014** The IWDG LL driver shall ensure that only the named bits are modified when writing to IWDG_PR.PR.
  - Source: RM0486 p.2980
  - Verification: host_unit_test passes when writes to IWDG_PR.PR modify only the PR field
- **SWR-015** The IWDG LL driver shall ensure that only the named bits are modified when writing to IWDG_RLR.RL.
  - Source: RM0486 p.2980
  - Verification: host_unit_test passes when writes to IWDG_RLR.RL modify only the RL field
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

- The safety allocation is pending review and no software safety requirement is allocated yet, making it impossible to determine if the requirement SWR-002 is objectively verifiable.
- Software safety requirements are not allocated yet; the safety allocation is PENDING owner allocation review.
- No failure handling, reset/startup behavior or safe states are specified in the software safety requirements. The safety allocation is pending review and no software safety requirements are allocated.
- Upstream inputs (HSI contract, safety allocation, budgets): NOT_PROVIDED.
- Safety allocation as stated in the manifest: ASIL B (SC-IWDG-2026-10-20, approved by Jefferson Nascimento on 2026-10-20); software safety allocation PENDING owner allocation review.
- Target silicon revision: UNSPECIFIED.
- Flash, static RAM and stack limits: development targets set by the work-order owner (2026-10-15).
