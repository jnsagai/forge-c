# Software requirements

Scope: header-only static inline register access through the generated extern ll_iwdg_regs array, indexed by LL_IWDG_<REG>_OFFSET / 4U. Command and setter functions return void; queries return normalized 1U or 0U. The caller controls polling and ensures write access is enabled and the applicable update flag is clear before configuration. The LL API performs no waiting and supplies no timeout or error-code interface. Setter input outside the documented field range is outside this contract.

The scope excludes IWDG_WINR, IWDG_EWCR, IWDG_ICR, option bytes, low-power behavior and debug freeze. Hardware write protection and hardware flag transitions are not emulated by the RAM register array; unit verification checks the documented key, field and query results. The register array represents peripheral storage and is not retained driver state.

- **SWR-001** When the watchdog start function is called, the IWDG LL driver shall write 0x0000CCCC to IWDG_KR.KEY.
  - Source: RM0486 p.2989
  - Verification: Host unit test: call the start function on the RAM register array; pass if IWDG_KR equals 0x0000CCCC.
- **SWR-002** When the counter refresh function is called, the IWDG LL driver shall write 0x0000AAAA to IWDG_KR.KEY.
  - Source: RM0486 p.2989
  - Verification: Host unit test: call the refresh function on the RAM register array; pass if IWDG_KR equals 0x0000AAAA.
- **SWR-003** When the write access enable function is called, the IWDG LL driver shall write 0x00005555 to IWDG_KR.KEY to enable write access to IWDG_PR and IWDG_RLR.
  - Source: RM0486 p.2989
  - Verification: Host unit test: call the write access enable function; pass if IWDG_KR in the RAM register array equals 0x00005555.
- **SWR-004** When the write access disable function is called, the IWDG LL driver shall write 0x00000000 to IWDG_KR.KEY to disable write access to IWDG_PR and IWDG_RLR.
  - Source: RM0486 p.2989
  - Verification: Host unit test: seed IWDG_KR with 0x00005555 and call the write access disable function; pass if IWDG_KR equals 0x00000000.
- **SWR-005** When the prescaler setting function is called with a requested value in the range 0x0 through 0xF, the IWDG LL driver shall write the requested value to IWDG_PR.PR.
  - Source: RM0486 p.2989; RM0486 p.2990
  - Verification: Host unit test: with reserved bits initially zero, set each value from 0x0 through 0xF; pass if IWDG_PR.PR equals the requested value and IWDG_PR bits 31:4 remain zero.
- **SWR-006** When the reload setting function is called with a requested value in the range 0x000 through 0xFFF, the IWDG LL driver shall write the requested value to IWDG_RLR.RL.
  - Source: RM0486 p.2990
  - Verification: Host unit test: with reserved bits initially zero, set each value from 0x000 through 0xFFF; pass if IWDG_RLR.RL equals the requested value and IWDG_RLR bits 31:12 remain zero.
- **SWR-007** When the prescaler update status query is called with IWDG_SR.PVU set, the IWDG LL driver shall return 1U and leave all IWDG registers unchanged.
  - Source: RM0486 p.2991
  - Verification: Host unit test: seed the RAM array with PVU set, including IWDG_SR = 0x1 and 0x103; pass if the query returns 1U and the array matches its pre-call snapshot.
- **SWR-008** When the prescaler update status query is called with IWDG_SR.PVU clear, the IWDG LL driver shall return 0U and leave all IWDG registers unchanged.
  - Source: RM0486 p.2991
  - Verification: Host unit test: seed the RAM array with PVU clear, including IWDG_SR = 0x0 and 0x102; pass if the query returns 0U and the array matches its pre-call snapshot.
- **SWR-009** When the reload update status query is called with IWDG_SR.RVU set, the IWDG LL driver shall return 1U and leave all IWDG registers unchanged.
  - Source: RM0486 p.2991
  - Verification: Host unit test: seed the RAM array with RVU set, including IWDG_SR = 0x2 and 0x103; pass if the query returns 1U and the array matches its pre-call snapshot.
- **SWR-010** When the reload update status query is called with IWDG_SR.RVU clear, the IWDG LL driver shall return 0U and leave all IWDG registers unchanged.
  - Source: RM0486 p.2991
  - Verification: Host unit test: seed the RAM array with RVU clear, including IWDG_SR = 0x0 and 0x101; pass if the query returns 0U and the array matches its pre-call snapshot.
- **SWR-011** When the watchdog enable status query is called with IWDG_SR.ONF set, the IWDG LL driver shall return 1U and leave all IWDG registers unchanged.
  - Source: RM0486 p.2991
  - Verification: Host unit test: seed the RAM array with ONF set, including IWDG_SR = 0x100 and 0x103; pass if the query returns 1U and the array matches its pre-call snapshot.
- **SWR-012** When the watchdog enable status query is called with IWDG_SR.ONF clear, the IWDG LL driver shall return 0U and leave all IWDG registers unchanged.
  - Source: RM0486 p.2991
  - Verification: Host unit test: seed the RAM array with ONF clear, including IWDG_SR = 0x0 and 0x3; pass if the query returns 0U and the array matches its pre-call snapshot.
- **SWR-013** While no LL function has been called after reset, the IWDG LL driver shall not write any IWDG register, including IWDG_KR.KEY, IWDG_PR.PR, IWDG_RLR.RL, IWDG_SR.PVU, IWDG_SR.RVU and IWDG_SR.ONF.
  - Source: RM0486 p.2989; RM0486 p.2990; RM0486 p.2991
  - Verification: Host startup test: link and include the LL header, snapshot the RAM register array before application startup and call no LL function; pass if the array remains identical after startup.
- **SWR-014** The IWDG LL driver shall occupy at most 4096 bytes of flash in the target verification build exercising all in-scope LL functions.
  - Source: work-order budget (owner development target)
  - Verification: SWE.6 target size tool: measure driver-attributable code and read-only data in the verification ELF; pass if their combined flash size is at most 4096 bytes.
- **SWR-015** The IWDG LL driver shall allocate 0 bytes of static RAM for retained driver state within the 64-byte static RAM budget.
  - Source: work-order budget (owner development target)
  - Verification: SWE.6 target size tool: measure driver-attributable writable static storage; pass if retained driver state occupies 0 bytes and total driver static RAM is at most 64 bytes, excluding the hardware register mapping and host RAM register fixture.
- **SWR-016** The IWDG LL driver shall require at most 128 bytes of stack for any in-scope LL function call in the target verification build.
  - Source: work-order budget (owner development target)
  - Verification: SWE.6 stack tool: analyze every in-scope LL call including compiler-generated stack frames; pass if the maximum driver call stack use is at most 128 bytes.

## Open points

- The manifest target safety_allocation is NOT_PROVIDED: no owner safety scope recorded for the IWDG work orders. No software safety requirement is allocated; owner safety scope and allocation remain unresolved.
- Human-approved upstream inputs are NOT_PROVIDED; the manifest reports an unapproved draft template and placeholder HSI, safety and budget fields. The supplied RM0486 register contract and work-order owner development budgets are the available basis.
- Target silicon_revision is UNSPECIFIED; owner confirmation of the target revision and approved HSI contract remains open.
