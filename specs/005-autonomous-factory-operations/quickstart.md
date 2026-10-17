# Feature 005 — Development Quickstart and Safe Activation Plan

**This is a proposal, not executable installation instructions for an already-built feature.** Do not copy production configuration and enable ACTIVE before implementation tests, owner authorization and live readiness.

## Initial Claude audit commands (run in Forge-C repository root)

```bash
pwd; git status --short --branch; git rev-parse HEAD
cat .specify/memory/constitution.md
sed -n '1,180p' specs/005-autonomous-factory-operations/spec.md
sed -n '1,220p' specs/005-autonomous-factory-operations/plan.md
sed -n '1,220p' specs/005-autonomous-factory-operations/tasks.md
# After environment preflight:
python3 tests/spec/validate_design.py
python3 -m unittest discover -s tests -v
# Use the repository's real test scripts and Python environment for 004:
make factory-test
```

Do not assume these succeed on an unprepared machine. Capture exact return code, versions and blockers. `make factory-test` may require Forge-C's pinned Python environment. Spec Kit command forms are discovered under `.claude/skills/` (e.g. `speckit-analyze`, `speckit-implement`, `speckit-converge`); do not invoke initializer with `--force`.

## Planned operator workflow once implemented

1. Inspect an AFO service plan (`dry-run` only), mount UUID and credential permissions. Operator approves any systemd host change separately; Fabro production jobs must not be running during migration.
2. Start in `DISABLED` then `OBSERVE_ONLY`. Verify 100 healthy control polls, queue read-only projection and zero inferred token spend. Keep existing supervisor running independently.
3. Operator installs/authorizes `systemd --user` services and `loginctl` linger if needed. Unit boot operation requires mounted data volume; no startup write to wrong disk.
4. Enqueue one approved offline *test* work order. Run `PILOT` only after verified operator authorization, one worker, bounded budgets, and known baseline inputs.
5. Inject reversible, **pre-authorized** faults in a maintenance window; log real process/host restores and protected evidence unchanged. Defer real reboot/kill test until no unsafe active operations.
6. Demonstrate one real READY and one intentionally BLOCKED package, with independent SWE gates and archive hashes. Do not count a BLOCKED archive as accepted success.
7. Run 24h then 72h then 168h soak with real elapsed time, independent watchdog and operator authorization. All quantitative SLO claims depend on observed time and comparable cohorts, not just code tests.
8. Only after individual external sign-offs consider AFO `ACTIVE` within approved product and operational scope. This never turns CRE `ACTIVE` or authorizes persistent code deployment by itself.

## Proposed CLI surface (not currently available)

```text
python -m forge_factory.conductor status
python -m forge_factory.conductor submit --manifest <approved-workorder.json> --authorization-ref <ref>
python -m forge_factory.conductor list --state QUEUED
python -m forge_factory.conductor deadletters
python -m forge_factory.conductor pause --authorization-ref <ref> --reason maintenance
python -m forge_factory.conductor drain --authorization-ref <ref> --reason upgrade
python -m forge_factory.conductor resume --authorization-ref <ref> --reason maintenance_complete
python -m forge_factory.conductor readiness
python -m forge_factory.conductor verify-recovery --order <order_id>
```

CLI syntax shown is a **target contract for implementation**. AFO must provide tests for API consistency and help output; never present these as existing commands until confirmed.

## Rollback and failure priorities

- If a service fails preflight or protected storage is not mounted, leave the queue durable, stop new admissions, issue a local alert; do not write to ephemeral fallback.
- If migration fails, restore last-good schema/versioned DB backup using a separately authorized deterministic rollback, with a tested restore drill; never rewrite 002/004 incident history.
- If operator disables AFO, existing 002/003/004 workflows continue unchanged; no loss of in-flight archive/evidence.
- If planner/maintainer agent produces unverifiable results, quarantine and stop at bounded failure. Return to last-approved baseline, not a dynamically self-accepted patch.

## Development artifacts after each milestone

`evidence/afo/M0..M8/` runtime test evidence, `docs/afo-capability-matrix.md`, `docs/afo-runbook.md`, `docs/adr/ADR-AFO-*.md`, `evidence/afo/readiness.json` and a deterministic `FR -> task -> test -> evidence` report. These paths are output requirements, not files pre-created with fabricated success.
