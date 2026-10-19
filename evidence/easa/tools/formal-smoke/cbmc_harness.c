/* CBMC harness for the sealed r102 HAL, run on an extracted copy. Properties from the SWRs, not the code. */
#include <stdint.h>
#include "evidence/software/hal/stm32n6xx_hal_rcc.c"
volatile uint32_t ll_rcc_regs[LL_RCC_REG_COUNT];
uint32_t nondet_u32(void);
void harness(void)
{
    uint32_t timeout = nondet_u32();
    uint32_t cr0 = nondet_u32(), sr0 = nondet_u32();
    ll_rcc_regs[LL_RCC_CR_OFFSET / 4U] = cr0;
    ll_rcc_regs[LL_RCC_SR_OFFSET / 4U] = sr0;     /* status held constant during the call */
    hal_status_t st = HAL_RCC_HSE_Enable(timeout);
    uint32_t cr1 = ll_rcc_regs[LL_RCC_CR_OFFSET / 4U];
    if ((timeout == 0U) || (timeout > HAL_RCC_TIMEOUT_VALUE)) {
        __CPROVER_assert(st == HAL_ERROR && cr1 == cr0, "SWR-014: invalid timeout -> HAL_ERROR, no register write");
    } else if ((sr0 & LL_RCC_SR_HSERDY_MSK) != 0U) {
        __CPROVER_assert(st == HAL_OK && (cr1 & LL_RCC_CR_HSEON_MSK) != 0U, "ready -> HAL_OK, HSEON set");
    } else {
        __CPROVER_assert(st == HAL_TIMEOUT, "never ready -> HAL_TIMEOUT");
        __CPROVER_assert((cr1 & LL_RCC_CR_HSEON_MSK) == 0U, "SWR-013: HSEON rolled back on timeout");
    }
    __CPROVER_assert((cr1 & ~LL_RCC_CR_HSEON_MSK) == (cr0 & ~LL_RCC_CR_HSEON_MSK), "no other RCC_CR bit changed");
}
void harness_hsi_on_at_reset(void)
{   /* F-04: HSI is on at reset (RM reset value 0x8); a timed-out HSI enable must not switch it off */
    uint32_t timeout = nondet_u32();
    __CPROVER_assume(timeout >= 1U && timeout <= HAL_RCC_TIMEOUT_VALUE);
    ll_rcc_regs[LL_RCC_CR_OFFSET / 4U] = LL_RCC_CR_HSION_MSK;
    ll_rcc_regs[LL_RCC_SR_OFFSET / 4U] = 0U;
    (void)HAL_RCC_HSI_Enable(timeout);
    __CPROVER_assert((ll_rcc_regs[LL_RCC_CR_OFFSET / 4U] & LL_RCC_CR_HSION_MSK) != 0U, "F-04: HSI on before the call stays on");
}
