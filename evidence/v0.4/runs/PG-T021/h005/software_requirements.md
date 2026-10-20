# Software requirements

The configuration is a const pointer containing prescaler, reload and timeout_ms. A valid configuration is non-NULL, with prescaler in 0..7, reload in 0..0xFFF, and timeout_ms in 1..HAL_IWDG_TIMEOUT_MS inclusive. HAL_IWDG_TIMEOUT_MS is 48 ms. This owner-selected limit covers the RM0486 update time of up to 6 LSI periods with margin (manifest scope). Reload values 0 and 1 are accepted by this interface although RM0486 p.2990 recommends values of at least 2. The window option is disabled by the integration configuration and is outside this interface.

- **SWR-001** When HAL_IWDG_Init is requested with a valid configuration, the IWDG driver shall start the watchdog by writing 0xCCCC to IWDG_KR.KEY before enabling register write access and, on successful completion, finish with 0xAAAA as the last write to IWDG_KR.KEY.
  - Source: RM0486 p.2989; work-order scope.
  - Verification: Host unit test with a valid configuration; the key-write sequence starts with 0xCCCC before the write-access key and ends with 0xAAAA on successful completion.
- **SWR-002** When HAL_IWDG_Init is requested with a valid configuration, the IWDG driver shall enable register write access by writing 0x5555 to IWDG_KR.KEY after the start key and before configuring IWDG_PR.PR or IWDG_RLR.RL and, on successful completion, finish with 0xAAAA as the last write to IWDG_KR.KEY.
  - Source: RM0486 p.2989; work-order scope.
  - Verification: Host unit test with a valid configuration; 0x5555 follows 0xCCCC and precedes either configuration-field write, and the last key is 0xAAAA on successful completion.
- **SWR-003** When HAL_IWDG_Init is requested with a valid configuration, the IWDG driver shall write the configured prescaler to IWDG_PR.PR with IWDG_SR.PVU clear.
  - Source: RM0486 p.2990.
  - Verification: Host unit test over prescaler values 0..7; IWDG_PR.PR equals the configured value and its write occurs with IWDG_SR.PVU clear.
- **SWR-004** When HAL_IWDG_Init is requested with a valid configuration, the IWDG driver shall write the configured reload value to IWDG_RLR.RL with IWDG_SR.RVU clear.
  - Source: RM0486 p.2990.
  - Verification: Host unit test including reload values 0, 1, 2 and 0xFFF; IWDG_RLR.RL equals the configured value and its write occurs with IWDG_SR.RVU clear.
- **SWR-005** When both IWDG_SR.PVU and IWDG_SR.RVU are clear within the configured timeout_ms after configuration updates in HAL_IWDG_Init, the IWDG driver shall write 0xAAAA to IWDG_KR.KEY to refresh the counter and write-protect IWDG_PR and IWDG_RLR before returning HAL_OK.
  - Source: RM0486 p.2989; RM0486 p.2991; work-order scope.
  - Verification: Host unit test with immediate and delayed update completion; the refresh key follows completion of both flags within timeout_ms of HAL_GetTick(), register write protection is restored, and the result is HAL_OK.
- **SWR-006** If IWDG_SR.PVU or IWDG_SR.RVU is still set when timeout_ms milliseconds of the system time base HAL_GetTick() have elapsed during HAL_IWDG_Init, then the IWDG driver shall write the write-protect key 0x0000 to IWDG_KR.KEY so IWDG_PR and IWDG_RLR are no longer writable, omit the refresh key, and return HAL_TIMEOUT with the started watchdog running and write-protected.
  - Source: RM0486 p.2989; RM0486 p.2991; work-order scope.
  - Verification: Host unit test holding each flag and both flags set; at timeout_ms elapsed according to HAL_GetTick(), the final key is 0x0000, no 0xAAAA is written, configuration registers are protected, the watchdog remains started, and the result is HAL_TIMEOUT.
