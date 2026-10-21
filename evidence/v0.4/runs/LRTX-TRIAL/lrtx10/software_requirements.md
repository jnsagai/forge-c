# Software requirements

Software requirements of the IWDG LL driver for this work order. Scope: LL (header-only, static inline): read/write IWDG registers through the generated register-block array ll_iwdg_regs (extern; placed at the IWDG base by the linker, defined in RAM by host tests), indexed by the generated LL_IWDG_<REG>_OFFSET / 4U Start the watchdog and refresh the counter by writing the documented keys to IWDG_KR; enable and disable write access to IWDG_PR, IWDG_RLR and IWDG_WINR with the documented keys Set the prescaler (IWDG_PR.PR) and the reload value (IWDG_RLR.RL); query the update flags in IWDG_SR (PVU, RVU) and the watchdog enable status (ONF) (no waiting: the caller bounds its polling) Out of scope: HAL API, window option (IWDG_WINR), early wake-up interrupt (IWDG_EWCR, IWDG_ICR), hardware watchdog option bytes, low-power freeze, debug freeze

- **SWR-001** When the IWDG LL driver is to start the watchdog, the IWDG LL driver shall write the key value 0xCCCC to IWDG_KR.KEY.
  - Source: RM0486 p.2989
  - Verification: The test passes when the register array ll_iwdg_regs[0] contains 0xCCCC at offset IWDG_KR_OFFSET after the function call.
- **SWR-002** When the IWDG LL driver is to refresh the watchdog counter, the IWDG LL driver shall write the key value 0xAAAA to IWDG_KR.KEY.
  - Source: RM0486 p.2989
  - Verification: The test passes when the register array ll_iwdg_regs[0] contains 0xAAAA at offset IWDG_KR_OFFSET after the function call.
- **SWR-003** When the IWDG LL driver is to enable write access to IWDG_PR and IWDG_RLR registers, the IWDG LL driver shall write the key value 0x5555 to IWDG_KR.KEY.
  - Source: RM0486 p.2989
  - Verification: The test passes when the register array ll_iwdg_regs[0] contains 0x5555 at offset IWDG_KR_OFFSET after the function call.
- **SWR-004** When the IWDG LL driver is to disable write access to IWDG_PR and IWDG_RLR registers, the IWDG LL driver shall write a key value different from 0x5555 to IWDG_KR.KEY.
  - Source: RM0486 p.2989
  - Verification: The test passes when the register array ll_iwdg_regs[0] does not contain 0x5555 at offset IWDG_KR_OFFSET after the function call.
- **SWR-005** The IWDG LL driver shall write the prescaler divider value to IWDG_PR.PR when requested by the caller.
  - Source: RM0486 p.2990
  - Verification: A host unit test passes when the function writes the correct value to the IWDG_PR.PR field and the ll_iwdg_regs array is updated accordingly.
- **SWR-006** The IWDG LL driver shall write the requested reload value to the IWDG_RLR.RL field when a function sets the watchdog reload value.
  - Source: RM0486 p.2990
  - Verification: A host unit test passes when the ll_iwdg_regs[IWDG_RLR_OFFSET/4U] register contains the written reload value after calling a function that sets the watchdog reload value.
- **SWR-007** The IWDG LL driver shall return 1U when the IWDG_SR.EWIF field is set, else 0U.
  - Source: RM0486 p.2991
  - Verification: The host unit test passes when the function returns 1U and IWDG_SR.EWIF is set in the register array, or returns 0U when IWDG_SR.EWIF is cleared.
- **SWR-008** The IWDG LL driver shall return 1U when the IWDG_SR.ONF field is set, else 0U.
  - Source: RM0486 p.2991
  - Verification: The host unit test passes when the function returns 1U and IWDG_SR.ONF is set in the register array, or returns 0U when IWDG_SR.ONF is cleared.
- **SWR-009** The IWDG LL driver shall return 1U when the IWDG_SR.EWU field is set, else 0U.
  - Source: RM0486 p.2991
  - Verification: The host unit test passes when the function returns 1U and IWDG_SR.EWU is set in the register array, or returns 0U when IWDG_SR.EWU is cleared.
- **SWR-010** The IWDG LL driver shall read the WVU bit of register IWDG_SR when a query function is called.
  - Source: RM0486 p.2991
  - Verification: The host unit test passes when the IWDG_SR.WVU bit is read correctly on every query call.
- **SWR-011** The IWDG LL driver shall read the RVU bit of register IWDG_SR when a query function is called.
  - Source: RM0486 p.2991
  - Verification: The host unit test passes when the IWDG_SR.RVU bit is read correctly on every query call.
- **SWR-012** The IWDG LL driver shall read the PVU bit of register IWDG_SR when a query function is called.
  - Source: RM0486 p.2991
  - Verification: The host unit test passes when the IWDG_SR.PVU bit is read correctly on every query call.
- **SWR-013** While no LL function has been called after reset, the IWDG LL driver shall not write any IWDG register.
  - Source: RM0486 p.2980
  - Verification: target_robot_test; passes when no writes to any IWDG register occur before first LL function call
- **SWR-014** The IWDG LL driver shall occupy at most 4096 bytes of flash.
  - Source: work-order budget (owner development target)
  - Verification: SWE.6 Robot suite checks the target linker map, size-tool and stack-usage evidence of the driver image; passes when the driver flash usage is at most 4096 bytes.
- **SWR-015** The IWDG LL driver shall use at most 64 bytes of static RAM.
  - Source: work-order budget (owner development target)
  - Verification: SWE.6 Robot suite checks the target linker map, size-tool and stack-usage evidence of the driver image; passes when the driver-owned data and BSS total at most 64 bytes, excluding the externally provided register array.
- **SWR-016** The IWDG LL driver shall use at most 128 bytes of stack for any public API call.
  - Source: work-order budget (owner development target)
  - Verification: SWE.6 Robot suite checks the target linker map, size-tool and stack-usage evidence of the driver image; passes when the worst-case stack usage of every public API call chain is at most 128 bytes.

## Open points

- Requirement SWR-001 [iwdg_kr_key_start] references a hardware register interface (RM0486 p.2989) without an approved safety allocation, making its feasibility unclear.
- The software requirements document contains open points indicating that requirement SWR-001 [iwdg_kr_key_start] references a hardware register interface without an approved safety allocation.
- SWE1-01: The safety allocation is marked as PENDING owner allocation review in the manifest and upstream_gaps.md. This indicates that no software safety requirements have been allocated yet, which prevents satisfying the requirement for failure handling.
- SWE1-03: No specification of failure handling found in the software safety requirements or related traceability documents. No specification of safe states found in software safety requirements or related traceability documents.
- Upstream inputs (HSI contract, safety allocation, budgets): NOT_PROVIDED.
- Safety allocation as stated in the manifest: ASIL B (SC-IWDG-2026-10-20, approved by Jefferson Nascimento on 2026-10-20); software safety allocation PENDING owner allocation review.
- Target silicon revision: UNSPECIFIED.
- Flash, static RAM and stack limits: development targets set by the work-order owner (2026-10-15).
