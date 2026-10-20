#include "stm32n6xx_hal_iwdg.h"

/**
 * @brief Validate, start, configure and poll the watchdog before refreshing.
 * @unit SWU-HAL-01
 * @spec USPEC-HAL-01-01
 * @spec USPEC-HAL-01-02
 * @spec USPEC-HAL-01-03
 * @spec USPEC-HAL-01-04
 * @spec USPEC-HAL-01-05
 * @spec USPEC-HAL-01-06
 */
hal_status_t HAL_IWDG_Init(const hal_iwdg_config_t *p_config, uint32_t timeout)
{
    hal_status_t status = HAL_ERROR;
    if ((p_config == NULL) || (timeout == 0U) || (timeout > HAL_IWDG_TIMEOUT_VALUE) || (p_config->prescaler > 7U) || (p_config->reload > 0x0FFFU))
    {
        status = HAL_ERROR;
    }
    else
    {
        uint32_t count = 0U;
        status = HAL_TIMEOUT;
        LL_IWDG_Enable();
        LL_IWDG_EnableWriteAccess();
        LL_IWDG_SetPrescaler(p_config->prescaler);
        LL_IWDG_SetReloadCounter(p_config->reload);
        while (count < timeout)
        {
            const uint32_t pvu = LL_IWDG_IsActiveFlag_PVU();
            const uint32_t rvu = LL_IWDG_IsActiveFlag_RVU();
            count++;
            if ((pvu == 0U) && (rvu == 0U))
            {
                LL_IWDG_ReloadCounter();
                status = HAL_OK;
                break;
            }
        }
    }
    return status;
}

/**
 * @brief Refresh the watchdog counter unconditionally and return HAL_OK.
 * @unit SWU-HAL-02
 * @spec USPEC-HAL-02-01
 */
hal_status_t HAL_IWDG_Refresh(void)
{
    LL_IWDG_ReloadCounter();
    return HAL_OK;
}

// HAL_IWDG API implementation (SWE.3 HAL author)
