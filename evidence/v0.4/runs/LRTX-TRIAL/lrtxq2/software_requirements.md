# Software requirements

Software requirements of the IWDG LL driver for this work order. Scope: LL (header-only, static inline): read/write IWDG registers through the generated register-block array ll_iwdg_regs (extern; placed at the IWDG base by the linker, defined in RAM by host tests), indexed by the generated LL_IWDG_<REG>_OFFSET / 4U Start the watchdog and refresh the counter by writing the documented keys to IWDG_KR; enable and disable write access to IWDG_PR, IWDG_RLR and IWDG_WINR with the documented keys Set the prescaler (IWDG_PR.PR) and the reload value (IWDG_RLR.RL); query the update flags in IWDG_SR (PVU, RVU) and the watchdog enable status (ONF) (no waiting: the caller bounds its polling) Out of scope: HAL API, window option (IWDG_WINR), early wake-up interrupt (IWDG_EWCR, IWDG_ICR), hardware watchdog option bytes, low-power freeze, debug freeze

- **SWR-001** When the IWDG LL driver is to start the watchdog, the IWDG LL driver shall write the value 0xCCCC to IWDG_KR.KEY.
  - Source: RM0486 p.2989
  - Verification: host_unit_test passes when ll_iwdg_regs[IWDG_KR_OFFSET/4U].u16 = 0xCCCC is written to register array.
- **SWR-002** When the IWDG LL driver is to refresh the watchdog counter, the IWDG LL driver shall write the value 0xAAAA to IWDG_KR.KEY.
  - Source: RM0486 p.2989
  - Verification: host_unit_test passes when ll_iwdg_regs[IWDG_KR_OFFSET/4U].u16 = 0xAAAA is written to register array.
- **SWR-003** When the IWDG LL driver is to enable write access to IWDG_PR and IWDG_RLR, the IWDG LL driver shall write the value 0x5555 to IWDG_KR.KEY.
  - Source: RM0486 p.2989
  - Verification: host_unit_test passes when ll_iwdg_regs[IWDG_KR_OFFSET/4U].u16 = 0x5555 is written to register array.
- **SWR-004** When the IWDG LL driver is to disable write access to IWDG_PR and IWDG_RLR, the IWDG LL driver shall write a value different from 0x5555 to IWDG_KR.KEY.
  - Source: RM0486 p.2989
  - Verification: host_unit_test passes when ll_iwdg_regs[IWDG_KR_OFFSET/4U].u16 != 0x5555 is written to register array.
- **SWR-005** The IWDG LL driver shall set the prescaler divider in the IWDG_PR.PR field to a value within its 4-bit range.
  - Source: RM0486 p.2990
  - Verification: The host unit test passes when the IWDG_PR.PR field is written with a representative value between 0 and 15, and a corresponding readback confirms the value.
- **SWR-006** The IWDG LL driver shall write the requested value to the IWDG_RLR.RL field when setting the watchdog reload value.
  - Source: RM0486 p.2990
  - Verification: The host unit test passes when writing a value to the IWDG_RLR register and reading back the same value from the ll_iwdg_regs array at the correct offset.
- **SWR-007** The IWDG LL driver shall read the current value of the IWDG_RLR.RL field when querying the watchdog reload value.
  - Source: RM0486 p.2990
  - Verification: The host unit test passes when reading the current value from IWDG_RLR and comparing it with the expected value stored in memory; this does not write to the register but reads its value.
- **SWR-008** The IWDG LL driver shall return 1U when the IWDG_SR.EWIF field is set, else 0U.
  - Source: RM0486 p.2991
  - Verification: The host unit test passes when ll_iwdg_regs[IWDG_SR_OFFSET / 4U] & (1U << 15) is evaluated and returns 1U when the bit is set, else 0U.
- **SWR-009** The IWDG LL driver shall return 1U when the IWDG_SR.ONF field is set, else 0U.
  - Source: RM0486 p.2991
  - Verification: The host unit test passes when ll_iwdg_regs[IWDG_SR_OFFSET / 4U] & (1U << 8) is evaluated and returns 1U when the bit is set, else 0U.
- **SWR-010** The IWDG LL driver shall return 1U when the IWDG_SR.EWU field is set, else 0U.
  - Source: RM0486 p.2991
  - Verification: The host unit test passes when ll_iwdg_regs[IWDG_SR_OFFSET / 4U] & (1U << 3) is evaluated and returns 1U when the bit is set, else 0U.
- **SWR-011** The IWDG LL driver shall return 1U if the IWDG_SR.PVU field is set, else 0U.
  - Source: RM0486 p.2994
  - Verification: The host unit test passes when the IWDG_SR.PVU bit is set and the function returns 1U, or when the IWDG_SR.PVU bit is reset and the function returns 0U.
- **SWR-012** The IWDG LL driver shall return 1U if the IWDG_SR.RVU field is set, else 0U.
  - Source: RM0486 p.2994
  - Verification: The host unit test passes when the IWDG_SR.RVU bit is set and the function returns 1U, or when the IWDG_SR.RVU bit is reset and the function returns 0U.
- **SWR-013** The IWDG LL driver shall return 1U if the IWDG_SR.WVU field is set, else 0U.
  - Source: RM0486 p.2994
  - Verification: The host unit test passes when the IWDG_SR.WVU bit is set and the function returns 1U, or when the IWDG_SR.WVU bit is reset and the function returns 0U.
- **SWR-014** While no LL function has been called after reset, the IWDG LL driver shall not write any IWDG register.
  - Source: RM0486 p.2980
  - Verification: target_robot_test passes when no IWDG register writes occur before first function call
- **SWR-015** The IWDG LL driver shall handle failure conditions by not relying on status flags for synchronization; the caller bounds its polling.
  - Source: RM0486 p.2980
  - Verification: target_robot_test passes when driver does not wait on status flags during polling
- **SWR-016** The IWDG LL driver shall ensure that writes to registers modify only the named fields and do not affect other bits.
  - Source: RM0486 p.2980
  - Verification: host_unit_test passes when register bit masking correctly limits write operations to specified fields
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

- The software requirements do not explicitly document the complete failure handling strategy for all potential error states, as SWE1-03 requires. The current requirement SWR-002 addresses polling but does not enumerate all possible failure modes or responses.
- Verification criteria and source page references are provided in the output, however explicit documentation of the resolution process for ambiguities related to the scope or expected behavior of the driver is not included in the requirements, as required by SWE1-06.
- Upstream inputs (HSI contract, safety allocation, budgets): NOT_PROVIDED.
- Safety allocation as stated in the manifest: OUT_OF_SCOPE: QM development, no safety allocation or safety claims (SC-IWDG-QM-2026-10-21, approved by Jefferson Nascimento on 2026-10-21).
- Target silicon revision: UNSPECIFIED.
- Flash, static RAM and stack limits: development targets set by the work-order owner (2026-10-15).
