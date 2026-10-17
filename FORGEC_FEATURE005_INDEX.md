# Forge-C Feature 005 — Autonomous Factory Operations (AFO)

**Date:** 2026-10-17. **Delivery:** Spec Kit specification + Claude Code implementation prompt. **Not implemented or deployed.**

## Why this feature

Forge-C Features 002–004 already monitor faults, perform bounded runtime repair, version CAPAs, measure reliability and validate promotion candidates. They do **not** yet provide a persistent headless work-order conductor that autonomously deals with repeated SWE failures and keeps the system processing approved work after reboots. The CRE baseline is configured `OBSERVE_ONLY`. Feature 005 fills that orchestration/engineering-recovery gap without overriding external source-change/safety approval.

## Branch strategy

Feature 004 remains an open draft PR #1 with hundreds of changes not in `main`. This **Feature 005 branch must start from the current head of Feature 004**, and its PR should target `feat/004-continuous-reliability-engineering`. When 004 merges, an authorized developer can retarget/rebase Feature 005; do not attempt it automatically.

## Contents

- [`CLAUDE_FEATURE005_START.md`](CLAUDE_FEATURE005_START.md) — copy/paste Claude execution contract.
- [`specs/005-autonomous-factory-operations/spec.md`](specs/005-autonomous-factory-operations/spec.md) — user stories, 18 safety/control invariants, 72 functional requirements and acceptance goals.
- [`specs/005-autonomous-factory-operations/plan.md`](specs/005-autonomous-factory-operations/plan.md) — technical plan, integration points and milestones M0–M8.
- [`specs/005-autonomous-factory-operations/architecture.md`](specs/005-autonomous-factory-operations/architecture.md) — sequence diagrams, responsibility and trust boundaries.
- [`specs/005-autonomous-factory-operations/research.md`](specs/005-autonomous-factory-operations/research.md) — repo-based design decisions and unresolved implementation checks.
- [`specs/005-autonomous-factory-operations/data-model.md`](specs/005-autonomous-factory-operations/data-model.md) — durable tables, FSM, idempotency, crash windows and provenance.
- [`specs/005-autonomous-factory-operations/tasks.md`](specs/005-autonomous-factory-operations/tasks.md) — 75 currently unchecked tasks.
- [`specs/005-autonomous-factory-operations/acceptance-tests.md`](specs/005-autonomous-factory-operations/acceptance-tests.md) — 66 named acceptance scenarios, initially NOT_RUN.
- [`specs/005-autonomous-factory-operations/operational-readiness.md`](specs/005-autonomous-factory-operations/operational-readiness.md) — uptime/yield separation and 24h/72h/168h soak readiness.
- [`specs/005-autonomous-factory-operations/quickstart.md`](specs/005-autonomous-factory-operations/quickstart.md) — audit/installation/activation blueprint.
- [`specs/005-autonomous-factory-operations/requirements.csv`](specs/005-autonomous-factory-operations/requirements.csv) — 72 requirements with test/task links and NOT_IMPLEMENTED.
- [`specs/005-autonomous-factory-operations/planned-traceability.csv`](specs/005-autonomous-factory-operations/planned-traceability.csv) — 75 tasks with requirement/test links and NOT_IMPLEMENTED.
- [`specs/005-autonomous-factory-operations/agent-contracts.md`](specs/005-autonomous-factory-operations/agent-contracts.md) — least-privilege Recovery Planner and Factory Maintainer contracts.
- [`specs/005-autonomous-factory-operations/validate_spec.py`](specs/005-autonomous-factory-operations/validate_spec.py) — read-only schema, example and traceability consistency validator.
- `contracts/` — JSON Schemas (work order, attempt, outbox, failure bundle, recovery plan, maintainer proposal, dead letter, authorization, readiness, policy); YAML sample policy, queue state machine, failure taxonomy, OpenAPI declaration. All are **specification contracts**, not deployed endpoints or claimed runnable services.

## Core architectural limits

- AFO is a deterministic Conductor + durable queue and reconciler. Fabro and existing 002/004 supervisor remain separate, CRE promotions are independent.
- Product draft recovery may be autonomous within immutable approved requirements and independent gates. Factory source/skill/workflow fixes may be prepared autonomously but must be externally reviewed before persistent deployment.
- No firmware flash, safety approval, policy weakening, unauthorized cloud use, self-invented work orders, auto-merge or repeated non-replayable side effects.
- 24/7 *service* availability can be targeted; 100% arbitrary engineering success cannot be guaranteed. A valid BLOCKED package is not engineering success.

## Validation performed on this package

Specification consistency, YAML parsing, Draft 2020-12 JSON schema validation, sample policy validation, requirements/task/test ID coverage, and filename SHA256 inventory are performed at authoring time. They do not represent host/systemd/real-model test results.
