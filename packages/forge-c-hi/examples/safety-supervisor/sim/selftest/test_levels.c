/* Self-test of the software-pended exceptions and their nesting: PendSV (lowest) is preempted by interrupt 117, and
 * that by interrupt 118 (CON-SUP-188). */
#include <stdint.h>
#define R(a) (*(volatile uint32_t *)(a))
#define USART 0x52001000U
static volatile char order[8];
static volatile uint32_t n;
static void mark(char c) { if (n < 7U) { order[n] = c; n++; } }
static void pend(uint32_t irq) { R(0xE000E200U + 4U * (irq / 32U)) = 1U << (irq % 32U); __asm volatile("dsb\n\tisb" ::: "memory"); }
void PendSV_Handler(void);
void SPARE0_IRQHandler(void);
void SPARE1_IRQHandler(void);
void PendSV_Handler(void) { mark('a'); pend(117U); mark('e'); }
void SPARE0_IRQHandler(void) { mark('b'); pend(118U); mark('d'); }
void SPARE1_IRQHandler(void) { mark('c'); }
static void puts_(const char *s) { while (*s != '\0') { while ((R(USART + 0x1CU) & 0x80U) == 0U) { } R(USART + 0x28U) = (uint32_t)*s++; } }
int main(void)
{
    static const char want[] = "abcde";
    uint32_t ok = 1U;
    R(USART + 0xCU) = 1736U; R(USART) = 0x9U;
    R(0xE000ED20U) |= 0xFFU << 16;                                    /* PendSV: lowest */
    *(volatile uint8_t *)(0xE000E400U + 117U) = 0x80U;
    *(volatile uint8_t *)(0xE000E400U + 118U) = 0x40U;
    R(0xE000E100U + 4U * (117U / 32U)) = (1U << (117U % 32U)) | (1U << (118U % 32U));
    R(0xE000ED04U) = 1U << 28;                                        /* pend PendSV */
    __asm volatile("dsb\n\tisb" ::: "memory");
    for (uint32_t i = 0U; i < 5U; i++) { if (order[i] != want[i]) { ok = 0U; } }
    puts_(((ok != 0U) && (n == 5U)) ? "HI-TEST SIM-LEVELS PASS\n" : "HI-TEST SIM-LEVELS FAIL wrong order\n");
    for (;;) { __asm volatile("wfi"); }
}
