# Specification: Forge-C factory (SPEC-001)

**Owner:** Engineering / Safety Authority. **Status:** DRAFT — requirements require review.

## Actors
- **Engineering owner:** declares target, reference sources, architecture and budget.
- **Functional Safety Manager / qualified reviewer:** approves safety allocations, verification approach, deviations and release gates.
- **Fabro agent worker:** generates change proposals and evidence indexes.
- **Independent verifier:** reviews safety-sensitive source, tests and trace consistency.

## Functional requirements

| ID | Requirement | Acceptance evidence |
|---|---|---|
| FR-001 | Import baseline of device variant, hardware reference and errata with provenance | versioned HSI inventory + human acceptance |
| FR-002 | Reject unknown hardware fields, unsafe default guesses and incompatible variants | negative intake tests |
| FR-003 | Generate SWE requirements from approved upstream sources, preserving identifiers and bidirectional links | requirements baseline and link report |
| FR-004 | Generate reviewed static/dynamic architecture with ISR, clock, reset, concurrency and error behavior | review record and diagrams |
| FR-005 | Generate C `.c/.h` HAL/LLD units consistent with detailed design and constraints | toolchain compile + design/code trace |
| FR-006 | Generate/execute host unit tests including register side-effect simulation and fault injection | raw test results and coverage scope |
| FR-007 | Generate/execute component and integration verification to approved architecture | integration sequence and results |
| FR-008 | Generate/execute requirements-based software verification including nonfunctional tests | software verification result links |
| FR-009 | Perform static analysis and MISRA scope evaluation; record all deviations and limitations | raw tool logs + approved exceptions |
| FR-010 | Capture Flash, static RAM, stack and target cycle metrics reproducibly | ELF/linker + hardware measurement metadata |
| FR-011 | Search bounded optimization candidates without weakening checks or acceptance | signed Pareto comparison and regression |
| FR-012 | Enforce deterministic fail-closed safety/quality gates and bounded repair loops | negative quality-gate tests |
| FR-013 | Produce reviewed outputs supporting ASPICE 4.0 SWE.1–SWE.6 indicators | evidence ledger / gap matrix |
| FR-014 | Produce ISO 26262:2018 Part 6/8 safety-related evidence with tool-confidence decisions | safety evidence and review approval |
| FR-015 | Export versioned source, builds, work products, trace graph and hashes in release package | authenticated release record |
| FR-016 | Separate human approval at design intake and final safety release from agent autonomy | workflow gate / SCM approval history |
| FR-017 | Configure agent models via provider-agnostic Fabro, without requiring a specific paid MCP | integration tests with CLI providers |
| FR-018 | Track engineering cost, run duration, failed iterations and per-driver reuse | non-normative observability report |

## Nonfunctional requirements

| ID | Requirement | Acceptance |
|---|---|---|
| NFR-001 | Target binaries have no dynamic heap usage unless explicit safety review grants a variant exception | binary source/analyzer review + HIL |
| NFR-002 | All target busy waits bounded by verified timeouts or approved proof | static and fault checks |
| NFR-003 | All release gates must be reproducible and fail when inputs are missing | self-tests |
| NFR-004 | All budgets project-specific and baselined before optimization | signed profile / change history |
| NFR-005 | Do not transfer restricted source/manuals to unapproved cloud agents | sandbox/network policy and audit |
| NFR-006 | Keep toolchains, source commits, logs and approvals immutable and verifiable | content digests and SCM protection |
| NFR-007 | Generated code remains readable and reviewable; optimization alternatives documented | independent source review |
| NFR-008 | Tool confidence strategy and limitations are explicit; no false certification assertions | signed tool register and safety review |

## User stories

**US-001:** As an embedded architect, I can select a specific MCU/HSI and obtain a proposed, traceable HAL driver, tests and design without supplying undocumented register constants.

**US-002:** As a safety engineer, I can see which software safety requirements are covered and which evidence is missing, and prevent release until missing items are addressed.

**US-003:** As a memory footprint owner, I can set Flash/RAM/stack/cycle budgets and compare independently verified candidate implementations.

**US-004:** As a factory operator, I can approve a design, leave an overnight run to generate candidate code and verification logs, and return to a reviewable release candidate—not an unattended release.

## Out of scope

Safety goal allocation, HARA, full ISO 26262 lifecycle organization, hardware qualification, product certification and unconstrained release autonomy.
