/** @file test_crc_target.c @verifies IF-00 IF-01 */
#include "stm32n6xx_ll_crc.h"
#include "forge_target_test.h"
FORGE_MAILBOX_DEFINE;
extern uint32_t ll_crc_regs[]; /* linker-placed CRC register block base */
#define LL_CRC_IDR_OFFSET 4U /* DR=0, IDR=4 */

static void it_roundtrip(void)
{
    static const uint32_t values[4] = {0U, 0xFFFFFFFFU, 0xAAAAAAAAU, 0x55555555U};
    for (unsigned int i = 0U; i < 4U; i++)
    {
        LL_CRC_Write_IDR(CRC, values[i]);
        TCHECK(1, ll_crc_regs[LL_CRC_IDR_OFFSET / 4U] == values[i]);
        TCHECK(2, LL_CRC_Read_IDR(CRC) == values[i]);
    }
}

static void it_read_preset(void)
{
    ll_crc_regs[LL_CRC_IDR_OFFSET / 4U] = 0x87654321U;
    TCHECK(3, LL_CRC_Read_IDR(CRC) == 0x87654321U);
    TCHECK(4, ll_crc_regs[LL_CRC_IDR_OFFSET / 4U] == 0x87654321U);
}

int main(void)
{
    FORGE_TEST_BEGIN();
    TCHECK(0, ll_crc_regs[LL_CRC_IDR_OFFSET / 4U] == 0U);
    it_roundtrip();
    it_read_preset();
    FORGE_TEST_END();
    return 0;
}
