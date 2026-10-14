# Forge-C open-source roadmap

**M0, already implemented in v0.1:** standalone C generic RCC demo, Clang/CMake/Ninja build, CTest, LLVM source-based/MC/DC host coverage, SHA-256 log manifest, optimization build comparison and Python fail-closed evidence gates. This is not target or safety evidence.

**M1, next:** install and pin Fabro MIT + Ollama CLI MIT + Apache-2.0 Qwen3 8B; prove local execution of `workflows/oss-bootstrap.fabro` with no external API; test prompt-to-code quality on controlled changes. Enforce deterministic shell allowlist and repository permissions.

**M2:** install Cppcheck MISRA subset and Clang Static Analyzer; create machine-readable covered/uncovered rule matrix, exception review and raw logs. Add CBMC property harnesses and Frama-C Eva runs for selected high-risk bit/offset code.

**M3:** replace basic `assert` tests with pinned Unity/CMock, add fault injection and bus-event logging; integrate Renode/HwSim only after agreeing exact peripheral register semantics. Obtain SWE.4/5/6 distinct verification evidence.

**M4:** select exact MCU/board and software safety allocation; pin Arm GCC, vendor HSI, errata and build flags; run target compile, linker-map analysis, stack upper-bound analysis and measured hardware cycles under controlled configurations.

**M5:** complete applicable ISO 26262 and ASPICE workproduct review, tool-confidence assessment, independence/confirmation plan, deviations and safety case interfaces. The human release gate remains mandatory. Commercial tool dependencies stay excluded from this version.

**Do not state a calendar commitment based only on this roadmap**; integration duration depends on silicon support, modeling, verification obligations and available safety reviewers.
