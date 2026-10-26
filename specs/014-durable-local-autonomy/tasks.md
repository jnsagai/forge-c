# Tasks: Durable local autonomy and recovery

**Input:** authored Feature 014 specification, plan, local-model design, data model and contracts. All tasks begin unchecked. Tests are required by this feature.

An unchecked task may contain completed subwork; mark it complete only when the claimed implementation/qualification scope has passing evidence. Runtime qualification and long soaks are distinct milestones, not prerequisites for merging every independently verified core increment. Record unavailable host/campaign prerequisites explicitly and continue independent work.

Task IDs map one-to-one to requirement/test IDs in `traceability.csv`; dependencies below determine execution order, not numeric order. No tasks are marked parallel because several share control-plane modules. Independent fixture/document work may be split when file ownership is explicit.

## Baseline and local-model design

- [X] **DA-T001 [US1]** Capture immutable baseline and native evidence inventory in `evidence/014-durable-local-autonomy/baseline/` and this feature's `validation.md`; reproduce available protocol failures and explicitly retain unknown v4 cause. Trace: DA-FR-001; DA-AT-001. Dependencies: none; host export may remain unavailable without blocking fixture work. ✅ Evidence: `evidence/v0.4/runs/DA014-history/latest.json`, `evidence/v0.4/runs/DA014-core/latest.json`

- [ ] **DA-T031 [US8]** Define a versioned per-role capability profile in the local qualification harness, recording actual model/precision/reasoning/schema/context identities and semantic case complexity; measure authorized baseline roles separately. Trace: DA-FR-031; DA-AT-031. Dependencies: DA-T001; design first, live measurement separately gated.

## US1/US8 — Complete evidence and bounded semantic decisions

- [X] **DA-T002 [US1]** Implement complete finding inventories, completeness flags and hash-bound primary references in `factory/python/forge_factory/afo/bundle.py` and proposed `afo/diagnosis_packet.py`; add late-finding/incomplete-case tests. Trace: DA-FR-002; DA-AT-002. Dependencies: DA-T001 fixture baseline. ✅ Evidence: `evidence/v0.4/runs/DA014-core/latest.json`

- [X] **DA-T003 [US1]** Add scoped evidence access in `factory/python/forge_factory/mcp/servers/afo.py` and `afo_payload.py`; test case/role/phase/path/hash barriers through actual MCP tickets. Trace: DA-FR-003; DA-AT-003. Dependencies: DA-T002. ✅ Evidence: `evidence/v0.4/runs/DA014-core/latest.json`

- [ ] **DA-T004 [US1]** Measure complete serialized prompts and partition coherent packets with coverage in the diagnosis packet/native adapter; add boundary/context tests under `factory/python/tests/`. Trace: DA-FR-004; DA-AT-004. Dependencies: DA-T002; DA-T031 design.

- [ ] **DA-T032 [US8]** Implement short-horizon obligation/task decomposition and global dependency/coverage checks in packet/recovery-context paths; compare with the same larger-task baseline without resetting budgets. Trace: DA-FR-032; DA-AT-032. Dependencies: DA-T002; DA-T004; DA-T031 design.

- [ ] **DA-T033 [US8]** Implement external evidence-indexed memory and compact checkpoints using existing hashes/artifact stores; test stale references, summary omissions and retrieval under the measured context allowance. Trace: DA-FR-033; DA-AT-033. Dependencies: DA-T002; DA-T003; DA-T031 design.

- [ ] **DA-T005 [US1]** Implement bounded semantic-proposal handling in proposed `factory/python/forge_factory/afo/semantic_proposal.py` and existing planner adapter; support evidence-request and blocked outcomes without broad tools. Trace: DA-FR-005; DA-AT-005. Dependencies: DA-T003; DA-T004; DA-T032.

