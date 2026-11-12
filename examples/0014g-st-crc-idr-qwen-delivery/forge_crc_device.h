/* SPDX-License-Identifier: Apache-2.0
 * Test/compile fixture for STM32N6 CRC register layout, not a driver.
 * Derived from ST cmsis-device-n6 v1.4.0 stm32n657xx.h CRC_TypeDef;
 * RM0486 Rev4 section26.4 and p.1172. No initialization or function bodies.
 * Host storage has no bus/access-control fidelity; target compilation alone
 * does not prove physical timing or peripheral accessibility.
 */
#ifndef FORGE_CRC_DEVICE_H
#define FORGE_CRC_DEVICE_H
#include <stdint.h>
#include <stddef.h>
typedef struct
{
    volatile uint32_t DR;
    volatile uint32_t IDR;
    volatile uint32_t CR;
    uint32_t RESERVED1;
    volatile uint32_t INIT;
    volatile uint32_t POL;
} CRC_TypeDef;
_Static_assert(offsetof(CRC_TypeDef, IDR) == 4U, "CRC IDR layout");
_Static_assert(sizeof(CRC_TypeDef) == 24U, "CRC register fixture layout");
#ifdef FORGE_HOST_BUILD
extern CRC_TypeDef forge_host_crc;
#define CRC (&forge_host_crc)
#ifdef FORGE_HOST_DEVICE_IMPLEMENTATION
CRC_TypeDef forge_host_crc;
#endif
#else
/* Source-backed secure peripheral base; caller accessibility is a precondition. */
#define CRC ((CRC_TypeDef *)0x56024C00UL)
#endif
#endif

