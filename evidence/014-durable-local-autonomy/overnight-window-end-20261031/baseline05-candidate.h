/*
 * STM32N6 CRC low-level driver - independent data register (IDR) access.
 *
 * Register authority: RM0486 Rev 4 section 26.4.2 (CRC_IDR), p.1172 -
 * general-purpose 32-bit data register at offset 0x04, bits IDR[31:0] all
 * read/write, reset value 0x00000000, not affected by CRC_CR.RESET.
 *
 * Register layout: forge_crc_device.h (immutable input fixture, derived from
 * ST cmsis-device-n6 v1.4.0 stm32n657xx.h CRC_TypeDef). This header does not
 * redeclare the type and adds no singleton register object.
 *
 * Invocation domain (inputs/IDR-CONTRACT.md): the caller supplies a valid,
 * accessible CRC_TypeDef instance; clock/power/security setup is a caller
 * precondition. No startup accesses, no status polling, no allocation and no
 * CRC calculation/configuration occur in this scope.
 */
#ifndef STM32N6XX_LL_CRC_H
#define STM32N6XX_LL_CRC_H

#include "forge_crc_device.h" /* CRC_TypeDef layout (RM0486 p.1172) */

/**
 * @brief  Write the supplied 32-bit value to the CRC independent data register.
 * @param  crcx   Pointer to a valid accessible CRC_TypeDef instance.
 * @param  indata Value to store in CRC_IDR.IDR[31:0]; all 32 bits are written.
 * @retval None
 */
static inline void LL_CRC_Write_IDR(CRC_TypeDef *crcx, uint32_t indata)
{
    crcx->IDR = indata; /* volatile 32-bit word write (RM0486 p.1172) */
}

/**
 * @brief  Read the 32-bit value currently stored in the CRC independent
 *         data register.
 * @param  crcx   Pointer to a valid accessible CRC_TypeDef instance.
 * @retval Current CRC_IDR.IDR[31:0] value.
 */
static inline uint32_t LL_CRC_Read_IDR(const CRC_TypeDef *crcx)
{
    return crcx->IDR; /* volatile 32-bit word read (RM0486 p.1172) */
}

#endif /* STM32N6XX_LL_CRC_H */
