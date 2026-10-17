# Feature 006 — Owner addendum 2026-10-17: SWC structure, unit specifications, Doxygen and traceability matrices

**Source:** owner message, 2026-10-17 (verbatim):

> additional requirements: HAL and LL shall be separate component. They should be represented by one single SWC each.
> The detailed designed shall be also done using plantuml diagrams, and each software unit shall have unit
> specification using reqIF. the code must be documented using doxygen with traceability to the software unit. the
> traceability shall be sw requirements allocated in the architectural diagrams. the sw unit specifications shall be
> traceable to the sw requirement. the code shall have the reference to the sw unit specification. the unit test is
> traceable to the sw unit specifications. the integration test is traceable to the architecture design. the software
> validation tests are traceable to the sw requirements. i want to have one traceability matrix for each traceability
> just described

**Status:** owner-approved additional scope for Feature 006.

The authored `spec.md`, `requirements.csv`, `tasks.md` and `planned-traceability.csv` stay unchanged, because
`validate_spec.py` pins 72 FR. These requirements extend them under their own IDs.

The scope is SWE.2–SWE.6 engineering work products only, with no SUP/MAN workflow. These requirements extend
EASA-FR-026 (two-way trace), EASA-FR-029/030 (architecture/PlantUML), EASA-FR-040 (code against detailed design),
EASA-FR-042 (tests exercise the allocated API) and EASA-FR-052/056 (trace cites executed artifacts).

## Requirements

| ID | Process | Requirement |
|---|---|---|
| EASA-OR-001 | SWE.2 | The LL driver and the HAL driver SHALL be separate software components. Each is represented by exactly one SWC (`<<SWC>>` element) in the static architecture diagram: `SWC_LL` and `SWC_HAL`. A HAL work order shows the provided LL as `SWC_LL` and does not re-implement it. |
| EASA-OR-002 | SWE.2 | Every software requirement SHALL be allocated to at least one SWC, and the allocation SHALL be stated in the architecture diagram itself (an `Allocated:` note on the SWC). Every interface between architecture elements SHALL carry an interface id `IF-nn`. |
| EASA-OR-003 | SWE.3 | The detailed design of every software unit SHALL be given as a PlantUML diagram (`workproducts/SWE.3/detailed_design/<SWU-id>.puml`) that renders without error. |
| EASA-OR-004 | SWE.3 | Every software unit SHALL have a unit specification in ReqIF (`workproducts/SWE.3/unit_specifications/<SWU-id>.reqif`, XSD-valid). It is generated deterministically from the authored `workproducts/SWE.3/unit_specifications.md`. |
| EASA-OR-005 | SWE.3 | Every unit specification item (`USPEC-…`) SHALL trace to at least one SW requirement allocated to the unit's SWC. Every SW requirement allocated to an SWC SHALL be refined by at least one unit specification item. |
| EASA-OR-006 | SWE.3 | The code SHALL be documented with Doxygen. Every function SHALL carry `@unit <SWU-id>` and `@spec <USPEC-id…>` of that unit. Doxygen SHALL process the sources without warnings for these tags, and every unit specification item SHALL be referenced by code. |
| EASA-OR-007 | SWE.4 | Every unit test case SHALL state `@verifies <USPEC-id…>`. Every unit specification item SHALL be verified by at least one executed, passing unit test case. |
| EASA-OR-008 | SWE.5 | Every integration test case SHALL state `@verifies <IF-id or SWC id…>` of the architecture. Every architecture interface SHALL be verified by at least one executed, passing integration test case. |
| EASA-OR-009 | SWE.6 | Every software validation (Robot) test SHALL be traced to SW requirements. Every SW requirement SHALL be verified by at least one executed, passing validation test. |
| EASA-OR-010 | SWE.2–SWE.6 | One traceability matrix SHALL be produced for each relation in OR-002 and OR-005 to OR-009, six in total, as CSV plus Markdown under `traceability/`. Each is generated deterministically from the work products and executed results (never authored by an agent), with uncovered items listed. |
| EASA-OR-011 | SWE.2–SWE.6 | A missing link in any of the six relations SHALL fail the corresponding phase's deterministic check, giving a precise issue code (bounded rework, existing gate semantics). |

## The six matrices (EASA-OR-010)

| # | Relation | File |
|---|---|---|
| 1 | SW requirement → SWC (allocation in the architecture diagram) | `traceability/matrix_1_swr_to_architecture.csv/.md` |
| 2 | Unit specification item → SW requirement | `traceability/matrix_2_unitspec_to_swr.csv/.md` |
| 3 | Code (function) → unit specification item | `traceability/matrix_3_code_to_unitspec.csv/.md` |
| 4 | Unit test case → unit specification item | `traceability/matrix_4_unittest_to_unitspec.csv/.md` |
| 5 | Integration test case → architecture element (IF/SWC) | `traceability/matrix_5_integrationtest_to_architecture.csv/.md` |
| 6 | Validation test → SW requirement | `traceability/matrix_6_validationtest_to_swr.csv/.md` |

## Tasks

