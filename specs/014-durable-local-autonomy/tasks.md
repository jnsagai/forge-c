# Tasks: Durable local autonomy and recovery

**Input:** authored Feature 014 specification, plan, local-model design, data model and contracts. All tasks begin unchecked. Tests are required by this feature.

An unchecked task may contain completed subwork; mark it complete only when the claimed implementation/qualification scope has passing evidence. Runtime qualification and long soaks are distinct milestones, not prerequisites for merging every independently verified core increment. Record unavailable host/campaign prerequisites explicitly and continue independent work.

Task IDs map one-to-one to requirement/test IDs in `traceability.csv`; dependencies below determine execution order, not numeric order. No tasks are marked parallel because several share control-plane modules. Independent fixture/document work may be split when file ownership is explicit.

## Baseline and local-model design

- [ ] **DA-T001 [US1]** Capture immutable baseline and native evidence inventory in `evidence/014-durable-local-autonomy/baseline/` and this feature's `validation.md`; reproduce available protocol failures and explicitly retain unknown v4 cause. Trace: DA-FR-001; DA-AT-001. Dependencies: none; host export may remain unavailable without blocking fixture work.

- [ ] **DA-T031 [US8]** Define a versioned per-role capability profile in the local qualification harness, recording actual model/precision/reasoning/schema/context identities and semantic case complexity; measure authorized baseline roles separately. Trace: DA-FR-031; DA-AT-031. Dependencies: DA-T001; design first, live measurement separately gated.

## US1/US8 — Complete evidence and bounded semantic decisions

- [ ] **DA-T002 [US1]** Implement complete finding inventories, completeness flags and hash-bound primary references in `factory/python/forge_factory/afo/bundle.py` and proposed `afo/diagnosis_packet.py`; add late-finding/incomplete-case tests. Trace: DA-FR-002; DA-AT-002. Dependencies: DA-T001 fixture baseline.

- [ ] **DA-T003 [US1]** Add scoped evidence access in `factory/python/forge_factory/mcp/servers/afo.py` and `afo_payload.py`; test case/role/phase/path/hash barriers through actual MCP tickets. Trace: DA-FR-003; DA-AT-003. Dependencies: DA-T002.

- [ ] **DA-T004 [US1]** Measure complete serialized prompts and partition coherent packets with coverage in the diagnosis packet/native adapter; add boundary/context tests under `factory/python/tests/`. Trace: DA-FR-004; DA-AT-004. Dependencies: DA-T002; DA-T031 design.

- [ ] **DA-T032 [US8]** Implement short-horizon obligation/task decomposition and global dependency/coverage checks in packet/recovery-context paths; compare with the same larger-task baseline without resetting budgets. Trace: DA-FR-032; DA-AT-032. Dependencies: DA-T002; DA-T004; DA-T031 design.

- [ ] **DA-T033 [US8]** Implement external evidence-indexed memory and compact checkpoints using existing hashes/artifact stores; test stale references, summary omissions and retrieval under the measured context allowance. Trace: DA-FR-033; DA-AT-033. Dependencies: DA-T002; DA-T003; DA-T031 design.

- [ ] **DA-T005 [US1]** Implement bounded semantic-proposal handling in proposed `factory/python/forge_factory/afo/semantic_proposal.py` and existing planner adapter; support evidence-request and blocked outcomes without broad tools. Trace: DA-FR-005; DA-AT-005. Dependencies: DA-T003; DA-T004; DA-T032.

- [ ] **DA-T006 [US1]** Bind proposals to the unchanged authoritative recovery-plan contract in `factory/python/forge_factory/afo/planner.py`/`recovery.py`; reject semantic coercion, missing evidence and superficial strategy changes. Trace: DA-FR-006; DA-AT-006. Dependencies: DA-T005.

- [ ] **DA-T007 [US1]** Add actual registered MCP/gateway contract integration tests around `mcp/servers/afo.py`, `fabro/runconfig.py` and the installed local adapter; qualify a narrow tool or constrained-output mode without assuming interoperability. Trace: DA-FR-007; DA-AT-007. Dependencies: DA-T005; deterministic wire fixtures first, native qualification later.

