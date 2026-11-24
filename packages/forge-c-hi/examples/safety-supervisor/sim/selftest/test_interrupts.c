/* Self-test of the interrupt wiring: TIM2 compare (IRQ 116) and USART1 receive (IRQ 159, see test_interrupts.uart). */
#include <stdint.h>
#define R(a) (*(volatile uint32_t *)(a))
#define TIM 0x50000000U
#define USART 0x52001000U
static volatile uint32_t fired_at, len;
static volatile char line[16];
void TIM2_IRQHandler(void);
void USART1_IRQHandler(void);
void TIM2_IRQHandler(void) { R(TIM + 0x10U) = 0U; R(TIM + 0xCU) = 0U; fired_at = R(TIM + 0x24U); }
void USART1_IRQHandler(void)
{
    while ((R(USART + 0x1CU) & 0x20U) != 0U) { char c = (char)R(USART + 0x24U); if (len < 15U) { line[len] = c; len++; } }
}
static void puts_(const char *s) { while (*s != '\0') { while ((R(USART + 0x1CU) & 0x80U) == 0U) { } R(USART + 0x28U) = (uint32_t)*s++; } }
static void check(const char *id, int ok) { puts_("HI-TEST "); puts_(id); puts_(ok ? " PASS\n" : " FAIL not seen\n"); }
int main(void)
{
    static const char want[] = "GET STATUS\n";
    uint32_t ok = 1U;
    R(USART + 0xCU) = 1736U; R(USART) = 0x2DU;
    R(TIM + 0x34U) = 200000U;                     /* CCR1: 1 ms at 200 MHz */
    R(TIM + 0xCU) = 2U; R(TIM) = 1U;              /* CC1IE, CEN */
    R(0xE000E100U + 4U * (116U / 32U)) = 1U << (116U % 32U);
    R(0xE000E100U + 4U * (159U / 32U)) = 1U << (159U % 32U);
    while (R(TIM + 0x24U) < 10000000U) { }        /* 50 ms */
    check("SIM-TIM2-IRQ", (fired_at >= 200000U) && (fired_at < 220000U));
    for (uint32_t i = 0U; i < sizeof(want) - 1U; i++) { if (line[i] != want[i]) { ok = 0U; } }
    check("SIM-USART1-IRQ", (ok != 0U) && (len == sizeof(want) - 1U));
    for (;;) { __asm volatile("wfi"); }
}
