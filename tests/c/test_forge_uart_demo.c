/* CRE-T046 host tests for the UART RX fixture: ring buffer behaviour and the interrupt boundary, with a deterministic
 * interrupt injected inside the main-context read-modify-write of the shared count. */
#include "forge_uart_demo.h"

#include <stdint.h>
#include <stdio.h>

static int failures = 0;
#define CHECK(id, cond) do { if (cond) { printf("%s PASS\n", (id)); } else { printf("%s FAIL\n", (id)); failures++; } } while (0)

static forge_uart_regs_t regs;
static int irq_enabled = 1;
static int irq_pending = 0;
static int inject_armed = 0;
static uint8_t inject_byte = 0U;

static void receive(uint8_t b)
{
    regs.DR = b;
    regs.SR |= FORGE_UART_SR_RXNE;
    if (irq_enabled != 0)
    {
        forge_uart_rx_isr();
    }
    else
    {
        irq_pending = 1;
    }
}

void forge_irq_disable(void)
{
    irq_enabled = 0;
}

void forge_irq_enable(void)
{
    irq_enabled = 1;
    if (irq_pending != 0)
    {
        irq_pending = 0;
        forge_uart_rx_isr();
    }
}

void forge_inject_point(void)
{
    if (inject_armed != 0)
    {
        inject_armed = 0;
        receive(inject_byte);
    }
}

static void setup(void)
{
    regs.SR = 0U;
    regs.DR = 0U;
    regs.CR = 0U;
    irq_enabled = 1;
    irq_pending = 0;
    inject_armed = 0;
    (void)forge_uart_init(&regs);
}

static void ut_init_and_empty(void)
{
    uint8_t b = 0U;
    setup();
    CHECK("UT-001", (regs.CR & FORGE_UART_CR_RXNEIE) != 0U);
    CHECK("UT-002", forge_uart_read(&b) == FORGE_UART_EMPTY);
    CHECK("UT-003", forge_uart_init(NULL) == FORGE_UART_INVALID_ARGUMENT);
    CHECK("UT-004", forge_uart_read(NULL) == FORGE_UART_INVALID_ARGUMENT);
}

static void ut_fifo_order(void)
{
    uint8_t a = 0U;
    uint8_t b = 0U;
    setup();
    receive(0x41U);
    receive(0x42U);
    CHECK("UT-005", forge_uart_available() == 2U);
    CHECK("UT-006", (forge_uart_read(&a) == FORGE_UART_OK) && (a == 0x41U));
    CHECK("UT-007", (forge_uart_read(&b) == FORGE_UART_OK) && (b == 0x42U));
    CHECK("UT-008", (regs.SR & FORGE_UART_SR_RXNE) == 0U);
}

static void ut_overflow_drops(void)
{
    uint32_t i;
    setup();
    for (i = 0U; i < (FORGE_UART_RX_SIZE + 2U); i++)
    {
        receive((uint8_t)i);
    }
    CHECK("UT-009", forge_uart_available() == FORGE_UART_RX_SIZE);
    CHECK("UT-010", forge_uart_dropped() == 2U);
}

static void ut_interrupt_inside_read_is_not_lost(void)
{
    uint8_t a = 0U;
    uint8_t c = 0U;
    setup();
    receive(0x10U);
    receive(0x20U);
    inject_byte = 0x30U;
    inject_armed = 1; /* an RX interrupt arrives in the middle of the read's count update */
    CHECK("UT-011", (forge_uart_read(&a) == FORGE_UART_OK) && (a == 0x10U));
    CHECK("UT-012", forge_uart_available() == 2U); /* 2 - 1 read + 1 received: no lost update */
    (void)forge_uart_read(&a);
    CHECK("UT-013", (forge_uart_read(&c) == FORGE_UART_OK) && (c == 0x30U));
}

int main(void)
{
    ut_init_and_empty();
    ut_fifo_order();
    ut_overflow_drops();
    ut_interrupt_inside_read_is_not_lost();
    return (failures == 0) ? 0 : 1;
}
