# Feature Specification: Brownfield Work Orders (existing code in, remaining work products out)

**Feature Branch**: `feat/008-brownfield-work-orders`

**Created**: 2026-10-20

**Status**: Draft

**Input**: User description: "implement a new workflow based on the existing one, where I bring to you the datasheet and an already existing code, and the factory mission is to produce all the remaining ASPICE and ISO26262 SW artifacts based on that" (owner, 2026-10-20).

**Owner choices (2026-10-20)**:
- Both code modes are supported, chosen per work order. Both are tested on the factory's own previously generated RCC LL and HAL code used as delivered code.
- Software requirements come from the datasheet/reference manual plus an owner-given scope, independently of the code.
- The first pilot is ST's existing STM32CubeN6 RCC driver code.

## Context

Today every Forge-C work order is **greenfield**. The owner supplies reference-manual sections and a scope, and the factory writes everything:
- requirements, architecture and design;
- the C code;
- tests and verification reports;
- the offline review package.

The latest LL run, r170, produced a READY_FOR_OFFLINE_REVIEW package this way.

Real projects often start from code that already exists: a silicon vendor's driver, a supplier delivery, or legacy code. What is missing is the evidence around that code: requirements, architecture, design, verification at three levels, traceability and the safety work products. This feature adds a **brownfield** work order. The owner brings the datasheet/reference manual, the existing code and a scope. The factory produces the remaining ASPICE SWE.1–SWE.6 and ISO 26262 software work products for that code, and judges the code against requirements derived independently from the datasheet.

**Vocabulary used in this spec:**
- **Delivered code:** the existing source files the owner brings, with their licence and origin.
- **Delivered baseline:** the delivered code as received: every file and its fingerprint (hash), frozen at intake.
- **Scope:** the part of the delivered code the work order covers. The owner names functions or features; the rest of the delivered code is outside the work order.
- **Code mode:** how the factory may treat the delivered code.
  - **FROZEN:** never changed; problems are reported.
  - **FIX_ALLOWED:** problems may be corrected, each change justified and re-verified.
- **Conformance finding:** a recorded disagreement between the delivered code and the requirements or the datasheet. Three kinds:
  - code with no requirement;
  - a requirement with no code;
  - code that contradicts the datasheet or a requirement.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Start a brownfield work order from a datasheet, existing code and a scope (Priority: P1)

The owner names the reference documents, the delivered code (a directory or archive), its licence and origin, the scope, and the code mode. At intake the factory:
- fingerprints every delivered file;
- makes the delivered baseline read-only;
- resolves the scope to concrete functions in the code;
- checks that the in-scope code builds;
- records all of this in the work order.

The owner learns at once whether the delivery is usable, before any analysis starts.

**Why this priority**: Every other story works on this baseline. A delivery that cannot be identified, built or scoped must stop here with a clear reason, not fail later in a phase.

**Independent Test**: Run intake on the factory's own LL code from r170, delivered as a directory with a licence note, with a scope of its 16 functions. The work order records:
- 16 resolved functions;
- one fingerprint per file;
- the code mode;
- a successful build check.

The delivered files cannot be modified by any factory role.

**Acceptance Scenarios**:

1. **Given** a delivery with a licence and origin, **When** intake runs, **Then** each delivered file is recorded with its fingerprint, licence and origin, and the delivered baseline is read-only to every factory role.
2. **Given** a scope that names a function that does not exist in the delivered code, **When** intake runs, **Then** the work order stops as BLOCKED at intake. The finding names the missing function.
3. **Given** a delivery without a stated licence or origin, **When** intake runs, **Then** the work order stops as BLOCKED at intake with a finding for each missing item.
4. **Given** in-scope code that does not build with the declared dependencies, **When** intake runs, **Then** the work order stops as BLOCKED with the build log, and nothing is analysed.
5. **Given** delivered code larger than the scope, **When** intake runs, **Then** the out-of-scope functions are listed as excluded and not analysed. No requirement is expected for them.

