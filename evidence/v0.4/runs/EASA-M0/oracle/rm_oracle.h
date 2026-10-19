/* Independent oracle constants: transcribed from RM0486 rev4 ch.14 (baselined markdown sha256 e3cf9752...),
 * NOT from the generated driver header. Word index = address offset / 4. */
#define RM_CR_W       (0x000U / 4U)  /* 14.10.1  RCC_CR  */
#define RM_SR_W       (0x004U / 4U)  /* 14.10.2  RCC_SR  */
#define RM_AHB1RSTR_W (0x210U / 4U)  /* 14.10.64 RCC_AHB1RSTR */
#define RM_AHB1ENR_W  (0x250U / 4U)  /* 14.10.79 RCC_AHB1ENR  */
#define RM_HSEON  ((uint32_t)1U << 4)  /* RCC_CR bit 4  */
#define RM_HSION  ((uint32_t)1U << 3)  /* RCC_CR bit 3, reset value 1 */
#define RM_HSERDY ((uint32_t)1U << 4)  /* RCC_SR bit 4  */
#define RM_HSIRDY ((uint32_t)1U << 3)  /* RCC_SR bit 3  */
#define RM_ADC12  ((uint32_t)1U << 5)  /* AHB1ENR.ADC12EN / AHB1RSTR.ADC12RST bit 5 */
#define RM_GPDMA1 ((uint32_t)1U << 4)  /* AHB1ENR.GPDMA1EN / AHB1RSTR.GPDMA1RST bit 4 */
#define NREG 1024U
#include <stdio.h>
#include <string.h>
#include <stdint.h>
extern unsigned long shim_accesses;
static int fails = 0;
#define EXPECT(id, cond) do { if (cond) printf("%s PASS\n", id); else { printf("%s FAIL\n", id); fails++; } } while (0)
static uint32_t snap[NREG];
static int only_changed(volatile uint32_t *r, uint32_t w, uint32_t mask)
{ /* every other word identical and only `mask` bits changed in word w */
    for (uint32_t i = 0; i < NREG; i++) {
        uint32_t d = r[i] ^ snap[i];
        if ((i == w) ? ((d & ~mask) != 0U) : (d != 0U)) return 0;
    }
    return 1;
}
