#include "evidence/software/ll/stm32n6xx_ll_rcc.h"
volatile uint32_t ll_rcc_regs[LL_RCC_REG_COUNT];
/*@ ensures \result == 0U || \result == 1U; */
uint32_t ready_hse(void) { return LL_RCC_HSE_IsReady(); }
/*@ assigns ll_rcc_regs[LL_RCC_CR_OFFSET / 4U];
    ensures (ll_rcc_regs[LL_RCC_CR_OFFSET / 4U] & LL_RCC_CR_HSEON_MSK) != 0U; */
void enable_hse(void) { LL_RCC_HSE_Enable(); }
