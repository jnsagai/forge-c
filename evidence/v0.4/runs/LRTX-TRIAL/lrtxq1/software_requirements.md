# Software requirements

Software requirements of the IWDG LL driver for this work order. Scope: LL (header-only, static inline): read/write IWDG registers through the generated register-block array ll_iwdg_regs (extern; placed at the IWDG base by the linker, defined in RAM by host tests), indexed by the generated LL_IWDG_<REG>_OFFSET / 4U Start the watchdog and refresh the counter by writing the documented keys to IWDG_KR; enable and disable write access to IWDG_PR, IWDG_RLR and IWDG_WINR with the documented keys Set the prescaler (IWDG_PR.PR) and the reload value (IWDG_RLR.RL); query the update flags in IWDG_SR (PVU, RVU) and the watchdog enable status (ONF) (no waiting: the caller bounds its polling) Out of scope: HAL API, window option (IWDG_WINR), early wake-up interrupt (IWDG_EWCR, IWDG_ICR), hardware watchdog option bytes, low-power freeze, debug freeze

- **SWR-001** When the IWDG LL driver is to start the watchdog, the IWDG LL driver shall write 0x0000CCCC to IWDG_KR.KEY.
  - Source: RM0486 p.2989
  - Verification: The test passes when ll_iwdg_regs[IWDG_KR_OFFSET/4U].KEY equals 0x0000CCCC after the call to the start function.
- **SWR-002** When the IWDG LL driver is to refresh the watchdog counter, the IWDG LL driver shall write 0x0000AAAA to IWDG_KR.KEY.
  - Source: RM0486 p.2989
  - Verification: The test passes when ll_iwdg_regs[IWDG_KR_OFFSET/4U].KEY equals 0x0000AAAA after the call to the refresh function.
- **SWR-003** When the IWDG LL driver is to enable write access to IWDG_PR and IWDG_RLR, the IWDG LL driver shall write 0x00005555 to IWDG_KR.KEY.
  - Source: RM0486 p.2989
  - Verification: The test passes when ll_iwdg_regs[IWDG_KR_OFFSET/4U].KEY equals 0x00005555 after the call to the enable write access function.
- **SWR-004** When the IWDG LL driver is to disable write access to IWDG_PR and IWDG_RLR, the IWDG LL driver shall write any value except 0x00005555 to IWDG_KR.KEY.
  - Source: RM0486 p.2989
  - Verification: The test passes when ll_iwdg_regs[IWDG_KR_OFFSET/4U].KEY is not equal to 0x00005555 after the call to the disable write access function.
- **SWR-005** The IWDG LL driver shall set the prescaler divider in the IWDG_PR.PR field to a valid value within its 4-bit range when write access is enabled.
  - Source: RM0486 p.2990
  - Verification: The test passes when the IWDG_PR.PR field is written with a valid 4-bit value and returns the corresponding prescaler divider in the following refresh cycles.
- **SWR-006** The IWDG LL driver shall write to IWDG_RLR.RL a value within the 12-bit range 0x000 to 0xFFF.
  - Source: RM0486 p.2990
  - Verification: The host_unit_test passes when the register array ll_iwdg_regs is written with the value 0x123 at offset IWDG_RLR_OFFSET, and the readback from that location matches 0x123.
- **SWR-007** While the IWDG LL driver is active, the IWDG LL driver shall not write to the IWDG_SR.EWIF field.
  - Source: RM0486 p.2991
  - Verification: The host unit test passes when the IWDG_SR.EWIF field is read as zero after reset and no function modifies this field.
- **SWR-008** While the IWDG LL driver is active, the IWDG LL driver shall return 1U if the IWDG_SR.ONF bit is set and 0U otherwise.
  - Source: RM0486 p.2991
  - Verification: The host unit test passes when the IWDG_SR.ONF field is read correctly after enabling the watchdog via a call to the appropriate LL function.
- **SWR-009** While the IWDG LL driver is active, the IWDG LL driver shall not write to the IWDG_SR.EWU field.
  - Source: RM0486 p.2991
  - Verification: The host unit test passes when the IWDG_SR.EWU field is read as zero after reset and no function modifies this field.
- **SWR-010** While no LL function has been called after reset, the IWDG LL driver shall not write any IWDG register.
  - Source: RM0486 p.2980
  - Verification: target_robot_test passes when no writes to IWDG registers occur before first function call
- **SWR-011** The IWDG LL driver shall occupy at most 4096 bytes of flash.
  - Source: work-order budget (owner development target)
  - Verification: SWE.6 Robot suite checks the target linker map, size-tool and stack-usage evidence of the driver image; passes when the driver flash usage is at most 4096 bytes.
- **SWR-012** The IWDG LL driver shall use at most 64 bytes of static RAM.
  - Source: work-order budget (owner development target)
  - Verification: SWE.6 Robot suite checks the target linker map, size-tool and stack-usage evidence of the driver image; passes when the driver-owned data and BSS total at most 64 bytes, excluding the externally provided register array.
- **SWR-013** The IWDG LL driver shall use at most 128 bytes of stack for any public API call.
  - Source: work-order budget (owner development target)
  - Verification: SWE.6 Robot suite checks the target linker map, size-tool and stack-usage evidence of the driver image; passes when the worst-case stack usage of every public API call chain is at most 128 bytes.

## Open points

- Upstream inputs (HSI contract, safety allocation, budgets): NOT_PROVIDED.
- Safety allocation as stated in the manifest: OUT_OF_SCOPE: QM development, no safety allocation or safety claims (SC-IWDG-QM-2026-10-21, approved by Jefferson Nascimento on 2026-10-21).
- Target silicon revision: UNSPECIFIED.
- Flash, static RAM and stack limits: development targets set by the work-order owner (2026-10-15).
