#ifndef STM32N6XX_HAL_IWDG_H
#define STM32N6XX_HAL_IWDG_H
#include <stddef.h>
#include "stm32n6xx_ll_iwdg.h"
typedef enum {HAL_OK=0U,HAL_ERROR=1U,HAL_TIMEOUT=2U} hal_status_t;
#define HAL_IWDG_TIMEOUT_VALUE 1000U
/**
 * @brief Independent watchdog initialization configuration.
 *
 * HAL_IWDG_Init validates both fields before accessing watchdog registers.
 */
typedef struct
{
    /** Watchdog prescaler encoding, from 0 through 7 inclusive. */
    uint32_t prescaler;
    /** Watchdog reload value, from 0 through 0x0FFF inclusive. */
    uint32_t reload;
} hal_iwdg_config_t;

hal_status_t HAL_IWDG_Init(const hal_iwdg_config_t *p_config, uint32_t timeout);
hal_status_t HAL_IWDG_Refresh(void);

// HAL_IWDG API prototypes (SWE.3 HAL author)
#endif /* STM32N6XX_HAL_IWDG_H */
