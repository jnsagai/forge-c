# Phase-scoped runs (--stop-after), CHANGE

- Owner 2026-10-31: "I want a fabro run by now just for SWE.1". Candidate ff33540a (builder/workorder stop_after + tests), with the 0014h example bbec7eb8.
- Targeted regression (regression-files.txt, 18 files: builder, workflow, workorder, ACP, structured, SWE.1, QM): candidate 193 passed, 1 skipped in 501.96s (0:08:21); baseline 06a485d2 188 passed, 1 skipped in 502.82s (0:08:22). No failures.
- CRE: pd-e9687ad0c3f3914f53f1 ELIGIBLE_FOR_OFFLINE_REVIEW (CHANGE; reproducer gate not applicable), promotion-gate.txt.
- Without --stop-after the graph is byte-identical (test_default_graph_is_unchanged, builder golden).

## Prune (owner: "we must test just the SWE.1")

- e14175db: a scoped graph holds only the phases up to --stop-after (16 nodes for SWE.1 instead of 90). 06914b8b: reinspect rewiring skips phases outside the scoped graph (found in design review: STRUCTURED_ROUTE_MISSING:swe2_route with reinspect_direct profiles).
- pd-1c84ddaa21d6a348698f REJECTED (06914b8b vs 0a421d25): prevention RPR-077 SYMPTOM_PRESENT, because CAPA-078 was verified before this ancestor commit was gated (ordering, promotion-gate-prune-rejected.txt).
- pd-1c4f0cc94004ada9f5f0 ELIGIBLE_FOR_OFFLINE_REVIEW (combined 8d6841bd vs 0a421d25, CHANGE, promotion-gate-prune-combined.txt). Targeted regression: ../capa-078/REGRESSION.md.
