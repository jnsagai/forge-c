# Verified upstream integration points and design assumptions (2026-10-14)

## Upstream facts

- Fabro is an MIT-licensed OSS dark software factory. Workflows are `.fabro` Graphviz DOT. The runtime has tools, token/turn limits, stages and loop handling: https://github.com/fabro-sh/fabro ; https://github.com/fabro-sh/fabro/blob/main/docs/public/core-concepts/workflows.mdx
- Fabro supports Open Agent Skills using `.fabro/skills/<name>/SKILL.md` and `use_skill`; there is a skill discovery lifecycle: https://github.com/fabro-sh/fabro/blob/main/docs/public/agents/skills.mdx
- Fabro can consume MCP servers using `~/.fabro/settings.toml` or `[run.agent.mcps.<name>]` in run TOML, and exposes run-management as an MCP server for Claude: https://github.com/fabro-sh/fabro/blob/main/docs/public/agents/mcp.mdx
- Fabro provides run events and API; exact structure must be pinned to installed commit/version: https://github.com/fabro-sh/fabro/blob/main/docs/internal/events-strategy.md
- GitHub Spec Kit supports Claude Code integration (`specify init --here --integration claude`), with skill-based workflow actions: https://github.com/github/spec-kit/blob/main/docs/installation.md ; https://github.com/github/spec-kit/blob/main/docs/reference/integrations.md

## Not verified/NOT claimed

- No assumption that every CLI tool has an upstream MCP server. All wrappers in the design are **new engineering tasks**.
- No assumption that Fabro provides an external model-free health supervisor, automated self-repair or a dashboard with the requested human/tool/AI per-channel filters.
- No claim that a `finally` block or `try/catch` exists in Fabro DOT; implement end-stage join or external finalizer after verifying runtime.
- No claim that a newly written adapter, skill or inspect-agent configuration is production-ready, validated in Fabro, ISO 26262 qualified or MISRA-compliant.
- Fabro's own dashboard may already cover some run screens. Reuse it where possible; implement only the missing cross-component/fault/trace controls, with a stable API adapter.

## ADR topics Claude must resolve

1. Stable Fabro run-event API version and consuming mechanism.
2. Repair dispatch transport when Fabro process is down.
3. MCP SDK/library and STDIO vs local Streamable HTTP in Ubuntu.
4. Safe process sandbox / systemd restrictions and atomic repair promotion.
5. Event/incident database schema, migration and retention defaults.
6. Source-of-truth for raw traces and hashed evidence export.
7. One authenticated dashboard frontend vs Fabro UI extension.
8. Local model licensing/versions, max context capacity, GPU sharing on 8 GB VRAM.
9. OSS analysis tools limitations, MISRA coverage matrix, target-vs-host evidence.
