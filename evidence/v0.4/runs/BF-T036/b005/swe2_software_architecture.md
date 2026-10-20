# Software architecture

Work order: WO-0008C-ST-RCC-LL-b005. Frozen brownfield delivery: STMicroelectronics stm32n6xx-hal-driver v1.4.0, STM32CubeN6. Requirement baseline: BL-SWE.1-001, hash 76699a7836aeddc6c6731b71b4b57398d7252a7578995698365cfae2734b6fd8. Authority: workproducts/SWE.1/software_requirements.md and .forge-run/manifest.json.

## Components

SWC_LL is the single logical RCC LL software component. Its delivered implementation comprises two header-only modules:
- software/ll/stm32n6xx_ll_rcc.h (stm32n6xx_ll_rcc): HSI and HSE enable, disable and ready query.
- software/ll/stm32n6xx_ll_bus.h (stm32n6xx_ll_bus): AHB1 peripheral clock and reset operations, selected by peripheral masks for GPDMA1 and ADC12.

Both headers include stm32n6xx.h and use its CMSIS RCC device structure and register macros. The RCC header also includes math.h; the covered functions do not use mathematics or call library functions. Device and core headers under inputs/vendor/include are delivered dependencies, not new software components. Each covered API is __STATIC_INLINE. No source compilation unit, state machine, startup initializer, driver-owned variable, heap allocation or HAL is introduced. A later HAL work order may use these interfaces to provide polling policy and errors. Other functions present in the vendor headers are outside the manifest's delivery.scope.functions.

The manifest's actual brownfield scope takes precedence over the generic single-header/peripheral-wrapper template: peripheral operations exist in stm32n6xx_ll_bus.h with LL_AHB1_GRP1 names and a mask argument. No per-peripheral LL_RCC wrappers are delivered or allocated. Both modules belong to SWC_LL; the static view represents that single component, not a HAL.

## Register access

The secure target uses RCC base address 0x56028000 (RM0486 p.176; manifest target contract). The delivered functions access RCC->member, through the CMSIS RCC_TypeDef structure; __IO uint32_t members are volatile. The target build selects STM32N657xx and secure operation as recorded in the manifest. CMSIS defines RCC as RCC_S and RCC_S as a cast of RCC_BASE_S to RCC_TypeDef *. This is delivered dependency behavior, not an extern volatile uint32_t array positioned by a linker. The covered function bodies themselves contain no integer-to-pointer casts. No replacement array-based target interface is designed.

WRITE_REG performs a direct register assignment. HSI/HSE enable writes RCC_CSR, disable writes RCC_CCR, and ready queries read RCC_SR. AHB1 clock enable writes RCC_AHB1ENSR then reads RCC_AHB1ENR into a local volatile temporary; disable writes RCC_AHB1ENCR; is-enabled reads RCC_AHB1ENR; reset assert and release write RCC_AHB1RSTSR and RCC_AHB1RSTCR respectively. Source evidence: stm32n6xx_ll_rcc.h lines 1781-1842; stm32n6xx_ll_bus.h lines 879-942.

The supplied logical-register sections explicitly permit set/clear aliases for the named bits (RM0486 p.480, p.548, p.575). Each single-bit mask write affects only its associated logical bit. There is no read-modify-write of a shared logical RCC register in the covered functions. The logical-state effect is initial OR mask on enable/assert and initial AND complement of mask on disable/release; all other bits are preserved. RCC_SR ready flags are read independently of RCC_CR enable bits (RM0486 p.482).

Host verification supplies a register-array model indexed by byte offset / 4, including the alias effects on logical registers. This array belongs to the test harness; it is not driver state or a delivered target declaration. Host adaptation must preserve the CMSIS-facing macro/member semantics and emulate write-one set/clear aliases; a plain array that treats aliases as unrelated storage cannot verify these functions. Do not count volatile accesses as a requirement: SWE.1 explicitly verifies logical contents and return values.

## Interfaces

The following are exactly the allocated delivered functions. __STATIC_INLINE is the delivered static inline declaration macro. Types void and uint32_t come from C/CMSIS. Enable, disable, force reset and release reset return void. Queries return uint32_t normalized values 1U or 0U (vendor source spells these values 1UL and 0UL).

