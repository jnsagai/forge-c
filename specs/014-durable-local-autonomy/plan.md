# Implementation Plan: Durable local autonomy and recovery

**Branch**: `feat/014-durable-local-autonomy` | **Date**: 2026-10-25 | **Spec**: [spec.md](spec.md)

## Summary

Repair the diagnosis-to-execution boundary before evaluating another product retry. Extend existing case preparation, MCP, native adapter, AFO ledger/outbox and verifier. Make Qwen return a small semantic judgment; deterministic code binds the authoritative plan, validates admission, records the receipt and completes the job.

Also close the learning loop on every ordinary driver/feature job using the existing knowledge, events, curator, inspection-lessons, CRE and KPI components. [Continuous learning](continuous-learning.md) defines the additive extension; a second learning engine or unrelated memory stack is not needed.

Make continuous 24/7 service a P0 core requirement. [Continuous operation](continuous-operation.md) defines how existing AFO/systemd/supervisor services survive empty or exhausted campaigns, process failures and dependency waits, while preserving bounded jobs and authenticated operator control. Implement this increment alongside core recovery; it is not a future enhancement.

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
| Continuous operation | `afo/conductor.py`, `scheduler.py`, `watchdog.py`, `services.py`, existing queue/outbox, `deploy/systemd/afo/*`, supervisor service | durable operations intent, bounded item isolation/fairness, independent cooldown recovery after start-limit exhaustion, resource hygiene and separate availability reporting |
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
4. **Operational recovery and 24/7 service:** typed incidents and approved recipes, resource isolation, model-free watchdog and restore tests. Implement DA-T045–052 through existing service/queue/operations paths: indefinite service intent, actual local units, boot/crash/hang/clean-exit/start-limit recovery, persistent bounded waiting, item isolation, fair scheduling, long-run resource hygiene and respected operator stop. An exact signed release transition is required for any deployment rollback; absent authority, restart/reload only within approved configuration.
5. **Product/maintainer paths:** counterexample-driven scoped repair and dependency impact, existing resume compatibility, independent inspections and candidate-only CRE. Add validated lessons without a trusted-prompt shortcut.
   Implement DA-T037–044 as the core every-job learning increment: factual capture, bounded consolidation, compatible source validation, qualified retrieval and measured cross-job benefit. Successful ordinary work and verified negative observations are first-class sources. Preserve legacy repair and inspector lesson semantics.
6. **Qualification:** deterministic checks first, then frozen native protocol cohort, real RCC recovery, staged operational soaks and representative product benchmark. Keep each status separate; record NOT_RUN/BLOCKED when live prerequisites are absent.
7. **Local inspection and offline improvement (US11, owner decisions 2026-10-26):** stepwise closed-question inspection measured on the learning set, then calibrated on a pre-registered held-out set; advisory continuation only after the full escalation ladder, with a gap register and attempt records; an offline export bundle, owner-signed dispositions and a signed patch-import gate with local preflight, regression and rollback (DA-T053–058). The deployed factory stays local and offline.
8. **Measured adaptation:** when unchanged-profile qualification fails after deterministic fixes, compare one authorized model/runtime variable at a time. Evaluate harness candidates with stated predictions and independent held-out outcomes. Core delivery does not wait for future source-promotion policy approval.

## State and transaction design

Persist intent before effects; use case/mission/job/nonce keys, compare-and-set fencing and an outbox. Store immutable receipt versions that distinguish submission from admissibility and execution. Generate legacy compact completion only from a validated receipt projection. Receipt recovery after lost acknowledgment must not launch a second product attempt.

Maintain execution liveness independently of task outcome: launch ambiguity, running, cancellation requested, quiescent and unresolved states remain visible even after an order is blocked. Do not free GPU admission based solely on business terminality. The verifier uses a separate recoverable lease with stable worker identity and heartbeat.

Link continuation orders to a single root mission ledger; retain existing phase/work-order limits as additional constraints. Define how reservations, actual usage, late usage and imported historical receipts reconcile without double-counting. Refuse further admission after exhaustion. Use monotonic deadlines where possible and UTC persisted provenance across restart/clock changes.

Refusal after exhaustion is scoped to the affected lineage. The factory continues model-free service, waiting/probing and unrelated eligible work. Persist operations intent/epoch separately from AFO inference mode, plus dependency wait/cooldown records and observed outage intervals. Bound each loop stage and isolate item-local failures without hiding shared integrity failures. A stopped native worker or completed benchmark must not become a command to stop the Conductor.

