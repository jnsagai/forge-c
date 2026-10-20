# Software requirements

Scope: header-only static inline register access through the external ll_iwdg_regs array, indexed by LL_IWDG_<REG>_OFFSET / 4U. Mutation functions have no return value. Queries return the specified unsigned Boolean value. Polling, waiting, timeouts, error codes, the window option, early wake-up interrupts, option bytes, low-power behavior and debug freeze are outside this LL work order. Callers supply in-range prescaler and reload values; invalid inputs have no allocated behavior.

Hardware behavior below is specified by the work-order instruction. The permitted RM0486 section files are explicitly unavailable, so page citations remain unresolved rather than invented.

- **SWR-001** When the start function is called, the IWDG LL driver shall write 0x0000CCCC to IWDG_KR.KEY.
  - Source: RM0486 p.unavailable (chapter 59 identified by manifest; permitted section/page evidence missing; behavior specified by work-order instruction)
  - Verification: Host unit test: call start with a different initial KEY value and pass when KEY equals 0xCCCC.

- **SWR-002** When the refresh function is called, the IWDG LL driver shall write 0x0000AAAA to IWDG_KR.KEY.
  - Source: RM0486 p.unavailable (chapter 59 identified by manifest; permitted section/page evidence missing; behavior specified by work-order instruction)
  - Verification: Host unit test: call refresh with a different initial KEY value and pass when KEY equals 0xAAAA.

- **SWR-003** When the enable write access function is called, the IWDG LL driver shall write 0x00005555 to IWDG_KR.KEY to enable write access to IWDG_PR and IWDG_RLR.
  - Source: RM0486 p.unavailable (chapter 59 identified by manifest; permitted section/page evidence missing; behavior specified by work-order instruction)
  - Verification: Host unit test: call enable write access and pass when KEY equals 0x5555.

- **SWR-004** When the disable write access function is called, the IWDG LL driver shall write 0x00000000 to IWDG_KR.KEY to disable write access to IWDG_PR and IWDG_RLR.
  - Source: RM0486 p.unavailable (chapter 59 identified by manifest; permitted section/page evidence missing; behavior specified by work-order instruction)
  - Verification: Host unit test: initialize KEY to 0x5555, call disable write access and pass when KEY equals zero.

- **SWR-005** When the prescaler setter is called with a requested value from 0U through 15U, the IWDG LL driver shall write the requested value to the 4-bit IWDG_PR.PR field.
  - Source: RM0486 p.unavailable (chapter 59 identified by manifest; permitted section/page evidence missing; behavior specified by work-order instruction)
  - Verification: Host unit test: exercise every value from 0U through 15U on the register array and pass when PR equals the requested value.

- **SWR-006** When the reload setter is called with a requested value from 0U through 4095U, the IWDG LL driver shall write the requested value to the 12-bit IWDG_RLR.RL field.
  - Source: RM0486 p.unavailable (chapter 59 identified by manifest; permitted section/page evidence missing; behavior specified by work-order instruction)
  - Verification: Host unit test: exercise every value from 0U through 4095U on the register array and pass when RL equals the requested value.

- **SWR-007** When the prescaler update query is called while IWDG_SR.PVU is set, the IWDG LL driver shall return 1U without modifying any IWDG register.
  - Source: RM0486 p.unavailable (chapter 59 identified by manifest; permitted section/page evidence missing; behavior specified by work-order instruction)
  - Verification: Host unit test: initialize PVU to one, vary other status fields, snapshot the array, call the query and pass when the return is 1U and the array is unchanged.

- **SWR-008** When the prescaler update query is called while IWDG_SR.PVU is clear, the IWDG LL driver shall return 0U without modifying any IWDG register.
  - Source: RM0486 p.unavailable (chapter 59 identified by manifest; permitted section/page evidence missing; behavior specified by work-order instruction)
  - Verification: Host unit test: initialize PVU to zero, vary other status fields, snapshot the array, call the query and pass when the return is 0U and the array is unchanged.

