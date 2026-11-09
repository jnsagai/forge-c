# Feature Specification: Factory-prepared run inputs

**Feature Branch**: `feat/019-factory-prepared-inputs`

**Created**: 2026-11-09

**Status**: Draft

**Input**: User description: "Factory-prepared run inputs (feature 019). Owner 2026-11-09: 'I want that Omniverse to be
fully responsible to prepare all the inputs for the run, not you.' and 'implement first the low level driver, then the
whole driver for the same model' (per peripheral: LL lineage SWE.1..SWE.6, then the HAL lineage built on that LL order;
ladder WWDG LL -> WWDG HAL -> SPI LL -> SPI HAL -> TIM LL -> TIM HAL). Today Claude hand-edits the campaign template in
the owner-lane deploy package and switches the active driver when one finishes. Goal: the ladder is versioned factory
source, the deploy derives the campaign from it, the line sequences lineages itself, the allowance carries the HAL
lineages, a step without its work-order spec is held and reported as an input gap (never hand-written by Claude). Must
keep: one GPU run at a time, mission E caps and Nov19 deadline, CRE gate before any deploy, signed controls and the
production Line Conductor untouched, rollback drops lineages it cannot authorize, the current WWDG LL run continues
from its passed SWE.1 without rerun."

## Context

The owner lane on Omniverse2 runs driver work orders unattended: the line chains phases (SWE.1 -> SWE.6), retries
failures, and marks a lineage done when its last phase passes. What it cannot do by itself today is decide **which
driver to build next and with which phases**. That decision lives in a campaign file that Claude edits by hand inside
the deploy package (status ACTIVE / ON_HOLD, phase list) and switches whenever a driver finishes. The owner wants the
factory to own every input of a run. This feature moves the driver ladder into versioned factory source and lets the
line walk it alone.

## Owner amendment 2026-11-09 ~14:00 (phase stages)

"Before going to SW2, I want to exercise a bit more SW1 with other examples. As I told you, we must go now for HAL
example on WWDG, Then we go for the SW1 on intermediate model, then a complex model. just when we are sure that SW1 is
really stable, then we can go for the next one."

- The ladder runs one **phase stage** across all its steps: today SWE.1 for WWDG LL -> WWDG HAL -> SPI LL -> TIM LL.
- The owner moves the stage to the next phase (a source change, gated and deployed like code) once SWE.1 is stable.
- In a stage that ends before SWE.6, a HAL step builds on an LL order of its peripheral that already passed all six
  phases (WWDG LL `WO-F014-SWE6-WWDGL-20261103-L29`); the factory re-checks those six gates at prepare (ADR-0009).
- SPI HAL and TIM HAL are not in this stage (no specs; they stay input gaps for feature 016).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The ladder is factory source, not a hand edit (Priority: P1)

The owner states the build order once: per peripheral the low-level (LL) driver through all six phases, then the full
(HAL) driver built on that LL result; peripherals in the order WWDG, SPI, TIM. The order lives in the factory's own
versioned source, passes the same independent gate as code, and every deploy builds the line's campaign from it. Nobody
edits a deploy package to change what runs.

**Why this priority**: it removes the manual step the owner objected to; without it every other story still needs a
hand-edited input.

**Independent Test**: deploy a revision whose ladder lists WWDG LL (six phases) and WWDG HAL; inspect the installed
campaign: it equals the one derived from source, and the deploy package holds no hand-written campaign.

**Acceptance Scenarios**:

1. **Given** a revision with the ladder in source, **When** the deployer prepares the deploy, **Then** the campaign it
   installs is derived from that source alone, and the deploy record names the source revision it came from.
2. **Given** someone edits a campaign file inside a deploy package, **When** the next deploy runs, **Then** the edit has
   no effect (the campaign is regenerated from source) and the difference is recorded.
3. **Given** a ladder change (e.g. a new peripheral), **When** it is proposed, **Then** it reaches the line only through
   a commit, the independent gate and the normal deploy.

---

