# Bootstrap validation (Forge-C v0.1 OSS)

## Verified in the scaffold build environment

- CMake+Ninja with Clang 17 compiled generic RCC-style C implementation and C test harness with `-Wall -Wextra -Werror` and relevant strict warnings.
- CTest native test suite ran successfully; LLVM `-fprofile-instr-generate -fcoverage-mapping -fcoverage-mcdc` produced raw profile, merged profile and `llvm-cov report --show-mcdc-summary`/`show --show-mcdc`.
- On this specific small host demo: region, function, line, branch and MC/DC metrics were all reported at 100%. These percentages are limited to **the tested, instrumented C source in the host environment** and cannot be used to justify ASIL B readiness.
- Host `-Os`, `-O2`, `-Oz` built and passed CTest with section-size and GCC/Clang `.su` instrumentation; results are host code-size comparisons, **not target Flash/stack bounds**.
- Clang Static Analyzer ran on the generic host RCC example with no diagnostics, using the logged compiler version. This is not a MISRA completeness claim.
- 16 Python automated tests of the original safety/evidence gate passed.
- Both new OSS workflow files are Graphviz parseable (`dot -Tsvg`). This is **not** a Fabro runtime validation.

## Not verified here

- Local Fabro runtime or Qwen tool calling; no Fabro/Ollama installed on build machine.
- Cppcheck MISRA checking, CBMC or Frama-C proof, Unity/CMock campaign, Arm GCC target compile, Renode MCU model, actual MCU footprint/stack/timing, HIL, independent reviewers, ASIL allocation or tool qualification.

Full current status: `OSS-STATUS.md`. A demo PASS does not cause release gate PASS.
