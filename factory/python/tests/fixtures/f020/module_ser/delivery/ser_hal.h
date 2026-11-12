/* Synthetic HAL serial driver (feature 020 test fixture, not vendor code). */
#ifndef SER_HAL_H
#define SER_HAL_H
#include <stdint.h>
#include "ser_ll.h"

typedef enum
{
  HAL_OK = 0,
  HAL_ERROR = 1,
  HAL_BUSY = 2,
  HAL_TIMEOUT = 3
} HAL_StatusTypeDef;

typedef enum
{
  HAL_SER_STATE_RESET = 0,
  HAL_SER_STATE_READY = 1,
  HAL_SER_STATE_BUSY = 2
} HAL_SER_StateTypeDef;

typedef struct
{
  SER_TypeDef *Instance;
  uint32_t BaudDivider;
  HAL_SER_StateTypeDef State;
} SER_HandleTypeDef;

HAL_StatusTypeDef HAL_SER_Init(SER_HandleTypeDef *hser);
HAL_StatusTypeDef HAL_SER_DeInit(SER_HandleTypeDef *hser);
void HAL_SER_MspInit(SER_HandleTypeDef *hser);
HAL_StatusTypeDef HAL_SER_Transmit(SER_HandleTypeDef *hser, const uint8_t *pData, uint16_t Size, uint32_t Timeout);
HAL_StatusTypeDef HAL_SER_Receive(SER_HandleTypeDef *hser, uint8_t *pData, uint16_t Size, uint32_t Timeout);
void HAL_SER_TxCpltCallback(SER_HandleTypeDef *hser);
HAL_SER_StateTypeDef HAL_SER_GetState(const SER_HandleTypeDef *hser);
HAL_StatusTypeDef HAL_SER_EnableLoop(SER_HandleTypeDef *hser);

#endif /* SER_HAL_H */
