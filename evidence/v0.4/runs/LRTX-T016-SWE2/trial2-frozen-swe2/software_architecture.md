# Software architecture

Work order: WO-0009A-STM32N6-IWDG-LL-rc1. Input baseline: BL-SWE.1-001 (hash 3a9658a6b12b3d9641cd071e7a984e1f782b6e276d6df9ffe54b2be676250fd2). Authority: the frozen SWE.1 work products, the work-order manifest and the RM0486 sections supplied with the work order.

## Components

The software component SWC_LL owns the static inline LL driver functions providing direct access to IWDG hardware registers without maintaining any driver-owned state. The caller or integration layer is responsible for managing timeouts, polling logic, and coordinating access to the watchdog interface. Integration must place the register-block array ll_iwdg_regs at the base address 0x56004800 by the linker as per the generated memory map, ensuring volatile access semantics and proper alignment. The component does not own or manage any hardware configuration beyond direct register writes and status reads.

Developed software component: SWC_LL, the header-only LL library stm32n6xx_ll_iwdg.h (static inline functions). The IWDG register block is hardware, not a software component.

## Register access

Register block: `extern volatile uint32_t ll_iwdg_regs[];` placed at the IWDG base address 0x56004800 (RM0486 p.179) by the linker; host tests define the array in RAM. Every access uses ll_iwdg_regs[LL_IWDG_<REG>_OFFSET / 4U]; no integer-to-pointer casts.

All register access is performed via the extern volatile uint32_t array ll_iwdg_regs accessed through computed offsets divided by four. Keys are written to IWDG_KR as a whole register write only, since it is a write-only key register. Other registers such as IWDG_PR, IWDG_RLR are updated using read-modify-write operations preserving the intact bits unless they are fully write-only and thus require whole-register writes. Clock and reset dependencies for IWDG are handled through integration of the peripheral clock enablement and reset assertions, not by the LL component itself.

## Interfaces

| Function signature | Operation | Register fields |
| --- | --- | --- |
| static inline void LL_IWDG_Enable(void) | Write 0x0000CCCC to IWDG_KR.KEY | IWDG_KR.KEY |
| static inline void LL_IWDG_ReloadCounter(void) | Write 0x0000AAAA to IWDG_KR.KEY | IWDG_KR.KEY |
| static inline void LL_IWDG_EnableWriteAccess(void) | Write 0x00005555 to IWDG_KR.KEY | IWDG_KR.KEY |
| static inline void LL_IWDG_DisableWriteAccess(void) | Write 0x00000000 to IWDG_KR.KEY | IWDG_KR.KEY |
| static inline void LL_IWDG_SetPrescaler(uint32_t prescaler) | Write prescaler value to IWDG_PR.PR | IWDG_PR.PR |
| static inline void LL_IWDG_SetReloadCounter(uint32_t counter) | Write counter value to IWDG_RLR.RL | IWDG_RLR.RL |
| static inline uint32_t LL_IWDG_IsActiveFlag_PVU(void) | Return 1U if IWDG_SR.PVU is set, otherwise 0U | IWDG_SR.PVU |
| static inline uint32_t LL_IWDG_IsActiveFlag_RVU(void) | Return 1U if IWDG_SR.RVU is set, otherwise 0U | IWDG_SR.RVU |
| static inline uint32_t LL_IWDG_IsEnabled(void) | Return 1U if IWDG_SR.ONF is set, otherwise 0U | IWDG_SR.ONF |

Interface ids: IF-01 Caller -> SWC_LL (LL API above); IF-02 SWC_LL -> register block (volatile register-array access).

## Timing and error handling

No waiting or timeout handling at LL level is performed. The implementation does not return error codes or provide blocking behavior. All polling must be bounded to a specific loop in the caller's context. This allows for flexible integration with different application-level timing constraints and avoids unbounded delays, keeping the LL layer lightweight and suitable for low-latency contexts.

## Memory and stack budget

| Budget | Limit | Allocated to | Requirement |
| --- | --- | --- | --- |
| Flash | 4096 B | SWC_LL | SWR-014 |
| Static RAM | 64 B | SWC_LL | - |
| Stack per API call | 128 B | SWC_LL | SWR-016 |

The Flash memory usage of the LL module is allocated within a limit of 4096 bytes, which includes code size for all static inline functions. Static RAM consumption remains within 64 bytes, and stack usage for function calls is bounded below 128 bytes, satisfying the requirements for a header-only driver suitable for resource-constrained microcontroller environments.

