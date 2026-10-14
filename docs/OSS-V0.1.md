# Forge-C OSS v0.1 — Implementation Specification

**Version:** 0.1 / 14 October 2026  
**Scope:** 100% open-source implementation tools and locally served open-source model weights.  
**Safety claim:** NONE. This is a reference software factory scaffold, not a qualified ISO 26262 development environment.  
**Status:** Host LLVM demo implemented/tested; Fabro and advanced analyzers are specified/integration-ready but not exercised in this distribution.

## Business and engineering objective

Create deterministic, minimal-memory, bounded-time C HAL and low-level driver code with linked Automotive SPICE PAM 4.0 SWE.1–SWE.6 workproducts and *ASIL B-oriented* safety records. Correctness, safety contracts and timing bounds are hard constraints; footprint optimization is performed inside the set of designs satisfying them. Never use generated justifications as evidence of execution.

## Tool selection and open-source policy

| Layer | Tool (software / model licenses to validate at deployment) | v0.1 status |
|---|---|---|
| Orchestrator | Fabro (MIT), DOT workflow | Workflow scaffold, no Fabro runtime validation here |
| Local LLM | Ollama CLI/server (MIT source repository), `qwen3:8b` (Apache-2.0 model weights) | Configuration example; user installs and tests |
| Compilation | GCC / Clang, CMake + Ninja, Arm GNU Toolchain | Native demonstration Clang/CMake/Ninja executed; arm-none-eabi not available here |
| MISRA C checking | Open-source Cppcheck MISRA addon | Adapter script; **partial rule coverage only**; requires documented licensed MISRA edition |
| General static checking | Clang Static Analyzer + Cppcheck | Clang analyzer executed; combined adapter requires Cppcheck installation |
| Verification / proofs | CBMC, Frama-C Eva/WP | Optional targeted advanced checks; not automatically qualified |
| Host tests | C `assert` bootstrap; Unity + CMock for real unit campaigns | Bootstrap tests exercised; Unity/CMock planned, not bundled |
| Structural coverage | LLVM-Cov + llvm-profdata | Native region / branch / MC/DC instrumented demo exercised |
| Alternate coverage | GCC gcov / gcovr | Adapter roadmap; not implemented |
| Peripheral simulation | Mock register block and optionally Renode/HwSim | Generic memory-mapped register example only; no MCU model |
| Memory budget | binutils/GNU size/map, `-fstack-usage`, target timing on hardware | Existing fail-closed gates; not target measured |
| Traceability | JSON / Git / Python gates | Existing gate tests executed |
| Evidence & documentation | Markdown + checksummed raw logs, MkDocs optionally | Templates and evidence manifest present |
| CI (later) | Forgejo + Woodpecker | Optional; not deployed |

Not in the solution: proprietary AI services, paid APIs, CodeQL service, Coverity, Parasoft, Codebeamer, Enterprise Architect, commercial MC/DC analyzers or license-gated design tools. **MISRA C and ISO 26262 standard publications are themselves proprietary and are NOT included.** Obtaining a compliant copy and selecting the project-specific rules is an organizational requirement; open-source checking software alone is insufficient.

## Architecture / trust boundary

```text
Approved upstream requirements / HSI / safety allocation (read-only human baseline)
                             |
                    Fabro (MIT) in isolated workspace
                             |
               Qwen3 8B (local Ollama, no paid API)
             /      |          |             \
            v       v          v              v
          SWE.1    SWE.2      SWE.3       SWE.4–SWE.6
          reqs    architecture   C/H         test design
                            |               |
                       CMake/Clang/GCC  CTest/Unity/CMock
                            |               |
                     Static / MISRA      LLVM coverage
                       / CBMC              / fault tests
                            \               /
                        immutable evidence + hashes
                                  |
                       footprint + trace + safety gates
                                  |
                   candidate proposal (NOT ASIL B release)
                                  |
                     independent human verification,
                     hardware tests and release approval
```

All LLM edits are untrusted proposals. Agents cannot approve baselines, waive violations, invent device registers, bypass tests, or authorize release. Tools run under a least-privilege user; physical flashing is not available to the unattended agent by default.

## Design for very low footprint

Budget on **target** ELF/map/disassembly, not host binary: total loadable Flash, `.data + .bss` and other RAM allocations, worst-case stack across call paths and interrupts, CPU cycles and worst-case interrupt latency. Prefer no heap, no RTTI/C++ runtime, no recursion, no unbounded loops, no copying opaque structs and no unnecessarily generic runtime abstraction. Compare `-Os`, `-O2` and, where justified, `-Oz` on pinned toolchains. Never treat the smallest unverified build as the winner.

**Optimization gate**: all existing functional tests pass, target ABI and compiler warnings pass, MISRA status does not regress without approved deviation, static findings are resolved or reviewed, coverage does not regress, target RAM/Flash/stack/cycle budgets pass, and the safety interface contracts remain satisfied.

## Two distinct execution modes

### A. Local bring-up demo (v0.1 runnable)