- [X] **DA-T006 [US1]** Bind proposals to the unchanged authoritative recovery-plan contract in `factory/python/forge_factory/afo/planner.py`/`recovery.py`; reject semantic coercion, missing evidence and superficial strategy changes. Trace: DA-FR-006; DA-AT-006. Dependencies: DA-T005. ✅ Evidence: `evidence/v0.4/runs/DA014-core/latest.json`

- [ ] **DA-T007 [US1]** Add actual registered MCP/gateway contract integration tests around `mcp/servers/afo.py`, `fabro/runconfig.py` and the installed local adapter; qualify a narrow tool or constrained-output mode without assuming interoperability. Trace: DA-FR-007; DA-AT-007. Dependencies: DA-T005; deterministic wire fixtures first, native qualification later.

- [X] **DA-T008 [US1]** Implement durable receipt projection and deterministic compact completion in `afo/local_agent.py`, `planner.py` and proposed `afo/completion_receipt.py`; fix missing-proposal misclassification with regressions. Trace: DA-FR-008; DA-AT-008. Dependencies: DA-T006. ✅ Evidence: `evidence/v0.4/runs/DA014-core/latest.json`

- [X] **DA-T009 [US1]** Integrate fenced idempotent receipt/dispatch/publication effects with existing AFO outbox/store; add crash-before/after-effect and lost-ack tests in `factory/python/tests/`. Trace: DA-FR-009; DA-AT-009. Dependencies: DA-T008. ✅ Evidence: `evidence/v0.4/runs/DA014-core/latest.json`

## US2 — Accounting, cancellation and verification durability

- [ ] **DA-T010 [US2]** Separate request/tool/token/wall/correction counters in `policy/governor.py`, `policy/fabro_hook.py` and native adapter; reserve completion where model submission remains. Trace: DA-FR-010; DA-AT-010. Dependencies: DA-T005; DA-T008.

- [X] **DA-T011 [US2]** Implement a shared mission ledger linked to existing order/resume accounting, proposed `afo/mission_ledger.py`; migrate copies of snapshots and deduplicate imported execution identities. Trace: DA-FR-011; DA-AT-011. Dependencies: DA-T009; no history rewrite. ✅ Evidence: `evidence/v0.4/runs/DA014-core/latest.json`

- [ ] **DA-T012 [US2]** Add request-level admission and late/missing/overrun reconciliation in local agent, gateway and ledger paths; test concurrent reservations, restart and provider caps. Trace: DA-FR-012; DA-AT-012. Dependencies: DA-T010; DA-T011.

- [ ] **DA-T013 [US2]** Separate execution liveness from job outcome in `afo/local_agent.py` and `fabro/client.py`; retain leases and reconcile late native adoption/cancellation after terminality. Trace: DA-FR-013; DA-AT-013. Dependencies: DA-T009; DA-T011.

- [X] **DA-T014 [US2]** Replace fragile verifier spawning in `afo/local_agent.py` with a stable verification job/outbox/lease and idempotent publication; inject conductor/verifier crashes. Trace: DA-FR-014; DA-AT-014. Dependencies: DA-T009; DA-T013. ✅ Evidence: `evidence/v0.4/runs/DA014-core/latest.json`

## US8/US3 — Capability-aware remedies and operations

- [ ] **DA-T034 [US8]** Implement bounded sequential candidate selection/stall detection in `afo/planner.py`/`recovery.py` using independent verifier results and canonical failure/strategy signatures; reject confidence-only/majority ranking. Trace: DA-FR-034; DA-AT-034. Dependencies: DA-T005; DA-T011; DA-T032.

- [ ] **DA-T035 [US8]** Extend independent inspector qualification with held-out mutants, metamorphic/reference checks and deterministic semantic coverage reports; test same-Qwen correlated author/reviewer errors. Trace: DA-FR-035; DA-AT-035. Dependencies: DA-T031 profile design and deterministic fixtures; existing independent inspection tools/oracles. Live inspector qualification is a separate milestone.

