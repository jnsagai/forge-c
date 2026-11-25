/* Self-test of the monitor (verification equipment): sent characters, output level changes, resets with cause and time,
 * injected received characters, all kept over a reset. */
#include <stdint.h>
#define R(a) (*(volatile uint32_t *)(a))
#define USART 0x52001000U
#define GPIOA 0x56020000U
#define MON 0x5FFF0000U
#define TX(n, r) (R(MON + 0x0CU) = (n), R(MON + (r)))
#define PIN(n, r) (R(MON + 0x24U) = (n), R(MON + (r)))
#define RST(n, r) (R(MON + 0x34U) = (n), R(MON + (r)))
__attribute__((section(".noinit"))) static uint32_t boot, magic, got, pin_at;
static void puts_(const char *s) { while (*s != '\0') { while ((R(USART + 0x1CU) & 0x80U) == 0U) { } R(USART + 0x28U) = (uint32_t)*s++; } }
static void check(const char *id, int ok) { puts_("HI-TEST "); puts_(id); puts_(ok ? " PASS\n" : " FAIL not as sent, set or reset\n"); }
int main(void)
{
    if (magic != 0x4D4F4E31U) { magic = 0x4D4F4E31U; boot = 0U; }
    boot++;
    R(USART + 0xCU) = 1736U; R(USART) = 0xDU;
    if (boot == 1U) {
        uint32_t t;
        puts_("ab\n");
        R(GPIOA) = (R(GPIOA) & ~(3U << 6)) | (1U << 6);            /* PA3 output */
        t = R(MON); while ((R(MON) - t) < 300U) { }
        pin_at = R(MON);
        R(GPIOA + 0x18U) = 1U << 3;
        t = R(MON); while ((R(MON) - t) < 200U) { }
        R(GPIOA + 0x18U) = 1U << (3 + 16);
        R(MON + 0x40U) = (uint32_t)'Z';
        t = R(MON); while ((R(MON) - t) < 200U) { }
        got = R(USART + 0x24U);
        R(0xE000ED0CU) = 0x05FA0004U;                              /* software reset */
        for (;;) { }
    }
    check("SIM-MON-TX", (TX(0U, 0x10U) == 'a') && (TX(1U, 0x10U) == 'b') && (TX(2U, 0x10U) == '\n') &&
                        (TX(0U, 0x14U) <= TX(1U, 0x14U)) && (TX(100000U, 0x10U) == 0xFFFFFFFFU));
    {
        uint32_t high = 0xFFFFFFFFU, low = 0xFFFFFFFFU;
        for (uint32_t i = 0U; i < R(MON + 0x20U); i++) {
            if ((PIN(i, 0x28U) == 0x103U) && (high == 0xFFFFFFFFU)) { high = PIN(i, 0x2CU); }
            if ((PIN(i, 0x28U) == 0x003U) && (high != 0xFFFFFFFFU) && (low == 0xFFFFFFFFU)) { low = PIN(i, 0x2CU); }
        }
        check("SIM-MON-PIN", (high - pin_at <= 10U) && (low - high >= 200U) && (low - high <= 215U));
    }
    check("SIM-MON-RX", got == 'Z');
    check("SIM-MON-RESET", (boot == 2U) && (R(MON + 0x30U) == 1U) && (RST(0U, 0x38U) == (1U << 24)) &&
                           (RST(0U, 0x3CU) > pin_at) && (RST(0U, 0x3CU) <= R(MON)));
    for (;;) { __asm volatile("wfi"); }
}
