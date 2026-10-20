#include "stm32n6xx_hal_rcc.h"

/**
 * @brief Enable the HSI oscillator and wait for readiness within the validated bound.
 * @unit SWU-HAL-01
 * @spec USPEC-HAL-01-01
 */
hal_status_t HAL_RCC_HSI_Enable(const hal_rcc_osc_config_t *config, uint32_t timeout)
{
  hal_status_t status = HAL_ERROR;
  if ((config != NULL) && (config->oscillator == HAL_RCC_OSC_HSI) && (timeout > 0U) && (timeout <= HAL_RCC_TIMEOUT_VALUE))
  {
    uint32_t count = 0U;
    uint32_t ready;
    LL_RCC_HSI_Enable();
    do
    {
      ready = LL_RCC_HSI_IsReady();
      count++;
    } while ((ready == 0U) && (count < timeout));
    if (ready == 0U)
    {
      LL_RCC_HSI_Disable();
      status = HAL_TIMEOUT;
    }
    else
    {
      status = HAL_OK;
    }
  }
  return status;
}

/**
 * @brief Disable the HSI oscillator.
 * @unit SWU-HAL-01
 * @spec USPEC-HAL-01-02
 */
hal_status_t HAL_RCC_HSI_Disable(const hal_rcc_osc_config_t *config)
{
  hal_status_t status = HAL_ERROR;
  if ((config != NULL) && (config->oscillator == HAL_RCC_OSC_HSI))
  {
    LL_RCC_HSI_Disable();
    status = HAL_OK;
  }
  return status;
}

/**
 * @brief Enable the HSE oscillator and wait for readiness within the validated bound.
 * @unit SWU-HAL-02
 * @spec USPEC-HAL-02-01
 */
hal_status_t HAL_RCC_HSE_Enable(const hal_rcc_osc_config_t *config, uint32_t timeout)
{
  hal_status_t status = HAL_ERROR;
  if ((config != NULL) && (config->oscillator == HAL_RCC_OSC_HSE) && (timeout > 0U) && (timeout <= HAL_RCC_TIMEOUT_VALUE))
  {
    uint32_t count = 0U;
    uint32_t ready;
    LL_RCC_HSE_Enable();
    do
    {
      ready = LL_RCC_HSE_IsReady();
      count++;
    } while ((ready == 0U) && (count < timeout));
    if (ready == 0U)
    {
      status = HAL_TIMEOUT;
    }
    else
    {
      status = HAL_OK;
    }
  }
  return status;
}

/**
 * @brief Disable the HSE oscillator.
 * @unit SWU-HAL-02
 * @spec USPEC-HAL-02-02
 */
hal_status_t HAL_RCC_HSE_Disable(const hal_rcc_osc_config_t *config)
{
  hal_status_t status = HAL_ERROR;
  if ((config != NULL) && (config->oscillator == HAL_RCC_OSC_HSE))
  {
    LL_RCC_HSE_Disable();
    status = HAL_OK;
  }
  return status;
}

/**
 * @brief Enable the GPDMA1 clock.
 * @unit SWU-HAL-03
 * @spec USPEC-HAL-03-01
 */
hal_status_t HAL_RCC_GPDMA1_Enable(const hal_rcc_periph_config_t *config)
{
  hal_status_t status = HAL_ERROR;
  if ((config != NULL) && (config->peripheral == HAL_RCC_PERIPH_GPDMA1))
  {
    LL_RCC_GPDMA1_Enable();
    status = HAL_OK;
  }
  return status;
}

/**
 * @brief Disable the GPDMA1 clock.
 * @unit SWU-HAL-03
 * @spec USPEC-HAL-03-02
 */
hal_status_t HAL_RCC_GPDMA1_Disable(const hal_rcc_periph_config_t *config)
{
  hal_status_t status = HAL_ERROR;
  if ((config != NULL) && (config->peripheral == HAL_RCC_PERIPH_GPDMA1))
  {
    LL_RCC_GPDMA1_Disable();
    status = HAL_OK;
  }
  return status;
}

/**
 * @brief Pulse the GPDMA1 reset (assert then release).
 * @unit SWU-HAL-03
 * @spec USPEC-HAL-03-03
 */
hal_status_t HAL_RCC_GPDMA1_Reset(const hal_rcc_periph_config_t *config)
{
  hal_status_t status = HAL_ERROR;
  if ((config != NULL) && (config->peripheral == HAL_RCC_PERIPH_GPDMA1))
  {
    LL_RCC_GPDMA1_ForceReset();
    LL_RCC_GPDMA1_ReleaseReset();
    status = HAL_OK;
  }
  return status;
}

/**
 * @brief Enable the ADC12 clock.
 * @unit SWU-HAL-04
 * @spec USPEC-HAL-04-01
 */
hal_status_t HAL_RCC_ADC12_Enable(const hal_rcc_periph_config_t *config)
{
  hal_status_t status = HAL_ERROR;
  if ((config != NULL) && (config->peripheral == HAL_RCC_PERIPH_ADC12))
  {
    LL_RCC_ADC12_Enable();
    status = HAL_OK;
  }
  return status;
}

/**
 * @brief Disable the ADC12 clock.
 * @unit SWU-HAL-04
 * @spec USPEC-HAL-04-02
 */
hal_status_t HAL_RCC_ADC12_Disable(const hal_rcc_periph_config_t *config)
{
  hal_status_t status = HAL_ERROR;
  if ((config != NULL) && (config->peripheral == HAL_RCC_PERIPH_ADC12))
  {
    LL_RCC_ADC12_Disable();
    status = HAL_OK;
  }
  return status;
}

/**
 * @brief Pulse the ADC12 reset (assert then release).
 * @unit SWU-HAL-04
 * @spec USPEC-HAL-04-03
 */
hal_status_t HAL_RCC_ADC12_Reset(const hal_rcc_periph_config_t *config)
{
  hal_status_t status = HAL_ERROR;
  if ((config != NULL) && (config->peripheral == HAL_RCC_PERIPH_ADC12))
  {
    LL_RCC_ADC12_ForceReset();
    LL_RCC_ADC12_ReleaseReset();
    status = HAL_OK;
  }
  return status;
}

// HAL_RCC API implementation (SWE.3 HAL author)