### User Story 2 - The line walks the ladder by itself (Priority: P1)

When a lineage passes its last phase, the line starts the next step of the ladder with no human or Claude action: after
the WWDG LL passes SWE.6 the WWDG HAL starts on that LL result; after the WWDG HAL passes SWE.6 the SPI LL starts (not
built on WWDG), and so on. One step runs at a time.

**Why this priority**: the owner's ladder only becomes autonomous when the switch between drivers is the line's job.

**Independent Test**: on a test line with two ladder steps, mark the first step's last phase PASS; the line places the
second step's first order within one supervision cycle, with the right "builds on" reference (HAL) or none (next LL).

**Acceptance Scenarios**:

1. **Given** WWDG LL passed SWE.6, **When** the line plans, **Then** it places the WWDG HAL SWE.1 order that builds on
   exactly that passing LL order.
2. **Given** WWDG HAL passed SWE.6, **When** the line plans, **Then** it places the SPI LL SWE.1 order, which builds on
   nothing.
3. **Given** a step is still running or retrying, **When** the line plans, **Then** no later step starts (one step at a
   time) and the waiting steps show why they wait.
4. **Given** a step stops (escalated, parked, retries exhausted), **When** the line plans, **Then** the later steps keep
   waiting and the floor shows the ladder blocked at that step.

---

### User Story 3 - A missing input is a visible gap, not a manual fix (Priority: P2)

Some steps have no work-order specification yet (today: SPI HAL and TIM HAL). When the ladder reaches such a step the
line holds it and reports an **input gap** on the floor (which step, which input is missing, who produces it: the
peripheral onboarding stage). The line does not skip the step and Claude does not write the specification.

**Why this priority**: the owner asked the factory to prepare all inputs; a gap must be visible so it is closed by the
factory (feature 016), not by hand.

**Independent Test**: a ladder whose second step names a specification that does not exist; after the first step
passes, the floor shows the second step as an input gap and no order is placed for it or for any later step.

**Acceptance Scenarios**:

1. **Given** the ladder reaches SPI HAL with no SPI HAL specification, **When** the line plans, **Then** the step is held
   with reason INPUT_GAP naming the missing specification, and the floor supervisor station shows it.
2. **Given** the missing specification later appears in a deployed revision, **When** the line plans, **Then** the step
   starts on the LL result it depends on, without other changes.

---

### User Story 4 - The allowance follows the ladder (Priority: P2)

The owner-lane allowance authorizes exactly the orders of the ladder's lineages: LL orders build on nothing; a HAL order
may only build on an SWE.6 order of its own peripheral's LL lineage that passed all six phases. Lineages the running
source does not know are dropped from the campaign (e.g. after a rollback) instead of placed and refused.

**Why this priority**: without it a HAL step is refused at admission even when the ladder reaches it.

**Independent Test**: validate one HAL order built on its LL SWE.6 order (accepted) and on any other order (refused);
roll back to a source without the HAL lineage and check the campaign no longer lists it.

**Acceptance Scenarios**:

1. **Given** a HAL order building on its own LL lineage's SWE.6 order, **When** it is admitted, **Then** it is accepted.
2. **Given** a HAL order building on another peripheral, an earlier LL phase or nothing, **When** it is admitted,
   **Then** it is refused.

---

### Edge Cases

- The ladder changes while a step runs: the running order finishes on its revision; the new ladder applies to the next
  placement; a step already passed is never rerun.
- A lineage that passed only some phases when its phase list grows (WWDG LL passed SWE.1 under a SWE.1-only campaign):
  the line continues from the last passed phase (SWE.2 resumes from the passed SWE.1 order), no rerun.
- Two ladder steps for the same peripheral and layer: refused at gate time (each step names a unique lineage).
- A ladder step names a lineage the allowance does not know: refused at gate/deploy preparation, not at run time.
- Rollback to an older source: lineages unknown to it are dropped from the campaign; passed results stay recorded.
- The LL result a HAL step builds on is superseded by a newer passing LL order: the HAL uses the newest passing LL
  SWE.6 order at the time it starts and records which one.
