# ADR-0012: Claude (owner account) for inspectors and the Release Manager via ACP, under the factory policy

- Status: accepted (owner decision OD-2026-10-19-08)
- Context: since OD-2026-10-19-06 the author roles run on Codex Sol 6.1 and every other agent node on DeepSeek flash.
  The owner asked that the "different model" (the non-author nodes) use Claude from now on, through the owner's
  Claude account and not the paid Anthropic API. Model: `claude-opus-5` (owner choice; Fabro's catalogue of
  2026-09-20 has no 5.5 IDs).

## Decision

The non-author agent nodes (every `*-inspector` role and `release-manager`) can run on Claude through the same
factory chain as the Codex authors (ADR-0011), so the policy gate stays the only tool path:

```
Fabro (ACP client) -> forge_factory.acp.proxy --agent claude -> claude-agent-acp 0.85.1 (pinned, Apache-2.0)
                                                   tools: forge_factory.acp.gate (MCP, one per server)
```

1. **Login** (`acp/claude_home.py`): an isolated `CLAUDE_CONFIG_DIR` (`<data_root>/claude-home`, mode 0700) holding
   only the owner's account login (`CLAUDE_CONFIG_DIR=<it> claude auth login`). The owner's `~/.claude` is never
   read or linked. API credentials (`ANTHROPIC_API_KEY`, `ANTHROPIC_AUTH_TOKEN`, `CLAUDE_CODE_OAUTH_TOKEN`, base-URL
   and Bedrock/Vertex switches) are removed from the agent environment.
2. **Session** (`session/new` rewritten by the proxy):
   - `mcpServers` = the gate servers only (forge_fs + the run's forge MCP servers); the client's servers are dropped;
   - `_meta.claudeCode.options`: `tools: []` (no built-in tool: no shell, file, web, sub-agent or ToolSearch tool),
     `settingSources: []` (no settings, hooks, CLAUDE.md or memory files load), `strictMcpConfig`, `model`,
     `allowedTools: ["mcp__<gate server>", ...]` (the gate decides each call, so Claude asks no permission),
     `ENABLE_TOOL_SEARCH=false` (MCP tools always loaded, since ToolSearch is off).
3. **Unchanged from ADR-0011:** client fs/terminal capabilities stripped; every agent->client request denied (a
   permission request with its reject option, CAPA-049); the tool note prepended and the reply rule appended
   (CAPA-045); proxy and gate logs under `.forge-run/acp/`.
4. **Work order:** `--acp-inspectors claude` converts the non-author nodes; deterministic script nodes are unchanged.
   The model profile records `acp_inspectors` (nodes, model, provider, adapter) and the independence attestation
   uses it for the inspector side.

## Evidence

Live probe 2026-10-19 (real adapter, owner login, `swe3-inspector` binding): the model was `claude-opus-5`; Claude's
only tools were the nine `mcp__forge_fs__*` tools; a workspace read was ALLOW_READ, a read of `/etc/hostname`
PATH_OUTSIDE_WORKSPACE, a write READONLY_ROLE_WRITE_DENIED (no file written); Claude reported no shell.
`evidence/v0.4/runs/ACP-CLAUDE-PROBE/probe.json`.

## Consequences

- Inspections now use a different model family and provider from the Codex authors, which strengthens the
  independence attestation.
- Usage counts against the owner's Claude plan limits; a rate-limited session fails the node like any agent error.
- An adapter or Claude Code upgrade needs the probe again. The AFO profiles are unchanged (separate owner decision).
- No model gets any approval authority. This is an engineering choice, not a qualification of Claude as a tool under
  ISO 26262.
