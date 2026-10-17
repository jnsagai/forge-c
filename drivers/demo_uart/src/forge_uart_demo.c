/* CRE-T046 benchmark fixture: UART RX ring buffer shared between the RX ISR and main context. The shared count is
 * updated with a read-modify-write in both contexts; main context protects it with a critical section. */
#include "forge_uart_demo.h"

#include <stddef.h>

static forge_uart_regs_t *s_regs = NULL;
static uint8_t s_buf[FORGE_UART_RX_SIZE];
static uint32_t s_head = 0U;
static uint32_t s_tail = 0U;
static volatile uint32_t s_count = 0U;
static uint32_t s_dropped = 0U;

forge_uart_status_t forge_uart_init(forge_uart_regs_t *regs)
{
    forge_uart_status_t st = FORGE_UART_INVALID_ARGUMENT;
    if (regs != NULL)
    {
        s_regs = regs;
        s_head = 0U;
        s_tail = 0U;
        s_count = 0U;
        s_dropped = 0U;
        regs->CR |= FORGE_UART_CR_RXNEIE;
        st = FORGE_UART_OK;
    }
    return st;
}

void forge_uart_rx_isr(void)
{
    if ((s_regs != NULL) && ((s_regs->SR & FORGE_UART_SR_RXNE) != 0U))
    {
        uint8_t b = (uint8_t)(s_regs->DR & 0xFFU);
        s_regs->SR &= ~FORGE_UART_SR_RXNE;
        if (s_count < FORGE_UART_RX_SIZE)
        {
            s_buf[s_head] = b;
            s_head = (s_head + 1U) % FORGE_UART_RX_SIZE;
            s_count = s_count + 1U;
        }
        else
        {
            s_dropped = s_dropped + 1U;
        }
    }
}

forge_uart_status_t forge_uart_read(uint8_t *out)
{
    forge_uart_status_t st = FORGE_UART_INVALID_ARGUMENT;
    if (out != NULL)
    {
        st = FORGE_UART_EMPTY;
        forge_irq_disable();
        if (s_count > 0U)
        {
            uint32_t c = s_count;
            *out = s_buf[s_tail];
            s_tail = (s_tail + 1U) % FORGE_UART_RX_SIZE;
            FORGE_INJECT();
            s_count = c - 1U;
            st = FORGE_UART_OK;
        }
        forge_irq_enable();
    }
    return st;
}

uint32_t forge_uart_available(void)
{
    return s_count;
}

uint32_t forge_uart_dropped(void)
{
    return s_dropped;
}
