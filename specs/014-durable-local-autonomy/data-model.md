# Data model — durable local autonomy

Status: **PARTIALLY_IMPLEMENTED / QUALIFICATION_INCOMPLETE**. Authored design base:
PR #41, commit f6ff873d5b4f3e9e46956ef26766181aaec2289d; original runtime findings
were inspected at36ed0fc70bd8765f0cc90a45b21bbf02924b0269. Preserve that baseline;
current implementation/evidence dispositions are in validation.md. The scoped
2026-10-29 implementation note below does not qualify all entities or live paths.

## Ownership and existing contracts

The model provides engineering judgments. Deterministic services own identity, provenance, authority, accounting, durable state transitions and verification decisions. An AI completion message is never execution evidence. The constitution's external release authority and protected repair boundary remain unchanged.

The existing `specs/005-autonomous-factory-operations/contracts/recovery-plan.schema.json` remains authoritative and **unchanged**. The new semantic proposal is an input to a checked host binding step, not a replacement plan or permission to execute. Existing failure bundles remain immutable; complete diagnosis packets supplement them without rewriting historical evidence.

| Entity | Stable identity and owner | Required information and relationships |
|---|---|---|
| Mission ledger | Host-issued mission ID; transactional governor | Root authorization lineage, linked order/attempt identities, original allowances, explicitly authorized new campaign increments, reservations, actual/unknown consumption, overshoot, deadlines and protected audit history. Replacing an order cannot reset mission expenditure. |
| Diagnosis packet | Content hash; deterministic case assembler | Frozen bundle reference, complete finding inventory, completeness/coverage manifest, authoritative requirement and scoped artifact hashes, tool diagnostics, prior strategies, allowed technique/test/profile/scope catalogs. The packet's identity is independent of model-generated prose. |
| Semantic proposal | Canonical content hash; model-authored semantic payload | One of PROPOSE_REPAIR, NEEDS_EVIDENCE or CLOSE_BLOCKED; role-scoped evidence references and decision-specific fields. The authenticated broker context supplies the current case/job binding. |
| Bound recovery plan | Existing plan ID/schema; deterministic binder | Existing authoritative identifiers and failure fingerprint, validated semantic strategy/scope, trusted budget estimate, stable material-strategy reference and a reference to the full semantic workproduct. |
| Completion receipt revision | Receipt ID plus monotonically increasing revision; broker/controller | Proposal hash, case hash, mission/order/attempt/job IDs, launch nonce, predecessor receipt digest, independent submission/admissibility/execution states and decision/verification references. Immutable revisions form an audit chain. |
| Execution record | Execution ID and stable launch nonce; controller | Durable dispatch intent, native identity candidates, admission state, task outcome, execution liveness, cancellation state, fenced resource lease and quiescence evidence. Terminal task outcome does not erase possible native execution. |
| Verification job/receipt | Stable verifier job ID and outbox key; independent verifier/broker | Baseline/candidate artifact hashes, verifier identity/configuration, scoped obligations, test invocations and results, lease/heartbeat, terminal decision, evidence references. Candidate authors cannot issue acceptance receipts. |
| Lesson candidate | Content hash plus applicability/version key; existing knowledge service | Explicit versioned source kind: legacy promoted repair, verified ordinary outcome or verified negative observation. Source-specific qualification, applicability/exclusions, supporting/adverse evidence and invalidation. No fake repair source or untested remedy claim. |
| Job experience | Stable execution/event identity plus evidence digest; existing event/knowledge subsystem | Job/driver/feature, phase/role, target/input/model/tool/configuration identities, factual verdicts, hypotheses labeled separately, artifacts, cost and uncertainty. Immutable and deduplicated across replay/adoption. |
| Learning disposition | Experience ID plus durable processing revision; existing knowledge/outbox path | Pending/candidate/duplicate/no-new-evidence/deferred/insufficient/restricted outcome, budget allocation and related lesson/evaluation IDs. Independent of product verdict. |
| Lesson use and effect | Existing lesson usage/history extended with version/hash, role and cohort | Retrieved/exposed/applied status, job/phase, input compatibility, independent later outcome and comparison evidence. Exposure is not proof of application or causal benefit. |
| Operations intent | Existing operations owner; durable intent ID and monotonic epoch | Desired RUNNING/PAUSED/DRAINING/STOPPED mode, authenticated actor, component scope, reason, requested/effective status and resume conditions. Start/restart effect records carry the epoch; serialized dispatch rejects stale effects and reconciles in-flight requests before confirming effective stop. Separate from AFO engineering authority and job outcome. Define a durable readable location for this minimal intent when the application mount is unavailable. |
| Dependency wait/recovery state | Dependency/recipe/scope key; existing supervisor/operations owner | Failure class/history, last probe, next-probe deadline, bounded backoff, cooldown, recovery intent/receipt, eligibility and material resumption predicate. Survives controller restart without resetting engineering budgets; uncertain native execution keeps its fenced lease. |
| Service observation interval | Observer identity, boot/session identity and interval ID; existing events/KPI | Desired mode, control-plane/worker availability, last successful cycle, data freshness, outage/wait cause, detection/restoration times and interventions. UNKNOWN intervals remain in gross 24/7 accounting; product progress is a separate dimension. |

