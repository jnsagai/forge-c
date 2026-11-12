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

/** @test UT-001 UT-003 UT-004 UT-006 @verifies USPEC-LL-01-01 USPEC-LL-01-02 USPEC-LL-01-03 USPEC-LL-01-04 */
static void ut_write_idr(void)
{
    uint32_t snap;
    CRC_TypeDef other;
    ut_reset_regs();
    LL_CRC_Write_IDR(CRC, 0x12345678U);
    CHECK("UT-001", CRC->IDR == 0x12345678U);
    LL_CRC_Write_IDR(CRC, 0x00000000U);
    CHECK("UT-003", CRC->IDR == 0x00000000U);
    LL_CRC_Write_IDR(CRC, 0xFFFFFFFFU);
    CHECK("UT-003", CRC->IDR == 0xFFFFFFFFU);
    LL_CRC_Write_IDR(CRC, 0xAAAAAAAAU);
    CHECK("UT-003", CRC->IDR == 0xAAAAAAAAU);
    LL_CRC_Write_IDR(CRC, 0x55555555U);
    CHECK("UT-003", CRC->IDR == 0x55555555U);
    CRC->IDR = 0x00000009U;
    CRC->DR = 0x00000001U;
    CRC->CR = 0x00000002U;
    CRC->RESERVED1 = 0x00000003U;
    CRC->INIT = 0x00000004U;
    CRC->POL = 0x00000005U;
    snap = CRC->IDR;
    LL_CRC_Write_IDR(CRC, 0x76543210U);
    CHECK("UT-004", snap == 0x00000009U && CRC->IDR == 0x76543210U);
    CHECK("UT-004", CRC->DR == 0x00000001U && CRC->CR == 0x00000002U);
    CHECK("UT-004", CRC->RESERVED1 == 0x00000003U);
    CHECK("UT-004", CRC->INIT == 0x00000004U && CRC->POL == 0x00000005U);
    memset(&other, 0, sizeof(other));
    LL_CRC_Write_IDR(&other, 0xCAFEBABEU);
    CHECK("UT-006", other.IDR == 0xCAFEBABEU);
    CHECK("UT-006", CRC->IDR == 0x76543210U && other.DR == 0U && other.CR == 0U);
}

/** @test UT-002 UT-005 UT-006 @verifies USPEC-LL-02-01 USPEC-LL-02-02 USPEC-LL-02-03 */
static void ut_read_idr(void)
{
    uint32_t got;
    CRC_TypeDef other;
    ut_reset_regs();
    CRC->IDR = 0x87654321U;
    got = LL_CRC_Read_IDR(CRC);
    CHECK("UT-002", got == 0x87654321U);
    CRC->IDR = 0x00000007U;
    got = LL_CRC_Read_IDR(CRC);
    CHECK("UT-005", got == 0x00000007U && CRC->IDR == 0x00000007U);
    CHECK("UT-005", CRC->DR == 0U && CRC->CR == 0U && CRC->INIT == 0U && CRC->POL == 0U);
    memset(&other, 0, sizeof(other));
    other.IDR = 0xDEADBEEFU;
    got = LL_CRC_Read_IDR(&other);
    CHECK("UT-006", got == 0xDEADBEEFU);
    CHECK("UT-006", other.IDR == 0xDEADBEEFU && CRC->IDR == 0x00000007U);
}

// UNIT TEST CASES (SWE.4 test author)

int main(void)
{
    ut_write_idr();
    ut_read_idr();
    // UNIT TEST CALLS (SWE.4 test author)
    return failures == 0 ? 0 : 1;
}
