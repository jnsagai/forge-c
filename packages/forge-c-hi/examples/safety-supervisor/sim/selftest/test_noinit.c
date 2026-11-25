#include <stdint.h>
#define R(a) (*(volatile uint32_t *)(a))
#define USART 0x52001000U
extern uint32_t __noinit_start[], __noinit_end[];
static void puts_(const char *s) { while (*s != '\0') { while ((R(USART + 0x1CU) & 0x80U) == 0U) { } R(USART + 0x28U) = (uint32_t)*s++; } }
int main(void)
{
    volatile uint32_t *w = __noinit_start;
    R(USART + 0xCU) = 1736U; R(USART) = 0xDU;
    if (w[0] != 0x1234ABCDU) { w[0] = 0x1234ABCDU; w[1023] = 7U; R(0xE000ED0CU) = 0x05FA0004U; for (;;) { } }
    puts_(((w[1023] == 7U) && ((uint32_t)((uint8_t *)__noinit_end - (uint8_t *)__noinit_start) == 4096U)) ? "HI-TEST NOINIT PASS\n" : "HI-TEST NOINIT FAIL\n");
    for (;;) { }
}