---

### User Story 2 - Requirements derived independently and traced to the delivered code (Priority: P1)

The factory writes the software requirements from the reference documents and the scope only, without reading the delivered code, exactly as in a greenfield work order. It then traces each requirement to the delivered code that implements it, and each in-scope function to the requirements it serves. Each gap becomes a conformance finding:
- code with no requirement;
- a requirement with no code;
- code that contradicts a requirement or the datasheet.

**Why this priority**: Requirements written from the code would only describe what the code does, including its defects. Independence is what makes the rest of the evidence meaningful.

**Independent Test**: Run the r170 LL code as delivered against the same RCC inputs. Then run five altered copies, each with one seeded mismatch:
- a wrong bit mask;
- a missing function;
- an extra unrequested function;
- a wrong register;
- an unrelated bit overwritten.

Each mismatch produces exactly the expected kind of conformance finding, naming the function and the requirement.

**Acceptance Scenarios**:

1. **Given** a brownfield work order, **When** requirements are written, **Then** the requirement author has no access to the delivered code. The record shows the requirements were frozen before tracing to the code began.
2. **Given** frozen requirements and the delivered code, **When** tracing runs, **Then** every in-scope function is traced to at least one requirement or reported as code with no requirement.
3. **Given** frozen requirements and the delivered code, **When** tracing runs, **Then** every requirement is traced to code or reported as a requirement with no code.
4. **Given** delivered code whose register access contradicts the reference document, **When** verification runs, **Then** a conformance finding cites the document page and the function.

---

### User Story 3 - Remaining ASPICE work products for frozen delivered code (Priority: P1)

In FROZEN mode the factory produces the rest of the SWE.1–SWE.6 evidence around the delivered code and never changes the code. The work products are:
- the architecture, recovered from the code and checked against it;
- the detailed design and unit specifications of the delivered units, each tied to requirements;
- unit, integration and qualification tests on the host and on the simulated target;
- verification reports, traceability matrices, defects and limitations;
- the offline review package.

The package states that the code is the delivered baseline and proves it with the fingerprints.

**Why this priority**: This is the core of the owner's request: the remaining work products for code that already exists.

**Independent Test**: Run the r170 LL code as delivered in FROZEN mode. The run produces every work product the greenfield package contains. The packaged code matches the delivered fingerprints byte for byte. The package is READY_FOR_OFFLINE_REVIEW, or BLOCKED with each gap named.

**Acceptance Scenarios**:

1. **Given** FROZEN mode, **When** any author role tries to change a delivered file, **Then** the change is refused and recorded, and the delivered fingerprints still match at packaging.
2. **Given** a test that fails on the delivered code, **When** the phase is evaluated, **Then** a defect is filed against the delivered code (not the test) with the failing evidence, and the package is BLOCKED.
3. **Given** a filed defect against frozen code that the owner has accepted as a deviation through the existing owner disposition process, **When** the package is built, **Then** the package can be READY with the deviation listed as a limitation.
4. **Given** a recovered architecture or design that describes behaviour the code does not have, **When** the phase gate runs, **Then** the work product is rejected for disagreeing with the code.

---

### User Story 4 - Delivered code corrected under control (FIX_ALLOWED mode) (Priority: P2)

In FIX_ALLOWED mode the factory may correct the delivered code, but only to resolve a filed defect. Every change:
- is linked to its defect;
- is shown as a difference against the delivered original;
- is re-verified by the same tests.

Delivered files not touched by a fix remain byte-identical. The package contains the delivered baseline, the corrected code and a change report.

**Why this priority**: Owners often want the factory to fix what it finds. That is valuable, but it is only trustworthy once the frozen flow (US3) already produces the evidence.

**Independent Test**: Seed a known defect into a copy of the factory's own HAL code from r164, for example a rollback that turns off an already-running oscillator, and deliver it in FIX_ALLOWED mode. The factory:
- files the defect;
- changes only the lines needed;
- links the change to the defect;
- shows the difference;
- passes all tests.

