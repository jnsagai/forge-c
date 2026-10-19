/* Access-counting shim: compiled into the code under test with -include, so every ll_rcc_regs[...] access
 * becomes one call. The declaration in the driver header turns into a function declaration. */
#include <stdint.h>
volatile uint32_t (*shim_regs(void))[1024];
#define ll_rcc_regs (*shim_regs())
