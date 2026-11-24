/* Start-up code for the simulator images of the Safety Supervisor demo (test infrastructure). */
#include <stdint.h>
extern uint32_t _estack, _sidata, _sdata, _edata, _sbss, _ebss;
extern int main(void);
void sim_reset_handler(void);
void sim_default_handler(void);
__attribute__((section(".isr_vector"), used)) static const void *const vectors[16] = {
    &_estack, (const void *)sim_reset_handler, (const void *)sim_default_handler, (const void *)sim_default_handler};
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