Files without a defect remain byte-identical.

**Acceptance Scenarios**:

1. **Given** FIX_ALLOWED mode, **When** an author changes delivered code without a filed defect, **Then** the change is refused.
2. **Given** a change that resolves a defect, **When** the package is built, **Then** the change report lists for each changed file:
   - the defect;
   - the original and corrected fingerprints;
   - the difference.
3. **Given** a change that touches code outside the scope, **When** the phase gate runs, **Then** it is rejected.
4. **Given** FIX_ALLOWED mode, **When** a change makes a previously passing test fail, **Then** the change is rejected and the defect stays open.

---

### User Story 5 - ISO 26262 software safety work products for the delivered code (Priority: P2)

For a safety-scoped work order the factory produces the software safety work products for the delivered code:
- the software safety requirements, or the explicit statement that none is allocated yet;
- a software safety analysis draft of the delivered design, covering fault modes, dependent failures and assumptions of use;
- a tool assurance assessment draft, which covers the tools used to verify delivered code.

The drafts are clearly marked as AI-drafted and unapproved, for the owner to review and sign through the existing owner-signed safety documents process. Until the owner signs, the package stays BLOCKED on them, exactly as for greenfield work orders.

**Why this priority**: These are among the "remaining ISO 26262 artifacts" the owner asked for, but the signature process already exists. The new part is drafting them against delivered code.

**Independent Test**: Run a safety-scoped brownfield work order. The package contains both drafts in a drafts area, each with the draft marker. It is BLOCKED on the two signed documents until the owner signs a version through the existing register.

**Acceptance Scenarios**:

1. **Given** a safety-scoped brownfield work order, **When** the safety phase runs, **Then** the drafts analyse the delivered functions in scope, cite the delivered fingerprints, and never claim approval.
2. **Given** unsigned drafts, **When** the package is built, **Then** the package is BLOCKED on the signed documents and lists the drafts for review.
3. **Given** a delivered product the owner has already signed documents for, with an unchanged basis, **When** a new brownfield work order runs, **Then** the signed documents are used as for greenfield work orders.

---

### User Story 6 - Pilot on ST's STM32CubeN6 RCC driver (Priority: P3)

The owner runs a brownfield work order on ST's existing RCC driver (stm32n6xx-hal-driver v1.4.0). The scope is a subset of its about 28,500 lines, comparable to the factory's own RCC scope:
- HSI and HSE oscillator on/off and ready;
- GPDMA1 and ADC12 clock and reset.

The owner sees how a vendor driver fares against independently derived requirements, with every finding and gap named.

**Why this priority**: This is the real-world demonstration. It depends on US1–US3, and on the vendor code's own dependencies being available.

**Independent Test**: Run the pilot in FROZEN mode. The package names ST as the origin and BSD-3-Clause as the licence, with the recorded download fingerprints. It lists every in-scope function with its requirements, tests and findings. It is READY or BLOCKED with every gap named.

**Acceptance Scenarios**:

1. **Given** the ST delivery and the RCC inputs, **When** intake runs, **Then** the scope resolves to the named ST functions, and every other ST function is listed as excluded.
2. **Given** ST code that needs vendor headers or configuration not in the delivery, **When** intake runs, **Then** each missing dependency is named. The work order is BLOCKED until it is supplied; it is never invented.
3. **Given** ST code with timing based on a system tick, **When** verification runs on the simulated target, **Then** the tick dependency is handled by a declared test environment and listed as a limitation.

---

### Edge Cases

