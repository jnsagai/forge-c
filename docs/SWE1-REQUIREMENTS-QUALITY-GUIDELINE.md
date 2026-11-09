# SWE.1 Software Requirements Quality Guideline

**Project:** Forge-C  
**Version:** 1.0  
**Date:** 2026-11-09  
**Scope:** Individual software requirements and the complete software requirements set, for any embedded software or driver work order  
**Status:** Engineering guidance; adoption into automated gates requires a separately reviewed implementation change

## 1. Purpose and applicability

This guideline defines what a *good SWE.1 software requirement* looks like and what constitutes a *good software requirements set*. It provides authoring and inspection criteria that can be applied to GPIO, RCC, watchdog, communication, memory, and other driver domains without introducing driver-specific assumptions.

It supports Automotive SPICE 4.1 SWE.1 and established requirements-engineering practice. Automotive SPICE describes process outcomes and base practices; the quality identifiers and the acceptance policy below are **Forge-C recommendations, not individually mandated Automotive SPICE assessment rules**.

Distinguish:
- **Individual quality (IQ):** each requirement is a sound, independently assessable statement.
- **Set quality (SQ):** the collection sufficiently and coherently specifies the software's obligations.
- **Process evidence:** the requirements were analyzed, structured, traced, agreed, and communicated as appropriate. Good wording alone does not establish SWE.1 process capability.

### Source-of-truth rule

Author requirements only from the applicable, controlled work-order inputs: allocated system/software needs, system architecture, HSI, approved interface contracts, platform/reference manuals and errata, applicable safety constraints, and justified derived requirements. A reference manual establishes hardware facts; it does not, by itself, authorize an arbitrary software behavior or performance target.

**Never invent** API behavior, register semantics, ASIL allocations, timing limits, default values, error codes, memory budgets, or safety reactions. If critical information is absent or contradictory, record an explicit gap and mark affected requirements **NEEDS_INPUT/BLOCKED**; do not fabricate a plausible value.

## 2. Individual software requirement quality (IQ)

| ID | Property | Acceptance criterion | Frequent defect |
|---|---|---|---|
| IQ-01 | **Necessary** | The obligation answers a real allocated need, applicable interface constraint, or justified derived need; its purpose is identifiable. | Speculative feature or needless implementation preference. |
| IQ-02 | **Correct / source-faithful** | Behavior, conditions, terminology, and constraints agree with approved input evidence; any derivation has an explicit rationale. | Changed threshold or assumed MCU behavior without authority. |
| IQ-03 | **Unambiguous** | A competent author, implementer, and verifier can reach one intended interpretation; actors, states, signals, conditions, and units are defined. | "Quickly", "normally", "appropriate", "etc.", or undefined "safe". |
| IQ-04 | **Complete within its scope** | The statement contains enough trigger/precondition, required response, and observable outcome to be understood without guessing; it may reference a controlled definition. | Unspecified response on a defined trigger. |
| IQ-05 | **Atomic / singular** | It contains one independently judgeable obligation. Split requirements when one behavior can pass while another fails. | A single statement combining initialization, diagnostics, and recovery. |
| IQ-06 | **Objectively verifiable** | A verifier can determine pass/fail by test, analysis, inspection, or demonstration using stated conditions and observable criteria. Values/tolerances are explicit when needed and source-justified. | "Optimized", "robust", "user-friendly" without measurable criteria. |
| IQ-07 | **Technically feasible** | No identified platform, resource, timing, safety, or interface constraint makes the requirement impossible; uncertainty is recorded for analysis. | A deadline below supported hardware capability. |
| IQ-08 | **Design-independent unless justified** | Describes required behavior, not an arbitrary algorithm, register sequence, data structure, task split, or coding technique. A required design constraint is permitted when explicitly allocated and sourced. | Mandating a lookup table with no upstream justification. |
| IQ-09 | **Consistent** | Does not contradict relevant upstream constraints, peer requirements, interface contracts, or defined modes. | Two incompatible reset-state requirements. |
| IQ-10 | **Appropriate SWE.1 abstraction** | States software-level externally relevant obligations, constraints, and interfaces; leaves unnecessary decomposition to SWE.2/SWE.3. | Source-code pseudocode presented as a software requirement. |
| IQ-11 | **Clear and conforming** | Uses controlled vocabulary, consistent naming/units, a mandatory verb (typically "shall"), and the approved project writing pattern. | Vague pronouns, mixed units, unspecified subject. |
| IQ-12 | **Identifiable and attributable** | Has a stable unique ID and source/derivation references; required project metadata is available without bloating the statement. | Unnumbered text with no provenance or change identity. |