- [ ] **DA-T008 [US1]** Implement durable receipt projection and deterministic compact completion in `afo/local_agent.py`, `planner.py` and proposed `afo/completion_receipt.py`; fix missing-proposal misclassification with regressions. Trace: DA-FR-008; DA-AT-008. Dependencies: DA-T006.

- [ ] **DA-T009 [US1]** Integrate fenced idempotent receipt/dispatch/publication effects with existing AFO outbox/store; add crash-before/after-effect and lost-ack tests in `factory/python/tests/`. Trace: DA-FR-009; DA-AT-009. Dependencies: DA-T008.

## US2 — Accounting, cancellation and verification durability

- [ ] **DA-T010 [US2]** Separate request/tool/token/wall/correction counters in `policy/governor.py`, `policy/fabro_hook.py` and native adapter; reserve completion where model submission remains. Trace: DA-FR-010; DA-AT-010. Dependencies: DA-T005; DA-T008.

- [ ] **DA-T011 [US2]** Implement a shared mission ledger linked to existing order/resume accounting, proposed `afo/mission_ledger.py`; migrate copies of snapshots and deduplicate imported execution identities. Trace: DA-FR-011; DA-AT-011. Dependencies: DA-T009; no history rewrite.

- [ ] **DA-T012 [US2]** Add request-level admission and late/missing/overrun reconciliation in local agent, gateway and ledger paths; test concurrent reservations, restart and provider caps. Trace: DA-FR-012; DA-AT-012. Dependencies: DA-T010; DA-T011.

- [ ] **DA-T013 [US2]** Separate execution liveness from job outcome in `afo/local_agent.py` and `fabro/client.py`; retain leases and reconcile late native adoption/cancellation after terminality. Trace: DA-FR-013; DA-AT-013. Dependencies: DA-T009; DA-T011.

- [ ] **DA-T014 [US2]** Replace fragile verifier spawning in `afo/local_agent.py` with a stable verification job/outbox/lease and idempotent publication; inject conductor/verifier crashes. Trace: DA-FR-014; DA-AT-014. Dependencies: DA-T009; DA-T013.

## US8/US3 — Capability-aware remedies and operations

- [ ] **DA-T034 [US8]** Implement bounded sequential candidate selection/stall detection in `afo/planner.py`/`recovery.py` using independent verifier results and canonical failure/strategy signatures; reject confidence-only/majority ranking. Trace: DA-FR-034; DA-AT-034. Dependencies: DA-T005; DA-T011; DA-T032.

- [ ] **DA-T035 [US8]** Extend independent inspector qualification with held-out mutants, metamorphic/reference checks and deterministic semantic coverage reports; test same-Qwen correlated author/reviewer errors. Trace: DA-FR-035; DA-AT-035. Dependencies: DA-T031 profile design and deterministic fixtures; existing independent inspection tools/oracles. Live inspector qualification is a separate milestone.

- [ ] **DA-T036 [US8]** Implement measured capability/missing-evidence disposition in planner/recovery paths; permit only repartition or already qualified authorized local alternatives, otherwise typed block; test no retry/budget/cloud/training bypass. Trace: DA-FR-036; DA-AT-036. Dependencies: DA-T005; DA-T031 profile design and deterministic fixtures; DA-T033 and DA-T034 implementation/fixture milestones. Live model measurement is not required to implement this route.

- [ ] **DA-T015 [US3]** Route typed protocol/transport/native incidents in `afo/recovery.py` and `local_agent.py` to approved bounded remedies or explicit block/candidate paths; retain semantic no-strategy distinction. Trace: DA-FR-015; DA-AT-015. Dependencies: DA-T008; DA-T013; DA-T036.

- [ ] **DA-T016 [US3]** Extend existing supervisor/service recovery and backup/restore checks; add approved recipe inventory in `docs/afo/LOCAL-SELF-HEALING.md`; test rate limits, restart and clock jumps without model inference. Trace: DA-FR-016; DA-AT-016. Dependencies: DA-T013; DA-T014.

- [ ] **DA-T017 [US3]** Extend existing local-profile admission/preflight and bounded verifier-resource checks; test mount/disk pressure, one-inference admission and external-route denial. Trace: DA-FR-017; DA-AT-017. Dependencies: DA-T012; DA-T013.