- **SWR-009** When the reload update query is called while IWDG_SR.RVU is set, the IWDG LL driver shall return 1U without modifying any IWDG register.
  - Source: RM0486 p.unavailable (chapter 59 identified by manifest; permitted section/page evidence missing; behavior specified by work-order instruction)
  - Verification: Host unit test: initialize RVU to one, vary other status fields, snapshot the array, call the query and pass when the return is 1U and the array is unchanged.

- **SWR-010** When the reload update query is called while IWDG_SR.RVU is clear, the IWDG LL driver shall return 0U without modifying any IWDG register.
  - Source: RM0486 p.unavailable (chapter 59 identified by manifest; permitted section/page evidence missing; behavior specified by work-order instruction)
  - Verification: Host unit test: initialize RVU to zero, vary other status fields, snapshot the array, call the query and pass when the return is 0U and the array is unchanged.

- **SWR-011** When the watchdog enable status query is called while IWDG_SR.ONF is set, the IWDG LL driver shall return 1U without modifying any IWDG register.
  - Source: RM0486 p.unavailable (chapter 59 identified by manifest; permitted section/page evidence missing; behavior specified by work-order instruction)
  - Verification: Host unit test: initialize ONF to one, vary other status fields, snapshot the array, call the query and pass when the return is 1U and the array is unchanged.

- **SWR-012** When the watchdog enable status query is called while IWDG_SR.ONF is clear, the IWDG LL driver shall return 0U without modifying any IWDG register.
  - Source: RM0486 p.unavailable (chapter 59 identified by manifest; permitted section/page evidence missing; behavior specified by work-order instruction)
  - Verification: Host unit test: initialize ONF to zero, vary other status fields, snapshot the array, call the query and pass when the return is 0U and the array is unchanged.

- **SWR-013** While no LL function has been called after reset, the IWDG LL driver shall not write any IWDG register, including IWDG_KR.KEY, IWDG_PR.PR, IWDG_RLR.RL, IWDG_SR.PVU, IWDG_SR.RVU and IWDG_SR.ONF.
  - Source: RM0486 p.unavailable (chapter 59 identified by manifest; permitted section/page evidence missing; behavior specified by work-order instruction)
  - Verification: Host startup test: snapshot the RAM register array before driver startup and pass when the array remains unchanged before the first LL call.

- **SWR-014** The IWDG LL driver shall occupy at most 4096 bytes of flash in the Cortex-M55 target build.
  - Source: work-order budget (owner development target)
  - Verification: SWE.6 size measurement: instantiate every public inline function in the target measurement harness and pass when attributed text plus read-only data plus initialized-data load image totals at most 4096 bytes.

- **SWR-015** The IWDG LL driver shall allocate zero bytes of persistent static RAM within the owner budget of 64 bytes.
  - Source: work-order budget (owner development target)
  - Verification: SWE.6 size measurement: instantiate every public inline function and pass when driver-owned .data plus .bss totals zero bytes, excluding the external register array and test harness.

- **SWR-016** The IWDG LL driver shall use at most 128 bytes of stack for any public function in the Cortex-M55 target build.
  - Source: work-order budget (owner development target)
  - Verification: SWE.6 stack analysis: instantiate every public inline function in the target measurement harness and pass when the maximum driver call-path stack usage is at most 128 bytes.

## Open points

- RM0486 page numbers and detailed IWDG section identifiers are unresolved: the work instruction lists unavailable sections 14.10.1, 14.10.2, 14.10.79 and 14.10.64, whereas the manifest identifies chapter 59. Correct section files and page evidence are needed to complete source citations. No hardware page is inferred from the memory-map page 179.
- target.safety_allocation is NOT_PROVIDED: no owner safety scope recorded for the IWDG work orders. No ASIL, QM classification or safety requirement allocation is inferred.
- inputs/upstream-inputs.yaml is absent; manifest upstream.status is NOT_PROVIDED, with unapproved draft template and placeholder issues. Budgets are owner development targets, not approved safety budgets.