- [ ] **EASA-T073 [P0]** Implement the architecture model parser (SWC, allocation notes, interfaces) and the SWC/allocation check. **Refs:** EASA-OR-001, EASA-OR-002, EASA-OR-011. **Acceptance:** EASA-AT-085, EASA-AT-086. **Done only with:** committed implementation, deterministic tests and checked hashes.
- [ ] **EASA-T074 [P0]** Implement the unit-specification parser, the per-unit ReqIF export with XSD validation and the PlantUML detailed-design check. **Refs:** EASA-OR-003, EASA-OR-004, EASA-OR-005. **Acceptance:** EASA-AT-087, EASA-AT-088. **Done only with:** committed implementation, deterministic tests and checked hashes.
- [ ] **EASA-T075 [P0]** Implement the Doxygen configuration and run, and the code-to-unit-specification check. **Refs:** EASA-OR-006. **Acceptance:** EASA-AT-089. **Done only with:** committed implementation, deterministic tests and checked hashes.
- [ ] **EASA-T076 [P0]** Implement the unit/integration/validation test trace extraction against executed results. **Refs:** EASA-OR-007, EASA-OR-008, EASA-OR-009. **Acceptance:** EASA-AT-090, EASA-AT-091. **Done only with:** committed implementation, deterministic tests and checked hashes.
- [ ] **EASA-T077 [P0]** Generate the six traceability matrices with coverage gaps. **Refs:** EASA-OR-010. **Acceptance:** EASA-AT-092. **Done only with:** committed implementation, deterministic tests and checked hashes.
- [ ] **EASA-T078 [P0]** Integrate into the SWE.2–SWE.6 workflow: prompts, required outputs, checklist checks, gate hooks and package inventory. **Refs:** EASA-OR-001 to EASA-OR-011. **Acceptance:** EASA-AT-093. **Done only with:** committed implementation, deterministic tests and checked hashes.
- [ ] **EASA-T079 [P0]** Run real DeepSeek LL then HAL work orders on the new revision and report the matrices or the blockers. **Refs:** EASA-OR-001 to EASA-OR-011. **Acceptance:** EASA-AT-094. **Done only with:** committed implementation, deterministic tests and checked hashes.

## Acceptance tests

- **EASA-AT-085 [INTEGRATION]** *Given/when:* An architecture with two `<<SWC>>` elements for the HAL, or the LL and HAL merged into one SWC. *Then:* `ARCH:SWC_COUNT` / `ARCH:LAYER_NOT_SEPARATE` fails SWE.2. **Trace:** EASA-T073, EASA-OR-001.
- **EASA-AT-086 [INTEGRATION]** *Given/when:* An SWR without an `Allocated:` entry in the diagram, or an unlabeled connection. *Then:* `ARCH:SWR_NOT_ALLOCATED` / `ARCH:INTERFACE_WITHOUT_ID`. **Trace:** EASA-T073, EASA-OR-002.
- **EASA-AT-087 [INTEGRATION]** *Given/when:* A unit without a PlantUML design, or a design that fails to render. *Then:* `UNIT:DESIGN_MISSING` / `UNIT:DESIGN_RENDER_FAILED`. **Trace:** EASA-T074, EASA-OR-003.
- **EASA-AT-088 [INTEGRATION]** *Given/when:* A USPEC tracing to an SWR not allocated to its SWC, or an allocated SWR refined by no USPEC. *Then:* `UNIT:SPEC_TRACES_UNALLOCATED_SWR` / `UNIT:SWR_NOT_REFINED`. The ReqIF of each unit is XSD-valid. **Trace:** EASA-T074, EASA-OR-004, EASA-OR-005.
- **EASA-AT-089 [INTEGRATION]** *Given/when:* A function without `@unit`/`@spec`, a tag naming an unknown unit or spec, or a USPEC no code references. *Then:* `CODE:UNDOCUMENTED_FUNCTION` / `CODE:UNKNOWN_SPEC_REF` / `CODE:SPEC_NOT_IMPLEMENTED`. **Trace:** EASA-T075, EASA-OR-006.
- **EASA-AT-090 [INTEGRATION]** *Given/when:* A USPEC verified only by a test that did not run or failed. *Then:* `UT:SPEC_NOT_VERIFIED`. A tag naming an unknown USPEC gives `UT:UNKNOWN_SPEC_REF`. **Trace:** EASA-T076, EASA-OR-007.
- **EASA-AT-091 [INTEGRATION]** *Given/when:* An interface with no executed passing integration test, or a validation test traced to an unknown SWR. *Then:* `IT:INTERFACE_NOT_VERIFIED` / `VT:UNKNOWN_SWR`. **Trace:** EASA-T076, EASA-OR-008, EASA-OR-009.
- **EASA-AT-092 [INTEGRATION]** *Given/when:* A complete, consistent work-product set, then the same set with one link removed. *Then:* Six matrices are generated byte-identically on rerun. The removed link appears as an uncovered row and its phase check fails. **Trace:** EASA-T077, EASA-OR-010, EASA-OR-011.
- **EASA-AT-093 [INTEGRATION]** *Given/when:* The SWE.2–SWE.6 gates on a workspace missing the new outputs. *Then:* `MISSING_REQUIRED_OUTPUT` for the new files and checklist checks FAIL. The existing 002/004 regression stays green. **Trace:** EASA-T078.
- **EASA-AT-094 [E2E]** *Given/when:* Real DeepSeek LL and HAL work orders. *Then:* The six matrices are present in the sealed package with measured coverage, or the run is BLOCKED with the exact failing relation. No completion is claimed without the package. **Trace:** EASA-T079.
