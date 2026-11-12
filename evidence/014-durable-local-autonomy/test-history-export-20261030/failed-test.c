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
static void ut_write_idr(void)
{
    ut_reset_regs();
    LL_CRC_Write_IDR(CRC, 0x12345678U);
    CHECK("UT-001", CRC->IDR == 0x12345678U);
    LL_CRC_Write_IDR(CRC, 0x00000000U);
    CHECK("UT-001", CRC->IDR == 0x00000000U);
    LL_CRC_Write_IDR(CRC, 0xFFFFFFFFU);
    CHECK("UT-001", CRC->IDR == 0xFFFFFFFFU);
    LL_CRC_Write_IDR(CRC, 0x55555555U);
    CHECK("UT-001", CRC->IDR == 0x55555555U);
    LL_CRC_Write_IDR(CRC, 0xAAAAAAAAU);
    CHECK("UT-001", CRC->IDR == 0xAAAAAAAAU);
    LL_CRC_Write_IDR(CRC, 0x80000000U);
    CHECK("UT-001", CRC->IDR == 0x80000000U);
    LL_CRC_Write_IDR(CRC, 0x00000001U);
    CHECK("UT-001", CRC->IDR == 0x00000001U);
}

/** @test UT-003 @verifies USPEC-LL-01-02 */
static void ut_write_preserves(void)
{
    ut_reset_regs();
    CRC->DR = 0x11111111U;
    CRC->CR = 0x22222222U;
    CRC->INIT = 0x33333333U;
    CRC->POL = 0x44444444U;
    CRC->IDR = 0x00000000U;
    LL_CRC_Write_IDR(CRC, 0xDEADBEEFU);
    CHECK("UT-003", CRC->IDR == 0xDEADBEEFU);
    CHECK("UT-003", CRC->DR == 0x11111111U);
    CHECK("UT-003", CRC->CR == 0x22222222U);
    CHECK("UT-003", CRC->INIT == 0x33333333U);
    CHECK("UT-003", CRC->POL == 0x44444444U);
}

/** @test UT-002 @verifies USPEC-LL-02-01 */
static void ut_read_idr(void)
{
    uint32_t i;
    ut_reset_regs();
    CRC->IDR = 0x87654321U;
    CHECK("UT-002", LL_CRC_Read_IDR(CRC) == 0x87654321U);
    CRC->IDR = 0x00000000U;
    CHECK("UT-002", LL_CRC_Read_IDR(CRC) == 0x00000000U);
    CRC->IDR = 0xFFFFFFFFU;
    CHECK("UT-002", LL_CRC_Read_IDR(CRC) == 0xFFFFFFFFU);
    CRC->IDR = 0x55555555U;
    CHECK("UT-002", LL_CRC_Read_IDR(CRC) == 0x55555555U);
    CRC->IDR = 0xAAAAAAAAU;
    CHECK("UT-002", LL_CRC_Read_IDR(CRC) == 0xAAAAAAAAU);
    for (i = 0U; i < 32U; i++)
    {
        uint32_t mask = 1U << i;
        CRC->IDR = mask;
        if (LL_CRC_Read_IDR(CRC) != mask)
        {
            break;
        }
    }
    CHECK("UT-002", i == 32U);
}

/** @test UT-004 @verifies USPEC-LL-01-03,USPEC-LL-02-03 */
static void ut_no_poll(void)
{
    ut_reset_regs();
    CRC->CR = 0x00000000U;
    LL_CRC_Write_IDR(CRC, 0xCAFEBABEU);
    CHECK("UT-004", LL_CRC_Read_IDR(CRC) == 0xCAFEBABEU);
    CHECK("UT-004", CRC->CR == 0x00000000U);
}

/** @test UT-005 @verifies USPEC-LL-01-04,USPEC-LL-02-02,USPEC-LL-02-04 */
static void ut_instance_isolation(void)
{
    CRC_TypeDef other;
    ut_reset_regs();
    (void)memset((void *)&other, 0, sizeof(other));
    other.DR = 0x0A0A0A0AU;
    other.CR = 0x0B0B0B0BU;
    other.IDR = 0x11111111U;
    other.INIT = 0x0C0C0C0CU;
    other.POL = 0x0D0D0D0DU;
    LL_CRC_Write_IDR(&other, 0x22222222U);
    CHECK("UT-005", other.IDR == 0x22222222U);
    CHECK("UT-005", CRC->IDR == 0x00000000U);
    CHECK("UT-005", CRC->DR == 0x00000000U);
    CHECK("UT-005", other.DR == 0x0A0A0A0AU);
    CHECK("UT-005", other.CR == 0x0B0B0B0BU);
    CHECK("UT-005", other.INIT == 0x0C0C0C0CU);
    CHECK("UT-005", other.POL == 0x0D0D0D0DU);
    CHECK("UT-005", LL_CRC_Read_IDR(&other) == 0x22222222U);
    CHECK("UT-005", other.IDR == 0x22222222U);
    CHECK("UT-005", other.DR == 0x0A0A0A0AU);
}

// UNIT TEST CASES (SWE.4 test author)

int main(void)
{
    ut_write_idr();
    ut_read_idr();
    ut_write_preserves();
    ut_no_poll();
    ut_instance_isolation();
    // UNIT TEST CALLS (SWE.4 test author)
    return failures == 0 ? 0 : 1;
}
