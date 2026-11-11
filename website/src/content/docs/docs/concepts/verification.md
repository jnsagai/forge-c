---
title: "Deterministic verification"
description: "AI agents propose work. Deterministic tools establish the recorded check results. Every conclusion is limited by its tool version, inputs, target model, co"
---

AI agents propose work. Deterministic tools establish the recorded check results. Every conclusion is limited by its tool version, inputs, target model, configuration, and assumptions.

## Evidence layers

| Evidence | What to examine |
| --- | --- |
| Compilation | Tool version, flags, target triple, source revision, exit code. |
| Static analysis | Enabled checks, tool coverage, unsupported rules, and dispositions. |
| Unit and integration tests | Requirement/specification traceability, test oracle, results, and environment. |
| Coverage | Instrumented sources, metric definitions, exclusions, and raw results. |
| Footprint | Object or linked-image scope, compiler options, memory and stack assumptions. |
| Simulator or hardware | Model/board identity, supported behavior, executable, and limitations. |
| Formal tools | Modeled assumptions, bounds, unsupported constructs, and result evidence. |

## Keep host and target results distinct

A passing host test does not prove silicon behavior. A register simulation is evidence about the recorded model, not arbitrary MCU timing. Object-level size is not a complete linked firmware footprint.

The project includes target simulation and formal-verifier integrations beyond the early host baseline. Availability in source does not establish that any particular work order executed them successfully. Inspect that order's actual package.

## MISRA and safety claims

The Cppcheck MISRA addon covers a subset. Forge-C does not claim full MISRA compliance. Licensed normative texts are not redistributed by this site. No tool, including Forge-C, is qualified by the fact that a factory gate passes.

Read the [MISRA coverage note](https://github.com/jnsagai/forge-c/blob/main/docs/OSS-MISRA-COVERAGE.md), [toolchain policy](https://github.com/jnsagai/forge-c/blob/main/docs/TOOLCHAIN.md), and [assurance guide](/docs/guides/assurance/) alongside the run-specific limitations.
