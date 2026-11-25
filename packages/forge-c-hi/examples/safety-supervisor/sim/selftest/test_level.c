/* Self-test: an enabled TIM2 flag that is still set, or becomes set, while its handler runs enters the handler again. */
#include <stdint.h>
#define R(a) (*(volatile uint32_t *)(a))
#define TIM 0x50000000U
#define USART 0x52001000U
static volatile uint32_t n, seen[4];
void TIM2_IRQHandler(void);
void TIM2_IRQHandler(void)
{
    const uint32_t sr = R(TIM + 0x10U);
    if (n < 4U) { seen[n] = sr & 6U; }
    n++;
    if (n == 1U) { R(TIM + 0x10U) = ~2U; while ((R(TIM + 0x10U) & 4U) == 0U) { } return; }   /* CC2IF set during the run, not cleared */
    if (n == 2U) { return; }                                                                   /* left set */
    R(TIM + 0x10U) = ~6U;
}
static void puts_(const char *s) { while (*s != '\0') { while ((R(USART + 0x1CU) & 0x80U) == 0U) { } R(USART + 0x28U) = (uint32_t)*s++; } }
static void check(const char *id, int ok) { puts_("HI-TEST "); puts_(id); puts_(ok ? " PASS\n" : " FAIL handler entries\n"); }
int main(void)
{
    R(USART + 0xCU) = 1736U; R(USART) = 0xDU;
    R(TIM + 0x2CU) = 0xFFFFFFFFU; R(TIM + 0x28U) = 1999U; R(TIM + 0x14U) = 1U; R(TIM + 0x10U) = 0U; R(TIM) = 1U;
    R(TIM + 0x34U) = 10U; R(TIM + 0x38U) = 14U; R(TIM + 0xCU) = 6U;
    R(0xE000E100U + 4U * (116U / 32U)) = 1U << (116U % 32U);
    while (R(TIM + 0x24U) < 200U) { }
    check("SIM-TIM2-LEVEL-DURING", (n >= 2U) && (seen[0] == 2U) && (seen[1] == 4U));
    check("SIM-TIM2-LEVEL-LEFT", (n == 3U) && (seen[2] == 4U));
    for (;;) { __asm volatile("wfi"); }
}
