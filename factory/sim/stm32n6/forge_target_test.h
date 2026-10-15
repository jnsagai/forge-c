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
#endif
