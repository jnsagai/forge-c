#ifndef FORGE_UART_DEMO_H
#define FORGE_UART_DEMO_H
/* CRE-T046 benchmark fixture: register-level UART receive path with an interrupt boundary (RX ISR -> ring buffer,
 * main-context read). Not a product driver: a deterministic benchmark workload for the CRE benchmark matrix. */
#include <stdint.h>

typedef struct
{
    volatile uint32_t SR; /* bit 5 RXNE: receive data register not empty */
    volatile uint32_t DR; /* received byte in bits 7:0 */
    volatile uint32_t CR; /* bit 5 RXNEIE: receive interrupt enable */
} forge_uart_regs_t;

#define FORGE_UART_SR_RXNE (1UL << 5U)
#define FORGE_UART_CR_RXNEIE (1UL << 5U)
#define FORGE_UART_RX_SIZE 8U

typedef enum
{
    FORGE_UART_OK = 0,
    FORGE_UART_EMPTY = 1,
    FORGE_UART_INVALID_ARGUMENT = 2
} forge_uart_status_t;

forge_uart_status_t forge_uart_init(forge_uart_regs_t *regs);
void forge_uart_rx_isr(void);
forge_uart_status_t forge_uart_read(uint8_t *out);
uint32_t forge_uart_available(void);
uint32_t forge_uart_dropped(void);

/* Platform hooks: on target the BSP maps them to __disable_irq/__enable_irq; host tests provide stubs. */
void forge_irq_disable(void);
void forge_irq_enable(void);

/* Deterministic interrupt injection point inside the read-modify-write of the shared count (host tests only). */
#ifdef FORGE_HOST_TEST
void forge_inject_point(void);
#define FORGE_INJECT() forge_inject_point()
#else
#define FORGE_INJECT() ((void)0)
#endif

#endif /* FORGE_UART_DEMO_H */
