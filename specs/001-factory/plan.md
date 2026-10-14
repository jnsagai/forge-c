# Implementation plan for SPEC-001

## Technical approach

1. Represent approved device HSI and safety allocation as versioned JSON plus signed source inventory; resolve unknowns prior to code generation.
2. Store work products as Markdown/JSON with stable IDs; optional ALM export adapter, never making the ALM a hidden source of truth.
3. Design small C-only units: public HAL API, register access module, peripheral finite state machine, platform compiler/config layer, test seam.
4. Use Fabro stages for requirements, architecture, human design gate, code, independent test generation, verification, optimization, evidence, human release gate.
5. Prefer real CLI tooling for compilation, static analysis and results. MCP is an optional connector and must not be part of the minimum trusted evidence chain.
6. Store raw verification logs and source/build hashes in artifact manifests; optimized builds must replay safety and functional verification.
7. Add proof of feasibility on STM32N6 RCC only after validating safety suitability; otherwise pilot as QM and apply ASIL B to a target with approved safety documentation.

## Non-negotiable dependencies

- Upstream SYS/technical/software safety requirement allocation and HSI.
- Hardware manual, datasheet, errata, selected silicon revision, target board.
- Valid tool licenses and confidence/qualification decisions for selected use cases.
- Physical target or accepted hardware integration test plan.
- Authorized reviewers/SCM branch protection and approval roles.

## Phase gates

- G0: HSI/safety inputs approved.
- G1: SWE.1/2 design approved.
- G2: code builds and unit/component/integration/software tests pass.
- G3: verification/footprint/trace evidence and tool confidence complete.
- G4: independent safety/code approval and controlled release.

## Testing the factory itself

- Unit tests for parsing/profile validation, trace completeness, footprint and checks evidence.
- Malicious/noisy model output tests (fake logs, false 'pass', missing files, overstated coverage, guessed register constants).
- Performance regression on actual device after compiler/config updates.
- Repeatability test in pinned clean container/runner with identical SHA256 and tool versions.
