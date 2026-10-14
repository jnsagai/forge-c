#include "forge_rcc_demo.h"
#include <assert.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>

static void test_init_and_invalid_args(void)
{
    forge_rcc_demo_registers_t regs = {UINT32_C(0), UINT32_C(0), UINT32_C(0)};
    forge_rcc_demo_t context = {&regs, UINT32_C(0)};
    assert(forge_rcc_demo_init(NULL, &regs, UINT32_C(1)) == FORGE_RCC_DEMO_INVALID_ARGUMENT);
    assert(forge_rcc_demo_init(&context, NULL, UINT32_C(1)) == FORGE_RCC_DEMO_INVALID_ARGUMENT);
    assert(forge_rcc_demo_init(&context, &regs, UINT32_C(0)) == FORGE_RCC_DEMO_INVALID_MASK);
    assert(forge_rcc_demo_init(&context, &regs, UINT32_C(0x0F)) == FORGE_RCC_DEMO_OK);
    assert(context.registers == &regs);
    assert(context.allowed_bits == UINT32_C(0x0F));
}

static void test_clock_enable_masks(void)
{
    forge_rcc_demo_registers_t regs = {UINT32_C(0x80), UINT32_C(0), UINT32_C(0)};
    forge_rcc_demo_t context = {&regs, UINT32_C(0x0F)};
    assert(forge_rcc_demo_enable_clock(&context, UINT32_C(0x03)) == FORGE_RCC_DEMO_OK);
    assert(regs.clock_enable == UINT32_C(0x83));
    assert(forge_rcc_demo_enable_clock(&context, UINT32_C(0x04)) == FORGE_RCC_DEMO_OK);
    assert(regs.clock_enable == UINT32_C(0x87));
    assert(forge_rcc_demo_enable_clock(&context, UINT32_C(0x10)) == FORGE_RCC_DEMO_INVALID_MASK);
    assert(forge_rcc_demo_enable_clock(&context, UINT32_C(0)) == FORGE_RCC_DEMO_INVALID_MASK);
    assert(regs.clock_enable == UINT32_C(0x87));
}

static void test_reset_pulse_and_invalid_context(void)
{
    forge_rcc_demo_registers_t regs = {UINT32_C(0xF0), UINT32_C(0), UINT32_C(0)};
    forge_rcc_demo_t context = {&regs, UINT32_C(0x0F)};
    forge_rcc_demo_t unbound = {NULL, UINT32_C(0x0F)};
    assert(forge_rcc_demo_reset_pulse(&context, UINT32_C(0x02)) == FORGE_RCC_DEMO_OK);
    assert(regs.reset_assert == UINT32_C(0x02));
    assert(regs.reset_release == UINT32_C(0x02));
    assert(regs.clock_enable == UINT32_C(0xF0));
    assert(forge_rcc_demo_reset_pulse(&context, UINT32_C(0x20)) == FORGE_RCC_DEMO_INVALID_MASK);
    assert(forge_rcc_demo_reset_pulse(&context, UINT32_C(0)) == FORGE_RCC_DEMO_INVALID_MASK);
    assert(regs.reset_release == UINT32_C(0x02));
    assert(forge_rcc_demo_reset_pulse(NULL, UINT32_C(0x02)) == FORGE_RCC_DEMO_INVALID_ARGUMENT);
    assert(forge_rcc_demo_enable_clock(&unbound, UINT32_C(0x01)) == FORGE_RCC_DEMO_INVALID_ARGUMENT);
    assert(forge_rcc_demo_enable_clock(NULL, UINT32_C(0x01)) == FORGE_RCC_DEMO_INVALID_ARGUMENT);
    assert(forge_rcc_demo_reset_pulse(&unbound, UINT32_C(0x01)) == FORGE_RCC_DEMO_INVALID_ARGUMENT);
}

int main(void)
{
    test_init_and_invalid_args();
    test_clock_enable_masks();
    test_reset_pulse_and_invalid_context();
    puts("FORGE-C generic RCC driver host tests: PASS (NOT hardware evidence)");
    return 0;
}
