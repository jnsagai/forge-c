/* Self-test of the simulator platform: each boot runs one step and is judged by the reset flags of the next boot. */
#include <stdint.h>
#define R(a) (*(volatile uint32_t *)(a))
#define RSR R(0x56028034U)
#define IWDG 0x56004800U
#define WWDG 0x50002C00U
#define TIM 0x50000000U
#define USART 0x52001000U
__attribute__((section(".noinit"))) static uint32_t step, magic, t_us[8];
static void putc_(char c) { while ((R(USART + 0x1CU) & 0x80U) == 0U) { } R(USART + 0x28U) = (uint32_t)c; }
static void puts_(const char *s) { while (*s != '\0') { putc_(*s++); } }
static void num(uint32_t v) { char b[11]; int i = 10; b[10] = '\0'; do { b[--i] = (char)('0' + (v % 10U)); v /= 10U; } while (v != 0U); puts_(&b[i]); }
static void check(const char *id, int ok) { puts_("HI-TEST "); puts_(id); puts_(ok ? " PASS\n" : " FAIL flags\n"); }
static uint32_t now(void) { return R(TIM + 0x24U) / 200U; }   /* microseconds at 200 MHz */
static void wait_us(uint32_t us) { uint32_t s = now(); while ((now() - s) < us) { } }
static void store(void) { t_us[0] = now(); }
int main(void)
{
    uint32_t f = RSR;
    R(USART + 0xCU) = 1736U; R(USART) = 0xDU;                  /* 115200 baud at 200 MHz, TE RE UE */
    R(TIM) = 1U;
    RSR = 1U << 16;
    if (magic != 0x5AFE5AFEU) { magic = 0x5AFE5AFEU; step = 0U; check("SIM-POR-001", f == 0x00A00000U); }
    else if (step == 1U) { check("SIM-IWDG-001", f == (1U << 26)); puts_("iwdg_us "); num(t_us[0]); putc_('\n'); }
    else if (step == 2U) { check("SIM-WWDG-001", f == (1U << 28)); }
    else if (step == 3U) { check("SIM-WWDG-002", f == (1U << 28)); puts_("wwdg_us "); num(t_us[0]); putc_('\n'); }
    else if (step == 4U) { check("SIM-WWDG-003", f == (1U << 24)); }
    else { check("SIM-UNEXPECTED", 0); }
    step++;
    wait_us(1000U);
    if (step == 1U) {                    /* independent watchdog, 100 ms: /32 -> 1 ms per tick, 100 ticks; never refreshed */
        uint32_t s; R(IWDG) = 0xCCCCU; R(IWDG) = 0x5555U; R(IWDG + 4U) = 3U; R(IWDG + 8U) = 99U; R(IWDG) = 0xAAAAU;
        s = now(); for (;;) { t_us[0] = now() - s; }
    } else if (step == 2U) {             /* window watchdog refreshed too early */
        R(WWDG + 4U) = (1U << 11) | 0x50U; R(WWDG) = 0xFFU; wait_us(500U); R(WWDG) = 0xFFU; for (;;) { }
    } else if (step == 3U) {             /* window watchdog never refreshed: (0x7F-0x3F) * 4096 * 2 / 50 MHz = 10.5 ms */
        uint32_t s; R(WWDG + 4U) = (1U << 11) | 0x7FU; R(WWDG) = 0xFFU; s = now(); for (;;) { t_us[0] = now() - s; }
    } else if (step == 4U) {             /* window watchdog refreshed inside its window survives; then a software reset */
        R(WWDG + 4U) = (1U << 11) | 0x60U;
        R(WWDG) = 0xFFU;
        for (uint32_t i = 0U; i < 5U; i++) { wait_us(7000U); R(WWDG) = 0xFFU; }
        R(0xE000ED0CU) = 0x05FA0004U; for (;;) { }
    } else { (void)store; puts_("DONE\n"); for (;;) { __asm volatile("wfi"); } }
}
