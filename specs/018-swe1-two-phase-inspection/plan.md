# Implementation Plan: Two-phase SWE.1 inspection

**Branch**: `feat/018-swe1-two-phase-inspection` (from the owner-lane campaign branch `de42bc29`) | **Date**: 2026-11-09 |
**Spec**: [spec.md](spec.md)

## Summary

Phase 1 (per requirement) runs between the SWE.1 author and its freeze gate: an inspector step judges each requirement
alone against IQ-01..IQ-12 (one structured call per requirement, verdicts checkpointed by requirement content), an
author step re-authors only the flagged requirement as a single requirement object that code splices into its task
answer (the other requirements are copied, never regenerated), and a check node loops the two until no requirement
needs rework or its rounds are used. Phase 2 is today's structured inspection extended with SQ-01..SQ-10 set items;
the SWE1-01..08 checklist stays the gate. Phase-1 carried findings are given to phase 2 as context.

## Technical Context

**Language/Version**: Python 3.13 (factory/python, uv lock)  
**Primary Dependencies**: existing lrtx structured calls (`lrtx/structured.py`), visit/checkpoint engine
(`lrtx/visit.py`), SWE.1 author (`lrtx/swe1.py`), structured inspector (`lrtx/review.py`), Fabro graph builder
(`workflow/builder.py`), node runner (`lrtx/runner.py`)  
**Storage**: JSON files in the work-order workspace `.forge-run/lrtx/SWE.1/phase1/`; versioned checklist YAML  
**Testing**: pytest (`factory/python/tests`), golden graph hashes (`tests/fixtures/process_lab`), design check
`tests/spec/validate_design.py`  
**Target Platform**: Omniverse2 owner lane (one RTX 6000 Ada, llama-server swapping Ornith-35B author and qwen3.8-27B
inspector; Fabro 0.362 graph; 240 s time boxes; 1800 s node stall watchdog)  
**Project Type**: factory pipeline change (single Python package)  
**Performance Goals**: at most two model swaps per phase-1 round (SC-003); no repeated verdict for unchanged
requirement content (SC-005)  
**Constraints**: product-role trial request shapes (swe1-author / swe1-inspector json_schema, effort medium,
inspector sampling temperature 0 seed 1); native token measurement; pinned adapters unchanged (`llm_gateway.py`,
`afo/product_job.py`, `afo/execution_lifecycle.py`, `fabro/client.py`, `lrtx/stack.py`); checklist SWE1-01..08 and
`maximum_rework_cycles` unchanged  
**Scale/Scope**: WWDG ~20 requirements, SPI ~100, GPIO/TIM 150-200 requirements per SWE.1 set

## Constitution Check

| Principle | Status |
|---|---|
| Versioned skills / role-approved operations | Phase-1 calls use the existing structured roles `swe1-inspector` / `swe1-author`; no new tool or MCP operation. |
| Supervisor zero model calls | Unchanged. |
| Bounded loops, rollback | Phase-1 rounds bounded (default 3 per requirement, no-progress stop); the graph loop is bounded by `max_visits`; set rework keeps the existing budgets. |
| No chain-of-thought / raw prompts in logs | Phase-1 evidence stores verdicts, findings and hashes only. |
| Never weaken safety policies / baselined outputs | Checklist and gate unchanged; SQ adds findings, never removes a check. |
| Claims only with evidence | Tasks are ticked only with run evidence; native WWDG run is the acceptance evidence. |

No violation.

## Design

### D1 Graph (workflow/builder.py, `structured_authors`)

Before `serve_swaps` (so serve nodes are added automatically), when the work order runs SWE.1 structured and
`structured.two_phase_inspection` is on (default on for SWE.1; a profile/work order can turn it off):

```
swe1_author -> swe1_iq_inspect -> swe1_iq_check -(succeeded: rework pending)-> swe1_iq_rework -> swe1_iq_inspect
                                   swe1_iq_check -(otherwise)-> swe1_author_gate
```

- The edge `swe1_author -> swe1_author_gate` is replaced; `continuation` wraps `swe1_iq_inspect` and `swe1_iq_rework`
  with their own time-box check nodes (their replies are `iq-inspect-reply.json` / `iq-rework-reply.json`).
- Model selection: `serve_swaps` classifies `runner iq-inspect ` as inspector and `runner iq-rework ` as author
  (regex extension); `continuation` picks the model by step.
- `max_visits` of the three nodes: `CONTINUATION_MAX_VISITS` (rounds are bounded in code, not by Fabro).
- If the author reply is not PASS, `iq-inspect` does nothing and `iq-check` routes to the gate (unchanged failure
  path). Phase 1 writes no `check_inspection` record, so it never uses the route gate's rework cycles.
- Golden graph hashes are re-recorded after verifying the diff is exactly the inserted nodes/edges.

### D2 Phase-1 inspector step (`lrtx/swe1_quality.py`, runner step `iq-inspect`)

- Requirements: from `assembly.json` (`swr -> task, key`) and the task checkpoints; stable identity is `(task, key)`;
  content hash is the canonical requirement object.
- Pending = requirements without a verdict for their current content hash, whose round count < rounds and not
  CARRIED. One structured call per pending requirement via `visit.run_task` (task id
  `iq:<task>:<key>:<content-hash[:12]>`, so checkpoints dedupe and resume after time boxes).
