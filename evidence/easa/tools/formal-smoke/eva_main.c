#include "__fc_builtin.h"
#include "evidence/software/hal/stm32n6xx_hal_rcc.c"
volatile uint32_t ll_rcc_regs[LL_RCC_REG_COUNT];
int main(void)
{
    for (unsigned i = 0; i < LL_RCC_REG_COUNT; i++) ll_rcc_regs[i] = Frama_C_unsigned_int_interval(0U, 0xFFFFFFFFU);
    uint32_t t = Frama_C_unsigned_int_interval(0U, 0xFFFFFFFFU);
    (void)HAL_RCC_HSI_Enable(t); (void)HAL_RCC_HSE_Enable(t);
    (void)HAL_RCC_HSI_Disable(); (void)HAL_RCC_HSE_Disable();
    (void)HAL_RCC_ADC12_Enable(); (void)HAL_RCC_ADC12_Disable(); (void)HAL_RCC_ADC12_Reset(); (void)HAL_RCC_ADC12_ReleaseReset();
    (void)HAL_RCC_GPDMA1_Enable(); (void)HAL_RCC_GPDMA1_Disable(); (void)HAL_RCC_GPDMA1_Reset(); (void)HAL_RCC_GPDMA1_ReleaseReset();
    return 0;
}
