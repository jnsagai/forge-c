/* Independent SWR/RM-derived tests for the r102 HAL (written by the M0 auditor, not the factory). */
#include "stm32n6xx_hal_rcc.h"   /* prototypes and hal_status_t only; expectations come from rm_oracle.h */
#undef ll_rcc_regs
#include "rm_oracle.h"
volatile uint32_t regs[NREG];
unsigned long shim_accesses;
volatile uint32_t (*shim_regs(void))[1024] { shim_accesses++; return &regs; }
static void reset_rm(void) { memset((void *)regs, 0, sizeof regs); regs[RM_CR_W] = RM_HSION; shim_accesses = 0; }
static void take(void) { memcpy(snap, (const void *)regs, sizeof snap); }
int main(void)
{
    hal_status_t s;
    reset_rm(); regs[RM_SR_W] = RM_HSERDY; take(); s = HAL_RCC_HSE_Enable(10U);
    EXPECT("IT-001 SWR-002 HSE enable sets CR bit4 only", s == HAL_OK && (regs[RM_CR_W] & RM_HSEON) && only_changed(regs, RM_CR_W, RM_HSEON));
    reset_rm(); regs[RM_CR_W] = 0; regs[RM_SR_W] = RM_HSIRDY; take(); s = HAL_RCC_HSI_Enable(10U);
    EXPECT("IT-002 SWR-001 HSI enable sets CR bit3 only", s == HAL_OK && (regs[RM_CR_W] & RM_HSION) && only_changed(regs, RM_CR_W, RM_HSION));
    reset_rm(); regs[RM_CR_W] |= RM_HSEON; take(); s = HAL_RCC_HSE_Disable();
    EXPECT("IT-003 SWR-006 HSE disable clears CR bit4 only", s == HAL_OK && !(regs[RM_CR_W] & RM_HSEON) && only_changed(regs, RM_CR_W, RM_HSEON));
    reset_rm(); take(); s = HAL_RCC_HSI_Disable();
    EXPECT("IT-004 SWR-005 HSI disable clears CR bit3 only", s == HAL_OK && !(regs[RM_CR_W] & RM_HSION) && only_changed(regs, RM_CR_W, RM_HSION));
    reset_rm(); take(); s = HAL_RCC_ADC12_Enable();
    EXPECT("IT-005 SWR-007 ADC12 enable -> AHB1ENR(0x250) bit5 only", s == HAL_OK && (regs[RM_AHB1ENR_W] & RM_ADC12) && only_changed(regs, RM_AHB1ENR_W, RM_ADC12));
    reset_rm(); take(); s = HAL_RCC_GPDMA1_Enable();
    EXPECT("IT-006 SWR-007 GPDMA1 enable -> AHB1ENR bit4 only", s == HAL_OK && (regs[RM_AHB1ENR_W] & RM_GPDMA1) && only_changed(regs, RM_AHB1ENR_W, RM_GPDMA1));
    reset_rm(); regs[RM_AHB1ENR_W] = RM_ADC12 | RM_GPDMA1; take(); s = HAL_RCC_ADC12_Disable();
    EXPECT("IT-007 SWR-008 ADC12 disable clears bit5 only", s == HAL_OK && regs[RM_AHB1ENR_W] == RM_GPDMA1 && only_changed(regs, RM_AHB1ENR_W, RM_ADC12));
    reset_rm(); regs[RM_AHB1ENR_W] = RM_ADC12 | RM_GPDMA1; take(); s = HAL_RCC_GPDMA1_Disable();
    EXPECT("IT-008 SWR-008 GPDMA1 disable clears bit4 only", s == HAL_OK && regs[RM_AHB1ENR_W] == RM_ADC12 && only_changed(regs, RM_AHB1ENR_W, RM_GPDMA1));
    reset_rm(); take(); s = HAL_RCC_ADC12_Reset();
    EXPECT("IT-009 SWR-009 ADC12 reset -> AHB1RSTR(0x210) bit5 only", s == HAL_OK && (regs[RM_AHB1RSTR_W] & RM_ADC12) && only_changed(regs, RM_AHB1RSTR_W, RM_ADC12));
    reset_rm(); take(); s = HAL_RCC_GPDMA1_Reset();
    EXPECT("IT-010 SWR-009 GPDMA1 reset -> AHB1RSTR bit4 only", s == HAL_OK && (regs[RM_AHB1RSTR_W] & RM_GPDMA1) && only_changed(regs, RM_AHB1RSTR_W, RM_GPDMA1));
    reset_rm(); regs[RM_AHB1RSTR_W] = RM_ADC12 | RM_GPDMA1; take(); s = HAL_RCC_ADC12_ReleaseReset();
    EXPECT("IT-011 SWR-010 ADC12 release clears bit5 only", s == HAL_OK && regs[RM_AHB1RSTR_W] == RM_GPDMA1);
    reset_rm(); regs[RM_AHB1RSTR_W] = RM_ADC12 | RM_GPDMA1; take(); s = HAL_RCC_GPDMA1_ReleaseReset();
    EXPECT("IT-012 SWR-010 GPDMA1 release clears bit4 only", s == HAL_OK && regs[RM_AHB1RSTR_W] == RM_ADC12);
    for (uint32_t t = 1U; t <= 1000U; t = (t < 3U) ? t + 1U : t * 10U) { /* 1,2,3,30,300 and 1000 below */
        reset_rm(); s = HAL_RCC_HSE_Enable(t);
        unsigned long polls = shim_accesses - 2UL; /* 1 RMW for enable + 1 RMW for the timeout disable */
        char id[96]; snprintf(id, sizeof id, "IT-013 SWR-015/013 HSE never ready t=%u: <=t polls (%lu), TIMEOUT, HSEON cleared", t, polls);
        EXPECT(id, s == HAL_TIMEOUT && polls <= t && polls >= 1UL && !(regs[RM_CR_W] & RM_HSEON));
    }
    reset_rm(); s = HAL_RCC_HSE_Enable(1000U);
    EXPECT("IT-014 SWR-015 bound at HAL_RCC_TIMEOUT_VALUE: <=1000 polls", s == HAL_TIMEOUT && (shim_accesses - 2UL) <= 1000UL);
    reset_rm(); take(); s = HAL_RCC_HSE_Enable(0U);
    EXPECT("IT-015 SWR-014 timeout 0 -> HAL_ERROR, no register access", s == HAL_ERROR && shim_accesses == 0UL && only_changed(regs, 0, 0));
    reset_rm(); take(); s = HAL_RCC_HSI_Enable(1001U);
    EXPECT("IT-016 SWR-014 timeout 1001 -> HAL_ERROR, no register access", s == HAL_ERROR && shim_accesses == 0UL);
    reset_rm(); regs[RM_CR_W] = 0U; s = HAL_RCC_HSI_Enable(7U);
    EXPECT("IT-017 SWR-003/013/015 HSI never ready from OFF: TIMEOUT, <=7 polls, HSION cleared", s == HAL_TIMEOUT && (shim_accesses - 2UL) <= 7UL && !(regs[RM_CR_W] & RM_HSION));
    /* SWR-013 'clear the enable bit it set': HSION is 1 from reset (RM p.480). Observation, reviewer to disposition. */
    reset_rm(); s = HAL_RCC_HSI_Enable(5U);
    printf("OBS-001 SWR-013 HSI already ON at reset, never ready: status=%d HSION_after=%u\n", (int)s, (unsigned)((regs[RM_CR_W] & RM_HSION) != 0U));
    return fails ? 1 : 0;
}
