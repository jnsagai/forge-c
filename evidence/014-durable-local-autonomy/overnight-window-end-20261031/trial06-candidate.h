/**
  * @file    stm32n6xx_ll_crc.h
  * @brief   STM32N6 CRC LL driver (independent data register slice), header-only.
  *
  * @details Qwen-authored candidate for WO-AFO-7f71565db57f0a76-a1. Scope is
  *          limited to the general-purpose 32-bit independent data register
  *          CRC_IDR (RM0486 Rev4 section 26.4.2, p.1172; address offset 0x04,
  *          bits IDR[31:0], all rw):
  *          - LL_CRC_Write_IDR writes the supplied 32-bit value to CRC_IDR.IDR.
  *          - LL_CRC_Read_IDR  returns the current 32-bit CRC_IDR.IDR value.
  *          No CRC calculation, feed, polynomial, INIT, reset, DMA, HAL,
  *          startup access, status polling, allocation or error signaling is
  *          implemented or implied by this slice.
  *
  *          The caller supplies a valid accessible CRC_TypeDef instance
  *          (clock, power, security and access setup are caller preconditions).
  *          The register layout type is provided by the immutable device
  *          fixture forge_crc_device.h; it is not redeclared here and no
  *          singleton register objects are added.
  */

#ifndef STM32N6XX_LL_CRC_H
#define STM32N6XX_LL_CRC_H

#include "forge_crc_device.h"

/**
  * @brief  Write the supplied 32-bit value to the CRC independent data register.
  * @param  CRCx  Pointer to a valid accessible CRC instance.
  * @param  InData 32-bit value written to CRC_IDR.IDR (all 32 bits, rw).
  * @retval None
  *
  * @note   RM0486 Rev4 section 26.4.2 (CRC_IDR), p.1172. The register is a
  *         general-purpose 32-bit data register, unaffected by CRC calculation
  *         resets. This function only writes the IDR field; no other register
  *         of the instance or of other instances is touched.
  */
static inline void LL_CRC_Write_IDR(CRC_TypeDef *CRCx, uint32_t InData)
{
  CRCx->IDR = InData;
}

/**
  * @brief  Read the current value of the CRC independent data register.
  * @param  CRCx  Pointer to a valid accessible CRC instance.
  * @retval 32-bit value currently stored in CRC_IDR.IDR (IDR[31:0]).
  *
  * @note   RM0486 Rev4 section 26.4.2 (CRC_IDR), p.1172. Plain register read
  *         with no side effects on the calculation unit or configuration.
  *         This function only reads the IDR field; no other register is
  *         accessed or modified.
  */
static inline uint32_t LL_CRC_Read_IDR(const CRC_TypeDef *CRCx)
{
  return CRCx->IDR;
}

#endif /* STM32N6XX_LL_CRC_H */
