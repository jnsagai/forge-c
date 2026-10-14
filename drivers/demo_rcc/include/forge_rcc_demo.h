#ifndef FORGE_RCC_DEMO_H
#define FORGE_RCC_DEMO_H

/* Generic register model for an educational RCC-style device. NOT STM32N6. */
#include <stdint.h>

typedef struct
{
    volatile uint32_t clock_enable;
    volatile uint32_t reset_assert;
    volatile uint32_t reset_release;
} forge_rcc_demo_registers_t;

typedef struct
{
    forge_rcc_demo_registers_t *registers;
    uint32_t allowed_bits;
} forge_rcc_demo_t;

typedef enum
{
    FORGE_RCC_DEMO_OK = 0,
    FORGE_RCC_DEMO_INVALID_ARGUMENT = 1,
    FORGE_RCC_DEMO_INVALID_MASK = 2
} forge_rcc_demo_status_t;

/* HSI CONTRACT (DEMO):
 * - Caller owns exclusive access; driver operations are NOT reentrant.
 * - The register block is a valid, aligned, writable memory-mapped region.
 * - No concurrency with ISRs/other bus masters modifying the same registers.
 * - reset_assert and reset_release have write-one-to-act semantics.
 * - Clock enable is a read-modify-write register.
 * - These are illustrative semantics; NOT copied from a vendor manual.
 */
forge_rcc_demo_status_t forge_rcc_demo_init(forge_rcc_demo_t *context,
                                            forge_rcc_demo_registers_t *registers,
                                            uint32_t allowed_bits);
forge_rcc_demo_status_t forge_rcc_demo_enable_clock(forge_rcc_demo_t *context,
                                                    uint32_t bits);
forge_rcc_demo_status_t forge_rcc_demo_reset_pulse(forge_rcc_demo_t *context,
                                                   uint32_t bits);

#endif /* FORGE_RCC_DEMO_H */