- [ ] **DA-T036 [US8]** Implement measured capability/missing-evidence disposition in planner/recovery paths; permit only repartition or already qualified authorized local alternatives, otherwise typed block; test no retry/budget/cloud/training bypass. Trace: DA-FR-036; DA-AT-036. Dependencies: DA-T005; DA-T031 profile design and deterministic fixtures; DA-T033 and DA-T034 implementation/fixture milestones. Live model measurement is not required to implement this route.

- [X] **DA-T015 [US3]** Route typed protocol/transport/native incidents in `afo/recovery.py` and `local_agent.py` to approved bounded remedies or explicit block/candidate paths; retain semantic no-strategy distinction. Trace: DA-FR-015; DA-AT-015. Dependencies: DA-T008; DA-T013; DA-T036. ✅ Evidence: `evidence/v0.4/runs/DA014-core/latest.json`

- [ ] **DA-T016 [US3]** Extend existing supervisor/service recovery and backup/restore checks; add approved recipe inventory in `docs/afo/LOCAL-SELF-HEALING.md`; test rate limits, restart and clock jumps without model inference. Trace: DA-FR-016; DA-AT-016. Dependencies: DA-T013; DA-T014.

- [ ] **DA-T017 [US3]** Extend existing local-profile admission/preflight and bounded verifier-resource checks; test mount/disk pressure, one-inference admission and external-route denial. Trace: DA-FR-017; DA-AT-017. Dependencies: DA-T012; DA-T013.

- [ ] **DA-T018 [US3]** Expose separate service/native/mission progress plus redacted usage/stop/receipt fields through existing AFO status and controlroom scorecard paths; test stale heartbeat versus engineering progress. Trace: DA-FR-018; DA-AT-018. Dependencies: DA-T008; DA-T011; DA-T013.

## US4/US5 — Product repair and candidate improvement

- [ ] **DA-T019 [US4]** Implement counterexample/obligation-scoped repair context and impact tracking in `afo/recovery_context.py` and existing author rework paths; compare root causes with package symptoms. Trace: DA-FR-019; DA-AT-019. Dependencies: DA-T006; DA-T032; DA-T034.

- [X] **DA-T020 [US4]** Integrate strategy dispatch with existing `brownfield.resume` and AFO runtime paths; test compatible prefix use and incompatible historical-revision refusal/fresh revalidation. Trace: DA-FR-020; DA-AT-020. Dependencies: DA-T009; DA-T019. ✅ Evidence: `evidence/v0.4/runs/DA014-core/latest.json`

- [ ] **DA-T021 [US4]** Run independent author/inspector, gate/oracle integrity and sealed package regression; integrate changed-obligation/dependency reinspection without changing release criteria. Trace: DA-FR-021; DA-AT-021. Dependencies: DA-T019; DA-T020; DA-T035 inspection integration and deterministic regression; live inspector qualification gates product acceptance separately.

- [X] **DA-T022 [US5]** Complete candidate-only maintainer/reproducer/CRE orchestration using existing maintainer allowlists and `afo/local_agent.py`; test protected-path rejection and holdout-failing candidate quarantine. Trace: DA-FR-022; DA-AT-022. Dependencies: DA-T014; DA-T015. ✅ Evidence: `evidence/v0.4/runs/DA014-core/latest.json`

- [X] **DA-T023 [US5]** Integrate evidence-linked lessons with version/applicability/invalidation checks in the existing lessons path; test malicious, stale and unsupported lessons without widening trust. Trace: DA-FR-023; DA-AT-023. Dependencies: DA-T019; DA-T033. ✅ Evidence: `evidence/v0.4/runs/DA014-core/latest.json`

## US6 — Qualification campaigns

- [ ] **DA-T024 [US6]** Add a frozen native protocol campaign manifest, dry-run/report and separately authorized live entry point under the existing local qualification harness; freeze 20 cases × 5 repeats and expected outcomes before execution. Trace: DA-FR-024; DA-AT-024. Dependencies: DA-T007 through DA-T018 core fixes; DA-T031 through DA-T036 implementation/fixture milestones only. Harness preparation and live diagnosis qualification do not require prior successful author/inspector/maintainer qualification; live execution is separately authorized.

