# Feature Specification: Peripheral onboarding as a factory pipeline stage

**Feature Branch**: `feat/016-peripheral-onboarding`

**Created**: 2026-10-27

**Status**: Draft

**Input**: Owner request 2026-10-27: "all the work that you are doing to prepare the environment for the run, it should
be part of the factory pipeline as well right? I mean, if we plan to run it on qwen, and we give only the datasheet and
hardware manual as input plus the code, we need to have some preparation before running for ASPICE artifacts work".
Owner choice (2026-10-27): specify this now and use the remaining ST HAL drivers of feature 015 T065 (GPIO, SPI,
USART, TIM) as its acceptance test, instead of onboarding them by hand.

## Context

Before a driver delivery can go through SWE.1-SWE.6 today, the implementation engineer (Claude Code) prepares it by
hand. For each peripheral and each driver layer this means:

- a peripheral profile: register prefix, instance, base address and memory-map page, header and function-name
  conventions, whether the driver waits on a time base, which functions it calls but that are not delivered (and the
  value a test environment returns for them), which concrete instance the driver compares its handle against, and
  about 30 prompt texts plus driver-style overlays;
- a work order: the inputs, the delivery file map, the configured framework modules, the scope and the budgets;
- the reference-manual chapter and memory-map conversion, with a hash manifest;
- a behavioural simulation model of the peripheral and its platform description;
- facts the host and target test harnesses need.

Feature 015 showed the cost. Each new driver style (ST LL, then ST HAL) needed new hand-written texts and several
factory fixes found only during live runs. Example: the CRC HAL run of 2026-10-27 worked around an architecture-view
check that still expected an LL component, by naming the LL in a note.

A factory that receives only the owner inputs cannot do this preparation today. It does not matter whether a local
model or the current author/inspector pair runs the factory.

## Goal

From the owner inputs alone, the factory produces an **onboarding package** before SWE.1. The owner inputs are:

- the datasheet;
- the reference manual chapter and memory map;
- the delivered code, with its licence and provenance;
- the owner's scope.

Most of the package is derived deterministically, with its source. The rest is authored and checked. The owner
approves the package, and only then does the ASPICE work start from it.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Deterministic onboarding facts from the inputs (Priority: P1)

The owner submits a work order with only the owner inputs and a scope that names the driver functions. Before any AI
role runs, the factory derives the facts that follow from the inputs. Each fact is recorded with its value and its
source location: a file and line, or a document and page.

The facts:

- the peripheral instance and its base address;
- the register prefix and the register/field index;
- the driver's header and function-name conventions;
- whether and how the driver waits (time base, timeout constants);
- the functions the driver calls but that are not delivered;
- the instances the driver compares its handle against;
- the framework modules and files the delivered code needs to build.

A fact that cannot be derived is marked NOT_DERIVED and named as a gap; it is never guessed. A fact on which two
sources disagree is marked CONFLICT, with both sources.

**Why this priority**: These facts are what the hand-written profiles hold today. Every later stage depends on them,
and none of them needs a model. On its own it removes most of the hand preparation and makes it reproducible.

**Independent Test**: Run the derivation on the feature 015 HAL work orders and on the eight existing onboarded
combinations (RCC LL/HAL, IWDG, and CRC, GPIO, SPI, USART and TIM LL, plus CRC HAL). Compare each derived fact with
the hand-written value. Expected: every hand-written derivable fact is reproduced, and every difference is a recorded
CONFLICT or a documented hand error.

**Acceptance Scenarios**:

1. **Given** the ST USART HAL delivery and the RM0486 USART chapter and memory map, **When** onboarding runs,
   **Then** the package names the following, each with its source:
   - instance USART1 at 0x52001000;
   - the HAL time base HAL_GetTick;
   - the undelivered kernel-clock function HAL_RCCEx_GetPeriphCLKFreq;
   - the instance comparison against USART1;
   - the framework modules UART, DMA and RCC.
2. **Given** a delivery whose code and memory map disagree on the base address, **When** onboarding runs, **Then** the
   base address is CONFLICT with both sources, and the package cannot be approved until the owner resolves it.
