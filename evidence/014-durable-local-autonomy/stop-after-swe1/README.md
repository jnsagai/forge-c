# Phase-scoped runs (--stop-after), CHANGE

- Owner 2026-10-31: "I want a fabro run by now just for SWE.1". Candidate ff33540a (builder/workorder stop_after + tests), with the 0014h example bbec7eb8.
- Targeted regression (regression-files.txt, 18 files: builder, workflow, workorder, ACP, structured, SWE.1, QM): candidate 193 passed, 1 skipped in 501.96s (0:08:21); baseline 06a485d2 188 passed, 1 skipped in 502.82s (0:08:22). No failures.
- CRE: pd-e9687ad0c3f3914f53f1 ELIGIBLE_FOR_OFFLINE_REVIEW (CHANGE; reproducer gate not applicable), promotion-gate.txt.
- Without --stop-after the graph is byte-identical (test_default_graph_is_unchanged, builder golden).