| Delivered declaration | Defining header | Behavior |
| --- | --- | --- |
| __STATIC_INLINE void LL_RCC_HSI_Enable(void) | stm32n6xx_ll_rcc.h | Write HSIONS to CSR |
| __STATIC_INLINE void LL_RCC_HSI_Disable(void) | stm32n6xx_ll_rcc.h | Write HSIONC to CCR |
| __STATIC_INLINE uint32_t LL_RCC_HSI_IsReady(void) | stm32n6xx_ll_rcc.h | Return SR.HSIRDY as 1U or 0U |
| __STATIC_INLINE void LL_RCC_HSE_Enable(void) | stm32n6xx_ll_rcc.h | Write HSEONS to CSR |
| __STATIC_INLINE void LL_RCC_HSE_Disable(void) | stm32n6xx_ll_rcc.h | Write HSEONC to CCR |
| __STATIC_INLINE uint32_t LL_RCC_HSE_IsReady(void) | stm32n6xx_ll_rcc.h | Return SR.HSERDY as 1U or 0U |
| __STATIC_INLINE void LL_AHB1_GRP1_EnableClock(uint32_t Periphs) | stm32n6xx_ll_bus.h | Write mask to AHB1ENSR, then read AHB1ENR |
| __STATIC_INLINE void LL_AHB1_GRP1_DisableClock(uint32_t Periphs) | stm32n6xx_ll_bus.h | Write mask to AHB1ENCR |
| __STATIC_INLINE uint32_t LL_AHB1_GRP1_IsEnabledClock(uint32_t Periphs) | stm32n6xx_ll_bus.h | Return 1U if all masked AHB1ENR bits are set, else 0U |
| __STATIC_INLINE void LL_AHB1_GRP1_ForceReset(uint32_t Periphs) | stm32n6xx_ll_bus.h | Write mask to AHB1RSTSR |
| __STATIC_INLINE void LL_AHB1_GRP1_ReleaseReset(uint32_t Periphs) | stm32n6xx_ll_bus.h | Write mask to AHB1RSTCR |

For every peripheral case, pass exactly one delivered constant:
- LL_AHB1_GRP1_PERIPH_GPDMA1 = RCC_AHB1ENR_GPDMA1EN = 0x00000010U.
- LL_AHB1_GRP1_PERIPH_ADC12 = RCC_AHB1ENR_ADC12EN = 0x00000020U.

Mask positions follow RM0486 p.575 (clock) and p.548 (reset); delivered constant definitions are stm32n6xx_ll_bus.h lines 112-113. The vendor interface also accepts combinations; this work order allocates single-peripheral calls only, so SWR-017 preservation is verified with one bit selected. No validation, function-pointer interface, per-peripheral wrapper or alternate naming convention is introduced. All six oscillator interfaces take (void); all five AHB1 interfaces take uint32_t Periphs exactly as delivered. api_calls.json records these actual argument lists.

## Timing and error handling

No covered LL function waits or polls, returns an error code, or enforces a timeout. Each oscillator API and each AHB1 disable/query/reset API performs one volatile register access. LL_AHB1_GRP1_EnableClock performs two: the set-register write followed by the delivered readback delay into local volatile uint32_t tmpreg. This exception is visible in source and must be retained; it does not violate a SWE.1 requirement. It is a readback, not a readiness wait.

The caller enables an oscillator and bounds its own repeated IsReady calls, deciding what to do when its bound expires. Oscillator stabilization time is not bounded by this architecture. Caller policy also determines when to use a peripheral after clock enable, when to assert/release reset, and whether disabling an oscillator is permitted by the clock tree. Access permissions and clock-tree policy are outside SWE.1 scope. There is no driver-owned state machine and no implicit reset on enable.

## Memory and stack budget

SWR-019 allocates flash <=4096 B for the target build exercising all covered functions. SWR-020 allocates RAM 0 B for driver state, within the manifest's static RAM budget of 64 B. SWR-021 allocates stack <=128 B for every covered path. The driver owns no static writable data, heap, register array or cached state. Hardware register mappings and host harness storage are excluded from driver RAM accounting by the requirements.

The covered functions contain no recursion or subroutine calls. EnableClock has one automatic volatile uint32_t temporary, logically 4 B; actual frame and inline expansion costs remain compiler dependent. Flash and maximum stack are target verification obligations, not measured claims here. SWE.6 shall check driver-attributed executable/read-only size, writable data/BSS and stack usage with target build evidence; include all eleven APIs and both peripheral masks. No target resource test has been run by SWE.2.

## Concurrency and reentrancy

The LL keeps no persistent state and is reentrant. The covered modifying APIs use the documented set/clear registers for atomic single-bit writes (RM0486 p.480, p.548, p.575), avoiding a shared-register read-modify-write. This preserves unrelated bits without a software critical section for that individual write. EnableClock's write/read pair and any multi-call enable/reset sequence are not a transaction.

