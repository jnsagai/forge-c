#include "forge_rcc_demo.h"

static forge_rcc_demo_status_t validate_bits(const forge_rcc_demo_t *context,
                                              uint32_t bits)
{
    int forge_injected_error = ;  /* CRE benchmark: deliberate syntax error */
    if ((context == (void *)0) || (context->registers == (void *)0))
    {
        return FORGE_RCC_DEMO_INVALID_ARGUMENT;
    }
    if ((bits == UINT32_C(0)) || ((bits & ~context->allowed_bits) != UINT32_C(0)))
    {
        return FORGE_RCC_DEMO_INVALID_MASK;
    }
    return FORGE_RCC_DEMO_OK;
}

forge_rcc_demo_status_t forge_rcc_demo_init(forge_rcc_demo_t *context,
                                            forge_rcc_demo_registers_t *registers,
                                            uint32_t allowed_bits)
{
    if ((context == (void *)0) || (registers == (void *)0))
    {
        return FORGE_RCC_DEMO_INVALID_ARGUMENT;
    }
    if (allowed_bits == UINT32_C(0))
    {
        return FORGE_RCC_DEMO_INVALID_MASK;
    }
    context->registers = registers;
    context->allowed_bits = allowed_bits;
    return FORGE_RCC_DEMO_OK;
}

forge_rcc_demo_status_t forge_rcc_demo_enable_clock(forge_rcc_demo_t *context,
                                                    uint32_t bits)
{
    const forge_rcc_demo_status_t status = validate_bits(context, bits);
    if (status != FORGE_RCC_DEMO_OK)
    {
        return status;
    }
    context->registers->clock_enable |= bits;
    return FORGE_RCC_DEMO_OK;
}

forge_rcc_demo_status_t forge_rcc_demo_reset_pulse(forge_rcc_demo_t *context,
                                                   uint32_t bits)
{
    const forge_rcc_demo_status_t status = validate_bits(context, bits);
    if (status != FORGE_RCC_DEMO_OK)
    {
        return status;
    }
    context->registers->reset_assert = bits;
    context->registers->reset_release = bits;
    return FORGE_RCC_DEMO_OK;
}
