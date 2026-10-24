# Implementation plan

1. Extend the existing work-order entry point; keep greenfield carry-over intact.
   Route every brownfield caller through `brownfield.resume`.
2. Record a versioned contract, configuration/derived-input fingerprints and
   runtime identity before model execution. Register original budgets durably.
3. Validate a terminal source, select the native accepted prefix, copy/hash-check
   evidence and inject the destination's own delivery after inherited SWE.1 PASS.
4. Carry scoped corrections, defect/test-snapshot and upstream-loop provenance;
   filter the authoritative tool ledger to accepted phases. Preserve source
   independence conservatively when a later attempt changes models.
5. Reserve attempts transactionally and enforce the inherited deadline through
   existing launch, native/ACP hooks and structured call paths.
6. Include validation, source manifest and lineage in offline packages. Exercise
   positive/negative tests, inherited regression and the independent CRE CHANGE
   promotion runner. Publish a reviewable branch/PR without deployment or merge.

The current remote run remains on its own frozen worktree. All verification for
this feature is CPU-only; no local model evaluation or remote competing GPU test
is part of this plan.
