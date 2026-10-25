# Local-model design: capability limits and qualification

**Status:** Design for Codex implementation; implementation and experiments are **NOT_RUN**.  
**Scope:** Companion to [spec.md](spec.md), [acceptance-tests.md](acceptance-tests.md) and [future-worker-promotion.md](future-worker-promotion.md).  
**Decision:** Design autonomy around a measured local model capability envelope. Do not assume that the currently selected Qwen can satisfy every engineering or inspection role merely because the orchestration defects are fixed.

## What local autonomy requires

Qwen should supply bounded engineering judgments. Deterministic components must own identity, evidence access, state transitions, accounting, completion, scheduling and enforcement. Independent verification must decide whether a proposed repair satisfies the product obligations. This allocation reduces the amount of reliable behavior demanded from the model without claiming that a controller can manufacture missing engineering competence.

The system must establish three different properties:

1. **Protocol competence:** the installed model and adapter can produce a valid, timely decision for the presented case.
2. **Engineering competence:** the decision is supported by authoritative evidence and leads to a useful independently checked repair.
3. **Operational reliability:** failures, interruption and uncertainty preserve authority, evidence and accounting, and receive the correct recovery or blocked disposition.

Passing one property does not establish the others. A service can be healthy while the model is ineffective; a valid plan can be technically wrong; a correct patch can still lack required verification or release authority.

The four historical diagnoses establish specific contract and orchestration failures and zero accepted model recovery plans. They do not isolate a Qwen capability ceiling. V4's native stopping cause remains unknown. Context overflow, quantization loss, insufficient reasoning ability, tool suppression and a turn-limit stop are **hypotheses to test**, not established explanations of V4. See [evidence-baseline.md](evidence-baseline.md).

## Risks and the design response

| Limitation or risk | Design response | Required measurement or check |
|---|---|---|
| Effective usable context can be smaller than the configured or advertised window | Admit the actual serialized request against a qualified per-role allowance. Partition coherent obligations and retain explicit dependency coverage. | Token counts after templates and schemas; required-evidence coverage; quality as evidence length and position vary; completion reserve. |
| Instruction following and tool calls can be brittle | Expose one role and a small semantic contract; bind administrative fields in code; qualify the actual transmitted schema and adapter. | Valid outcome rate, wrong-type/enum rate, missing submission, correction count, useful-plan rate and precise stop reason. |
| Long conversations accumulate irrelevant state and can lose the objective | Use short bounded work units, durable checkpoints and explicit remaining obligations. Reassemble subsequent contexts from evidence rather than replaying unlimited conversation. | Resumption correctness, evidence retention, repeated work, failure to preserve constraints and cost per independently closed obligation. |
| The same model can repeat its own reasoning errors when inspecting | Preserve separate author and inspector roles, but do not equate separate sessions or seeds with independent error behavior. Use independent oracles and held-out defects. | Seeded-defect detection, false acceptance and false rejection, including cases the author confidently describes as correct. |
| Low-level hardware/API facts can be invented or transferred from the wrong device | Require authoritative, versioned source references for register fields, masks, reset values, ordering constraints and similar facts; check them mechanically where possible. | Unsupported-claim rejection; reference identity; field/value consistency; adversarial near-neighbor device cases. |
| Quantization, context allocation and serving settings can change quality and performance | Pin the current configuration first. Compare one approved factor at a time by role after deterministic failures are repaired. | Quality, peak VRAM/RAM, CPU offload, prompt/generation latency, throughput, failures and total cost including rejected attempts. |
| Additional samples may repeat the same misconception | Explore only materially different bounded hypotheses, serially under the same ledger; use checker evidence rather than self-voting. | Independent defect closure per additional candidate, regression rate and marginal token/time cost. |
| A model may produce plausible but ineffective repair plans | Require a predicted observable repair effect, an impact set and a failing counterexample or concrete obligation before implementation. | Baseline failure, actual changed artifact, independent before/after verdict and preserved passing obligations. |
| Retrieved lessons can be stale, overgeneralized or malicious | Treat lessons as untrusted suggestions with verified provenance, applicability predicates, negative cases and invalidation. | Out-of-version rejection, held-out benefit, rollback/retraction and absence of policy/oracle override. |
| Some tasks remain beyond the qualified model | Record a capability-limited incident or dependency block, preserve the failed evidence and select only an already authorized alternative. | No blind retry loop, invented success, relaxed gate, cloud fallback or budget/authority reset. |

## Role matrix and expected stage outputs