The first implementation should extend the existing transactional state/outbox design. This document does not mandate a new database, orchestrator or distributed service.

Define versioned contracts/migrations for the continuous-operation records during DA-T045–051. The three supplied JSON schemas remain proposal/receipt/execution examples; they do not claim these new operations contracts are implemented. Service intent has no implicit expiry at a campaign boundary, but all engineering allowances retain their original expiry and cumulative usage. A new operations epoch never renews them. Explicit operator shutdown prevents automatic restart; missing or unverifiable intent fails closed. See [continuous-operation.md](continuous-operation.md).

Model capability belongs to the qualified role/profile record: exact model digest, precision, reasoning settings, serving adapter and measured task class. It is not inferred from model name or advertised context size. The controller partitions the 50-gap inventory into coherent obligations with a global coverage map and shared budget; each semantic proposal addresses a small objective. A capability-limited outcome retains its evidence and triggers only a prequalified bounded alternative or explicit block. The contract does not authorize unlimited retries, cloud fallback, weight training or self-modification of qualification criteria.

## Semantic binding without invented judgments

| Semantic input | Existing plan binding | Required rejection/validation behavior |
|---|---|---|
| `strategy`, `affected_phase`, `artifact_scope` | Same fields in the authoritative plan | Validate against failure class, owning phase, protected paths and authorized scope. Resolve paths safely; string/schema checks are insufficient. Do not silently widen or replace the model's proposed scope. |
| `technique_id`, `material_difference`, `proposed_change`, target obligations and expected verification | `material_difference_ref` points to a validated strategy record; detailed proposal retained as a workproduct | Technique/test/obligation IDs must exist in the packet. A stable semantic strategy signature excludes wording, random IDs and receipt revisions. Rephrasing the same approach is not material difference. |
| `model_profile` for a switch | Existing `model_profile` | Required only for SWITCH_PREAPPROVED_MODEL_PROFILE; must be present in both the case's allowed catalog and current authorization. No cloud or unapproved fallback. |
| `owner_phase` for upstream return | Existing `owner_phase`; deterministic downstream invalidation list | Required only for RETURN_TO_OWNING_UPSTREAM_PHASE. Enforce phase ordering/ownership and upstream information barriers. |
| `validation_expectations[].test_ref` | Existing `validation_tests` references | References must resolve to independent existing checks or a separately governed new reproducer. The host preserves expected semantic results in the referenced proposal; it cannot invent them. |
| CLOSE_BLOCKED reason/explanation | Existing CLOSE_BLOCKED plan with trusted phase/identity and references to the explanation | An independently admissible blocked decision is not a repair. Required legacy fields are explicitly marked not applicable or refer to the authoritative case; no invented recovery hypothesis. |
| NEEDS_EVIDENCE | **No recovery plan** | Bounded, scoped evidence acquisition only. A complete supplement produces a new sealed packet linked to the previous hash and consumes the same mission allowance; unresolved inputs become an explicit dependency block. |

The host binds schema version, plan/order/attempt IDs, failure fingerprint, policy decision reference, deterministic budget fields and hashes from trusted state. It does not coerce invalid semantic types, truncate a decision to fit a contract, fabricate causal evidence, choose an omitted model profile, or fill an absent repair hypothesis. If the proposal cannot be represented without loss, reject it with a typed diagnostic and preserve the original bounded payload. Long semantic detail remains in a referenced workproduct, not in a silently shortened legacy field.

