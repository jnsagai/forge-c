/* Independent RM-derived tests for the r101 LL header (M0 auditor). */
#include "stm32n6xx_ll_rcc.h"
#undef ll_rcc_regs
#include "rm_oracle.h"
volatile uint32_t regs[NREG];
unsigned long shim_accesses;
volatile uint32_t (*shim_regs(void))[1024] { shim_accesses++; return &regs; }
#define ll_rcc_regs (*shim_regs())
static void reset_rm(void) { memset((void *)regs, 0, sizeof regs); regs[RM_CR_W] = RM_HSION; }
static void take(void) { memcpy(snap, (const void *)regs, sizeof snap); }
#define SETCASE(id, fn, w, bit) do { reset_rm(); regs[w] &= ~(bit); take(); fn(); EXPECT(id, (regs[w] & (bit)) && only_changed(regs, w, bit)); } while (0)
#define CLRCASE(id, fn, w, bit) do { reset_rm(); regs[w] = 0xFFFFFFFFU; take(); fn(); EXPECT(id, !(regs[w] & (bit)) && only_changed(regs, w, bit)); } while (0)
#define RDCASE(id, fn, w, bit) do { reset_rm(); regs[w] = (bit); EXPECT(id "/1", fn() == 1U); regs[w] = ~(bit); EXPECT(id "/0", fn() == 0U); } while (0)
int main(void)
{
    SETCASE("IL-001 HSI_Enable CR bit3", LL_RCC_HSI_Enable, RM_CR_W, RM_HSION);
    CLRCASE("IL-002 HSI_Disable CR bit3", LL_RCC_HSI_Disable, RM_CR_W, RM_HSION);
    RDCASE("IL-003 HSI_IsReady SR bit3", LL_RCC_HSI_IsReady, RM_SR_W, RM_HSIRDY);
    SETCASE("IL-004 HSE_Enable CR bit4", LL_RCC_HSE_Enable, RM_CR_W, RM_HSEON);
    CLRCASE("IL-005 HSE_Disable CR bit4", LL_RCC_HSE_Disable, RM_CR_W, RM_HSEON);
    RDCASE("IL-006 HSE_IsReady SR bit4", LL_RCC_HSE_IsReady, RM_SR_W, RM_HSERDY);
    SETCASE("IL-007 ADC12_Enable AHB1ENR bit5", LL_RCC_ADC12_Enable, RM_AHB1ENR_W, RM_ADC12);
    CLRCASE("IL-008 ADC12_Disable AHB1ENR bit5", LL_RCC_ADC12_Disable, RM_AHB1ENR_W, RM_ADC12);
    RDCASE("IL-009 ADC12_IsEnabled AHB1ENR bit5", LL_RCC_ADC12_IsEnabled, RM_AHB1ENR_W, RM_ADC12);
    SETCASE("IL-010 ADC12_ForceReset AHB1RSTR bit5", LL_RCC_ADC12_ForceReset, RM_AHB1RSTR_W, RM_ADC12);
    CLRCASE("IL-011 ADC12_ReleaseReset AHB1RSTR bit5", LL_RCC_ADC12_ReleaseReset, RM_AHB1RSTR_W, RM_ADC12);
    SETCASE("IL-012 GPDMA1_Enable AHB1ENR bit4", LL_RCC_GPDMA1_Enable, RM_AHB1ENR_W, RM_GPDMA1);
    CLRCASE("IL-013 GPDMA1_Disable AHB1ENR bit4", LL_RCC_GPDMA1_Disable, RM_AHB1ENR_W, RM_GPDMA1);
    RDCASE("IL-014 GPDMA1_IsEnabled AHB1ENR bit4", LL_RCC_GPDMA1_IsEnabled, RM_AHB1ENR_W, RM_GPDMA1);
    SETCASE("IL-015 GPDMA1_ForceReset AHB1RSTR bit4", LL_RCC_GPDMA1_ForceReset, RM_AHB1RSTR_W, RM_GPDMA1);
    CLRCASE("IL-016 GPDMA1_ReleaseReset AHB1RSTR bit4", LL_RCC_GPDMA1_ReleaseReset, RM_AHB1RSTR_W, RM_GPDMA1);
    return fails ? 1 : 0;
}
