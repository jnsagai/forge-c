/** @file test_performance.c @verifies IF-01 IF-02 */
/*
 * SWE.5/SWE.6 simulation-only performance measurement scenario (QM demo).
 * Pinned Renode STM32N6 Cortex-M55 behavioural CRC model, 100 MIPS virtual
 * clock, no injected interrupts or bus stalls. The generated
 * forge_performance_calls.h declares typed wrappers forge_measure_LL_CRC_
 * Write_IDR / forge_measure_LL_CRC_Read_IDR for exactly the scoped functions;
 * the simulator observes entry and return PCs of each completed call.
 * The budget (64 executed instructions and 100 microseconds of virtual time
 * per measured call) is enforced by the SWE.6 "Simulation Performance Should
 * Meet Budget" check, not by a TCHECK here. This is NOT a hardware timing
 * claim and not physical WCET.
 */
#include "stm32n6xx_ll_crc.h"
#include "forge_target_test.h"
#include "forge_performance_calls.h"

FORGE_MAILBOX_DEFINE;

/* Linker-placed CRC register block (RM0486 p.176, 0x56024C00). */
#define LL_CRC_IDR_OFFSET  4U
#define LL_CRC_CR_OFFSET   8U
extern char ll_crc_regs[];
#define ll_crc_word(n) (((volatile uint32_t *)(void *)ll_crc_regs)[(n)])

int main(void)
{
    uint32_t r;
    FORGE_TEST_BEGIN();
    /* Measured writes: zero, all ones, alternating patterns (SWR-012 scope). */
    (void)forge_measure_LL_CRC_Write_IDR(CRC, 0x00000000U);
    (void)forge_measure_LL_CRC_Write_IDR(CRC, 0xFFFFFFFFU);
    (void)forge_measure_LL_CRC_Write_IDR(CRC, 0xAAAAAAAAU);
    /* Functional checks on LL return values and register bits. */
    r = (uint32_t)forge_measure_LL_CRC_Read_IDR(CRC);
    TCHECK(1, r == 0xAAAAAAAAU);
    TCHECK(2, ll_crc_word(LL_CRC_IDR_OFFSET / 4U) == 0xAAAAAAAAU);
    TCHECK(3, ll_crc_word(LL_CRC_CR_OFFSET / 4U) == 0x00000000U);
    /* Measured reads: alternating pattern, all ones, zero. */
    (void)forge_measure_LL_CRC_Read_IDR(CRC);
    (void)forge_measure_LL_CRC_Write_IDR(CRC, 0x55555555U);
    r = (uint32_t)forge_measure_LL_CRC_Read_IDR(CRC);
    TCHECK(4, r == 0x55555555U);
    TCHECK(5, ll_crc_word(LL_CRC_IDR_OFFSET / 4U) == 0x55555555U);
    (void)forge_measure_LL_CRC_Write_IDR(CRC, 0xFFFFFFFFU);
    (void)forge_measure_LL_CRC_Read_IDR(CRC);
    (void)forge_measure_LL_CRC_Write_IDR(CRC, 0x00000000U);
    r = (uint32_t)forge_measure_LL_CRC_Read_IDR(CRC);
    TCHECK(6, r == 0x00000000U);
    TCHECK(7, ll_crc_word(LL_CRC_IDR_OFFSET / 4U) == 0x00000000U);
    FORGE_TEST_END();
    return 0;
}
