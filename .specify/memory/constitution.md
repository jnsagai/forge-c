<!--
Sync Impact Report
- Version change: 0.4.0 → 0.5.0 (MINOR)
  Principle II is generalised from a fixed ASPICE/ISO 26262 orientation to standard profiles. Principle I's scope
  reaches middleware and application software, and new operating-mode clarifications are added. No principle is
  removed and no existing obligation is weakened.
- Modified principles:
  - II. "All execution is evidence driven": the evidence obligations are unchanged. The standard orientation moves from
    "ASPICE 4.0 SWE.1–SWE.6 + ISO 26262 ASIL B" to "a standard-neutral high-integrity core with standard profiles".
    ISO 26262 and ASPICE remain supported profiles.
  - I. "Safety and correctness precede optimization": the scope now covers middleware and application software as well
    as C HAL/LLD. Nothing is removed.
- Added sections: "Operating modes, models and the V-model".
- Removed sections: none.
- Unchanged: III, IV, V, VI, VII, VIII, IX and X. The existing on-premise factory (Fabro workflows, model-free
  supervisor, CRE, AFO, KPIs, dashboards, lessons, traces) keeps all its obligations.
- Templates:
  - ✅ .specify/templates/plan-template.md: its Constitution Check derives gates from this file, so no edit is needed.
  - ✅ .specify/templates/spec-template.md: no new mandatory section.
  - ✅ .specify/templates/tasks-template.md: no new principle-driven task type.
  - ✅ .claude/skills/speckit-*: they reference the constitution generically; no agent-specific wording to fix.
  - ✅ README.md and the website: feature 023 (T084) added the portable skills package with its standard profiles; the
    factory's own ASPICE SWE.1–SWE.6 description stays accurate for the factory.
- Deferred TODOs: none.
-->

# Forge-C Constitution

**Version:** 0.5.0
**Adopted for the implementation plan:** 2026-10-14
**Last amended:** 2026-11-22 (owner-authorized, feature 023: high-integrity standard profiles)
**Ratification:** pending external engineering review; this does not constitute a safety-process sign-off.

## I. Safety and correctness precede optimization

All C HAL/LLD functions, and all middleware and application software produced with Forge-C, SHALL meet deterministic
functional and safety constraints before any reduction of Flash, RAM, stack or cycles. No measured footprint benefit may
waive a blocking verification defect. Hardware semantics come only from baselined authoritative reference manuals,
datasheets, reference models, errata, HSI and allocated safety requirements. Never invent MCU registers, timing or reset
behavior.

## II. All execution is evidence driven, under high-integrity standard profiles

AI completion messages are not test evidence. Every engineering change has reproducible tool invocations, version, exit
code, results and hashes.

Forge-C is led by **generic high-integrity software standards** through a standard-neutral core:

- neutral V-model stages, workproducts, integrity levels, traceability rules and checklists;
- **standard profiles** that map them to a specific standard's terms, clause identifiers and rigor settings (required
  checks, independence, verification and coverage targets).

The supported profiles are:

- a generic baseline;
- ISO 26262 (including the existing ASIL B-oriented evidence);
- IEC 61508;
- ASPICE 4.0 as the process reference (SWE.1–SWE.6 and SYS.2–SYS.5).

Further standards, such as DO-178C, EN 50716 and IEC 62304, are added as profiles, never hard-wired into skills or
gates. With no profile selected, the generic profile applies at an explicitly stated integrity level. No standard is
ever assumed silently.

Under every profile, workproducts keep:

- bidirectional traceability;
- support-process evidence equivalent to SUP.1/8/9/10 (quality assurance, configuration management, problem resolution
  and change request management);
- tool-confidence assumptions;
- deviation tracking;
- an independently verifiable offline package.

Profiles cite clause identifiers only and never reproduce normative text.

## III. Fully unattended run, external release authority

No human approval gate inside normal Fabro runtime. Failures generate BLOCKED packages with all available workproducts
and findings. Only an offline human/organization may accept safety-related deviations, confirm independent review,
approve process evidence or authorize deployment.

## IV. AI roles require versioned SKILLs

Every AI agent has a discoverable `SKILL.md` with role permissions, input/output contracts, and explicit limits. SWE
inspector and author never share identity/context. Deterministic policy services, not agent prompts, enforce safety and
role boundaries.

## V. Every production AI tool call uses MCP

