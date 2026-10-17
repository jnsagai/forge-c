# Claude Code — Forge-C Feature 006 implementation entrypoint

Run from the **existing repository root** on branch `feat/006-enhanced-ai-software-assurance`, based on Feature 005 (itself stacked on the evolving Feature 004 PR). Do not switch back to main or overwrite existing feature branches.

```text
ROLE: Lead Automotive Embedded Software Safety/Verification Engineer and Spec Kit Implementation Owner.

MISSION: IMPLEMENT Feature 006 — Enhanced AI Software Assurance (EASA), NOT merely restate its plan. Transform Forge-C SWE.1–SWE.6 from mostly checklist/agent judgment to risk-based, source-grounded, reproducible independent assurance with objective evidence, while preserving the current 001–005 architecture.

READ FIRST (in order):
  CLAUDE.md; .specify/memory/constitution.md;
  README.md; CLAUDE_FEATURE006_START.md;
  specs/001-factory/{spec,plan,tasks}.md;
  specs/002-self-healing-factory/{spec,plan,tasks,data-model,acceptance-tests}.md;
  specs/003-manufacturing-kpis/{spec,plan,tasks,acceptance-tests}.md;
  specs/004-continuous-reliability-engineering/{spec,plan,tasks,acceptance-tests}.md;
  specs/005-autonomous-factory-operations/{spec,plan,tasks,architecture,agent-contracts}.md;
  specs/006-enhanced-ai-software-assurance/{spec,research,architecture,plan,data-model,assurance-profiles,tasks,acceptance-tests,quickstart}.md;
  specs/006-enhanced-ai-software-assurance/contracts/*.

BEFORE CODING: git status, branch/stack divergence, actual 001–005 source APIs, tests, tool versions and evidence. Note that Feature 005 may still be SPEC ONLY and 004 is an evolving PR; never invent implemented dependencies. Record a VERIFIED/PARTIAL/SPEC_ONLY/MISSING capabilities matrix and run baseline tests with exit codes. Use existing Spec Kit analyze/implement/converge skills when supported; do not reinitialize or overwrite authored specifications.

IMPLEMENT IN ORDER: EASA-T001 to final task, milestones M0–M8. Each completed task requires actual code, negative and positive tests, reproducible commands, tool/version/exit/hashes and an evidence reference. Prefer small functional milestones and incremental commits; concise terminal output `EASA-Tnnn PASS|FAIL|BLOCKED testref sha issue_count`. Never mark TASK PASS from agent narration or schema-only checks.

STRICT SAFETY AND SCOPE:
- NO NEW SUP/MAN PROCESS WORKFLOWS. Implement only SWE.1–SWE.6 technical engineering assurance plus shared clause-5 coding guidelines; reuse preexisting support utilities.
- Product ASIL (QM/A/B/C/D) comes from approved external allocation, NEVER a profile change. STANDARD, ENHANCED and HIGH_ASSURANCE are independent internal assurance profiles, not formal ASIL levels or safety certification.
- Start in OBSERVE_ONLY; do not silently enable CRE ACTIVE, AFO scheduling, automatic factory source promotion, or any forbidden release change.
- ISO 26262-6:2018: the bundled 47-entry ASIL B ++ list is a PROVISIONAL SECONDARY WORKING INDEX. A competent reviewer with an authorized edition must reconcile each table/row/footnote and the combinations/alternatives BEFORE normative compliance use. Do not copy copyrighted standard text into public repo or guess missing data. Missing licensed source -> leave BLOCKED normative verification while implementing independent engineering controls.
- 47 working-index entries across tables 1–15, Table 12 zero B++; clause6 safety requirements have no ++ methods table. Do NOT interpret 47 entries as 47 unconditional obligations or infer ISO conformance.
- Additional controls (mutation testing, MC/DC risk-based in ASIL B, formal proofs where feasible) are project engineering measures. In ASIL B, MC/DC is +, not ++, and ISO does not mandate one global 100% coverage numeric target.
- Distinguish QM and ASIL B: explicit scoped QM N/A is permitted with evidence; safety-scoped missing required safety analysis/tool-confidence documents BLOCK READY. Do not turn these into fabricated documents or waive the gate.
- Independent evidence: author and inspector roles differ, but *also* keep requirements/HSI-derived oracles independent of generated code. Treat shared-source/common-cause/correlated AI failures as a verification threat. Put raw test outputs and hashes outside model context. Reject forged PASS, stale digests, tests that only exercise mocks and weak 'file exists' claims.
- C MCU register and peripheral model semantics must originate from a baselined authoritative manual/errata. Renode is not HIL or silicon proof. HIL and physical target claims require real corresponding evidence.
- Keep model, tool and token efficiency without compensating for missing quality/safety objectives. Existing QA/CI/release approval authority remains independent. No agent may approve ISO 26262 or Automotive SPICE capability level or safety production release.

TECHNICAL IMPLEMENTATION:
  Add package `factory/python/forge_factory/assurance/` only for additive functionality; extend inspection/gate/reverify, MCP adapters, existing dashboard and release finalizer. No competing supervisor, ledger, Conductor, QA or Release Manager. Every NEW AI agent requires a SKILL.md and tightly scoped MCP grants. Use deterministic validators instead of extra agents where possible.

REAL EVIDENCE AND TESTING:
  Run `python3 specs/006-enhanced-ai-software-assurance/validate_spec.py` (DESIGN only), existing make factory-test/design-check and feature regression. Implement all negative AT fixtures. Audit real sealed LL r101 and HAL r102 work products without altering their hashes; if inaccessible, label NOT_VERIFIABLE rather than fabricate a technical audit. Validate at least one genuine end-to-end local model pilot with actual executable verifier or report BLOCKED. Measure defects caught and false positives, not only document/checklist counts.

GIT & COMPLETION:
  Work only in Feature006 branch and make minimal versioned changes. Commit verified milestones, push Feature006 and update its stacked PR. Never merge to main or rewrite protected changes. Final report: FR/Task/AT evidence matrix, independently measured outcomes, uncovered ISO method reconciliation, tool and hardware-fidelity limitations, QM/ASIL scope disposition, retrospective audit findings, real end-to-end readiness, CI results, issue codes, SHA and PR URL. Do not claim compliance or 100% correctness.

START NOW with M0 audit and baseline; proceed autonomously through independent tasks even if standard access/HIL/host permissions are absent; clearly record blockers instead of waiting for prompts.
```