**Important distinctions:**
- A single occurrence of **shall** is a useful syntactic check but does **not** prove atomicity, correctness, completeness, or testability.
- A requirement need not repeat every definition: controlled glossary entries, interface specifications, operating modes, and parameter tables can be referenced precisely.
- Quantification is required **where needed for objective verification**, not as an excuse to manufacture numeric limits.
- **Implementation-independent** does not prohibit a legitimate allocated technology, protocol, diagnostic, or safety constraint. Record why it is required.
- Technical feasibility and source correctness often require engineering judgment; a text classifier alone cannot prove them.
- Requirement-level coverage of corner cases is contextual: do not force every requirement to mention normal, boundary, error, and recovery behavior in one sentence.

### 2.1 Recommended authoring pattern

Prefer a concise EARS-compatible statement when the active Forge-C profile requires EARS:

> When **[defined trigger]**, **[named software element]** shall **[single observable behavior]** **[under applicable conditions/constraints]**.

Other valid EARS forms cover state-driven, ubiquitous, optional-feature, and unwanted-behavior requirements. Use the active project syntax policy; **EARS is a Forge-C writing convention, not mandated by Automotive SPICE**.

**Illustrative example (not an approved API contract):**

Poor:
> The driver shall handle invalid channels safely and quickly using a lookup table.

Improved, provided the approved interface defines `INVALID_CHANNEL`:
- **SWR-EX-001:** When a request references a channel outside the configured channel set, the driver shall return `INVALID_CHANNEL`.
- **SWR-EX-002:** When a request references a channel outside the configured channel set, the driver shall leave all channel configurations unchanged.

The improved pair separates independently verifiable outcomes, removes an unjustified algorithm, and uses observable behavior. Adopt it only when those outcomes are supported by the actual work-order inputs.

## 3. Quality of the complete requirements set (SQ)

Evaluate the set separately from the IQ checklist. A set can contain perfectly worded requirements and still omit essential software behavior.

| ID | Property | Acceptance criterion / evidence |
|---|---|---|
| SQ-01 | **Source coverage and justified derivation** | Applicable upstream system requirements, system-architecture allocations, HSI obligations, and approved constraints are addressed; uncovered sources and derived requirements are identified and dispositioned. Coverage is semantic, not merely link-count based. |
| SQ-02 | **Behavioral completeness** | For *applicable* functions and modes, capture initialization/startup, configured operation, boundary cases, invalid requests, fault detection/response, recovery/reset, shutdown/deinitialization, and relevant state transitions. Explicitly justify N/A scenarios; do not insert boilerplate for irrelevant modes. |
| SQ-03 | **Non-functional and interface completeness** | Include justified timing, resource, concurrency, data integrity, safety, diagnostics, robustness, and external-interface obligations when allocated. Do not invent budgets simply to fill a category. |
| SQ-04 | **Coherent structure and priorities** | Organize by function/interface/mode/variant; give stable identifiers and applicable priorities or release scopes so requirements can be understood and maintained. |
| SQ-05 | **Internal consistency and controlled redundancy** | No incompatible obligations or contradictory terms; duplicates and overlapping statements are removed or explicitly justified. |
| SQ-06 | **Bidirectional traceability with consistency** | Establish relevant links to system requirements and system architecture (or approved stakeholder/context inputs for software-only development), with evidence that linked meanings agree. No gratuitous duplicate trace paths. |
| SQ-07 | **Interdependency and feasibility analysis** | Identify dependencies, assumptions, parameter relationships, and constraints; assess feasibility and record unresolved conflicts and decisions. |
| SQ-08 | **Operating-environment impact analyzed** | Evaluate effects on hardware, other software, interfaces, startup/reset behavior, timing/resource use, and interactions with surrounding systems, as applicable. |
| SQ-09 | **Agreement, configuration, and communication** | The approved baseline, revisions, open issues, affected parties, and communication/approval status are identifiable. An LLM-generated file is not an approved baseline by itself. |
| SQ-10 | **Verification readiness** | Required outcomes can be linked to prospective verification measures; verification intent and unresolved verification ambiguities are recorded. Actual verification results belong to downstream verification processes, not SWE.1. |