- [ ] **DA-T025 [US6]** Prepare and, only when authorized, execute RCC qualification using actual SWE.3 evidence, shared history and every native phase; validate sealed READY and GPIO prerequisite gating. Trace: DA-FR-025; DA-AT-025. Dependencies: DA-T019 through DA-T021; DA-T024 live protocol qualification.

- [ ] **DA-T026 [US6]** Implement fault-campaign manifest/reporting and perform separately authorized 24h/72h/168h operational campaigns; retain all fault exposure and intervention outcomes in feature evidence. Trace: DA-FR-026; DA-AT-026. Dependencies: DA-T016 through DA-T018; core verified; real-work/live authority.

- [ ] **DA-T027 [US6]** Freeze and run the representative Omniverse2 product benchmark with full denominators, seeded critical defects, inspector false rejection and comparable prompt/cost measurements. Trace: DA-FR-027; DA-AT-027. Dependencies: DA-T021; DA-T024; relevant live authority and input readiness.

- [ ] **DA-T028 [US6]** Implement controlled local-model/runtime comparison reports using the same frozen cases and actual configuration identities; permit a bounded comparison after deterministic fixes and unchanged-baseline measurement, without requiring RCC success. Trace: DA-FR-028; DA-AT-028. Dependencies: DA-T024 harness; DA-T031 profile design; live comparisons additionally require recorded unchanged-baseline measurements; no dependency on successful DA-T025.

## US7/US5 — Compatibility and honest handoff

- [ ] **DA-T029 [US7]** Run inherited provider/native/ACP/AFO/brownfield/local-profile/package regressions, static design/provenance checks and independent CRE on the exact candidate; preserve unavailable live checks as NOT_RUN. Trace: DA-FR-029; DA-AT-029. Dependencies: per increment; final core changes complete.

- [X] **DA-T030 [US5]** Maintain readiness/evidence ledgers and document future-worker-promotion as proposal-only; update `docs/afo/LOCAL-SELF-HEALING.md` and this feature's `validation.md` without adding an auto-promote switch. Trace: DA-FR-030; DA-AT-030. Dependencies: independent documentation; final status after relevant tests. ✅ Evidence: `evidence/v0.4/runs/DA014-docs/latest.json`

## US9 — Continuous learning from every driver and feature

Core scope: extend existing knowledge, events, inspection, CRE and KPI paths. Design compatible source types early; capture/disposition can ship before live effectiveness is demonstrated. Independent implementation and fixture milestones do not wait for live campaign authorization.

- [X] **DA-T037 [US9]** Add idempotent factual job/phase experience capture through existing `events/*`, `workorder.py`, AFO reconciliation and `knowledge/store.py`; cover all terminal outcomes, immutable package references and adopted/replayed execution deduplication. Trace: DA-FR-037; DA-AT-037. Dependencies: existing event receipts; DA-T009 durable effects. ✅ Evidence: `evidence/v0.4/runs/DA014-core/latest.json`

- [X] **DA-T038 [US9]** Add recoverable learning intent/disposition and bounded consolidation in the existing knowledge/curator/AFO dispatch paths; deterministic duplicate/no-new-evidence handling and explicit deferred budgets must not require extra inference. Trace: DA-FR-038; DA-AT-038. Dependencies: DA-T037; DA-T011/012 accounting and admission. ✅ Evidence: `evidence/v0.4/runs/DA014-core/latest.json`

- [X] **DA-T039 [US9]** Extend the existing lesson contract, `knowledge/store.py`, `mcp/servers/knowledge.py` and lessons-curator SKILL plus matching registries/locks with versioned ordinary-outcome/negative-observation sources; preserve legacy PROMOTED repair validation and migration history. Trace: DA-FR-039; DA-AT-039. Dependencies: DA-T037; source-contract design before DA-T038 model integration; no live campaign prerequisite. ✅ Evidence: `evidence/v0.4/runs/DA014-core/latest.json`

