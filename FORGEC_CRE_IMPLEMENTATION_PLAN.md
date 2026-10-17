# Forge-C / ForgeC — Continuous Reliability Engineering (CRE)

**Feature 004 implementation plan for Claude Code** · 16 October 2026  
**Status:** specification and executable task backlog only; **not yet implemented**  
**Baseline:** existing Forge-C v0.5 design/features 001–003  
**Goal:** transform the existing factory's retry/self-healing mechanisms into measurable, evidence-driven reliability growth, bounded recovery and prevention of recurring failures.

## 1. Executive directive

Implement **Feature 004** incrementally in the existing Forge-C repository using GitHub Spec Kit. Claude must inspect reality first and extend features 002 and 003 instead of rewriting or duplicating their supervisor, Fabro workflows, Repair Agent, lessons DB, trace dashboard, Release Manager and 20-KPI catalog. Preserve versioned SKILLs for every AI agent, scoped MCP tools for every agent-accessible engineering operation and local Qwen for runtime inference. Claude Code is the developer, not a mandatory factory production model.

Implement two **separate** closed loops:

1. **Operational self-stabilizing recovery:** detect/classify, handle only allowed transient faults with bounded retries, recover from checkpoints or reach an explicit stable failure disposition. No infinite loops and no hidden cost explosion.
2. **Evolutionary reliability growth:** CAPA/reproducer/root-cause verification, independent candidate/holdout testing, deterministic policy/safety/quality promotion veto, durable validated lessons, recurrence monitoring and calibrated SPC statistics.

The second loop should verify improvements in consecutive factory versions; it cannot **guarantee** zero future failures of probabilistic agents under unseen workloads. Operational safety and termination properties can be strongly established only within explicitly modelled assumptions.

## 2. Dependencies and preservation rules

Existing contracts are authoritative, even if design-only:

- `specs/001-factory/` — real C RCC host demonstrator, compilers/tests/evidence.
- `specs/002-self-healing-factory/` — planned/existing dark factory architecture; model-free supervisor, repair, Fabro/MCP, skills, dashboard, SWE.1–SWE.6 and offline release.
- `specs/003-manufacturing-kpis/` — K01–K20 formulas, including K16 recovery effectiveness and K17 recurrence.
- `.specify/memory/constitution.md`, `CLAUDE.md` and project release/safety policies remain immutable unless authorized outside autonomous repair.

**Very important:** v0.5 documentation identifies some components as **specification only**, not deployed implementations. A capability audit must distinguish `IMPLEMENTED`, `PARTIAL`, `SPEC_ONLY` and `MISSING` before Claude starts coding. Real E2E readiness is BLOCKED until actual Fabro, MCP and Qwen integration exists. Do not silently change the approved Automotive SPICE baseline or claim ASIL B/capability certification.

## 3. Deliverable milestones

| Milestone | Main deliverable | Tasks | Exit evidence |
|---|---|---|---|
| **D0** Baseline and integration audit | Reality-based capability matrix, baseline test hashes, ADRs, observe-only policy | CRE-T001–004 | No invented implementations; dependencies 002/003 mapped |
| **D1** Incidents and failure taxonomy | Typed CRE events, deterministic fingerprints, durable idempotent replay | CRE-T005–010 | Replay/dedup and provenance tests |
| **D2** Bounded recovery control | Retry+breaker policy, leases, checkpoint safety, stable terminal states | CRE-T011–016 | Zero LLMs in healthy polls, no unbounded retries; recovery fault tests |
| **D3** CAPA and verified prevention | RCA hypotheses vs verified causes, reproduction tests, existing lesson integration | CRE-T017–023 | Recurrence reopens CAPA; poisoned knowledge blocked |
| **D4** Independent regression/promotion | Frozen golden+holdout benchmark, quarantined patches, protected independent gate, rollback | CRE-T024–029 | Bad candidate rejected even if faster; no code self-promotion |
| **D5** Quantitative growth/SPC | Existing K16/K17 preserved, CRE-R01..R08 analytics, Wilson intervals, calibrated p-chart/EWMA | CRE-T030–034 | Faithful denominators, sample sizes, no misleading reliability claims |
| **D6** UI and safety evidence | Existing dashboard Reliability view, protected audit traces, release evidence package | CRE-T035–038 | Drills to provenance; READY/BLOCKED handoff remains trustworthy |
| **D7** Chaos, E2E and readiness | Fault-injection suite, real RCC run if supported, complete traceability and readiness decision | CRE-T039–042 | Evidence-based OBSERVE_ONLY/PILOT_ELIGIBLE/ACTIVE_ELIGIBLE/NOT_DEMONSTRATED |

