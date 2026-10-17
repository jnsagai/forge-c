# Feature Specification — 006 Enhanced AI Software Assurance (EASA)

**Branch:** `feat/006-enhanced-ai-software-assurance`  
**Created:** 2026-10-17  
**Status:** PROPOSED / SPECIFICATION ONLY / NOT IMPLEMENTED  
**Baseline:** Feature 005 branch, which depends on Feature 004; existing features 001–005 unchanged.  
**Target:** Enhanced independent engineering assurance of AI-generated embedded C HAL/LLD across SWE.1–SWE.6, on current approved Automotive SPICE baseline; **NO new SUP/MAN process workflows**.

## 1. User intent and interpretation

The product's ASIL comes from approved automotive safety allocation; an internal **assurance overmatch** profile may apply verification methods more demanding than the product ASIL recommendations, where risk and evidence justify them. Assurance Overmatch is a Forge-C engineering term, NOT a normative ISO concept or a new ASIL. The goal is to detect wrong artefacts, unreliable oracles and test gaps, not to grow paperwork or falsely assert compliance.

## 2. Non-negotiable invariants

- **INV-01:** no agent may change product ASIL, ISO/ASPICE edition, safety allocation, HSI authority, or release status to make a gate pass.
- **INV-02:** selected methods, metrics and rationale are bound to product ASIL and a *separate* project assurance profile, each frozen and versioned.
- **INV-03:** initial 47 ASIL B `++` rows are **a traceable secondary-source working index**, NOT reproduced copyrighted standard text or an authoritative licensed-method baseline. Their accuracy, alternatives, footnotes and applicability require competent reconciliation against a licensed ISO 26262-6:2018 copy before a normative claim. Unverified ratings cannot independently support a compliance claim.
- **INV-04:** a file being present, an LLM author/inspector stating PASS, or a terminal package being created is not evidence of correctness.
- **INV-05:** independent deterministic executable or appropriately controlled human technical evidence must support every acceptance claim; common-cause model/oracle contamination must be detected and explicitly recorded.
- **INV-06:** preserve existing SWE.1–SWE.6 author/independent-inspector/gate cycle and traceability; no agent-created safety approval or automatic certification.
- **INV-07:** coverage metrics are measured rather than assumed. No ISO-mandated universal 100% coverage threshold may be invented. Explicit gaps have justified disposition under approved project policy.
- **INV-08:** MC/DC is a *supplementary risk-based technique* for ASIL B (`+`, not `++` in ISO 26262-6:2018 Table 9). Mutation score is a Forge-C project measure, not a normative ISO 26262 threshold.
- **INV-09:** Renode/Cortex-M55 model, host, HIL and physical hardware are distinct verification environments. Simulated success cannot be labelled hardware-validated or HIL.
- **INV-10:** incomplete tool confidence/MISRA family coverage are visible gaps; Cppcheck partial checks cannot masquerade as complete MISRA or tool qualification.
- **INV-11:** ISO 26262 safety support documentation missing in ASIL-scoped production blocks release; formally scoped QM may designate N/A with a rationale, never a silent waiver.
- **INV-12:** evidence files/first-pass verdicts, approved requirements, tests or holdout expected outcomes cannot be overwritten by an autonomous agent.
- **INV-13:** no new SUP or MAN process workflow, capability assessment, certification or paid mandatory toolchain. Existing support infrastructure remains untouched.
- **INV-14:** Feature 006 starts OBSERVE_ONLY; transition to PILOT/ENFORCING needs explicit owner authorization and measured independent validation. No CRE/AFO auto-promotion or cross-branch merge.

## 3. Independent user stories
### US01: Assurance scope and profiles

**Independent acceptance scenario:** Given the same ASIL B requirements, selecting Enhanced increases selected verification evidence without changing ASIL or creating SUP/MAN workflows.

### US02: Normative method applicability

**Independent acceptance scenario:** Given a method `++` marked in the working index, reviewer-confirmed applicability and alternative rationale are recorded; lack of authorized normative reconciliation prohibits standards-compliance claims.

### US03: Independent verification

**Independent acceptance scenario:** Given an author-generated source and tests, evaluator rejects shared oracle provenance, forged PASS, stale revision or absent execution evidence.

### US04: Requirements and architecture assurance