The caller serialises conflicting operations and sequences, for example in a critical section. No LL function is called from an ISR concurrently with another operation on the same register in the supported integration model. If outside code uses a read-modify-write of a shared RCC register, that operation is not atomic and callers must serialise it with all other accesses. Polling reads are volatile observations, not synchronization or mutual exclusion. Ready flags may change under hardware control (RM0486 p.482); the caller owns its polling policy and resource ownership.

## Requirement allocation table

Every SWR is allocated to SWC_LL. Function spelling and masks below are the delivered interface; no missing function cases were found. General constraints marked all LL functions cover exactly the eleven interface entries above.

| SWR | Component | Concrete delivered function(s) / case allocation |
| --- | --- | --- |
| SWR-001 | SWC_LL | LL_RCC_HSI_Enable(void), HSI_ENABLE |
| SWR-002 | SWC_LL | LL_RCC_HSI_Disable(void), HSI_DISABLE |
| SWR-003 | SWC_LL | LL_RCC_HSI_IsReady(void), both HSIRDY values |
| SWR-004 | SWC_LL | LL_RCC_HSE_Enable(void), HSE_ENABLE |
| SWR-005 | SWC_LL | LL_RCC_HSE_Disable(void), HSE_DISABLE |
| SWR-006 | SWC_LL | LL_RCC_HSE_IsReady(void), both HSERDY values |
| SWR-007 | SWC_LL | LL_AHB1_GRP1_EnableClock(LL_AHB1_GRP1_PERIPH_GPDMA1), GPDMA1_CLOCK_ENABLE |
| SWR-008 | SWC_LL | LL_AHB1_GRP1_DisableClock(LL_AHB1_GRP1_PERIPH_GPDMA1), GPDMA1_CLOCK_DISABLE |
| SWR-009 | SWC_LL | LL_AHB1_GRP1_IsEnabledClock(LL_AHB1_GRP1_PERIPH_GPDMA1), both GPDMA1EN values |
| SWR-010 | SWC_LL | LL_AHB1_GRP1_ForceReset(LL_AHB1_GRP1_PERIPH_GPDMA1), GPDMA1_RESET_ASSERT |
| SWR-011 | SWC_LL | LL_AHB1_GRP1_ReleaseReset(LL_AHB1_GRP1_PERIPH_GPDMA1), GPDMA1_RESET_RELEASE |
| SWR-012 | SWC_LL | LL_AHB1_GRP1_EnableClock(LL_AHB1_GRP1_PERIPH_ADC12), ADC12_CLOCK_ENABLE |
| SWR-013 | SWC_LL | LL_AHB1_GRP1_DisableClock(LL_AHB1_GRP1_PERIPH_ADC12), ADC12_CLOCK_DISABLE |
| SWR-014 | SWC_LL | LL_AHB1_GRP1_IsEnabledClock(LL_AHB1_GRP1_PERIPH_ADC12), both ADC12EN values |
| SWR-015 | SWC_LL | LL_AHB1_GRP1_ForceReset(LL_AHB1_GRP1_PERIPH_ADC12), ADC12_RESET_ASSERT |
| SWR-016 | SWC_LL | LL_AHB1_GRP1_ReleaseReset(LL_AHB1_GRP1_PERIPH_ADC12), ADC12_RESET_RELEASE |
| SWR-017 | SWC_LL | all LL functions; modifying calls use only their allocated single-bit mask, queries write nothing |
| SWR-018 | SWC_LL | all LL functions; header inclusion and startup without calls produce no RCC writes |
| SWR-019 | SWC_LL | all LL functions; combined target flash <=4096 B |
| SWR-020 | SWC_LL | all LL functions; driver static RAM 0 B |
| SWR-021 | SWC_LL | all LL functions; maximum stack <=128 B |

## Register table

RCC base is 0x56028000 (RM0486 p.176). Offsets are bytes relative to that base. Each row identifies one register/bit used by these calls or their logical effects. For the host register array the index is offset / 4. The access column distinguishes logical state from write-one aliases; aliases never require reading the logical register to preserve unrelated bits.

The four supplied RM0486 sections give logical-register offsets, bit positions, access and permission to use named set/clear aliases. Alias byte offsets are verified from the delivered RCC_TypeDef members in inputs/vendor/include/stm32n657xx.h (CSR line 2168, CCR line 2240, AHB1RSTSR line 2174, AHB1RSTCR line 2246, AHB1ENSR line 2190, AHB1ENCR line 2262). The RM0486 page column for aliases cites the supplied page defining their logical effect, not a claim that their address is printed on that page.