- [ ] **DA-T040 [US9]** Integrate qualified lesson retrieval before relevant jobs/phases via existing knowledge MCP/packet builders; enforce actual phase/role/target/source/tool-version predicates, current k/token bounds and measured context; deliver complete bounded lesson meaning/constraints/provenance via authorized artifact resolution or packet assembly, testing an exclusion after character 120 and explicit omission when unfit; record exposure versus application. Trace: DA-FR-040; DA-AT-040. Dependencies: DA-T039; DA-T003/004 role and context implementation. Status 2026-10-26: both delivery paths tested (`tests/test_da014_lesson_delivery.py`): complete meaning past character 120 in the packet and over MCP, explicit whole-block omission (`lessons_omitted` CONTEXT_UNFIT; MCP `omitted_unfit`) instead of refusing the task, no lesson for inspectors, holdouts, other targets or tool versions, EXPOSURE with the packet input hash. Over MCP the provenance travels as a hash-bound stored artifact because a full lesson does not fit the 2048-byte tool result. APPLICATION is not yet recorded at runtime; native DA-AT-040 NOT_RUN.

- [ ] **DA-T041 [US9]** Implement independent source-specific candidate validation and applicable/adverse qualification through existing knowledge/CRE tools; retain generic inspector IL recorded-source/paired-defect/CRE promotion and author-inspector boundaries. Trace: DA-FR-041; DA-AT-041. Dependencies: DA-T039; existing independent knowledge/inspection validators.

- [ ] **DA-T042 [US9]** Add chronological job-A-to-B transfer and frozen memory-enabled/baseline comparisons under existing KPI/qualification mechanisms, including all learning costs and holdout isolation; demonstrate benefit without a per-run monotonic-score claim. Trace: DA-FR-042; DA-AT-042. Dependencies: DA-T040/041 implementation; authorized model evaluation separately gated.

- [X] **DA-T043 [US9]** Extend existing knowledge dedup/history/TTL/retract/consumer tracking with source-scope/version identity, contradiction detection and successor-version qualification; test stale tools/MCUs and rollback of retrieval eligibility. Trace: DA-FR-043; DA-AT-043. Dependencies: DA-T039/040/041 implementation. ✅ Evidence: `evidence/v0.4/runs/DA014-core/latest.json`

- [X] **DA-T044 [US9]** Connect measured recurring findings/success patterns to the appropriate existing CAPA/CRE/maintainer or external-engineering lane (repair reproducer versus measured-baseline CHANGE, without fake incidents), and add separate learning coverage/usage/benefit views to `kpi/engine.py` and `controlroom/scorecard.py`. Trace: DA-FR-044; DA-AT-044. Dependencies: DA-T037 through DA-T043 implementation milestones; demonstrated benefit remains separately reported. ✅ Evidence: `evidence/v0.4/runs/DA014-core/latest.json`

## US10 — Continuous 24/7 factory operation (P0)

Core increment through existing AFO/systemd/supervisor capabilities. Service lifetime is indefinite; individual engineering jobs and all budgets remain finite. Design operations intent and restart ownership before wiring automatic recovery so operator stop is preserved from the first increment.

- [X] **DA-T045 [US10]** Add compatible durable operations intent and separate service/authority/job state in existing Conductor/operations paths; prevent production finite-cycle/end-of-campaign exit and verify last-job/empty/exhausted-queue continuity. Trace: DA-FR-045; DA-AT-045. Dependencies: DA-T009/011/013 durable state/accounting/liveness; DA-T050 operator-control design before activation. ✅ Evidence: `evidence/v0.4/runs/DA014-core/latest.json`

