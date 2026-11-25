/* Self-test of TIM2 (100 kHz): channel 2 re-armed every 5 counts in the handler while the program re-arms channel 1 through
 * CCR1, SR and DIER, as a driver does. A write for one channel must not lose a match of the other. */
#include <stdint.h>
#define R(a) (*(volatile uint32_t *)(a))
#define TIM 0x50000000U
#define USART 0x52001000U
static volatile uint32_t n1, n2, last, maxgap, late;
void TIM2_IRQHandler(void);
void TIM2_IRQHandler(void)
{
    const uint32_t sr = R(TIM + 0x10U), c = R(TIM + 0x24U);
    if ((sr & 4U) != 0U) {
        R(TIM + 0x10U) = 0x1E5FU & ~4U;
        if ((n2 != 0U) && ((c - last) > maxgap)) { maxgap = c - last; }
        if (c != R(TIM + 0x38U)) { late++; }
        last = c; n2++;
        R(TIM + 0x38U) += 5U;
    }
    if ((sr & 2U) != 0U) { R(TIM + 0x10U) = 0x1E5FU & ~2U; R(TIM + 0xCU) &= ~2U; n1++; }
}
static void puts_(const char *s) { while (*s != '\0') { while ((R(USART + 0x1CU) & 0x80U) == 0U) { } R(USART + 0x28U) = (uint32_t)*s++; } }
static void check(const char *id, int ok) { puts_("HI-TEST "); puts_(id); puts_(ok ? " PASS\n" : " FAIL a match was lost\n"); }
int main(void)
{
    uint32_t armed = 0U;
    R(USART + 0xCU) = 1736U; R(USART) = 0xDU;
    R(TIM + 0x2CU) = 0xFFFFFFFFU; R(TIM + 0x28U) = 1999U; R(TIM + 0x14U) = 1U; R(TIM + 0x10U) = 0U; R(TIM) = 1U;
    R(TIM + 0x38U) = R(TIM + 0x24U) + 5U; R(TIM + 0xCU) = 4U;
    R(0xE000E100U + 4U * (116U / 32U)) = 1U << (116U % 32U);
    while (R(TIM + 0x24U) < 20000U) {
        if (n1 == armed) {
            __asm volatile("cpsid i");
            R(TIM + 0xCU) &= ~2U; R(TIM + 0x34U) = R(TIM + 0x24U) + 7U; R(TIM + 0x10U) = 0x1E5FU & ~2U; R(TIM + 0xCU) |= 2U;
            __asm volatile("cpsie i");
            armed++;
        }
    }
    check("SIM-TIM2-REARM-CH2", (n2 >= 3999U) && (n2 <= 4000U) && (maxgap <= 6U));
    check("SIM-TIM2-REARM-CH1", (n1 >= 2400U) && (n1 <= 2900U));
    for (;;) { __asm volatile("wfi"); }
}
