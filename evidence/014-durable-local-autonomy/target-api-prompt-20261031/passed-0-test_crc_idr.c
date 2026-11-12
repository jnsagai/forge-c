/** @file test_crc_idr.c @verifies IF-01 IF-02 */
/*
 * SWE.5 component/target integration test, STM32N6 CRC IDR (QM demo).
 * Exercises IF-01 (LL_CRC_Write_IDR) and IF-02 (LL_CRC_Read_IDR) through
 * IF-03 (CRC_IDR.IDR, offset 0x04) on the Renode STM32N6 Cortex-M55
 * behavioural CRC model. Simulation-only evidence; no physical board
 * verification. Expected values follow the pinned behavioural model
 * (factory/sim/stm32n6/crc_model.py; RM0486 26.3.3/26.4.2).
 */
#include "stm32n6xx_ll_crc.h"
#include "forge_target_test.h"

FORGE_MAILBOX_DEFINE;

/* Linker-placed CRC register block (RM0486 p.176, 0x56024C00), words: */
#define LL_CRC_DR_OFFSET   0U
#define LL_CRC_IDR_OFFSET  4U
#define LL_CRC_CR_OFFSET   8U
#define LL_CRC_INIT_OFFSET 16U
#define LL_CRC_POL_OFFSET  20U
extern char ll_crc_regs[];
#define ll_crc_word(n) (((volatile uint32_t *)(void *)ll_crc_regs)[(n)])

static void tt_startup_reset_state(void)
{
    /* SWR-005: no LL call has occurred yet; IDR keeps reset value 0. */
    TCHECK(1, CRC->IDR == 0x00000000U);
    /* Behavioural model reset: DR/INIT 0xFFFFFFFF, POL 0x04C11DB7, CR 0. */
    TCHECK(2, ll_crc_word(LL_CRC_IDR_OFFSET / 4U) == 0x00000000U);
    TCHECK(3, ll_crc_word(LL_CRC_DR_OFFSET / 4U) == 0xFFFFFFFFU);
    TCHECK(4, ll_crc_word(LL_CRC_INIT_OFFSET / 4U) == 0xFFFFFFFFU);
    TCHECK(5, ll_crc_word(LL_CRC_POL_OFFSET / 4U) == 0x04C11DB7U);
    TCHECK(6, ll_crc_word(LL_CRC_CR_OFFSET / 4U) == 0x00000000U);
}

static void tt_write_roundtrip(void)
{
    static const uint32_t pat[3] = {0x00000000U, 0xFFFFFFFFU, 0xAAAAAAAAU};
    unsigned int i;
    uint32_t r;
    for (i = 0U; i < 3U; i++) {
        LL_CRC_Write_IDR(CRC, pat[i]); /* IF-01 -> IF-03 */
        TCHECK(7 + i, ll_crc_word(LL_CRC_IDR_OFFSET / 4U) == pat[i]);
        r = LL_CRC_Read_IDR(CRC); /* IF-02 -> IF-03 */
        TCHECK(10 + i, r == pat[i]);
    }
    /* CRC_DR is untouched by an IDR write (RM0486 26.3.3 model). */
    TCHECK(13, ll_crc_word(LL_CRC_DR_OFFSET / 4U) == 0xFFFFFFFFU);
    TCHECK(14, ll_crc_word(LL_CRC_INIT_OFFSET / 4U) == 0xFFFFFFFFU);
    TCHECK(15, ll_crc_word(LL_CRC_CR_OFFSET / 4U) == 0x00000000U);
    /* Model example: DR write 0x12345678 in reset config reads 0xDF8A8A2B. */
    CRC->DR = 0x12345678U;
    TCHECK(16, CRC->DR == 0xDF8A8A2BU);
}

static void tt_read_independent_presets(void)
{
    /* SWR-002/SWR-004: IDR preset without the write API, read returns it. */
    CRC->IDR = 0x00000000U;
    TCHECK(17, LL_CRC_Read_IDR(CRC) == 0x00000000U);
    CRC->IDR = 0xFFFFFFFFU;
    TCHECK(18, LL_CRC_Read_IDR(CRC) == 0xFFFFFFFFU);
    CRC->IDR = 0x55555555U;
    TCHECK(19, LL_CRC_Read_IDR(CRC) == 0x55555555U);
    TCHECK(20, LL_CRC_Read_IDR(CRC) == 0x55555555U); /* read must not write */
}

static void tt_preservation(void)
{
    /* SWR-003: IDR write/read leaves the other registers unchanged. */
    CRC->IDR = 0x80000001U;
    TCHECK(21, LL_CRC_Read_IDR(CRC) == 0x80000001U);
    LL_CRC_Write_IDR(CRC, 0xAAAAAAAAU);
    TCHECK(22, ll_crc_word(LL_CRC_IDR_OFFSET / 4U) == 0xAAAAAAAAU);
    TCHECK(23, ll_crc_word(LL_CRC_CR_OFFSET / 4U) == 0x00000000U);
    TCHECK(24, ll_crc_word(LL_CRC_INIT_OFFSET / 4U) == 0xFFFFFFFFU);
    TCHECK(25, ll_crc_word(LL_CRC_POL_OFFSET / 4U) == 0x04C11DB7U);
    /* IDR stays the plain storage value written; no CRC computation. */
    TCHECK(26, LL_CRC_Read_IDR(CRC) == 0xAAAAAAAAU);
}

int main(void)
{
    FORGE_TEST_BEGIN();
    tt_startup_reset_state();
    tt_write_roundtrip();
    tt_read_independent_presets();
    tt_preservation();
    FORGE_TEST_END();
    return 0;
}