The complete bound plan must pass the unchanged legacy schema and the existing deterministic recovery validator. New packet/receipt checks supplement those checks. Source-provenance and cross-revision reuse rules remain in force.

## Receipt semantics

The three axes in `contracts/completion-receipt.schema.json` answer different questions:

| Axis | States | Meaning |
|---|---|---|
| Submission | STORED, REJECTED | STORED means a schema-valid proposal has been durably retained. REJECTED is an audit receipt for a malformed/unrepresentable submission. Neither is acceptance. |
| Admissibility | NOT_EVALUATED, PENDING, ACCEPTED, REJECTED | A deterministic decision bound to exact case, policy/authority and budgets. ACCEPTED records that decision at its time; dispatch must still revalidate current authority, evidence and remaining resources. |
| Execution | NOT_REQUESTED, NOT_APPLICABLE, DISPATCH_PENDING, APPLYING, VERIFYING, VERIFIED, FAILED, CANCELLED, UNKNOWN | Progress of the proposed repair. NEEDS_EVIDENCE and CLOSE_BLOCKED use NOT_APPLICABLE after acceptance. VERIFIED requires independent scoped verification; it does not claim READY, release approval, deployment or safety compliance. |

Each receipt revision is immutable and links to the exact predecessor digest. `receipt_id` remains stable across revisions; concurrent writers use compare-and-swap on the current revision and a fenced lease. The pair `(job_id, launch_nonce, proposal_sha256)` identifies an idempotent submission. Repeating that tuple returns the same receipt family. The same job/nonce with a different proposal is a bounded correction only when explicitly permitted; it gets a separate proposal identity and cannot cause a second effective implementation dispatch.

The broker commits a stored proposal and its first receipt atomically, or through a recoverable write intent whose digest is verified before exposing STORED. Acceptance and the associated dispatch-outbox intent must have an idempotent, recoverable boundary. Lost acknowledgements never justify blind replay. A deterministic adapter produces any required legacy compact completion artifact from authoritative receipt state; model prose is irrelevant to receipt recovery. A compact PASS string is never an acceptance or execution oracle.

Admissibility REJECTED remains rejected in that receipt family. A corrected proposal is a new submission, charged under the original mission. Accepted evidence retrieval or CLOSE_BLOCKED cannot enter APPLYING. A later policy revocation does not rewrite historical acceptance: current dispatch authorization is refused, and any already-live execution is reconciled/cancelled under its execution record.

## Execution and cancellation invariants

`contracts/execution-lifecycle.schema.json` describes a snapshot, not proof that its preceding transition was legal. The controller and fault-injection suite must enforce the following across records and time:

1. **Intent before effect:** commit resource reservation, immutable execution identity, launch nonce and dispatch intent before contacting Fabro. One mission's inference lease covers every possibly live request, including orphan candidates.
2. **No blind repeat:** reconcile lost native receipts by job identity and nonce. Multiple matches become AMBIGUOUS; no new inference may start while possible work holds the exclusive lease. A listing window or transient 404 is not proof that no run exists.
3. **Fresh admission:** every generation and implementation dispatch rechecks policy, authority, immutable evidence and budget; historical ACCEPTED is insufficient. Revocation blocks new admission but does not prevent read-only native reconciliation or approved cancellation.
4. **Two independent axes:** ACTIVE/RECOVERED/BLOCKED/EXHAUSTED/FAILED_PROTOCOL/ROLLED_BACK describe task outcome. NOT_STARTED/POSSIBLY_LIVE/LIVE/QUIESCENT/UNKNOWN describe native liveness. A blocked outcome may still be LIVE or UNKNOWN and must retain its resource lease and cancellation intent.
5. **Cancellation is a process:** REQUESTED records intent; ACKNOWLEDGED records transport/native acceptance only; QUIESCENCE_CONFIRMED requires authoritative proof of termination or proof that dispatch never occurred. Errors and timeouts retain uncertainty. Reconciliation continues after terminal task outcomes and restarts.
6. **Resource release:** release only on proven NOT_STARTED or QUIESCENT. Quiet GPU telemetry, elapsed deadline, HTTP success, missing usage or missing run listing is insufficient. With ambiguous native identity, quiescence evidence must cover every possible native execution and the dispatch-intent reconciliation.
7. **No reactivation:** a terminal task outcome is not changed back to ACTIVE. Further work uses a separately authorized execution/attempt linked to the same mission ledger. Liveness and accounting may continue to reconcile for the terminal task.
8. **Fencing and leases:** stale epochs cannot write transitions or issue new effects. Verifier worker adoption requires stable job identity, lease and heartbeat; repeatable verification is separated from idempotent publication. No permanently stranded DISPATCHED/RUNNING verifier is considered healthy.
9. **Accounting convergence:** preserve unknown reservations; record late usage and observed overrun. Consumption uses the documented conservative charge until reconciled. Additional campaign authority is an explicit audited increment, never deletion/reset of past consumption.
10. **Verification and release:** RECOVERED/VERIFIED require an authentic independent receipt covering the intended repair and impacted dependencies plus native quiescence. A complete READY archive requires all unchanged release gates. External release/deployment authority remains external.