### 3.1 Coverage inspection method

Build a small coverage matrix from **actual source obligations**, not from a generic driver feature list.

| Source / scenario | SWE.1 requirement IDs | Status | Evidence / gap |
|---|---|---|---|
| Approved functional allocation | SWR-... | Covered / Partial / Gap / N/A | Input reference and relevant clause |
| Approved interface and invalid-input obligation | SWR-... | Covered / Partial / Gap / N/A | Interface contract reference |
| Allocated diagnostic or safe-state behavior | SWR-... | Covered / Partial / Gap / N/A | Safety or system allocation |
| Allocated non-functional limit | SWR-... | Covered / Partial / Gap / N/A | Budget, rationale, test boundary |

A category is **N/A** only with a short justification. A missing or conflicting authoritative input is a **Gap / NEEDS_INPUT**, not silently marked N/A. Do not infer requirement-set completeness from number of requirements or formatting score.

## 4. Authoring, inspection, and acceptance workflow

1. **Read and inventory approved inputs.** Create a compact list of allocated obligations, modes, constraints, interfaces, and unresolved questions.
2. **Draft only justified requirements.** Each requirement gets a stable ID, one observable obligation, and source/derived provenance. Keep text concise.
3. **Run deterministic checks.** Check parseable IDs, duplicates, required fields, EARS syntax and the project's one-`shall` convention, referenced IDs, glossary terms, units, trace link integrity, and ReqIF generation/XSD when active.
4. **Perform semantic IQ review.** Examine source fidelity, necessity, atomicity, unambiguity, completeness within scope, verifiability, feasibility, abstraction, and contradictions. Cite the specific statement and input evidence for a defect; do not emit narrative reasoning.
5. **Perform semantic SQ review.** Compare the set against upstream allocations, relevant scenarios/modes, constraints, interfaces, and environment impacts. Detect omissions and incompatible combinations.
6. **Emit concise findings.** Use `requirement_id / quality_id / severity / evidence / required_action`. For set gaps use `SQ-xx` with the missing source or scenario. Separate uncertain input from author defects.
7. **Repair and re-check affected items.** A deterministic controller decides the gate result; the author does not self-approve. Re-run traceability and consistency checks after changes.

### 4.1 Suggested severity and disposition

| Disposition | Examples | Outcome |
|---|---|---|
| **BLOCKING** | Unsupported safety or hardware behavior; invented mandatory limit; contradictory obligations; unverifiable mandatory behavior; applicable upstream need uncovered; trace inconsistency; missing critical source | FAIL / NEEDS_INPUT; do not freeze a compliant SWE.1 baseline |
| **CORRECTABLE** | Missing precision that can be resolved from available inputs; combined independent obligations; ambiguous term | Revise, then re-inspect |
| **EDITORIAL** | Typo or formatting issue that does not change technical meaning | Fix or formally disposition under project policy |
| **N/A** | A reviewed property/scenario does not apply | Record a concise reason; never use N/A to hide missing evidence |

**No automatic waivers** for safety-relevant or unknown-source conflicts. These are proposed inspection classifications, not a replacement for existing versioned Forge-C gate policy.

### 4.2 Minimum useful outputs

