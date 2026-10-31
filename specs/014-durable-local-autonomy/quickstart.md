# Quickstart for implementation and qualification

## Select the feature without losing existing work

From a clean checkout, or a new worktree if there are local changes:

```bash
git fetch origin
git worktree add ../forge-c-014 feat/014-durable-local-autonomy
cd ../forge-c-014
```

If the branch is not local yet, create the worktree from its remote tracking ref:

```bash
git worktree add -b feat/014-durable-local-autonomy ../forge-c-014 origin/feat/014-durable-local-autonomy
```

Use one of these alternatives, not both. Do not reset a dirty working tree. The feature is based on PR #41; do not implement on an older main checkout missing Features 012/013.

## Read before coding

Read `.specify/memory/constitution.md`, this feature's `spec.md`, `local-model-design.md`, `continuous-learning.md`, `continuous-operation.md`, `plan.md`, `research.md`, `data-model.md`, `contracts/README.md`, `tasks.md` and `acceptance-tests.md`. Review Features 002/003/004 learning/KPI/CRE, 005, 010/011, 012 and 013 where referenced. Preserve applicable repository instructions. Do not reinitialize Spec Kit or regenerate these authored documents from generic templates.

## Validate this specification

Use the repository Python environment with its existing test dependencies and `jsonschema` available:

```bash
python3 specs/014-durable-local-autonomy/validate_spec.py
python3 specs/014-durable-local-autonomy/contracts/validate_contracts.py
```

These validate documentation traceability and proposed contract fixtures only. They do not exercise the production broker, model or remote host.

## Implement and test incrementally

Follow `tasks.md`; start with immutable baseline/reproducers and the local capability envelope, then packet/receipt, accounting/liveness and operational recovery. Before changing runtime behavior, reproduce the target failure on the baseline where possible. Keep model/GPU tests separate from deterministic tests.

Relevant existing regression entry points include:

```bash
PYTHONPATH=factory/python python3 -m pytest factory/python/tests/test_afo_local_autonomy.py factory/python/tests/test_afo_m4_recovery.py factory/python/tests/test_afo_m5_maintainer.py factory/python/tests/test_brownfield_resume.py
PYTHONPATH=factory/python python3 -m pytest factory/python/tests/test_m5_lessons.py factory/python/tests/test_inspection_lessons.py factory/python/tests/test_controlroom_scorecard.py
PYTHONPATH=factory/python python3 -m pytest factory/python/tests/test_m3_supervisor.py factory/python/tests/test_t024_systemd.py
python3 tests/spec/validate_design.py
```

Use the actual repository environment and dependencies; do not claim these commands ran as part of specification delivery. Add meaningful fault/integration cases described in `acceptance-tests.md`, then run relevant inherited native/MCP/policy/local-profile/legacy packaging tests and independent CRE through the existing documented runner. Record exact candidate revision, command, versions, exit code, result and artifact hashes.

The implementation must add an executable, documented native qualification entry point as DA-T024. Do not invent an existing CLI command for it in advance. It must support frozen manifest validation and dry-run/report generation without inference, plus a separate explicitly authorized live mode. Live mode must refuse missing authority and preserve cumulative accounting.

For DA-T045–052, inspect existing AFO service/queue tests and add the continuous-operation matrix. Inventory actual installed local-profile units and boot/lingering/mount behavior; distinguish unit syntax validation from real crash/hang/reboot recovery. Prepare a manifest with finite probe/startup/backoff/cooldown/fairness bounds, authenticated operations intent and explicit fault exposure. Never install/start/stop host services merely to run a documentation validator. A measurement window ending must not disable the factory; test later eligible intake while preserving campaign budget expiry.

## Run live qualification only under valid campaign authority

Confirm exact source/profile/model digest, external-route denial, local dependency availability, current grants and the shared mission ledger. Preserve all October 24 attempts/expenditure. Existing download permission does not authorize a new model trial.

Run the frozen protocol cohort before the RCC attempt, then staged operational campaigns and the product benchmark. A correctly blocked recoverable protocol case fails that cohort. Preserve every failed/blocked/timeout run in the denominator. If host access, authoritative inputs or campaign authority is unavailable, mark the specific live milestone NOT_RUN/BLOCKED and continue independent implementation work.

Do not merge/deploy source or amend the future promotion policy as an implicit consequence of completing tests. Keep core implementation, local protocol, product recovery, benchmark and operational readiness distinct in `validation.md`.
