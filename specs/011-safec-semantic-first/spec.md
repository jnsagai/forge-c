# Feature Specification: Forge-C local semantic-first execution with SafeC Forge

**Feature branch:** `feat/011-safec-semantic-first`  
**Created:** 2026-10-22  
**Status:** DRAFT / SPECIFICATION ONLY — no runtime implementation or model qualification claimed.  
**Input:** Owner approved planning a new Forge-C local strategy using an independently maintained SafeC Forge semantic/formal core, and requested Claude Code as development implementer.

## Problem and verified baseline

- Feature 010 / PR #34 has merged into Forge-C `main`; preserve it. The LRTX-T024 campaign stopped after 13/30 attempts, **0 READY**, all blocked at SWE.1, consuming 8.41 h, 640 model calls, 3,190,255 input tokens and 204 Wh GPU-board energy. The campaign is NOT_PASS, not a completed 30-case benchmark.
- IWDG-LL 10/10 SWE.1 author outputs passed the deterministic author gate and were subsequently blocked by the NOT_QUALIFIED local Qwen inspector. RCC-LL 3/3 blocked earlier: invalid field-value/register-mask interpretation and an EARS unknown-symbol error persisted despite actionable feedback.
- T021 seeded defects: 2 deterministic detections, 1 of 7 inspection-relevant defects detected **on target**, 4 off-target failures and 2 misses; 2/2 clean READY holdouts were falsely rejected. T023: `qwen3:8b` SWE.1 author 0/3 frozen vs Qwen3-Coder 30B 3/3, so do not promote the small model without new evidence.
- A separate, documented shared rework-route bug computes progress extensions but can still return BLOCKED when `Store.gate` has already blocked at the checklist threshold; remediation is subject to independent shared-path review.
- The current SafeC Forge (independent **private** repository, reference commit `556dca8df4d2fccd9cb59fd8fb0432aafdd05835`) has a Rust core, narrow validated CSRI/sampled-latch semantics, formal Kind 2 analysis, C11/ACSL contracts, test generation, candidate verification and immutable evidence. **It does not yet implement a generic MCU-register/RCC/IWDG semantics profile.**
- Forge-C base commit: `2f4b9cf44fd9cc56648fa26b6da6c2e29248338d` (merged PR #34). The preserved Claude/Codex source reference is `86f1f40c030bc721e7e5125a572d69647c4ac041` on `baseline/codex-claude-2026-10-21`.

## Goal

Enable a genuinely offline Forge-C execution profile on RTX 4070 Laptop 8 GB VRAM / i9-14900HX / 32 GB RAM. Combine authoritative, traceable hardware semantics and deterministic contracts/test oracles with **small, bounded local-model decisions**, independently assessed evidence and the **unchanged** ASPICE SWE.1–SWE.6 gates. Preserve the functional Codex/Claude deployment; do not substitute a cloud service at factory runtime. Claude Code may implement this feature using cloud inference in a separate development workflow.

## User scenarios and independent acceptance

### US1 (P1) — Reproducible and non-destructive semantic bridge

The operator explicitly selects `local-rtx-v2`; the existing local profile, default and ACP/Codex/Claude lines behave as before. A read-only, pinned SafeC executable receives bounded typed requests and emits auditable evidence without depending on network access. **Independent test:** run `safec-bridge` conformance fixtures offline, then compare all existing compatibility fixtures before and after; verify denied network and isolated writable roots.

**Scenarios:** Given a missing/wrong executable digest, the request is REFUSED before execution; given the old profile, the generated graph/provider config is unchanged; given SafeC returns unsupported, the phase is not allowed to PASS because of that response.

### US2 (P1) — Hardware truth before text generation

For RCC-LL and IWDG-LL, a deterministic register semantic model records source RM/errata provenance, field location/width/access, reset/access side effects and typed operations. The model can only propose functional intent referencing verified fields; the engine computes values, masks and effects and renders EARS/trace artifacts **without inventing missing facts**. **Independent test:** known IWDG key values, RO flags, RCC ADC12EN 1-bit value vs bit mask, out-of-scope registers, reserved bits and contradictions give the expected PASS, FAIL or UNSUPPORTED with exact finding IDs.

**Scenarios:** Given logical `1` on a 1-bit field at bit 5, compute field value `1` and register mask `0x20` separately; given a field that is RO/unknown or W1C without approved semantics, reject improper operations; given a missing owner safety allocation, preserve PENDING and applicable EASA blockers without fabricated acceptance.

### US3 (P1) — Evidence-grounded and independent inspection

Inspectors receive only a frozen candidate baseline and authoritative evidence, not author chat state. Findings name check ID, artifact/path/requirement, exact source reference, falsifiable assertion, effect and remediation; factual refutations and owner scope decisions are adjudicated deterministically, without a wording blacklist or indefinite semantic restatement loop. **Independent test:** run clean holdouts and seeded mutants, count on-target detections, off-target findings, misses and false rejections separately. Model family and digest are measured; no unqualified model becomes the release inspector.

**Scenarios:** Given a PENDING allocation allowed as a recorded process state, do not invent it as approved or repeatedly flag it contrary to policy; given a genuinely missing required ASIL B safety input, preserve the genuine blocker; given missing source support, emit INCONCLUSIVE/UNSUPPORTED and stop, never PASS.

### US4 (P2) — Bounded repair and useful progression

The operator can pilot SWE.1 and SWE.2 separately before any end-to-end run. Deterministic feedback identifies the exact element and changes only that element; identical invalid output short-circuits to STUCK, while measurable legitimate improvement follows the authored bounded policy. **Independent test:** freeze RCC and IWDG reference work orders, compare original source fingerprints, and run repeated genuine local visits and route regressions.

### US5 (P3) — Independent tests and proofs through SWE.3–SWE.6

Generated candidate C and tests trace to the same validated requirement contract but test oracles never derive from candidate C. Candidate compilation, host tests, Renode/Robot, bounded CBMC/Frama-C/Kind 2 **where semantically supported** are versioned evidence; unsupported/partial analysis is not labeled proof or MISRA coverage. **Independent test:** corrected and mutant implementations diverge as expected in independently generated assertions; no full-phase gate is bypassed.

## Functional requirements

- **F011-FR-001** Provide explicit `local-rtx-v2` opt-in. Default, ACP Codex/Claude and `local-rtx-v1` routing shall be observationally unchanged in compatibility fixtures.
- **F011-FR-002** Preserve immutable source/provenance baseline, archived workorders and host deployment. Independent roots, ports, service names, environments, models and archives; no writes to protected deployed paths.
- **F011-FR-003** Keep production local-only: block cloud/ACP provider fallback, prove network denied, allow only version/digest-pinned local tools/models. Cloud-based Claude **development** is not a runtime provider.
- **F011-FR-004** Keep one canonical Forge-C SWE.1–SWE.6 gate and offline review authority. No shortcut, change in ASIL/QM scope, false ISO/ASPICE/MISRA claim, automatic product acceptance, or SUP/MAN scope expansion.
- **F011-FR-005** Use a cross-repository, versioned SafeC CLI/JSON boundary with SHA-256 inputs, exact tool identity, bounded resource limits, closed result statuses and independently verified evidence. Do not vendor or publish private SafeC source in public Forge-C.
- **F011-FR-006** Verify Linux build/tool compatibility on the actual target before enabling SafeC formal backends; absence or incompatible tool versions are UNKNOWN/UNSUPPORTED, never PASS.
- **F011-FR-007** Create a new, explicitly versioned `register-io-0.1` semantic domain **inside SafeC**; do not reinterpret the existing sampled-latch CSRI or silently change its approved semantics.
- **F011-FR-008** Anchor each register, field, access mode, value encoding, reset/side-effect assumption and source passage to baselined RM/errata and owner-scoped work order hashes.
- **F011-FR-009** Distinguish field logical value from register-bit mask/shift; validate widths, signedness, reserved bits and read/write modes, with explicit unsupported access semantics.
- **F011-FR-010** Support only specifically modeled operations (read, set/clear, field write, key/write-only sequences) with conservative and explicit semantics; no inference of W1C, self-clearing, lock, timing or side effects.
- **F011-FR-011** Detect unknown symbols, out-of-scope field use, aliases, contradictions, duplicate operations and contradictory startup/reset behaviors before synthesis.
- **F011-FR-012** Generate a versioned typed intermediate contract and deterministic SWE.1 effects, EARS statements/IDs, source-to-SWR mappings and test expectations; keep all existing final workproduct formats.
- **F011-FR-013** Restrict local author model to choosing/documenting source-backed semantic intentions in finite JSON schemas. Unsupported ambiguity remains OPEN_POINT/INCONCLUSIVE, never guessed.
- **F011-FR-014** Keep full source/requirement coverage inventory; explicitly record not-covered fields and signed/approved scope exceptions where needed. A narrow task never silently loses whole-system coverage.
- **F011-FR-015** Bind checkpoints to input/source, SafeC executable & schema, model digest, prompt, policy and gate hashes; invalidate dependent outputs on any relevant change.
- **F011-FR-016** Enforce role-separated author/inspector identities, contexts, permissions and source-only inspection; production AI tool use remains SKILL/MCP-governed.
- **F011-FR-017** Each inspection finding requires check ID, exact target, claim, evidence provenance, expected-vs-observed semantics, severity and actionable remediation. A prose-only objection cannot authorize rework.
- **F011-FR-018** Triage contested findings under a closed policy with deterministic evidence checks and auditable adjudication; do not teach an inspector to pass by adding wording-pattern exceptions.
- **F011-FR-019** Treat fail, inconclusive, unsupported, stale, timeout, tool-error and incomplete checks distinctly; any mandatory unresolved state yields BLOCKED, never READY.
- **F011-FR-020** Run the T021 catalog on clean holdouts and seeded semantic mutants, plus held-out unseen cases, with blind provenance and on-target detection metrics. No training/evaluation leakage.
- **F011-FR-021** Local inspector candidates (including separate-family models) are NOT_QUALIFIED until independently measured on target hardware and exact digest. Measure switching, loading and retries; never silently route to another model.
- **F011-FR-022** Preserve rework/stuck caps; repair exact semantic deltas, detect repeated unchanged invalid outputs, and keep all attempts in the evidence. Any shared gate bug fix requires independent tests and CRE review in a separate change.
- **F011-FR-023** Extend SWE.2 interface binding without name drift, retain full allocation; SWE.3/4/5/6 verification oracles derive from frozen requirements, not generated implementation.
- **F011-FR-024** Bind all proof/test claims to exact model, assumptions, bounds, target/host execution mode, policy and tool digest; a bounded proof is not an unbounded or on-hardware guarantee.
- **F011-FR-025** Reuse SafeC evidence envelopes only after mapping their semantics into Forge-C policy. Never treat SafeC `policy_satisfied` as Forge-C release approval or full MISRA/ISO proof.
- **F011-FR-026** Record tokens, calls, prefill/decode, load/switch, wall time, verified GPU-board energy and quality per accepted package, with failures included and UNKNOWN clearly marked.
- **F011-FR-027** Stage qualification from contract fixtures to holdouts to isolated SWE.1/2 to gated end-to-end 30-case campaign. Abort expansion early if the prior gate failed; no repeated expensive campaign to hide a blocker.
- **F011-FR-028** All work is reproducible from pinned commit IDs and dependency/tool/model manifests. Human offline safety/process acceptance remains external.

## Entities

- `SemanticSource`: immutable RM/errata/workorder excerpt, digest, section, pages, authority, scope.
- `RegisterDomain`: peripheral, register, field, bit span, access, supported side effects and source link.
- `SemanticIntent`: model-proposed, finite operation linked to known sources and named requirement.
- `ValidatedContract`: canonical versioned semantics, exact hashes, effect and verification obligations.
- `InspectionClaim`: independent criterion, targeted evidence, finding or evidence-backed non-finding.
- `BridgeExecution`: versioned request/result, tool identity, resource use, deterministic verdict, evidence digest.
- `QualificationRecord`: role/model digest, host, catalog and independent measured results, no self-qualification.

## Success criteria — measured, not presumed

- **F011-SC-001** Existing default/ACP and local-v1 compatibility fixtures remain unchanged; existing deployment and archived evidence remain untouched.
- **F011-SC-002** Offline, hash-pinned Linux bridge conformance passes; no cloud calls or host/deployment root overlap; SafeC source is not exposed.
- **F011-SC-003** All frozen register semantic positive and adversarial fixtures produce exact expected machine-readable results; no accepted mask-as-value, RO write, unknown field, invented semantics or out-of-scope effect.
- **F011-SC-004** On the frozen T021 catalog, all applicable critical seeded defects are detected **on target**, 0 known false rejections on 2 clean holdouts, plus independent unseen holdouts. Failures are reported, not waived. Sample size is not a reliability/qualification proof.
- **F011-SC-005** Three independent local SWE.1 author+inspector visits per IWDG-LL and RCC-LL freeze and pass the unchanged SWE.1 gates, without manipulating recorded owner safety decisions; any genuine missing mandatory allocation is reported honestly.
- **F011-SC-006** Three isolated SWE.2 attempts per pilot after a genuinely accepted frozen SWE.1 baseline pass the existing SWE.2 author+inspection gates; record retries and confidence limits.
- **F011-SC-007** No new SWE.3–SWE.6 claim without actual local-model, tool and inspection evidence. Correct and mutated candidate implementations must be distinguished on specified verification obligations.
- **F011-SC-008** Only after SC-001..007 are met, execute a newly frozen comparable 30-case end-to-end campaign with target >=27/30 READY_FOR_OFFLINE_REVIEW and separate false-positive/miss metrics. This is pilot target, not ASIL qualification.
- **F011-SC-009** Report total wall time, calls, tokens and GPU energy per accepted work order, including all attempts, and compare with Feature 010 baseline. Improvement is a goal; quality gates have absolute priority.

## Non-goals and assumptions

- No training/fine-tuning, no cloud inference in unattended factory operation, no release auto-promotion, no claim of tool qualification, ASPICE capability or ISO 26262 certification.
- Do not require all of SafeC formal proving capabilities for operations outside its validated semantic domain; mark them UNSUPPORTED and preserve separate Forge-C assurance obligations.
- SafeC remains a separately versioned **private** dependency. Its Windows/WSL verification does not establish Linux portability; perform Linux probes on the actual host before claiming support.
- Claude Code uses cloud resources only for **engineering and PR authoring**, with approved repository access. The shipped `local-rtx-v2` runtime is fully offline.
- Runtime resource reference: RTX 4070 Laptop 8 GB VRAM, 32 GB RAM; only one local model resident/request in the initial pilot. New models must pass resource and quality probes.
- Existing ASIL B work orders with missing mandatory owner-supplied safety evidence may remain BLOCKED by correct policy. Never manipulate scope to meet SC-008.
