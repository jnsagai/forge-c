# Software requirements

- **SWR-001** When HAL_IWDG_Init receives a valid configuration, the IWDG driver shall write the start key 0xCCCC followed by the register access key 0x5555 to IWDG_KR.KEY before configuring the prescaler and reload value, with 0xAAAA as the final key write on successful completion.
  - Source: RM0486 p.2989; work-order HAL initialisation scope.
  - Verification: Host unit test with a valid configuration; the observed key writes are 0xCCCC followed by 0x5555 before configuration writes and the final key is 0xAAAA on HAL_OK.
- **SWR-002** When HAL_IWDG_Init receives a valid configuration and IWDG_SR.PVU is clear, the IWDG driver shall write the configured prescaler in the range 0 through 7 to IWDG_PR.PR while preserving reserved bits at their reset value.
  - Source: RM0486 p.2989; RM0486 p.2990; work-order prescaler acceptance range.
  - Verification: Host unit test over prescalers 0 through 7 with PVU clear; IWDG_PR.PR equals the configured value and reserved bits remain at their reset value.
- **SWR-003** When HAL_IWDG_Init receives a valid configuration and IWDG_SR.RVU is clear, the IWDG driver shall write the configured reload value in the range 0 through 0xFFF to IWDG_RLR.RL while preserving reserved bits at their reset value.
  - Source: RM0486 p.2990.
  - Verification: Host unit test including reload values 0, 1, 2 and 0xFFF with RVU clear; IWDG_RLR.RL equals the configured value and reserved bits remain at their reset value.
- **SWR-004** When HAL_IWDG_Init has configured the prescaler and reload value and both IWDG_SR.PVU and IWDG_SR.RVU clear before the update deadline, the IWDG driver shall write the refresh key 0xAAAA to IWDG_KR.KEY and return HAL_OK with the watchdog running and IWDG_PR and IWDG_RLR write-protected.
  - Source: RM0486 p.2989; RM0486 p.2991; work-order HAL initialisation scope.
  - Verification: Host unit test with each update flag clearing before timeout_ms elapses; the final key is 0xAAAA, no refresh precedes completion of both updates, and the return value is HAL_OK.
- **SWR-005** If HAL_IWDG_Init receives a NULL configuration pointer or a prescaler above 7 or a reload value above 0xFFF or a timeout_ms of 0 or greater than HAL_IWDG_TIMEOUT_MS, then the IWDG driver shall return HAL_ERROR without accessing any IWDG register.
  - Source: RM0486 p.2990; work-order HAL parameter validation policy.
  - Verification: Host unit test for each invalid input separately; the return value is HAL_ERROR and there is no IWDG register access.
- **SWR-006** When HAL_IWDG_Init waits for completion of the prescaler and reload updates, the IWDG driver shall bound the total update wait by the caller-supplied timeout_ms measured as elapsed milliseconds of the system time base HAL_GetTick(), including unsigned tick wraparound, with HAL_IWDG_TIMEOUT_MS equal to 48 ms and without using a count of polling iterations as the timeout.
  - Source: RM0486 p.2991; work-order time bound of 48 ms covering up to 6 LSI periods with margin.
  - Verification: Host unit test with flags held busy and with advancing, variable-rate and wrapping HAL_GetTick() values; the wait terminates when elapsed time reaches timeout_ms, for valid timeout_ms values 1 through 48, independently of polling iteration count.
- **SWR-007** If IWDG_SR.PVU or IWDG_SR.RVU is still set when timeout_ms milliseconds of HAL_GetTick() have elapsed during HAL_IWDG_Init, then the IWDG driver shall write the write-protect key 0x0000 to IWDG_KR.KEY, omit the refresh key 0xAAAA, and return HAL_TIMEOUT with IWDG_PR and IWDG_RLR no longer writable and the already started watchdog running until watchdog reset unless the caller recovers.
  - Source: RM0486 p.2989; RM0486 p.2991; work-order update-timeout fallback.
  - Verification: Host unit test holding PVU and RVU set in separate cases; at the timeout_ms deadline the final key is 0x0000, no refresh key is written, and HAL_TIMEOUT is returned; target verification confirms continued watchdog operation and eventual reset without caller recovery.
- **SWR-008** When HAL_IWDG_Refresh is requested, the IWDG driver shall write the refresh key 0xAAAA to IWDG_KR.KEY and return HAL_OK.
  - Source: RM0486 p.2989.
  - Verification: Host unit test invoking HAL_IWDG_Refresh; the key written is 0xAAAA and the return value is HAL_OK.
- **SWR-009** While no watchdog initialisation has been requested after reset, the IWDG driver shall not access any IWDG register.
  - Source: RM0486 p.2989; work-order reset and startup policy.
  - Verification: SWE.6 Robot startup verification from reset without a driver API request; no IWDG register access originates from the IWDG driver.
- **SWR-010** The IWDG driver shall occupy at most 4096 bytes of flash.
  - Source: work-order budget (owner development target).
  - Verification: SWE.6 Robot analysis of the target linked image; driver-attributed flash use is at most 4096 bytes.
- **SWR-011** The IWDG driver shall occupy at most 64 bytes of static RAM.
  - Source: work-order budget (owner development target).
  - Verification: SWE.6 Robot analysis of the target linked image; driver-attributed static RAM use is at most 64 bytes.
- **SWR-012** The IWDG driver shall use at most 128 bytes of stack.
  - Source: work-order budget (owner development target).
  - Verification: SWE.6 Robot analysis of target stack evidence including the deepest driver call chain; maximum driver stack use is at most 128 bytes.
- **SWR-013** The IWDG driver shall expose HAL_IWDG_Init with a const configuration pointer and timeout_ms and HAL_IWDG_Refresh with hal_status_t return values, implementing all IWDG register operations through the provided LL_IWDG_ functions.
  - Source: RM0486 p.2989; RM0486 p.2990; RM0486 p.2991; work-order HAL interface and verified LL reuse scope.
  - Verification: Host unit compile and LL-fake isolation test; the API accepts a const configuration pointer and timeout_ms, returns hal_status_t, and all IWDG operations are observable through the provided LL interface.

## Open points

- Software safety allocation is PENDING owner allocation review for target ASIL B, scope SC-IWDG-2026-10-20; no software safety requirements are allocated yet.
- The manifest upstream status is NOT_PROVIDED with issue UPSTREAM_FILE_MISSING; no human-approved upstream allocation is inferred.
- The target silicon revision is UNSPECIFIED in the manifest.
- The work order restricts the accepted prescaler to 0 through 7 although RM0486 p.2990 describes additional encodings; this restriction is the driver API policy.
- RM0486 p.2990 recommends a reload value of at least 2, but the work-order invalid-input policy accepts 0 and 1; callers remain responsible for selecting a usable watchdog period.
- The window option is assumed disabled as stated in the work-order scope; configuring window mode, early wake-up, option bytes and freeze controls is outside this HAL work order.