3. **Given** a scope that names no instance and code that supports several, **When** onboarding runs, **Then** the
   instance is NOT_DERIVED and the package lists it as an owner question.
4. **Given** onboarding has run, **When** the derivation is repeated on the same inputs, **Then** the facts and the
   package hash are identical, and no model call is recorded.

---

### User Story 2 - Owner approval gates the ASPICE work (Priority: P1)

The owner receives one onboarding summary. It lists:

- the derived facts, with their sources;
- the authored items, with their gate results and inspection verdicts;
- the test-environment assumptions the owner must confirm, for example the kernel clock frequency a host test assumes;
- every gap.

The owner approves the package, or rejects it with a reason, in an owner-decision record. SWE.1 cannot start for a
work order whose onboarding package is not approved. Any change to an input invalidates the approval.

**Why this priority**: Onboarding facts become the ground truth of every later work product. The owner's authority
over the inputs must extend to them, as it already does for the scope and the safety documents.

**Independent Test**: Try to start SWE.1 on a work order whose package is not approved, then on one whose package
was approved before an input file changed. Both must be refused, with the reason recorded. Approve, then start:
accepted.

**Acceptance Scenarios**:

1. **Given** an onboarding package with an open CONFLICT, **When** the owner tries to approve it, **Then** the
   approval is refused until the conflict has an owner resolution.
2. **Given** an approved package, **When** a delivered file's hash changes, **Then** the approval is void and the
   work order returns to onboarding.
3. **Given** an approved package, **When** the work order runs, **Then** every SWE work product's evidence records
   the package hash it was produced from.

---

### User Story 3 - Prompts built from the package, not hand-written per peripheral (Priority: P2)

The SWE.1-SWE.6 instructions for authors, inspectors and test authors are composed from the approved package. A new
peripheral or driver style needs no hand-written prompt text. Where a role needs domain content that cannot be
derived, an AI role authors it during onboarding from the reference manual and the delivered code. Examples: a worked
requirement example, an expected value for a target test scenario.

Each authored text passes deterministic checks before use. It names only registers and fields that exist in the
reference-manual index, and only functions and types the delivered code declares. An independent inspector also
reviews it.

**Why this priority**: The hand-written texts and overlays are the main per-peripheral cost, and the main source of
leftover text from another peripheral or layer (an LL include in a HAL prompt, an oscillator example in a USART
prompt). The ASPICE work cannot run unattended for a new peripheral without removing them.

**Independent Test**: Build the SWE.1-SWE.6 instructions for the four acceptance drivers from their packages. Scan
them for identifiers of another peripheral or layer: none. Check that every register, field and function they name
exists in that driver's package.

**Acceptance Scenarios**:

1. **Given** the approved package of the ST GPIO HAL, **When** the instructions are built, **Then** they name only
   GPIO registers and fields and the delivered HAL_GPIO functions and types. No text in them was written by hand for
   GPIO.
2. **Given** an authored requirement example that names a field absent from the reference-manual index, **When** it
   is checked, **Then** it fails and is re-authored within a bounded number of attempts. Otherwise it becomes a gap.
3. **Given** a peripheral onboarded by hand before this feature, **When** its work orders run, **Then** they behave as
   before. Its hand-written texts stay valid until the owner chooses to migrate it.

---

### User Story 4 - Authored simulation model behind a gate (Priority: P3)

When no behavioural simulation model exists for the peripheral, an AI role authors one from the reference-manual
chapter during onboarding. Deterministic gates check it:

- it loads in the simulator;
- every register's reset value matches the reference-manual register tables;
- its access types (read-only, write-1-to-clear, and so on) match those tables;
- a smoke program built from the delivered code runs on it to the end.

An independent inspector reviews the modelled behaviour against the chapter. The model and its limits, meaning the
behaviour it does not model, become part of the package. When a model already exists, onboarding re-runs the same
gates on it and records the result.

**Why this priority**: The model is the only onboarding item that truly needs authoring. The acceptance drivers
already have hand-written models from feature 015, so this story is tested separately, on a held-out peripheral.

