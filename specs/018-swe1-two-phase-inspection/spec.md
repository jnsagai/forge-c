# Feature Specification: Two-phase SWE.1 inspection (per requirement, then the complete set)

**Feature Branch**: `feat/018-swe1-two-phase-inspection`

**Created**: 2026-11-09

**Status**: Draft

**Input**: Owner 2026-11-09: "for the inspection, i want the inspector and rework be divided in 2 phases, one in which
the inspection and rework cycle will be done requirement per requirement without modifying others, and after that
inspector and rework phase for the complete set. use this guideline
https://github.com/jnsagai/forge-c/blob/main/docs/SWE1-REQUIREMENTS-QUALITY-GUIDELINE.md"

Owner decisions recorded with the request (2026-11-09):

- A requirement that still has per-requirement findings after its rework rounds is **carried to the set phase**; the
  existing SWE.1 checklist gate decides (it does not block before the set phase).
- The set phase judges the **existing SWE1-01..08 checklist (the gate) plus SQ-01..10** of the guideline as additional
  set findings that route to rework.
- Delivery as a Spec Kit feature: spec, plan and tasks first, then implementation with tests and the CRE gate.

Guideline: `docs/SWE1-REQUIREMENTS-QUALITY-GUIDELINE.md` v1.0 (main `248e423a`), copied unchanged into this branch.
Individual quality (IQ-01..IQ-12), set quality (SQ-01..SQ-10), finding shape and dispositions (section 4).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Each requirement is inspected and repaired on its own (Priority: P1)

After the SWE.1 author has produced a complete requirement set, every software requirement (SWR) is judged on its
own against the individual-quality criteria (IQ-01..IQ-12). A requirement with a correctable defect is reworked by
the author alone; no other requirement changes. Reworked requirements are re-judged until they pass or their rounds
are used.

**Why this priority**: Whole-set inspection of 100+ requirements gives coarse findings that route to whole register
groups; the author then rewrites many correct requirements and new defects appear (owner lane L40-L43, F017 trial
findings). Fixing one requirement at a time keeps good requirements stable and makes each finding actionable.

**Independent Test**: On a frozen SWE.1 set with one seeded defective requirement (e.g. two obligations in one
"shall"), phase 1 reports exactly that requirement, the rework changes only that requirement's statement, every other
requirement is byte-identical, and the re-judgement passes.

**Acceptance Scenarios**:

1. **Given** an assembled SWE.1 set, **When** phase 1 runs, **Then** every SWR receives one individual verdict with
   findings in the guideline shape (`requirement_id / quality_id / severity / evidence / required_action`).
2. **Given** an SWR with a CORRECTABLE or BLOCKING finding, **When** phase 1 rework runs, **Then** only that SWR's
   statement (and its own metadata) may change; any change to another SWR is refused before it is recorded.
3. **Given** a reworked SWR, **When** the next phase-1 round runs, **Then** only reworked SWRs are re-judged; passed
   SWRs are not re-inspected.
4. **Given** an SWR whose rounds are used and still has findings, **When** phase 1 ends, **Then** its open findings
   are recorded and passed to the set phase (owner decision: carry, not block).
5. **Given** a requirement whose defect is a missing or contradictory input (NEEDS_INPUT), **When** phase 1 judges
   it, **Then** the finding is recorded as input uncertainty, not as an author defect, and is not reworked by guessing.

---

### User Story 2 - The complete set is inspected and repaired after phase 1 (Priority: P1)

After phase 1, the whole set is inspected against the existing SWE.1 checklist (SWE1-01..08, unchanged and still the
gate) and the guideline's set-quality criteria SQ-01..SQ-10. Set findings (omissions, inconsistencies, coverage and
traceability gaps) route to the existing set rework, which may change, add or remove requirements; the set is then
re-inspected as today.

**Why this priority**: A set of individually good requirements can still omit behaviour or contradict itself
(guideline section 3); only a set view finds that.

**Independent Test**: On a set where every SWR passes phase 1 but one scoped register field has no requirement, the
set phase reports an SQ-01/SQ-02 gap naming the field, the rework adds a requirement, and the existing SWE1-05
judgement passes on re-inspection.

**Acceptance Scenarios**:

1. **Given** phase 1 has ended, **When** the set phase runs, **Then** it judges SWE1-01..08 exactly as today plus
   SQ-01..SQ-10, and receives phase 1's carried findings as context.
2. **Given** an SQ finding with severity BLOCKING or CORRECTABLE, **When** set rework runs, **Then** it is routed to
   the tasks that own the affected requirements or scope, as checklist findings are today.
3. **Given** the set phase passes the SWE1 checklist, **When** SQ findings remain that are EDITORIAL or N/A with a
   reason, **Then** SWE.1 passes; the SQ findings are recorded in the inspection evidence.

---

### User Story 3 - Owner can see both phases' results (Priority: P2)

The SWE.1 evidence shows, per requirement, the phase-1 verdict history (rounds, findings, what changed), and the set
phase's checklist and SQ findings, without chain-of-thought or prompts.

**Why this priority**: The owner evaluates quality by the findings, not by pass/fail alone.

**Independent Test**: After a run, one compact report lists per SWR: rounds, final verdict, open findings; and per
SQ/SWE1 item: verdict and findings.

**Acceptance Scenarios**:

1. **Given** a finished SWE.1 inspection, **When** the owner opens the inspection report, **Then** both phases are
   listed with counts and the exact open findings.

### Edge Cases

- A requirement removed or renumbered by set rework: phase-1 history stays attached to its stable key, not its SWR
  number.
