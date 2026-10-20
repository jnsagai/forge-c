# Software architecture

Work order: WO-0002A-STM32N6-RCC-LL-r170.
Architecture component owner: SWC_LL.
Input baseline: BL-SWE.1-001, hash dc079fae1044c698b859894d01350caf0fbd4b8c1523fdd49beaf8386c4c20ff.
Authoritative requirements: workproducts/SWE.1/software_requirements.md.
Register-effect cases: workproducts/SWE.1/register_effects.json.

## Components

The sole software component is SWC_LL, RCC_LL, implemented by the header-only module stm32n6xx_ll_rcc.h in software/ll/. It provides exactly the 16 static inline functions below. Its dependency is <stdint.h> for uint32_t and the externally supplied RCC register-block array. The caller owns sequencing, polling, hardware permissions and concurrency control.

No HAL component is part of this work order. A later HAL work order builds on this LL. Scope is HSI, HSE, GPDMA1 and ADC12, as allocated by SWE.1 and the supplied RM0486 sections. Additional buses, oscillators, PLL configuration, clock-tree switching, security configuration, interrupts and low-power configuration have no architecture allocation here.

The static view is architecture_static.puml; the dynamic view is architecture_dynamic.puml. SWC_LL owns every SWR. IF-01 connects the caller to the LL API; IF-02 connects the LL to the register block. api_calls.json binds each register-effect case to its allocated interface.

## Register access

RCC base address is 0x56028000 (RM0486 p.176). Declare the register block without defining driver storage:

```c
extern volatile uint32_t ll_rcc_regs[];
```

The target linker supplies ll_rcc_regs at 0x56028000 as an absolute register-block symbol. No RAM section, initializer, startup routine, pointer variable or integer-to-pointer cast is used for this mapping. Host tests supply a real volatile uint32_t array with at least 149 elements, covering offset 0x250 through its complete 32-bit word. The target MMIO block and the host fixture are external to driver-owned RAM.

Every access uses ll_rcc_regs[LL_RCC_<REG>_OFFSET / 4U], with <REG> concretely CR, SR, AHB1RSTR or AHB1ENR. Offsets are byte offsets from the RCC base; accesses are uint32_t wide. Define these constants in the header:

```c
#define LL_RCC_CR_OFFSET 0x000U
#define LL_RCC_SR_OFFSET 0x004U
#define LL_RCC_AHB1RSTR_OFFSET 0x210U
#define LL_RCC_AHB1ENR_OFFSET 0x250U
#define LL_RCC_CR_HSION (1U << 3U)
#define LL_RCC_CR_HSEON (1U << 4U)
#define LL_RCC_SR_HSIRDY (1U << 3U)
#define LL_RCC_SR_HSERDY (1U << 4U)
#define LL_RCC_AHB1ENR_GPDMA1EN (1U << 4U)
#define LL_RCC_AHB1ENR_ADC12EN (1U << 5U)
#define LL_RCC_AHB1RSTR_GPDMA1RST (1U << 4U)
#define LL_RCC_AHB1RSTR_ADC12RST (1U << 5U)
```

The Register table is the complete hardware implementation contract for SWE.3. For set operations, perform one volatile read followed by one volatile write of the read value OR the specified mask. For clear operations, perform one volatile read followed by one volatile write of the read value AND the uint32_t complement of the specified mask. This single read-modify-write operation preserves every other bit and does not access another register. The implementation must not clear reserved bits as a side effect; callers maintain valid hardware reserved-bit values (RM0486 p.479, p.481, p.548, p.575).

For a query, read the specified register exactly once, mask the specified bit and return 1U if nonzero or 0U otherwise. Queries perform no writes. Ready queries read RCC_SR hardware flags, independently of RCC_CR enable bits (RM0486 p.482). No LL startup code runs and no register is written before an explicit modifying call. A header inclusion alone has no register effects.

## Interfaces

All functions take (void), have internal linkage through static inline definitions, and use the standard uint32_t type from <stdint.h>. Modifying functions return void. Query functions return uint32_t with exactly 1U or 0U. No input parameters, context handles, callbacks, status enums or error codes are defined.