**Independent Test**: Hide one existing hand-written model from the author, for example CRC. Let onboarding author a
model from RM0486 chapter 26. Expected: it passes the gates, and the existing target tests of that peripheral pass on
it.

**Acceptance Scenarios**:

1. **Given** a peripheral without a model, **When** onboarding runs, **Then** a model is authored, gated and
   inspected within bounded attempts, or the package records MODEL_MISSING as a gap. Without a model, the target
   (SWE.5/SWE.6) evidence of that work order is BLOCKED; it is never skipped silently.
2. **Given** an authored model whose reset value for a register differs from the reference-manual table, **When** the
   gate runs, **Then** the model fails with that register named.

---

### User Story 5 - The four ST HAL drivers end to end (Priority: P2)

The ST HAL drivers for GPIO, SPI, USART and TIM are onboarded by the pipeline from their owner inputs. After owner
approval, each runs SWE.1-SWE.6 to a release package: READY_FOR_OFFLINE_REVIEW, or BLOCKED with every gap named. No
per-driver text is written by hand.

**Why this priority**: It is the owner's acceptance test of this feature, and it completes feature 015 T065.

**Independent Test**: The four runs, with their onboarding packages, owner approvals, Fabro run ids, release packages
and the per-attempt record, in the same form as the feature 015 benchmark record.

**Acceptance Scenarios**:

1. **Given** the four approved packages, **When** each work order runs, **Then** each ends in a release package. Every
   BLOCKED gap traces to a phase gate, an inspection or a defect, not to a missing onboarding fact.
2. **Given** any of the four runs, **When** its inputs are audited, **Then** no file outside the owner inputs and the
   approved package was written by a person or by the implementation engineer for that driver.

### Edge Cases

- **A value the test environment chooses.** The delivered code calls a function that is not delivered, and the value
  it returns feeds a register computation (the UART kernel clock feeds the baud-rate register). That value cannot be
  derived. It is an owner-confirmed test-environment assumption, recorded as a limitation of every result that
  depends on it.
- **The vendor package lacks a needed file.** A header or source the delivered code needs is missing from the vendor
  package. Onboarding is BLOCKED and names the missing file; it never substitutes a file from another package.
- **No register table in the chapter.** The reference-manual chapter has no register table for a register the code
  writes. That register's facts are NOT_DERIVED, and any model gate on it is BLOCKED.
- **Code outside the scope.** The delivered code reaches registers of another peripheral (a GPIO initialisation that
  also configures external interrupts). The facts name that peripheral, and the scope decides whether it is in or
  out. Code paths out of scope are recorded, not silently dropped.
- **Several instances.** The code supports several instances. Only the instance the owner's scope names is onboarded.
  A scope naming none gives NOT_DERIVED.
- **Bounded authoring.** Authoring of a model or text keeps failing its gate. The attempts are bounded; the item
  becomes a gap, and the package can still be approved with that gap stated.
- **Conversion changes.** A conversion of the reference manual gives different text from an earlier conversion of the
  same PDF. The hash manifests differ, so it is a new input, and any approval based on the old one is void.
- **A run already in flight.** A package is approved while a run started under the old, hand-onboarded profile is
  still going. The run keeps its own recorded basis; the new package applies to new work orders only.

## Requirements *(mandatory)*

### Functional Requirements

**Onboarding stage**

- **FR-001**: The factory MUST run an onboarding stage for every work order before SWE.1. Its inputs MUST be the owner
  inputs only: the datasheet, the reference-manual chapter and memory map, the delivered code with licence and
  provenance, the owner scope, and the budgets.
- **FR-002**: The onboarding stage MUST include the existing delivery intake (provenance, hashes, build check) and
  MUST NOT weaken any intake check.
- **FR-003**: Onboarding MUST convert the reference-manual inputs with the factory's existing document converter and
  record a hash manifest, as feature 015 does by hand today.

**Deterministic derivation**

