/* Existing IDR-CONTRACT.md signatures, expressed as a compile-only contract.
 * This input supplies no implementation. Candidate code remains Qwen-authored. */
#ifndef FORGE_IDR_API_CONTRACT_H
#define FORGE_IDR_API_CONTRACT_H
#include "forge_crc_device.h"
static inline void LL_CRC_Write_IDR(CRC_TypeDef *CRCx, uint32_t InData);
static inline uint32_t LL_CRC_Read_IDR(const CRC_TypeDef *CRCx);
#endif
