/* Synthetic HAL serial driver (feature 020 test fixture, not vendor code). */
#include "ser_hal.h"

#define SER_WEAK __attribute__((weak))

static void SER_SetConfig(SER_HandleTypeDef *hser)
{
  hser->Instance->BRR = hser->BaudDivider & 0xFFFFUL;
}

HAL_StatusTypeDef HAL_SER_Init(SER_HandleTypeDef *hser)
{
  if (hser == 0)
  {
    return HAL_ERROR;
  }
  HAL_SER_MspInit(hser);
  SER_SetConfig(hser);
  hser->Instance->CR |= LL_SER_CR_UE;
  hser->State = HAL_SER_STATE_READY;
  return HAL_OK;
}

HAL_StatusTypeDef HAL_SER_DeInit(SER_HandleTypeDef *hser)
{
  if (hser == 0)
  {
    return HAL_ERROR;
  }
  hser->Instance->CR = 0UL;
  hser->State = HAL_SER_STATE_RESET;
  return HAL_OK;
}

SER_WEAK void HAL_SER_MspInit(SER_HandleTypeDef *hser)
{
  (void)hser;
}

HAL_StatusTypeDef HAL_SER_Transmit(SER_HandleTypeDef *hser, const uint8_t *pData, uint16_t Size, uint32_t Timeout)
{
  uint16_t i;
  if ((hser == 0) || (pData == 0) || (Size == 0U))
  {
    return HAL_ERROR;
  }
  for (i = 0U; i < Size; i++)
  {
    uint32_t n = Timeout;
    while (((hser->Instance->ISR & LL_SER_ISR_TXE) == 0UL) && (n > 0UL))
    {
      n--;
    }
    if (n == 0UL)
    {
      return HAL_TIMEOUT;
    }
    hser->Instance->TDR = pData[i];
  }
  HAL_SER_TxCpltCallback(hser);
  return HAL_OK;
}

HAL_StatusTypeDef HAL_SER_Receive(SER_HandleTypeDef *hser, uint8_t *pData, uint16_t Size, uint32_t Timeout)
{
  uint16_t i;
  (void)Timeout;
  if ((hser == 0) || (pData == 0) || (Size == 0U))
  {
    return HAL_ERROR;
  }
  for (i = 0U; i < Size; i++)
  {
    pData[i] = (uint8_t)(hser->Instance->RDR & 0xFFUL);
  }
  return HAL_OK;
}

SER_WEAK void HAL_SER_TxCpltCallback(SER_HandleTypeDef *hser)
{
  (void)hser;
}

HAL_SER_StateTypeDef HAL_SER_GetState(const SER_HandleTypeDef *hser)
{
  return hser->State;
}

HAL_StatusTypeDef HAL_SER_EnableLoop(SER_HandleTypeDef *hser)
{
  hser->Instance->CR |= LL_SER_CR_LOOP;
  return HAL_OK;
}
