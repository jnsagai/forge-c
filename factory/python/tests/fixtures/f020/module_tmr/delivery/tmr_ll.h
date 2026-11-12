/* Synthetic LL timer driver (feature 020 test fixture, not vendor code). */
#ifndef TMR_LL_H
#define TMR_LL_H
#include <stdint.h>

typedef struct
{
  volatile uint32_t CR;
  volatile uint32_t SR;
  volatile uint32_t CNT;
  volatile uint32_t ARR;
} TMR_TypeDef;

#define LL_TMR_CR_CEN (0x1UL << 0U)
#define LL_TMR_CR_OPM (0x1UL << 3U)
#define LL_TMR_SR_UIF (0x1UL << 0U)

static inline void LL_TMR_Enable(TMR_TypeDef *TMRx)
{
  TMRx->CR |= LL_TMR_CR_CEN;
}

static inline void LL_TMR_Disable(TMR_TypeDef *TMRx)
{
  TMRx->CR &= ~LL_TMR_CR_CEN;
}

static inline void LL_TMR_SetPeriod(TMR_TypeDef *TMRx, uint32_t Period)
{
  TMRx->ARR = Period;
}

static inline uint32_t LL_TMR_GetCounter(const TMR_TypeDef *TMRx)
{
  return TMRx->CNT;
}

static inline uint32_t LL_TMR_IsActiveFlag_UPD(const TMR_TypeDef *TMRx)
{
  return ((TMRx->SR & LL_TMR_SR_UIF) == LL_TMR_SR_UIF) ? 1UL : 0UL;
}

static inline void LL_TMR_ClearFlag_UPD(TMR_TypeDef *TMRx)
{
  TMRx->SR = ~LL_TMR_SR_UIF;
}

static inline void LL_TMR_EnableOnePulse(TMR_TypeDef *TMRx)
{
  TMRx->CR |= LL_TMR_CR_OPM;
}

#endif /* TMR_LL_H */
