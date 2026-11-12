# Feature Specification: SWE.1 output-first requirements pipeline

**Feature Branch**: `feat/017-swe1-output-first`
**Created**: 2026-11-08
**Status**: Specified for incremental implementation; native validation NOT_RUN
**Owner intent**: Optimize SWE.1 first. Produce requirements, not reasoning narratives. Apply the approach to any driver. Prefer determinism and simplification, while proving the deployed author and inspector can operate effectively at the selected reasoning settings.

## Scope and boundaries

The deliverable is reviewed software requirements, source/upstream traceability, verification criteria, coverage disposition and explicit unresolved issues. Keep `stop_after: SWE.1` for this feature's experiments. A phase-complete SWE.1 result is not a complete SWE.1–SWE.6 release package.

Runtime remains local-only. Claude is the factory implementation engineer, not a runtime dependency. Preserve Fabro, existing admission controls, author/inspector separation, versioned role skills and production MCP boundaries. Use the existing ASPICE-only development lane without implicitly enabling SafeC or safety-assurance requirements. Protected safety lanes and acceptance policies remain intact.

Out of scope: implementing SWE.2–SWE.6, modifying delivered frozen drivers, changing the models by default, fine-tuning, adding a vector database, replacing the orchestrator, creating a multi-agent platform, collecting chain-of-thought, production rollout and claiming assessed ASPICE or safety compliance.

## User scenarios and acceptance

### US1 — Verify output mode and cost on the deployed stack (P1)

As the operator, I can discover the actual author and inspector identities, probe thinking controls through their real gateway, and compare author output modes without changing inspector behavior at the same time.

Independent test: a bounded probe plus paired requirement tasks produces a reproducible report even when thinking-off is unsupported.

1. Given an unknown runtime, discovery records model name/digest, quantization, backend version, template identity, gateway revision and effective role routing; missing information remains unknown.
2. Given an ignored or unsupported control, the result is UNSUPPORTED or UNVERIFIED, never PASS merely because the HTTP request succeeded.
3. Given a thinking-off candidate, trials compare accepted requirements and full repair cost against the unchanged author baseline, with inspector settings held constant.
4. Given no access to Omniverse, replay/unit work can proceed but native results remain NATIVE_NOT_RUN and no profile is promoted.

### US2 — Preserve work and produce accurate diagnostics (P1)

As the operator, I can trust call accounting, repair findings and resume behavior.

Independent test: synthetic replay demonstrates normalization, patch rejection, crash recovery and exact ledger-to-summary reconciliation without a model.

1. A redundant, matching register prefix is normalized to the canonical field; an ambiguous or mismatching prefix becomes a representation finding, not an instruction to delete requirements.
2. A repair removing required or accepted behavior is rejected atomically; the previous candidate remains available.
3. All launched calls have a durable outcome or an explicit unknown/interrupted outcome. Superseded attempts remain in totals.
4. Resuming with unchanged dependencies reuses accepted contracts. Changed dependencies reopen only affected contracts and aggregate checks.

### US3 — Author compact generic contracts and render requirements (P2)

As a requirements engineer, I receive readable requirements and source links while the factory handles IDs, formatting and bookkeeping.

Independent test: configuration, bounded waiting and asynchronous completion behaviors use the same core schema and renderer, without new driver-name branches.

1. The model receives one coherent behavior and relevant evidence and returns only requested contract fields or scoped findings.
2. Deterministic rendering creates EARS statements, stable IDs, trace links and verification criteria without another model call.
3. Non-applicable timing, concurrency or failure concerns have an explicit justified disposition; no invented behavior fills a mandatory-looking field.
4. A reusable behavior can cover multiple instances through explicit domains and exceptions without authoring independent policies for each instance.

### US4 — Complete behavioral coverage and review meaning (P2)

As an engineer, I can distinguish structurally valid JSON from complete, source-supported requirements.

Independent test: an independently reviewed obligation inventory and seeded defective requirements expose omissions, source conflicts and cross-contract inconsistencies.

1. Mentioning every API or field does not satisfy missing behavior/value/state obligations.
2. An invalid-input policy unsupported by sources or an accepted engineering decision remains unresolved.
3. A frozen implementation discrepancy is recorded; neither code nor requirements are silently changed to hide it.
4. Valid contracts are also checked together for inconsistent shared domains, preconditions and failure policies before SWE.1 acceptance.

### US5 — Recover with bounded, measurable progress (P3)

As an operator, failures produce appropriate repairs, continued independent work or precise blockers rather than unlimited repeated generation.

Independent test: repeated findings cause a strategy change or terminal task blocker; accepted dependencies survive restart.

1. Representation errors use deterministic repair where unambiguous; semantic gaps use targeted authoring or evidence acquisition.
2. An initial draft plus at most two targeted repairs is the initial configurable policy. Further model work requires a recorded different strategy and remaining task/phase budgets.
3. Independent tasks may continue after a blocker, but a phase cannot pass with mandatory unresolved obligations.
4. Neither a repeated visit nor task repartitioning resets the enclosing phase budget.

## Functional requirements

