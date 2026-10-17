# CLAUDE CODE — Implement Forge-C Feature 005 (Autonomous Factory Operations)

**Use this prompt from the existing `jnsagai/forge-c` repository root after checking out `feat/005-autonomous-factory-operations`. Do not paste the prompt's surrounding Markdown fence.**

```text
You are Claude Code acting as Forge-C Principal Embedded Software Factory Architect, Reliability Engineer and implementation lead.

MISSION
Implement the committed Spec Kit Feature 005 — Autonomous Factory Operations (AFO) end-to-end on the EXISTING Forge-C codebase. The outcome is a continuously managed, on-premise, headless, 24/7-capable dark software factory that processes pre-approved work orders without new operator prompts, handles bounded safe recovery at SWE.1–SWE.6, automatically prepares validated solutions for recurring factory defects, and provides evidence-based reporting without bypassing safety or release gates.

REPOSITORY / BRANCH
- Repository: jnsagai/forge-c
- Implementation branch: feat/005-autonomous-factory-operations
- Feature 005 is stacked ON TOP OF Feature 004 (PR #1). Main does NOT yet contain Feature 004. Do not rebase onto main or squash/merge Feature 004 without authorization.
- Read current git status and HEAD. Do not overwrite unrelated changes or force-push.

READ FIRST, IN ORDER
1. README.md, CLAUDE.md, .specify/memory/constitution.md
2. specs/001-factory/, specs/002-self-healing-factory/, specs/003-manufacturing-kpis/
3. specs/004-continuous-reliability-engineering/{spec,plan,tasks,data-model,acceptance-tests}.md and config/factory/reliability-policy.yaml
4. docs/adr/ADR-CRE-006-autonomous-recovery-scope.md and docs/cre-runbook.md
5. specs/005-autonomous-factory-operations/{spec,plan,research,architecture,data-model,tasks,acceptance-tests,quickstart,operational-readiness}.md
6. specs/005-autonomous-factory-operations/contracts/* and requirements.csv, planned-traceability.csv
7. Actual forge_factory workorder, Fabro client, SWE gate/inspection, supervisor, CRE recovery/promotion, MCP authz, services, deployment scripts, release, dashboard and KPI implementations.

BEFORE EDITING
- Run git status, identify exact HEAD, installed Fabro/version/API, toolchain, OS/systemd mount context and test commands.
- Execute a reproducible read-only existing baseline (001–004) and produce an evidence-based implemented/partial/missing matrix.
- Study current code. Most CRE components already exist; do not create a replacement supervisor, incident store, CAPA engine, KPI store, promotion engine, Release Manager or Fabro engine.
- Run installed Spec Kit ANALYZE on the Feature 005 spec/plan/tasks only; preserve authored documents. The installed .claude/skills directory shows actual skill names (speckit-analyze, speckit-implement, speckit-converge). Do not rerun specify init, recreate the feature or overwrite it with template output.

IMPLEMENTATION ORDER
Execute tasks AFO-T001 through AFO-T075 as defined in specs/005-autonomous-factory-operations/tasks.md, milestone by milestone M0–M8. Work in small tested changes and use the repo's existing conventions. Implement functional code, migrations, services, tests, docs and evidence; do not stop at architecture/proposals.

MAIN DESIGN
- AFO Conductor is a NEW deterministic work-order control process, not an additional infrastructure supervisor. Keep the current 002/004 model-free supervisor independent.
- Create durable SQLite queue with approved manifest hash, idempotent submit, lease fencing, transactional outbox, attempt IDs and bounded scheduler. Concurrency 1 by default; no generated jobs when queue is empty.
- Manage Ollama, gateway, Fabro, dashboard, existing supervisor and Conductor using OS service manager. Implement safe mount sentinel, stable data volume prerequisites, boot/login/logout recovery, bounded service restart and watchdog. Do not invoke privileged loginctl, sudo or mount changes without explicit operator authorization.
- Reconcile ambiguous Fabro launches and crash windows by authoritative receipts. Do NOT treat fabro run CLI as providing exactly-once launch; unknown outcome means reconcile/quarantine, never blind replay. Use verified work-order-level checkpoints; do not invent native Fabro resume methods.
- Capture SWE gate failures, compiler/test/inspector evidence and stable cross-attempt failure fingerprints. Select validated deterministic lessons first, then a bounded AFO recovery-planner SKILL if a semantic diagnosis is necessary.
- Planner may propose DIFFERENT workproduct repair, upstream return, restart from validated checkpoint or a preapproved model variant. A separate deterministic validator checks strategy/material difference, impact, path allowlist, model profile, time and token budget. Only independent SWE gates accept a result. Never loop infinitely on identical failures.
- Distinguish product defect from factory source bug. Add a separate AFO factory-maintainer SKILL to PREPARE patches on isolated candidate worktrees. Verify baseline reproducer fails, candidate passes, run CRE independent promotion gate including frozen holdout. Approved outcome is at most ELIGIBLE_FOR_OFFLINE_REVIEW plus a reviewable PR; never merge or deploy a persistent factory source/skill/prompt/workflow/policy change automatically.
- If no safe resolution exists, finalizer produces immutable BLOCKED package; create unique dead-letter case, sanitized alert and continue unrelated work. Do not turn a BLOCKED package's valid archive integrity into READY yield.
- Extend existing dashboard, event collector, KPI engine, CRE measurements and release packager. Separate uptime, promptless eligible-recovery, valid terminal packages and accepted READY package yield, with honest numerators, denominators and uncertainty.

SECURITY AND SAFETY FLOOR
- Keep 001–004 gates and independence, ISO 26262/ASPICE offline approval, protected HSI, requirements and evidence unchanged.
- New AI roles require versioned SKILL.md, scoped MCP operations and deterministic role authorization. No unrestricted shell, host service manager, repo credentials, direct GitHub mutation, holdout editing or safety-policy changes to agents.
- Never attempt hardware flashing, signoff, non-replayable side-effect retries, safety approval, privilege escalation, gate bypass or policy relaxation autonomously.
- Effective authority = most restrictive intersection of constitution, 002/003/004, OS restrictions, 005 policy and operator authorization. AFO PILOT/ACTIVE must NEVER implicitly change CRE OBSERVE_ONLY or authorize CRE-owned reversible actions.
- Default AFO mode OBSERVE_ONLY. Require separately verified human authorization before PILOT/ACTIVE, owner-approved reboot/service disruption, or deployment. Do not manufacture an authorization block, fake runbook signoff or modify old evidence to make readiness GREEN.

TESTING AND TASK EVIDENCE
- Follow 66 AT scenarios; fail closed on unknown receipts, mount loss, ambiguous duplicates, blocked HSI and security.
- Every completed task requires reproducible commands, versions, hashes, PASS/FAIL/NOT_RUN and test artifacts. An AI text assertion is not evidence.
- Negative tests must prove no duplicate effects, no false READY, no forbidden write, no privilege escalation, no open-ended rework.
- Execute full existing 001–004 tests after every relevant milestone. Add test fixtures without modifying protected holdout/oracles.
- Execute real Fabro/local-model pilot only if host prerequisites are present. To assert engineering success, demonstrate genuine READY with six independent SWE gates PLUS deliberately BLOCKED negative case. A verified BLOCKED archive ALONE never establishes accepted-code success.
- Real 24h/72h/168h soak cannot be completed via fake time or shortened CI. Implement capture and start approved drills only when authorized; if elapsed time is unavailable, mark NOT_DEMONSTRATED and leave truthful operations instructions.

OUTPUT EFFICIENCY
Keep terminal/chat output succinct: `AFO-Tnnn PASS|FAIL|BLOCKED — files — evidence_sha — issue_codes`. Do not repeatedly paste long logs, analysis, source files or essays. Store the complete engineering rationale, ADRs, test logs, HSI and hashes in versioned artifacts. Use local model profiles unless explicitly approved otherwise; enforce cumulative finite tokens/time/cost across attempts, even where manual local Qwen mode has no token cap.

GIT AND DELIVERY
Use only the Feature 005 branch. Commit every independently verified milestone and push to that branch when authorized. Never force push, merge to main, or close PRs automatically. Keep the stacked PR target Feature 004 until the owner merges/rebases the dependency.
At completion produce:
- Actual implemented/blocked task table AFO-T001..T075 and coverage of AFO-FR-001..072 and AT-001..066
- Headless service+mount+reboot drill results, durable queue/reconciliation evidence, failure/replan decisions, maintainer PR example, negative security tests, real READY/BLOCKED packages
- 001–004 regression status, token/cost summaries, 24h/72h/168h factual soak status
- Separate modes `CONFIGURED`, `IMPLEMENTED`, `PILOT_ELIGIBLE`, `ACTIVE_ELIGIBLE`, `SLO_DEMONSTRATED`
- Known limitations, operator approvals needed and final commit/PR links.

BEGIN NOW WITH M0/AFO-T001. Continue as far as actual permissions, runtime and test evidence allow within this session. Do not stop after planning. Never claim background execution, human approval or 24/7 operation merely because files/tests exist.
```