Each model role has its own measured context, output, time and verification profile. A configuration qualified for compact diagnosis is not automatically qualified for code generation or semantic inspection. The same served model may fill several roles serially; this design does not require simultaneous model replicas or an agent swarm.

| Stage / role | Input boundary | Expected output | Acceptance owner | Model-specific qualification |
|---|---|---|---|---|
| Supervisor and resource admission | Health observations, signed policy, ledger and execution identities | Admission, reconciliation, approved operational action or explicit block | Deterministic controller | No inference; healthy idle and operational recipes use zero model tokens. |
| Evidence assembly | Authoritative artifacts, typed findings, provenance and phase/role permissions | Sealed packet, coverage/dependency manifest and explicit missing evidence | Deterministic assembler | No model assertion may establish completeness or source identity. |
| Diagnosis planner | One coherent failed obligation, relevant evidence, prior strategies and permitted scopes | `PROPOSE_REPAIR`, `NEEDS_EVIDENCE` or `CLOSE_BLOCKED` conforming to the semantic proposal contract | Strict parser, binder and independent admissibility validator | Valid outcome and useful-plan rates; evidence grounding; material difference; bounded completion. |
| Product author / repair worker | Admissible scoped plan, authoritative inputs, allowed files and required counterexample | Patch/artifact changes plus a machine-readable changed-file/obligation manifest where supported by existing contracts | Existing author workflow followed by independent gates | Actual defect closure, unsupported facts, patch scope, compile/test results and regressions. |
| Semantic inspector | Required role-appropriate inputs and frozen inspection obligations | Existing inspection verdict, finding identities and evidence references | Independent inspection framework and frozen release gates | Critical-defect detection and false rejection on separate held-out defects; formatting alone is insufficient. |
| Counterexample / deterministic verifier | Candidate artifacts, authoritative property/test definitions and impact manifest | Reproducible failure or supported PASS for the checked properties | Existing independent tools and oracles | Tool coverage and assumptions are recorded; a model does not expand the meaning of PASS. |
| Factory maintainer | Eligible incident, reproducer and currently allowlisted candidate workspace | Candidate patch, predicted improvement and qualification evidence | Independent CRE and existing external promotion authority | Baseline-fail/candidate-pass plus regression and holdout results; protected edits remain external engineering. |
| Existing lessons curator, when model distillation is useful | Verified ordinary-job outcomes, checked negative observations or promoted repairs with explicit source kind | Conditional lesson proposal with evidence references and applicability limits | Existing deterministic knowledge validation extended compatibly; separate inspector promotion path | Benefit on separate applicable/adverse cases; stale and nonapplicable lessons rejected. Every-job factual capture itself is model-free. |

Administrative plan fields, broker receipts and compact completion artifacts are controller outputs. They are not a second model task. Optional narrative explanations cannot replace any required structured artifact.

## Effective context and working memory

For each role, record the served model digest, tokenizer/template identity where available, effective context setting, generation limits, reasoning-mode configuration where observable, adapter version and actual registered tool/skill hashes. Do not infer the served configuration from a base-profile default or model download name.

Measure the complete request after role instructions, tool schemas, message wrappers, retrieved evidence and previous tool results are included. If exact admission-time token counting is unavailable, use a documented conservative estimator and quantify its error during qualification. A nominal context setting is an implementation ceiling, not evidence that the model will reliably use all included information.

Determine a usable context range from fixed engineering cases, not only synthetic token-fit tests. Include a decisive fact near the beginning, middle and end; distractors from similar devices; and a case requiring two separated facts together. The objective is correct grounded decisions and retained coverage, rather than successful ingestion of a long prompt. No test result about V4 context is assumed in advance.

When a packet is too large, partition by obligation and dependency structure. Each partition retains relevant authoritative clauses, definitions and cross-unit dependencies. The controller maintains the coverage manifest and blocks a decision whose mandatory evidence is missing. A short summary may guide retrieval, but cannot silently replace the underlying evidence. An author cannot establish that an omitted clause is irrelevant merely by saying so.

Persist a bounded working-memory checkpoint containing:

- Case, mission, configuration and artifact identities.
- Independently accepted facts and their source references.
- Remaining obligations, unresolved dependencies and explicit uncertainty.
- Previous hypotheses, attempted changes and independent outcomes, including negative results.
- Current admissible plan/receipt, execution identity and remaining policy-derived allowances.

