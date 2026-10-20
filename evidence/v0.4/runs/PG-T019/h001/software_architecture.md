# Software architecture

## Scope and baseline

Work order WO-0009B-STM32N6-IWDG-HAL-h001 implements the frozen SWE.1 baseline BL-SWE.1-001, hash 89c1208aeecc337c3a28c5aa5a4c53e73d1e38f2ec8f48d7ef4d9c4887eb9b5e. The architecture owns only the HAL. The PROVIDED LL is frozen from verified work order WO-0009A-STM32N6-IWDG-LL-i003.

Window operation is assumed disabled by the integration environment. Window, early interrupt, option bytes, low-power freeze and debug freeze configuration are outside this architecture. No watchdog-stop operation is provided. The watchdog enable state persists until reset (RM0486 p.2991).

## Components

- SWC_HAL: software/hal/stm32n6xx_hal_iwdg.h and software/hal/stm32n6xx_hal_iwdg.c. Publishes the configuration type, status type, bounds and two HAL APIs. Owns validation, ordered initialization, bounded polling and return status.
- SWC_LL: PROVIDED software/ll/stm32n6xx_ll_iwdg.h, header-only and read-only. Owns volatile register accesses. It is a dependency with no allocation of this work order's SWRs.
- IWDG: peripheral register block at base address 0x56004800 (RM0486 p.179).

Dependency direction is Caller -> HAL -> LL -> IWDG. HAL includes the PROVIDED LL header and calls only functions actually declared there. Required LL calls are LL_IWDG_Enable, LL_IWDG_EnableWriteAccess, LL_IWDG_SetPrescaler, LL_IWDG_SetReloadCounter, LL_IWDG_IsActiveFlag_PVU, LL_IWDG_IsActiveFlag_RVU and LL_IWDG_ReloadCounter. HAL performs no direct register access. No alternate LL implementation is part of the delivered driver; unit tests may substitute an LL fake under the manifest's ll-fake-v1 isolation contract.

Interfaces IF-01 and IF-02 in the static view respectively identify HAL-to-LL accessor calls and LL-to-IWDG volatile register access.

## Register access

The PROVIDED LL declares the register-block symbol as follows:

```c
extern volatile uint32_t ll_iwdg_regs[LL_IWDG_REG_COUNT];
```

LL_IWDG_REG_COUNT is 256U in the frozen LL. The target linker places this extern symbol at the IWDG base, 0x56004800 (RM0486 p.179); it is a memory-mapped peripheral symbol, not an allocated driver RAM buffer. LL indexes registers by their byte offset divided by 4U. There are no integer-to-pointer casts. Host tests define the array in host memory. The HAL neither defines the array nor indexes it.

The key accessor performs a whole-register write with reserved high bits zero. The provided prescaler and reload setters preserve bits outside their field masks; integration must retain reserved bits at their reset values (RM0486 p.2989; RM0486 p.2990). Status accessors only read their respective bits; HAL never writes SR (RM0486 p.2991).

## Interfaces

The public header includes stdint.h and stddef.h, making uint32_t and NULL available. Public declarations are:

```c
typedef enum
{
    HAL_OK = 0U,
    HAL_ERROR = 1U,
    HAL_TIMEOUT = 2U
} hal_status_t;

typedef struct
{
    uint32_t prescaler;
    uint32_t reload;
} hal_iwdg_config_t;

#define HAL_IWDG_TIMEOUT_VALUE 1000U

hal_status_t HAL_IWDG_Init(const hal_iwdg_config_t *p_config, uint32_t timeout);
hal_status_t HAL_IWDG_Refresh(void);
```

Prescaler is a raw register encoding in the inclusive API range 0U through 7U, not a divider value. Reload is in the inclusive range 0U through 0x0FFFU. Timeout is in the inclusive range 1U through HAL_IWDG_TIMEOUT_VALUE (1000U). Unsigned integer literals and address-of const hal_iwdg_config_t compound literals are valid caller arguments; the generated test caller may substitute its own timeout for the api_calls.json expression "{timeout}". Configurations with prescaler 8U or reload 0x1000U, NULL, timeout 0U and HAL_IWDG_TIMEOUT_VALUE + 1U are expressly representable invalid calls.

HAL_IWDG_Init validates the pointer before dereferencing it, then validates all scalar bounds before any LL call or register access. The pointer must designate readable configuration memory for the duration of the call. The function does not modify the configuration or retain its address.