| Name | Offset | Bit position(s) | Access | RM0486 page |
| --- | --- | --- | --- | --- |
| RCC_CR.HSION | 0x0000 | 3 | rw logical state; enabled/disabled via aliases | p.479-480 |
| RCC_CR.HSEON | 0x0000 | 4 | rw logical state; enabled/disabled via aliases | p.479-480 |
| RCC_SR.HSIRDY | 0x0004 | 3 | r, hardware ready flag | p.481-482 |
| RCC_SR.HSERDY | 0x0004 | 4 | r, hardware ready flag | p.481-482 |
| RCC_AHB1ENR.GPDMA1EN | 0x0250 | 4 | rw logical state; read by clock query/readback | p.575 |
| RCC_AHB1ENR.ADC12EN | 0x0250 | 5 | rw logical state; read by clock query/readback | p.575 |
| RCC_AHB1RSTR.GPDMA1RST | 0x0210 | 4 | rw logical state; assert/release via aliases | p.548 |
| RCC_AHB1RSTR.ADC12RST | 0x0210 | 5 | rw logical state; assert/release via aliases | p.548 |
| RCC_CSR.HSIONS | 0x0800 | 3 | write 1 sets CR.HSION | p.480 |
| RCC_CSR.HSEONS | 0x0800 | 4 | write 1 sets CR.HSEON | p.480 |
| RCC_CCR.HSIONC | 0x1000 | 3 | write 1 clears CR.HSION | p.480 |
| RCC_CCR.HSEONC | 0x1000 | 4 | write 1 clears CR.HSEON | p.480 |
| RCC_AHB1ENSR.GPDMA1ENS | 0x0A50 | 4 | write 1 sets AHB1ENR.GPDMA1EN | p.575 |
| RCC_AHB1ENSR.ADC12ENS | 0x0A50 | 5 | write 1 sets AHB1ENR.ADC12EN | p.575 |
| RCC_AHB1ENCR.GPDMA1ENC | 0x1250 | 4 | write 1 clears AHB1ENR.GPDMA1EN | p.575 |
| RCC_AHB1ENCR.ADC12ENC | 0x1250 | 5 | write 1 clears AHB1ENR.ADC12EN | p.575 |
| RCC_AHB1RSTSR.GPDMA1RSTS | 0x0A10 | 4 | write 1 sets AHB1RSTR.GPDMA1RST | p.548 |
| RCC_AHB1RSTSR.ADC12RSTS | 0x0A10 | 5 | write 1 sets AHB1RSTR.ADC12RST | p.548 |
| RCC_AHB1RSTCR.GPDMA1RSTC | 0x1210 | 4 | write 1 clears AHB1RSTR.GPDMA1RST | p.548 |
| RCC_AHB1RSTCR.ADC12RSTC | 0x1210 | 5 | write 1 clears AHB1RSTR.ADC12RST | p.548 |

RCC_CR resets to 0x00000008; RCC_SR, RCC_AHB1ENR and RCC_AHB1RSTR reset to zero (RM0486 p.479, p.481, p.575, p.548). Reserved and unrelated bits must remain at their incoming values in unit verification. No MSI, LSI, LSE, PLL or other peripheral bit is allocated. In FROZEN mode SWE.3 describes and verifies these delivered accesses using this table; it must not reimplement the driver, substitute a target array, remove the readback, or edit any delivered file. Any demonstrated requirement disagreement is a CODE defect for the delivery owner, not grounds to weaken SWE.1 or its tests.

## Delivered functions without requirement

none. Every function in delivery.scope.functions is allocated above. Additional functions elsewhere in the complete vendor headers are outside this work-order scope and are not claimed to be requirement-covered.

## Verification and traceability

architecture_static.puml assigns all SWR-001 through SWR-021 to SWC_LL and labels dependencies with unique interface IDs. architecture_dynamic.puml shows bounded caller polling, the clock-enable readback and explicit reset assert/release. api_calls.json maps every case in workproducts/SWE.1/register_effects.json to its allocated delivered call and exact mask; ready/query requirements remain allocated even though register_effects.json contains only modifying cases. The gate generates traceability/matrix_1_swr_to_architecture.csv from the static allocation note.

SWE.4 verifies initial target-bit values and unrelated-bit patterns through the alias-aware host model, independent readiness flags, and startup without calls. SWE.6 supplies target budget evidence. No source change, measured target timing, resource result, safety allocation or compliance claim is made here. The manifest records unspecified silicon revision and missing approved upstream inputs; those baseline open points remain visible in SWE.1.
