/* CBMC BOUNDED DEMONSTRATOR, not a qualification proof.
 * Use with: cbmc tests/formal/cbmc_rcc_harness.c \
 *   drivers/demo_rcc/src/forge_rcc_demo.c \
 *   --function main --bounds-check --pointer-check --unwind 2 \
 *   -I drivers/demo_rcc/include
 */
#include "forge_rcc_demo.h"
#include <stdint.h>

extern uint32_t nondet_uint32(void);

int main(void)
{
    forge_rcc_demo_registers_t regs = {
        nondet_uint32(), UINT32_C(0), UINT32_C(0)
    };
    forge_rcc_demo_t context = {&regs, UINT32_C(0x0F)};
    const uint32_t old_clock = regs.clock_enable;
    const uint32_t mask = nondet_uint32();
    const forge_rcc_demo_status_t result = forge_rcc_demo_enable_clock(&context, mask);

    if ((mask == UINT32_C(0)) || ((mask & UINT32_C(0xFFFFFFF0)) != UINT32_C(0)))
    {
        __CPROVER_assert(result == FORGE_RCC_DEMO_INVALID_MASK, "invalid mask rejected");
        __CPROVER_assert(regs.clock_enable == old_clock, "invalid request has no side effects");
    }
    else
    {
        __CPROVER_assert(result == FORGE_RCC_DEMO_OK, "valid mask accepted");
        __CPROVER_assert(regs.clock_enable == (old_clock | mask), "only allowed bits set");
    }
    return 0;
}