- Packet (`role swe1-inspector`, inspector sampling): the requirement object, the other requirements of the same task
  (IQ-09 context, read-only), the cited RM section text (from the inventory section of `source_page`), the
  work-order scope and the out-of-context note when applicable, the IQ criteria from the versioned checklist,
  `contracts/individual-verdict.schema.json` as output schema, output reserve 4096.
- Validation: findings shape; `N/A` needs a reason; evidence must quote text present in the requirement or the cited
  source (repairable finding otherwise, like `fact_conflicts`).
- Result: one verdict line per round in `phase1/verdicts/<task>__<key>.jsonl`; `phase1/summary.json` updated; reply
  `iq-inspect-reply.json` (PASS/CONTINUE/FAILED).

### D3 Phase-1 rework step (runner step `iq-rework`)

- For each requirement whose latest verdict needs rework (BLOCKING/CORRECTABLE, not input uncertainty) and that is
  model-authored (register groups and crosscutting; budget/performance requirements are code-generated -> CARRIED):
- Packet (`role swe1-author`): the requirement object, the findings, the same sources the group packet cites, the
  authoring rules of `group_packet`; output schema = one requirement object (the SWE.1 requirement item schema).
- Splice: the answer replaces exactly the element with that key in the task's checkpoint document (key must be
  unchanged); the group is re-validated with `validate_group`; on success the checkpoint is rewritten with status
  VALID, same `base_hash`, a `phase1_rework` provenance entry, and the set is re-assembled with `assemble` from the
  existing records (no author task re-runs).
- Invariant check before writing (FR-004): canonical hashes of every other requirement in `assembly.json` before and
  after are equal; otherwise `REFUSED_OTHER_CHANGED`, nothing written.
- Stop rules: answer identical -> UNCHANGED (CARRIED); validation errors after the repair budget (2) -> INVALID
  (CARRIED); round limit -> CARRIED.
- Reply `iq-rework-reply.json`; `iq-check` exits 0 iff the latest round reworked at least one requirement that now
  needs re-judgement.

### D4 Phase 2 (lrtx/review.py)

- After the SWE1-01..06 items, the inspector judges SQ-01..SQ-10 as items with the existing verdict machinery and
  packet sources (whole set), plus the phase-1 summary (carried findings) as an extra source.
- SQ verdicts are recorded beside the checklist verdicts (`inspection-record.json` `set_quality`,
  `phase2/set-quality.json`); they are not gate items.
- Routing (implementation decision, 2026-11-09): the gate decides from the recorded checklist verdicts only, so an
  actionable SQ finding (and every phase-1 carried finding) is handed to the checklist item it belongs to
  (`review.SQ_ITEMS`; carried -> SWE1-02) as context the item's inspector must check against the sources; a finding
  that holds fails the item, which routes to the existing rework with its budgets (`maximum_rework_cycles`). No
  separate SQ allowance is needed: the checklist rework budget bounds the loop.

### D5 Versioned criteria and evidence

- `factory/checklists/v0.4/SWE.1-quality.yaml` (schema `forge-c/swe1-quality-checklist/1`): IQ/SQ criteria derived
  from `docs/SWE1-REQUIREMENTS-QUALITY-GUIDELINE.md` with its sha256; a test re-derives the IDs and properties from
  the guideline tables so drift is caught.
- Evidence: `phase1/summary.json` + verdict/rework JSONL; the inspection record keeps SQ verdicts; a compact report
  `.forge-run/lrtx/SWE.1/quality-report.md` (run evidence, outside the baselined work products) lists per requirement rounds/final verdict/open findings and per item the
  verdict (US3).

### D6 Rollout

- Implement on the feature branch; full suite vs the branch base; CRE CHANGE gate; merge into the campaign branch
  (merge commit, no force push) so the owner-lane deployer gates and deploys it; first native evidence = the WWDG
  SWE.1 order.
- Feature flag in the profile code-side pin: on for the live trial profile; F017's frozen evaluation (separate
  branch) unaffected.

## Project Structure

```
specs/018-swe1-two-phase-inspection/{spec,plan,research,data-model,quickstart,tasks}.md, contracts/
docs/SWE1-REQUIREMENTS-QUALITY-GUIDELINE.md                      (pinned copy of main 248e423a)
factory/checklists/v0.4/SWE.1-quality.yaml                       (new)
factory/python/forge_factory/lrtx/swe1_quality.py                (new: phase 1 inspect/rework/check, report)
factory/python/forge_factory/lrtx/runner.py                      (steps iq-inspect, iq-rework, iq-check)
factory/python/forge_factory/lrtx/swe1.py                        (single-requirement packet + splice helpers)
factory/python/forge_factory/lrtx/review.py                      (SQ items, carried findings source, reply rule)
factory/python/forge_factory/workflow/builder.py                 (phase-1 nodes, model classification)
factory/python/tests/test_f018_*.py                              (new)
```

## Complexity Tracking

| Item | Why needed | Simpler alternative rejected because |
|---|---|---|
| Splice instead of group re-authoring | FR-004 byte-identical other requirements | Group repair packets rely on a prompt instruction only; observed rewrites of correct requirements |
| Phase 1 before the freeze gate | Re-freeze after every requirement fix would invalidate all set checkpoints and use route-gate cycles | Phase 1 after freeze re-runs SWE1-01..06 per change |
| Separate check node | Fabro routes on node outcome; two models need two nodes | One node cannot swap models mid-node under managed serving |
