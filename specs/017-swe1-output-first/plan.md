# Implementation Plan: SWE.1 output-first requirements pipeline

Branch: `feat/017-swe1-output-first` | Date: 2026-11-08 | [Specification](spec.md)

## Approach

Preserve the workflow engine and model pair. Establish observability and native capability first; then introduce a minimal contract and deterministic rendering behind a SWE.1-only selector. Separate factory bookkeeping from model output. Optimize accepted requirement throughput, not short replies in isolation.

## Technical context and integration

Use the repository's pinned Python toolchain and dependency lock. Reuse existing structured requests, gateway admission, role skills, schema validation, replay and profile selection. No new service, database or agent framework is required. Durable JSON/JSONL artifacts under the existing work-order store are sufficient initially.

Inspected remote-main anchors (names may have evolved on the active runtime):

| Existing path | Integration responsibility |
|---|---|
| `factory/python/forge_factory/lrtx/structured.py` | Packet identity, bounded requests, capabilities, structured output |
| `factory/python/forge_factory/llm_gateway.py` | Backend mapping, admission, numeric usage, cancellation |
| `factory/python/forge_factory/lrtx/swe1.py` | Scope inventory, packet construction, validation, assembly, repair/resume |
| `factory/python/forge_factory/lrtx/swe1_semantic.py` | Existing intent/render separation; assess reuse without enabling its SafeC dependency in this lane |
| `factory/python/forge_factory/lrtx/review.py`, `review_semantic.py`, `reinspect.py` | Independent inspection and finding transport |
| `factory/python/forge_factory/lrtx/modelprobe.py`, `modelcmp.py`, `runmetrics.py`, `replay.py` | Existing probe, comparison, metrics and replay mechanisms |
| `factory/python/forge_factory/lrtx/profile.py`, `visit.py` | Selection, budgets, checkpoint boundaries |
| `.fabro/skills/swe1-author/SKILL.md`, `.fabro/skills/swe1-inspector/SKILL.md` | Minimal role output contracts and permissions |
| `factory/python/tests/test_lrtx_swe1.py`, `test_lrtx_v2_swe1.py`, `test_llm_gateway.py` | Existing regression suites |

Proposed new cohesive modules, only where existing modules cannot be extended cleanly: `lrtx/swe1_contract.py`, `lrtx/swe1_coverage.py`, `lrtx/swe1_recovery.py`, `lrtx/call_ledger.py`. Do not create a parallel runtime. Record any changed path mapping in the implementation report.

## Constitution check

No change to release authority, safety criteria, protected inputs, healthy model-free supervision or MCP boundaries. Hidden reasoning is never persisted. Raw prompts/responses remain off by default; source references/hashes and numeric counters suffice for normal telemetry. An isolated ASPICE-only selector does not reinterpret the protected safety lane. Role skills remain versioned and hashed. Acceptance remains evidence-backed and bounded. No constitution amendment is proposed.

## Milestones and stopping points

### M0 — Baseline and trustworthy measurement

Inspect the actual Omniverse checkout, selected profiles, gateway path and deployment topology. Record baseline tests, model identities and unresolved drift from the documentation branch. Add minimal call lifecycle accounting and reconcile summaries before comparing modes. Reproduce identifier normalization and repair coverage loss with synthetic fixtures; fix the deterministic defect so it does not contaminate all subsequent trials.

Output: environment record, baseline/replay report, tested ledger and repair guards. No production-profile change.

### M1 — Native author capability experiment (first delivery)

Verify thinking controls and generation limits through the real application path. A template switch alone is insufficient. Run the paired experiment in validation.md with inspector held fixed and existing prompts/checks otherwise held constant. If effective thinking-off cannot be established, record the limitation and test a genuinely supported bounded mode; do not label suppressed display as disabled generation.

Output: measured role-specific capability matrix, author-mode comparison, recommended candidate or retained baseline, and explicit NOT_RUN items. Stop here for the first handoff. This is an evidence checkpoint, not a new runtime human-approval gate.

### M2 — Minimal contract and deterministic rendering

Implement data-model.md with the smallest useful schema, dynamic applicability and a compact author projection. Known identifiers, facts and bookkeeping are supplied by the factory. EARS rendering and trace assembly require zero model calls. Validate round trips and semantic preservation with synthetic golden examples. Select this path only for SWE.1 and preserve existing workproduct adapters.

Output: reusable schema, renderer, compatibility adapter, unit/replay evidence.

### M3 — Coverage planning and independent semantic inspection

Create an obligation inventory from work-order scope and source/interface facts. Review it independently before drafting; an automatically extracted inventory can itself be incomplete. Parameterize repeated instances only where applicability and exception facts support it. Preserve verification criteria as obligations, not executed-test evidence. Separate frozen implementation consistency checks from normative requirement derivation.

Output: coverage report, cross-contract checks, seeded-defect evaluation and isolated inspector-mode experiment if justified. Do not weaken inspector settings solely to match author settings.

### M4 — Recovery, resume and full SWE.1 validation

Route stable failure classes to deterministic normalization, targeted patches, evidence acquisition, task repartition or blockers. A default draft plus two repairs is bounded by enclosing phase budgets and cannot be reset by continuation. Continue unrelated obligations where possible. Resume accepted work by content/dependency identities; invalidate downstream artifacts when upstream meaning changes.

Output: complete SWE.1 experiment, aggregate quality/cost report, rollback instructions and remaining gaps. No SWE.2 launch or production cutover is part of this milestone.

## Budget policy

Resolve all policy layers into one recorded effective policy. Track answer tokens, reasoning tokens when reported, total generation, call count, queue/inference/load time and wall-time ceilings separately. Enforce limits with backend-supported controls plus application deadlines. Cancellation requires evidence that backend work ended or an explicit unconfirmed/quarantined state before more inference is admitted. If streaming or accounting cannot prove a token cap, do not pretend it can; record the limitation and enforce independent call/time bounds.

Suggested experiment starting limits, to validate rather than hard-code globally: one draft plus two repairs per behavior; one changed-strategy recovery; 120 seconds per ordinary small author call and 15 minutes per task including queue/recovery. Baseline calls may use the existing measured limits for fair comparison. Set the complete phase budget from the finite inventory before launch. Size output reserves to schema/task cardinality, not one universal number. Record all deviations before the trial.

## Compatibility and rollback

Create a new versioned experimental profile and preserve baseline profile bytes. Avoid mass invalidation or conversion of existing work orders. Old packets remain readable; new schemas have explicit versions. Choose either an explicit migration with a recorded compatibility check or a fresh isolated work order. No silent acceptance of legacy VALID as semantically reviewed. Rollback selects the original profile; keep experimental evidence and checkpoints separate.

## Validation commands

Read the current Makefile/environment setup on the chosen implementation base. Existing entrypoints include `make test`, `make design-check`, `make factory-test` and `make factory-lint`. Run focused Python tests during each milestone, required design checks after changes, and applicable legacy suites before integration. Do not run live service/campaign targets as substitutes for unit validation. Record exact commands, versions, exit status and evidence paths. Any new probe/benchmark CLI must be implemented and documented before its use is claimed.

## Complexity limit

Do not implement a general theorem prover, autonomous policy editor, all-driver capability catalogue or generic orchestration replacement. Extend the contract only when a benchmark exposes a concrete need. Reuse existing semantic-first code where suitable, but do not require an excluded assurance engine merely to render EARS.
