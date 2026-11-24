/* Self-test of the image layout: the stored references match the code and the configuration block. */
#include <stdint.h>
#define R(a) (*(volatile uint32_t *)(a))
#define USART 0x52001000U
extern const uint8_t __app_start[], __app_end[], __cfg_start[], __cfg_end[];
extern const uint32_t __app_crc, __cfg_crc;
__attribute__((section(".cfg"), used)) static const uint8_t cfg[5] = {1U, 2U, 3U, 4U, 5U};
static uint32_t crc(const uint8_t *p, const uint8_t *e)
{
    uint32_t c = 0xFFFFFFFFU;
    while (p < e) { c ^= (uint32_t)*p++ << 24; for (int i = 0; i < 8; i++) { c = ((c & 0x80000000U) != 0U) ? ((c << 1) ^ 0x04C11DB7U) : (c << 1); } }
    return c;
}
static void puts_(const char *s) { while (*s != '\0') { while ((R(USART + 0x1CU) & 0x80U) == 0U) { } R(USART + 0x28U) = (uint32_t)*s++; } }
static void check(const char *id, int ok) { puts_("HI-TEST "); puts_(id); puts_(ok ? " PASS\n" : " FAIL differs\n"); }
int main(void)
{
    R(USART + 0xCU) = 1736U; R(USART) = 0xDU;
    check("SIM-APP-CRC", (__app_end > __app_start) && (crc(__app_start, __app_end) == __app_crc));
    check("SIM-CFG-CRC", ((__cfg_end - __cfg_start) == 8) && (cfg[4] == 5U) && (crc(__cfg_start, __cfg_end) == __cfg_crc));
    for (;;) { __asm volatile("wfi"); }
}
