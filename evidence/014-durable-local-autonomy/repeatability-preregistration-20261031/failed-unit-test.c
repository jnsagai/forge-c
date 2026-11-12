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
    LL_CRC_Write_IDR(CRC, 0x00000000U);
    CHECK("UT-001", CRC->IDR == 0x00000000U);
    LL_CRC_Write_IDR(CRC, 0xFFFFFFFFU);
    CHECK("UT-001", CRC->IDR == 0xFFFFFFFFU);
    LL_CRC_Write_IDR(CRC, 0xAAAAAAAAU);
    CHECK("UT-001", CRC->IDR == 0xAAAAAAAAU);
    LL_CRC_Write_IDR(CRC, 0x55555555U);
    CHECK("UT-001", CRC->IDR == 0x55555555U);
    LL_CRC_Write_IDR(CRC, 0x80000000U);
    CHECK("UT-001", CRC->IDR == 0x80000000U);
    LL_CRC_Write_IDR(CRC, 0x01000000U);
    CHECK("UT-001", CRC->IDR == 0x01000000U);
    LL_CRC_Write_IDR(CRC, 0x00800000U);
    CHECK("UT-001", CRC->IDR == 0x00800000U);
    LL_CRC_Write_IDR(CRC, 0x00000002U);
    CHECK("UT-001", CRC->IDR == 0x00000002U);
    LL_CRC_Write_IDR(CRC, 0x00000001U);
    CHECK("UT-001", CRC->IDR == 0x00000001U);
    LL_CRC_Write_IDR(CRC, 0x12345678U);
    CHECK("UT-001", CRC->IDR == 0x12345678U);
}

/** @test UT-002 @verifies USPEC-LL-01-02 */
static void ut_idr_read(void)
{
    CRC->IDR = 0x00000000U;
    CHECK("UT-002", LL_CRC_Read_IDR(CRC) == 0x00000000U);
    CRC->IDR = 0xFFFFFFFFU;
    CHECK("UT-002", LL_CRC_Read_IDR(CRC) == 0xFFFFFFFFU);
    CRC->IDR = 0xAAAAAAAAU;
    CHECK("UT-002", LL_CRC_Read_IDR(CRC) == 0xAAAAAAAAU);
    CRC->IDR = 0x55555555U;
    CHECK("UT-002", LL_CRC_Read_IDR(CRC) == 0x55555555U);
    CRC->IDR = 0x80000000U;
    CHECK("UT-002", LL_CRC_Read_IDR(CRC) == 0x80000000U);
    CRC->IDR = 0x01000000U;
    CHECK("UT-002", LL_CRC_Read_IDR(CRC) == 0x01000000U);
    CRC->IDR = 0x00800000U;
    CHECK("UT-002", LL_CRC_Read_IDR(CRC) == 0x00800000U);
    CRC->IDR = 0x00000002U;
    CHECK("UT-002", LL_CRC_Read_IDR(CRC) == 0x00000002U);
    CRC->IDR = 0x00000001U;
    CHECK("UT-002", LL_CRC_Read_IDR(CRC) == 0x00000001U);
    CRC->IDR = 0x87654321U;
    CHECK("UT-002", LL_CRC_Read_IDR(CRC) == 0x87654321U);
}

/** @test UT-003 @verifies USPEC-LL-01-03 */
static void ut_idr_preservation(void)
{
    CRC->DR = 0x11111111U;
    CRC->CR = 0x22222222U;
    CRC->INIT = 0x33333333U;
    CRC->POL = 0x44444444U;
    LL_CRC_Write_IDR(CRC, 0x55555555U);
    (void)LL_CRC_Read_IDR(CRC);
    CHECK("UT-003", CRC->DR == 0x11111111U);
    CHECK("UT-003", CRC->IDR == 0x55555555U);
    CHECK("UT-003", CRC->CR == 0x22222222U);
    CHECK("UT-003", CRC->INIT == 0x33333333U);
    CHECK("UT-003", CRC->POL == 0x44444444U);
    ut_reset_regs();
    LL_CRC_Read_IDR(CRC);
    CHECK("UT-003", CRC->DR == 0x00000000U);
    CHECK("UT-003", CRC->IDR == 0x00000000U);
    CHECK("UT-003", CRC->CR == 0x00000000U);
    CHECK("UT-003", CRC->INIT == 0x00000000U);
    CHECK("UT-003", CRC->POL == 0x00000000U);
}

/** @test UT-004 @verifies USPEC-LL-01-04 */
static void ut_idr_read_no_write(void)
{
    CRC->IDR = 0xDEADBEEFU;
    (void)LL_CRC_Read_IDR(CRC);
    CHECK("UT-004", CRC->IDR == 0xDEADBEEFU);
    CRC->IDR = 0x00000000U;
    (void)LL_CRC_Read_IDR(CRC);
    CHECK("UT-004", CRC->IDR == 0x00000000U);
    CRC->IDR = 0x55555555U;
    (void)LL_CRC_Read_IDR(CRC);
    CHECK("UT-004", CRC->IDR == 0x55555555U);
}

/** @test UT-005 @verifies USPEC-LL-01-05 */
static void ut_no_startup_access(void)
{
    ut_reset_regs();
    CHECK("UT-005", CRC->IDR == 0x00000000U);
    CHECK("UT-005", CRC->DR == 0x00000000U);
    CHECK("UT-005", CRC->CR == 0x00000000U);
    CHECK("UT-005", CRC->INIT == 0x00000000U);
    CHECK("UT-005", CRC->POL == 0x00000000U);
}

/** @test UT-006 @verifies USPEC-LL-01-06 */
static void ut_instance_targeting(void)
{
    CRC_TypeDef other;
    (void)memset((void *)&other, 0, sizeof(other));
    LL_CRC_Write_IDR(&other, 0x12345678U);
    CHECK("UT-006", other.IDR == 0x12345678U);
    CHECK("UT-006", other.DR == 0x00000000U);
    CHECK("UT-006", other.CR == 0x00000000U);
    CHECK("UT-006", other.INIT == 0x00000000U);
    CHECK("UT-006", other.POL == 0x00000000U);
    CHECK("UT-006", CRC->IDR == 0x55555555U);
    CHECK("UT-006", other.IDR == LL_CRC_Read_IDR(&other));
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
    // UNIT TEST CALLS (SWE.4 test author)
    return failures == 0 ? 0 : 1;
}