- **SWR-007** If HAL_IWDG_Init receives any invalid parameter (a NULL configuration pointer; a prescaler above 7; a reload value above 0xFFF; a timeout_ms of 0 or greater than HAL_IWDG_TIMEOUT_MS), then the IWDG driver shall return HAL_ERROR without any IWDG register access.
  - Source: RM0486 p.2990; work-order scope (software interface bounds).
  - Verification: Host unit test for NULL, prescaler 8, reload 0x1000, timeout_ms 0 and timeout_ms 49; each returns HAL_ERROR with no IWDG register reads or writes.
- **SWR-008** While HAL_IWDG_Init waits for completion of configuration updates, the IWDG driver shall bound the wait by the caller's timeout_ms measured using elapsed HAL_GetTick() milliseconds, including unsigned tick wraparound, with timeout_ms at most HAL_IWDG_TIMEOUT_MS = 48 ms and without a polling-iteration bound.
  - Source: RM0486 p.2991; work-order scope (48 ms development interface bound covering up to 6 LSI periods with margin).
  - Verification: Host unit test with varied tick progression and tick wraparound; a persistent busy flag causes timeout when timeout_ms elapsed HAL_GetTick() milliseconds is reached, for accepted bounds including 1 and 48 ms, independently of polling-iteration count.
- **SWR-009** When HAL_IWDG_Refresh is requested, the IWDG driver shall write 0xAAAA to IWDG_KR.KEY to reload the counter and return HAL_OK.
  - Source: RM0486 p.2989.
  - Verification: Host unit test; the refresh call writes 0xAAAA to IWDG_KR.KEY and returns HAL_OK.
- **SWR-010** While no watchdog initialisation has been requested after reset, the IWDG driver shall not write any IWDG register.
  - Source: RM0486 p.2989; work-order scope (explicit-call startup behaviour).
  - Verification: SWE.6 Robot suite with reset/startup evidence and no IWDG API calls; no IWDG register write attributable to the driver occurs before an initialisation request.
- **SWR-011** The IWDG driver shall occupy at most 4096 bytes of flash.
  - Source: work-order budget (owner development target).
  - Verification: SWE.6 Robot suite using the target build map; driver flash occupancy is at most 4096 bytes.
- **SWR-012** The IWDG driver shall occupy at most 64 bytes of static RAM.
  - Source: work-order budget (owner development target).
  - Verification: SWE.6 Robot suite using the target build map; driver static RAM occupancy is at most 64 bytes.
- **SWR-013** The IWDG driver shall use at most 128 bytes of stack.
  - Source: work-order budget (owner development target).
  - Verification: SWE.6 Robot suite using target compiler stack-usage evidence including the driver call chain; maximum driver stack usage is at most 128 bytes.
- **SWR-014** The IWDG driver shall implement its hal_status_t HAL_IWDG_Init API with a const configuration pointer and its hal_status_t HAL_IWDG_Refresh API exclusively through the provided LL_IWDG_ functions for IWDG register access.
  - Source: work-order scope (HAL interface and provided read-only LL driver).
  - Verification: Host unit build and source inspection; both APIs return hal_status_t, the initialisation configuration pointer is const, and all IWDG accesses use the provided LL_IWDG_ interface.

A started watchdog cannot be stopped: on SWR-006 the fallback is the running, write-protected watchdog. A watchdog reset follows unless the caller recovers by refreshing in time (RM0486 p.2989 and p.2991). No safety allocation is inferred from this functional response.

SWR-008 constrains elapsed time only. Update completion is a hardware status observation, not a software write to IWDG_SR.PVU or IWDG_SR.RVU (RM0486 p.2991). Its timeout register response is specified separately in SWR-006. The register contract records final observable register values; unit tests verify the intermediate start and write-access keys and their order.

## Open points

- Software safety allocation is PENDING owner allocation review for ASIL B scope SC-IWDG-2026-10-20; no software safety requirements are allocated yet.
- Human-approved upstream HSI, safety allocation and budgets contract inputs/upstream-inputs.yaml is not provided (manifest upstream status NOT_PROVIDED, UPSTREAM_FILE_MISSING). The manifest HSI reference and owner development budgets are the available basis.
- Target silicon revision is UNSPECIFIED in the manifest; revision-specific applicability remains unresolved.