Generate authoritative checkpoint fields from recorded state. Model-written notes are labeled untrusted and revalidated before use. Restart or context compaction reconstructs work from this checkpoint and referenced artifacts; it does not reset a budget, create a new attempt identity or import incompatible historical PASS evidence. A new context is a continuation of the same work, not permission for additional work.

## Bounded proposal and repair search

The initial path uses one compact semantic proposal for one coherent case. Evidence acquisition and correction bounds come from the existing policy/campaign configuration. This document does not allocate additional calls, tokens, attempts or concurrency.

If permitted capacity and a qualified strategy exist, the controller may evaluate a small serial set of materially different candidates. Candidate width, depth, total calls, wall time and token limits must be explicit, configurable and subordinate to the same mission ledger. With no authorized remaining capacity, search stops. A random seed or rephrased rationale alone is not material difference.

Each candidate states a causal hypothesis, evidence references, expected observable change and impacted obligations. Rank or reject candidates using independently computed results: plan admissibility, reproducer behavior, required tests, regressions and resource cost. Model self-scoring or majority agreement between same-model samples cannot establish correctness.

Use a verifier-guided loop:

1. Preserve the baseline failure and the smallest meaningful counterexample or violated obligation.
2. Ask for one scoped hypothesis/repair proposal within the qualified role allowance.
3. Bind and independently validate the plan; execute only if authorized.
4. Check the target and impacted obligations with the existing independent machinery.
5. Continue only with new relevant evidence or a materially different strategy and sufficient remaining authority.

Do not repeatedly replay the full log or ask the model to solve all 50 RCC gaps in a single unbounded conversation. First distinguish root defects from downstream symptoms. Preserve required cross-cutting invariants so decomposition does not turn a local patch into an unobserved system regression.

This is counterexample-guided engineering, not a proof of arbitrary program correctness or guaranteed convergence. Formal claims apply only where the actual verifier and encoded semantics support them. A decreasing gap count does not establish convergence without stable gap identities and classifications.

## Verification limits and correlated self-judgment

Separate sessions, prompts and roles improve isolation but do not prove statistical independence. The same Qwen may share the same mistaken hardware fact or miss the same class of implementation defect in both author and inspector roles.

Retain independently maintained deterministic checks, authoritative reference extraction, compile/test evidence, property checks where available, and held-out mutants maintained outside the author's write authority. Record which defects are detected deterministically and which depend on semantic inspection. Do not credit a model inspector for a defect rejected before that inspector ran.

Qualify the inspector separately with valid controls and seeded critical defects, including plausible near-correct implementations and unsupported success claims. Measure false rejection as well as missed defects. If the inspector does not meet its inherited threshold, local authorship may continue only where the existing workflow permits staged unaccepted output; the factory cannot claim READY by substituting author confidence or weakening the inspection gate.

For low-level code, require exact device/revision provenance for relevant values and behavior. Missing reference-manual content is an input dependency. Neither Qwen's memory nor agreement between local agents supplies authoritative missing facts. This applies directly to the conditional GPIO profile and intake prerequisites.

## Initial experiments

All experiments below are **NOT_RUN**. They require bounded campaign authority where they invoke a model or change a live host. These are implementation/qualification instructions, not authorization to run them. The current selected Qwen digest and effective profile remain the initial model baseline.

Freeze case identities, expected outcomes, admissibility oracles, evidence hashes and measurement definitions before comparison. Development comparisons use the same cases and repetitions on each side. Preserve separate independent qualification/holdout sets; do not tune prompts, lessons or weights against final held-out answers. Any exposed holdout becomes development evidence and must be labeled accordingly. A preregistered comparison does not authorize unlimited adaptive experimentation on a holdout.

