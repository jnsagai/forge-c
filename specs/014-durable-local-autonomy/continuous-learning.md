# Continuous learning from every job

**Owner intent:** Forge-C accumulates useful engineering experience from every run, driver and feature, and uses qualified experience to improve subsequent work. This is a core Feature 014 capability, including ordinary successful work; it is not limited to incident repair or deferred to automatic source promotion.

**Status:** SPECIFIED / NOT_IMPLEMENTED. Every job must contribute factual experience and receive a durable learning disposition. A new lesson or a higher score after every job is not guaranteed. Evidence capture, reusable knowledge and demonstrated improvement are separate outcomes.

## Fit with the existing factory

The baseline already implements significant parts of learning. Extend them coherently:

| Existing capability at `34d21c0` | Role in this feature | Required extension |
|---|---|---|
| `knowledge/store.py`: SQLite/WAL, FTS5, lesson history, usage, validation, TTL, retraction | Authoritative shared engineering lesson store and retrieval path | Add job experience/disposition records and explicit versioned lesson source kinds in the same knowledge subsystem; preserve legacy repair lessons. Do not create a competing vector database or parallel publication authority. |
| `mcp/servers/knowledge.py`: `find_lessons`, `propose_lesson` | Existing production AI interface | Add a compatible typed path for verified job outcomes and negative observations; retain deterministic publication, role grants and bounded result transport. No arbitrary write or publication permission for Qwen. |
| `.fabro/skills/lessons-curator/SKILL.md` | Bounded candidate distillation role | Externally implement and qualify the broadened input/source contract with matching registry/lock updates. Runtime cannot rewrite its own SKILL. Deterministic capture and deduplication should avoid an extra model call on routine duplicate experience. |
| `knowledge/inspection.py` and `config/factory/inspection-lessons/IL-*.yaml` | Separately qualified generic inspection knowledge | Preserve deterministic phase/checklist/layer/artifact selection, recorded semantic sources, paired seeded-defect checks, CRE promotion and frozen lesson hashes. General author memory cannot feed inspector conclusions or bypass this channel. |
| `events/*`, native tool/inspection/package receipts, AFO reconciliation | Factual job/phase evidence and durable effects | Link terminal event handling to idempotent experience capture and a recoverable learning outbox; reconcile missed events after restart. Existing sealed packages remain immutable. |
| `reliability/capa.py`, `reproduce.py`, `promotion.py`, AFO maintainer | Factory improvement evaluation | Turn measured recurring problems or successful reusable patterns into scoped candidates through existing CAPA/CRE/maintainer authority. Do not create incidents falsely or auto-deploy source. |
| `kpi/sources.py`, `kpi/engine.py`, `controlroom/scorecard.py` | Deterministic outcomes and comparable cohorts | Add learning coverage/impact views linked to existing quality, first-pass yield, recurrence and cost definitions; do not replace or improve KPI formulas to manufacture progress. |

Current `LessonStore.validators` requires an authoritative PROMOTED repair attempt; its schema and curator are repair-specific. Ordinary successful jobs must not be represented as fake incidents or fake promoted repairs. Introduce an additive versioned source discriminator and source-specific checks. The legacy source path must continue to require its existing evidence. Migration preserves old IDs, versions, usage and retractions.

Current general retrieval caps `k` at three and uses a default estimated 700-token allowance. Preserve those bounds unless a separately measured policy change permits otherwise; also check the actual fully serialized context. Its `phase` argument currently does not filter records and its `tool` filter checks the name, not exact version compatibility. Implement and test real phase/role/device/configuration applicability before broad cross-job transfer. General lesson deduplication currently hashes symptoms/remedy; extend scope/version identity so similar wording does not collapse incompatible hardware facts. These are integration gaps to fix, not capabilities already demonstrated.

The existing knowledge MCP stores the full result as an artifact but exposes a remedy snippet capped at 120 characters inline. The consuming role must receive the complete bounded statement/remedy, constraints, exclusions and provenance through authorized artifact resolution or deterministic packet assembly. A snippet is an index, not the lesson. Test an exclusion after character 120. If the complete relevant lesson cannot fit, explicitly omit/defer it rather than supply a misleading partial remedy.

## Lifecycle for every job

1. **Capture facts.** Each unique execution contributes an immutable experience record at authoritative phase/job transitions. Terminal success, failure, block, cancellation, timeout and unresolved execution all receive a disposition. Record partial verified progress where available, keeping observations separate from model hypotheses. Re-imported historical rows and replayed events must not inflate experience or support counts.
2. **Consolidate under budget.** A durable outbox requests deduplication and candidate extraction. Prefer deterministic rules; use the existing curator only when permitted and useful. Charge inference/verification to the explicit mission or learning allocation, preserving one-inference admission. No remaining capacity means deferred distillation, not lost facts or an unauthorized retrospective run.
3. **Propose conditional knowledge.** Candidates can describe successful procedures, design/test patterns, prerequisites, failure avoidance or resource strategies. A failed run may support a verified negative observation; it cannot establish that an untested remedy succeeds. Success alone supports a hypothesis about a useful technique, not proof of general benefit.
4. **Qualify independently.** Authenticate original receipts, applicable authoritative sources, scope/version predicates and positive/negative checks. Assess unseen applicable and deliberately inapplicable cases. Keep unqualified, conflicting or unsafe candidates quarantined. Validation, not Qwen's confidence, authorizes retrieval eligibility under the implemented knowledge policy.
5. **Use in later jobs.** Before a relevant author/planner phase, the existing knowledge service selects a small set of applicable VALIDATED lessons as reference data. Record lesson ID/version/hash, source evidence, selection, exposure and observed application separately. A retrieved lesson does not prove it was followed. Primary requirements/manuals and existing context/role boundaries retain authority.
6. **Measure and revise.** Independent later outcomes can strengthen support, narrow applicability, create a successor version or retract a lesson. Preserve old versions and the list of consumers. Qualify a new version rather than silently changing text under a previously recorded hash.

