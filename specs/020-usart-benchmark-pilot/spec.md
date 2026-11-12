# Feature Specification: USART benchmark pilot - SWE.1 the benchmark way

**Feature Branch**: `feat/020-usart-benchmark-pilot`

**Created**: 2026-11-12

**Status**: Draft

**Input**: Owner 2026-11-12: "I want to review the things from SWE.1 and use this export as a benchmark for us. Lets
start by implementing a USART by ourselves, but this time, lets mimic the benchmark process". The benchmark is a private
Enterprise Architect export of a real ASPICE SWE.1-SWE.3 UART driver from another programme, plus the transcripts of
its SWE.2/SWE.3 workshops. Only its **process** is mimicked; its content is private and never enters the repository.

## Context

The benchmark organises one UART module (a HAL component and an LL component) around one requirement set. Before any
requirement is written it records the module's inputs (an input document register), its actors and use cases, its
assumptions and its open points. Its software requirements are written at the functional/API level, each with a fixed
set of attributes (status, statement, type, ASIL, CAL, pre-condition, allocated interface, allocated operation,
verification method, test level), grouped by where they come from (use cases, out-of-context IP behaviour, HAL design
constraints, awaiting traceability) and linked to their inputs as traced or derived. Register-level detail and the
concrete negative paths (null pointers, ranges, states, timeouts) appear only at SWE.3, in the unit specifications.

Today the factory writes SWE.1 for drivers at register level, traced to reference-manual pages, one lineage per layer
(LL first, then HAL), with no governance package and no per-requirement attributes beyond source and verification.

Owner decisions taken 2026-11-12 (recorded in the conversation that started this feature):

1. **Brownfield.** ST's delivered code stays frozen: the STM32CubeN6 HAL driver v1.4.0 UART HAL
   (`stm32n6xx_hal_uart.c/.h`, `stm32n6xx_hal_uart_ex.c/.h`, as in example 0012d) and the USART LL
   (`stm32n6xx_ll_usart.h`, as in example 0012c). The mission is to generate the ASPICE artefacts around it.
2. **One module.** "UART" = HAL_UART + LL_USART under one requirement set, not two lineages. The delivered HAL_UART
   does not call LL_USART (it accesses the registers directly), so the two components are parallel APIs over the same
   peripheral - unlike the benchmark, whose HAL is built on its LL.
3. **Functional level, as a pilot.** SWE.1 is written at the functional/API level and register-level content moves to
   SWE.3, selected per work order by a versioned setting. The driver ladder (WWDG, SPI, TIM) keeps its register-level
   SWE.1 unchanged.
4. **Factory-generated inputs.** There are no customer system requirements. The factory generates the governance
   package and checks it itself; no owner sign-off (the owner revoked sign-offs). The owner may add product-context use
   cases at any time.
5. **Scope.** The full delivered public API, but only the functionality comparable with the benchmark (listed in
   FR-009/FR-010); everything else delivered is recorded as out of benchmark scope.
6. **Quality.** SWE.1 keeps the feature 018 two-phase inspection with the same IQ-01..12 / SQ-01..10 criteria.
7. **Comparison.** The pilot ends with a comparison of our SWE.1 against the benchmark's measurable characteristics,
   without copying benchmark text.

Owner 2026-11-12: "what we will do with UART will shape the new way of working with Forge-C workflow". The pilot is
therefore the first use of a **new, general Forge-C way of working**, not a UART special case: every mechanism it adds
(governance package, requirement template, level setting, origin groups, trace links, self-checks, comparison) must be
peripheral- and module-agnostic, and the pilot ends with a way-of-working proposal for all future modules.

This feature covers SWE.1 of the pilot. Aligning SWE.2 and SWE.3 with the benchmark (interfaces as groups, one
sequence diagram per API use case, a unit-specification template with preconditions, inputs, expected result and
failure behaviour, unit attributes, state machines) is a later feature.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The factory prepares the module's inputs before any requirement (Priority: P1)