- **The delivered files change after intake** (on disk or in a work order): the fingerprints no longer match, so verification and packaging stop as BLOCKED with the changed file named.
- **The delivered code uses a language feature or construct the analysis tools cannot handle:** the affected checks report NOT_MEASURED for those functions. They never report a pass.
- **A reference document is silent on a behaviour the code implements:** a "code with no requirement" finding, marked as needing owner judgement. It is never silently accepted.
- **The same function serves both in-scope and out-of-scope features:** it is in scope, and the out-of-scope paths are listed as not verified.
- **A FIX_ALLOWED change would also be needed outside the scope:** the change is refused, and the defect remains open with that reason.
- **The delivered code already contains tests:** they are recorded as delivered evidence. The factory still writes its own tests from the requirements and reports any delivered test it could not run.
- **The licence forbids modification:** FIX_ALLOWED cannot be selected, and intake rejects the combination.
- **Very large deliveries:** only the scope is analysed. The excluded part is listed by name, not loaded into the analysis.

## Requirements *(mandatory)*

### Functional Requirements

**Intake and delivered baseline**

- **FR-001**: The factory MUST accept a brownfield work order that names the reference documents, the delivered code, its licence and origin, the scope, and the code mode (FROZEN or FIX_ALLOWED).
- **FR-002**: At intake the factory MUST record every delivered file with its fingerprint, and the delivery's licence and origin. It MUST make the delivered baseline read-only to every factory role.
- **FR-003**: The factory MUST resolve the scope to concrete delivered functions. It MUST stop as BLOCKED when a scoped function does not exist, and MUST list out-of-scope functions as excluded.
- **FR-004**: The factory MUST check that the in-scope delivered code builds with the declared dependencies before any analysis. It MUST stop as BLOCKED with the build evidence when it does not.
- **FR-005**: The factory MUST refuse a delivery without a stated licence and origin, and MUST refuse FIX_ALLOWED when the stated licence forbids modification.
- **FR-006**: The factory MUST re-check the delivered fingerprints before verification and at packaging, and MUST stop as BLOCKED on any mismatch that is not an approved FIX_ALLOWED change.

**Independent requirements and traceability**

- **FR-007**: The factory MUST derive the software requirements from the reference documents and the scope only. The requirement author MUST NOT have access to the delivered code, and the requirements MUST be frozen before tracing to the code starts.
- **FR-008**: The factory MUST trace every requirement to delivered code and every in-scope delivered function to requirements. It MUST report each gap as a conformance finding: code with no requirement, a requirement with no code, or code contradicting a requirement or reference document (with document and page).
- **FR-009**: Conformance findings MUST appear in the package with their evidence. A finding that the owner has not dispositioned MUST keep the package BLOCKED.

**Remaining SWE work products**

- **FR-010**: The factory MUST produce, for the delivered code, the same set of SWE.1–SWE.6 work products, traceability matrices, verification reports, defects, limitations and package contents as a greenfield work order.
- **FR-011**: The recovered architecture and detailed design MUST be checked against the delivered code by deterministic checks. A work product describing structure or behaviour the code does not have MUST be rejected.
- **FR-012**: Unit, integration and qualification tests MUST be derived from the requirements and unit specifications, not from the code's observed behaviour. A test failure on delivered code MUST be filed as a defect against the code.
- **FR-013**: In FROZEN mode no factory role may change a delivered file. Any attempt MUST be refused and recorded.
- **FR-014**: In FIX_ALLOWED mode a change to delivered code MUST:
  - resolve a filed defect;
  - stay within the scope;
  - be re-verified by the full test set.

  Each changed file MUST be reported with the defect, its original and corrected fingerprints and the difference. Untouched delivered files MUST remain byte-identical.

**Safety work products**

- **FR-015**: For a safety-scoped work order the factory MUST produce:
  - the software safety requirements, or an explicit statement that none is allocated;
  - an AI-drafted software safety analysis of the delivered in-scope functions;
  - an AI-drafted tool assurance assessment.

  Each draft MUST be marked as unapproved and kept apart from the owner-signed documents.
- **FR-016**: Brownfield work orders MUST use the existing owner-signed safety documents process unchanged: only signed, unaltered documents with a matching basis count, and the package stays BLOCKED until then.

**Package, honesty and compatibility**