For valid input the exact order is:
1. LL_IWDG_Enable(): write key 0xCCCC to start the watchdog (RM0486 p.2989).
2. LL_IWDG_EnableWriteAccess(): write key 0x5555 to enable configuration writes (RM0486 p.2989).
3. LL_IWDG_SetPrescaler(p_config->prescaler): update IWDG_PR.PR (RM0486 p.2990).
4. LL_IWDG_SetReloadCounter(p_config->reload): update IWDG_RLR.RL (RM0486 p.2990).
5. Poll LL_IWDG_IsActiveFlag_PVU() and LL_IWDG_IsActiveFlag_RVU() until both are zero, for at most timeout iterations (RM0486 p.2991).
6. If both are zero within the budget, call LL_IWDG_ReloadCounter() to write 0xAAAA, then return HAL_OK. This refresh also write-protects configuration registers (RM0486 p.2989).

HAL_IWDG_Refresh calls LL_IWDG_ReloadCounter() once to write 0xAAAA to IWDG_KR.KEY and returns HAL_OK (RM0486 p.2989). It has no argument, no wait, no state query and no retained software state. Its specified use is after initialization; the caller owns that sequencing.

## Timeouts and error handling

HAL_IWDG_Init returns HAL_ERROR for NULL or any invalid scalar input, before any IWDG read or write. There is no startup constructor, implicit initialization or background register access. Before the first explicit Init or Refresh request, the module performs no IWDG access.

There is one polling loop and one shared budget for both PVU and RVU. Each iteration samples PVU once and RVU once, including when PVU is set; a polling iteration therefore contains two LL flag reads. If both sampled flags are zero, success is accepted immediately, including on the final allowed iteration. If either flag is nonzero for all timeout iterations, return HAL_TIMEOUT immediately after the final iteration without another poll and without writing the refresh key. No unbounded wait, extra pre-loop read, second per-flag budget, tick dependency or interrupt dependency is used. All waits use the caller's timeout, never more than 1000 iterations. These are polling counts, not a wall-clock time guarantee.

After a timeout the watchdog has already been started and remains running until caller recovery or watchdog reset (RM0486 p.2989; RM0486 p.2991). No stop, refresh, configuration rollback or extra key write is attempted on the timeout path. Recovery belongs to the caller and must account for potentially pending configuration updates; no retry loop is hidden inside the HAL.

The hardware requires PVU clear before changing PR and RVU clear before changing RL (RM0486 p.2990; RM0486 p.2991). This architecture implements the frozen initial-start sequence. Reconfiguration with a previous update already pending remains an upstream open point; it does not add a preconfiguration wait or undocumented error status.

## Clock, reset and interference assumptions

The integration environment supplies a working target peripheral mapping and the clock/reset environment needed for IWDG operation. This HAL has no clock-tree, reset-controller or option-byte dependency in its API and performs no access to those peripherals. No clock frequency or hardware delay is assumed in the iteration bound. The reset behavior used here is the persistent active state described by RM0486 p.2991.

A single serialized caller owns IWDG configuration and refresh. Concurrent calls, interrupt accesses or other writers to the same peripheral must be serialized externally. The HAL changes only KR, PR and RLR through LL and reads only PVU and RVU. It does not allocate heap memory, schedule tasks, install interrupts, or access unrelated peripherals. Configurations with reload 0 or 1 are accepted as required, despite the hardware recommendation for at least 2 (RM0486 p.2990). No system recovery interval or safety integrity allocation is inferred.

## Memory and stack budget

| Resource | Limit | Design allocation and verification |
| --- | --- | --- |
| Flash | <=4096 B | Both HAL functions and their linked LL call paths; measure target linked driver allocation in SWE.6. |
| Static RAM | <=64 B | No HAL mutable globals or retained configuration; expected HAL static RAM 0 B. MMIO symbol is not driver RAM; host test array belongs to tests. Verify linked target allocation in SWE.6. |
| Stack | <=128 B | Fixed scalar validation, two sampled flags and a loop counter; no recursion, VLA or heap. Measure maximum target call path including LL in SWE.6. |

The caller owns the two-uint32_t configuration object. Budgets are owner development targets, not measured results at SWE.2. Inline LL code still contributes to the linked HAL flash and maximum call-path stack accounting.

