# Feature Specification: Forge-C High-Integrity V-Model Skills (APM package)

**Feature Branch**: `feat/023-high-integrity-vmodel-skills`

**Created**: 2026-11-22

**Status**: Draft

**Input**: User description: "Package Forge-C's factory know-how as a portable, published APM package of reusable skills for the Capgemini Global Agentic Engineering Hackathon 2026 (deadline 2026-12-07 23:59 CET). Led by generic high-integrity standards (ISO 26262 one profile among others), ready for cloud and local models, applying the standard V-model from system requirements. Inputs are natural-language requirements for middleware/application, or datasheets/reference manuals/reference models for HAL/LL. Work cloud-based, not on Omniverse2."

## Context

Forge-C today is an on-premise factory: 20 versioned role skills run inside a workflow engine, with policy-enforced
tools, a local model and an ASPICE SWE.1–SWE.6 / ISO 26262 orientation. That know-how can't be used outside the
factory. This feature turns it into a **portable skills package**. An engineer installs the package into the coding
agent they already use, and it applies a **standard V-model under a standard-neutral high-integrity core**.

- **Standards.** Individual standards (ISO 26262, IEC 61508, ASPICE and others) plug in as **profiles**. None is hard-wired.
- **Models.** The package works with **cloud and local models**.
- **Hackathon deliverables.** The published package, its README, measurable-impact evidence and a demo.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - From natural-language system requirements to verified software requirements (Priority: P1)

An embedded/middleware engineer starts from stakeholder and system needs written in natural language, for example
"the ECU shall recover to a safe state within 50 ms when the application task stalls". With the package installed in
their coding agent, they run four steps:

1. An author skill derives **system requirements**.
2. An independent inspector skill reviews them one requirement at a time, then as a set.
3. Deterministic gates check quality and traceability.
4. The same pattern derives **software requirements** for the middleware/application component, traced back to the
   system requirements.

The engineer gets the workproducts on disk, a trace matrix and a compact pass/fail status with findings.

**Why this priority**: This is the hackathon's core demonstration and the first step of the V. It covers the input class
that most Capgemini engineering teams have (natural-language requirements). It is enough on its own to show the
value of the skills.

**Independent Test**: Install the package into a clean project. Supply the public demo stakeholder needs and run the
system-requirements and software-requirements stages. Check that both levels exist, that every software requirement
traces to a system requirement and vice versa (or is a declared derived requirement), that the gate verdicts are
recorded, and that the inspector's findings were applied or carried as open points.

**Acceptance Scenarios**:

1. **Given** a project with approved natural-language stakeholder needs and a selected standard profile, **When** the
   engineer runs the system-requirements stage, **Then** the package produces uniquely identified, atomic, verifiable
   system requirements, each traced to a stakeholder need, plus a list of open points for anything the inputs do not
   state.
2. **Given** authored system requirements, **When** the inspector stage runs, **Then** each requirement is judged on its
   own against a versioned checklist. The whole set is then judged for consistency, completeness and coverage. The
   findings go back to the author, and the inspector never edits the workproduct.
3. **Given** inspected system requirements, **When** the software-requirements stage runs for the middleware component,
   **Then** every software requirement traces upward and every system requirement allocated to software is covered
   downward. A gap fails the gate.
4. **Given** a requirement set with a defect that the author cannot resolve within the configured rework limit, **When**
   the limit is reached, **Then** the stage ends **BLOCKED** with the unresolved findings. It never ends with a silent pass.

---

### User Story 2 - From a reference manual or datasheet to driver requirements (Priority: P1)

A HAL/LL driver engineer supplies their own copy of a microcontroller reference manual or datasheet, or a reference
model, for one peripheral. The package derives **out-of-context** driver software requirements. Every hardware-related
statement cites the document's section and page. Nothing about registers, timing or reset behaviour is invented. Facts
the document does not state become open points.

**Why this priority**: The driver input class is what makes Forge-C distinctive and is where it has the most evidence.
It shows that the same skills serve both input classes.

**Independent Test**: Supply a peripheral section of a public reference manual and run the software-requirements
stage in driver mode. Check that every hardware claim carries a section+page reference that the gate can resolve to the
supplied document, and that no hardware fact appears without a source.

**Acceptance Scenarios**:

1. **Given** a supplied reference document and a peripheral scope, **When** the driver requirements stage runs, **Then**
   each requirement cites a document section and page, and the trace gate rejects any hardware claim without a source.
2. **Given** a middleware project (User Story 1) that depends on this driver, **When** both are run, **Then** the
   middleware's software requirements trace down to the driver's interface requirements. This shows one V across both
   input classes.