The owner asks for the UART module. Before the SWE.1 author writes anything, the factory produces the module's
governance package: the register of input documents it will derive from, the actors and use cases of the driver, the
scope list (what is in benchmark scope, what is delivered but out of scope, what the benchmark has that the delivery
lacks), the assumptions and the open points. The factory checks the package itself and refuses to start SWE.1 when
something in scope is not covered.

**Why this priority**: every requirement must trace to an input; without the package the pilot cannot mimic the
benchmark's traceability, and the frozen code would silently become its own specification.

**Independent Test**: prepare the UART order with no model run; the package is produced, its coverage check passes,
and removing one in-scope delivered function from every use case makes the check fail with that function named.

**Acceptance Scenarios**:

1. **Given** the delivered UART code and the module's input documents, **When** the factory prepares the order,
   **Then** it writes a governance package listing every input document with its identity, the actors, the use cases,
   the in-scope / out-of-scope / not-delivered lists, assumptions and open points.
2. **Given** a governance package where an in-scope delivered public function belongs to no use case and no open
   point, **When** the coverage check runs, **Then** preparation stops and names the uncovered function.
3. **Given** the delivered code, **When** the input register is written, **Then** the delivered code is listed only as
   the implementation under analysis and never as a requirement source.
4. **Given** owner-provided product-context use cases, **When** the factory prepares the order, **Then** they are
   included alongside the generated ones and marked as owner-provided.

---

### User Story 2 - SWE.1 written and inspected at the functional level with the benchmark template (Priority: P1)

The line runs SWE.1 for the one-module UART order. The author writes functional/API-level requirements, each with the
full attribute set, in origin groups, linked to the governance inputs as traced, derived or awaiting traceability. The
requirements are inspected with the unchanged feature 018 two-phase criteria and pass the SWE.1 gate. The ladder
drivers are unaffected.

**Why this priority**: this is the requirement set the benchmark comparison and every later phase build on.

**Independent Test**: run SWE.1 for the UART order; check the output against the template, the level rule and the
trace rule, and check that a ladder order prepared with the same factory revision produces exactly the same SWE.1
graph, prompts and checks as before.

**Acceptance Scenarios**:

1. **Given** the prepared UART order, **When** SWE.1 runs, **Then** every requirement has all template attributes,
   belongs to one origin group and has a trace link, a derive link with a rationale, or sits in "awaiting traceability".
2. **Given** a functional-level order, **When** a requirement statement names a register, a bit field or an address,
   **Then** the SWE.1 gate rejects it with the offending requirement and term.
3. **Given** the HAL driver guideline among the inputs, **When** SWE.1 runs, **Then** the design constraints it imposes
   on the HAL (for example no operating-system dependency, no dynamic memory, callbacks, handle-based state) are
   written as design-constraint requirements verified by inspection.
4. **Given** a functional-level order, **When** invalid use is specified, **Then** SWE.1 states it generically
   (parameter validity, operation permitted in the current state, error reporting) and leaves concrete cases to SWE.3.
5. **Given** a ladder order (register-level setting), **When** it is prepared and run on the new factory revision,
   **Then** its SWE.1 graph, prompts, gate checks and outputs are unchanged.
6. **Given** the SWE.1 requirement set, **When** the two-phase inspection runs, **Then** it uses exactly the feature 018
   criteria file, unchanged.

---

### User Story 3 - The owner sees how our SWE.1 compares with the benchmark (Priority: P2)

After the pilot's SWE.1 passes, the factory produces a comparison of its measurable characteristics against the
benchmark's: number of requirements, distribution by type, attribute completeness, distribution by origin group, share
traced / derived / awaiting traceability, verification methods and test levels, scope coverage, and the list of
benchmark capabilities with no delivered equivalent.

**Why this priority**: the point of the pilot is to learn whether the benchmark way of working is better for us; the
comparison is the evidence the owner decides on.

