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
    /* CP10/CP11 (FPU + MVE) full access, as CMSIS SystemInit does on the device: the compiler may use FP registers
       (e.g. `vmov s15, r1` as a spill slot under -mfloat-abi=hard), and without it the first one is a NOCP
       UsageFault (F015 GPIO-R3 scn_configuration: CFSR 0x00080000, stopped in forge_default_handler). */
    *(volatile uint32_t *)0xE000ED88U |= (0xFU << 20);
    __asm volatile("dsb\n\tisb" ::: "memory");
    for (p = &_sbss; p < &_ebss; p++) { *p = 0U; }
    (void)main();
    for (;;) { __asm volatile("wfi"); }
}