**Independent acceptance scenario:** Given approved upstream/HSI, SWE.1/2 detects unsourced/contradictory requirements, missing interface allocation and unowned shared resources.

### US05: Embedded C and hardware semantics

**Independent acceptance scenario:** Given a frozen MCU manual/errata, SWE.3 rejects invalid register access, MISRA coverage omissions, API hallucinations and unbounded execution where applicable.

### US06: Effective unit testing

**Independent acceptance scenario:** Given a mutant with behavior violating a baselined requirement, independent tests detect it or survivor evidence blocks unsupported adequacy claims.

### US07: Integration and embedded verification

**Independent acceptance scenario:** Given a Renode run and an actual hardware claim, the gate refuses the HIL assertion and preserves a fidelity gap; positive integration evidence remains precisely scoped.

### US08: Assurance claims and offline package

**Independent acceptance scenario:** Given independent evidence and limitations, CAE and Release Manager include traceable verdicts and fail closed on missing obligations.

### US09: Historical retrospective audit

**Independent acceptance scenario:** Given LL r101 and HAL r102, produce a read-only report detecting unsupportable claims without altering any SHA-256 sealed package.

## 4. Functional requirements

### Foundations, scope and profiles

- **EASA-FR-001 [P0]:** Scope SHALL remain SWE.1–SWE.6 and Part 6 clause 5 general topics; no NEW SUP/MAN process workflows, products or assessments.
- **EASA-FR-002 [P0]:** The product ASIL target SHALL be independently baselined and never inferred or raised from the assurance profile.
- **EASA-FR-003 [P0]:** Support STANDARD, ENHANCED and HIGH_ASSURANCE project profiles selected by policy, independent of ASIL.
- **EASA-FR-004 [P0]:** QM work orders SHALL never be described as ASIL compliant; safety-related work orders require approved source allocation and HSI.
- **EASA-FR-005 [P0]:** ASIL B ++ working index SHALL cover tables 1–15 and distinguish clauses without a methods table.
- **EASA-FR-006 [P0]:** Normative catalog SHALL keep edition, table, row, A/B/C/D recommendation placeholders, checked status, reviewer, source provenance and footnote/application notes.
- **EASA-FR-007 [P0]:** An unverified normative catalog SHALL NOT justify an ISO 26262 compliance declaration or safety release, and normative-required evidence unresolved SHALL block an assurance READY claim.
- **EASA-FR-008 [P0]:** An applicability decision SHALL classify every selected method as APPLICABLE, NOT_APPLICABLE_WITH_RATIONALE, ALTERNATIVE_SELECTED, NOT_SUPPORTED or UNKNOWN and retain approver/provenance.
- **EASA-FR-009 [P0]:** ASIL B ++ SHALL be interpreted according to table alternatives and applicable section requirements; no blind all-methods-mandatory rule.
- **EASA-FR-010 [P0]:** Existing Automotive SPICE 4.0 SWE baseline SHALL be preserved unless separately approved; no fake CL3/CL4 achievement.
- **EASA-FR-011 [P1]:** An assurance method catalog change SHALL be baselined, reviewed and reflected in affected claims, without modifying old sealed archives.
- **EASA-FR-012 [P1]:** STANDARD SHALL preserve existing gates; ENHANCED adds independent assurance checks; HIGH_ASSURANCE adds scoped formal/deeper verification after feasibility checks.

### Independence and evidence