**Independent Test**: generate the comparison from a finished SWE.1; every metric is present for both sides and no
benchmark sentence appears in the output.

**Acceptance Scenarios**:

1. **Given** a passed pilot SWE.1, **When** the comparison is produced, **Then** it reports every metric listed above
   for both sides, side by side.
2. **Given** the benchmark export, **When** its metrics are taken, **Then** only numbers and category names are
   recorded; no benchmark requirement text, identifier list or diagram content enters the repository.

---

### Edge Cases

- **A delivered public function in scope but not described by any input document**: it becomes an open point, not a
  requirement written from the code.
- **An input document and the delivered code disagree** (for example a configuration the reference manual allows but
  the code does not offer): SWE.1 states the requirement from the input; the mismatch is recorded as a finding for the
  later phases, and the code is never changed.
- **A benchmark capability the delivery does not have** (separate configuration setters/getters, DMA linking calls,
  loopback/self-test): recorded in the not-delivered list and in the comparison, never invented as a requirement.
- **An out-of-scope delivered feature used by an in-scope one** (for example receive-to-idle sharing interrupt
  handling): the in-scope behaviour is specified; the out-of-scope feature stays listed as out of scope.
- **The governance check passes but a use case covers nothing in scope**: reported as an open point (unused use case).
- **The owner adds use cases later**: the package changes version; SWE.1 re-runs on the new package as a normal
  re-preparation, never by hand-editing run inputs.
- **The order is too large for one author conversation**: the existing bounded-view mechanisms apply; a context-limit
  refusal is a factory defect handled through CRE, not a reason to drop scope.

## Requirements *(mandatory)*

### Functional Requirements

**Governance package**

- **FR-001**: Before SWE.1 of a functional-level order, the factory MUST generate a governance package for the module:
  input document register, actors, use cases, scope lists, assumptions and open points.
- **FR-002**: The input register MUST identify each input by name, version or revision, and content fingerprint, and
  MUST include for the UART module: the reference-manual USART chapter, the USART memory-map excerpt, the interrupt
  mapping for the USART instances, the datasheet, the HAL driver guideline and the CMSIS device header.
- **FR-003**: The delivered code MUST appear in the package only as "implementation under analysis"; it MUST NOT be a
  permitted source of any requirement.
- **FR-004**: Use cases MUST be generated from the inputs and the delivered public API surface, each naming its actor
  and the in-scope functions it exercises; owner-provided use cases MUST be accepted and marked as such.
- **FR-005**: The factory MUST check that every in-scope delivered public function and every in-scope reference-manual
  feature belongs to at least one use case or one open point, and MUST refuse to start SWE.1 otherwise, naming what is
  uncovered.
- **FR-006**: The package MUST be versioned and fingerprinted; SWE.1 MUST record the package version it used.

**Module and scope**

- **FR-007**: The UART module MUST be one work order covering both delivered components (HAL_UART and LL_USART) under
  one requirement set, with the delivered code frozen.
- **FR-008**: The factory MUST record that the delivered HAL does not use the delivered LL (parallel components over
  one peripheral) as a fact of the module, available to SWE.2.
- **FR-008a**: Because LL_USART is a public API an application may use directly (not an internal layer of the HAL, as
  in the benchmark), SWE.1 MUST contain functional requirements for the services the in-scope LL_USART subset offers,
  at the same functional level (FR-017), in addition to the HAL_UART requirements. The LL code is frozen like the HAL;
  only its artefacts are generated.
- **FR-009**: In scope for HAL_UART: initialisation and de-initialisation with their platform hooks; configuration
  through the initialisation structure (baud rate, word length, stop bits, parity, direction, oversampling); FIFO mode
  and FIFO thresholds; blocking transmit and receive; interrupt-driven transmit, receive and interrupt handling;
  DMA-driven transmit and receive; abort of transmit, receive or both, blocking and interrupt-driven; callback
  registration and unregistration and the transmit/receive complete, half-complete, error and abort-complete
  callbacks; state and error queries.