- **FR-001** Preserve SWE.1-only scope and local-only runtime, with an isolated experimental profile and rollback to the unchanged baseline.
- **FR-002** Discover deployed identities and serving configuration per role; never infer the current inspector from an old plan or author-only archive.
- **FR-003** Probe structured-output support, thinking control, output/total-generation limits, streaming, timeout and cancellation through the real gateway. Capability records bind to model digest, template, backend, gateway and profile identity.
- **FR-004** Express reasoning policy as a backend-neutral request (`off`, `bounded`, `baseline`) with backend-specific verified mappings. Unsupported mappings must not silently fall back to an expensive default.
- **FR-005** Try author thinking-off as a candidate, not an automatic production default. Preserve the inspector configuration during the initial author comparison; evaluate inspector changes independently with seeded defects.
- **FR-006** Return requirements/contracts and concise structured findings only. Do not request plans, self-review essays or thought traces. Do not persist hidden reasoning. Numeric reasoning counts are allowed; absent counts are null with a measurement basis, not zero.
- **FR-007** Maintain an append-only call lifecycle ledger. Derived summaries account for retries, rejected outputs, cancellations, errors, loading/queue time and incomplete usage. Deduplicate by call/event identity, not matching token totals.
- **FR-008** Enforce one resolved budget policy for calls, tokens and elapsed time at task and phase levels. Record requested versus effective settings. Separate context reservation from enforceable generation limits. Unknown token usage cannot bypass time/call limits.
- **FR-009** Represent required behavior as generic contracts and a separate coverage inventory; core rules must not depend on a peripheral name or register presence.
- **FR-010** Separate known source facts from model-proposed engineering decisions and unresolved claims. Every substantive contract claim has evidence or a traceable decision. Sources and decisions remain distinguishable.
- **FR-011** Make applicability explicit for timing, failure, concurrency and resource constraints. Missing evidence is not proof that a concern is not applicable.
- **FR-012** Render EARS, IDs, traceability and document structure deterministically. Rendering must preserve meaning and may not invent behavior, resolve ambiguity or assert verification execution.
- **FR-013** Canonicalize identifiers only when semantics are unambiguous. Use task-specific enums and validate matching prefixes. Do not mislabel malformed identifiers as scope exclusions.
- **FR-014** Plan and review coverage before authoring. Map obligations to behaviors, supported domains, states, values and exceptions. Parameterization requires explicit domain membership and exception handling.
- **FR-015** Use bounded evidence packets containing applicable rules, interfaces and authoritative facts. Preserve necessary conditions and provenance; repartition instead of silently truncating evidence.
- **FR-016** Apply constrained patches against a recorded base revision/hash, then validate structure, meaning and coverage. Reject stale, unrelated or regressive patches atomically.
- **FR-017** Separate structural checks, semantic inspection, aggregate consistency and phase acceptance. Deterministic checks do not prove all semantic claims, and model inspection is not formal certification.
- **FR-018** Distinguish new development, frozen implementation assessment and controlled modification. Unsupported behavior for a frozen driver becomes a discrepancy or an explicit supported-domain gap; it cannot be invented as defined behavior.
- **FR-019** Classify findings and route recovery deterministically, using stable finding codes and target IDs. Lack of progress triggers a different strategy or explicit blocker, never unchanged unbounded retries.
- **FR-020** Preserve accepted units and invalidate them by dependency hashes, including shared decisions, sources, schema, renderer, validator and inspection policy. Cache reuse and invalidation have auditable reasons.
- **FR-021** Keep author and inspector identities/contexts separate. The inspector receives requirements, relevant evidence and obligations, not author reasoning. Findings identify defect, location and supporting evidence.
- **FR-022** Emit a SWE.1 phase report containing reviewed requirements, upstream/source traceability, verification criteria, scope/coverage dispositions and blockers. Preserve existing downstream formats through an adapter; do not fabricate test execution or future SWE.6 completion.
- **FR-023** Promotion requires the frozen evaluation protocol in validation.md. Faster generation alone, schema validity, empty findings or one successful example cannot qualify a profile.
- **FR-024** Retain private inputs and runtime artifacts outside git. Use synthetic or license-cleared fixtures in repository tests; do not commit uploaded diagnostic archives or vendor excerpts.

## Edge cases

An empty requirement array for a nonempty mandatory scope; a server that ignores thinking-off; truncated JSON; cancelled streams with no final usage; unknown model digest; a crash between response receipt and ledger completion; concurrent repair against an old revision; missing source clauses; empty parameter domains; mismatching field prefixes; accepted exclusion later invalidated by scope change; source facts contradicting frozen code; insufficient memory for both models resident; all-nonzero presets masking neighboring-bit corruption; unchanged token totals across genuinely distinct calls.

## Success criteria

- **SC-001** Every capability claim is either native-evidence-backed for the exact serving identity or explicitly UNVERIFIED/UNSUPPORTED/NATIVE_NOT_RUN.
- **SC-002** Synthetic ledger fixtures reconcile exactly and retain all attempts; incomplete measurements are surfaced, never silently converted to zero.
- **SC-003** All mandatory normalization, patch-regression, cancellation, resume, coverage and seeded-defect regressions pass.
- **SC-004** At least three contrasting behavior families across at least two driver families use the same core contract, with one held-out behavior case not used for prompt tuning.
- **SC-005** The native candidate meets validation.md correctness and coverage gates before any performance claim or promotion. Initial improvement targets are at least 50% fewer total generated tokens and 30% lower median full task latency, including repair cost; report actual results if unmet.
- **SC-006** A complete SWE.1 work order either reaches phase acceptance with all mandatory obligations satisfied or produces a correct gap package. A correct BLOCKED outcome is not mislabeled as complete requirements.
- **SC-007** Later-phase execution, frozen delivery bytes, legacy selected-profile behavior and existing protected gates remain unchanged by this feature's selection.

## Assumptions

The implementation engineer can inspect the actual deployment or will report native work NOT_RUN. Model families in historical plans are candidates until discovered. The existing runtime may already implement portions of this design; reconcile and reuse them. The feature is prospective ASPICE-only engineering development and adds no safety or compliance qualification.