Learning disposition examples: CAPTURED_PENDING, CANDIDATE_CREATED, DUPLICATE_SUPPORT, NO_NEW_EVIDENCE, INSUFFICIENT_EVIDENCE, DEFERRED_BUDGET and RESTRICTED_SCOPE. These describe learning work, not product acceptance. Queue backlog and unavailable storage must be visible and reconciled; 100% coverage cannot be claimed while experiences are missing. A learning-service failure never rewrites a sealed READY/BLOCKED package or silently loses the learning intent.

An explicitly admitted consolidation/evaluation job may use otherwise idle capacity under its existing allocation; that is recorded learning work. Healthy-idle monitoring itself still makes zero model calls. An empty product queue alone does not authorize an extra learning run.

## Persistent memory without an ever-growing prompt

Reuse three scopes within existing storage and evidence ownership:

- **Working state:** current-job checkpoints, obligations and remaining allowances from Feature 014/012.
- **Experience records:** what actually happened across eligible jobs, linked to immutable events/artifacts and explicit visibility restrictions.
- **Validated lessons:** concise conditional knowledge with supporting/negative evidence, applicability, qualification receipt and invalidation rules in the existing knowledge subsystem.

An experience records execution/job/work-order identity, task/driver/feature class, role/phase, MCU/peripheral/layer where applicable, authoritative input hashes, source/model/tool/configuration versions, attempted approach, independent results, referenced artifacts, measured/estimated costs and uncertainty. Avoid copying entire workspaces, private manuals or hidden model reasoning into memory.

A lesson candidate records source kind and experience IDs, lesson type, supported statement or proposed procedure, predicted observable benefit, applicability/exclusions, evidence, qualification cases/results, evaluator identity and version history. Device-specific facts remain tied to exact authoritative source scope. Broader transfer requires separate support. Metadata references may point to existing receipts rather than duplicating their data.

Reuse immutable artifacts only through current valid-prefix/hash rules. A remembered successful driver is not permission to import its acceptance state or copy facts to another MCU. Inspection knowledge remains generic and follows its existing separately governed publication path. Upstream SWE.1 authors must not receive forbidden downstream code or author judgments through memory.

## Example target behavior

A successful RCC job may suggest that building an evidence-indexed effect table before code generation reduces omitted register effects. That is a candidate procedure, not an established causal lesson. An independent replay can compare the procedure on separate applicable cases and check adverse cases. If qualified, a later GPIO job can retrieve the procedure; RCC register addresses, masks and sequencing cannot be reused as GPIO facts. GPIO still needs its own authoritative inputs and all independent gates.

A blocked job missing an authoritative manual contributes a prerequisite observation. The next comparable intake can detect that absence earlier. It does not teach that the driver is impossible. A duplicate successful run can add properly deduplicated supporting evidence without producing another summary or another lesson.

## Proving that the factory improves

Require complete capture and disposition coverage for terminal jobs after bounded reconciliation, with pending/deferred/failed capture shown separately. These are completeness metrics, not engineering quality.

Use existing Feature 003 cohort rules: driver complexity, MCU, layer, safety profile, model, compiler/tool settings and source/configuration versions. Compare frozen memory-enabled versus baseline replays with the same budgets and independent oracles, and evaluate chronological transfer where job N cannot access evidence from N+1. Keep final held-out acceptance answers out of experience distillation; an exposed holdout must be relabeled and replaced under the existing evaluation process.

Report first-pass yield, independently closed obligations, recurrent finding fingerprints, false rejections, critical-defect detection, READY yield and total time/tokens per accepted job. Include learning extraction, qualification, retrieval, failed candidates and all retries in cost. Separate simple exposure/use correlation from controlled evidence of benefit. If data are insufficient, report INSUFFICIENT_BASELINE; if a lesson regresses quality, retract or narrow it.

Learning coverage should reach 100%; improvement must be demonstrated over comparable cohorts. No requirement forces a novel lesson or monotonically higher metrics after every run. Quality gates and critical defect detection cannot be traded for speed.

## Evolution within current capabilities and authority

Validated memory can change future evidence selection and engineering choices through the existing knowledge interface. It cannot rewrite source, persistent prompts/SKILLs, workflows, policy, inspection criteria or oracles. Candidate improvements to those artifacts follow the existing external engineering/CRE path and Feature 014's source-promotion boundary. An executable instruction disguised as a lesson is rejected.

Use the appropriate existing evaluation lane: a defect repair retains its failing-baseline reproducer/CAPA requirements; a success-derived optimization uses a measured baseline and the existing CHANGE evaluation, with external engineering when it is outside the maintainer's defect/scope grant. Do not fabricate a failed repair incident to submit an otherwise useful improvement.

This is system-level learning with persistent knowledge and measured adaptation. Online weight training is outside this feature. Useful experience can later inform a separately authorized training study, but successful-looking self-generated output or final benchmark answers are not automatically training truth.

Implementation tasks DA-T037–044 and acceptance cases DA-AT-037–044 extend the existing knowledge, event, KPI and CRE tests. They are core work, independent of the future worker-promotion policy proposal.