## Requirement allocation table

Every requirement is owned by SWC_HAL; no SWR is allocated to the PROVIDED SWC_LL. Resource requirements apply to the aggregate driver, including linked LL code used by the HAL.

| SWR | Component | Function | Allocation |
| --- | --- | --- | --- |
| SWR-001 | SWC_HAL | HAL_IWDG_Init; HAL_IWDG_Refresh | Passive module before explicit request; no implicit register access. |
| SWR-002 | SWC_HAL | HAL_IWDG_Init | Start, access, configure, bounded update check, refresh and HAL_OK. |
| SWR-003 | SWC_HAL | HAL_IWDG_Init | Prescaler API range 0..7 and LL prescaler write. |
| SWR-004 | SWC_HAL | HAL_IWDG_Init | Reload API range 0..0xFFF and LL reload write. |
| SWR-005 | SWC_HAL | HAL_IWDG_Refresh | Refresh key and HAL_OK. |
| SWR-006 | SWC_HAL | HAL_IWDG_Init | Validate every input before all register access; HAL_ERROR. |
| SWR-007 | SWC_HAL | HAL_IWDG_Init | HAL_TIMEOUT without refresh if either update flag remains set. |
| SWR-008 | SWC_HAL | HAL_IWDG_Init | Single polling budget of at most timeout <=1000 iterations. |
| SWR-009 | SWC_HAL | HAL_IWDG_Init | Leave started watchdog running after timeout; caller recovery. |
| SWR-010 | SWC_HAL | HAL_IWDG_Init; HAL_IWDG_Refresh | Aggregate flash <=4096 B. |
| SWR-011 | SWC_HAL | HAL_IWDG_Init; HAL_IWDG_Refresh | Aggregate static RAM <=64 B. |
| SWR-012 | SWC_HAL | HAL_IWDG_Init; HAL_IWDG_Refresh | Maximum call-path stack <=128 B including LL. |

## Register table

The following table is the complete hardware interface used by this HAL. SWE.3 shall use this table and the frozen LL accessors, without adding hardware fields. Register offsets are byte offsets from base 0x56004800 (RM0486 p.179). A field row supplies the field mask and the only permitted use; register rows specify the whole-register boundary.

| Name | Offset | Bit position(s) | Access | RM0486 page |
| --- | --- | --- | --- | --- |
| IWDG_KR | 0x00 | 31:0; 31:16 reserved, kept zero | Write only key interface; no read; whole-register writes | RM0486 p.2989 |
| IWDG_KR.KEY | 0x00 | 15:0; mask 0x0000FFFF | W; 0xCCCC start, 0x5555 write access, 0xAAAA refresh and write protection | RM0486 p.2989 |
| IWDG_PR | 0x04 | 31:0; 31:4 reserved at reset value | RW; LL read-modify-write preserves bits outside PR | RM0486 p.2989; RM0486 p.2990 |
| IWDG_PR.PR | 0x04 | 3:0; mask 0x0000000F | RW, write protected; HAL accepts 0..7; change only with PVU clear | RM0486 p.2990 |
| IWDG_RLR | 0x08 | 31:0; 31:12 reserved at reset value | RW; LL read-modify-write preserves bits outside RL | RM0486 p.2990 |
| IWDG_RLR.RL | 0x08 | 11:0; mask 0x00000FFF | RW, write protected; HAL accepts 0..0xFFF; change only with RVU clear | RM0486 p.2990 |
| IWDG_SR | 0x0C | 31:0; HAL observes only bits 1:0 | R; no HAL writes; each LL flag query reads SR | RM0486 p.2990; RM0486 p.2991 |
| IWDG_SR.PVU | 0x0C | 0; mask 0x00000001 | R; 1 means prescaler update ongoing, hardware clears on completion | RM0486 p.2991 |
| IWDG_SR.RVU | 0x0C | 1; mask 0x00000002 | R; 1 means reload update ongoing, hardware clears on completion | RM0486 p.2991 |

## Architecture views and call evidence

architecture_static.puml contains the two distinct SWC components, interface identifiers and complete SWR ownership note. architecture_dynamic.puml contains invalid-input, successful-init, timeout and refresh paths. api_calls.json maps every SWE.1 register-effects case to an allocated public function and valid C argument expressions, including each required invalid value. Traceability matrix generation is owned by the deterministic gate.
