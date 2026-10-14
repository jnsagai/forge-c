# Forge-C — OSS project charter

The implementation baseline is **[OSS-V0.1.md](OSS-V0.1.md)**. All orchestration, inferencing, compilers and verifiers are open-source, used locally; no paid APIs or proprietary ALM/analysis software is allowed in this first release.

## Mission

Generate compact, deterministic, maintainable, memory-efficient HAL/LLD C modules from approved hardware and software safety contracts. Each generated candidate must be accompanied by requirements, architecture, unit design, tests, static/MISRA assessment (scoped), coverage, footprint, stack and timing analyses, traceability, known deviations, and human-gated release evidence. The factory organizes ASPICE SWE.1–SWE.6 workproducts and ASIL B-related software activities; it cannot invent allocated ASIL or declare itself qualified.

## Boundaries

1. Source documents (HSI, part/variant/errata, TSR/SSR safety allocation) require human approval before generator execution.
2. Generated firmware uses freestanding C, no heap, and target-specific policies for volatile MMIO, register semantics, preemption and interrupts.
3. Distinguish host mock tests, model/simulation tests, target-board measurements and actual safety verification.
4. Tool output plus original hashes, baselines and reviewers' identities determine the evidence status; agent-written prose is only a proposal.
5. Footprint optimization is bounded by behavior, stack/timing constraints, coding policy and safety evidence; never auto-accept deviations.
6. Production release requires an independent safety review and organization-owned authenticated SCM/ALM approvals.

## Milestone artifact

A working **generic RCC-style C driver** demonstrates native Clang build, unit assertions, and LLVM branch/MC/DC report. The target/ASIL profile (`profiles/stm32n6-rcc-pilot.json`) intentionally remains blocked. See `docs/PILOT-GENERIC-RCC.md`, `docs/OSS-SETUP.md` and `docs/OSS-STATUS.md`.
