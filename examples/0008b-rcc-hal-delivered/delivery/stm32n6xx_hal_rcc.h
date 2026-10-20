#ifndef STM32N6XX_HAL_RCC_H
#define STM32N6XX_HAL_RCC_H
#include "stm32n6xx_ll_rcc.h"
#include <stddef.h>

typedef enum {HAL_OK=0U,HAL_ERROR=1U,HAL_TIMEOUT=2U} hal_status_t;
#define HAL_RCC_TIMEOUT_VALUE 1000U

typedef enum
{
  HAL_RCC_OSC_HSI = 0,
  HAL_RCC_OSC_HSE = 1
} hal_rcc_oscillator_t;

/** @brief Configuration selecting the oscillator for an RCC operation. */
typedef struct hal_rcc_osc_config
{
  hal_rcc_oscillator_t oscillator; /**< Oscillator selected for the operation. */
} hal_rcc_osc_config_t;

typedef enum
{
  HAL_RCC_PERIPH_GPDMA1 = 0,
  HAL_RCC_PERIPH_ADC12 = 1
} hal_rcc_peripheral_t;

/** @brief Configuration selecting the peripheral for an RCC operation. */
typedef struct hal_rcc_periph_config
{
  hal_rcc_peripheral_t peripheral; /**< Peripheral selected for the operation. */
} hal_rcc_periph_config_t;

hal_status_t HAL_RCC_HSI_Enable(const hal_rcc_osc_config_t *config, uint32_t timeout);
hal_status_t HAL_RCC_HSI_Disable(const hal_rcc_osc_config_t *config);
hal_status_t HAL_RCC_HSE_Enable(const hal_rcc_osc_config_t *config, uint32_t timeout);
hal_status_t HAL_RCC_HSE_Disable(const hal_rcc_osc_config_t *config);
hal_status_t HAL_RCC_GPDMA1_Enable(const hal_rcc_periph_config_t *config);
hal_status_t HAL_RCC_GPDMA1_Disable(const hal_rcc_periph_config_t *config);
hal_status_t HAL_RCC_GPDMA1_Reset(const hal_rcc_periph_config_t *config);
hal_status_t HAL_RCC_ADC12_Enable(const hal_rcc_periph_config_t *config);

hal_status_t HAL_RCC_ADC12_Disable(const hal_rcc_periph_config_t *config);
hal_status_t HAL_RCC_ADC12_Reset(const hal_rcc_periph_config_t *config);

// HAL_RCC API prototypes (SWE.3 HAL author)
#endif /* STM32N6XX_HAL_RCC_H */