- [ ] **DA-T046 [US10]** Extend existing service renderer/templates and supervisor/watchdog with approved boot, crash, unexpected clean-exit, hung-cycle and start-limit recovery; persist bounded slow-path cooldown and respect actual local-profile dependencies and operator intent. Test real systemd semantics separately from fixture/render checks. Trace: DA-FR-046; DA-AT-046. Dependencies: DA-T016/017; DA-T045/050 implementation before recovery activation.

- [X] **DA-T047 [US10]** Persist dependency wait/reprobe/recovery predicates in existing queue/supervisor operations paths; bound probes and subprocess calls, preserve cooldown across restart and automatically resume only eligible work after verified restoration. Exercise long outages, exhausted authority and ambiguous native execution without budget/lease resets. Trace: DA-FR-047; DA-AT-047. Dependencies: DA-T011/013/015/045; coordinate DA-T046 recovery ownership. ✅ Evidence: `evidence/v0.4/runs/DA014-core/latest.json`

- [X] **DA-T048 [US10]** Add item-local exception containment and fair continuation to existing scheduler/reconciliation/learning paths, including authority-refused head-of-line and malformed candidates; preserve shared integrity fail-closed behavior, dependencies and one-inference admission. Trace: DA-FR-048; DA-AT-048. Dependencies: DA-T045/047; DA-T038 learning integration where enabled. ✅ Evidence: `evidence/v0.4/runs/DA014-core/latest.json`

- [ ] **DA-T049 [US10]** Extend existing resource/retention/backup/preflight mechanisms for long-running service: bounded housekeeping, evidence/pin protection, reserved control-plane capacity, backpressure and missing/full/read-only-mount observation. Test restoration without data-root fallback, destructive resets or starvation. Trace: DA-FR-049; DA-AT-049. Dependencies: DA-T017/045/047; DA-T043 retention compatibility.

- [ ] **DA-T050 [US10]** Integrate authenticated durable pause/drain/resume/revocation/shutdown with existing operations controls and every boot/restart actor; define intent storage/epoch and fail-closed unknown intent, fence/serialize start effects, reject stale outbox replay and settle concurrent start-versus-stop before confirming effective shutdown. Respect deliberate OS stop/disable/mask and reconcile native workers on resume. Trace: DA-FR-050; DA-AT-050. Dependencies: DA-T045 intent-contract co-design; existing operator controls; no dependency on live DA-T046 qualification.

- [X] **DA-T051 [US10]** Extend existing events/status/KPI/scorecard with separate service intent, control-plane/worker readiness and product progress, gross 24/7 outage intervals, UNKNOWN telemetry, wait deadlines, recovery/intervention counts and queue-age metrics. Freeze denominator and restoration rules. Trace: DA-FR-051; DA-AT-051. Dependencies: DA-T018/045/047/050; compatible with DA-T044 learning metrics. ✅ Evidence: `evidence/v0.4/runs/DA014-core/latest.json`

- [ ] **DA-T052 [US10]** Extend the fault harness and DA-T026 campaign report with DA-AT-045–051 coverage, declared finite timing/fairness bounds, real-work exposure and post-campaign continuous-service/later-intake checks; run deterministic/systemd integration and only separately authorized live 24h/72h/168h campaigns. Preserve all faults/outages and distinct 30-day SLO status. Trace: DA-FR-052; DA-AT-052. Dependencies: DA-T045–051 implementation; DA-T026 harness; live execution additionally requires valid authority and prerequisites.

## US11 — Local inspection, honest continuation and offline improvement

Owner decisions of 2026-10-26: "Stepwise inspector in 014", "Advisory + calibrate" (the model tries its best first; zero error is the KPI), the deployment factory is strictly local/offline, and improvement happens in development through export and signed patch bundles. No task here is ticked before its full evidence exists (owner: "Keep unticked").

