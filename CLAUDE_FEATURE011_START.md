# Claude Code — Feature 011 implementation handoff (SafeC semantic-first local Forge-C)

You are the IMPLEMENTATION ENGINEER. Work in the existing Forge-C repository branch `feat/011-safec-semantic-first`; the approved target is to implement the authored Spec Kit package at `specs/011-safec-semantic-first/`. Do not regenerate/overwrite those documents or replace them with a generic plan. Inspect actual current Git state before modifications. If the branch has changed, reconcile rather than resetting user work.

## Read first, in order

1. `.specify/memory/constitution.md`, `CLAUDE.md` and this file.
2. `specs/011-safec-semantic-first/{spec,plan,research,data-model,acceptance-tests,tasks,validation,quickstart}.md` and `contracts/*.schema.json`.
3. `docs/adr/ADR-0013-preserve-codex-claude-local-rtx-line.md`, `docs/adr/ADR-0014-structured-local-author-tasks.md`, `docs/adr/ADR-0015-safec-semantic-boundary.md`.
4. `specs/010-local-rtx-optimization/validation.md`, `evidence/v0.4/runs/LRTX-T024/README.md`, `LRTX-T021/README.md`, `LRTX-T023/README.md`, `LRTX-T016-SWE2/README.md`, `LRTX-TRIAL/README.md`.
5. Inspect actual `factory/python/forge_factory/lrtx/{swe1,structured,runner,profile}.py`, `inspection/gate.py`, compatibility fixtures and author/inspector permission boundaries.
6. With authorized access only, inspect the **separate private SafeC Forge** at its observed discovery ref `556dca8df4d2fccd9cb59fd8fb0432aafdd05835` and its own repository constitution/AGENTS/readiness notes; establish a separate SafeC feature branch before changes. DO NOT copy its source, logs or confidential fixtures into public Forge-C.

## Hard constraints

- Preserve Claude/Codex existing production deployment and archives, the working local-v1 profile and all default/ACP paths. The new profile is **explicit opt-in**. Do not modify live service units, owner workorder archive or policy to get a green benchmark.
- You may use Claude/cloud inference to DEVELOP this feature. **The resulting Forge-C local-rtx-v2 runtime must use only verified locally hosted models/tools, remain offline and deny cloud/ACP fallback.**
- Build a strict source-bound `register-io-0.1` semantic contract inside SafeC, **not** a silent extension of current wheel-specific sampled-latch semantics. The local model proposes only finite source-linked intentions; trusted Rust computes masks and validates fields/access/assumptions.
- Respect ASIL B vs QM owner allocations and the unchanged SWE.1–SWE.6 author/inspector gates, bounded loops, admission, role SKILL/MCP, deterministic finalizer and independent offline review. No false MISRA/ISO 26262/ASPICE/ASIL claims.
- For any missing source, backend, license, proof, hardware behavior, acceptance policy or SafeC checkout, STOP THAT SUBTASK with an actionable BLOCKED/UNSUPPORTED result. Never invent a fact, change a golden oracle, auto-approve a safety input or fabricate proof.
- Claude model and any proprietary/commercial API are **not** permitted as runtime fallbacks for the local profile. Model comparisons are real local-host measurements, never benchmark-only assertions.
- Any shared `inspection/gate.py` progress-extension fix goes through its own CRE-controlled candidate/PR, with regression against ACP/v1; do NOT smuggle gate changes into v2.

## Execution milestones

**Start at M0 only (F011-T001–T005).** Establish exact current version, tools/licenses, isolation/host feasibility and baseline compatibility with actual commands. Write evidence into `validation.md` (or dedicated evidence ledger), preserving initial spec-only provenance.

Once M0 is measured, implement M1 bridge with **tests first**, M2 SafeC register semantics, M3 semantic SWE.1, M4 independent inspector comparison/qualification, then M5 SWE.2–SWE.6 and M6 campaign/rollback. Consult task dependencies. Do not run the 30-case campaign until inspector seeded/clean holdout gates pass.

Each milestone must have an atomic, reviewable diff; full positive and adversarial tests; evidence files with SHA256, tool/model identity, stdout/exit where appropriate; compatibility regression; no private source leak; and a truthfully updated `[ ]`/`[x]` tasks ledger.

## Required immediate result from Claude

Deliver M0 audit + a detailed, executable M1 contract implementation diff or an explicit BLOCKED reason. Create draft PR(s) for the separate repositories as relevant; do not merge. Summarize in compact form:

`M0 F011-T001 PASS|FAIL|BLOCKED — <evidence/commit> — <test count> — <remaining issues>`

If the private SafeC repository is not available in the Claude environment, implement the public Forge-C bridge against strict fixtures while leaving semantics unavailable/UNSUPPORTED; never claim live integration.

**No background/automatic future claim:** work only in the active Claude coding session, recording the actual completed scope and leaving the rest open.