3. **Given** no reference document, or an unreadable one, **When** the driver stage starts, **Then** intake ends
   **BLOCKED** with the reason, before any author runs.

---

### User Story 3 - Choose the standard, not the tool (Priority: P2)

A safety or quality lead selects a standard profile and an integrity level for the project, such as ISO 26262 at
ASIL B, IEC 61508 at SIL 2, ASPICE as the process reference, or a generic baseline. The profile decides how rigorous the
process is:

- which checks are required;
- the inspector's independence level;
- the coverage and verification targets;
- the vocabulary used in the reports.

The skills themselves do not change.

**Why this priority**: The owner directs Forge-C to be led by generic high-integrity standards, with ISO 26262 as only
one of them. This makes the package usable across automotive, industrial, rail, medical and aerospace teams.

**Independent Test**: Run the same demo once under ISO 26262/ASIL B and once under IEC 61508/SIL 2, changing only the
project configuration. Check that the reports use each standard's terms and rigor settings, and that no skill file
changed.

**Acceptance Scenarios**:

1. **Given** a project configured with profile A, **When** the profile is switched to profile B, **Then** the gates apply
   profile B's required checks and targets, and the reports use profile B's terms, with zero edits to skills.
2. **Given** a project with no profile selected, **When** any stage runs, **Then** the generic profile applies, at a
   stated integrity level. The package never assumes a specific standard silently.
3. **Given** any profile, **When** a report is generated, **Then** it cites clause identifiers only, reproduces no
   normative text, and states that it is not a certification or compliance claim.

---

### User Story 4 - The whole V, right side included (Priority: P2)

An engineer continues past requirements:

- **Left side:** system architecture, software architecture, then detailed design and unit construction.
- **Right side:** unit verification, software integration verification, software qualification, then system
  integration and system qualification verification.

Each right-side stage plans and records verification against its left-side counterpart. The output is a sealed review
package.

**Why this priority**: The owner asked for the standard V-model. For the hackathon the left-side requirement stages are
deep (P1). The remaining stages ship as defined skills with checklists and gates, at lower depth.

**Independent Test**: On the demo, run each later stage at least once and check that each produces its workproduct,
traces to its counterpart, and records a gate verdict.

**Acceptance Scenarios**:

1. **Given** approved software requirements, **When** the architecture and design stages run, **Then** every element
   traces to the requirements it realises, and every requirement is allocated.
2. **Given** a right-side stage, **When** it runs, **Then** each test case or verification item traces to the left-side
   item it verifies. Unverified items are listed as gaps.
3. **Given** a stage whose deterministic tool is unavailable (for example no compiler or static analyser installed),
   **When** the gate runs, **Then** that check is recorded **NOT_RUN** and the package lists it as a gap. It is never
   recorded as passed.

---

### User Story 5 - Sealed offline review package (Priority: P2)

At any point, a release skill and a deterministic packager build a review package: the workproducts, the trace matrix,
the findings, the gate results, the tool and model provenance, and a hash manifest. The status is
**READY_FOR_OFFLINE_REVIEW** or **BLOCKED** with a gap list.

**Why this priority**: The constitution requires every run to end in a reviewable package. It is also the concrete
artefact judges and reviewers can inspect.

**Independent Test**: Run the packager after a passing demo and after a deliberately failing one. Check the status, the
gap list and that every hash in the manifest matches.

**Acceptance Scenarios**:

1. **Given** all required gates passed, **When** packaging runs, **Then** the status is READY_FOR_OFFLINE_REVIEW, the
   manifest hashes verify, and the disclaimer states it is not a certification, approval or production release.
2. **Given** any failed, missing or NOT_RUN required check, **When** packaging runs, **Then** the status is BLOCKED and
   every gap is listed with its source.

---

### User Story 6 - Same skills on cloud and local models (Priority: P2)

An engineer runs the demo once with a cloud model and once with a local model, using the same skills, gates and
inputs, changing only the agent or model configuration.

**Why this priority**: The owner requires both. Cloud comes first for the hackathon; local keeps the on-premise,
zero-cost option that Forge-C was built for.

**Independent Test**: Run the P1 demo on one cloud model and one local model. Check that both produce gate verdicts and
review packages, and that the package records which model produced each workproduct.

**Acceptance Scenarios**:

1. **Given** the same project and inputs, **When** run with a cloud model and then with a local model, **Then** both runs
   complete through the deterministic gates and record their model provenance. Their quality metrics are reported side
   by side, with no claim of equivalence.

---

### User Story 7 - Hackathon submission with measurable impact (Priority: P1)

