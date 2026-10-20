#include "stm32n6xx_hal_iwdg.h"

/**
 * @brief Validate and configure IWDG with one shared millisecond deadline.
 * @unit SWU-HAL-01
 * @spec USPEC-HAL-01-01
 * @spec USPEC-HAL-01-02
 * @spec USPEC-HAL-01-03
 * @spec USPEC-HAL-01-04
 * @spec USPEC-HAL-01-05
 */
hal_status_t HAL_IWDG_Init(const hal_iwdg_config_t *p_config, uint32_t timeout_ms)
{
    hal_status_t status = HAL_ERROR;
    if ((p_config != NULL) && (timeout_ms != 0U) && (timeout_ms <= HAL_IWDG_TIMEOUT_MS) &&
        (p_config->prescaler <= 7U) && (p_config->reload <= 0x0FFFU)) {
        uint32_t start_tick;
        LL_IWDG_Enable();
        LL_IWDG_EnableWriteAccess();
        start_tick = HAL_GetTick();
        while (((LL_IWDG_IsActiveFlag_PVU() != 0U) || (LL_IWDG_IsActiveFlag_RVU() != 0U)) &&
               ((uint32_t)(HAL_GetTick() - start_tick) < timeout_ms)) {
        }
        if ((LL_IWDG_IsActiveFlag_PVU() != 0U) || (LL_IWDG_IsActiveFlag_RVU() != 0U)) {
            LL_IWDG_DisableWriteAccess();
            status = HAL_TIMEOUT;
        } else {
            LL_IWDG_SetPrescaler(p_config->prescaler);
            LL_IWDG_SetReloadCounter(p_config->reload);
            while (((LL_IWDG_IsActiveFlag_PVU() != 0U) || (LL_IWDG_IsActiveFlag_RVU() != 0U)) &&
                   ((uint32_t)(HAL_GetTick() - start_tick) < timeout_ms)) {
            }
            if ((LL_IWDG_IsActiveFlag_PVU() != 0U) || (LL_IWDG_IsActiveFlag_RVU() != 0U)) {
                LL_IWDG_DisableWriteAccess();
                status = HAL_TIMEOUT;
            } else {
                LL_IWDG_ReloadCounter();
                status = HAL_OK;
            }
        }
    }
    return status;
}

/**
 * @brief Refresh IWDG once and return success.
 * @unit SWU-HAL-02
 * @spec USPEC-HAL-02-01
 */
hal_status_t HAL_IWDG_Refresh(void)
{
    LL_IWDG_ReloadCounter();
    return HAL_OK;
}

// HAL_IWDG API implementation (SWE.3 HAL author)
