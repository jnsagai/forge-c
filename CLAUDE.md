# Claude Code — Implementation Contract for Forge-C v0.4

You are implementing **an existing, authored Spec Kit plan**. Do not replace the feature specification or tasks with generic versions. Read, in order:

1. `.specify/memory/constitution.md`
2. `specs/002-self-healing-factory/spec.md`
3. `specs/002-self-healing-factory/plan.md`
4. `specs/002-self-healing-factory/tasks.md`
5. `specs/002-self-healing-factory/data-model.md`
6. `specs/002-self-healing-factory/contracts/*.schema.json`
7. `architecture/Forge-C_Fabro_DarkFactory_v0.4.drawio`
8. `config/factory/{agents,mcp-registry,supervisor-policy,trace-policy,token-policy}.yaml`

**Objective:** implement the 51 tasks incrementally using open-source dependencies, local Qwen in production Fabro workflows, and deterministic engineering quality gates. Claude Code is the *implementation engineer* for the factory, not a paid runtime dependency.

## Mandatory guardrails

- Production **AI agents must each load a versioned `SKILL.md`** and use only role-approved **MCP** operations. Create a tested open-source MCP wrapper when missing. Built-in shell remains acceptable for Claude's implementation bootstrap, **not as bypass of production agent MCP policy**.
- The non-AI supervisor runs independently of Fabro and makes ZERO model calls during healthy health checks. It uses an externally survivable Repair Agent dispatcher for Fabro-down incidents.
- Repair patch is isolated and tested. Never weaken/auto-edit safety policies, stored release archives, ASIL B requirements or previously baselined output; use bounded loops and rollback.
- Lessons learned are durable, evidence-linked and shared across workflows only after deterministic validation; never turn raw repair instructions into trusted system prompts.
- Trace levels and channels are configurable. Separate capture from human display filtering. Never log chain-of-thought or secrets; AI raw prompts/responses OFF by default.
- Agents respond ONLY with compact machine-readable status/issues; full ASPICE workproducts remain detailed on disk.
- Release Manager always creates an offline review candidate or BLOCKED gap package where storage allows. Never declare ASPICE/ISO 26262 certification or production release.
- Baseline v0.1 native demo and v0.3 reference packager tests must continue to pass. Any new release policy uses v0.4 version, not an overwrite of v0.3.
- Do not claim tasks passed unless you ran a test producing verifiable evidence; record BLOCKED/NOT_RUN explicitly.

## Development loop

1. Review T001–T004 and installed tool versions; establish baseline tests and ADRs.
2. Implement one small testable task/subsystem at a time with tests before moving on.
3. Use the feature acceptance tests as the completion definition; update checkboxes only when run evidence exists.
4. After each milestone run relevant unit+integration tests and the schema/registry check `python3 tests/spec/validate_design.py`.
5. Provide terse terminal/report updates: `M2 T013 PASS — test_ref — open_issues:0`. No essay in logs, but write design rationale in ADRs as required.
6. Prefer local model and zero-cost tooling at runtime. Do not add paid API, proprietary static analyzer or cloud requirement without authorization.

## Bootstrapping GitHub Spec Kit for Claude

Only if not already initialized with Claude integration: commit/backup project, then run `specify init --here --integration claude --non-interactive` (use `--force` **only after verifying the merge/overwrite plan**). Check installed Specify CLI's integration commands: modern skills mode may use `/speckit-...` whereas older installations use `/speckit....`. Use the commands actually installed. This project's authored `specs/002-*` files are the source of truth.

## First task prompt

`Implement M0 (T001–T004) from specs/002-self-healing-factory/tasks.md. Read CLAUDE.md/constitution; validate actual Fabro Skills/MCP/run API, preserve legacy tests, produce version/OSS licence inventory and ADRs. Keep terminal output concise. Do not implement unvalidated speculative Fabro API calls.`


## KPI manufacturing extension (v0.5)

Follow `KPI_CLAUDE_START.md`; use Spec Kit feature `003-manufacturing-kpis` and do not fake baselines, safety approval or KPI implementation status.