| Function declaration | Register/bit | Operation |
| --- | --- | --- |
| static inline void LL_RCC_HSI_Enable(void); | RCC_CR.HSION | set |
| static inline void LL_RCC_HSI_Disable(void); | RCC_CR.HSION | clear |
| static inline void LL_RCC_HSE_Enable(void); | RCC_CR.HSEON | set |
| static inline void LL_RCC_HSE_Disable(void); | RCC_CR.HSEON | clear |
| static inline uint32_t LL_RCC_HSI_IsReady(void); | RCC_SR.HSIRDY | query |
| static inline uint32_t LL_RCC_HSE_IsReady(void); | RCC_SR.HSERDY | query |
| static inline void LL_RCC_GPDMA1_Enable(void); | RCC_AHB1ENR.GPDMA1EN | set |
| static inline void LL_RCC_GPDMA1_Disable(void); | RCC_AHB1ENR.GPDMA1EN | clear |
| static inline uint32_t LL_RCC_GPDMA1_IsEnabled(void); | RCC_AHB1ENR.GPDMA1EN | query |
| static inline void LL_RCC_GPDMA1_ForceReset(void); | RCC_AHB1RSTR.GPDMA1RST | set |
| static inline void LL_RCC_GPDMA1_ReleaseReset(void); | RCC_AHB1RSTR.GPDMA1RST | clear |
| static inline void LL_RCC_ADC12_Enable(void); | RCC_AHB1ENR.ADC12EN | set |
| static inline void LL_RCC_ADC12_Disable(void); | RCC_AHB1ENR.ADC12EN | clear |
| static inline uint32_t LL_RCC_ADC12_IsEnabled(void); | RCC_AHB1ENR.ADC12EN | query |
| static inline void LL_RCC_ADC12_ForceReset(void); | RCC_AHB1RSTR.ADC12RST | set |
| static inline void LL_RCC_ADC12_ReleaseReset(void); | RCC_AHB1RSTR.ADC12RST | clear |

Enable sets the allocated enable bit; Disable clears it. ForceReset asserts the allocated peripheral reset bit and ReleaseReset clears it (RM0486 p.480, p.548, p.575). Neither reset operation implies any clock change. IsEnabled observes the allocated enable bit, not oscillator readiness or peripheral activity (RM0486 p.575). Register constants and array mapping are defined in Register access; every API call in api_calls.json has args [].

## Timing and error handling

There is no waiting, retry loop, timeout, delay, error code or parameter validation at LL level. Each function performs one logical register operation: either a single read for a query or a single read-modify-write for a modifier. A read-modify-write comprises two volatile bus accesses; no claim of a single bus access is made for modifying functions.

The caller bounds its own polling of LL_RCC_HSI_IsReady or LL_RCC_HSE_IsReady and decides what to do when its bound is exhausted. Enable does not promise that the oscillator is ready on return (RM0486 p.480, p.482). LL code neither polls nor writes a ready flag. Hardware startup time and a numerical polling bound are not specified by these requirements. No numerical cycle-time or physical-target timing result is claimed.

A caller sequences clock enable and reset assertion/release explicitly, as shown in the dynamic diagram. The LL makes no implicit calls to other LL APIs. Callers satisfy hardware security and privilege permissions before accessing RCC; these protections are documented for the allocated bits (RM0486 p.480, p.482, p.548, p.575).

## Memory and stack budget

Flash contribution is at most 4096 B for a target build exercising all LL functions (SWR-019). Driver-owned static RAM is 0 B: there is no mutable state, register-block definition, .data or .bss allocation (SWR-020), meeting the manifest's 64 B upper bound. The external register symbol and host fixture are excluded from driver state.

Stack use attributable to any individual LL call is at most 128 B including any callees (SWR-021). Functions contain no recursion, variable-length arrays, dynamic allocation or nested calls; expressions use only scalar uint32_t values. These are design budgets, to be verified with target link-map/size differences and compiler stack-usage reports and disassembly as required by SWE.1. This architecture asserts no measured build results.

## Concurrency and reentrancy

The LL keeps no state and is reentrant. Shared-register read-modify-write is not atomic. This architecture uses the base registers in the Register table, rather than the documented set/clear aliases; no set/clear-alias offsets are introduced from unavailable sections.

Callers serialise every modifying access to a shared RCC register, including accesses by other driver components, for example in a critical section. No LL function is called from an ISR concurrently with an access to the same register. Protection must cover both the read and the write; volatile alone does not provide mutual exclusion. Host tests likewise avoid concurrent fixture modification during a call. Hardware can update the read-only ready flags independently (RM0486 p.482).

Freedom from interference relies on caller serialization, correct linker mapping and valid access permissions. The driver confines each modifier to its allocated bit, preserves other bits and other registers, and keeps no shared software state. This is not an allocation of additional safety requirements.

## Requirement allocation table

Every row is owned by SWC_LL (stm32n6xx_ll_rcc). The interface set is exactly the set in Interfaces.