- [ ] **DA-T053 [US11]** Implement the stepwise local SWE.1 inspector in `lrtx/review_semantic.py` with the seeded-defect harness `lrtx/seeded.py` (truthful preflight, empty-inspection stop), regression tests per measured failure, and learning-set runs on Omniverse2. Trace: DA-FR-053; DA-AT-053. Dependencies: Feature 011 seeded catalogue and learning set; existing adjudicator. Status: implemented through `285d21e`; learning-14 49/49 (preliminary, `evidence/014-durable-local-autonomy/stepwise-inspector-20261026/README.md`).

- [ ] **DA-T054 [US11]** Integrate the escalation ladder before any gap (rework, finer re-questions, validated lesson/CAPA retrieval, diagnosis repair strategy, stall detection) with advisory continuation in `inspection/gate.py`, the advisory node in `workflow/builder.py`, the attempt record and the package gap register in `release/finalize.py`. Trace: DA-FR-054; DA-AT-054. Dependencies: DA-T040/041 lesson retrieval; DA-T004 diagnosis role. Status: advisory continuation after the existing bounded rework/progress/stall ladder implemented in `ad5447a`; lesson/CAPA and diagnosis rungs not integrated.

- [ ] **DA-T055 [US11]** Calibrate the inspector on the pre-registered F011-T046 subset (`calibration-subset.json`, 3 runs) with integrity and coverage gates, then freeze a refreshed held-out set with a recorded seed (including Feature 015 drivers) and repeat. Trace: DA-FR-055; DA-AT-055. Dependencies: DA-T053 learning-set pass.

- [ ] **DA-T056 [US11]** Add the offline export command and a bundle contract schema reusing the existing deterministic zip/manifest/SHA256SUMS pattern (`lrtx/review_bundle.py`) and redaction (`afo/bundle.py`); test exclusion of prompts, chain-of-thought, secrets and vendor inputs, determinism and hash verification. Trace: DA-FR-056; DA-AT-056. Dependencies: DA-T054 gap register; existing inspection and gate records. Status: `forge_factory.offline.export` and `contracts/offline-export-manifest.schema.json` implemented with `tests/test_da014_offline_export.py` (5 local passes); not ticked before the regression evidence.

- [ ] **DA-T057 [US11]** Add the owner-signed disposition record for registered gaps and findings, signed and verified with the existing `ssh-keygen -Y` authorization pattern (`afo/authz.py`), routed to the learning set only. Trace: DA-FR-057; DA-AT-057. Dependencies: DA-T056 export identities; DA-T039 lesson sources. Status: `forge_factory.offline.disposition` and `contracts/review-disposition.schema.json` implemented with `tests/test_da014_offline_disposition.py` (7 local passes); the owner adds a `namespaces="forge-review-disposition"` allowed-signers line to sign; not ticked.

- [ ] **DA-T058 [US11]** Add the signed patch-bundle builder (development) and the local import gate: signature, base revision, hashes, protected paths with their CRE decision, truthful preflight and declared regression before activation, one-step rollback and an import record; prove refusal of tampered, unsigned and wrong-base bundles and an offline round trip. Trace: DA-FR-058; DA-AT-058. Dependencies: DA-T056/057; existing CRE promotion gate. Status: `forge_factory.offline.patch` (build, owner sign, import, rollback) and `contracts/patch-bundle.schema.json` implemented with `tests/test_da014_offline_patch.py` (4 local passes); a live offline round trip on Omniverse2 is not yet run; not ticked.

## Completion evidence

Use the repository evidence convention (`scripts/mark_task.py` where applicable) and cite an existing passing `evidence/v0.4/runs/.../latest.json` with tested revision, command, exit code and artifact hashes. Spec validators validate documentation/contracts only; their PASS cannot tick implementation tasks. Do not overwrite old evidence.

For live-containing tasks, document implementation and live status separately until both required parts are evidenced. The 168-hour soak, 30-day SLO observation and future policy amendment must not prevent delivery/review of verified core fixes; they constrain the associated readiness claim.
