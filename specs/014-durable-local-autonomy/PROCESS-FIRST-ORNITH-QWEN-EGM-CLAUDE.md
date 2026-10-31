# Forge-C — Process-First Factory: Ornith Author, Qwen Inspector, EGM with Claude

**Claude Cloud implementation plan and EGM spec-driven engineering handoff**  
**Date:** 2026-10-31  
**Status:** PROPOSED — NOT IMPLEMENTED OR DEPLOYED BY THIS DOCUMENT  
**Repository:** `jnsagai/forge-c`  
**Integration branch:** `feat/014-durable-local-autonomy` (stacked PR #42; verify current state before changes)  
**Repository path:** `specs/014-durable-local-autonomy/PROCESS-FIRST-ORNITH-QWEN-EGM-CLAUDE.md`  
**Implementation environment:** Claude Code / cloud development environment, with Google's Elephant–Goldfish Model (EGM) SDD plugin when genuinely available; isolated checkout/PR and deterministic CI.  
**Inference/verification environment:** the separately operated Omniverse2 RTX 6000 Ada 48 GB machine. **Cloud implementation does not authorize cloud inference or live remote deployment.**

> **Decision:** Mature Forge-C **one Automotive SPICE software process at a time** across **multiple embedded-C projects**, with independent, frozen reference criteria and measured improvement. Maintain a **thin end-to-end smoke path** after every process increment to prevent six isolated document generators from replacing a functioning factory. Set **Ornith-1.5-35B-A3B-GGUF Q8_0** as the *preferred experimental SWE.1 author*, and **Qwen3.8-27B Q8** as the *read-only semantic inspector*. Keep Qwen's measured authoring profile as baseline/rollback. Use **real EGM Elephant/Goldfish design review in Claude** before code changes, not an EGM runtime. Optimize for functional product yield and process artifact quality, not the count of green gates or generated pages.

---

## 0. Non-negotiable evidence and history

Read before implementation:

1. `docs/reports/ASTRA-OVERNIGHT-REVIEW-20261030-31.md` on `main` (October 30–31); use pinned evidence revision `dce7ad273e6cb31d6bcca1060f1e4e54eadd2acf` for its detailed evidence.
2. `specs/014-durable-local-autonomy/ASTRA-REVIEW-20261028-30.md`.
3. `specs/014-durable-local-autonomy/DELIVERY-FIRST-E2E.md` and `DELIVERY-FIRST-IMPLEMENTATION.md` on the feature branch.
4. `IMPLEMENTATION-INCREMENTAL-E2E.md`, `spec.md`, `plan.md`, `tasks.md`, `acceptance-tests.md`, `GENERIC-EMBEDDED-C.md`, `HANDOVER-CODEX.md` and `.specify/memory/constitution.md`.
5. Actual implementation files and existing tests (not assumptions based on a report): `factory/python/forge_factory/{delivery_first.py,workflow/builder.py,llm_gateway.py,lrtx/profile.py,inspection/gate.py,afo/{scheduler.py,conductor.py,runtime.py,product_role_trial.py},knowledge/experience.py}`, existing release/finalizer modules, YAML profiles, workorder tools, and the Feature 015 ST benchmark.

### Frozen known baseline

- The **fresh** Qwen Delivery-First cohort `06/07/08` was **2/3** terminal *scoped functional* milestone passes; `08` was operator-stopped, **not** replaced or promoted.
- Fresh `06` passed independent initial and final verification and packaged available artifacts with **16 strict release gaps**; fresh `07` likewise passed the scoped functional milestone, but its SWE.5 inspection timed out and SWE.6 lacked an executed Robot verification/report (**35 gaps**). No fully qualified LL/HAL product was demonstrated.
- The two-function scope was `LL_CRC_Write_IDR` and `LL_CRC_Read_IDR`. Independent controls included 630 host assertions and 351 simulated target assertions, host/target compilation and simulated resource/call-cost checks. Do not generalize to hardware WCET or other peripherals.
- Four generic fixes were **not active in the frozen 06–08 producer**: GPU contention backoff (`d2e083e3`), MCP optional-container authorization normalization (`50a4813d`, `3788ace6`), bounded gateway admission after prior-request drain (`60619be0`), and correct declared target API guidance (`d0090099`). Their fixture regressions passed; native end-to-end effectiveness remains **NOT_RUN** as of the report cutoff.
- Feature 014 main ledger remained `30/58`; Delivery-First `DF-T001..009` were scoped complete, `DF-T010` incomplete, `DF-T011/012` deferred. Preserve these records. Historical 1470 requests, 2583 tools, and ~467M *conservatively reserved/charged* tokens are **not measured generated tokens**; historical usage uncertainty remains.
- Previously attempted 64K context for the entire legacy workflow failed complete serialized-request sizing. Do not impose 64K universally or claim that model-advertised 262K context is automatically usable at Q8 on a 48 GB GPU.
- The prior overnight grant expired at `2026-10-31T07:57:59Z`; its original mission, terminal states, expenditures and SHA identities are immutable. A new bounded live campaign needs **new explicit authorization** and a new prospective experiment identity, with history cross-linked, not rewritten or reset.

---

## 1. Why change the sequence?

The overnight run demonstrated that local Qwen can generate and independently verify a *small functional C slice*. It did **not** demonstrate an efficient or reliable full ASPICE-inspired SWE.1–6 engineering journey. Running the full pipeline for every model or prompt improvement is expensive, entangles failure causes, and delays useful feedback.

**New development strategy:** isolate **one process capability**, test it on a **diverse driver corpus**, improve that process to a declared **USABLE** threshold, then connect it to the next process. Preserve a minimal, truthful end-to-end smoke test at each increment, using already-known small fixtures or sealed, verified handoff artifacts; the smoke test does not count as qualification of unimplemented phases.

Process order follows Automotive SPICE 4.0 terms:

| Wave | Process | Primary candidate work products | First downstream contract |
|---|---|---|---|
| P1 | **SWE.1** Software Requirements Analysis | Source-grounded software requirements, verification criteria, interface/behavior constraints, traceability and unresolved questions | SWE.2 can import requirements, resolve IDs and scope, and identify ambiguities deterministically |
| P2 | **SWE.2** Software Architectural Design | Components, interfaces, allocation, dynamics/dependencies, design decisions, trace to requirements | SWE.3 can identify owned units and implementable interfaces |
| P3 | **SWE.3** Software Detailed Design and Unit Construction | Detailed unit design and real authored C with compiler-visible interfaces | SWE.4 can build and test the units; baseline code provenance remains pinned |
| P4 | **SWE.4** Software Unit Verification | Unit cases, coverage/trace, executed results and defects | Unit outputs and evidence are usable for integration |
| P5 | **SWE.5** Software Component Verification and Integration Verification | Integration strategy, interface checks, integration execution and outcomes | Software behaves correctly at declared component boundaries |
| P6 | **SWE.6** Software Verification | Software verification cases/results and trace to software requirements | Scoped terminal evidence package can be evaluated independently |

This is a **development sequence**, not a claim that all processes must execute in a rigid serial order in production. `SWE.3` already includes unit construction; `SWE.4`–`SWE.6` form a verification structure and should retain appropriate upstream trace links. **Software requirements need a declared source of stakeholder/system/software obligations**, not merely a hardware reference manual. When that upstream input is absent, label the work a *QM engineering-contract exercise / ASPICE-inspired artifact*, not assessed Automotive SPICE compliance.

### Two-dimensional maturity

- **Horizontal:** SWE.1 on CRC, GPIO, USART, SPI, TIM, IWDG and later an unseen non-register-oriented embedded-C use case.
- **Vertical:** a stable SWE.1 package can be read by SWE.2; its architecture can be handed to SWE.3; one tiny integration smoke case remains runnable at each milestone.

**Do not wait for perfect documents. Do not allow green documents to substitute for useful working software.**

---

## 2. Architecture: one existing engine, two model roles, independent acceptance

```text
       OWNER SOFTWARE CONTRACT + FROZEN AUTHORITATIVE SOURCES
                              |
                    Existing AFO workorder
                              |
                 process_under_test = SWE.1
                              |
               GPU lease + single-model scheduler
                              |
                ORNITH Q8 AUTHOR (batch)
                              |
              Requirements candidate + hash
                              |
               Deterministic validation
                              |
               QWEN Q8 INSPECTOR (batch)
                              |
               Structured, sourced findings
                              |
              ORNITH one bounded rework pass
                              |
        Independent human/frozen engineering oracle
                              |
          SWE.1 HANDOFF + GAPS + PROCESS STATUS
                 |                       |
          SWE.2 minimal importer      Tiny E2E smoke
```

A single RTX 6000 Ada 48-GB GPU cannot hold both full Q8 models resident with useful KV caches. Batch all Ornith authoring work, prove request/native/lease quiescence, unload; batch Qwen read-only inspections, prove quiescence, unload; optionally reload Ornith once for correction. No model switch on a mere Fabro terminal business status. Measure load/swap overhead because it can erase MoE decode advantages.

Extend existing AFO, Fabro, model gateway, workorder, inspection, release, knowledge and Delivery-First mechanisms. **No second scheduler, release authority, database, autonomous model router or EGM runtime.** EGM is a Claude *development review method*, not another production worker.

### Architectural invariants

1. `process_under_test` is explicit and immutable within one experiment; an artifact judged by the process bench is not automatically a production-released deliverable.
2. A process-specific output **must be consumable** by the next stage through a versioned, deterministic handoff schema; the importing process may reject ambiguity.
3. Mandatory original obligations remain in a frozen coverage inventory, including owner-stated exceptions; never hide missing functionality by shrinking scope or replacing source data.
4. Every claim is linked to actual author bytes, model/runtime/configuration/input hashes and frozen external oracle results.
5. Never convert failed/absent tests, wrong tool returns, insufficient source evidence, unresolved gate findings, or UNKNOWN into PASS.
6. No same-model inspector opinion substitutes for source evidence, executable verification, or independently specified negative cases.
7. Stop, revoke, network-isolation, single-inference ownership, verified quiescence, storage integrity, and strict production release remain protected. A development convenience mode may reduce administrative friction, **not** silently bypass those boundaries.
8. A failed or interrupted process job must have a durable terminal/factual disposition before being considered fully reconciled.
9. A quality finding is usually **advisory for development continuation** but may still block functional verification, handoff, or strict release according to its actual impact.
10. Any process improvement or model switch is prospective: keep a separate frozen baseline and independent held-out benchmark; never rewrite prior 2/3 history.

---

## 3. Process capability profile and maturity gates

Use one opt-in `QM_PROCESS_LAB` development profile, initially for `SWE.1`. Retain the existing `QM_DELIVERY_FIRST_DEMO` path and strict policy untouched. Avoid claiming conformance from shared naming.

```
process_lab:
  schema: forge-c/process-lab/1
  purpose: QM
  process_under_test: SWE.1
  experiment_id: <immutable unique id>
  model_profile: <explicit Qwen OR Ornith profile>
  work_order_manifest_hash: <sha256>
  source_inventory_ref: <hash-bound manifest>
  frozen_acceptance_oracle_ref: <hash-bound independent oracle>
  output_contract: forge-c/process-handoff/1
  max_semantic_rework: 2
  quality_policy: advisory_with_blocking_integrity
  strict_release_unchanged: true
```

Illustrative schema only; Codex must map it to existing project contracts rather than blindly injecting unsupported YAML fields.

### Maturity levels

- **EXPERIMENTAL:** complete attempt and complete traceable gaps; usable output not yet demonstrated.
- **USABLE:** demonstrated source-grounded output on a preregistered multi-driver corpus; handoff interface works; all critical obligations are handled or openly blocked; remaining issues recorded. Eligible for subsequent process-development work, **not** strict release.
- **QUALIFIED:** fresh held-out repeatability, independent judgments and process/role-specific criteria passed under a documented qualification plan. Not a synonym for Automotive SPICE assessment/certification.

**Proposed preliminary SWE.1 USABLE threshold** (engineering proposal, *not* an ASPICE-mandated numerical criterion):

- On at least **five declared driver examples** with at least one unseen case, no silent omission of **critical** functional/behavioral obligations; explicitly unresolved critical obligations make a candidate **NOT_USABLE**.
- At least **90% independently scored noncritical obligation coverage** across the eligible corpus, with per-driver results visible (no aggregate hiding of a failing driver).
- **100% of emitted source references resolvable** to immutable supplied inputs or explicitly marked as unverified assumptions (assumptions cannot masquerade as sourced requirements).
- At least **90% of requirements judgeable** by objective verification criteria, reviewed against a pre-registered oracle; no false claim of requirements approval.
- Output validates against the schema, can be imported by a minimal SWE.2 consumer, and preserves missing/contradictory items.
- Median time/model calls and repair cycles reported; no mandatory arbitrary wall-time threshold for acceptance until performance distribution is measured.

These targets are adjustable **only for a future preregistered cohort**; not during an active comparison to manufacture a pass. Use severity-weighted evidence, expert review for semantic ambiguity, and deterministic checks for structure/identity/traceability. A model cannot be its own sole oracle.

### Process handoff schema (minimum)

Record `schema/version`, project/target profile, experiment/run, process, source/model/runtime/agent/template hashes, frozen scope/obligation inventory, generated artifact list with sha256, requirements or design IDs and graph edges, provenance, independent evaluator results, PASS/FAIL/UNKNOWN by check, unresolved critical/noncritical gaps, downstream-use constraints, `process_maturity` and strict release status (always separate). Never store sensitive vendor source text or model private reasoning in public evidence.

---

## 4. SWE.1-first benchmark design

### Candidate driver corpus

| Case | Characteristic | Requirements failure modes |
|---|---|---|
| CRC | Small MMIO / data register | read/write semantics, caller preconditions, word width |
| GPIO | Modes / pin configuration | reset/defaults, ownership, interactions, invalid configurations |
| USART | State / interrupts / transfer | error conditions, concurrent state, sequencing and performance |
| SPI | Transactions / inter-device interface | timing and ordering, framing, controller/peripheral roles |
| TIM | Counting, capture/compare | bounds, transitions, timing assumptions and clocks |
| IWDG | Watchdog startup/service | reset behavior, timing window and required preconditions |
| Holdout example | Different MCU/manual or non-peripheral embedded-C component | prevent memorizing fixed RM0486 conventions and output templates |

Use available real or explicitly synthetic/test-permitted inputs, with lawful source access and pinned versions. The initial corpus may use `examples/0014*`, Feature 015 reference-driver scopes, and existing IWDG/CRC fixtures. Do **not** equate frozen vendor code or previously accepted requirements with fresh AI authorship; designate any reused material as *upstream source*, *reference answer* (oracle-only) or *prior result*. Do not expose oracle answers to the author prompt.

### SWE.1 evaluation dimensions

1. **Obligation recall:** every essential behavior, caller contract, interface, state and error condition in the frozen oracle is represented or explicitly identified as missing.
2. **Source correctness:** each hardware/API claim has real source support, not invented requirements; differentiate sourced facts from owner assumptions and inferred suggestions.
3. **Atomicity and testability:** requirements are unambiguous, individually verifiable, with meaningful acceptance criteria; avoid exploding trivial details into hundreds of artificial requirements.
4. **Internal consistency:** no contradictory reset, sequencing, data-width or failure semantics.
5. **Traceability:** stable requirement IDs map to the correct upstream obligations and later can map to SWE.2 design elements.
6. **Efficiency:** generation latency, output tokens, tool calls, reviewer effort, prompts and context consumed; a document with 637 requirements is not inherently better than one with 25 correctly scoped requirements.
7. **Handoff quality:** independent minimal SWE.2 importer can ingest identifiers/constraints and produce a deterministic report of usable/ambiguous/missing information.

### Evaluation process

- Freeze corpus, source versions, corpus split, answer inventory, negative examples, rubrics and scoring scripts before live inference. Ensure independent subject-matter review of the oracle (including error semantics and system constraints). Keep fresh held-out examples for promotion decisions.
- Generate one process candidate; run deterministic schema and provenance checks; request at most two bounded content revisions **on actionable deficiencies**, not dozens of rewording loops.
- Review semantic obligations independently (human or qualified independent reviewer). Log disagreements as UNKNOWN; don't auto-accept model votes.
- Produce a signed/hash-bound `SWE1_PROCESS_HANDOFF` candidate with gaps and a machine-readable comparison report.
- Re-run the old tiny CRC functional smoke with frozen known-good process inputs to ensure no integration regression. Its outcome is a smoke result, not a newly AI-authored SWE.1 qualification result.

**Important:** ASPICE SWE.1 is software requirements analysis. Without declared upstream system/software stakeholder requirements, do not represent an RM-only driver exercise as a full ASPICE v4.0-compliant process.

---

## 5. Model roles: Ornith author, Qwen inspector, deterministic judge

### 5.1 Experimental model assignment

| Role | Choice | Boundary |
|---|---|---|
| SWE.1 author (new default *only in opt-in Process Lab*) | **Ornith-1.5-35B-A3B-GGUF Q8_0** | Produce requirements with source traces, stable IDs, objective verification criteria; maximum one consolidated rework |
| SWE.1 inspector | **Qwen3.8-27B Q8** | Read-only, bounded batches, structured evidence-grounded findings; cannot write candidate/policy/oracle |
| Final SWE.1 usability evaluation | **Independent frozen oracle + deterministic validators**, human adjudication when semantic ambiguity persists | Both models can be wrong; model agreement is not a correctness proof |
| Historical reference/fallback author | Qwen3.8 Q8 | Existing previously measured author profile remains intact; no unearned Ornith promotion |
| Later SWE.2–6 roles | Undecided | New process- and role-specific benchmarks are required |

This is a **proposed experimental baseline**, not evidence that Ornith is better. Compare the complete configuration **Ornith author + Qwen inspector** against **Qwen author + Qwen inspector**, with the exact same independent oracle. Optionally run Ornith author without inspector to isolate inspection benefit. Measure inspector false positives, missed seeded defects, time and repair effect.

### 5.2 Exact model and runtime qualification

- Pin `AtomicChat/Ornith-1.5-35B-A3B-GGUF` exact `Ornith-1.5-35B-A3B-Q8_0.gguf` (~36.9 GB); verify actual SHA256, MIT license, prompt/chat template, backend binary and loaded digest. Other GGUF builds may differ: **no interchangeable model IDs**.
- Use a new **versioned experimental** local profile; keep installed Qwen Q8/f16/MTP3 profile/digest unchanged. Do not copy Qwen's MTP, sampling, tokenization or thinking controls to Ornith without native tests.
- Use a pinned llama.cpp/OpenAI-compatible server as an initial option, **not** an assumed working tool adapter. Validate tool-call JSON/arguments, `tools`/`tool_choice`, multi-turn tool results, malformed responses, contract JSON, reasoning redaction, context measurement, 429/timeouts, cancellation, admission and request usage with actual SDK/gateway protocol fixtures.
- Start Ornith at 32K or 64K **only for independently complete small SWE.1 tasks**, subject to real memory/token allocation. Earlier full Qwen workflow's 64K hypothesis failed; never silently truncate mandatory data. Increase context only after measured success on 48 GB.
- Download/caching before network isolation requires separately approved preparation. Actual **factory inference stays offline on Omniverse2**; Claude Cloud performs source implementation and deterministic CI, not model execution.
- Single GPU means **one resident model, one admitted inference request**. Model replacement needs a fenced, logged, explicitly authorized, verified-quiescent handoff; stop, revoke, unknown provider outcomes and held native leases refuse admission.
- No new autonomous multi-model routing agent. Use the existing AFO queue and versioned manifests to schedule **role batches**: Ornith author -> Qwen inspector -> at most one Ornith rework.

### 5.3 Inspector contract, cost ceiling and failure semantics

Qwen should inspect **small read-only requirement batches**, not run a repository-wide maintenance agent. Return typed `requirement_id`, `category`, `severity`, `source_ref`, `evidence_span`, `finding`, `recommended_verification`, `uncertainty`. A timeout, tool error, invalid response or uninspected obligation is **NOT_INSPECTED**, never PASS. Bounded tool, time and output limits are configurable and measured. The overnight SWE.5 900-second/175-tool-call failure is evidence that unrestricted inspection is too expensive; investigate it separately rather than copying its budgets to SWE.1.

Author receives only actionable consolidated findings and authoritative source. One correction round, then immutable candidate plus an honest gap register. Critical missing source-backed obligations block `PROCESS_USABLE` and unsafe dependent handoffs; noncritical style findings do not force infinite retries. Strict release rules remain unchanged.

### 5.4 Matched evaluation and model promotion

Preregister a minimum of five fresh comparison trials per configuration across diverse drivers plus one unseen holdout. This is a small engineering sample, not statistical proof. Evaluate *initial* author quality separately from *post-inspector/rework* quality. Same-model inspection in the Qwen reference arm is correlated and must be disclosed.

Suggested future promotion rule: Ornith+Qwen becomes the preferred **measured** SWE.1 configuration only when its critical obligation and tool-protocol correctness are not worse, and median full time-to-accepted-handoff is at least **25% lower**, counting model unload/load, inspection, rework and GPU waiting. Do not promote merely from decode tokens/sec. If not demonstrated, keep Qwen author fallback and report UNKNOWN/FAIL honestly.

---

## 6. Fix demonstrated orchestration defects before multi-model campaigns

**Priority 0, same existing engine and authority:**

1. **Sole GPU contention:** integrate/test the tested 15-second reeligibility correction (`d2e083e3`) on top of current source; mixed dependency failures retain bounded exponential backoff. Do not release leases based merely on business-terminal status.
2. **MCP defaults/authorization:** integrate/test builtin optional-container normalization (`50a4813d`, `3788ace6`) for actual registered tool calls, including default `defines=[]` / `evidence_refs=[]`, negative tamper cases and one-use tickets. Native preflight must perform a real authorized tool call.
3. **Timeout/drain cascade:** integrate/test bounded Admission queue (`60619be0`) *before* durable model request reservation and recheck permissions after wait. Preserve one inference and stop/revocation. Also **investigate the original 900-second SWE.5 inspection with 175 tool calls** rather than assuming queueing fixes its cause.
4. **Declared target API:** integrate/test corrected target-author guidance (`d0090099`) respecting the target adapter, not hardcoded legacy register arrays.
5. **Terminal lifecycle:** after operator-stop or timeout, let existing Conductor/reconciliation deterministically transition native/order to a truthful terminal result and emit every factual JOB/phase learning disposition, idempotently and without a model call. Preserve no-generation-after-stop proof. Tests should cover interrupted SWE.3, finalizer races, SQLite contention and at-least-once replay.

Validate composed source and no regression in existing strict/Feature 015 workflows. None of these fixes counts as a newly successful production run until an authorized **native** trial validates it. An isolated deployment is not automatically implied by merging code.

---

## 7. Two loops, one factory: production and process improvement

**Fast loop:** scoped contract → Ornith author → deterministic artifact validator → Qwen bounded read-only inspection → at most one Ornith correction → independent oracle → *sealed process candidate*. For SWE.3, actual compiler/tests are required.

**Slow loop:** inspect source completeness, traceability, process quality and adverse cases → record gaps → improve prompts/fixtures/lesson candidates → rerun frozen held-out process benchmarks → progressively qualify process capability.

A successful SWE.1 experiment may hand its accepted *development* requirements to SWE.2. A functional SWE.3 candidate may be packaged before later documentation finishes, with `FUNCTIONAL_CANDIDATE_READY` and `ENGINEERING_EVIDENCE_INCOMPLETE` separately visible. The normal release gate remains authoritative.

Use existing AFO durable queue and lesson store. A process has a clear boundary and next-process handoff, but not a second scheduling database. Always capture skipped/failed trials in denominators. Factual experience capture is separate from validated transferable learning; no auto-promotion or unproven fine-tuning.

---

## 8. Google EGM SDD — mandatory Claude design/review workflow

**Use Google's real Elephant–Goldfish Model (EGM) in the Claude development environment.** The **Elephant** is Claude with Forge-C's existing architectural context; **Goldfish** reviewers are genuinely fresh-context agents criticizing the design. EGM does **not** run inside the Forge-C production runtime or become another quality authority for generated requirements.

### 8.1 Claude Code setup and capability preflight

Official Claude Code plugin installation:

```bash
claude plugin marketplace add google/elephant-goldfish-model
claude plugin install egm@egm
claude plugin enable egm@egm
```

Start a new Claude session after installation. Use the installed plugin's actual `docs/claude.md`; current official guidance recommends **Claude Code 2.1.271+** for `omitClaudeMd` Goldfish context-isolation support. Install the full plugin (personas and standards, not just skills). In Claude the command forms are `/egm:egm-draft` and `/egm:egm-review` (not arbitrary made-up slash commands). Grant the actual installed plugin's persona/standard directories **read-only** access as required, not blanket write permissions. The real review requires native fresh `Agent` subagents with read-only tools/context isolation. A cloud Claude job without plugin/subagents cannot pretend the parent self-review is independent Goldfish.

If capability is absent, record `EGM_REVIEW_NOT_RUN` with exact blocker and do **not** falsely mark design reviewed. Source inventory and deterministic unrelated regressions may proceed; final EGM design approval must await a real supported environment.

### 8.2 Minimal bounded EGM process

1. **Elephant reads actual code** and this specification, Feature 014/015, runtime status from available evidence and frozen overnight reports. No open-ended `egm-brainstorm` needed: the owner has already selected SWE.1-first, Ornith author, Qwen inspector.
2. **Draft** with `/egm:egm-draft`: create `docs/designs/forge-c-process-first-ornith-qwen.md` (or installed skill's actual workspace path) with component change map, state transition for GPU handoff, model protocol interfaces, SWE.1 artifact schema/oracle, tests and rollback. Cross-reference Feature 014 Spec-Kit as the source of truth.
3. **Review** via `/egm:egm-review docs/designs/forge-c-process-first-ornith-qwen.md` and real isolated Goldfish reviewer personas/standards. Require architecture/codebase fit, E2E feasibility, and authority/provenance/stop boundaries. Keep findings evidence-backed and severity-ranked.
4. **Resolve** material blockers with the installed EGM `egm-resolve` procedure in the Elephant context. Preserve deferred findings with rationale; at most **one full review/resolution cycle** before first SWE.1 implementation, and only a targeted re-review for a changed blocking item. No "perfect-spec" loop.
5. **Implement** in small tested increments; design review never replaces compilation, protocol fixtures, independent oracle or real native GPU evidence.
6. **Drift** (optional after real implementation): run installed `egm-drift-report` if available; report NOT_RUN when absent. Commit design and redacted reviewer outputs, excluding secrets, proprietary manuals, raw reasoning and private prompts.

**EGM design gate:** Block on incorrect state machine, invalid 48-GB handoff, accidental old-release weakening, hidden oracle leakage, fake acceptance, unverifiable source inputs or non-reproducible tool calls. Defer style, speculative scale and unrelated architecture. **No EGM runtime integration**.

## 9. Claude Cloud work packages (dependency order)

| ID | Priority | Deliverable | Acceptance |
|---|---|---|---|
| PF-EGM-001 | P0 | EGM preflight, draft, real Goldfish review, bounded triage | Design/review evidence or honest NOT_RUN blocker; no simulated reviewers |
| PF-ENG-002 | P0 | Inventory existing branch/source/roles/overnight evidence | Installed-vs-feature-vs-main evidence clearly separated; no stale source assumptions |
| PF-ENG-003 | P0 | Integrate four prepared overnight fixes using existing components | Failed-before/passing regression; strict graph and Feature 015 unaffected |
| PF-ENG-004 | P0 | Deterministic operator-stop/finalization/learning disposition reconciliation | Replayed interrupted SWE.3, no model calls, eventual terminal facts |
| PF-SWE1-005 | P0 | `QM_PROCESS_LAB` SWE.1-only intake and versioned handoff | Hash-bound explicit scope; negative schema/provenance checks |
| PF-SWE1-006 | P0 | Frozen CRC/GPIO/USART/SPI/TIM/IWDG SWE.1 corpus + held-out example and oracle | Source/obligation/criterion inventory, no oracle leakage |
| PF-MODEL-007 | P0 | Ornith Q8 experimental author profile + Qwen bounded read-only inspector | Template/tool/SDK/identity/timeout fixtures; Qwen author fallback untouched |
| PF-MODEL-008 | P0 | Existing AFO-controlled one-GPU batch handoff and rollback | Quiescence, stop, held-lease, failed load and unknown provider tests |
| PF-SWE1-009 | P0 | SWE.1 author -> validate -> inspect -> one rework -> independent acceptance | Genuine artifacts and full gaps, no fake PASS/automatic release |
| PF-SWE1-010 | P0 | Versioned minimal SWE.2 importer and CRC vertical smoke | Positive/negative handoff and inherited functional regression |
| PF-BENCH-011 | P1 | Matched configuration A/B reporter incl. inspector value and swap cost | All failed/interrupted attempts retained; per-driver blind scores |
| PF-OPS-012 | P1 | Omniverse2 runbook + rollback for owner-authorized native experiments | Cloud CI labels native NOT_RUN; no remote activation |
| PF-QUAL-013 | P1 | SWE.1 USABLE experimental decision on held-out cases | No critical omission, source-based acceptance, real oracle evidence |
| PF-NEXT-014 | Later | SWE.2 then SWE.3–6 incrementally, process by process | Each has independent process oracle and vertical handoff |
| PF-NEXT-015 | Later | Broader CRC LL, provisional LL→HAL, full reliability/learning campaigns | Strict release kept separate; only actual evidence closes DA tasks |

Begin with **PF-EGM-001 and the smallest code path to one real SWE.1 package**; do not wait for every later task or a complete 58-task Feature 014 ledger to deliver value. EGM review must not balloon into a new implementation program.

### Required negative acceptance scenarios

- **AT01 EGM:** Real fresh-context Goldfish is verifiable; if unavailable review is `EGM_REVIEW_NOT_RUN`.
- **AT02 Legacy:** strict graphs, Feature 015 and existing Delivery-First results remain unchanged.
- **AT03 Identity:** role/model/digest/profile/source change invalidates frozen cached outputs.
- **AT04 GPU:** Qwen active/held lease blocks Ornith loading and second inference; verified quiescence permits an authorized switch.
- **AT05 Stop:** stop/revoke during model switch, provider-drain and SWE.1 inspection prevents new inference and preserves history.
- **AT06 MCP:** omitted optional `defines=[]`/`evidence_refs=[]` validates actual ticket and nondefault tampering rejects.
- **AT07 Gateway:** draining request waits boundedly rather than spamming 429; unknown outcome remains blocked.
- **AT08 Scheduler:** sole GPU-contention cooldown clears quickly after true release; mixed dependency failures stay bounded.
- **AT09 Inspector:** Qwen read-only role cannot alter author bytes/manuals/oracle; timeout is NOT_INSPECTED, not PASS.
- **AT10 Oracle:** critical omission or fabricated source remains NOT_USABLE even if Qwen says PASS.
- **AT11 Rework:** exactly one bounded correction, frozen prior hash remains auditable and inspection is invalidated if candidate changes.
- **AT12 Handoff:** SWE.2 importer handles valid trace IDs and rejects duplicates/missing contradictory IDs.
- **AT13 Fairness:** model comparison includes inspection and model-switch costs, source/role mismatches and every incomplete trial.
- **AT14 History:** original fresh 2/3 overnight cohort, blocked packages, expired authority and token uncertainty never overwritten.
- **AT15 Cloud:** CI without GPU/private inputs reports NATIVE_NOT_RUN; synthetic provider fixtures never called a local model.
- **AT16 Privacy:** source-controlled artifacts contain no private manual, credentials, hidden reasoning or raw private prompts.
- **AT17 Learning:** operator stop produces final factual job/phase disposition idempotently without inventing a qualified lesson.

## 10. Native benchmark protocol, metrics and promotion

Cloud produces source/tests/design/EGM evidence only. Real Qwen/Ornith inference requires separately authorized finite Omniverse2 execution, offline network containment and actual model/runtime/provenance verification. Do not reuse the expired 30–31 October grant or reset old mission counters. Only a deliberate handoff after quiescence can replace the GPU-resident Qwen model.

Pre-register corpus, oracle and model profiles, then compare configuration A (Ornith author + Qwen inspector) with B (Qwen author + Qwen inspector). Use at least five fresh runs per configuration with multiple drivers and a withheld example. Optional diagnostic Ornith author without inspector measures the incremental contribution of Qwen criticism. Preserve every incomplete/cancelled result. Native measurements: independent obligation accuracy, verifiability, unsupported claims, inspector precision/recall on seeded defects, rework effect, schema/tool success, load/swap time, p50/p95 accepted-handoff latency, total reported tokens vs reservations, total tool calls, queue waits, VRAM peak, role-specific throughput and strict-release gaps.

**Preliminary USABLE criterion:** no missing critical obligations; at least 90% noncritical obligation coverage; resolvable support for accepted technical claims; 90% verifiable requirements; verified SWE.2 importer with negative tests. Thresholds are proposed owner engineering targets, not Automotive SPICE compliance. No model promotion without real evidence.

**Explicit stop/go:** successful isolated SWE.1 on multiple drivers allows SWE.2 engineering work even if full SWE.1–6 release, strict 3/3 repeatability, long-duration campaigns, continuous learning and generic LL/HAL qualification remain unproven. Never label such development packages released or safety-qualified.

## 11. Claude Cloud implementation directive

> Work in `jnsagai/forge-c` from the current `feat/014-durable-local-autonomy` branch in an isolated implementation worktree. Follow `specs/014-durable-local-autonomy/PROCESS-FIRST-ORNITH-QWEN-EGM-CLAUDE.md`. **First run Google's official EGM SDD workflow in supported Claude Code**: install/enable the full plugin, create a short design with `egm-draft`, dispatch genuine fresh-context Goldfish design reviewers via `egm-review`, resolve important findings once, then implement. Never claim a simulated parent-context review is EGM. Make **Ornith Q8 the preferred experimental SWE.1 author and Qwen3.8 Q8 the bounded read-only inspector**, followed by deterministic independent oracle acceptance. Reuse existing AFO/Fabro and protect one-GPU model handoff/lease, old Qwen fallback and strict release. Prioritize source/role/protocol fixes from the overnight review, then a multi-driver SWE.1 lab with frozen oracles and SWE.2 importer, leaving one tiny CRC end-to-end smoke. Implement small tested changes with failed-before negative cases, provenance, actual source-contract checks and reproducible CI. Cloud execution cannot assert real model behavior; prepare an authorized Omniverse runbook, do not remotely deploy or spend inference without a new grant. Preserve old 2/3 cohort, all stops/charges, private inputs and historic source identities. Deliver source commit/PR, EGM reports, tests, exact NOT_RUN limits and next measured experiment; do not add a scheduler, EGM runtime, agents for runtime maintenance or a new release authority.

---

## 12. External technical references

- Automotive SPICE 4.0 process names: <https://www.ul.com/sis/services/automotive-spice-process-model-spice-extensions>.
- Ornith base model, model-specific tool/reasoning parser and runtime requirements: <https://huggingface.co/ornith-ai/Ornith-1.5-35B-A3B>.
- Ornith official GGUF Q8_0 file: <https://huggingface.co/ornith-ai/Ornith-1.5-35B-A3B-GGUF>.
- AtomicChat GGUF conversion (different Q8_0 file size/digest): <https://huggingface.co/AtomicChat/Ornith-1.5-35B-A3B-GGUF>.
- Forge-C overnight review: <https://github.com/jnsagai/forge-c/blob/main/docs/reports/ASTRA-OVERNIGHT-REVIEW-20261030-31.md>.
- Google EGM: <https://github.com/google/elephant-goldfish-model>, Claude integration: <https://github.com/google/elephant-goldfish-model/blob/main/docs/claude.md>, EGM review: <https://github.com/google/elephant-goldfish-model/blob/main/skills/egm-review/SKILL.md>.

**Publication note:** This is an implementation plan, not evidence of deployment, live inference, new process qualification, performance improvement, or release. No repository changes are implied by creating this file.