- **FR-004**: Onboarding MUST derive, without any model call, at least the following, each with value, method and
  source location (file:line, or document:page):
  - the instance and its base address;
  - the memory-map page;
  - the register prefix;
  - the register/field index with reset values and access types;
  - the driver's header names and function-name prefix;
  - the driver style (register-level LL, factory HAL on an LL, or a standalone handle-based HAL);
  - the time base the driver calls, and the timeout constants;
  - the functions the delivered code calls but that are not delivered;
  - the concrete instances the code compares a handle against;
  - the framework modules and delivered files the build needs (the delivery file map and the configured modules).
- **FR-005**: Every derived fact MUST have one of the statuses DERIVED, NOT_DERIVED or CONFLICT. NOT_DERIVED and
  CONFLICT facts MUST appear as gaps or owner questions. A fact MUST NOT be filled with a default or a guess.
- **FR-006**: Derivation MUST be repeatable: the same inputs give the same facts and the same package hash.
- **FR-007**: A test-environment value that cannot be derived MUST be an owner-confirmed assumption, carried into the
  limitations of every dependent result. Examples: the kernel clock a host test returns, the clock rate a simulation
  assumes.

**Authored items**

- **FR-008**: Items that cannot be derived MUST be authored by AI roles during onboarding: the behavioural simulation
  model, where none exists, and domain texts the SWE roles need.
- **FR-009**: Each authored item MUST be produced through Fabro by a role that loads a versioned SKILL.md and uses
  only role-approved MCP operations. It MUST be checked by deterministic gates and by an independent inspector, in a
  bounded loop. An item that does not pass becomes a gap.
- **FR-010**: Authored domain texts MUST name only:
  - registers and fields present in the derived register/field index;
  - functions, types and constants declared by the delivered code;
  - expected values the inspector can trace to the reference manual.
- **FR-011**: An authored or existing simulation model MUST pass these gates:
  - it loads;
  - its reset values and access types agree with the register/field index;
  - a smoke program built from the delivered code runs to completion on it.

  The behaviour it does not model MUST be stated in the package.

**Generic instructions**

- **FR-012**: The SWE.1-SWE.6 role instructions MUST be composed from the approved package. A work order onboarded by
  this stage MUST NOT need hand-written per-peripheral or per-driver-style prompt text.
- **FR-013**: Built instructions MUST pass a deterministic leftover check. It fails on any identifier of another
  peripheral, another driver layer, or a register, field or function absent from the package.
- **FR-014**: Factory checks that depend on the driver style MUST take it from the package, not from fixed
  assumptions. Examples: the components the architecture view must show, whether a timeout path is required, the host
  test instance mapping.

**Owner approval**

- **FR-015**: Onboarding MUST produce one package containing:
  - the facts with their sources;
  - the authored items with their gate results and verdicts;
  - the assumptions;
  - the gaps;
  - a human-readable summary for owner review;
  - the package hash.
- **FR-016**: SWE.1 MUST NOT start until the owner has approved the package in an owner-decision record. Approval MUST
  be refused while a CONFLICT has no owner resolution.
- **FR-017**: Approval MUST be void when any input or package item changes hash. The work order then returns to
  onboarding.
- **FR-018**: Every SWE work product's evidence MUST record the hash of the package it was produced from.

**Compatibility and regression**

- **FR-019**: Existing hand-onboarded peripherals and driver styles MUST keep working unchanged, and their existing
  tests MUST pass. Migrating one to the package-driven path is an explicit owner choice.
- **FR-020**: For every existing hand-onboarded combination, re-derivation MUST reproduce the hand-written derivable
  facts. Differences MUST be recorded and explained, as a CONFLICT or as a hand error; this is the regression oracle.

**Policy and governance**

- **FR-021**: The onboarding stage MUST NOT:
  - change the delivered code;
  - change owner-only files (scope, safety scope, verification dispositions, safety-document registers);
  - change any safety policy;
  - start before the work order's intake is accepted.
- **FR-022**: The deterministic parts of onboarding MUST make zero model calls. The authored parts MUST run with the
  factory's configured model profile, local or remote, and need no paid service.
- **FR-023**: The onboarding stage, its gates and its role skills are factory changes. They MUST pass the CRE
  promotion gate before deployment, like every factory change.