The submitter publishes the package to Capgemini's Agentic AI Artifacts repository. The submission includes:

- the mandatory README;
- measurable-impact evidence;
- a recorded demo;
- the install link and the legal/IP acknowledgement.

**Why this priority**: Without a valid submission by 2026-12-07 23:59 CET, none of the other stories count for the
hackathon.

**Independent Test**: A person who has not used Forge-C follows the README from a clean machine, installs the package
from its link and reproduces the P1 demo. The impact report's numbers are reproducible from the stored run evidence.

**Acceptance Scenarios**:

1. **Given** the published package, **When** a new user follows the README, **Then** the README contains:
   - the problem;
   - the intended users;
   - installation and execution;
   - inputs, outputs and parameters;
   - supported models;
   - prerequisites and dependencies;
   - the expected benefits;
   - example usage.
   The user completes the P1 demo.
2. **Given** the impact evaluation, **When** the judges read it, **Then** each metric links to stored run evidence. The
   metrics compare the same model with and without the package, and the limitations are stated.

---

### Edge Cases

- **Contradictory or ambiguous needs:** the author records an open point or conflict and never resolves it by invention.
  The set inspection must flag unresolved conflicts.
- **Reference document too large for the model's context:** the user or intake narrows the input to the peripheral's
  sections. Requirements cite only the sections that were supplied.
- **Agent harness without hooks:** the write-scope guardrail is enforced afterwards. The gate compares the files
  changed against the role's allowed outputs and fails any change outside them.
- **Model without reliable tool calling (common on small local models):** the skills still work through files on disk,
  and all verdicts come from the deterministic gates.
- **Author and inspector run in the same session or context:** independence cannot be demonstrated, so the package
  records an "independence not demonstrated" gap. The profile decides whether that blocks.
- **A user or prompt asks the package to declare certification, compliance or release:** the release skill refuses and
  records the request as a finding.
- **Profile requires a check whose open-source tool is missing:** the check is NOT_RUN, which is a gap, never a pass.
- **Re-running a stage after an upstream change:** downstream trace links to the changed items are marked suspect until
  re-inspected.
- **Inputs containing personal data or secrets:** intake warns the user and does not copy them into the review package
  or the traces.

## Requirements *(mandatory)*

### Functional Requirements

**Packaging and distribution**

- **FR-001**: The deliverable MUST be one APM package, installable from a versioned link. The hackathon mandates APM.
  Its skills MUST load in at least three agent harnesses, for example Claude Code, GitHub Copilot and Kiro.
- **FR-002**: Every AI role MUST be a versioned skill. Each skill MUST declare:
  - its V-model stage;
  - author or inspector role;
  - its inputs;
  - its output workproducts and their write scope;
  - the tools it may use;
  - its output-status contract;
  - its explicit limits.
- **FR-003**: The published package MUST NOT contain private benchmark data, copyrighted standard text, or
  reference-manual or datasheet text. A deterministic content check MUST run before every publish and fail on a violation.
- **FR-004**: The package MUST include the deterministic gates and the packager, runnable without any AI model.

**Standard-neutral high-integrity core**

- **FR-005**: The process stages, workproduct types, trace rules and checklists MUST be expressed in standard-neutral
  terms.
- **FR-006**: Standard **profiles** MUST map neutral integrity levels, workproducts and rigor settings to each
  standard's terms. Rigor settings include required checks, inspector independence, verification and coverage targets,
  and rework limits. The package MUST ship at least:
  - a generic baseline;
  - ISO 26262;
  - IEC 61508;
  - ASPICE as process reference.

  It MUST also ship a documented template for adding further profiles, for example DO-178C, EN 50716 and IEC 62304.
- **FR-007**: Switching profile or integrity level MUST require only a project-configuration change and no skill edits.
- **FR-008**: Profiles and reports MUST cite clause identifiers only. Every report MUST state that it is not a
  certification, compliance, approval or production-release claim.
- **FR-009**: With no profile configured, the generic profile MUST apply at an explicitly stated integrity level.

**Model independence**

- **FR-010**: Skills MUST NOT depend on a specific model provider. The same skill content MUST serve cloud and local
  models.
- **FR-011**: Every pass/fail verdict MUST come from a deterministic gate. A model's own claim of success MUST NOT count
  as evidence.
- **FR-012**: Each workproduct MUST record its provenance: role, stage, the declared harness and model, input hashes and
  a timestamp.

**V-model process**