| Experiment | Controlled comparison on frozen cases | Per-stage expected output / evidence | Decision enabled |
|---|---|---|---|
| LM-01 — Installed baseline and protocol capability | Record the unchanged current Qwen path before configuration optimization; use complete fixtures and the real serialized schema. Preserve historical malformed and missing-output cases as separate regression fixtures. | Packet/contract/configuration hashes; actual stop reason; proposal or typed failure; receipt presence; model requests, tool calls and usage. | Separate adapter/protocol defects from useful-plan failures. Historical failures are not silently replaced by the new baseline. |
| LM-02 — Context and evidence position | Same engineering obligation with controlled evidence length, location and relevant distractors; remain within authorized limits. | Coverage manifest; measured input/completion allowance; grounded proposal; reference correctness; latency/resource observations. | Establish a per-role usable context range and partition rule. A token-fit-only result does not qualify engineering use. |
| LM-03 — Proposal protocol | Compare the existing compatible proposal path with the implemented compact semantic proposal under a qualified constrained-output mode or narrow proposal tool. Keep model and case facts fixed. | Strict validity, evidence/semantic admissibility, completion receipt, useful-plan rate, corrections and total cost. | Select a protocol on observed full-path performance; do not assume simultaneous tool navigation and constrained final generation is supported. |
| LM-04 — Checkpoint and bounded decomposition | Same multi-obligation development cases through a bounded complete packet versus obligation-scoped work with controller checkpoints and dependency coverage. | Scoped proposals, preserved constraints, resumed-work identity, independently closed obligations, regressions and repeated-work cost. | Decide when decomposition improves useful outcomes and when cross-obligation context must stay together. |
| LM-05 — Verifier feedback and optional candidate search | Same repair cases with a concrete counterexample; compare one candidate against a predeclared small serial candidate allowance only if policy permits. | Candidate hypotheses, independent before/after checks, material-difference decisions and complete resource/attempt ledger. | Retain search only where incremental independent defect closure justifies cost; do not select by self-vote. |
| LM-06 — Inspector capability | Frozen valid controls and independently seeded defects, distinct from author training/development examples. Keep current inspector configuration fixed initially. | Exact verdict/finding references; deterministic versus semantic detection; false acceptance/rejection; unsupported-claim handling. | Establish whether the current local inspector is qualified for each required role. Failure blocks acceptance claims, not the recording of useful staged work. |
| LM-07 — Resource and configuration tradeoffs | Only after deterministic fixes and baseline measurement: one authorized serving/configuration factor at a time, using the same development cases. Alternative quantization/model artifacts require their existing qualification and allowlist process. | Role-specific quality; prompt processing and generation times; queue/load time; peak memory; offload/OOM; total cost including failed attempts. | Adopt a change only if it satisfies required quality and resource limits. Faster tokens or a larger context alone are insufficient. |
| LM-08 — Lesson usefulness and capability ceiling | Apply a proposed lesson to separate applicable and deliberately nonapplicable cases; retain unsolved cases and bound all retries. | Lesson applicability/provenance verdict; independent repair outcome; stale-lesson rejection; explicit unsupported/blocked disposition. | Admit or retract lessons and identify tasks the current qualified local stack cannot solve within its envelope. |

Run model-free contract, receipt, accounting and crash tests first; those must not consume the remaining historical product attempt. Real-model protocol trials use their own expressly authorized campaign accounting and cannot silently become product executions. The frozen 20-case × 5-repeat pilot and its mandatory outcomes remain as specified by DA-FR-024; a valid `CLOSE_BLOCKED` on a designated recoverable case fails useful-plan qualification.

Experiments must report complete denominators and individual failures, not only the best sample. Distinguish input and output usage where observable, and record unknown usage conservatively. Record permitted reasoning configuration and aggregate usage, but do not store hidden reasoning. Keep raw prompt/completion logging OFF by default and retain only permitted redacted evidence.

## Resource choices on Omniverse2

The profile-recorded RTX 6000 Ada 48 GB and approximately 125 GiB observed system RAM do not establish that a selected model, quantization, context and cache allocation will fit or perform acceptably together. Measure the installed workload. In particular, distinguish model loading, prompt processing, generation, queued time, tool execution and independent verification.

Preserve one admitted inference request and the existing bounded CPU verification allowance. Serial role execution can still benefit from concurrent deterministic verification where policy and resources allow it. Additional model agents do not create more GPU memory or independent verification and can multiply context, latency and accounting failure modes.

Keep the baseline served model pinned while changing the harness. Later approved comparisons may consider context allocation, generation/reasoning configuration, cache behavior or quantization, but each must be measured per role. A candidate that helps authoring may harm inspection. Downloads remain separate from inference permission; this specification does not authorize an alternative model, raise a limit or change a protected profile.

Fine-tuning is not a first-line fix for a broken evidence/protocol/completion path. Consider it only as a separate authorized experiment after repeated verified examples and held-out evaluation exist, and only if a measured residual capability gap motivates it. Do not train on unverified self-generated repairs or final acceptance answers. Model or weight promotion remains governed by existing authority.

## Lessons and self-improvement