The SWE.1 author should primarily deliver:
- **Requirements baseline:** `workproducts/SWE.1/software_requirements.md`, using the active EARS style.
- **Traceability/coverage:** source-to-SWR and relevant downstream verification references in the project-prescribed format, with uncovered-source list.
- **Required export:** `workproducts/SWE.1/software_requirements.reqif` generated and validated by the existing project pipeline when the gate requires it.
- **Concise review result:** IQ and SQ findings with exact evidence references and disposition, plus any blocking input questions.

Suggested metadata per requirement (adapt to existing repo schemas rather than introducing a competing schema): **id, type, statement, source / derivation, priority or variant if applicable, status**, and an appropriate verification method or reference when required.

Avoid speculative explanatory prose, self-scoring narratives, hidden chain-of-thought dumps, duplicate workproducts, and invented "compliance" percentages. More tokens and more requirements do not inherently improve quality.

## 5. Definition of done for a candidate SWE.1 baseline

A candidate is ready for its configured inspection/freeze gate when all of the following are evidenced:

- [ ] Each applicable SWR satisfies IQ-01 to IQ-12 or has an explicitly tracked, permitted disposition.
- [ ] SQ-01 to SQ-10 have been evaluated with traceable evidence and no unresolved blocking gaps.
- [ ] Source and derivation provenance is preserved; no unsupported platform behavior, parameters, or safety claims were invented.
- [ ] The active Forge-C EARS/ReqIF and traceability checks pass (where enabled).
- [ ] Required technical feasibility, dependencies, and operating-environment impacts have been analyzed.
- [ ] The baseline version, findings, agreement/communication evidence, and outstanding restrictions are recorded.
- [ ] A separate authorized reviewer or gate evaluates the outputs; generator completion is not equivalent to approval.

This checklist is **guidance**. The actual operational gate remains the repository's versioned checklists and policy; incorporating or superseding checks requires a deliberate, reviewed change.

## 6. Relationship to Automotive SPICE 4.1 SWE.1

| Base practice | Relationship to this guideline |
|---|---|
| **SWE.1.BP1** — specify | IQ characteristics and capture of functional/non-functional requirements. |
| **SWE.1.BP2** — structure | SQ-04 and applicable priorities/variants. |
| **SWE.1.BP3** — analyze | IQ-02, IQ-07, SQ-07; correctness, interdependencies, technical feasibility. |
| **SWE.1.BP4** — operating environment | SQ-08. |
| **SWE.1.BP5** — consistency and traceability | IQ-09, SQ-01, SQ-05, SQ-06; both meaningful consistency and bidirectional links. |
| **SWE.1.BP6** — communicate | SQ-09 and communication of environment impacts. |

Automotive SPICE 4.1 does **not** require one particular EARS pattern, Markdown/ReqIF schema, numerical quality score, or LLM inspection strategy. It does not make a single SWE.1 document sufficient evidence of process performance or an ISO 26262 safety case. Verifiability is a property of the requirement text; project-maintained verification metadata remains useful, but the old Automotive SPICE 3.1 SWE.1 verification-criteria base practice is not a separate BP in 4.1.

## 7. References and repository alignment

1. **VDA QMC**, *Automotive SPICE Process Reference/Assessment Model 4.1*, released 2026-08-24, section 4.4.1, pages 44–45: https://vda-qmc.de/wp-content/uploads/2026/09/Automotive-SPICE-PAM-v41.pdf
2. **ISO/IEC/IEEE 29148**, *Requirements engineering* (see organization's licensed edition).
3. **INCOSE**, *Guide for Writing Requirements* (see organization's licensed edition).
4. **ISO 26262-8:2018**, supporting processes (when within the work-order safety scope; see licensed edition).
5. Forge-C active project checklist: [SWE-CHECKLISTS.md](SWE-CHECKLISTS.md).
6. Forge-C governing principles: [constitution.md](../.specify/memory/constitution.md).

**Implementation note:** As of this document's creation, the existing Forge-C checklist includes mandatory SWE1-01 through SWE1-08 criteria, EARS validation, ReqIF export, and project-specific safety/driver checks. This generic guideline **supplements** those requirements; it does not change their implementation, downgrade required criteria, or claim new gates have been deployed.