- [ ] **DA-T018 [US3]** Expose separate service/native/mission progress plus redacted usage/stop/receipt fields through existing AFO status and controlroom scorecard paths; test stale heartbeat versus engineering progress. Trace: DA-FR-018; DA-AT-018. Dependencies: DA-T008; DA-T011; DA-T013.

## US4/US5 — Product repair and candidate improvement

- [ ] **DA-T019 [US4]** Implement counterexample/obligation-scoped repair context and impact tracking in `afo/recovery_context.py` and existing author rework paths; compare root causes with package symptoms. Trace: DA-FR-019; DA-AT-019. Dependencies: DA-T006; DA-T032; DA-T034.

- [ ] **DA-T020 [US4]** Integrate strategy dispatch with existing `brownfield.resume` and AFO runtime paths; test compatible prefix use and incompatible historical-revision refusal/fresh revalidation. Trace: DA-FR-020; DA-AT-020. Dependencies: DA-T009; DA-T019.

- [ ] **DA-T021 [US4]** Run independent author/inspector, gate/oracle integrity and sealed package regression; integrate changed-obligation/dependency reinspection without changing release criteria. Trace: DA-FR-021; DA-AT-021. Dependencies: DA-T019; DA-T020; DA-T035 inspection integration and deterministic regression; live inspector qualification gates product acceptance separately.

- [ ] **DA-T022 [US5]** Complete candidate-only maintainer/reproducer/CRE orchestration using existing maintainer allowlists and `afo/local_agent.py`; test protected-path rejection and holdout-failing candidate quarantine. Trace: DA-FR-022; DA-AT-022. Dependencies: DA-T014; DA-T015.

- [ ] **DA-T023 [US5]** Integrate evidence-linked lessons with version/applicability/invalidation checks in the existing lessons path; test malicious, stale and unsupported lessons without widening trust. Trace: DA-FR-023; DA-AT-023. Dependencies: DA-T019; DA-T033.

## US6 — Qualification campaigns

- [ ] **DA-T024 [US6]** Add a frozen native protocol campaign manifest, dry-run/report and separately authorized live entry point under the existing local qualification harness; freeze 20 cases × 5 repeats and expected outcomes before execution. Trace: DA-FR-024; DA-AT-024. Dependencies: DA-T007 through DA-T018 core fixes; DA-T031 through DA-T036 implementation/fixture milestones only. Harness preparation and live diagnosis qualification do not require prior successful author/inspector/maintainer qualification; live execution is separately authorized.

- [ ] **DA-T025 [US6]** Prepare and, only when authorized, execute RCC qualification using actual SWE.3 evidence, shared history and every native phase; validate sealed READY and GPIO prerequisite gating. Trace: DA-FR-025; DA-AT-025. Dependencies: DA-T019 through DA-T021; DA-T024 live protocol qualification.

- [ ] **DA-T026 [US6]** Implement fault-campaign manifest/reporting and perform separately authorized 24h/72h/168h operational campaigns; retain all fault exposure and intervention outcomes in feature evidence. Trace: DA-FR-026; DA-AT-026. Dependencies: DA-T016 through DA-T018; core verified; real-work/live authority.

- [ ] **DA-T027 [US6]** Freeze and run the representative Omniverse2 product benchmark with full denominators, seeded critical defects, inspector false rejection and comparable prompt/cost measurements. Trace: DA-FR-027; DA-AT-027. Dependencies: DA-T021; DA-T024; relevant live authority and input readiness.

- [ ] **DA-T028 [US6]** Implement controlled local-model/runtime comparison reports using the same frozen cases and actual configuration identities; permit a bounded comparison after deterministic fixes and unchanged-baseline measurement, without requiring RCC success. Trace: DA-FR-028; DA-AT-028. Dependencies: DA-T024 harness; DA-T031 profile design; live comparisons additionally require recorded unchanged-baseline measurements; no dependency on successful DA-T025.

## US7/US5 — Compatibility and honest handoff

- [ ] **DA-T029 [US7]** Run inherited provider/native/ACP/AFO/brownfield/local-profile/package regressions, static design/provenance checks and independent CRE on the exact candidate; preserve unavailable live checks as NOT_RUN. Trace: DA-FR-029; DA-AT-029. Dependencies: per increment; final core changes complete.

