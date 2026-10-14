# Forge-C v0.1 — OSS toolchain policy

The **sole supported v0.1 solution** uses open-source development tools and locally served open-source model weights, without paid APIs or proprietary software dependencies. See [OSS-V0.1.md](OSS-V0.1.md) and [OSS-SETUP.md](OSS-SETUP.md) for an executable breakdown and install instructions.

Core: Fabro, Ollama CLI/server, Qwen3 8B Apache-2.0 weights, CMake, Ninja, Clang, GCC/Arm GCC, Cppcheck with partial MISRA C addon, LLVM-Cov, Python/Git, Unity/CMock (deployment phase), Renode/HwSim (deployment phase). CBMC and Frama-C's open-source distribution provide deeper verification for critical routines.

The first runnable demo is a generic host RCC-style driver; it has no chip-specific addresses or safety allocation. The production profile validation is intentionally locked. The correct user-facing description is **ASIL B-oriented engineering workproducts**, never 'qualified/approved ASIL B' without project-specific safety evidence and authorized signoff.

Rule standards and MCU datasheets may have proprietary terms independent of the OSS toolchain. The MISRA C 2012 addon is not full MISRA C conformance, and no purchased rules text is redistributed. Closed-source commercial integrations from the previous architecture are excluded from this version.

This package has separate **host/demo** and **candidate/release** gates. An AI agent cannot mark a checked result PASS without a real tool log with validated file hash, and cannot approve an ISO 26262 workproduct. Verification tools require project-specific tool confidence assessment (TI/TD/TCL) and mitigation/qualification as applicable.