### Key Entities

- **Onboarding package**: Everything SWE.1-SWE.6 needs beyond the owner inputs, for one work order. It holds derived
  facts, authored items, assumptions, gaps, a summary and a hash. It is linked to the work order and to its input
  hashes.
- **Derived fact**: A named fact (for example base address or time base). It has a value, a status (DERIVED,
  NOT_DERIVED or CONFLICT), a derivation method and one or more source locations.
- **Authored item**: A simulation model or a domain text, with its author role, attempts, gate results, inspection
  verdict and stated limits.
- **Test-environment assumption**: A value the environment chooses rather than the inputs. It has the value, the
  reason it cannot be derived, the owner confirmation and the results it limits.
- **Onboarding gap**: A NOT_DERIVED or CONFLICT fact, a failed authored item, or a missing input, with its effect on
  later phases.
- **Onboarding approval**: The owner-decision record that approves or rejects a package hash, with the reason and the
  resolutions of any conflicts.
- **Regression oracle**: The hand-written facts of the existing onboarded combinations that re-derivation is compared
  against.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The ST HAL drivers for GPIO, SPI, USART and TIM are onboarded from their owner inputs alone. For these
  four, there are 0 per-driver files or texts written by a person or by the implementation engineer, apart from the
  owner inputs and the owner's decisions.
- **SC-002**: For each of the eight existing hand-onboarded combinations, re-derivation reproduces 100% of the
  hand-written derivable facts. Every difference is recorded with its explanation.
- **SC-003**: 100% of the facts in every package have a source location, or carry NOT_DERIVED, CONFLICT or
  owner-assumption status. An audit finds 0 guessed facts.
- **SC-004**: The deterministic part of onboarding completes in under 10 minutes per work order on the factory host,
  with 0 model calls recorded.
- **SC-005**: All four acceptance drivers reach a release package (READY_FOR_OFFLINE_REVIEW, or BLOCKED with every
  gap named). 0 of their gaps are caused by a missing or wrong onboarding fact.
- **SC-006**: The built instructions of the four acceptance drivers pass the leftover check with 0 findings.
- **SC-007**: A model authored for a held-out peripheral, whose hand-written model was hidden from the author, passes
  the model gates. The existing target tests of that peripheral pass on it.
- **SC-008**: The owner can review and decide on an onboarding package from its summary alone, in 15 minutes or less
  per driver.
- **SC-009**: The full factory test suite shows no new failures, beyond the known baseline failures recorded before
  this feature.

## Assumptions

- The acceptance runs execute on loop10 with the current production profile: Codex authors and Claude inspectors,
  through the owner's Claude login. The feature is model-profile independent.
  - A run of the onboarding stage with a local model on omniverse2 is wanted but not part of the acceptance. It is
    recorded as NOT_RUN until a local profile is qualified.
- The four acceptance drivers reuse the behavioural simulation models written by hand in feature 015. Models are
  per peripheral, not per driver. Onboarding re-gates those models (FR-011), and authoring is tested on a held-out
  peripheral (User Story 4).
- The owner keeps providing:
  - the scope (which functions, what is out of scope, which instance);
  - the budgets;
  - the safety scope and the signed safety documents.

  Onboarding derives neither safety relevance nor safety documents. The HAL safety-document v1.1 extension the owner
  chose on 2026-10-27 stays an owner decision outside this feature.
- The existing delivery intake, the brownfield scope extraction, the register-effect conformance checks and the
  release packaging are reused.
- The hand-written profiles of existing peripherals stay as they are until migrated.
- The reference-manual and datasheet PDFs are vendor documents kept locally, outside version control; only their
  hash manifests are tracked, as today.
- The CRC HAL run started 2026-10-27 under the hand-onboarded profile is the comparison baseline for the HAL style. It
  is not re-run under this feature unless the owner asks.
- Nothing in this feature claims ASPICE or ISO 26262 compliance, certification or a safety approval. An approved
  onboarding package means the owner accepted the facts and assumptions, not that the driver is safe.