| Requirement | Concrete LL function(s) | Allocation / responsibility |
| --- | --- | --- |
| SWR-001 | LL_RCC_HSI_Enable | set RCC_CR.HSION |
| SWR-002 | LL_RCC_HSI_Disable | clear RCC_CR.HSION |
| SWR-003 | LL_RCC_HSE_Enable | set RCC_CR.HSEON |
| SWR-004 | LL_RCC_HSE_Disable | clear RCC_CR.HSEON |
| SWR-005 | LL_RCC_HSI_IsReady | query RCC_SR.HSIRDY |
| SWR-006 | LL_RCC_HSE_IsReady | query RCC_SR.HSERDY |
| SWR-007 | LL_RCC_GPDMA1_Enable | set RCC_AHB1ENR.GPDMA1EN |
| SWR-008 | LL_RCC_GPDMA1_Disable | clear RCC_AHB1ENR.GPDMA1EN |
| SWR-009 | LL_RCC_GPDMA1_IsEnabled | query RCC_AHB1ENR.GPDMA1EN |
| SWR-010 | LL_RCC_GPDMA1_ForceReset | set RCC_AHB1RSTR.GPDMA1RST |
| SWR-011 | LL_RCC_GPDMA1_ReleaseReset | clear RCC_AHB1RSTR.GPDMA1RST |
| SWR-012 | LL_RCC_ADC12_Enable | set RCC_AHB1ENR.ADC12EN |
| SWR-013 | LL_RCC_ADC12_Disable | clear RCC_AHB1ENR.ADC12EN |
| SWR-014 | LL_RCC_ADC12_IsEnabled | query RCC_AHB1ENR.ADC12EN |
| SWR-015 | LL_RCC_ADC12_ForceReset | set RCC_AHB1RSTR.ADC12RST |
| SWR-016 | LL_RCC_ADC12_ReleaseReset | clear RCC_AHB1RSTR.ADC12RST |
| SWR-017 | LL_RCC_HSI_Enable, LL_RCC_HSI_Disable, LL_RCC_HSE_Enable, LL_RCC_HSE_Disable, LL_RCC_GPDMA1_Enable, LL_RCC_GPDMA1_Disable, LL_RCC_GPDMA1_ForceReset, LL_RCC_GPDMA1_ReleaseReset, LL_RCC_ADC12_Enable, LL_RCC_ADC12_Disable, LL_RCC_ADC12_ForceReset, LL_RCC_ADC12_ReleaseReset | Preserve all bits except the allocated bit and preserve all other registers through read-modify-write. |
| SWR-018 | all LL functions | No startup execution or implicit register writes; no calls means no register writes. |
| SWR-019 | all LL functions | Flash contribution <=4096 B. |
| SWR-020 | all LL functions | Driver-owned static RAM 0 B. |
| SWR-021 | all LL functions | Incremental stack <=128 B per call. |

## Register table

One row per used register/bit; no other register or bit is accessed. Offsets are relative to RCC base 0x56028000 (RM0486 p.176). Access denotes the hardware field access, followed by the LL access policy.

| Name | Offset | Bit position(s) | Access | RM0486 page |
| --- | --- | --- | --- | --- |
| RCC_CR.HSION | 0x000 | 3 | rw; set/clear by read-modify-write | RM0486 p.479 (offset), p.480 (field) |
| RCC_CR.HSEON | 0x000 | 4 | rw; set/clear by read-modify-write | RM0486 p.479 (offset), p.480 (field) |
| RCC_SR.HSIRDY | 0x004 | 3 | r; query only | RM0486 p.481 (offset), p.482 (field) |
| RCC_SR.HSERDY | 0x004 | 4 | r; query only | RM0486 p.481 (offset), p.482 (field) |
| RCC_AHB1ENR.GPDMA1EN | 0x250 | 4 | rw; set/clear by read-modify-write and query | RM0486 p.575 |
| RCC_AHB1ENR.ADC12EN | 0x250 | 5 | rw; set/clear by read-modify-write and query | RM0486 p.575 |
| RCC_AHB1RSTR.GPDMA1RST | 0x210 | 4 | rw; set/clear by read-modify-write | RM0486 p.548 |
| RCC_AHB1RSTR.ADC12RST | 0x210 | 5 | rw; set/clear by read-modify-write | RM0486 p.548 |

The documented reset fixture is RCC_CR = 0x00000008, RCC_SR = 0, RCC_AHB1ENR = 0 and RCC_AHB1RSTR = 0 (RM0486 p.479, p.481, p.575, p.548). This is a host test fixture and documented-reset comparison, never a driver initialization routine. OD-2026-10-18-01 limits HSION reset evidence to the documented reset value; the recorded Renode model resets registers to zero and physical target/HIL observation is unavailable.

## Assumptions and open points

The frozen SWE.1 baseline covers only the supplied four RM sections. Wider manifest buses await inputs and allocated requirements. Target silicon revision is unspecified. Human-approved upstream inputs are NOT_PROVIDED and software safety allocation remains pending owner review; this architecture neither derives requirements from draft placeholders nor claims ASPICE or ASIL compliance.
