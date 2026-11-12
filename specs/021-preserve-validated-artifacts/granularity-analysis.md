# Preserve validated artifacts across runs - granularity per SWE process (analysis)

Owner rule 2026-11-13: "whenever a run finish and need to run again due to any reason, the artifacts that was already
inspected and validated must be preserved between runs, it can be changed if other dependencies requires to, otherwise
must be kept, and on which swe process we need to analyze how to define the granularity of artifacts that this rule can
be applied reasonably". Input for feature 021 (spec to follow); read from the code at feature 020 commit da891c87,
nothing run. Paths relative to `factory/python/forge_factory/`. UNVERIFIED marks what was not confirmed.

## What exists today (all phases)

- Phase scope `inspection/engine.py` PHASE_PATHS / UPSTREAM; `freeze` hashes every phase file and records the upstream
  baselines; `stale_reason` marks the WHOLE phase stale when any phase or upstream file changes.
- Inspection items are judged once per baseline (`lrtx/review.py:501` task key `inspect:{baseline[:16]}:{item}`): any
  file change re-judges every item.
- Author task checkpoints `.forge-run/lrtx/<phase>/packets/<task>.json` are reused while VALID and `base_hash` equals
  the packet `input_hash` (`lrtx/visit.py:257-260`); `input_hash` (`lrtx/structured.py:220-299`) covers prompt
  version, task/role, skill sha, model, instructions, criteria, schema, sources/artifacts (path+sha), lessons offered,
  served-model identity and the QM assessment scope.
- Cross-run author reuse `inherited_task` (`lrtx/visit.py:120-165`) only via `resumed_from` or
  `fresh_recovery_from.revalidate_author_tasks` (CAPA-209 LINE_RETRY), one parent, author roles only; SWE.1 IQ verdicts
  only via LINE_RETRY with an identical inspection packet (`lrtx/swe1_quality.py:331-365`).
- `--resume-from` (`workorder.py:649-758`) is all-or-nothing per phase: leading gate-PASS phases copied, everything from
  the first non-PASS phase deleted.
- QM orders: `release/qm.py:72-75` binds `work_order_id` into the packet scope, so no packet hash ever matches across
  work orders (kills inheritance for QM orders). Lessons are looked up per work order (`structured.py:196-210`;
  whether they differ in practice: UNVERIFIED).
- `assurance/impact.py` ImpactGraph exists but is used nowhere.

## Per process

| Phase | Validation unit today | Recommended preservation granularity | Gaps |
|---|---|---|---|
| SWE.1 register | IQ verdict per requirement (`swe1_quality.py:392-401`); SQ-01..10 + gate items per set baseline | per requirement (object sha + inspection packet hash); set-level checks re-run once | verdict record lacks its packet hash; phase1/ not carried |
| SWE.1 functional | same two-phase path | per requirement (+ governance package when its inventory is unchanged) | governance/template version not bound per verdict |
| SWE.2 | 2 author tasks (`interfaces`, `design`, `swe2.py:683-704`); 3 checklist items per baseline | per interface function / per design decision | two monolithic tasks: any SWR change re-authors all |
| SWE.3 | author task per unit `code:<SWU>` (`swe3.py:407-410`); build/cppcheck/MISRA per build | per unit (function + its spec items) | tool evidence per build, not per unit |
| SWE.4 | `test:<UT>` per test (`swe4.py:574`); run_unit/coverage per suite; tool PASS must be newer than the SWE.3 freeze (timestamp, engine:196) | per unit test + its run result | staleness by time, not hash; suite-level runs |
| SWE.5 | 3 file tasks (`swe5.py:318`); run_integration + run_renode | per integration test id | coarse files; Renode model version not keyed (UNVERIFIED) |
| SWE.6 | `scenario:<group>` (`swe6.py:301`); run_robot | per requirement (one robot case each) | task per group, not per requirement |

Set-level judgements (SQ, checklist items, gate) stay per baseline by nature: they are re-run once after the carried and
reworked items are assembled - cheap compared with re-authoring and re-inspecting every item.

## Mechanisms needed (priority)

1. Cross-run validated-item store keyed by (phase, item key, content sha, dependency-set sha), looked up from any prior
   order of the same component, for author answers AND inspector verdicts (generalise `inherited_task` /
   `_inherited_verdict`).
2. Run-identity-free semantic hash: split `input_hash` into a semantic key and run context; drop `work_order_id` from
   the QM scope binding; pin or exclude the lessons offered.
3. Per-item dependency manifest + impact walk (SWR -> interface/unit -> UT/IT/robot case, with content shas), wiring
   `assurance/impact.ImpactGraph` into resume instead of whole-phase `stale_reason`.
4. Partial phase carry: keep the valid items of a non-PASS phase, re-author/re-inspect only invalidated items, then
   re-freeze and run the set-level checks once; add packet input hash and guideline/template/governance shas to
   `phase1/verdicts.jsonl`.
5. Content-keyed tool evidence: bind run_unit / run_renode / run_robot results to the code, test and tool-image hashes
   per test id instead of timestamps, so an unchanged test's PASS carries.

First application: the feature 020 UART round 2 (SWE.1 functional, per requirement), decision log D36.
