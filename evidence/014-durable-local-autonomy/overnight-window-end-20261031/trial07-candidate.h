/*
 * Copyright (c) 2026 STMicroelectronics
 * All rights reserved.
 *
 * This software is licensed under terms that can be found in the LICENSE file
 * in the root directory of this software component.
 */

/**
  * @file    stm32n6xx_ll_crc.h
  * @brief   STM32N6 CRC LL driver - CRC independent data register (CRC_IDR).
  *
  * Header-only LL driver exposing the two declared public functions for the
  * general-purpose 32-bit CRC independent data register (CRC_IDR.IDR,
  * offset 0x04, bits IDR[31:0], read/write):
  *
  *   - LL_CRC_Write_IDR : write the supplied 32-bit value to CRC_IDR.IDR
  *   - LL_CRC_Read_IDR  : read the current 32-bit value of CRC_IDR.IDR
  *
  * Source-backed CRC_TypeDef register layout (DR, IDR, CR, RESERVED1, INIT,
  * POL; IDR at offset 4) is supplied by the immutable device fixture
  * forge_crc_device.h (derived from ST cmsis-device-n6 v1.4.0 stm32n657xx.h,
  * RM0486 Rev4 section 26.4). The type is not redeclared and no singleton
  * register object is added.
  *
  * Caller precondition: CRCx is a valid, accessible CRC peripheral instance;
  * clock, power, security and access setup are owned by the caller. No
  * startup accesses, status polling, allocation or setup occur in this header.
  * Invalid pointers, inaccessible hardware and CRC polynomial/calculation/
  * configuration are outside the supported invocation domain.
  */

#ifndef STM32N6XX_LL_CRC_H
#define STM32N6XX_LL_CRC_H

#ifdef __cplusplus
extern "C" {
#endif

#include <stdint.h>
#include "forge_crc_device.h"

/**
  * @brief  Write the supplied 32-bit value to the CRC independent data
  *         register (CRC_IDR.IDR, bits IDR[31:0]).
  * @param  CRCx  Pointer to a valid, accessible CRC_TypeDef instance.
  * @param  InData 32-bit value; all 32 bits are written to IDR[31:0].
  * @retval None
  */
static void LL_CRC_Write_IDR(CRC_TypeDef *CRCx, uint32_t InData)
{
  CRCx->IDR = InData;
}

/**
  * @brief  Read the current value of the CRC independent data register
  *         (CRC_IDR.IDR, bits IDR[31:0]).
  * @param  CRCx  Pointer to a valid, accessible CRC_TypeDef instance.
  * @retval 32-bit value currently stored in CRC_IDR.IDR.
  */
static uint32_t LL_CRC_Read_IDR(const CRC_TypeDef *CRCx)
{
  return (uint32_t)CRCx->IDR;
}

#ifdef __cplusplus
}
#endif

#endif /* STM32N6XX_LL_CRC_H */
