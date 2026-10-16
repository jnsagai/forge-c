# ADR-CRE-004: Immutable benchmark/oracles and independent promotion authority

Status: accepted (2026-10-16) · Tasks: CRE-T018..T020, CRE-T024..T029

* **Candidate = a factory source revision** (git commit). Baseline = the pinned revision it is compared with.
  Evaluation runs each revision in its own detached `git worktree` (isolated tree, no write access to the main
  checkout), started as a separate process by the runner — never by the authoring agent.
* **Oracles and holdout belong to the runner, not the candidate**: the suite manifest, reproducers and holdout
  fixtures are read from the *runner's* revision (`tests/reliability/…`), hash-locked in the manifest; a candidate
  that changes any of them is rejected at the protected-file gate, and a manifest whose hashes do not match is
  `INCOMPLETE` (AT-021, AT-022).
* **Reproducers are black-box programs** (stable CLI / module entry points) that exit 1 while the symptom is present
  and 0 when it is absent. Causal verification = baseline exit 1 *and* candidate exit 0 *and* the baseline failure is
  the expected signature (not an import/attribute error from API drift). Anything else keeps the root cause at
  `HYPOTHESIS` (AT-015, AT-016).
* **Gate order** (hard gates first, cheapest first): protected files/security → reproducer → safety/process/quality
  (policy invariants, gate test suites, design check) → existing regression (golden benchmark) → holdout →
  statistics/efficiency → change-control disposition. A hard failure stops evaluation; no weighting of metrics can
  overturn a veto (AT-024).
* **Decisions**: `REJECTED`, `INCONCLUSIVE`, `ELIGIBLE_FOR_OFFLINE_REVIEW`, written as `promotion-decision.json`
  (schema in the 004 contracts) with input hashes, policy hash, runner revision and per-gate evidence;
  `allowed_auto_deployment` is always `false` in this release (CRE-FR-028). The existing human change-control
  (commit/merge) remains the only path to production.