- **FR-010**: In scope for LL_USART: the functions matching the benchmark's LL units - configuration, enable/disable,
  FIFO, DMA request enable, transmit/receive/error interrupt enable and status, the corresponding flags and flag
  clears, and data transmit/receive. The exact list MUST be generated from this rule, not hand-picked.
- **FR-011**: Everything else delivered (half-duplex, LIN, multiprocessor, RS-485, receive-to-idle and its event
  callbacks, receiver timeout, DMA pause/resume/stop, stop-mode wake-up; LL LIN, smartcard, IrDA, auto-baud, wake-up,
  RS-485 driver enable) MUST be listed as "delivered, out of benchmark scope".
- **FR-012**: Benchmark capabilities with no delivered equivalent MUST be listed as "not delivered" and MUST NOT
  produce requirements.

**SWE.1 template, level and groups (pilot setting)**

- **FR-013**: A versioned per-order setting MUST select the SWE.1 level (functional or register); orders without it
  MUST behave exactly as today (register level).
- **FR-014**: Each functional-level requirement MUST carry: identifier and short title, status, statement, type
  (functional, design constraint, architectural), ASIL and CAL (fixed QM and 0 in this lane), pre-condition, allocated
  interface and allocated operation (not applicable until SWE.2), verification method, and test level.
- **FR-015**: Each requirement MUST belong to exactly one origin group: use-case requirements, out-of-context
  peripheral requirements, HAL design constraints, state behaviour, or awaiting traceability.
- **FR-016**: Each requirement MUST have a trace link to an input statement, or a derive link to an input with a
  written rationale, or MUST be in "awaiting traceability"; the share in "awaiting traceability" MUST be reported.
- **FR-017**: Functional-level statements MUST NOT name registers, bit fields, register addresses or reset values;
  they MAY name public API concepts (functions, states, option constants) of the delivered interface.
- **FR-018**: Invalid use MUST be specified generically at SWE.1 (parameter validity, operation permitted in the current
  state, error reporting); concrete negative cases belong to SWE.3.
- **FR-019**: Design constraints of the HAL driver guideline that apply to the module MUST be written as design
  constraint requirements, verified by inspection.
- **FR-020**: The SWE.1 gate MUST check FR-014 to FR-017 deterministically for functional-level orders and reject with
  the requirement identifier and the failed rule.
- **FR-021**: The register-level evidence the gate requires today at SWE.1 MUST NOT be required for functional-level
  orders; for register-level orders it MUST stay required, unchanged.
- **FR-022**: The SWE.1 requirement set MUST be inspected with the feature 018 two-phase inspection and its criteria
  file unchanged.
- **FR-023**: The requirements exchange file and the traceability matrices MUST include the new attributes and links.

**Comparison**

- **FR-024**: After a passed pilot SWE.1, the factory MUST produce a side-by-side comparison with the benchmark covering:
  requirement count; distribution by type; attribute completeness; distribution by origin group; traced / derived /
  awaiting shares; verification methods and test levels; scope coverage; not-delivered capabilities.
- **FR-025**: Benchmark metrics MUST be taken from the private export outside the repository and recorded as numbers
  and category names only; no benchmark requirement text, identifiers, diagram content or programme names may be
  stored in the repository.

**A new way of working, not a UART special case**

- **FR-027**: Every mechanism of this feature MUST be defined independently of the UART: the governance package, the
  template, the level setting, the origin groups, the trace rules, the gate checks and the comparison MUST take the
  module, its components, its inputs and its scope rule as data, so another peripheral or module can use them with no
  code change. UART-specific facts (files, scope lists, inputs) MUST live only in the UART order's data.
- **FR-028**: The pilot MUST keep a decision log: every rule chosen during the pilot (by the owner or the factory), its
  rationale and the evidence that confirmed or contradicted it.
