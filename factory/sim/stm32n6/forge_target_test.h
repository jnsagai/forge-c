/* Forge-C target-test harness for Renode (results via a RAM mailbox read by forge-sim-mcp). */
#ifndef FORGE_TARGET_TEST_H
#define FORGE_TARGET_TEST_H
#include <stdint.h>
typedef struct { uint32_t magic; uint32_t passed; uint32_t failed; uint32_t done; uint32_t failed_ids[8]; } forge_mailbox_t;
extern volatile forge_mailbox_t forge_mailbox;
#define FORGE_MAILBOX_DEFINE volatile forge_mailbox_t forge_mailbox __attribute__((section(".forge_mailbox")))
/* TCHECK(n, cond): n is the numeric test id (e.g. 7 for UT-007) */
#define TCHECK(n, cond) do { if (cond) { forge_mailbox.passed++; } else { \
    if (forge_mailbox.failed < 8U) { forge_mailbox.failed_ids[forge_mailbox.failed] = (uint32_t)(n); } \
    forge_mailbox.failed++; } } while (0)
#define FORGE_TEST_BEGIN() do { forge_mailbox.magic = 0xF0C6E5A1U; forge_mailbox.passed = 0U; \
    forge_mailbox.failed = 0U; forge_mailbox.done = 0U; } while (0)
#define FORGE_TEST_END() do { forge_mailbox.done = 1U; } while (0)
/* Register-access log (owner 2026-11-02): the simulated peripheral model counts every read/write of its registers in
   this RAM block (factory/sim/stm32n6/forge_access_log.py), tagged with the phase the test set last. A prohibition is
   checked on the log, e.g. 'shall not access a register before the first call':
       TCHECK(1, FORGE_ACCESS_COUNT() == 0U);   (at the start of main, before any LL call)
       FORGE_ACCESS_PHASE(1U); LL_..._Init(...); FORGE_ACCESS_PHASE(2U);
       TCHECK(2, FORGE_ACCESS_COUNT_IN(2U) == 0U);   (after code that must not access the peripheral)
   Phases are 0..15 (0 = from reset until the first FORGE_ACCESS_PHASE). The phase write and the count reads are RAM
   accesses, never logged. Simulation only: the host RAM register block has no access log. */
#define FORGE_ACCESS_LOG_ADDR 0x341F0100U
#define FORGE_ACCESS_PHASE(p) do { ((volatile uint32_t *)FORGE_ACCESS_LOG_ADDR)[0] = (uint32_t)(p); } while (0)
#define FORGE_ACCESS_COUNT() (((volatile const uint32_t *)FORGE_ACCESS_LOG_ADDR)[1])
#define FORGE_ACCESS_COUNT_IN(p) (((volatile const uint32_t *)FORGE_ACCESS_LOG_ADDR)[2U + ((uint32_t)(p) & 15U)])
#endif
