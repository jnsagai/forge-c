# Pilot: Cortex-M55 STM32N6 RCC driver (candidate)

This pilot is **proposed**, not yet baselined and not declared an ISO 26262 safety-qualified microcontroller. Choose a precise STM32N6 order code / revision / board and determine whether it is suitable for the **actual automotive ASIL B safety context**. If no suitable safety documentation/assumptions exist, validate the technology on STM32N6 as a **QM experimental pilot** and use a safety-supported MCU for the ASIL B release candidate.

Why RCC first: exercises MMIO access, bitfield masking, clocks, reset sequences, hardware timeouts, startup states, interdependencies, power states and resource constraints. The pilot is a regression case for Forge-C's register/HSI engine.

## Baseline inputs

- MCU: STM32N6 family, Arm Cortex-M55 (confirm exact variant, security context, HSI bus and silicon revision).
- Reference manual: `RM0486` (pin document revision; verify vendor link), device datasheet and errata; official vendor source only.
- Register map: source-controlled **approved derived contract**: base addresses, offsets, register access semantics, reset values, legal masks, mandatory prerequisites, clocks/domains, interactions and variants.
- Software requirements: no guessed address values or safety goals; define reset/clock API from upstream architecture and HSI.
- First unit test: enable/disable one peripheral clock only after target-specific prerequisites; emulate register side effects and invalid operation.

## Candidate API families, not prescriptive signatures

```c
/* Candidate design API only. No register addresses or implementation here. */
typedef enum {
    RCC_RESULT_OK = 0,
    RCC_RESULT_BAD_PARAMETER,
    RCC_RESULT_TIMEOUT,
    RCC_RESULT_HW_FAULT
} rcc_result_t;

rcc_result_t rcc_enable_peripheral_clock(unsigned int peripheral_id,
                                         unsigned int timeout_ticks);
rcc_result_t rcc_reset_peripheral(unsigned int peripheral_id);
```

**Important:** The final APIs, types, validation policy, enum ABI and parameter semantics must follow detailed design, AUTOSAR or platform interface expectations, and safety requirements. Avoid `unsigned int` in a final API if width and strong typing are required; the snippet is only an intake discussion placeholder.

## Mandatory safety questions

1. Is reset management safety-relevant and which ASIL B safety requirements are actually allocated?
2. What is the safe state when a clock does not become ready or a reset is stuck?
3. Which registers are written-only, W1C, read-to-clear, protected or secure?
4. Which interrupts/cores/subsystems may race on the same registers?
5. Can clock switching temporarily invalidate watchdog, timers, debug or flash access?
6. Are the safety monitor and error detection independent of this driver?
7. What hardware revision errata impact reset cause reporting or clock initialization?

## HIL required before any target-dependent release

Instrument target clock/reset sequences, wrong states, stuck-ready/stuck-reset faults (where injectable), power-cycle and brownout conditions, interrupt concurrency and API max cycles. Renode may be used for software integration when a reliable peripheral model is implemented, but must not stand in for actual hardware performance/errata evidence.

Link: https://www.st.com/resource/en/reference_manual/dm00769900.pdf (verify RM revision against selected device).
