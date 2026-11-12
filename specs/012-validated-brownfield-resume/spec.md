# Feature 012 — Validated brownfield resume

Requested by the owner on 2026-10-24. Applies to Forge-C's public work-order API,
CLI and AFO recovery, across local and existing approved providers. This is a
new work-order attempt carrying verified evidence; it is not Fabro-native resume.

The problem: brownfield `--resume-from` was refused unconditionally. Repeating
accepted SWE phases consumes model time and introduces variation. The replacement
must retain requirements-before-code provenance and all independent quality gates.

## Requirements

- BR-FR-001: Require an authoritative terminal source run, a new destination ID,
  a versioned identity record and immutable original source evidence.
- BR-FR-002: Match approved and derived inputs, workspace configuration, delivery scope/mode/licence/fingerprints,
  provided dependencies, clean factory revision and assets, resolved checklists,
  tool executable identities, relevant build flags and local profile.
- BR-FR-003: Copy only the leading phases with intact native PASS baselines,
  upstream dependencies and independent inspections. A stale phase, changed
  inspector identity/checklist, open upstream defect or explicit upstream return
  invalidates that phase and every later phase.
- BR-FR-004: Re-run intake into the destination's own store. After the inherited
  SWE.1 gate passes in the destination, inject that delivery anew, recording the
  accepted requirement baseline. Never expose delivered code when SWE.1 must rerun.
- BR-FR-005: FROZEN code remains byte-identical and read-only. FIX_ALLOWED
  corrections are reusable only with accepted SWE.3 and the original CODE defect
  provenance, and must pass the existing scoped delivery verifier again.
- BR-FR-006: Share attempt/time budgets across all children of one lineage through
  atomic SQLite reservations. Failed/ambiguous copies consume reservations.
  Preserve the root deadline and upstream-loop history. Enforce elapsed-time limits
  at launch and model/tool boundaries; do not label unknown token usage as zero or
  relax existing per-role/AFO limits.
- BR-FR-007: Record source run/manifest, copied hashes, accepted phases, restart
  reason and lineage in the workspace and offline package. Preserve the source
  independence assessment conservatively; model switching cannot upgrade inherited
  evidence. No old terminal package or failed-phase inspection may become a new PASS.
- BR-FR-008: Expose the same validation through CLI/API/AFO without enabling AFO,
  changing safety/release policies, modifying live deployments or starting GPU tests.

## Conservative compatibility boundary

Version 1 requires the exact same clean factory commit and runtime identity.
Cross-revision migration needs a separate reviewed compatibility mechanism; this
feature provides no override. Pre-feature runs have no trustworthy recorded tool
identity and are refused. Existing greenfield carry-over remains unchanged.

Budgets default to six total attempts and 86400 elapsed seconds from the initial
work-order creation. Set stricter initial limits using the work-order API or CLI;
resumed attempts inherit them. An in-flight bounded tool/model call can finish after
the deadline; subsequent model/tool admissions are refused. The ledger is local to
the factory state root and must accompany it in backups.

## Validation

`factory/python/tests/test_brownfield_resume.py` exercises real baseline hashes,
native gates and delivery injection with fixture inspector verdicts. Live Fabro
status is mocked in those deterministic tests; they make no model calls and do not
establish model qualification. The inherited brownfield, resume, AFO, hook,
structured-visit, legacy packager and CRE suites remain regression requirements.
