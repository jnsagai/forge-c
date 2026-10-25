# Research and design decisions

**Status:** design rationale, not runtime qualification. Local-model limitations are specified in [local-model-design.md](local-model-design.md); native facts and unresolved causes are separated in [evidence-baseline.md](evidence-baseline.md).

## D1 — Retain existing orchestration and strengthen effect boundaries

The repository already has durable attempts, nonce adoption, policy checks, outbox concepts and independent gates. Extend those paths instead of introducing a second orchestration authority. Stable effect identities and reconciliation matter more than framework choice. Temporal's [activity documentation](https://docs.temporal.io/activity-definition) explains why retries still require idempotent effects; importing a framework does not prevent duplicate external actions by itself.

## D2 — Controller-owned packet and small semantic proposal

The observed invalid administrative fields and missing final artifact justify removing clerical work from the model. Qwen selects a scoped strategy and predicts a testable effect; deterministic binding supplies authoritative identifiers and budgets. The existing full plan remains independently validated. An optional evidence-request exchange is bounded and charged to the same mission.

[Ollama structured output](https://docs.ollama.com/capabilities/structured-outputs) supports JSON schemas, but generated structure is not semantic correctness. Test the installed gateway's exact behavior; do not assume tool calling and constrained final generation compose correctly. [MCP structured content](https://modelcontextprotocol.io/specification/2026-07-28/server/tools) is a different mechanism from constrained model generation. Real SDK registration tests address the metadata-loss defect the trial exposed.

## D3 — Receipt instead of model-authored completion

Separate proposal storage, plan admissibility, dispatch and verified repair. A deterministic projection of a durable receipt is the compact final output. A correct CLOSE_BLOCKED decision is distinct from protocol failure and cannot count as successful repair. The authoritative receipt is reconstructed after response loss without another effective dispatch.

## D4 — Explicit budgets and liveness

Model calls, tool calls, tokens and wall time are different resources. Shared lineage accounting must survive continuation and restart. Request admission and provider-supported output limits precede inference; late/unknown usage retains conservative charges. Polling alone cannot enforce an exact token cap. Business terminality must not discard a potentially live native process or verifier.

## D5 — Verification-driven local engineering

Small obligation/counterexample/patch/check loops reduce the amount of simultaneous reasoning demanded of a local model. This follows the proposal/check/feedback pattern of [CounterExample Guided Neural Synthesis](https://arxiv.org/abs/2001.09245). It supplies no general proof that Qwen repairs arbitrary C code: formal guarantees apply only to properties represented in a sound verifier. SafeC and other deterministic checks retain their actual coverage limitations and do not become universal phase authorities.

Decomposition requires a global obligation inventory and dependency checks. Otherwise a collection of locally plausible answers can omit behavior or contradict another component. Repeated self-review by the same model is not independent defect detection.

## D6 — Observable, reversible candidate improvement

[Agentic Harness Engineering](https://arxiv.org/abs/2604.25850) motivates explicit editable components, drill-down experience and hypotheses evaluated against later outcomes. Apply that method to permitted candidate patches and validated lessons, using separate development/validation/final holdout data. Published benchmark improvements do not qualify Omniverse2 or justify uncontrolled runtime mutation.

Weight training, online reinforcement learning, model swarms and unconditional token increases are excluded from this feature. They do not address the demonstrated protocol defects and would confound the baseline. A separately authorized measured local-model comparison is allowed after deterministic fixes and unchanged-profile measurement; successful RCC recovery is not required before testing a necessary model change.

## D7 — Operational autonomy and source promotion remain distinct

Model-free recovery uses currently approved recipes. Changing or rolling back a release needs explicit authorization for that transition. AFO-FR-053 and protected maintainer paths remain unchanged. A future narrow worker-promotion design is documented separately and cannot block delivery of the core recovery substrate.

## Open questions resolved through experiments

- V4 native termination: inspect stop reason, actual counted calls and recorder behavior; do not select a cause from aggregate token usage.
- Effective context: measure full serialized packets and semantic evidence retrieval at varying complexity; configured capacity is not a competence guarantee.
- Local semantic capability: freeze per-role cases and independent expected outcomes; distinguish protocol failure, missing evidence, faulty verifier and model capability limit.
- Resource limits: measure model residency, input processing, generation and cancellation on the selected profile before changing precision/context/concurrency.
- Full RCC repair cause: inspect actual SWE.3 findings and reference/tool evidence; 50 package gaps are not 50 independently diagnosed defects.

## D8 — Every-job learning extends existing capabilities

The existing general `LessonStore` has durable SQLite/FTS5, validation, bounded retrieval, usage, TTL and retraction, but its source proof is restricted to PROMOTED repairs. The knowledge MCP and curator use that same repair-only contract. Extend those interfaces with explicit versioned ordinary-outcome/negative-observation source checks instead of fabricating incidents or adding a parallel knowledge authority.

Keep Feature 011 inspector knowledge separate: generic recorded-source lessons, deterministic scope selection, paired critical-defect checks and CRE promotion are stronger than ordinary author memory. Reuse Feature 003 comparable KPI cohorts and Feature 004 CAPA/CRE for effect measurement and candidate improvements. Full detail and observed integration gaps are in [continuous-learning.md](continuous-learning.md).

Every job produces factual experience and a disposition. A novel transferable lesson or improved metric is an empirical result, not a mandatory model assertion. Preserve negative results, chronological evaluation and independent holdouts; count learning overhead. Normal validated-memory use can improve future behavior within existing knowledge authority, while protected source/prompt changes still follow external promotion rules.

## D9 — Continuous service extends existing AFO recovery ownership

Feature 005 already requires headless 24/7 service, bounded recovery, fair continuous intake, dead letters and operator controls. The amendment makes service lifetime explicitly independent of finite engineering work. At inspected repository revision `511861f`, the Conductor template uses `Restart=on-failure`, a bounded start burst and notify/watchdog; the external AFO watchdog explicitly alerts without restarting. The supervisor has `Restart=always` and its own bounded burst. Installed host behavior remains unverified.

Unexpected clean exit and exhausted start limits need explicit recovery coverage. Official [systemd.service](https://www.freedesktop.org/software/systemd/man/latest/systemd.service.html) documents exit/restart and operator-stop semantics; [systemd.unit](https://www.freedesktop.org/software/systemd/man/latest/systemd.unit.html) explains that start-limited units need a later start trigger. Extend the existing independent operations path with persistent bounded cooldown and intent checks, preserving restart limits and human shutdown. Inspect the installed version rather than assuming latest-manual directives exist on Omniverse2.

Continuous availability requires isolation, durable waiting and resource housekeeping as well as restarts. A budget-exhausted model job cannot renew itself, while model-free supervision continues and unrelated eligible jobs progress. Missing telemetry, storage loss and power failure remain reported outages; no single-host zero-downtime claim follows from an indefinite loop. Full integration design and qualification scope are in [continuous-operation.md](continuous-operation.md).
