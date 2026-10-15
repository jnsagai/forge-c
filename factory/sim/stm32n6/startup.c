/* Forge-C Renode target-test startup (Cortex-M55, RAM-resident image). Test-infrastructure only. */
#include <stdint.h>
extern uint32_t _estack, _sbss, _ebss;
extern int main(void);
void forge_reset_handler(void);
void forge_default_handler(void);
__attribute__((section(".isr_vector"), used)) static const void *const vectors[16] = {
    &_estack, (const void *)forge_reset_handler, (const void *)forge_default_handler,
    (const void *)forge_default_handler};
void forge_default_handler(void) { for (;;) { } }
void forge_reset_handler(void)
{
    uint32_t *p;
    for (p = &_sbss; p < &_ebss; p++) { *p = 0U; }
    (void)main();
    for (;;) { __asm volatile("wfi"); }
}