A reusable lesson must name its verified source kind, supported success pattern/failure observation/procedure, applicable component/device/source versions, independent outcome receipts, known adverse cases and invalidation conditions. Every ordinary job contributes factual experience even when no new lesson is justified. Extend the existing knowledge store/curator/MCP and usage history as described in [continuous-learning.md](continuous-learning.md); preserve legacy repair validation and the separate inspector channel. Store learning separately from authoritative requirements/policy, test applicability and support retraction without altering historical evidence.

Prefer compact conditional recipes that improve evidence selection or repair targeting over growing a universal prompt with every prior experience. A lesson may suggest an action; it cannot authorize it, declare a gate passed or override a source contradiction. Evaluate benefit on separate cases and retain failures so repeated mistakes do not become accepted memory.

Candidate factory improvement follows DA-FR-022 and DA-FR-030. Current protected AFO/CRE/skill/policy defects remain external engineering work. The future worker-promotion design is proposal-only and does not block delivery of the core recovery implementation.

## Capability-ceiling behavior

When the qualified local role repeatedly fails within its permitted envelope, stop and retain an explicit reason: missing evidence, unsupported protocol, insufficient qualified context, repeated unsupported engineering hypothesis, inspector qualification failure, exhausted resources, or unresolved cause. Do not label an unresolved failure as proven model incapability.

The allowed next step is selected from current authority: deterministic repair recipe; qualified adapter; narrower evidence-complete work unit; bounded materially different candidate; already qualified local configuration; or staged external-engineering need. No step may silently relax gates, extend an expired grant, reset lineage, introduce cloud inference, activate an unqualified model or promote protected source.

If no authorized capable path remains, preserve staged artifacts, evidence, receipts and the exact unmet obligation, and report BLOCKED/EXHAUSTED/FAILED_PROTOCOL as appropriate. Other independent authorized work may proceed. Conditional downstream work such as GPIO remains dependent on its real prerequisites.

The intended outcome is measured unattended progress within this capability envelope. The spec must not claim that Qwen is sufficient for the full product benchmark until the required local protocol, repair, inspector and end-to-end campaigns demonstrate it.

## Requirement and acceptance mapping

| Design concern | Existing feature requirements | Qualification coverage |
|---|---|---|
| Complete evidence and effective context | DA-FR-002–004 | DA-AT-002–004; LM-02, LM-04 |
| Bounded semantic judgment and actual adapter contract | DA-FR-005–010 | DA-AT-005–010; LM-01, LM-03 |
| Mission-bounded search, costs and cancellation | DA-FR-011–013, DA-FR-017–018 | DA-AT-011–013, DA-AT-017–018; LM-05, LM-07 |
| Counterexamples, grounding and independent gates | DA-FR-019–021 | DA-AT-019–021; LM-04–06 |
| Candidate-only improvement and validated lessons | DA-FR-022–023, DA-FR-030 | DA-AT-022–023, DA-AT-030; LM-08 |
| Fixed cohorts, capability measurement and honest limits | DA-FR-024–028 | DA-AT-024–028; all LM experiments with explicit NOT_RUN/PASS/FAIL evidence |
| Per-role capability and short-horizon decomposition | DA-FR-031–032 | DA-AT-031–032; LM-01, LM-02, LM-04, LM-06 |
| Evidence-indexed memory and bounded verifier-guided search | DA-FR-033–034 | DA-AT-033–034; LM-04, LM-05, LM-08 |
| Correlated inspection errors and capability-limit fallback | DA-FR-035–036 | DA-AT-035–036; LM-06, LM-08 |
| Every-job learning through existing knowledge, inspection, CRE and KPI paths | DA-FR-037–044 | DA-AT-037–044; chronological ordinary-job transfer and comparable memory-enabled/baseline evaluation |

## Primary references

- [Ollama structured outputs](https://docs.ollama.com/capabilities/structured-outputs): schema-constrained generation and post-generation parsing; installed adapter behavior still requires local qualification.
- [MCP tools specification](https://modelcontextprotocol.io/specification/2026-07-28/server/tools): actual tool schemas, structured results and actionable execution errors. MCP result structure is distinct from constrained model generation.
- [CounterExample Guided Neural Synthesis](https://arxiv.org/abs/2001.09245): combining neural candidates with deductive checking; guarantees depend on the formal specification and verifier.
- [Agentic Harness Engineering](https://arxiv.org/abs/2604.25850): explicit editable components, inspectable experience and hypothesis-driven evaluation. Published results do not establish this local model's competence.
- [Temporal activity definition](https://docs.temporal.io/activity-definition): durable execution requires application-level idempotency and reconciliation of effects. Adopting that pattern does not require replacing Forge-C/Fabro.
