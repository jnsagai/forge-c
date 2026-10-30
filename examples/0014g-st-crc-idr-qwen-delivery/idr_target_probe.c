/* SPDX-License-Identifier: Apache-2.0
 * Target compilation probe for both declared public API signatures.
 * No main, physical execution or timing evidence is implied by this object.
 */
#include "forge_crc_device.h"
#include "stm32n6xx_ll_crc.h"
void forge_probe_write(CRC_TypeDef *instance, uint32_t value);
uint32_t forge_probe_read(const CRC_TypeDef *instance);
void forge_probe_write(CRC_TypeDef *instance, uint32_t value)
{
    LL_CRC_Write_IDR(instance, value);
}
uint32_t forge_probe_read(const CRC_TypeDef *instance)
{
    return LL_CRC_Read_IDR(instance);
}

