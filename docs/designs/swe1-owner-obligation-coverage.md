# SWE.1 owner-obligation coverage

*   **Status:** Approved plan (owner 2026-10-31: "save your proposal to be implemented after we test the codex-next"),
    implemented as a global mechanism (owner 2026-10-31: "as a global mechanism, not only for CRC").
*   **Source:** `evidence/014-durable-local-autonomy/swe1-inspector-omission-20261031/PROPOSAL-completeness.md`,
    options 3 and 1.
*   **Not in scope:** option 2, a checklist change. `factory/checklists/**` is a protected path, so it needs separate
    owner approval.

## Problem (measured)

A gate-frozen SWE.1 baseline (Ornith attempt 2, CRC IDR) omitted three obligations that the owner contract states:
no status polling, no error code on a valid call, and preserving the other fields and registers.
- **Four inspector configurations missed them:** Qwen medium, Qwen xhigh, qwen3-coder-next, and Qwen inspecting
  Ornith.
- **The inspector cannot see the contract.** `lrtx/review.evidence` does not include the owner contract.
- **No mechanism compares requirements with owner obligations.** Neither the author gate nor the checklist does.

## Design

**Global, opt-in per work order.** The mechanism lives in `forge_factory/assurance/owner_obligations.py` and applies
to any work order and any SWE.1 author path. It is active only when the work order declares an input with role
`owner_obligations`. Work orders without one, which is every existing order, keep their packets, schemas and work
products; their assembly record states `owner_obligations: NOT_DECLARED`, so the absence is visible. Making the input
mandatory for every work order needs a separate owner decision.

1.  **Obligations input (`forge-c/owner-obligations/1`, JSON).** It is written by the owner, or drafted for owner
    review. Each obligation has:
    *   `id` (`OBL-[a-z0-9-]+`);
    *   `statement`, the owner's own words;
    *   `critical: bool`;
    *   optionally `effects: [{register, field, op}]`, register effects that any covering requirement must state.

    It is validated by a runtime schema (`specs/014-durable-local-autonomy/contracts/runtime/owner-obligations.schema.json`,
    loaded by `process_lab.contracts`, with fixtures). The oracle stays separate: it is hidden from the author and may
    hold more than the owner states.
2.  **Author mapping.** For SWE.1 group and cross-cutting packets:
    *   **Requirement schema:** `REQ_SCHEMA` gains `obligations: [OBL ids]`. This applies only to the obligation-aware
        schema variant, so schemas without obligations are unchanged.
    *   **Cross-cutting schema:** the cross-cutting `GROUP_SCHEMA` variant gains
        `obligation_gaps: [{id, reason ≥ 10 chars}]`.
    *   **Packet sources:** the obligations file is added as a packet source.
    *   **Instructions:** they say to map every requirement to the obligation ids it implements, and to list any
        obligation the inputs cannot support in `obligation_gaps` with a reason. An obligation must never be dropped
        silently.
3.  **Deterministic coverage check.** `owner_obligations.coverage_findings` reads only the SWE.1 artifacts, so it
    holds every author path (structured, semantic or an agent) to the same rule. It runs twice:
    *   in `swe1.self_check` after assembly, as localized findings for the existing repair path. An uncovered
        obligation with register effects is routed to that register's task, any other one to the cross-cutting task;
        an effect finding goes to the task of the citing requirement;
    *   in the SWE.1 author gate (`inspection/gate.step_author`), so an author that skips the self-check cannot
        freeze an incomplete baseline.

    The findings are:
    *   every obligation id is covered by at least one requirement or listed in `obligation_gaps`
        (`SWE1_OBLIGATION_UNCOVERED:<id>`);
    *   every cited id exists (`SWE1_OBLIGATION_UNKNOWN:<SWR or gap>:<id>`), and every gap has a reason
        (`SWE1_OBLIGATION_GAP_REASON_MISSING:<id>`);
    *   a declared input that changed after preparation, is invalid or is declared twice refuses
        (`SWE1_OWNER_OBLIGATIONS_*`), never silently ignored;
    *   for an obligation with `effects`, at least one covering requirement states each effect
        (`SWE1_OBLIGATION_EFFECT_MISSING:<id>:<register.field.op>`), so a requirement cannot cite an obligation it
        does not implement.
4.  **Artifacts.**
    *   Each requirement that implements obligations gets a `  - Obligations: OBL-…` line after its Verification
        line, and recorded gaps form a `## Obligation gaps` section (`- **OBL-x**: <reason>`).
    *   `traceability/obligations_to_requirements.csv` lists the `obligation_id`, `requirement_id` and `gap_reason`
        columns.
    *   The obligations file path and hash are bound into the assembly record (`owner_obligations`).
5.  **Inspector sources (option 1).** For SWE.1, `lrtx/review.evidence` (also used by `review_semantic`) adds the
    obligations file and the declared inputs its `source_inputs` name (for CRC IDR: the owner contract) as sources. The inspector can then judge whether a requirement implements its
    cited obligation, which the deterministic check cannot decide.

## CRE and tests

*   **Reproducer RPR-076:** a scripted author run with an obligations input. One obligation is omitted and no gap is
    recorded. On the old code the baseline freezes, which is the symptom. On the fix the author gate rejects it with
    `SWE1_OBLIGATION_UNCOVERED`.
*   **Unit tests:**
    *   covered, uncovered, gap-recorded, unknown-id and effect-missing cases;
    *   orders without obligations are byte-identical (the packet and schema golden);
    *   inspector sources include the contract only when it is declared.
*   **CAPA-077,** then a regression against the baseline with the same ST inputs, then the promotion gate.

**Known limitation.** The semantic SWE.1 author (`lrtx/swe1_semantic.py`) has its own answer schemas without
obligation ids. With obligations declared, it fails closed (UNCOVERED at self-check and gate) until it is made
obligation-aware.

## CRC IDR obligations (draft for owner review)

`owner-obligations/crc-idr-owner-obligations.json` (`DRAFT_FOR_OWNER_REVIEW`; the 0014g example is unchanged) is
transcribed from the scope paragraph of `IDR-CONTRACT.md`; review points are in `owner-obligations/README.md`. Its
obligations are:
*   write all 32 bits to IDR;
*   a read returns the stored value;
*   preserve every other register and instance;
*   no startup accesses;
*   no status polling;
*   no allocation or setup;
*   no error code for valid accessible calls;
*   invalid pointers and calculation/configuration are out of domain.

Each is marked critical or not, for owner review. A standalone rerun then repeats the Ornith author arm with
obligations, to measure whether attempts still drop obligations and whether the gate now catches them.
