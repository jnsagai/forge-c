/* Start-up code for the simulator images of the Safety Supervisor demo (test infrastructure). */
#include <stdint.h>
extern uint32_t _estack, _sidata, _sdata, _edata, _sbss, _ebss;
extern int main(void);
void sim_reset_handler(void);
void sim_default_handler(void);
#define WEAK __attribute__((weak, alias("sim_default_handler")))
WEAK void SVC_Handler(void);
WEAK void PendSV_Handler(void);
WEAK void SysTick_Handler(void);
WEAK void TIM2_IRQHandler(void);
WEAK void USART1_IRQHandler(void);
/* 16 exceptions and 195 interrupts; interrupt numbers: RM0486 section 24.1.2. Handlers not listed stop the program. */
__attribute__((section(".isr_vector"), used, aligned(1024))) static const void *const vectors[16 + 195] = {
    [0] = &_estack, [1] = (const void *)sim_reset_handler, [2 ... 10] = (const void *)sim_default_handler,
    [11] = (const void *)SVC_Handler, [12 ... 13] = (const void *)sim_default_handler,
    [14] = (const void *)PendSV_Handler, [15] = (const void *)SysTick_Handler,
    [16 ... 16 + 115] = (const void *)sim_default_handler, [16 + 116] = (const void *)TIM2_IRQHandler,
    [16 + 117 ... 16 + 158] = (const void *)sim_default_handler, [16 + 159] = (const void *)USART1_IRQHandler,
    [16 + 160 ... 16 + 194] = (const void *)sim_default_handler};
void sim_default_handler(void) { for (;;) { } }
void sim_reset_handler(void)
{
    uint32_t *d = &_sdata;
    const uint32_t *s = &_sidata;
    *(volatile uint32_t *)0xE000ED88U |= (0xFU << 20);
    __asm volatile("dsb\n\tisb" ::: "memory");
    while (d < &_edata) { *d++ = *s++; }
    for (d = &_sbss; d < &_ebss; d++) { *d = 0U; }
    (void)main();          /* .noinit is left as it was: retained over a reset */
    for (;;) { __asm volatile("wfi"); }
}
