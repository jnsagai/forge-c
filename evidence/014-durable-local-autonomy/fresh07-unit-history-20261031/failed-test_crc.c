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

static int inst_eq(const CRC_TypeDef *a, const CRC_TypeDef *b)
{
    return a->DR == b->DR && a->IDR == b->IDR && a->CR == b->CR &&
           a->RESERVED1 == b->RESERVED1 && a->INIT == b->INIT && a->POL == b->POL;
}

/** @test UT-001 @verifies USPEC-LL-01-01 USPEC-LL-01-05 */
static void ut_crc_write(void)
{
    ut_reset_regs();
    CHECK("UT-001a", CRC->IDR == 0x00000000U);
    LL_CRC_Write_IDR(CRC, 0x12345678U);
    CHECK("UT-001", CRC->IDR == 0x12345678U);
}

/** @test UT-002 @verifies USPEC-LL-01-01 */
static void ut_crc_write_patterns(void)
{
    uint32_t bit;
    static const uint32_t patterns[3] = { 0x00000000U, 0xFFFFFFFFU, 0x55555555U };
    ut_reset_regs();
    LL_CRC_Write_IDR(CRC, 0xAAAAAAAAU);
    CHECK("UT-002", CRC->IDR == 0xAAAAAAAAU);
    for (unsigned i = 0U; i < 3U; i++) {
        LL_CRC_Write_IDR(CRC, patterns[i]);
        CHECK("UT-002", CRC->IDR == patterns[i]);
    }
    for (bit = 1U; bit != 0U; bit <<= 1U) {
        LL_CRC_Write_IDR(CRC, bit);
        CHECK("UT-002", CRC->IDR == bit);
        LL_CRC_Write_IDR(CRC, ~bit);
        CHECK("UT-002", CRC->IDR == ~bit);
    }
}

/** @test UT-003 @verifies USPEC-LL-01-02 */
static void ut_crc_read(void)
{
    ut_reset_regs();
    CRC->IDR = 0x87654321U;
    CHECK("UT-003", LL_CRC_Read_IDR(CRC) == 0x87654321U);
}

/** @test UT-004 @verifies USPEC-LL-01-02 USPEC-LL-01-03 */
static void ut_crc_read_no_modify(void)
{
    uint32_t r1;
    uint32_t r2;
    ut_reset_regs();
    CRC->IDR = 0xDEADBEEFU;
    r1 = LL_CRC_Read_IDR(CRC);
    r2 = LL_CRC_Read_IDR(CRC);
    CHECK("UT-004", r1 == 0xDEADBEEFU && r2 == 0xDEADBEEFU);
    CHECK("UT-004", CRC->IDR == 0xDEADBEEFU);
    CRC->IDR = 0x00000001U;
    CHECK("UT-004", LL_CRC_Read_IDR(CRC) == 0x00000001U);
    CHECK("UT-004", CRC->IDR == 0x00000001U);
}

/** @test UT-005 @verifies USPEC-LL-01-03 USPEC-LL-01-04 */
static void ut_crc_preserve(void)
{
    uint32_t dr;
    uint32_t cr;
    uint32_t init;
    uint32_t pol;
    ut_reset_regs();
    CRC->DR = 0x11111111U;
    CRC->CR = 0x22222222U;
    CRC->RESERVED1 = 0x33333333U;
    CRC->INIT = 0x44444444U;
    CRC->POL = 0x04C11DB7U;
    dr = CRC->DR;
    cr = CRC->CR;
    init = CRC->INIT;
    pol = CRC->POL;
    LL_CRC_Write_IDR(CRC, 0x5A5A5A5AU);
    CHECK("UT-005", CRC->IDR == 0x5A5A5A5AU);
    CHECK("UT-005", CRC->DR == dr && CRC->CR == cr && CRC->RESERVED1 == 0x33333333U);
    CHECK("UT-005", CRC->INIT == init && CRC->POL == pol);
    LL_CRC_Read_IDR(CRC);
    CHECK("UT-005", CRC->DR == dr && CRC->CR == cr && CRC->RESERVED1 == 0x33333333U);
    CHECK("UT-005", CRC->INIT == init && CRC->POL == pol);
}

/** @test UT-006 @verifies USPEC-LL-01-04 */
static void ut_crc_instance_isolation(void)
{
    static CRC_TypeDef second;
    CRC_TypeDef snapshot;
    ut_reset_regs();
    (void)memset((void *)&second, 0, sizeof(second));
    second.DR = 0xA0000001U;
    second.IDR = 0xB0000002U;
    second.CR = 0xC0000003U;
    second.RESERVED1 = 0xD0000004U;
    second.INIT = 0xE0000005U;
    second.POL = 0xF0000006U;
    snapshot = second;
    LL_CRC_Write_IDR(CRC, 0x12345678U);
    LL_CRC_Read_IDR(CRC);
    CHECK("UT-006", CRC->IDR == 0x12345678U);
    CHECK("UT-006", inst_eq(&second, &snapshot));
}

/** @test UT-007 @verifies USPEC-LL-01-04 */
static void ut_crc_supplied_instance(void)
{
    static CRC_TypeDef first;
    static CRC_TypeDef second;
    CRC_TypeDef *supplied;
    ut_reset_regs();
    (void)memset((void *)&first, 0, sizeof(first));
    (void)memset((void *)&second, 0, sizeof(second));
    second.IDR = 0x77777777U;
    supplied = &first;
    LL_CRC_Write_IDR(supplied, 0x12345678U);
    CHECK("UT-007", supplied->IDR == 0x12345678U);
    CHECK("UT-007", LL_CRC_Read_IDR(supplied) == 0x12345678U);
    CHECK("UT-007", CRC->IDR == 0x00000000U);
    CHECK("UT-007", second.IDR == 0x77777777U);
}

/** @test UT-008 @verifies USPEC-LL-01-02 */
static void ut_crc_no_status(void)
{
    uint32_t value;
    uint32_t result;
    ut_reset_regs();
    CRC->IDR = 0x0BADF00DU;
    result = LL_CRC_Read_IDR(CRC);
    CHECK("UT-008", result == 0x0BADF00DU);
    value = 0xC0FFEE00U;
    LL_CRC_Write_IDR(CRC, value);
    CHECK("UT-008", CRC->IDR == value);
    CHECK("UT-008", LL_CRC_Read_IDR(CRC) == value);
}

/** @test UT-009 @verifies USPEC-LL-01-01 USPEC-LL-01-02 USPEC-LL-01-06 */
static void ut_crc_roundtrip(void)
{
    static const uint32_t values[4] = { 0x00000000U, 0xFFFFFFFFU, 0xAAAAAAAAU, 0x55555555U };
    for (unsigned i = 0U; i < 4U; i++) {
        ut_reset_regs();
        LL_CRC_Write_IDR(CRC, values[i]);
        CHECK("UT-009", CRC->IDR == values[i]);
        CHECK("UT-009", LL_CRC_Read_IDR(CRC) == values[i]);
    }
}

// UNIT TEST CASES (SWE.4 test author)

int main(void)
{
    ut_crc_write();
    ut_crc_write_patterns();
    ut_crc_read();
    ut_crc_read_no_modify();
    ut_crc_preserve();
    ut_crc_instance_isolation();
    ut_crc_supplied_instance();
    ut_crc_no_status();
    ut_crc_roundtrip();
    // UNIT TEST CALLS (SWE.4 test author)
    return failures == 0 ? 0 : 1;
}
