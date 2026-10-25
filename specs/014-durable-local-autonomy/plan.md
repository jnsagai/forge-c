# Implementation Plan: Durable local autonomy and recovery

**Branch**: `feat/014-durable-local-autonomy` | **Date**: 2026-10-25 | **Spec**: [spec.md](spec.md)

## Summary

Repair the diagnosis-to-execution boundary before evaluating another product retry. Extend existing case preparation, MCP, native adapter, AFO ledger/outbox and verifier. Make Qwen return a small semantic judgment; deterministic code binds the authoritative plan, validates admission, records the receipt and completes the job.

Also close the learning loop on every ordinary driver/feature job using the existing knowledge, events, curator, inspection-lessons, CRE and KPI components. [Continuous learning](continuous-learning.md) defines the additive extension; a second learning engine or unrelated memory stack is not needed.

## Technical Context

- **Language/version:** existing repository Python environment and lockfiles; inspect actual supported version during implementation rather than upgrading it for this feature.
- **Dependencies:** existing Fabro client/native workflows, Ollama gateway, MCP SDK, Pydantic/contracts, SQLite, pytest and CRE runner. No new mandatory orchestration framework or cloud service.
- **Storage:** current Conductor SQLite/WAL plus immutable hash-addressed case/evidence files. Migrations are additive, versioned and backup-tested before activation.
- **Target:** Linux isolated local profile on Omniverse2; developer fixtures run without a model/GPU. CPU verification remains bounded.
- **Performance:** one admitted inference; responsive model-free control loop; bounded queue and measurable prompt/generation/tool/recovery time. No unsupported throughput promise.
- **Constraints:** constitution, AFO-FR-053, current agent allowlists, source retention, role separation, fixed oracles, no hidden reasoning capture, no activation implied by source merge.

## Constitution Check

| Principle | Design compliance |
|---|---|
| I–II: correctness/evidence | Preserve gates and source truth; receipts and independent checks establish results. |
| III: unattended operation/external release | Normal eligible recovery has no interactive approval; policy/deployment authorization remains external and pre-established. |
| IV–V: SKILL/MCP | Existing versioned role assets and tested MCP grants remain; deterministic controller/native internals may assemble packets and bind metadata. |
| VI: independent supervision | No model in healthy monitoring; bounded recipes, liveness reconciliation and isolated candidates. |
| VII–IX: lessons/privacy/budgets | Validated, retractable lessons; redacted events; separate limits and shared lineage expenditure. |
| X/governance | Fully local runtime; no safety certification claim; future worker promotion stays a proposal. |

Recheck after design and before activation. No constitutional exception is requested. Implementing protected AFO changes as external engineering must not expand runtime maintainer grants.

## Project Structure and change targets

| Concern | Existing target | Proposed additions, subject to integration design |
|---|---|---|
| Evidence packet | `factory/python/forge_factory/afo/bundle.py`, `recovery_context.py`; `mcp/servers/afo.py`, `afo_payload.py` | `afo/diagnosis_packet.py`, typed evidence manifest/read API |
| Proposal/receipt | `afo/planner.py`, `recovery.py`, `local_agent.py`; `contracts/agent_output.py` | `afo/semantic_proposal.py`, `afo/completion_receipt.py` |
| Limits and accounting | `policy/governor.py`, `policy/fabro_hook.py`, `fabro/runconfig.py`, local gateway admission | `afo/mission_ledger.py`, request-bound accounting adapter |
| Execution and review | `afo/local_agent.py`, `fabro/client.py`, existing AFO queue/outbox/store | liveness record and durable verifier lease/outbox |
| Operations | existing supervisor/watchdog, local-profile preflight and service configuration | approved recipe inventory, deterministic restore/reconciliation tests |
| Qualification | existing local harness, CRE, package verifier and status/scorecard | feature-scoped native protocol campaign and reporting |
| Every-job learning | `knowledge/store.py`, `mcp/servers/knowledge.py`, existing lessons-curator SKILL, `events/*`, `workorder.py`/AFO reconciliation | additive experience/disposition records, versioned source kinds, durable learning outbox and backward-compatible qualification |
| Learning transfer and impact | `knowledge/inspection.py`, `kpi/sources.py`, `kpi/engine.py`, `controlroom/scorecard.py`, existing CRE/maintainer | strict applicable retrieval, separate inspector channel, per-version consumption and comparable learning-benefit reports |

Proposed filenames are design targets, not claims that modules already exist. Prefer extending an existing owner module when it avoids duplicate authorities. Do not migrate the whole application to new state enums; version internal adapter records and preserve compatible public states.

Documentation resides in `specs/014-durable-local-autonomy/`: specification, research, evidence baseline, plan, data model, contracts/fixtures, acceptance cases, task/requirement traceability, quickstart, Codex prompt, validation ledger and future-promotion proposal.

## Delivery increments

1. **Establish baseline:** read pinned source and records, reproduce deterministic failures, inspect actual adapter limits and record unresolved native evidence. Keep the original terminal records unchanged.
   Define the role-specific local-model capability envelope and short-horizon task design before changing prompts or adding agents. See [local-model-design.md](local-model-design.md).
