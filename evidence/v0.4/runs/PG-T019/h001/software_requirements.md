# Software requirements

- **SWR-001** While no watchdog initialisation has been requested after reset, the IWDG driver shall perform no IWDG register access.
  - Source: RM0486 p.2989; work-order startup behaviour.
  - Verification: Host unit test observes no IWDG register access from reset until an initialisation request, with no explicit refresh request.
- **SWR-002** When HAL_IWDG_Init is requested with a valid configuration, the IWDG driver shall write 0xCCCC followed by 0x5555 to IWDG_KR.KEY before configuring IWDG_PR.PR and IWDG_RLR.RL, then write 0xAAAA to IWDG_KR.KEY and return HAL_OK when IWDG_SR.PVU and IWDG_SR.RVU both clear within the caller-supplied timeout.
  - Source: RM0486 p.2989; RM0486 p.2991; work-order initialisation sequence.
  - Verification: Host unit test observes the ordered start and access keys before configuration writes and the refresh key with HAL_OK after both update flags clear within the supplied timeout; the final key is 0xAAAA.
- **SWR-003** When HAL_IWDG_Init is requested with a valid configuration, the IWDG driver shall write the configured prescaler value in the range 0 through 7 to IWDG_PR.PR before waiting for update completion.
  - Source: RM0486 p.2990; work-order prescaler API range.
  - Verification: Host unit test varies the prescaler across 0 through 7, including 4, and observes the configured IWDG_PR.PR value before the update wait.
- **SWR-004** When HAL_IWDG_Init is requested with a valid configuration, the IWDG driver shall write the configured reload value in the range 0 through 0xFFF to IWDG_RLR.RL before waiting for update completion.
  - Source: RM0486 p.2990; work-order reload API range.
  - Verification: Host unit test exercises reload values 0, 1, 2, 0xABC and 0xFFF and observes the configured IWDG_RLR.RL value before the update wait.
- **SWR-005** When HAL_IWDG_Refresh is requested after watchdog initialisation, the IWDG driver shall write 0xAAAA to IWDG_KR.KEY and return HAL_OK.
  - Source: RM0486 p.2989.
  - Verification: Host unit test observes IWDG_KR.KEY equal to 0xAAAA and a HAL_OK return for a refresh request.
- **SWR-006** If HAL_IWDG_Init receives any invalid parameter (a NULL configuration pointer or a prescaler above 7 or a reload value above 0xFFF or a timeout argument of 0 or greater than HAL_IWDG_TIMEOUT_VALUE), then the IWDG driver shall return HAL_ERROR without any IWDG register access.
  - Source: RM0486 p.2989; RM0486 p.2990; work-order invalid-parameter response and API bounds.
  - Verification: Host unit test independently supplies a NULL pointer, prescaler 8, reload 0x1000, timeout 0 and timeout HAL_IWDG_TIMEOUT_VALUE + 1, and observes HAL_ERROR with no register access for each case.
- **SWR-007** If IWDG_SR.PVU or IWDG_SR.RVU remains set after the caller-supplied update timeout following configuration writes, then the IWDG driver shall return HAL_TIMEOUT without writing the refresh key 0xAAAA to IWDG_KR.KEY.
  - Source: RM0486 p.2989; RM0486 p.2991; work-order update-timeout response.
  - Verification: Host unit test holds PVU and RVU set in separate cases and observes HAL_TIMEOUT within the supplied timeout, with no refresh-key write after configuration.
- **SWR-008** While an update wait is in progress during HAL_IWDG_Init, the IWDG driver shall bound every wait by the caller-supplied timeout of at most HAL_IWDG_TIMEOUT_VALUE = 1000 polling iterations.
  - Source: RM0486 p.2991; work-order timing bound.
  - Verification: Host unit test holds update flags set with timeout values 1 and 1000 and observes each wait terminate within the supplied bound, at most HAL_IWDG_TIMEOUT_VALUE polling iterations.
- **SWR-009** If an update timeout occurs after the watchdog has started, then the IWDG driver shall leave the watchdog running as the fallback state until caller recovery or watchdog reset.
  - Source: RM0486 p.2989; RM0486 p.2991; work-order fallback behaviour.
  - Verification: Target test forces an update timeout and observes the running watchdog remain active after HAL_TIMEOUT and generate a watchdog reset when the caller does not recover or refresh it.
- **SWR-010** The IWDG driver shall occupy at most 4096 bytes of flash.
  - Source: work-order budget (owner development target).
  - Verification: SWE.6 Robot suite measures the linked target driver flash allocation and passes when it is at most 4096 bytes.
- **SWR-011** The IWDG driver shall occupy at most 64 bytes of static RAM.
  - Source: work-order budget (owner development target).
  - Verification: SWE.6 Robot suite measures the linked target driver static RAM allocation and passes when it is at most 64 bytes.
- **SWR-012** The IWDG driver shall use at most 128 bytes of stack.
  - Source: work-order budget (owner development target).
  - Verification: SWE.6 Robot suite evaluates the maximum driver call-path stack usage, including called LL functions, and passes when it is at most 128 bytes.

## Open points

- Safety allocation is NOT_PROVIDED: no owner safety scope is recorded for the IWDG work orders; no ASIL or QM allocation can be inferred.
- The human-approved upstream input file is absent; stakeholder-level HSI approval, safety allocation and upstream requirement identifiers remain unavailable.
- The manifest specifies silicon_revision as UNSPECIFIED.
- Prescaler values above 7 are rejected by this work-order API even though RM0486 p.2990 defines higher encodings as divider /1024.
- RM0486 p.2990 recommends reload values of at least 2; the work-order validation contract accepts 0 and 1 without guaranteeing a useful recovery interval.
- Initialisation is scoped to the work-order sequence with window operation disabled; reconfiguration while a previous prescaler or reload update is already pending requires owner clarification because RM0486 p.2991 permits those field changes only when the corresponding flag is clear.
- The 1000-iteration bound is a software polling bound; no wall-clock duration or system fault-tolerant time interval is allocated.
