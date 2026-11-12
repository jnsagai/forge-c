/* SPDX-License-Identifier: Apache-2.0
 * Host infrastructure only. Tests and the implementation are NOT supplied.
 */
#include <stdio.h>
#include <stdint.h>
#include <string.h>
#define FORGE_HOST_DEVICE_IMPLEMENTATION
#include "forge_crc_device.h"
#include "stm32n6xx_ll_crc.h"

static int failures;
#define CHECK(id, cond) do { if (cond) { printf("%s PASS\n", (id)); } \
    else { printf("%s FAIL\n", (id)); failures++; } } while (0)

static void ut_reset_regs(void)
{
    (void)memset((void *)&forge_host_crc, 0, sizeof(forge_host_crc));
}

/** @test UT-001 @verifies USPEC-LL-01-01 */
static void ut_idr_write(void)
{
    static const uint32_t pat[6] = {0x00000000U, 0xFFFFFFFFU, 0xAAAAAAAAU,
                                    0x55555555U, 0x12345678U, 0x80000001U};
    unsigned int i;
    unsigned int bit;
    uint32_t m;
    int ok = 1;
    for (i = 0U; i < 6U; i++) {
        LL_CRC_Write_IDR(CRC, pat[i]);
        if (CRC->IDR != pat[i]) { ok = 0; }
    }
    for (bit = 0U; bit < 32U; bit++) {
        m = (uint32_t)1U << bit;
        LL_CRC_Write_IDR(CRC, m);
        if (CRC->IDR != m) { ok = 0; }
        LL_CRC_Write_IDR(CRC, ~m);
        if (CRC->IDR != (~m)) { ok = 0; }
    }
    CHECK("UT-001", ok);
}

/** @test UT-002 @verifies USPEC-LL-01-02 */
static void ut_idr_read(void)
{
    static const uint32_t pat[6] = {0x00000000U, 0xFFFFFFFFU, 0xAAAAAAAAU,
                                    0x55555555U, 0x87654321U, 0x80000001U};
    unsigned int i;
    unsigned int bit;
    uint32_t m;
    int ok = 1;
    for (i = 0U; i < 6U; i++) {
        CRC->IDR = pat[i];
        if (LL_CRC_Read_IDR(CRC) != pat[i]) { ok = 0; }
    }
    for (bit = 0U; bit < 32U; bit++) {
        m = (uint32_t)1U << bit;
        CRC->IDR = m;
        if (LL_CRC_Read_IDR(CRC) != m) { ok = 0; }
        CRC->IDR = ~m;
        if (LL_CRC_Read_IDR(CRC) != (~m)) { ok = 0; }
    }
    CHECK("UT-002", ok);
}

/** @test UT-003 @verifies USPEC-LL-01-03 */
static void ut_idr_preservation(void)
{
    int ok;
    CRC->DR = 0x11111111U;
    CRC->CR = 0x22222222U;
    CRC->INIT = 0x33333333U;
    CRC->POL = 0x44444444U;
    LL_CRC_Write_IDR(CRC, 0x55555555U);
    (void)LL_CRC_Read_IDR(CRC);
    ok = (CRC->DR == 0x11111111U) && (CRC->IDR == 0x55555555U) &&
         (CRC->CR == 0x22222222U) && (CRC->INIT == 0x33333333U) &&
         (CRC->POL == 0x44444444U);
    CHECK("UT-003", ok);
}

/** @test UT-004 @verifies USPEC-LL-01-04 */
static void ut_idr_read_no_write(void)
{
    int ok;
    CRC->IDR = 0xDEADBEEFU;
    (void)LL_CRC_Read_IDR(CRC);
    ok = (CRC->IDR == 0xDEADBEEFU);
    CRC->IDR = 0x00000000U;
    (void)LL_CRC_Read_IDR(CRC);
    ok = ok && (CRC->IDR == 0x00000000U);
    CRC->IDR = 0x55555555U;
    (void)LL_CRC_Read_IDR(CRC);
    ok = ok && (CRC->IDR == 0x55555555U);
    CHECK("UT-004", ok);
}

/** @test UT-005 @verifies USPEC-LL-01-05 */
static void ut_no_startup_access(void)
{
    int ok;
    ok = (CRC->IDR == 0x00000000U) && (CRC->DR == 0x00000000U) &&
         (CRC->CR == 0x00000000U) && (CRC->INIT == 0x00000000U) &&
         (CRC->POL == 0x00000000U);
    CHECK("UT-005", ok);
    ut_reset_regs();
}

/** @test UT-006 @verifies USPEC-LL-01-06 */
static void ut_instance_targeting(void)
{
    CRC_TypeDef other;
    int ok;
    (void)memset((void *)&other, 0, sizeof(other));
    LL_CRC_Write_IDR(&other, 0x12345678U);
    ok = (other.IDR == 0x12345678U) && (other.DR == 0x00000000U) &&
         (other.CR == 0x00000000U) && (other.INIT == 0x00000000U) &&
         (other.POL == 0x00000000U) && (other.IDR == LL_CRC_Read_IDR(&other));
    CHECK("UT-006", ok);
    ut_reset_regs();
}

/** @test UT-007 @verifies USPEC-LL-01-07 */
static void ut_no_self_setup(void)
{
    int ok;
    CRC->CR = 0xA5A5A5A5U;
    LL_CRC_Write_IDR(CRC, 0x600DF00DU);
    (void)LL_CRC_Read_IDR(CRC);
    ok = (CRC->CR == 0xA5A5A5A5U) && (CRC->IDR == 0x600DF00DU);
    CHECK("UT-007", ok);
    ut_reset_regs();
}

// UNIT TEST CASES (SWE.4 test author)

int main(void)
{
        ut_no_startup_access();
    ut_idr_write();
    ut_idr_read();
    ut_idr_preservation();
    ut_idr_read_no_write();
    ut_instance_targeting();
    ut_no_self_setup();
    // UNIT TEST CALLS (SWE.4 test author)
    return failures == 0 ? 0 : 1;
}