- **FR-013**: The package MUST define these stages, each with an author skill, an independent inspector skill and a
  gate:
  - **Left side:** system requirements, system architecture, software requirements, software architecture, and
    detailed design with unit construction.
  - **Right side:** unit verification, software integration verification, software qualification verification, and
    system integration and system qualification verification.
- **FR-014**: Projects MUST be able to enter the V by input class:
  - **(a) Natural-language stakeholder/system needs** for middleware/application. These start at system requirements.
  - **(b) Datasheets, reference manuals or reference models** for HAL/LL drivers. These may start out-of-context at
    software requirements, with hardware claims traced to document section and page.

  A middleware project MUST be able to trace down to a driver project's interface requirements.
- **FR-015**: Traceability MUST be bidirectional across every level. Each right-side item MUST trace to the left-side
  item it verifies. The gate MUST fail on orphans, on uncovered items, and on links to items that do not exist.
- **FR-016**: Requirement inspection MUST run in two phases: one requirement at a time without changing the others,
  then the whole set. Unresolved findings from the first phase MUST carry into the set phase.
- **FR-017**: Inspectors MUST NOT modify author workproducts. Findings MUST return to the author, who reworks within a
  configurable, bounded number of rounds. When the rounds run out, the result MUST be BLOCKED with the open findings.
- **FR-018**: Skills MUST NOT invent hardware facts, requirements, test results or approvals. Anything the inputs do not
  support MUST become an open point.
- **FR-019**: The deterministic gates MUST cover:
  - workproduct structure validity;
  - identifier uniqueness;
  - trace completeness;
  - rule-based requirement quality: atomic, verifiable, no ambiguous terms, no implementation in requirements;
  - for code stages, where the profile requires them: build, static analysis, coding-rule check, unit tests and
    coverage, using open-source tools.

  A missing tool MUST yield NOT_RUN and a gap.
- **FR-020**: Where the harness supports hooks, a guardrail MUST restrict each role's writes to its declared output scope.
  Where it does not, the gate MUST detect out-of-scope changes and fail.
- **FR-021**: Agents MUST respond with compact machine-readable status and issues. Full detail belongs in the
  workproducts on disk.
- **FR-022**: Changing an upstream item MUST mark the downstream links to it as suspect until they are re-inspected.

**Release**

- **FR-023**: A deterministic packager MUST seal a review package containing:
  - the workproducts;
  - the trace matrix;
  - the findings;
  - the gate results with tool versions;
  - provenance;
  - a hash manifest.

  Its status MUST be READY_FOR_OFFLINE_REVIEW or BLOCKED with a gap list. It MUST produce a package even when stages
  failed, wherever storage allows.

**Hackathon deliverables**

- **FR-024**: The package README MUST cover:
  - the problem and use case;
  - the intended users;
  - installation and execution;
  - inputs, outputs and parameters;
  - supported foundation models;
  - prerequisites and dependencies;
  - the expected benefits;
  - example usage;
  - the limitations and the non-certification statement.
- **FR-025**: The package MUST ship public demo inputs for both input classes:
  - a middleware example from natural-language needs, for example a watchdog/health-monitor manager;
  - a driver example that references, but does not include, a public reference manual, for example the watchdog
    peripheral that the middleware uses.
- **FR-026**: An impact evaluation MUST compare runs of the same model and inputs **with and without** the package. It
  MUST measure:
  - trace coverage;
  - requirement-quality rule violations;
  - the inspector's detection rate on a seeded-defect corpus;
  - gate outcomes;
  - elapsed time and model usage.

  Every number MUST link to stored run evidence.
- **FR-027**: The submission MUST include the install link, the README, the impact evidence, a recorded demo or
  screenshots, and the legal/IP acknowledgement. The acknowledgement is completed by the submitter.
- **FR-028**: The hackathon demonstrations MUST use cloud models as the first target, with [NEEDS CLARIFICATION: which
  agent harness(es) and cloud model(s) are acceptable to Capgemini for the evidence and demo — e.g. Claude Code with
  Claude, GitHub Copilot with its selectable models, Kiro?]. At least one local-model run follows as secondary evidence.

### Key Entities

- **Project configuration**: the selected standard profile, the integrity level, the input class, the enabled stages,
  the rework limits and the declared harness/model.
- **Standard profile**: maps neutral integrity levels, workproduct names and rigor settings to one standard's terms and
  clause identifiers.
- **Integrity level**: a neutral rigor tier that each profile maps to its own scale (ASIL, SIL, DAL, software safety
  class).
- **Stage**: one V-model step. It has an author role, an inspector role, input workproducts, output workproducts, a
  checklist and a gate.