- **EASA-FR-013 [P0]:** Separate product author, inspection agent, oracle creator, deterministic verifier, gate authority and external reviewer identities or trust domains.
- **EASA-FR-014 [P0]:** An AI-generated PASS, test name, file presence or artifact count SHALL NEVER suffice for assurance gate PASS.
- **EASA-FR-015 [P0]:** Oracle sources SHALL be immutable approved requirements/HSI/hardware semantics and SHALL NOT be derived solely from implementation under test.
- **EASA-FR-016 [P0]:** Hidden holdout fixtures, requirements and expected outcomes SHALL remain inaccessible to candidate and code author roles.
- **EASA-FR-017 [P0]:** Each verification claim SHALL link an actual executed tool result (name/version/argv or adapter id/exit/digest/time/environment) or a controlled documented review.
- **EASA-FR-018 [P0]:** Unobserved results SHALL be UNKNOWN/NOT_RUN/NOT_APPLICABLE with rationale, never turned into zero or PASS.
- **EASA-FR-019 [P0]:** The assurance evaluator SHALL verify provenance, evidence digest, frozen revision, method applicability and independence before accepting a claim.
- **EASA-FR-020 [P0]:** Failed or incomplete checks SHALL create precise issue codes and provenance; no safety-gate bypass through time/token retry exhaustion.
- **EASA-FR-021 [P0]:** Evidence and decisions SHALL be append-only with allowed supersession; reinspection SHALL never overwrite first-pass outcomes.
- **EASA-FR-022 [P0]:** Tool confidence claims SHALL distinguish partial MISRA checks, actual tools, covered rules, exceptions, and qualified-tool evidence when applicable.
- **EASA-FR-023 [P1]:** Claims SHALL record direct counterevidence and defeaters; unsupported/contradictory claims shall not be silently closed.
- **EASA-FR-024 [P0]:** Every build and gate SHALL bind a factory revision, profile hash, method catalog hash, requirement baseline hash and target/toolchain identity.

### SWE.1 and SWE.2

- **EASA-FR-025 [P1]:** SWE.1 SHALL check unambiguous testability, completeness, internal consistency, time bounds, safe-state behavior and source-provenance for each allocated requirement.
- **EASA-FR-026 [P1]:** SWE.1 SHALL generate a machine-checkable two-way mapping between requirements, derived tests and source references.
- **EASA-FR-027 [P1]:** SWE.1 semantic AI review SHALL cite approved source excerpts; contradictory interpretations SHALL open findings rather than invent requirements.
- **EASA-FR-028 [P1]:** SWE.1 safety requirement gaps SHALL BLOCK safety-scoped packages; QM inapplicability requires scoped rationale.
- **EASA-FR-029 [P1]:** SWE.2 SHALL check architectural unit allocation, typed interfaces, cohesion/coupling, resource/IRQ ownership, scheduling and shared-resource guards.
- **EASA-FR-030 [P1]:** SWE.2 SHALL reconcile static/dynamic PlantUML views with component IDs and requirements without treating rendering success as semantic proof.
- **EASA-FR-031 [P1]:** SWE.2 SHALL include appropriate control-flow, data-flow and scheduling analyses where supported, marking estimates or unsupported tools explicitly.
- **EASA-FR-032 [P1]:** SWE.2 SHALL provide reasoned interface/architecture inspection independent from architecture author, plus deterministic structural checks.

### SWE.3 implementation and hardware

- **EASA-FR-033 [P0]:** SWE.3 SHALL enforce low complexity, constrained C constructs, initialization, naming, pointer rules and explicit type conversion via versioned policy and measured analyzers.
- **EASA-FR-034 [P0]:** SWE.3 SHALL map generated MCU accesses to baselined reference manual/errata including register access semantics, bit fields, reset and side effects.
- **EASA-FR-035 [P0]:** SWE.3 SHALL detect writes to read-only registers, undefined bits, unsupported register addresses and contradicted simulated peripheral semantics.
- **EASA-FR-036 [P1]:** SWE.3 SHALL verify reentrancy, concurrency, interrupt execution constraints, timing/timeout and state-transition behavior where applicable.
- **EASA-FR-037 [P0]:** SWE.3 SHALL output actual static-analysis, MISRA scope/rule coverage, deviation justifications and tool assurance gaps, never infer full MISRA compliance from a partial Cppcheck subset.
- **EASA-FR-038 [P1]:** SWE.3 SHALL track Flash/RAM/stack/timing budgets by host/simulator/target and by MEASURED/ESTIMATED/UNKNOWN evidence provenance.
- **EASA-FR-039 [P1]:** SWE.3 SHALL support optionally feasible formal/semiformal proof obligations (e.g., CBMC) on critical low-level operations and report bounded assumptions.
- **EASA-FR-040 [P1]:** SWE.3 SHALL reject fabricated APIs, missing interface implementations, code not corresponding to detailed design, and changes to frozen tests.

### SWE.4 and SWE.5

