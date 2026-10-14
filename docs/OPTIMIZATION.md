# Ultra-lean C Optimization Policy

## Goal hierarchy

**1. Correct behavior and safety integrity** → **2. Bounded worst-case execution and resource use** → **3. footprint minimization** → **4. throughput**.

The factory compares only candidates that preserve the approved functional and safety requirements, HSI/errata constraints and all verification gates.

## Metrics (all per target, configuration and version)

| Metric | Source | Contract |
|---|---|---|
| Loaded Flash (bytes) | Linker map + ELF sections | `.text + .rodata + initializers loaded from ROM + vector/boot contribution` according to target linker memory layout |
| Static RAM (bytes) | Linker map + ELF | `.data + .bss + retained / noinit` according to linker and actual allocation |
| Peak stack (bytes) | `-fstack-usage` + callgraph + ISR/preemption nesting + measurement | Proof of upper bound or documented conservative estimate, not `.su` alone |
| Worst-case cycles per API | Hardware DWT/timer/trace, workload & statistical/analytical characterization | API-specific upper bound or justified margin with measurement limitations |
| BSS vs driver global memory | ELF symbol report (`nm`, `readelf`) | Zero or approved bounded globals; separate test-only overhead |
| ROM/CPU Pareto frontier | locked compiler and binary comparison | Preserve behavior, coverage, function/interrupt contract |
| Complexity and timing | static measurements, hardware traces, loop bounds | No unbounded loops, critical-section timing cap |

The automated `footprint_gate.py` uses **explicitly precomputed section bytes**, not a generic sum of every ELF section; reporter must normalize target-specific load/run memory layouts before emitting metrics. It does **not** independently establish a whole-system WCET guarantee.

## Optimization search sequence

1. Compile a **readable reference implementation**, preserving all safety checks. Baseline complete verification.
2. Obtain disassembly, map file, symbol sizes, stack reports and target cycle trace for defined use cases.
3. Generate up to 2–3 constrained candidates per iteration: structural simplification, inlining strategy, tables vs branching, compile-time specializations, `-Os` / optimized compiler settings, optional LTO.
4. Build each in an isolated reproducible environment; rerun all required tests, static analysis, sanitizer host builds, compatibility tests and assigned fault tests.
5. Reject any candidate violating a hard budget, ASIL mechanism, deterministic timing or verification evidence.
6. Record alternatives with `{commit, compiler flags, memory map, budget deltas, behavior proof, risk assessment, reviewer}`.
7. Choose a Pareto-efficient implementation or retain the baseline. Stop after 3 failed repair cycles and escalate issue, never silently loosen budgets.

## Code-level rules

- Favor typed `static inline` API accessors when a compiled footprint benchmark demonstrates benefit; never use a macro with multiple evaluation side effects.
- Avoid heap/recursion/VLA/excessive buffer copies, nonessential tables and unused dependencies; keep structs externally stable and alignment-correct.
- Prefer thin low-level drivers with documented preconditions and compile-time supported feature sets; no dynamic dispatch unless required.
- Extract or generate register masks from independently validated SVD/manual/errata; masks/shifts must preserve reserved bits and obey write-only / W1C / read-to-clear semantics.
- Shared read-modify-write and ISR interactions need explicit atomicity, critical section and ordering requirements; unsafe optimization is rejected.
- Poll loops MUST have bounded timeout or a formally justified hardware guarantee and safe failure response; clocks/reset handshakes verified.
- Consider compiler-specific `volatile` behavior, aliasing, alignment and CPU memory ordering. Avoid depending on unspecified/undefined behavior.
- Use `-ffunction-sections -fdata-sections`, linker GC and optionally LTO only after demonstrating no retained objects/startup hooks/diagnostics are accidentally dropped.
- Avoid `-Ofast` and undocumented flags for safety builds; compare target compiler outputs and safety behavior before accepting any optimization.

## Standard build profiles

- `BASELINE`: `-O0` or `-Og` used **only** for reference/debug and diagnostic tests, not as the fairness comparator unless defined as such.
- `RELEASE_SIZE`: `-Os` with compiler, CPU/FPU ABI, libs, LTO and linker script **fully version pinned**.
- `RELEASE_SPEED`: `-O2` benchmark profile with identical external conditions.
- `DIAGNOSTIC`: host Clang/GCC with strict warnings + ASan/UBSan, static analyzers, mocks, instrumentation.
- `SECOND_COMPILER`: optionally armclang/Clang vs GCC, checking behavioral divergence; must use tool-confidence plan.

Size budget and API-cycle limits are **engineering decisions** owned by project stakeholders. Example constraints in a pilot are illustrative placeholders until real system allocation.

## Measurement examples (not release measurements)

```bash
arm-none-eabi-size -A build/driver.elf
arm-none-eabi-nm --size-sort --print-size build/driver.elf
arm-none-eabi-objdump -d build/driver.elf > evidence/disassembly.txt
# GCC flag when compiling target C objects: -fstack-usage
# Linker: -Wl,-Map=build/driver.map
```

## Mandatory rejection examples

- Removing a watchdog/clock-ready timeout to save ROM.
- Changing a volatile register read into a cached local without safe equivalence proof.
- Changing an atomic / interrupt-protected RMW into unprotected access.
- Treating simulated Renode cycles as measured target timing.
- Failing to include upper-level interrupt nesting and callee stack when claiming stack bound.
- Automatically accepting MISRA deviations because a code-size gain was measured.