## Concurrency and reentrancy

The LL driver is reentrant and suitable for use in both task-level and ISR contexts. However, read-modify-write operations (e.g., setting prescaler or reload) may not be atomic if the register access spans multiple memory locations or if interrupts are disabled during an operation, requiring callers to perform serialisation of access to prevent race conditions when multiple tasks or ISRs interact with these fields.

## Safety mechanisms, degraded states and dependencies

The LL driver does not implement safety mechanisms such as error reporting or degradation handling. It assumes the integration handles proper ordering of register accesses, correct use of keys, and appropriate clock/reset assertions. The functionality provided is directly mapped to hardware behavior, without additional checks for operational integrity. Dependencies on the integration include correct peripheral base address placement, access key sequence correctness, and bounded polling loop implementation by caller.

## Architecture decisions

- The IWDG LL layer implements only header-only static inline functions to minimize code size and maximize performance in constrained embedded environments.
- Keys are written as complete register writes to the IWDG_KR register because it is a write-only register that does not support read-modify-write operations.
- All register updates for IWDG_PR, IWDG_RLR etc. use read-modify-write semantics except when they are fully write-only registers, which require whole-register writes.
- No timing, waiting or error handling is implemented at LL level; polling loops must be bounded and handled by the caller to satisfy real-time requirements.
- The driver assumes correct integration of clock enablement and reset state prior to invoking IWDG functions.
- Caller-bound access control ensures that concurrent access is serialized outside of the driver to prevent conflicts during register updates.

## Requirement allocation table

| Requirement | Function allocation | Responsibility |
| --- | --- | --- |
| SWR-001 | LL_IWDG_Enable | Start the watchdog timer |
| SWR-002 | LL_IWDG_ReloadCounter | Refresh the watchdog timer |
| SWR-003 | LL_IWDG_EnableWriteAccess | Enable write access to configuration registers |
| SWR-004 | LL_IWDG_DisableWriteAccess | Disable write access to configuration registers |
| SWR-005 | LL_IWDG_SetPrescaler | Set the prescaler value for the watchdog timer |
| SWR-006 | LL_IWDG_SetReloadCounter | Set the reload value for the watchdog timer |
| SWR-007 | LL_IWDG_IsActiveFlag_PVU | Check if prescaler value is updated |
| SWR-008 | LL_IWDG_IsActiveFlag_PVU | Check if prescaler value is updated |
| SWR-009 | LL_IWDG_IsActiveFlag_RVU | Check if reload value is updated |
| SWR-010 | LL_IWDG_IsActiveFlag_RVU | Check if reload value is updated |
| SWR-011 | LL_IWDG_IsEnabled | Check if watchdog timer is active |
| SWR-012 | LL_IWDG_IsEnabled | Check if watchdog timer is active |
| SWR-013 | all LL functions (component-level constraint of SWC_LL, no dedicated function) | While no LL function has been called after reset, the IWDG LL driver shall not write any IWDG register. |
| SWR-014 | all LL functions (component-level constraint of SWC_LL, no dedicated function) | The IWDG LL driver shall occupy at most 4096 bytes of flash in the linked target verification image. |
| SWR-015 | LL_IWDG_Enable, LL_IWDG_ReloadCounter, LL_IWDG_EnableWriteAccess, LL_IWDG_DisableWriteAccess, LL_IWDG_SetPrescaler, LL_IWDG_SetReloadCounter, LL_IWDG_IsActiveFlag_PVU, LL_IWDG_IsActiveFlag_RVU, LL_IWDG_IsEnabled | IWDG LL driver uses 0 bytes of static RAM for driver-owned state |
| SWR-016 | all LL functions (component-level constraint of SWC_LL, no dedicated function) | The IWDG LL driver shall use at most 128 bytes of stack for any public API call. |

## Register table

IWDG base address 0x56004800. Offsets are bytes; the array index is offset / 4U.

| Name | Offset | Bit position(s) | Access | RM0486 page |
| --- | --- | --- | --- | --- |
| IWDG_KR | 0x00 | 15:0 (KEY) | w | p.2989 |
| IWDG_PR | 0x04 | 3:0 (PR) | rw | p.2989 |
| IWDG_RLR | 0x08 | 11:0 (RL) | rw | p.2990 |
| IWDG_SR | 0x0C | 0 (PVU) | r | p.2990 |
| IWDG_SR | 0x0C | 1 (RVU) | r | p.2990 |
| IWDG_SR | 0x0C | 8 (ONF) | r | p.2990 |
