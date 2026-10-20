# Software requirements

- **SWR-001** When HAL_IWDG_Init is requested with a valid configuration and IWDG_SR.PVU and IWDG_SR.RVU clear within the supplied timeout, the IWDG driver shall write 0xCCCC then 0x5555 to IWDG_KR.KEY before configuring the prescaler and reload, wait for both update flags to clear after configuration, then write 0xAAAA to IWDG_KR.KEY and return HAL_OK.
  - Source: RM0486 p.2989; RM0486 p.2991; work-order initialisation scope.
  - Verification: Host unit test with immediate and delayed update completion; pass if the start, access and refresh keys occur in that order, configuration occurs between access and refresh, refresh follows both flags clearing within the supplied timeout, and HAL_OK is returned.
- **SWR-002** When HAL_IWDG_Init is requested with a valid configuration, the IWDG driver shall write the configured prescaler encoding from 0 through 7 to IWDG_PR.PR before waiting for update completion.
  - Source: RM0486 p.2990; work-order HAL parameter range.
  - Verification: Host unit test for all supported prescaler encodings and a subsequent update timeout; pass if IWDG_PR.PR equals the configured encoding.
- **SWR-003** When HAL_IWDG_Init is requested with a valid configuration, the IWDG driver shall write the configured reload value from 0 through 0xFFF to IWDG_RLR.RL before waiting for update completion.
  - Source: RM0486 p.2990.
  - Verification: Host unit test for reload values 0, 1, 2, 0xABC and 0xFFF; pass if IWDG_RLR.RL equals the configured value.
- **SWR-004** When HAL_IWDG_Refresh is requested, the IWDG driver shall write 0xAAAA to IWDG_KR.KEY and return HAL_OK.
  - Source: RM0486 p.2989.
  - Verification: Host unit test; pass if IWDG_KR.KEY receives 0xAAAA and the result is HAL_OK.
- **SWR-005** When HAL_IWDG_Init is requested with any invalid parameter (a NULL configuration pointer or a prescaler above 7 or a reload value above 0xFFF or a timeout argument of 0 or greater than HAL_IWDG_TIMEOUT_VALUE), the IWDG driver shall return HAL_ERROR without accessing any IWDG register.
  - Source: RM0486 p.2990; work-order invalid-parameter response.
  - Verification: Host unit tests for each invalid input independently, including timeout 0 and HAL_IWDG_TIMEOUT_VALUE + 1; pass if each result is HAL_ERROR with no IWDG register access.
- **SWR-006** If IWDG_SR.PVU or IWDG_SR.RVU is still set after the supplied update timeout during HAL_IWDG_Init, then the IWDG driver shall return HAL_TIMEOUT with the configured values retained in IWDG_PR.PR and IWDG_RLR.RL and without writing the refresh key 0xAAAA to IWDG_KR.KEY.
  - Source: RM0486 p.2989; RM0486 p.2991; work-order update-timeout response.
  - Verification: Host unit tests holding PVU, RVU and both flags set; pass if each call returns HAL_TIMEOUT within the supplied polling-iteration bound and never writes the refresh key.
- **SWR-007** While the watchdog remains started after an update timeout, the IWDG driver shall leave the watchdog running as the fallback state without attempting to stop it.
  - Source: RM0486 p.2989; RM0486 p.2991; work-order scope excluding watchdog stop.
  - Verification: Target verification with a started watchdog and induced update timeout; pass if the watchdog remains active and generates a watchdog reset on counter expiry unless the caller recovers by refreshing it.
- **SWR-008** When any update wait is performed, the IWDG driver shall bound that wait by the supplied timeout in polling iterations, with every wait bounded by HAL_IWDG_TIMEOUT_VALUE = 1000 polling iterations.
  - Source: RM0486 p.2991; work-order bounded-wait policy.
  - Verification: Host unit tests using timeouts 1, 17 and 1000 with held update flags; pass if each wait terminates within its supplied bound and at most HAL_IWDG_TIMEOUT_VALUE polling iterations.
- **SWR-009** While no watchdog initialisation has been requested after reset, the IWDG driver shall not write any IWDG register.
  - Source: RM0486 p.2989; work-order reset/startup behaviour.
  - Verification: Target startup verification before the first explicit watchdog initialisation request; pass if the IWDG driver performs no IWDG register writes.
- **SWR-010** The IWDG driver shall occupy at most 4096 bytes of flash.
  - Source: work-order budget (owner development target).
  - Verification: SWE.6 Robot suite checks the target build size evidence; pass if driver flash usage is at most 4096 bytes.
- **SWR-011** The IWDG driver shall occupy at most 64 bytes of static RAM.
  - Source: work-order budget (owner development target).
  - Verification: SWE.6 Robot suite checks the target build size evidence; pass if driver static RAM usage is at most 64 bytes.
- **SWR-012** The IWDG driver shall use at most 128 bytes of stack.
  - Source: work-order budget (owner development target).
  - Verification: SWE.6 Robot suite checks the target stack evidence for the deepest driver call path including LL calls; pass if stack usage is at most 128 bytes.

## Open points

- Software safety allocation is PENDING owner allocation review for ASIL B scope SC-IWDG-2026-10-20; no software safety requirement is allocated yet.
- Human-approved upstream requirements and HSI contract file inputs/upstream-inputs.yaml are not provided; the manifest HSI description and owner budgets are the available upstream basis.
- Silicon revision is UNSPECIFIED in the manifest.
- The HAL range is deliberately 0 through 7 for the prescaler despite RM0486 p.2990 defining additional hardware encodings; reload values 0 and 1 remain valid although RM0486 p.2990 discourages values below 2.
- Polling iterations are a software bound, not an elapsed-time guarantee; clock-dependent watchdog expiry and caller recovery deadlines require target integration evidence.
- Reconfiguration while an earlier prescaler or reload update is already pending requires an owner-approved interface policy; RM0486 p.2990 requires the respective update flag to be clear before changing its field.