`./scripts/run_oss_demo.sh` builds an **invented RCC-style peripheral** on the Linux host. It tests argument/mask checking, bit changes and simulated reset-register writes, then generates LLVM region/branch/MC/DC coverage and a SHA-256 evidence manifest. Only standard-C assertions are used to keep the first bring-up offline and dependency-free.

This mode proves the wiring of Clang/CMake/CTest/LLVM coverage—not the MCU, ISO 26262, MISRA compliance or actual driver timing. The demo's 100% MC/DC report (when achieved) applies **only to instrumented host C code**, not to target integration or the safety application.

### B. Real safety-oriented candidate workflow (existing strict gates)

The prior `workflows/forge-c.fabro` requires a **reviewed** device profile, HSI, allocated safety requirements, documented toolchain and approved resource budgets. `tools/quality_gate.py` rejects unapproved or missing data, unreviewed trace links, fake logs, missing target cycles/stack proof on release, and required approvals. A separate `workflows/release.fabro` is a human-gated release candidate assessment—not a replacement for SCM/safety authorization.

## ASPICE SWE.1–SWE.6 and safety artifacts

| Process | Generated and independently checked outputs | Current completeness |
|---|---|---|
| SWE.1 | SW requirements, constraints, analyses, allocated safety links | template only |
| SWE.2 | Architecture, register semantics, HSI, dynamic behavior, resource assumptions | template only |
| SWE.3 | Unit detailed design, C/H source, build configuration and evidence | **generic RCC sample code** |
| SWE.4 | Unit verification measures/results, static/MISRA findings, structural coverage | **host demo tests and LLVM coverage only** |
| SWE.5 | Component verification, integration sequence and verification results | template only |
| SWE.6 | Software requirements-based test design and verified integrated software results | template only |
| ASIL B | Software safety requirements, failure/dependency analyses, tool-confidence assessment, deviations, safety review and release evidence | templates and gated status; NO certification claim |

The workproduct inventory must be audited against the organization's licensed editions of ISO 26262 and ASPICE plus tailoring decisions. ASPICE workproducts alone do not establish capability level, and no universal 100% MC/DC requirement is asserted for ASIL B. Include SUP.1, SUP.8–10, MAN.3 and confirmation/verification processes as applicable.

## Phase plan

| Phase | Deliverable | Exit criterion |
|---|---|---|
| **0** | Host generic RCC C, CMake, Clang, test and MC/DC report | Running script produces hashed logs and tests pass (implemented here) |
| **1** | Fabro + Ollama Qwen offline provider + strict agent prompts | Same demo produced by Fabro without external model APIs; per-stage logs |
| **2** | Cppcheck MISRA subset + Clang analyzer + CBMC assertions | Unchecked rules documented; analyzer output stored as verifiable evidence |
| **3** | Unity/CMock + fault injection + Renode/HwSim peripheral model | Test trace and independent negative cases demonstrate expected behavior |
| **4** | Target toolchain STM32N6 or another approved MCU, measured Flash/RAM/stack | MCU reference manuals/errata pinned; target build and hardware tests pass |
| **5** | Complete SWE/ISO safety evidence and human-authorized release controls | Independent review, tool-confidence assessment, signed organizational approvals |

## Measurable acceptance criteria

- Technical pipeline refuses to report safety success if source files, test outputs or hashes are missing.
- All API operations have stable error handling, reviewed timing/side effects, bounded memory usage and safety mapping.
- Verifiable raw coverage output and a clear **host vs. target** provenance flag.
- Rule-by-rule MISRA assessment classifies `automated`, `manual`, `deviation`, `not_applicable`, `unassessed` and references the project's licensed rule baseline. Never claim full MISRA compliance from Cppcheck alone.
- `-fstack-usage` values are not claimed to be complete when indirect calls or interrupts are not accounted for.
- Release candidate cannot be promoted to safety release without approved HSI/TSR allocation, actual target measurements, independent checks and tool-confidence evaluation.

## Primary documentation

- Fabro source/LICENSE: https://github.com/fabro-sh/fabro
- Fabro local providers: https://github.com/fabro-sh/fabro/blob/main/docs/public/core-concepts/models.mdx
- Cppcheck MISRA addon limitations: https://github.com/cppcheck-opensource/cppcheck/blob/main/man/manual.md
- LLVM-Cov MC/DC: https://clang.llvm.org/docs/SourceBasedCodeCoverage.html
- Qwen3 8B model: https://ollama.com/library/qwen3:8b
- CBMC: https://github.com/diffblue/cbmc
- Frama-C analyses: https://www.frama-c.com/html/kernel-plugin.html
- Unity/CMock: https://github.com/ThrowTheSwitch
- Eclipse S-CORE open-source reference: https://github.com/eclipse-score/coverage_tool

## Threat model and limits of evidence capture

The v0.1 SHA-256 manifest detects accidental or post-generation changes only when the manifest itself is trusted. An agent that can edit both log and manifest can forge a self-consistent result. Hence no v0.1 JSON/MD/shell output is self-authenticating safety evidence. Production deployment must isolate the agent write workspace from verification runners, pin tool binaries/images and input commits, sign or attest evidence with runner-controlled keys, keep append-only immutable records, and require independently authenticated review.
