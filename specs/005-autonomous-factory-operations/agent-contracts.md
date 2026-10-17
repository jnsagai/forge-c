# Feature 005 — AI Agent Roles, SKILLs and MCP Permissions

**Status:** proposed agent contracts. Do not activate agents or register new MCP permissions until deterministic authorization and tests exist. Existing Fabro role manifests/skills remain source of truth; this document adds only two limited roles.

## `afo-recovery-planner` (P0)

**Purpose:** propose—not execute—a bounded, materially different recovery plan for an eligible PRODUCT_QUALITY issue where deterministic rules and verified CRE lessons are insufficient.

**SKILL path (proposed):** `.fabro/skills/afo-recovery-planner/SKILL.md` (register in `config/factory/agents.yaml`, regenerate `skills.lock.json` through the existing audited mechanism). **Input:** one `failure-bundle.schema.json` record with authoritative refs; normalized failure fingerprint; current approved requirement/HSI digest references; prior attempted plan fingerprints; remaining policy budgets; allowed strategies. Context is bounded, sanitized and clearly tagged **untrusted data**. No unsafe chain-of-thought requested or captured.

**Output:** compact JSON `status, artifacts, issues, next_action, recovery_plan_ref`; referenced plan must validate `recovery-plan.schema.json`; each strategy names owning SWE phase, allowed artifact scope, expected meaningful difference, exact tests, downstream invalidations and estimated finite resource budget. `status=PROPOSED` is not acceptance.

**Allowed operations (MCP only, names adapt to verified registry):** `forge-evidence/read_frozen_failure_summary`, `forge-evidence/list_gate_findings`, `forge-evidence/read_approved_requirement_excerpt`, `forge-knowledge/find_validated_lessons`, `forge-observer/read_budget_snapshot`, `forge-docs/read_authorized_hsi_excerpt`. Every read operation is restricted to the current immutable order/attempt and has size and token limits. Final plan submitted via a *deterministic broker*; direct writes, unrestricted shell and service control forbidden.

**Always forbidden:** editing code, tests, requirements, oracles, frozen evidence, service policies, code repositories or release archive; performing a Git push or model-provider change; seeing privileged credentials or full hidden model reasoning.

**Negative tests:** malformed JSON, prompt injection in a compiler log, missing HSI, plan requesting gate disable, unauthorized cloud switch, unchanged plan fingerprint, repeated strategy after budget exhausted.

## `afo-factory-maintainer` (P1)

**Purpose:** make a candidate patch to non-protected Forge-C source/skill/workflow code when real verified evidence identifies a FACTORY_CODE_DEFECT. This is distinct from the existing `fabric-repair` role limited to infra `runtime/**`/`services/**`.

**SKILL path (proposed):** `.fabro/skills/afo-factory-maintainer/SKILL.md`. **Input:** verified incident/CAPA, failing reproducer and baseline hash, path allowlist, tool versions, sanitized symptoms and separate test mandate. **Output:** `status, artifacts, issues, next_action`, plus `maintenance-proposal.schema.json` candidate reference. A textual claim of PASS is never test evidence.

**Allowed operations (MCP only):** constrained workspace read/write restricted to a candidate worktree's non-protected source, code formatting and isolated compilation/test execution with bounded logs; submit a candidate patch/ref for *independent* CRE evaluation. If a new MCP adapter is needed, create an OSS allowlisted wrapper with canonical path checks, argv allowlists, timeout/memory limits, host UID isolation and secret scrubbing.

**Always forbidden:** write to 004 holdouts, `tests/reliability/**`, signed archives, `config/factory/*policy*`, checklists, constitution, approved requirements or `evidence/**`; alter baseline results, change quality thresholds, delete negative tests, grant itself MCP permissions, change model providers, use unrestricted shell or possess GitHub/operator tokens. Broker alone may open a reviewable PR after independent gates.

**Independent evaluator:** invoke existing `forge_factory.reliability.promotion.evaluate` via a protected deterministic service, with baseline-vs-candidate reproducer, frozen prevention suite, golden and holdout cases and policy integrity. Result `ELIGIBLE_FOR_OFFLINE_REVIEW` permits a proposal PR **only**, never deployment.

**Negative tests:** malicious code in untrusted issue details, symlink/path traversal, writing a holdout file, attempted credential access, forged runner PASS, reverted previous fix, no working reproducer, patch requesting self-merge. Fail closed, audit, quarantine.

## Token-efficiency and separation rules

- Keep tool output excerpts <= existing configured `max_mcp_output_bytes`; return artifact pointers for full reports.
- Each new inference call is budgeted cumulatively at order level and individual role level; model weights and availability are runtime concerns, not a guarantee.
- The controller and policy validator are deterministic services without SKILL or model calls; do not disguise them as LLM agents.
- Existing SWE authors may execute only product-draft work in bounded workspaces, with separate inspector role and frozen revision. Maintainer may prepare a factory source patch, never adjudicate its own tests or promote it.
