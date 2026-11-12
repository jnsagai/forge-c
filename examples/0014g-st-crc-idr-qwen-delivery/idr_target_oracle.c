/* External deterministic simulation fixture, derived from the declared IDR
 * contract. No driver implementation is supplied or rewritten.
 * Preregistered for prospective delivery-first pipeline runs.
 */
#include "forge_performance_calls.h"
#include "forge_target_test.h"
FORGE_MAILBOX_DEFINE;

static void pattern(uint32_t value)
{
    const uint32_t dr = CRC->DR;
    const uint32_t cr = CRC->CR;
    const uint32_t init = CRC->INIT;
    const uint32_t pol = CRC->POL;
    forge_measure_LL_CRC_Write_IDR(CRC, value);
    TCHECK(2, CRC->IDR == value);
    TCHECK(3, CRC->DR == dr && CRC->CR == cr && CRC->INIT == init && CRC->POL == pol);
    CRC->IDR = ~value;
    TCHECK(4, forge_measure_LL_CRC_Read_IDR(CRC) == ~value);
    TCHECK(5, CRC->IDR == ~value);
    TCHECK(6, CRC->DR == dr && CRC->CR == cr && CRC->INIT == init && CRC->POL == pol);
}

int main(void)
{
    const uint32_t values[] = {0U, 0xFFFFFFFFU, 0xAAAAAAAAU, 0x55555555U, 0x80000000U, 1U};
    FORGE_TEST_BEGIN();
    TCHECK(1, CRC->IDR == 0U); /* simulator reset state, before any explicit LL call */
    for (unsigned int i = 0U; i < 6U; i++)
    {
        pattern(values[i]);
    }
    for (unsigned int bit = 0U; bit < 32U; bit++)
    {
        pattern(1U << bit);
        pattern(~(1U << bit));
    }
    FORGE_TEST_END();
    return 0;
}