- **FR-029**: At the end of the pilot's SWE.1, the factory MUST produce a way-of-working proposal for future modules
  from the decision log and the comparison: which rules become the default, which stay per-order settings, and what the
  ladder drivers would need to adopt them.

**Must keep**

- **FR-026**: Every factory change of this feature MUST pass the CRE gate before any deploy; frozen code is never
  edited; the pinned owner-lane adapters, signed controls and the production Line Conductor stay untouched; one GPU
  run at a time; the ladder's SWE.3 stage stays on hold until the owner releases it.

### Key Entities

- **Governance package**: the module's versioned inputs: input register, actors, use cases, scope lists, assumptions,
  open points; fingerprinted; produced by the factory.
- **Input document**: a source requirements may trace to; identity, revision, fingerprint, role (requirement source or
  implementation under analysis).
- **Use case**: actor, goal, in-scope functions exercised; generated or owner-provided.
- **Scope item**: a delivered public function or reference-manual feature with its scope class (in scope, out of
  benchmark scope, not delivered).
- **Open point**: an unresolved question or uncovered item, with the inputs it concerns.
- **Software requirement (functional level)**: the template attributes of FR-014, an origin group and its links.
- **Trace link**: requirement to input, kind traced or derived (with rationale), or the awaiting-traceability marker.
- **Benchmark comparison**: the metrics of FR-024 for both sides.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of in-scope delivered public functions and in-scope reference-manual features are covered by at least
  one use case or open point before SWE.1 starts.
- **SC-002**: 100% of pilot requirements carry every template attribute and exactly one origin group.
- **SC-003**: 0 pilot requirement statements name a register, bit field, address or reset value.
- **SC-004**: 100% of pilot requirements have a trace link, a derive link with rationale, or the awaiting marker; the
  awaiting share is reported (target: at most 10%).
- **SC-005**: 0 pilot requirements cite the delivered code as their source.
- **SC-006**: The pilot SWE.1 passes its gate and the two-phase inspection within the normal rework budget, with no
  owner input.
- **SC-007**: Ladder orders prepared on the new factory revision produce the same SWE.1 workflow and checks as before
  (verified by the existing frozen fingerprints and tests, all unchanged).
- **SC-008**: The comparison reports all FR-024 metrics for both sides, and an automated scan finds no benchmark
  programme or peripheral names in the repository.
- **SC-009**: A second, different peripheral module can be prepared with the governance step, template and checks of
  this feature by supplying only its own data (inputs, components, scope rule) - zero factory code changes.
- **SC-010**: The way-of-working proposal exists at the end of the pilot's SWE.1 and every rule in it cites the
  decision-log entry and evidence behind it.

## Assumptions

- Requirement identifiers keep the factory's existing format (the factory's trace tooling reads it); the module name is
  recorded at document level. The benchmark's module-prefixed identifiers are cosmetic and not required.
- ASIL and CAL are fixed at QM and 0 in this ASPICE-only lane; they are recorded so the template is complete.
- The allocated interface and operation attributes are filled at SWE.2 (later feature); at SWE.1 they read "not
  applicable" or name the whole interface family, as in the benchmark.
- The interrupt mapping input can be extracted from the reference manual and datasheet already held; no new external
  document is needed. If it cannot, it becomes an open point.
- No ST HAL user manual is available offline; the public API surface of the delivered headers is used only to define
  scope and use cases, never as a requirement source.
- The feature 018 SQ-02 criterion ("invalid requests, fault detection") is satisfied at SWE.1 by the generic validity,
  state and error-reporting requirements of FR-018.
- The pilot runs on the owner lane's line like any other order, one GPU run at a time, when the line is idle.
- The ladder's SWE.3 work held on branches 578df4d8 / 751dc57f is the base of this feature branch; deploying this
  feature does not release the ladder's SWE.3 stage.
