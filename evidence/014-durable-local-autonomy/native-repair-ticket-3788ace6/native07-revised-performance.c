/** @file test_performance.c @verifies IF-00 IF-01 */
#include "stm32n6xx_ll_crc.h"
#include "forge_performance_calls.h"
#include "forge_target_test.h"
FORGE_MAILBOX_DEFINE;
extern volatile uint32_t ll_crc_regs[]; /* linker-placed CRC register block */
#define LL_CRC_IDR_OFFSET 4U /* DR=0, IDR=4 */

int main(void)
{
    FORGE_TEST_BEGIN();
    forge_measure_LL_CRC_Write_IDR(CRC, 0x12345678U);
    TCHECK(1, ll_crc_regs[LL_CRC_IDR_OFFSET / 4U] == 0x12345678U);
    TCHECK(2, forge_measure_LL_CRC_Read_IDR(CRC) == 0x12345678U);
    forge_measure_LL_CRC_Write_IDR(CRC, 0U);
    TCHECK(3, ll_crc_regs[LL_CRC_IDR_OFFSET / 4U] == 0U);
    forge_measure_LL_CRC_Write_IDR(CRC, 0xFFFFFFFFU);
    forge_measure_LL_CRC_Write_IDR(CRC, 0xAAAAAAAAU);
    forge_measure_LL_CRC_Write_IDR(CRC, 0x55555555U);
    TCHECK(4, forge_measure_LL_CRC_Read_IDR(CRC) == 0x55555555U);
    forge_measure_LL_CRC_Write_IDR(CRC, 0U);
    TCHECK(5, forge_measure_LL_CRC_Read_IDR(CRC) == 0U);
    FORGE_TEST_END();
    return 0;
}
