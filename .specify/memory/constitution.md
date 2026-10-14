# Forge-C Constitution

**Version:** 0.4.0 (proposed implementation baseline)  
**Adopted for the implementation plan:** 2026-10-14  
**Ratification:** pending external engineering review; this does not constitute a safety-process sign-off.

## I. Safety and correctness precede optimization

All C HAL/LLD functions SHALL meet deterministic functional and safety constraints before reducing Flash, RAM, stack or cycles. No measured footprint benefit may waive a blocking verification defect. HW semantics come only from baselined authoritative reference manuals, errata, HSI and allocated safety requirements; never invent MCU registers, timing or reset behavior.

## II. All execution is evidence driven

AI completion messages are not test evidence. Every engineering change has reproducible tool invocations, version, exit code, results and hashes. Workproducts align with applicable ASPICE 4.0 SWE.1–SWE.6 and ISO 26262 ASIL B-oriented evidence, with SUP.1/8/9/10, traceability, tool-confidence assumptions, deviation tracking and an independently verifiable offline package.

## III. Fully unattended run, external release authority

No human approval gate inside normal Fabro runtime. Failures generate BLOCKED packages with all available workproducts and findings. Only an offline human/organization may accept safety-related deviations, confirm independent review, approve process evidence or authorize deployment.

## IV. AI roles require versioned SKILLs

Every AI agent has a discoverable `SKILL.md` with role permissions, input/output contracts, and explicit limits. SWE inspector and author never share identity/context. Deterministic policy services, not agent prompts, enforce safety and role boundaries.

## V. Every production AI tool call uses MCP

Re-use valid open-source MCP servers or build thin audited domain wrappers. A required missing MCP means BLOCKED before an agent executes. Builtin Fabro platform internals, the OS watchdog and non-AI monitoring use their native APIs where safer; this does not circumvent agent MCP policy. Never expose arbitrary shell/privileged device flashing or broad filesystem writes via MCP.

## VI. Model-free supervision and bounded self-healing

Health checks are deterministic, independent of Fabro, and consume exactly zero model tokens when healthy. Failed health creates a durable incident and eligible repair dispatch; patches are isolated, tested and promoted by policy or rolled back. Repair cannot modify protected safety/QA policies or released artifacts. Rate limits prevent recovery storms.

## VII. Evidence-based shared knowledge only

Lessons learned are sourced from real repairs, sanitized, versioned, deterministically validated and retractable. Unknown, unsupported, outdated or malicious lessons are quarantined. Cross-workflow retrieval is selective and token-bounded. Lessons never outrank approved requirements or change safety gates.

## VIII. Observable, configurable, privacy-preserving traces

Trace capture levels per category are independent of human dashboard display filters. Critical audit events cannot be disabled. No hidden model reasoning is collected; raw prompts/completions default OFF. All logs are structured, correlated, redacted and subject to retention/least privilege.

## IX. Minimal model cost without lost engineering evidence

The supervisor is model-free. Agent output is compact structured status/issue data; full arguments and calculations live in workproducts, not verbosity. Tool output is referenced through artifact IDs, deltas replace repeated full context, and every role has a budget enforced by deterministic governor. Budget exhaustion yields an explicit blocked state, never waived verification.

## X. Open-source-first and clean interfaces

No commercial API or licensed tool is mandatory for the v0.4 factory runtime. Build/test/static coverage/tool wrappers must be reproducible and pin versions/licences. MISRA text and official ISO publications are not included and may require separate organizational access. A model or MCP server cannot certify tool confidence, ASPICE capability or functional-safety compliance.

## Governance

Any change to the constitution, release gates, HSI source-of-truth, safety policy, repair protected paths or assurance criteria is **out of automated self-heal scope**. Such changes require explicit externally baselined engineering authorization; in unattended mode, create a BLOCKED offline review request. Proposed updates retain audit history and include impact assessment. The constitution is the single runtime requirements source; Spec Kit feature templates and tests reference it rather than copy/paste contradictory principles.
