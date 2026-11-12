/* SPDX-License-Identifier: Apache-2.0
 * Independent predeclared oracle; no driver implementation is supplied.
 * Source: RM0486 Rev4 section26.4.2, p.1172; host memory semantics only.
 */
#include <stdint.h>
#include <stdio.h>
#include "forge_crc_device.h"
#include "stm32n6xx_ll_crc.h"

static int failures;
static unsigned int checks;

#define EXPECT(c) do { checks++; if (!(c)) { \
    (void)printf("FAIL line %u\n", (unsigned int)__LINE__); failures++; } } while (0)

static void verify_pattern(uint32_t value)
{
    CRC_TypeDef a = {0xDEADBEEFU, 0U, 0x13579BDFU, 0x2468ACE0U, 0x01234567U, 0x89ABCDEFU};
    CRC_TypeDef b = {0x5A5A5A5AU, 0xA5A5A5A5U, 3U, 4U, 5U, 6U};
    LL_CRC_Write_IDR(&a, value);
    EXPECT(a.IDR == value);
    EXPECT(a.DR == 0xDEADBEEFU && a.CR == 0x13579BDFU && a.RESERVED1 == 0x2468ACE0U);
    EXPECT(a.INIT == 0x01234567U && a.POL == 0x89ABCDEFU);
    EXPECT(b.IDR == 0xA5A5A5A5U); /* instance isolation */
    a.IDR = ~value; /* independent read oracle, not a writer/readback tautology */
    EXPECT(LL_CRC_Read_IDR(&a) == ~value);
    EXPECT(a.IDR == ~value);
    EXPECT(a.DR == 0xDEADBEEFU && a.CR == 0x13579BDFU && a.RESERVED1 == 0x2468ACE0U);
    EXPECT(a.INIT == 0x01234567U && a.POL == 0x89ABCDEFU);
    EXPECT(LL_CRC_Read_IDR(&b) == 0xA5A5A5A5U);
}

int main(void)
{
    const uint32_t values[] = {0U, UINT32_MAX, 0xAAAAAAAAU, 0x55555555U, 0x80000000U, 1U};
    for (unsigned int i = 0U; i < sizeof(values) / sizeof(values[0]); i++)
    {
        verify_pattern(values[i]);
    }
    for (unsigned int bit = 0U; bit < 32U; bit++)
    {
        verify_pattern(UINT32_C(1) << bit);
        verify_pattern(~(UINT32_C(1) << bit));
    }
    (void)printf("independent IDR host oracle: %u checks, %d failures\n", checks, failures);
    return failures == 0 ? 0 : 1;
}