- The mission deadline or caps are reached mid-ladder: the line stops placing and reports it; no cap is raised.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The driver ladder (ordered steps; each step = peripheral, layer LL or HAL, work-order specification,
  phases) MUST be part of the factory's versioned source and change only through a commit and the independent gate.
- **FR-002**: Each deploy MUST derive the line's campaign from the ladder of the revision being deployed; a hand-edited
  campaign inside a deploy package MUST NOT influence what the line runs, and a difference MUST be recorded.
- **FR-003**: The line MUST start a ladder step only when the previous step passed its last phase; at most one ladder
  step runs at a time.
- **FR-004**: A HAL step MUST build on the newest LL order of the same peripheral that passed all six phases and record
  that reference; an LL step MUST build on nothing.
- **FR-005**: The line MUST continue a lineage from its last passed phase when the lineage's phase list grows; no
  passed phase is rerun.
- **FR-006**: A step whose work-order specification is missing MUST be held with reason INPUT_GAP (step, missing input,
  producing stage), shown on the floor, and MUST block later steps.
- **FR-007**: The owner-lane allowance MUST authorize the orders of every ladder lineage and refuse a HAL order unless
  it builds on an SWE.6 order of its own LL lineage.
- **FR-008**: A deploy of a source that does not know a lineage MUST drop that lineage from the campaign.
- **FR-009**: The floor MUST show the ladder: each step's state (done, running, waiting for which step, input gap,
  blocked) and which step runs next.
- **FR-010**: Claude MUST NOT write run inputs (campaign files, work-order specifications) as a manual step; a missing
  input is reported, and closing it is the factory's job (onboarding stage) or an owner decision.
- **FR-012**: The ladder MUST run one owner-chosen phase stage across all steps (FR-003 "last phase" = the stage's
  last phase); only the owner moves the stage forward.
- **FR-013**: In a stage that ends before SWE.6, a HAL step MUST build on a named LL order of its own peripheral that
  passed all six phases; no other lineage may use it.
- **FR-011**: Mission E caps, the Nov 19 deadline, the CRE gate before deploy, signed controls and the production Line
  Conductor MUST stay unchanged.

### Key Entities

- **Driver ladder**: the owner's ordered build plan; steps in order; versioned with the factory source.
- **Ladder step**: one lineage = peripheral + layer + work-order specification + phases; for HAL, the LL step it builds
  on.
- **Campaign (derived)**: the line's run plan generated from the ladder at deploy; records the source revision.
- **Input gap**: a held step with the missing input and the stage that must produce it.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: From this feature's deploy until the WWDG HAL starts, zero hand edits of campaign or work-order inputs are
  needed (checked in the deploy records and package hashes).
- **SC-002**: After a step passes its last phase, the next ladder step is placed within one supervision cycle (about
  2 minutes) without human action.
- **SC-003**: 100 % of HAL orders build on an LL order of the same peripheral that passed all six phases; 0 HAL orders
  are admitted otherwise (tests and admission records).
- **SC-004**: A ladder step without its specification is visible on the floor as an input gap within one floor refresh,
  and no later step is placed.
- **SC-005**: The WWDG LL lineage continues at SWE.2 from the passed SWE.1 order (L44F) with zero reruns of SWE.1.

## Assumptions

- The ladder steps after WWDG HAL use the existing LL examples (SPI LL `0011l-st-cube-spi-swe1-gen`, TIM LL
  `0013l-st-cube-tim-swe1-gen`); SPI HAL and TIM HAL specifications do not exist and stay input gaps until feature 016
  produces them.
- GPIO and USART lineages stay in the allowance but are not on the ladder (owner ladder 2026-11-09).
- "Model" in the owner's message means the peripheral (WWDG), i.e. the HAL of the same peripheral.
- The line's existing phase chaining, retries, recovery and DONE detection are reused unchanged.
- Producing missing work-order specifications (onboarding) is out of scope (feature 016).
