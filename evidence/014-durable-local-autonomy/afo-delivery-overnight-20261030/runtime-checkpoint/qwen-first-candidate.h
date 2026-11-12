/*
 * STM32N6 CRC low-layer (LL) driver candidate: independent data register (IDR).
 *
 * QM development candidate, work order WO-AFO-5faf7b5e42e6d55f-a1.
 * Register layout: CRC_TypeDef from forge_crc_device.h (source-backed fixture
 * derived from ST cmsis-device-n6 v1.4.0 stm32n657xx.h; RM0486 p.1172).
 *
 * Scope (RM0486 Rev 4 section 26.4.2, p.1172):
 *   - write all 32 bits of CRC_IDR.IDR (general-purpose 32-bit storage, rw,
 *     not affected by CRC_CR.RESET; RM0486 p.1171, p.1172);
 *   - read back the current 32-bit CRC_IDR.IDR value.
 * Out of scope: CRC calculation, polynomial/initial-value configuration,
 * status polling, allocation and any autonomous startup access.
 *
 * Caller precondition (RM0486 p.176): CRCx is a valid, accessible CRC_TypeDef
 * instance; clock/power/security and access setup are owned by the caller.
 * Invalid pointers and inaccessible hardware are outside the invocation
 * domain of these functions.
 */
#ifndef STM32N6XX_LL_CRC_H
#define STM32N6XX_LL_CRC_H

#include <stdint.h>

#include "forge_crc_device.h"

/**
 * @brief  Write the supplied 32-bit value to the CRC independent data register.
 * @param  CRCx   Pointer to a valid accessible CRC_TypeDef instance.
 * @param  InData Value to store in CRC_IDR.IDR[31:0].
 * @retval None.
 * @note   RM0486 p.1172: CRC_IDR at offset 0x04, word access only,
 *         general-purpose temporary storage, not affected by CRC reset
 *         (RM0486 p.1171). No other register is written.
 */
static inline void LL_CRC_Write_IDR(CRC_TypeDef *CRCx, uint32_t InData)
{
    CRCx->IDR = InData;
}

/**
 * @brief  Read the current 32-bit value of the CRC independent data register.
 * @param  CRCx Pointer to a valid accessible CRC_TypeDef instance.
 * @retval Current CRC_IDR.IDR[31:0] value.
 * @note   RM0486 p.1172: plain read of CRC_IDR; no register is modified,
 *         no calculation or status side effect occurs.
 */
static inline uint32_t LL_CRC_Read_IDR(const CRC_TypeDef *CRCx)
{
    return CRCx->IDR;
}

#endif /* STM32N6XX_LL_CRC_H */