- **EASA-FR-041 [P0]:** SWE.4 unit tests SHALL derive independent executable expected behavior for positive, negative, boundary and interface conditions from approved requirements.
- **EASA-FR-042 [P0]:** SWE.4 SHALL prove test cases exercise the allocated API and not only harness/stub code; ambiguous trace-to-call mappings SHALL fail.
- **EASA-FR-043 [P0]:** SWE.4 SHALL compute statement and branch coverage with justified gaps; never fabricate 100% thresholds attributed to ISO.
- **EASA-FR-044 [P1]:** SWE.4 enhanced profile SHALL execute a controlled mutation campaign and report eligible/killed/surviving/invalid/equivalent mutants and evidence; thresholds are project policy.
- **EASA-FR-045 [P1]:** SWE.4 MAY apply selected MC/DC when technically feasible/risk-justified; report that MC/DC is not ++ for ASIL B.
- **EASA-FR-046 [P0]:** SWE.4 SHALL prevent agents from altering reference-oracle expected results or holdout fixtures to turn failures into passes.
- **EASA-FR-047 [P0]:** SWE.5 SHALL verify interface integration with requirements-derived, equivalence, boundary, negative, timing and resource-use cases.
- **EASA-FR-048 [P1]:** SWE.5 enhanced profile SHALL exercise and independently verify relevant fault injection and concurrency/interrupt recovery cases.
- **EASA-FR-049 [P0]:** SWE.5 SHALL distinguish host, emulator/functional simulation, Renode peripheral model, HIL and actual MCU, including fidelity limitations and expected outcomes.
- **EASA-FR-050 [P1]:** SWE.5 SHALL support back-to-back model/code comparisons when applicable and justify exclusions.
- **EASA-FR-051 [P0]:** SWE.5 SHALL verify raw tool outcomes (including Renode), ensure no test-output-only passing without intended target behavior, and open findings for incomplete fidelity.
- **EASA-FR-052 [P1]:** SWE.5 SHALL ensure integration coverage and requirement trace reports cite immutable executed artifact IDs rather than agent narratives.

### SWE.6, assurance case and release

- **EASA-FR-053 [P0]:** SWE.6 SHALL verify real requirement-observing tests against approved requirements and operational use cases, with negative/degraded/transition scenarios.
- **EASA-FR-054 [P0]:** SWE.6 SHALL distinguish genuine physical HIL/ECU network evidence from simulator results; missing required target evidence produces an honest blocker.
- **EASA-FR-055 [P1]:** SWE.6 SHALL capture test environment and observability limitations per requirement, including what behavior cannot yet be demonstrated.
- **EASA-FR-056 [P0]:** SWE.6 SHALL compute requirement coverage from real executed assertions/measurements and expose uncovered or weakly observed items.
- **EASA-FR-057 [P0]:** Every project SHALL have a structured Claim-Argument-Evidence (CAE) graph linking requirements, methods, verification, limitations and counterevidence.
- **EASA-FR-058 [P0]:** Assurance cases SHALL maintain supported/unsupported/contested state; no AI self-signed safety claim or fabricated ISO 15026-2 certification.
- **EASA-FR-059 [P0]:** Assurance Gate SHALL aggregate per-phase claims without trading coverage/quality/safety against throughput, token cost or other KPIs.
- **EASA-FR-060 [P0]:** The Release Manager SHALL include versioned method selection, applicability, oracle evidence, test/coverage/mutation results, assurance case, deficits and hashes in offline review packages.
- **EASA-FR-061 [P0]:** The factory SHALL output READY_FOR_OFFLINE_REVIEW or BLOCKED only under existing independent policy, and never label automatically ASIL_B_APPROVED.
- **EASA-FR-062 [P0]:** Safety-specific mandatory supporting documentation missing (e.g., software safety analysis or tool assurance evaluation) SHALL block safety-scoped READY; QM inapplicability may be documented.
- **EASA-FR-063 [P0]:** Changes to requirements, implementation, tools, prompts or test oracles SHALL trigger explicit impact revalidation of dependent verification and CAE nodes.
- **EASA-FR-064 [P0]:** SWE.1–SWE.6 gates SHALL retain first-pass/rework states, independent inspector identity and phase revision binding.

### Validation and rollout