2. **Packet and completion MVP:** complete finding inventory, scoped retrieval, measured packet partitioning, semantic proposal, strict binder and durable receipt. Remove model-authored administrative/finalization work. Validate actual SDK serialization, not only Pydantic classes.
3. **Bounded execution:** separate limit dimensions; link mission/product ledgers; admit requests before dispatch; reconcile cancellation and late run adoption; recover verifier leases and publication receipts. Exercise crashes at every effect/ack boundary.
4. **Operational recovery:** typed incidents and approved recipes, resource isolation, model-free watchdog and restore tests. An exact signed release transition is required for any deployment rollback; absent authority, restart/reload only within approved configuration.
5. **Product/maintainer paths:** counterexample-driven scoped repair and dependency impact, existing resume compatibility, independent inspections and candidate-only CRE. Add validated lessons without a trusted-prompt shortcut.
   Implement DA-T037–044 as the core every-job learning increment: factual capture, bounded consolidation, compatible source validation, qualified retrieval and measured cross-job benefit. Successful ordinary work and verified negative observations are first-class sources. Preserve legacy repair and inspector lesson semantics.
6. **Qualification:** deterministic checks first, then frozen native protocol cohort, real RCC recovery, staged operational soaks and representative product benchmark. Keep each status separate; record NOT_RUN/BLOCKED when live prerequisites are absent.
7. **Measured adaptation:** when unchanged-profile qualification fails after deterministic fixes, compare one authorized model/runtime variable at a time. Evaluate harness candidates with stated predictions and independent held-out outcomes. Core delivery does not wait for future source-promotion policy approval.

## State and transaction design

Persist intent before effects; use case/mission/job/nonce keys, compare-and-set fencing and an outbox. Store immutable receipt versions that distinguish submission from admissibility and execution. Generate legacy compact completion only from a validated receipt projection. Receipt recovery after lost acknowledgment must not launch a second product attempt.

Maintain execution liveness independently of task outcome: launch ambiguity, running, cancellation requested, quiescent and unresolved states remain visible even after an order is blocked. Do not free GPU admission based solely on business terminality. The verifier uses a separate recoverable lease with stable worker identity and heartbeat.

Link continuation orders to a single root mission ledger; retain existing phase/work-order limits as additional constraints. Define how reservations, actual usage, late usage and imported historical receipts reconcile without double-counting. Refuse further admission after exhaustion. Use monotonic deadlines where possible and UTC persisted provenance across restart/clock changes.

## Evidence and qualification strategy

Follow [acceptance-tests.md](acceptance-tests.md). Use deterministic provider fixtures to reproduce protocol faults; label them as fixtures. Native qualification must run the actual selected Qwen → gateway → Fabro → MCP path. Mixed protocol cases must include valid repairs, correct blocks, evidence requests, invalid proposals and transport failures with frozen expected outcomes.

The 100-run protocol gate does not imply 99% reliability or prove all product repairs. The RCC and 30-work-order engineering cohorts measure actual independent outcomes. The 24/72/168h campaigns require eligible fault exposure and real work, not merely elapsed idle service time.

Qualify diagnosis, authoring, inspection and maintainer behavior separately. Compare coherent obligation decomposition with the frozen larger-task baseline while retaining identical source coverage and cumulative budgets. Measure stale-memory handling, semantic defect detection, false rejections, useful-plan rate, regression-free defect closure and stall behavior. Do not choose a model/runtime configuration from tokens-per-second or schema compliance alone. Same-Qwen agreement cannot replace independent evidence.

Add an end-to-end chronological learning scenario: ordinary job A → experience/disposition → independently qualified candidate → eligible job B retrieval/application → independent outcome comparison. Capture and deduplication can be tested without inference. Use current `test_m5_lessons.py` and `test_inspection_lessons.py` as mandatory regression anchors. A successful source job does not by itself prove transfer benefit, and a failed job does not prove its proposed remedy works.

Every completed implementation task cites passing evidence from the exact tested candidate revision using the repository evidence conventions. Deployment/model tests use a separate currently valid signed campaign; implementation and offline tests proceed while live authorization is absent. No credential/private manual/raw reasoning enters committed evidence.

## Compatibility, migration and rollback

Keep public legacy states and provider paths compatible; add explicit versioned adapter records. Test migration on copies of representative SQLite snapshots with history/usage conservation and restore verification. Do not rewrite the exhausted original mission. Runtime rollback means an authorized release transition, never an automatic downgrade of policy or database schema. Plan forward-compatible records before canary deployment.

Knowledge migration is additive: preserve v0.4 repair source checks and existing lesson IDs/history/usage; add explicitly versioned ordinary-outcome/negative-observation sources and their validators. Implement matching curator/MCP/schema/registry/lock updates through normal external engineering. Keep `IL-*.yaml` inspector knowledge separately reviewed, selected and CRE-qualified. Test actual phase and tool-version matching, not just the presence of those API parameters.

No automatic merge, deployment, new model allowlist, budget increase or gate relaxation is introduced. The optional future design is documented in [future-worker-promotion.md](future-worker-promotion.md).
