# Feature Specification: Preserve validated artifacts across runs

**Feature Branch**: `feat/021-preserve-validated-artifacts` (specified on the feature 020 worktree; implementation on its own branch)
**Created**: 2026-11-13
**Status**: Draft
**Input**: Owner rule 2026-11-13: "whenever a run finish and need to run again due to any reason, the artifacts that was
already inspected and validated must be preserved between runs, it can be changed if other dependencies requires to,
otherwise must be kept, and on which swe process we need to analyze how to define the granularity of artifacts that this
rule can be applied reasonably". Analysis: [granularity-analysis.md](granularity-analysis.md). First application
(SWE.1 functional, per requirement): feature 020 decision log D36/D39/D40 (`lrtx/swe1_carry.py`).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A rerun keeps every item that was already validated (Priority: P1)

The factory reruns an order (a retry after a failure, a new round after a factory fix, a recovery after a crash). Every
item of the earlier run that passed its inspection and whose dependencies did not change is taken over unchanged with its
verdict; only invalidated items are authored and inspected again; the set-level checks run once on the result.

**Why this priority**: it is the owner's rule; today a rerun re-authors and re-judges whole phases (e.g. UART C03 -> C04
re-judged 300 requirements to fix 20), wasting GPU hours and letting good content regress.

**Independent Test**: run an order to a phase failure, change one input that only some items depend on, rerun: exactly
the dependent items are re-authored/re-inspected; all others are byte-identical with the same verdict and carry a record
naming the source run.

**Acceptance Scenarios**:

1. **Given** a finished run whose phase failed at the set level, **When** the order reruns with unchanged inputs and
   factory rules, **Then** no item is re-authored or re-inspected and only the set-level checks run.
2. **Given** a factory rule change that names some items (e.g. D40 REFERENCE_BY_ID), **When** the order reruns, **Then**
   only the named items are reworked and every other item keeps its content and verdict.
3. **Given** a changed upstream artifact (e.g. one SWR), **When** a downstream phase reruns, **Then** only the downstream
   items that depend on that artifact are invalidated (impact walk), the rest are carried.
4. **Given** an input the whole phase depends on changed (e.g. the governance inventory), **When** the order reruns,
   **Then** nothing is carried (`INPUT_CHANGED`) and the reason is recorded.

---

### User Story 2 - A carried item is auditable (Priority: P1)

An assessor reading a package can tell, for every artifact, whether it was produced in this run or carried, from which
run and record, against which dependency set, and why it was still valid.

**Why this priority**: ASPICE evidence must stay traceable; a carried verdict without provenance would be a silent claim.

**Independent Test**: inspect a carried item's record: it names source work order, source record sha, item content sha,
dependency-set sha and the validator/inspection versions that re-confirmed it.

**Acceptance Scenarios**:

1. **Given** a package with carried items, **When** it is assembled, **Then** a carry manifest lists every carried item
   with its provenance and the package never labels a carried verdict as a direct verdict of this run.
2. **Given** a carried item whose source record was altered after the fact, **When** the rerun starts, **Then** the item is
   not carried (`SOURCE_RECORD_CHANGED`).

---

### User Story 3 - Preservation works in every SWE phase at a reasonable granularity (Priority: P2)

Each process has a defined preservation unit: SWE.1 per requirement, SWE.2 per interface function / design decision,
SWE.3 per unit, SWE.4 per unit test with its run result, SWE.5 per integration test, SWE.6 per requirement scenario.

**Why this priority**: SWE.1 (P1 scope) already proves the rule; the later phases are where reruns cost the most.

**Independent Test**: per phase, a rerun after one item's dependency changed re-does only that item (and its set checks).

**Acceptance Scenarios**:

1. **Given** SWE.4 tests whose unit code is unchanged, **When** the phase reruns, **Then** their PASS run results carry,
   bound to code, test and tool-image hashes rather than timestamps.
