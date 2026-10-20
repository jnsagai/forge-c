#include "stm32n6xx_hal_iwdg.h"

/**
 * @brief Wait for both update flags using the shared millisecond deadline.
 * @unit SWU-HAL-01
 * @spec USPEC-HAL-01-03
 */
static hal_status_t hal_iwdg_wait_ready(uint32_t start_tick, uint32_t timeout_ms)
{
    hal_status_t status = HAL_OK;
    uint32_t pvu;
    uint32_t rvu;
    uint32_t elapsed;
    do
    {
        pvu = LL_IWDG_IsActiveFlag_PVU();
        rvu = LL_IWDG_IsActiveFlag_RVU();
        elapsed = (uint32_t)(HAL_GetTick() - start_tick);
    } while (((pvu != 0U) || (rvu != 0U)) && (elapsed < timeout_ms));
    if ((pvu != 0U) || (rvu != 0U) || (elapsed > timeout_ms))
    {
        status = HAL_TIMEOUT;
    }
    return status;
}

/**
 * @brief Validate, start, configure and refresh within one deadline.
 * @unit SWU-HAL-01
 * @spec USPEC-HAL-01-01
 * @spec USPEC-HAL-01-02
 * @spec USPEC-HAL-01-03
 * @spec USPEC-HAL-01-04
 * @spec USPEC-HAL-01-05
 * @spec USPEC-HAL-01-06
 */
hal_status_t HAL_IWDG_Init(const hal_iwdg_config_t *p_config, uint32_t timeout_ms)
{
    hal_status_t status = HAL_ERROR;
    if (p_config != NULL)
    {
        if ((p_config->prescaler <= 7U) && (p_config->reload <= 0x0FFFU) &&
            (timeout_ms != 0U) && (timeout_ms <= HAL_IWDG_TIMEOUT_MS))
        {
            uint32_t start_tick;
            LL_IWDG_Enable();
            LL_IWDG_EnableWriteAccess();
            start_tick = HAL_GetTick();
            status = hal_iwdg_wait_ready(start_tick, timeout_ms);
            if (status == HAL_OK)
            {
                LL_IWDG_SetPrescaler(p_config->prescaler);
                LL_IWDG_SetReloadCounter(p_config->reload);
                status = hal_iwdg_wait_ready(start_tick, timeout_ms);
            }
            if (status == HAL_OK)
            {
                LL_IWDG_ReloadCounter();
            }
            else
            {
                LL_IWDG_DisableWriteAccess();
            }
        }
    }
    return status;
}

/**
 * @brief Refresh the independent watchdog and return success.
 * @unit SWU-HAL-02
 * @spec USPEC-HAL-02-01
 */
hal_status_t HAL_IWDG_Refresh(void)
{
    LL_IWDG_ReloadCounter();
    return HAL_OK;
}

// HAL_IWDG API implementation (SWE.3 HAL author)