- **Workproduct**: a stage output on disk, for example a requirement set, an architecture, a design, code, a test
  specification or a test report. It carries provenance.
- **Requirement item**: an identified, atomic statement. It has a level (stakeholder, system, software, driver
  interface), a source reference (an upstream item, or a document section and page), a verification method and a status.
- **Trace link**: a typed, bidirectional relation between items, for example "derives", "allocates", "realises" or
  "verifies". It can be valid or suspect.
- **Finding**: an inspector or gate issue, with a checklist item, severity, location, status and the round it was raised.
- **Gate result**: one deterministic check's verdict (PASS, FAIL or NOT_RUN), with the tool, its version and the
  evidence reference.
- **Reference document reference**: a document identifier plus a section and page. The document's text is never stored.
- **Review package**: the sealed bundle with its status (READY_FOR_OFFLINE_REVIEW or BLOCKED), the gap list, the
  manifest and the disclaimer.
- **Evaluation run**: one measured demo run, either with or without the package, with its model, metrics and links to
  evidence.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user new to Forge-C can install the package from its link and complete the P1 demo (needs → system
  requirements → software requirements, with gates) in under 30 minutes of hands-on time, following only the README.
- **SC-002**: The package's skills load and run the P1 demo in at least 3 agent harnesses.
- **SC-003**: The P1 demo completes, with recorded gate verdicts, on at least 1 cloud model and at least 1 local model.
- **SC-004**: In every package marked READY_FOR_OFFLINE_REVIEW, 100% of requirement items are traced in both directions.
  Any orphan or uncovered item results in BLOCKED in 100% of test cases.
- **SC-005**: On a seeded-defect corpus of at least 20 requirement defects, the inspector plus the gates detect at least
  80% of them. The measured rate is reported, whatever it turns out to be.
- **SC-006**: With the package, requirement-quality rule violations per 100 requirements fall by at least 50% compared
  with the same model and inputs without the package. The target is stated in advance and the measured result is
  reported honestly either way.
- **SC-007**: Switching between at least 2 standard profiles changes only the project configuration: 0 skill files
  change, and 100% of reports use the selected profile's terms.
- **SC-008**: The pre-publish content check finds 0 excerpts of copyrighted standard or reference-manual text and 0
  private benchmark artefacts in the published package.
- **SC-009**: Every unavailable required check appears as NOT_RUN and as a gap. 0 cases report a check as passed when it
  did not run.
- **SC-010**: The complete submission is made by 2026-12-05 (2-day buffer). The hard deadline is 2026-12-07 23:59 CET.

## Assumptions

- **Fabro-free.** The package is derived from the existing Forge-C skills, checklists, gates and SWE.1 quality guideline,
  rewritten so that it depends on neither the Fabro engine nor the factory's private tool servers.
- **Scope.** The existing on-premise factory, Omniverse2 and its runs are out of scope. Work happens in the local
  repository, on GitHub and with cloud models.
- **No copyrighted inputs shipped.** Users supply their own copies of reference manuals, datasheets and standards. The
  package ships identifiers only. Standard texts and coding-rule texts (for example MISRA) are not included.
- **Licence.** The package is licensed Apache-2.0, like Forge-C. The submitter reviews the hackathon's legal/IP terms
  before publishing and completes the acknowledgement.
- **Measuring impact.** Impact is measured against the same model without the package, not against human engineers.
  Measuring human effort is out of scope for the deadline.
- **Depth.** Hackathon depth is uneven by design. The system- and software-requirements stages, traceability, the gates
  and packaging are fully exercised on the demo. The remaining V stages ship as defined skills, checklists and gates and
  are exercised at least once on the demo.
- **Install route.** Capgemini's Agentic AI Artifacts repository accepts an APM package installable from a git
  reference. If it requires a different publication route, only the publication step changes.
- **Constitution.** The Forge-C constitution currently names ASPICE SWE.1–SWE.6 and ISO 26262 ASIL B in Principle II. The
  owner's directive (2026-11-22) to be led by generic high-integrity standards requires a constitution amendment
  (Principle II generalised to profiles), made through the governed constitution update. Assisted, human-invoked use of
  the package inside a coding agent is a mode alongside the unattended factory (Principle III). Tool use goes through
  MCP where the harness supports it, with gates as the backstop (Principle V).

## Out of Scope

- Certification, qualification, compliance claims, or tool-confidence claims for any standard.
- Running or changing the Omniverse2 factory, its line, its maintainer loop or its live runs.
- Self-healing supervision and lessons-learned sharing (factory features), beyond describing them in the README as
  the reference implementation.
- Reproducing any standard's normative text or any vendor document's content.