- **FR-017**: The package MUST state the code mode and the delivered origin, licence and fingerprints. In FIX_ALLOWED mode it MUST also contain the change report.
- **FR-018**: The factory MUST NOT claim compliance, certification, qualification or safety approval in any brownfield work product. Missing evidence MUST stay NOT_MEASURED or BLOCKED.
- **FR-019**: Existing greenfield work orders, their workflow, gates and packages MUST behave exactly as before.
- **FR-020**: Reference-standard text (ISO, MISRA) MUST NOT be copied into the repository or the work products.

### Key Entities

- **Brownfield Work Order:** a work order with a delivered baseline, scope and code mode, in addition to the greenfield inputs.
- **Delivered Baseline:** the delivered files, each with its fingerprint, plus the licence, origin and intake time. It is read-only.
- **Scope:** the named in-scope functions or features, resolved to delivered functions; the excluded remainder is listed.
- **Code Mode:** FROZEN or FIX_ALLOWED, fixed at intake for the life of the work order.
- **Conformance Finding:** its kind (no requirement, no code, contradiction), the function, the requirement or document page, the evidence and the owner disposition state.
- **Code Change Record** (FIX_ALLOWED only): for each changed file, the defect, the original and corrected fingerprints, the difference and the re-verification result.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: With the factory's own r170 LL code delivered in FROZEN mode, a brownfield work order produces every work product a greenfield package contains, and the packaged code matches the delivered fingerprints in 100 % of files.
- **SC-002**: Each of five seeded mismatch kinds is reported as a conformance finding of the right kind, naming the function: wrong bit mask, missing function, extra function, wrong register, overwritten unrelated bit. 5 of 5.
- **SC-003**: In FIX_ALLOWED mode, 100 % of changed lines belong to a change linked to a defect. 100 % of untouched delivered files are byte-identical after the run.
- **SC-004**: 100 % of in-scope delivered functions are traced to a requirement or reported, and 100 % of requirements are traced to code or reported.
- **SC-005**: Every intake failure (missing function, missing licence, build failure, missing dependency) stops the work order before analysis, with a finding that names the cause. 0 unnamed failures.
- **SC-006**: The ST RCC pilot ends READY_FOR_OFFLINE_REVIEW or BLOCKED with every gap named, and its package states origin, licence and fingerprints.
- **SC-007**: A brownfield work order with an LL scope the size of r170 finishes within 60 minutes. The comparable greenfield r170 took about 35 minutes.
- **SC-008**: All existing greenfield tests and the reliability benchmark still pass unchanged.

## Assumptions

- **Delivery format:** the owner brings delivered code as a directory or archive with a licence statement and an origin (URL or supplier). The first pilot is the ST download already recorded under the factory's data directory with its provenance.
- **Default code mode:** FROZEN; FIX_ALLOWED is chosen explicitly per work order.
- **Reference documents:** the existing RCC inputs (RM0486 Rev 4 chapter 14, DS14791 Rev 9) and their section index are reused. Other peripherals need their own reference sections, as for greenfield work orders.
- **Same agents, gates and limits:** the existing agent roles, models (Codex Sol 6.1 authors, Claude Opus 5.5 inspectors), tool restrictions, budgets, assurance (observe-only today), continuous reliability process and release packaging are reused. Brownfield-specific checks are added; existing ones are not weakened.
- **Simulator:** target verification uses the existing simulated Cortex-M55 and behavioural RCC model. Delivered code that needs hardware or timing the model lacks is verified as far as the model allows, and the rest is listed as a limitation.
- **Vendor dependencies:** vendor dependencies the delivered code needs (for ST: the CMSIS device header and a HAL configuration) are supplied as declared, fingerprinted inputs from the vendor's official source. They are never written by an agent.
- **Owner-only decisions:** defect dispositions, accepted deviations and safety document signatures remain owner decisions through the existing processes.
- **Out of scope:** automatic choice of scope; delivered code in languages other than C; hardware-in-the-loop; merging fixes back to the vendor.
