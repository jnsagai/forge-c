/* Synthetic CMSIS-style device header (feature 020 test fixture, not a real device). */
#ifndef SER_DEVICE_H
#define SER_DEVICE_H
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

#define SER1_BASE           (0x40001000UL)
#define SER1                ((SER_TypeDef *) SER1_BASE)

#define SER_CR_UE_Pos       (0U)
#define SER_CR_UE_Msk       (0x1UL << SER_CR_UE_Pos)
#define SER_CR_UE           SER_CR_UE_Msk
#define SER_CR_LOOP_Pos     (5U)
#define SER_CR_LOOP_Msk     (0x1UL << SER_CR_LOOP_Pos)
#define SER_CR_LOOP         SER_CR_LOOP_Msk
#define SER_ISR_TXE_Pos     (7U)
#define SER_ISR_TXE_Msk     (0x1UL << SER_ISR_TXE_Pos)
#define SER_ISR_TXE         SER_ISR_TXE_Msk
#define SER_ISR_ORE_Pos     (3U)
#define SER_ISR_ORE_Msk     (0x1UL << SER_ISR_ORE_Pos)
#define SER_ISR_ORE         SER_ISR_ORE_Msk
#define SER_ICR_ORECF_Pos   (3U)
#define SER_ICR_ORECF_Msk   (0x1UL << SER_ICR_ORECF_Pos)
#define SER_ICR_ORECF       SER_ICR_ORECF_Msk

#endif /* SER_DEVICE_H */