Re-use valid open-source MCP servers or build thin audited domain wrappers. A required missing MCP means BLOCKED before
an agent executes. Builtin Fabro platform internals, the OS watchdog and non-AI monitoring use their native APIs where
safer; this does not circumvent agent MCP policy. Never expose arbitrary shell/privileged device flashing or broad
filesystem writes via MCP.

## VI. Model-free supervision and bounded self-healing

Health checks are deterministic, independent of Fabro, and consume exactly zero model tokens when healthy. Failed health
creates a durable incident and eligible repair dispatch; patches are isolated, tested and promoted by policy or rolled
back. Repair cannot modify protected safety/QA policies or released artifacts. Rate limits prevent recovery storms.

## VII. Evidence-based shared knowledge only

Lessons learned are sourced from real repairs, sanitized, versioned, deterministically validated and retractable.
Unknown, unsupported, outdated or malicious lessons are quarantined. Cross-workflow retrieval is selective and
token-bounded. Lessons never outrank approved requirements or change safety gates.

## VIII. Observable, configurable, privacy-preserving traces

Trace capture levels per category are independent of human dashboard display filters. Critical audit events cannot be
disabled. No hidden model reasoning is collected; raw prompts/completions default OFF. All logs are structured,
correlated, redacted and subject to retention/least privilege.

## IX. Minimal model cost without lost engineering evidence

The supervisor is model-free. Agent output is compact structured status/issue data; full arguments and calculations
live in workproducts, not verbosity. Tool output is referenced through artifact IDs, deltas replace repeated full
context, and every role has a budget enforced by deterministic governor. Budget exhaustion yields an explicit blocked
state, never waived verification.

## X. Open-source-first and clean interfaces

No commercial API or licensed tool is mandatory for the factory runtime or for the portable skills package. Build, test,
static analysis, coverage and tool wrappers must be reproducible and pin their versions and licences. MISRA text and
official ISO/IEC publications are not included and may require separate organizational access. A model or MCP server
cannot certify tool confidence, ASPICE capability or compliance with any functional-safety standard.

## Operating modes, models and the V-model

1. **Model-agnostic.** Forge-C works with cloud and local models. The harness and the model are configurable per role
   (author, inspector, release) for each stage. No provider, model or harness is hard-wired into skills, gates or
   profiles. Every run records the configuration actually used. A profile may require the author and the inspector to
   use different model families. Cloud models are used through the operator's own authorized accounts. They are never a
   mandatory paid dependency (Principle X).
2. **Two operating modes, one assurance bar.**
   - **Unattended factory mode** (Fabro workflows, supervisor, CRE, AFO) follows Principles III–VI as written.
   - **Assisted mode** is the same versioned skills invoked by a human inside a coding agent.

   In assisted mode, role write scope is enforced by harness hooks where they exist, and otherwise detected and failed by
   the deterministic gates. Tool use goes through MCP where the harness supports it. Both modes use the same
   deterministic gates, the same author/inspector independence, and the same READY_FOR_OFFLINE_REVIEW or BLOCKED
   packages. A human's presence in assisted mode is never a release approval (Principle III).
3. **Standard V-model from system requirements.**
   - **Left side:** system requirements, system architecture, software requirements, software architecture, then
     detailed design and unit construction.
   - **Right side:** unit verification, software integration verification, software qualification verification, then
     system integration and system qualification verification.

   Each right-side item traces to the left-side item it verifies. There are two input classes:
   - natural-language stakeholder/system needs (middleware and application), entering at system requirements;
   - reference documents (datasheets, reference manuals, reference models) for HAL/LL, which may enter out-of-context at
     software requirements, with every hardware claim citing the document's section and page.

## Governance

Any change to the constitution, release gates, HSI source-of-truth, safety policy, standard profiles' rigor settings,
repair protected paths or assurance criteria is **out of automated self-heal scope**. Such changes require explicit
externally baselined engineering authorization; in unattended mode, create a BLOCKED offline review request. Proposed
updates retain audit history and include impact assessment. The constitution is the single runtime requirements source;
Spec Kit feature templates and tests reference it rather than copy/paste contradictory principles.

Versioning follows semantic versioning:

- **MAJOR:** a principle is removed or redefined incompatibly.
- **MINOR:** a principle or section is added or materially expanded.
- **PATCH:** wording only.

**Amendment log:**

- 0.5.0 (2026-11-22, owner-authorized): Principle II generalised to high-integrity standard profiles; Principle I scope
  extended to middleware and application; "Operating modes, models and the V-model" added. No principle was removed.