## Evidence and qualification strategy

Follow [acceptance-tests.md](acceptance-tests.md). Use deterministic provider fixtures to reproduce protocol faults; label them as fixtures. Native qualification must run the actual selected Qwen → gateway → Fabro → MCP path. Mixed protocol cases must include valid repairs, correct blocks, evidence requests, invalid proposals and transport failures with frozen expected outcomes.

The 100-run protocol gate does not imply 99% reliability or prove all product repairs. The RCC and 30-work-order engineering cohorts measure actual independent outcomes. The 24/72/168h campaigns require eligible fault exposure and real work, not merely elapsed idle service time.

Continuous-operation qualification must also test unexpected exit code 0, exhausted systemd start limits, restored dependencies after prolonged waits, a denied item ahead of eligible work, disk/mount faults, deliberate operator shutdown and post-campaign service continuity. Inspect installed systemd and actual local-profile units; rendered templates alone do not prove host behavior. Retain complete gross 24/7 outage accounting and separately qualify the 30-day availability objective.

Qualify diagnosis, authoring, inspection and maintainer behavior separately. Compare coherent obligation decomposition with the frozen larger-task baseline while retaining identical source coverage and cumulative budgets. Measure stale-memory handling, semantic defect detection, false rejections, useful-plan rate, regression-free defect closure and stall behavior. Do not choose a model/runtime configuration from tokens-per-second or schema compliance alone. Same-Qwen agreement cannot replace independent evidence.

Add an end-to-end chronological learning scenario: ordinary job A → experience/disposition → independently qualified candidate → eligible job B retrieval/application → independent outcome comparison. Capture and deduplication can be tested without inference. Use current `test_m5_lessons.py` and `test_inspection_lessons.py` as mandatory regression anchors. A successful source job does not by itself prove transfer benefit, and a failed job does not prove its proposed remedy works.

Every completed implementation task cites passing evidence from the exact tested candidate revision using the repository evidence conventions. Deployment/model tests use a separate currently valid signed campaign; implementation and offline tests proceed while live authorization is absent. No credential/private manual/raw reasoning enters committed evidence.

## Compatibility, migration and rollback

Keep public legacy states and provider paths compatible; add explicit versioned adapter records. Test migration on copies of representative SQLite snapshots with history/usage conservation and restore verification. Do not rewrite the exhausted original mission. Runtime rollback means an authorized release transition, never an automatic downgrade of policy or database schema. Plan forward-compatible records before canary deployment.

Knowledge migration is additive: preserve v0.4 repair source checks and existing lesson IDs/history/usage; add explicitly versioned ordinary-outcome/negative-observation sources and their validators. Implement matching curator/MCP/schema/registry/lock updates through normal external engineering. Keep `IL-*.yaml` inspector knowledge separately reviewed, selected and CRE-qualified. Test actual phase and tool-version matching, not just the presence of those API parameters.

No automatic merge, deployment, new model allowlist, budget increase or gate relaxation is introduced. The optional future design is documented in [future-worker-promotion.md](future-worker-promotion.md).

## Incremental M1 engineering sequence

Implement [the owner handoff](IMPLEMENTATION-INCREMENTAL-E2E.md) through the current
work-order/peripheral, phase runner/gate, Fabro/MCP and release mechanisms.
1. Freeze a distinct two-function IDR operation scope, original frozen ST/CMSIS inputs,
   source-backed candidate requirements and independent negative oracle.
2. Add a minimal provided-requirements import with content/source/scope/review provenance;
   pending human review is a real live prerequisite, not an inferred approval.
3. Opt in to versioned development execution; share finite repair allowances across
   nested calls/re-entry and record deferred ladder steps without altering other profiles.
4. Exercise real preparation, import/validation, phase transitions, evidence, compilation,
   tests and package boundaries with explicitly substituted provider responses only.
5. Preserve98d066d and reproduce the original failed-incident recovery/advisory route.
6. Prepare exact per-role serialized admission, including release and gateway reasoning,
   plus source/profile/model pins and a finite live harness. Never use old expired authority.
7. Run M1 only with actual review/current runtime scope; keep every unresolved acceptance
   prerequisite explicit. Only after accepted M1 proceed to unassisted M2, then M3–M5.

Administrative source records stay hash-bound outside small semantic role views. No budget,
reasoning, tokenizer, backend or model change is inferred from this incremental brief.