## Evolution and privacy constraints

Every-job knowledge integration follows [continuous-learning.md](continuous-learning.md). Extend `LessonStore` persistence and `forge-knowledge-mcp`, preserving its lifecycle and legacy schema/source rules. During implementation, define and validate additive versioned experience/source contracts against the existing lesson schema; do not reuse repair-only fields for fabricated incidents. The proposed semantic-proposal/completion/execution schemas in this package do not claim to implement this migration.

Lesson identity includes applicability/source versions as well as content; old versions remain auditable. Independent job experience may support or contradict a candidate without altering previously sealed records. Ordinary success/failure learning never bypasses the separately governed generic inspection-lesson path. Terminal job capture and learning processing reconcile independently, with deterministic capture possible even when distillation has no authorized budget.

Version these proposed interfaces independently of the unchanged recovery-plan schema. Unknown versions fail closed. Hash serialization is defined in `contracts/README.md`; clients cannot rely on unspecified JSON key order. State migrations require independently qualified compatibility/recovery evidence and remain outside automatic worker promotion.

Store only the bounded semantic proposal, redacted evidence references, tool events and receipts needed for audit. Raw prompts/completions remain off by default; no hidden model reasoning is collected. No schema, fixture or synthetic hash in this feature is evidence of an actual Omniverse2 run.

## Operational verification artifacts (implementation follow-up)

`forge-c/independent-operational-work/1` is a recomputable qualification artifact,
not a new authority or database. It references the frozen observer plan, existing
product qualification row and external sample artifacts. It binds order, latest
attempt, mission, native run, nonce and request identities; records independently
verified outcome separately from product success; and carries native quiescence,
false-READY and observation-window facts. Product correctness still comes from the
existing independent CRE/reference/metamorphic/mutant qualification audit.

The product observation compatibly includes `request_ids` and `attempt_created_utc`.
Missing legacy values remain unknown. Observer projections include attempt creation
and the existing execution's `last_reconciled_at`. `native_active_observed_at` records
actual matching RUNNING/HELD observations with fresh reconciliation and healthy
control/native/storage prerequisites. A terminal observation's time is not its
execution time: campaign work exposure needs a new in-window attempt or captured
in-window native activity. Historical audit evidence can verify an outcome without
proving fresh campaign work. All primary source/artifact hashes remain bound; no
ledger or finite mission allowance is reset by capture or replay.


### Implemented time-only amendment — 2026-10-29

The scoped operator API at afo.mission_deadline extends only an existing product
mission's deadline and current authorization reference. It uses the existing
afo_independent_decisions table with kind MISSION_DEADLINE_EXTENSION; no new store,
scheduler or migration. Up to8 sealed receipts bind the initial mission record,
previous deadline, exact current snapshot, complete signed request and grant hash.
The original afo_missions row and every non-time allowance remain immutable.

MissionLedger.snapshot overlays the validated deadline chain on that base before
normal cumulative accounting. Unknown usage and conservative charges remain.
No task outcome, replay, expiry or amendment releases inference. Held native work
refuses the amendment. Only the authenticated state-owner CLI exposes it; agent
MCP/proposals cannot call it. Each increment requires current recover_workorder
authority specifically signed over mission-deadline-extension-014:<request digest>.
Dispatch and any new order still need normal independent current authorization.
