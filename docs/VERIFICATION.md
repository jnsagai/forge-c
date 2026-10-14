# Verification strategy for HAL / low-level drivers

## Verification layers

1. **Host unit verification (SWE.4):** C11 native build; Unity/CMock or C compiled into test target with GoogleTest host C++ test harness. Register models allow verifying exact read/write sequences and side-effects, not just return values.
2. **Static verification (SWE.4):** GCC/Clang warnings-as-errors, clang-tidy/Clang Static Analyzer, Cppcheck, configured MISRA checker; CBMC/Frama-C selectively for pointer and bit manipulations.
3. **Component verification (SWE.5):** state machine/API contracts, clock gating, reset recovery, interrupts, error handling, concurrency and supported variants.
4. **Integration verification (SWE.5):** HSI integration with clock tree, reset controller, NVIC, HAL users, DMA and application-side driver contracts in HwSim/Renode as appropriate.
5. **Software verification (SWE.6):** full software assembled for target, requirements-based functional and non-functional requirements, timing, footprint and safety responses.
6. **Target HIL (ISO 26262-6, applicable):** reference board or ECU with real clock/reset/fault conditions, measured timing and errata regression, flash and boot flow.

## Register-controller test matrix

| Area | Nominal | Boundary / negative / fault tests |
|---|---|---|
| Reset values | detect each documented reset state | POR vs warm reset, retained state, reset cause flags |
| Enable/disable clock | exact register write and ready indication | no clock present, invalid selector, timeout, clock domains |
| Peripheral reset | assert / deassert with supported order | reset during transaction, peripheral busy, clock disabled |
| Masks | preserve reserved bits and other peripherals | W1C/read-to-clear, mixed write restrictions, read-only |
| Concurrent access | ISR/task ordering and critical section | nested ISR, preemption, torn RMW, shared domains |
| Startup/shutdown | safe state after boot and after recovery | brownout, low power, illegal mode transition |
| Initialization | idempotence/sequence | repeated init, invocation before dependencies, bad parameters |
| Error handling | status propagation and bounded wait | fault injection, stuck-ready flag, unexpected reset |
| Optimization | behavior preserved in `-Os` and `-O2` | LTO, alternate compiler, cross-variant ABI |
| API footprint | bytes/stack/cycles per selected workload | worst-case path / IRQ preemption, target instrumentation |

## Coverage policy

- Define testing techniques and justifications per **ASIL B** software safety requirements and ISO 26262-6 method suitability, not by guessed universal numerical thresholds.
- Record statement/branch coverage from host and integration runs. If MC/DC is included, use a tool and qualification/confidence argument that actually measures MC/DC; **gcovr does not by itself establish qualified MC/DC evidence**.
- Use uncovered-code review to classify `unreachable/dead/not-executed`; waivers require documented rationale and approval.
- Verify safety mechanisms with **fault injection** (stuck flags, timing faults, inconsistent readbacks, illegal states); assess detection latency when relevant.
- Mutation testing can assess test effectiveness but is supplementary, not a substitute for requirements-based verification.

## Gate sequence per commit

`format -> compile(target/host) -> static analysis -> MISRA evaluation -> unit -> interface -> integration -> software -> coverage & faults -> resource and timing budget -> consistency/trace -> reviews -> release`.

Each tool produces raw output with: version/command/build digest/target config/result/time; evidence assembler only records hashes and links to these outputs. An AI summary cannot replace failed or missing raw output. Target-dependent gates can remain pending during development but MUST be closed before release.
