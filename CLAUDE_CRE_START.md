# CLAUDE CODE — Forge-C Feature 004 Execution Contract

> Paste the **Execution Prompt** below into Claude Code, from the **existing Forge-C repository root**. Copy the accompanying `specs/004-continuous-reliability-engineering/` folder into the repository first. The Markdown specifications are instructions and starter contracts, **not evidence that feature 004 is implemented**.

## Context and baseline

Forge-C / ForgeC is an open-source, dark software factory for ultra-low-footprint embedded C HAL and low-level drivers. The established v0.5 specification consists of:

- `specs/001-factory/` — host RCC demonstrator and deterministic verification tools.
- `specs/002-self-healing-factory/` — Fabro, versioned agent SKILLs, scoped MCP operations, external model-free supervisor, isolated Repair Agent, knowledge, trace dashboard, independent SWE.1–SWE.6 inspections and offline Release Manager.
- `specs/003-manufacturing-kpis/` — 20 deterministic manufacturing-inspired KPIs with evidence provenance and dashboard snapshots.

**004 is additive, not a fork, rewrite or replacement** for 001–003. Existing source/baseline is authoritative. Local Qwen is the intended runtime inference model. Claude Code is the implementation engineer, not an additional mandatory paid production service. Existing approved ASPICE baseline must be preserved (v0.5 targets Automotive SPICE 4.0); do not silently migrate process references or claim a capability rating/ISO 26262 certification.

## Execution Prompt — paste into Claude Code

```text
Implement Forge-C Feature 004 — Continuous Reliability Engineering (CRE), using the attached specs/004-continuous-reliability-engineering directory as the authoritative feature definition and the existing Forge-C repository as the source of truth.

READ FIRST, in this order:
  README.md; CLAUDE.md; CLAUDE_START.md; PROJECT_HANDOFF_v0.5.md;
  .specify/memory/constitution.md;
  specs/001-factory/{spec,plan,tasks}.md;
  specs/002-self-healing-factory/{spec,plan,tasks,data-model,acceptance-tests}.md;
  specs/003-manufacturing-kpis/{spec,plan,tasks,acceptance-tests}.md;
  config/factory/*; actual factory code; Fabro agent/MCP manifests and SKILL files;
  specs/004-continuous-reliability-engineering/{spec,plan,tasks,acceptance-tests}.md;
  specs/004-continuous-reliability-engineering/contracts/*.

FIRST: inspect git status, existing implementation, existing runtime APIs, tests, dependencies and actual schemas. Create an evidence-based capability matrix: IMPLEMENTED / PARTIAL / SPEC_ONLY / MISSING. Preserve existing work and do not overwrite or silently upgrade earlier features. Report blockers with precise dependency IDs.

FOLLOW the existing installed Spec Kit convention. If available, use its analyze -> implement -> converge cycle, after checking that 004's spec/plan/tasks are consistent with the constitution and with 001-003. Do NOT rerun specify/plan in a way that overwrites the supplied feature definition. Run implement in bounded milestone groups, and converge after each group. If slash command spelling differs in this installed Spec Kit release, discover the actual commands instead of guessing.

IMPLEMENT task order CRE-T001 ... CRE-T042 as specified. Start with an audited, reproducible baseline and OBSERVE_ONLY mode. Reuse 002's incident/supervisor/repair/lesson/trace control plane and 003's K01-K20 KPI store. Extend these instead of creating a competing service or a second source of truth. Existing 002/003 P0 tasks on the critical path must be completed or explicitly reported BLOCKED; mocks alone never qualify as production integration.

NON-NEGOTIABLE:
- Healthy supervisor polling: ZERO LLM requests/tokens; Fabro-independent failure observation.
- All agent-invoked engineering tools use scoped MCP tools; each NEW AI role has a versioned SKILL.md and a least-privilege grants manifest. No unrestricted shell.
- Distinguish infrastructure faults, transient tool faults, quality/driver defects, and unknown causes. No infinite retries; enforce deterministic retry budgets/backoff/circuit breaker and fail closed.
- Do not allow an agent to self-certify root cause, test success, readiness, compliance or promotion. Require independently reproducible evidence.
- Isolated repairs; immutable historical artifacts; never relax or autonomously edit safety policy, approved baselines, tool qualification, MISRA/coverage/traceability gates, security boundaries or released archives.
- Use append-only, provenance-linked failure/CAPA/promotion history; lessons only after validation; retract on discovered regression.
- Separate workflow recovery (bounded runtime states) from factory evolution (candidate release gates), and explain the limits of formal/stochastic convergence.
- Reuse the 20 KPI formulas; any new CRE reliability analytics must have unique names and must not relabel/redefine historical measurements.
- Production agents stay terse (machine-readable status, artifact refs, issues). Full tests and rationale are stored as artifacts, not agent narration. Respect existing token and tool-output budgets.
- Preserve completely dark normal execution and human observation; any human approval is an offline review step, not a blocking interactive step inside a running workflow. Never auto-approve ASIL B/ASPICE capability/production safety release.
- Do not claim benchmark improvement from synthetic fixtures. Treat unknown/missing evidence as UNKNOWN/NOT_COMPUTABLE, not zero or PASS.

For each task, output ONLY: task ID, state PASS/FAIL/BLOCKED, affected files, executable test command, evidence artifact/hash and next blocker. Update tasks.md without marking unimplemented or mock-only capabilities PASS. Keep a machine-readable task status ledger. Finish with an ADR/change summary, requirement->task->test matrix, reproducible demo, fault injection reports, KPI/SPC results with sample size/confidence qualifications and a READY_FOR_OFFLINE_REVIEW or BLOCKED evidence package from the existing deterministic Release Manager path.

Do not wait for interactive confirmation for routine coding. If a required dependency/approval is missing, preserve a BLOCKED outcome and continue with independent safe tasks. Never fabricate integration or compliance results.
```

## Operator workflow

1. Extract the ZIP to a temporary directory and copy **only** `specs/004-continuous-reliability-engineering/` to the existing repository, retaining its folder name. Keep `CLAUDE_CRE_START.md` as a reference or copy it into the repository with a nonconflicting name.
2. Create a new feature branch. Run Claude Code from the existing repository root, not from an empty folder.
3. Paste the Execution Prompt. Claude must inspect dependencies and capability evidence before modifying code.
4. Review Claude's artifacts, acceptance and CI output. The presence of documentation or a simulated successful test is not a production-ready claim.

## Spec Kit guidance

The current official Spec Kit supports `specify → plan → tasks → implement → converge`, with clarify/checklist/analyze for deeper reviews. Because the feature specification in this package is already authored, **do not overwrite it**. Use the actual installed command syntax (skill or older slash command naming) determined in the repository.

Useful independent baseline smoke commands from the earlier v0.5 handoff (run only where dependencies exist; capture exit codes):

```bash
python3 tests/spec/validate_design.py
python3 -m unittest discover -s tests -v
python3 -m unittest discover -s factory/release-manager/tests -p 'test_*.py' -v
python3 scripts/verify_bundle.py
./scripts/run_oss_demo.sh  # optional: native LLVM toolchain available
```

**Outcome sought:** a factory whose *operational recovery is bounded and verifiable* and whose *successive versions are admitted only on repeatable, quality-preserving evidence*. Neither AI reasoning nor statistically finite testing guarantees universal 100% reliability.

References: https://github.com/github/spec-kit ; https://github.com/github/spec-kit/blob/main/docs/guides/evolving-specs.md