- **EASA-FR-065 [P0]:** Feature 006 SHALL audit archived LL r101 and HAL r102 without mutating their workspaces/archives and report claims that cannot be substantiated from available bytes.
- **EASA-FR-066 [P0]:** Feature 006 SHALL preserve current 001–005 behavior in OBSERVE_ONLY mode and shall not silently promote CRE/AFO authorization.
- **EASA-FR-067 [P0]:** Deployment SHALL progress OBSERVE_ONLY -> PILOT -> ENFORCING based on evidence, explicit authorization and independently verified non-regression.
- **EASA-FR-068 [P0]:** A non-computable metric or absent hardware/tool dependency SHALL show a blocked or inapplicable reason rather than synthetic passing evidence.
- **EASA-FR-069 [P0]:** Negative tests SHALL prove that forged PASS, stale hashes, poisoned lessons and correlated oracle contamination are rejected.
- **EASA-FR-070 [P0]:** All 47 ASIL B ++ working-index entries SHALL have mapping to methods/evidence applicability and a baseline verification process.
- **EASA-FR-071 [P0]:** Project compliance SHALL not be claimed from an internal checklist or ASPICE gate PASS; published result is bounded assurance evidence.
- **EASA-FR-072 [P0]:** Existing repo safety constitution, credentials, historical baselines and release policies SHALL remain protected from autonomous edits.

## 5. Entities and interfaces

- **AssuranceProfile** (scope + selected methods + versioned quality thresholds), separate from **ProductSafetyScope** (QM/ASIL target, source allocation and HSI).
- **NormMethod / ApplicabilityDecision** (table+row, recommendations, source authority, alternatives and reviewer evidence).
- **OracleProvenance / VerificationExecution** (independent origin, tool, revision, command, actual observations and digests).
- **CoverageEvidence / MutationCampaign / EnvironmentFidelity** (measured scope; honest limits).
- **AssuranceClaim / AssuranceCase** (Claim-Argument-Evidence graph with counterevidence and provenance).
- **AssuranceGateDecision** (independent hard-gate result; missing/invalid evidence blocks).
- **AssuranceHandover** (release attachments + gaps; no safety approval).

Normative and typed contracts are under `contracts/`. Source proposals under `factory/python/forge_factory/assurance/` shall extend, not duplicate, `inspection/`, `reliability/`, `mcp/`, `release/` or dashboard.

## 6. Success criteria (engineering, not product-certification)

1. Source catalog contains exactly 47 provisional ASIL B `++` index entries across Tables 1–15, noting no Table 12 `++`, and supports edition/provenance and reconciled selections.
2. All 72 EASA-FRs have task and acceptance-test coverage with verifiable results or explicit BLOCKED/NOT_RUN.
3. False PASS injection, reference-only fake tests, frozen-holdout tampering, source/hardware fidelity mislabelling and stale SHA tests are rejected by deterministic gates.
4. Read-only LL r101/HAL r102 audits identify claim- and evidence-level gaps without changing archived outputs.
5. At least one **real** full SWE.1–SWE.6 pilot attempts passes the enhanced gates only if actual requirements, tool, environment and document evidence supports that status; otherwise the result must remain BLOCKED.
6. Existing 001–005 tests and policies remain valid. Rollout requires measured false positive/negative analysis, independent review and explicit authorization.
7. No release can be called ASIL approved, CL3, ISO certified or physically validated without external approval/evidence.

## 7. Explicit exclusions

- **NO SUP.1/SUP.8/SUP.9/SUP.10/MAN.3/MAN.5/MAN.6 workflows.** Reuse existing incident, change, trace, quality and metric services as utilities only.
- No change to HARA/safety-goal ASIL, system safety engineering, technical safety concept or signed human decisions.
- No claim of 100% correctness, no generic 100% test coverage requirement, no deployment to MCU without separate authorization.
- No procurement, copying or redistribution of copyrighted ISO/MISRA norms or a licensed analyzer within the repository.

## 8. Dependencies and limitations

- Feature 004 CRE remains OBSERVE_ONLY until separately authorized and proven; Feature 005 AFO is only specified at this branch baseline.
- `evidence/cre/slo/`, user-provided report of 27 DeepSeek attempts (12/27 passing all SWE process gates, 10/27 lacking two owner-deferred safety documents) provides an *audit target*, not a qualified product baseline.
- Import actual LL r101/HAL r102 archive bytes from authorized data volume only; a summary report alone cannot prove behavioral correctness.
- ISO 26262-6:2018 remains ISO-published; current project must obtain authorized copy to baseline exact row classification and applicability; a draft edition must not be silently substituted.
- See `research.md` for primary/secondary source links, normative interpretation and project-defined supplemental practices.