2. **Given** an SWE.2 change to one interface, **When** SWE.2 reruns, **Then** the other interfaces' design content is kept.

### Edge Cases

- The source run used another model or profile: content carries only if the dependency set excludes the model (author
  answers are content, re-validated by current validators); inspector verdicts carry only with the same inspection
  criteria and packet semantics.
- Validators changed since the source run: every carried item is re-validated by the current deterministic checks; a new
  finding releases exactly that item (D39 behaviour).
- Two candidate source runs: the order names them in priority order; the first existing, intact source wins (D39).
- QM orders bind the work order id into packet scope today: the semantic key must exclude run identity (FR-004).
- A carried set must still pass the set-level checks; a set-level failure never invalidates items wholesale, it routes
  findings to the named items.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The factory MUST keep a validated-item store keyed by (phase, item key, item content sha, dependency-set
  sha) holding author answers and inspector verdicts with their provenance.
- **FR-002**: A rerun MUST look up every item of the phase in the store from the sources the order names and carry an item
  only when its dependency-set sha is unchanged and its source record is intact.
- **FR-003**: Every carried item MUST be re-validated by the current deterministic validators; a finding releases only that
  item for rework.
- **FR-004**: The item key MUST be run-identity-free: the semantic part of the packet input hash is separated from run
  context, and the QM scope binding no longer includes the work order id; lessons offered are pinned or excluded.
- **FR-005**: Each phase MUST declare its preservation unit and the dependencies of each unit (SWR -> interface/unit ->
  UT/IT/robot case, by content sha); the impact walk (assurance ImpactGraph) decides which units a change invalidates,
  replacing whole-phase staleness.
- **FR-006**: A non-PASS phase MUST keep its valid items; only invalidated items are re-authored/re-inspected; then the
  phase is re-frozen and its set-level checks run once.
- **FR-007**: Tool evidence (run_unit, run_renode, run_robot, coverage) MUST be bound to code, test and tool-image hashes
  per test id, so an unchanged test's PASS carries.
- **FR-008**: Every package MUST include a carry manifest (item, source order, source record sha, dependency-set sha,
  re-validation result); a carried verdict is never presented as a direct verdict of the run.
- **FR-009**: Carry MUST be refused with a recorded reason when the source record changed, a whole-phase input changed or
  the inspection criteria changed (`SOURCE_RECORD_CHANGED`, `INPUT_CHANGED`, `CRITERIA_CHANGED`).
- **FR-010**: Existing behaviour stays available: an order without carry sources runs exactly as today (register-level
  ladder orders byte-identical).

### Key Entities

- **Validated item**: phase, item key, content, content sha, verdicts, dependency-set sha, provenance (order, record sha).
- **Dependency set**: the content shas of the inputs/upstream items/rules an item depends on.
- **Carry source**: an earlier run named by the order, in priority order.
- **Carry manifest**: per package, every carried item and why it was valid.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: After a set-level-only failure, a rerun re-judges 0 items per-item and only the set checks (SWE.1 UART:
  ~300 per-requirement judgements avoided per rerun).
- **SC-002**: After a change touching k of n items, at most k items (plus their impact-walk dependents) are re-authored.
- **SC-003**: 100% of carried items appear in the carry manifest with complete provenance; 0 carried verdicts are labelled
  as direct verdicts.
- **SC-004**: Register-level ladder orders without carry sources produce byte-identical packets and workproducts.
- **SC-005**: Guarded benchmark metrics (D34) never regress because of a carried item.

## Assumptions

- Carry applies within one component lineage (same module/driver); cross-module reuse is out of scope.
- The SWE.1 functional carry (`lrtx/swe1_carry.py`) is the reference implementation and is generalised, not replaced.
- Set-level judgements (SQ, checklists, gates) remain per baseline by nature.
- Implementation order follows the analysis priority: store + semantic key (FR-001/004), partial phase carry (FR-006),
  per-phase units and impact walk (FR-005), tool evidence binding (FR-007).
