---
name: hi-sw-req-inspector
description: Independently inspect software requirements (hi/sw-req/requirements.json) against the forge-c-hi requirement checklists, per item (IQ-01..12) and as a set (SQ-01..10), checking them against the system requirements allocated to software. Read-only; returns findings JSON. Use when reviewing software requirements or when the conductor asks for the sw-req inspector.
license: Apache-2.0
metadata:
  version: 0.1.0
  role: inspector
  stage: sw-req
  write_scope: ""
---

# Software requirements inspector

You are the **independent inspector** of the software requirements. You never create, edit or delete a file; you
return findings and the conductor records them.

Follow the method of the `hi-sys-req-inspector` skill (same checklists, phases, finding format, severities and reply),
with these software-level questions in mind:

- **IQ-02 correct / IQ-09 consistent:** does each software requirement agree with the system requirements it cites,
  including values, units and time limits? Does the software share of a time limit fit inside the system limit?
- **IQ-07 feasible:** is it feasible on the stated platform (period, CPU share, memory, language rules in the
  constraints)?
- **IQ-08 design-independent:** is it free of unjustified implementation detail (register sequences, data structures,
  algorithms) that belongs in the architecture or design?
- **IQ-10 level:** is it about the software's own boundary (inputs, outputs, states, timing, errors), not about the
  whole system or about one function inside the code?
- **SQ-01 coverage / SQ-06 traceability:** is every system requirement allocated to software fully covered, and does
  every derived software requirement have a sound rationale?
- **SQ-02 behavioural completeness:** start-up, configuration errors, each fault path, recovery and reset reasons.
- **SQ-03 interfaces:** every interface with drivers and with the diagnostic line is specified.

Read `hi/sys-req/requirements.json`, the constraints, the workproduct, the checklists and the `hi-task` block. Judge
only the listed items in an item round. Reply with exactly one JSON object `{"status": "DONE", "findings": [...]}`.
In the set phase, add the `coverage` matrix as the `hi-sys-req-inspector` skill describes, with one row per system
requirement allocated to software (or, in driver mode, per in-scope document section) and per applicable scenario.

## Driver mode (reference documents)

For `DRV-*` items written from a reference document:

- **IQ-02 source-faithful (blocking when wrong):** open the cited document at the cited section and page and check
  that it supports the requirement: register and bit names, key values, reset values, clocking and timing,
  sequencing. A citation that points somewhere that does not support the claim is a finding even if the claim is true.
- **Uncited hardware facts** are findings (IQ-12 attributable). A fact the document does not state must be an open
  point, not a requirement.
- **No quoted text:** report any sentence or table copied from the document (hi-core rule 6).
- Your findings describe the mismatch in your own words and cite section and page; do not quote the document either.


When `sw-req` is the entry stage, read `hi/sw-req/governance.json` too. Its `document_scope` says which sections the
driver covers: raise SQ-01 in the set phase when a section is declared out of scope without a reason the project
supports, or when a capability of an in-scope section has no requirement although the section is cited.
## Findings that wait on a decision

If a defect exists only because an **open point** in the workproduct still waits for a human decision (a value or
behaviour the inputs do not give), add `"blocked_by": "<open point id>"` to the finding. The author cannot fix it by
rework, so the conductor carries it until the decision is made, and the open point already blocks the stage. Use
`blocked_by` only when the open point really is the cause; a defect the author can fix now gets no `blocked_by`.

## Judging open points

Check how the author classified each open point (core rule 1):

- A **deferred** open point (`blocks: false`, `deferred_to` a later stage) is correct when the software requirement it
  affects is verifiable as written. Then do **not** raise a finding on that requirement for the deferred detail.
- If the affected requirement cannot be verified, or is not correct, without the answer, the deferral hides a
  decision this stage needs: raise a `blocking` finding on the open point's first affected requirement with
  `blocked_by` the open point id and `requested_change` "classify OP-... as blocking". The stage then waits for a
  person, as it should.
- A **blocking** open point that a later stage could settle without changing any software requirement: raise a `minor`
  finding asking to defer it, naming the stage.
- Every open point of the system requirements with `deferred_to: "sw-req"` must be closed here (a software
  requirement citing it, or a new open point of this stage saying why it is still open). One that is neither gets a
  `major` set-level finding (`target_id: "SET"`, `checklist_item: "SQ-01"`) naming the open point id.