- Set rework (phase 2) changes a requirement that passed phase 1: phase 1 is not repeated for the whole set; the set
  re-inspection judges the changed requirements (bounded by the existing rework budgets).
- A requirement too large for one inspector request: refused before any model call with a typed reason (never
  silently truncated).
- Phase 1 rework produces an answer that changes another requirement, the effects table of another requirement or
  the requirement's identity: refused deterministically; the attempt counts against the requirement's rounds.
- Model service outage mid-phase: existing outage handling; finished per-requirement verdicts are checkpointed and
  not repeated.
- Budget (requirements derived only from budgets, e.g. flash/RAM) and simulation-performance requirements are judged
  like any other requirement.
- A work order with zero requirements: phase 1 is a no-op; the set phase reports the gap.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: SWE.1 inspection MUST run in two ordered phases after the SWE.1 author's set is assembled: phase 1
  (per requirement) then phase 2 (complete set).
- **FR-002**: Phase 1 MUST judge each requirement individually against IQ-01..IQ-12 of the guideline, giving the
  inspector that requirement, its cited reference-manual source, the definitions it references and the work-order
  scope, and not the other requirements' text except where needed for IQ-09 consistency (its own task's requirements).
- **FR-003**: Phase-1 findings MUST use the guideline shape `requirement_id / quality_id / severity / evidence /
  required_action`, with severity BLOCKING, CORRECTABLE, EDITORIAL or N/A (with reason), and separate input
  uncertainty (NEEDS_INPUT) from author defects.
- **FR-004**: Phase-1 rework MUST re-author only the requirement that has findings; every other requirement of the set
  MUST stay byte-identical, verified deterministically before the rework result is recorded.
- **FR-005**: Phase 1 MUST batch its work so that each round judges all pending requirements with the inspector model
  and then reworks all failing requirements with the author model (one model swap per stage, not per requirement).
- **FR-006**: Phase 1 MUST re-judge only requirements reworked in the previous round, and stop for a requirement when
  it passes, when its rounds are used (default 3 rounds), or when rework makes no change.
- **FR-007**: Requirements that still have findings when phase 1 ends MUST be carried to phase 2 as recorded
  findings (owner decision); phase 1 MUST NOT block SWE.1 by itself.
- **FR-008**: Phase 2 MUST judge the existing SWE.1 checklist items SWE1-01..08 unchanged as the gate, plus SQ-01..SQ-10
  as set findings, and MUST provide phase 1's carried findings as context.
- **FR-009**: Phase-2 findings with severity BLOCKING or CORRECTABLE MUST route to the existing set rework and
  re-inspection; EDITORIAL and justified N/A findings MUST be recorded without forcing rework.
- **FR-010**: The SWE.1 gate verdict MUST remain the existing checklist decision (SWE1-01..08); SQ findings and
  carried phase-1 findings influence it only through those items and through rework.
- **FR-011**: Every phase-1 verdict and rework result MUST be checkpointed per requirement so that a resumed or
  time-boxed visit never repeats finished work.
- **FR-012**: All inspector and author requests MUST stay within the existing admission, context and measurement
  rules (native token counting, product-role trial shapes, call ledger); an oversized request is refused with a
  typed reason before any model call.
- **FR-013**: The evidence MUST record, without prompts or chain-of-thought: per requirement the phase-1 rounds,
  verdicts, findings and whether its text changed; per set item the verdict and findings.
- **FR-014**: The guideline MUST be pinned by content hash in the evidence; criteria text given to models MUST come
  from a versioned checklist file derived from it, not from free text in code.
- **FR-015**: Drivers developed out of context (owner 2026-11-09) MUST be judged with the reference manual as their
  upstream baseline in both phases (SQ-01/SQ-06 trace to RM sections); missing upstream system requirements are not a
  finding.

### Key Entities

- **Requirement under inspection**: one SWR with its stable key, owning author task, statement, source citation,
  verification, effects, and phase-1 history.
- **Individual verdict**: the phase-1 judgement of one requirement in one round: findings list and a pass decision.
- **Finding**: `requirement_id / quality_id / severity / evidence / required_action`, plus `input_uncertainty`.
- **Set verdict**: the phase-2 judgement of one checklist item or SQ criterion over the complete set.
- **Quality checklist**: the versioned IQ/SQ criteria derived from the pinned guideline.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In phase-1 rework, 100% of requirements without findings are unchanged (byte-identical), on every run.
- **SC-002**: Every requirement of the set receives a phase-1 verdict before phase 2 starts (or a typed refusal).
- **SC-003**: Model swaps in phase 1 are at most 2 per round (inspector, author), independent of the number of
  requirements.
- **SC-004**: On the WWDG LL SWE.1 run, the set phase passes the existing SWE1-01..08 gate in no more set-rework
  cycles than the current single-phase inspection needs on comparable inputs, and the number of requirements changed
  by set rework drops compared with the single-phase baseline.
- **SC-005**: A resumed SWE.1 inspection repeats no finished per-requirement verdict (0 duplicate verdict calls).

## Assumptions

- The existing SWE.1 author, assembly, freeze gate, checklist items and set rework are reused; phase 2 is today's
  inspection extended with SQ criteria.
- One GPU and two models (author Ornith-35B, inspector qwen3.8-27B) as on the owner lane; batching per round is
  required for throughput.
- The inspector stays the independent role (the author does not judge its own requirements).
- The guideline is engineering guidance; adopting it here is the owner's reviewed decision of 2026-11-09. The
  checklist gate stays the versioned SWE1-01..08 (guideline section 7 implementation note).
- Scope: SWE.1 only. Later phases may reuse the pattern in a later feature.