- [ ] **DA-T030 [US5]** Maintain readiness/evidence ledgers and document future-worker-promotion as proposal-only; update `docs/afo/LOCAL-SELF-HEALING.md` and this feature's `validation.md` without adding an auto-promote switch. Trace: DA-FR-030; DA-AT-030. Dependencies: independent documentation; final status after relevant tests.

## US9 — Continuous learning from every driver and feature

Core scope: extend existing knowledge, events, inspection, CRE and KPI paths. Design compatible source types early; capture/disposition can ship before live effectiveness is demonstrated. Independent implementation and fixture milestones do not wait for live campaign authorization.

- [ ] **DA-T037 [US9]** Add idempotent factual job/phase experience capture through existing `events/*`, `workorder.py`, AFO reconciliation and `knowledge/store.py`; cover all terminal outcomes, immutable package references and adopted/replayed execution deduplication. Trace: DA-FR-037; DA-AT-037. Dependencies: existing event receipts; DA-T009 durable effects.

- [ ] **DA-T038 [US9]** Add recoverable learning intent/disposition and bounded consolidation in the existing knowledge/curator/AFO dispatch paths; deterministic duplicate/no-new-evidence handling and explicit deferred budgets must not require extra inference. Trace: DA-FR-038; DA-AT-038. Dependencies: DA-T037; DA-T011/012 accounting and admission.

- [ ] **DA-T039 [US9]** Extend the existing lesson contract, `knowledge/store.py`, `mcp/servers/knowledge.py` and lessons-curator SKILL plus matching registries/locks with versioned ordinary-outcome/negative-observation sources; preserve legacy PROMOTED repair validation and migration history. Trace: DA-FR-039; DA-AT-039. Dependencies: DA-T037; source-contract design before DA-T038 model integration; no live campaign prerequisite.

- [ ] **DA-T040 [US9]** Integrate qualified lesson retrieval before relevant jobs/phases via existing knowledge MCP/packet builders; enforce actual phase/role/target/source/tool-version predicates, current k/token bounds and measured context; deliver complete bounded lesson meaning/constraints/provenance via authorized artifact resolution or packet assembly, testing an exclusion after character 120 and explicit omission when unfit; record exposure versus application. Trace: DA-FR-040; DA-AT-040. Dependencies: DA-T039; DA-T003/004 role and context implementation.

- [ ] **DA-T041 [US9]** Implement independent source-specific candidate validation and applicable/adverse qualification through existing knowledge/CRE tools; retain generic inspector IL recorded-source/paired-defect/CRE promotion and author-inspector boundaries. Trace: DA-FR-041; DA-AT-041. Dependencies: DA-T039; existing independent knowledge/inspection validators.

- [ ] **DA-T042 [US9]** Add chronological job-A-to-B transfer and frozen memory-enabled/baseline comparisons under existing KPI/qualification mechanisms, including all learning costs and holdout isolation; demonstrate benefit without a per-run monotonic-score claim. Trace: DA-FR-042; DA-AT-042. Dependencies: DA-T040/041 implementation; authorized model evaluation separately gated.

- [ ] **DA-T043 [US9]** Extend existing knowledge dedup/history/TTL/retract/consumer tracking with source-scope/version identity, contradiction detection and successor-version qualification; test stale tools/MCUs and rollback of retrieval eligibility. Trace: DA-FR-043; DA-AT-043. Dependencies: DA-T039/040/041 implementation.

- [ ] **DA-T044 [US9]** Connect measured recurring findings/success patterns to the appropriate existing CAPA/CRE/maintainer or external-engineering lane (repair reproducer versus measured-baseline CHANGE, without fake incidents), and add separate learning coverage/usage/benefit views to `kpi/engine.py` and `controlroom/scorecard.py`. Trace: DA-FR-044; DA-AT-044. Dependencies: DA-T037 through DA-T043 implementation milestones; demonstrated benefit remains separately reported.

## Completion evidence

Use the repository evidence convention (`scripts/mark_task.py` where applicable) and cite an existing passing `evidence/v0.4/runs/.../latest.json` with tested revision, command, exit code and artifact hashes. Spec validators validate documentation/contracts only; their PASS cannot tick implementation tasks. Do not overwrite old evidence.

For live-containing tasks, document implementation and live status separately until both required parts are evidenced. The 168-hour soak, 30-day SLO observation and future policy amendment must not prevent delivery/review of verified core fixes; they constrain the associated readiness claim.