## 4. Hard acceptance conditions

- **Convergence/termination:** for supported fault classes, finite state transitions lead to `RECOVERED` or `REQUIRES_OFFLINE_ATTENTION` within configured attempt budgets. Document assumptions; if the infrastructure prevents observation, persist the unresolved incident and escalate via watchdog.
- **Closure/safety:** healthy polling leaves healthy state unchanged; historical evidence and safety/security policies cannot be modified by repair. A new external fault remains possible.
- **Root-cause verification:** must reproduce original defect in pinned baseline and demonstrate independent contrast/test. AI explanations are hypotheses, not proof.
- **Promotion:** isolated worktree + independent validator + baseline/holdout + protected-file + safety/quality + threat tests. Result `REJECTED`, `INCONCLUSIVE` or `ELIGIBLE_FOR_OFFLINE_REVIEW`; initial policy forbids automated persistent-code release.
- **Statistical rigor:** numerator/denominator/workload cohort, 95% Wilson CI for binomial rates where suitable, explicit uncertainty and censoring. SPC measurement-only until calibrated; models such as Duane are diagnostic, not release gates.
- **Engineering controls:** SWE.1–SWE.6 independent inspections, MISRA scope/coverage, traceability, footprint and ISO 26262 evidence remain strict non-compensable requirements.
- **Costs:** supervisor zero healthy-poll tokens; deterministic-first classification and policy; model calls for eligible unresolved diagnostics only; short structured agent status and bounded log excerpts.
- **Offline release:** always preserve `READY_FOR_OFFLINE_REVIEW` / `BLOCKED`, with hashed CRE evidence and authorized human release assessment separate from normal dark execution.

## 5. Start sequence for Claude

From the **existing Forge-C repository**, copy the `specs/004-continuous-reliability-engineering/` directory and read `CLAUDE_CRE_START.md`. Run the project baseline tests before edits, then implement the milestones in order. Use the actual installed Spec Kit syntax. Preferred process is review/check specs → analyze → implement bounded milestone → converge → address appended gaps → repeat. Keep a task status/evidence ledger; DO NOT mark a task complete solely because a document or mock test exists.

Useful baseline commands inherited from the v0.5 handoff:

```bash
python3 tests/spec/validate_design.py
python3 -m unittest discover -s tests -v
python3 -m unittest discover -s factory/release-manager/tests -p 'test_*.py' -v
python3 scripts/verify_bundle.py
./scripts/run_oss_demo.sh  # optional, when native LLVM tools are installed
```

Read the package's detailed artifacts for the normative definition:

- `CLAUDE_CRE_START.md` — copy/paste execution directive, constraints and status contract.
- `specs/004-continuous-reliability-engineering/spec.md` — 40 numbered functional requirements, boundaries, invariants and user stories.
- `specs/004-continuous-reliability-engineering/plan.md` — architecture, state machines, metrics, promotion gates, threat constraints, integration ADRs.
- `specs/004-continuous-reliability-engineering/tasks.md` — 42 implementation tasks with dependencies and acceptance links.
- `specs/004-continuous-reliability-engineering/acceptance-tests.md` — 39 concrete acceptance/chaos scenarios and proof rules.
- `specs/004-continuous-reliability-engineering/contracts/` — JSON Schemas, example config and provisional benchmark suite for Claude to reconcile with actual source.

### Expected final handoff from Claude

1. Actual Git commit IDs and changed-file inventory; no hidden modifications to baseline safety or 001–003 evidence.
2. Status by task and requirement with precise PASS/FAIL/BLOCKED and rerunnable commands.
3. New runtime code, tests, config migrations, documentation and pinned dependency/version evidence.
4. Reliable negative-case failure-injection proof, including retries bounded, rollback, CAPA retraction and zero model calls on healthy polling.
5. Frozen benchmark comparisons, KPI/formula provenance, statistical limitations and deterministic promotion verdicts.
6. Integrated dashboard/report evidence and versioned offline Release Manager package (`READY_FOR_OFFLINE_REVIEW`/`BLOCKED`).

**Scope limit:** Spec Kit's `converge` checks compliance with the specification; **it is not a theorem of runtime reliability**. Production readiness requires independent actual-running evidence and offline authorized reviews.

## Reference material

- https://github.com/github/spec-kit/blob/main/docs/guides/evolving-specs.md
- https://learn.microsoft.com/en-us/azure/architecture/patterns/circuit-breaker
- https://learn.microsoft.com/en-us/azure/architecture/patterns/bulkhead
- https://www.itl.nist.gov/div898/handbook/
- https://sre.google/sre-book/monitoring-distributed-systems/
