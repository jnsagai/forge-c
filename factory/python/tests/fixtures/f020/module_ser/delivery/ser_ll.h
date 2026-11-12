/* Synthetic LL serial driver (feature 020 test fixture, not vendor code). */
#ifndef SER_LL_H
#define SER_LL_H
#include <stdint.h>

typedef struct
{
  volatile uint32_t CR;
  volatile uint32_t BRR;
  volatile uint32_t ISR;
  volatile uint32_t ICR;
  volatile uint32_t TDR;
  volatile uint32_t RDR;
} SER_TypeDef;

#define LL_SER_CR_UE     (0x1UL << 0U)
#define LL_SER_CR_LOOP   (0x1UL << 5U)
#define LL_SER_ISR_TXE   (0x1UL << 7U)
#define LL_SER_ISR_ORE   (0x1UL << 3U)
#define LL_SER_ICR_ORECF (0x1UL << 3U)

static inline void LL_SER_Enable(SER_TypeDef *SERx)
{
  SERx->CR |= LL_SER_CR_UE;
}

static inline void LL_SER_Disable(SER_TypeDef *SERx)
{
  SERx->CR &= ~LL_SER_CR_UE;
}

static inline uint32_t LL_SER_IsEnabled(const SER_TypeDef *SERx)
{
  return ((SERx->CR & LL_SER_CR_UE) == LL_SER_CR_UE) ? 1UL : 0UL;
}

static inline void LL_SER_SetBaud(SER_TypeDef *SERx, uint32_t Divider)
{
  SERx->BRR = Divider & 0xFFFFUL;
}

static inline void LL_SER_TransmitData(SER_TypeDef *SERx, uint32_t Value)
{
  SERx->TDR = Value & 0x1FFUL;
}

static inline uint32_t LL_SER_ReceiveData(const SER_TypeDef *SERx)
{
  return SERx->RDR & 0x1FFUL;
}

static inline uint32_t LL_SER_IsActiveFlag_TXE(const SER_TypeDef *SERx)
{
  return ((SERx->ISR & LL_SER_ISR_TXE) == LL_SER_ISR_TXE) ? 1UL : 0UL;
}

static inline uint32_t LL_SER_IsActiveFlag_ORE(const SER_TypeDef *SERx)
{
  return ((SERx->ISR & LL_SER_ISR_ORE) == LL_SER_ISR_ORE) ? 1UL : 0UL;
}

static inline void LL_SER_ClearFlag_ORE(SER_TypeDef *SERx)
{
  SERx->ICR = LL_SER_ICR_ORECF;
}

static inline void LL_SER_EnableLoop(SER_TypeDef *SERx)
{
  SERx->CR |= LL_SER_CR_LOOP;
}

static inline uint32_t LL_SER_IsEnabledLoop(const SER_TypeDef *SERx)
{
  return ((SERx->CR & LL_SER_CR_LOOP) == LL_SER_CR_LOOP) ? 1UL : 0UL;
}

#endif /* SER_LL_H */
