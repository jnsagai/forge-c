# ADR-0011: Codex (ChatGPT login) as SWE author via ACP, under the factory policy

- Status: accepted (owner decision 2026-10-18, option 3)
- Context: HAL pilot yield with DeepSeek flash was 0/5 on a frozen revision; the owner asked to compare a stronger
  model, Codex `gpt-6.1-sol` with high reasoning effort, using their ChatGPT/Codex subscription (no OpenAI API key).

## Problem

Fabro 0.362 can drive an external agent through its ACP backend (`backend="acp"`). A probe on 2026-10-18 showed that
for an ACP node:

- the factory's `pre_tool_use` policy hook does not fire;
- the run's MCP servers are not exposed to the agent;
- Fabro, as the ACP client, let the agent write a file although the agent ran in read-only mode.

Running factory nodes that way would break CLAUDE.md's guardrail: production agents use only role-approved MCP
operations behind the policy gate.

## Decision

Author roles can run on Codex through a factory-owned chain that restores the gate:

```
Fabro (ACP client) -> forge_factory.acp.proxy -> codex-acp 2.1.1 -> Codex 0.162.1 (pinned copy)
                                                   tools: forge_factory.acp.gate (MCP, one per server)
```

1. **Codex profile** (`acp/codex_home.py`):
   - an isolated `CODEX_HOME` with a factory config only, so personal hooks, plugins and MCP servers never load;
   - read-only sandbox, `web_search = "disabled"`, no history;
   - every Codex feature that acts outside MCP is turned off: shell, unified exec, browser and computer use, apps,
     plugins, sub-agents, image tools, worktrees and others.
   - `code_mode_host` stays on, because Codex 0.162 runs all tool calls through it. Its JavaScript sandbox has no file
     system, no `fetch` and no `child_process` (probe-verified).
2. **Gate** (`acp/gate.py`):
   - the only tools Codex has: `forge_fs` (Fabro-native-equivalent `read_file`, `read_many_files`, `glob`, `grep`,
     `list_dir`, `write_file`, `edit_file`, `use_skill`, `update_plan`) and the run's forge MCP operations;
   - every call goes through `policy.fabro_hook.handle` with the hook's context (role grants, path scopes, protected
     paths, per-visit turn budget), is audited, and forge MCP calls are ticketed before `sdk.invoke`;
   - fail closed.
   - Servers are declared in the Codex session config with `default_tools_approval_mode = "approve"`. The gate is
     the decision point, and codex-acp 2.1.1 cannot relay Codex's MCP approval question.
3. **Proxy** (`acp/proxy.py`):
   - strips the client's fs and terminal capabilities;
   - drops client-supplied MCP servers;
   - denies every agent-to-client request, including permission requests for edits and commands, without
     forwarding it;
   - prepends a short tool note to prompts.
4. **Work order** (`--acp-authors codex`):
   - author nodes get `backend="acp"` and `acp.command`; inspectors and all other nodes stay on the run model
     (DeepSeek). That gives author/inspector model diversity, and the independence attestation becomes SUPPORTED
     instead of PARTIAL.
   - The model profile records the Codex nodes.
   - Launch is refused if the factory Codex home is not logged in.

## Consequences

- **Evidence:** a Fabro end-to-end adversarial probe gave
  - in-scope read and write ALLOW;
  - out-of-scope write WRITE_SCOPE_DENIED;
  - shell and web search unavailable;
  - un-granted MCP operation MCP_TOOL_NOT_GRANTED;
  - only the in-scope file was written.

  Unit tests cover the gate, the proxy and graph conversion.
- **Not covered:**
  - Codex token usage is not reported to Fabro, so the token-budget check does not apply to ACP nodes, and the
    DeepSeek cost cap does not cover Codex: usage counts against the owner's ChatGPT plan.
  - Fabro's ACP backend still does not run hooks for ACP agents. The guarantee rests on the proxy and the gates, and
    on the pinned Codex and codex-acp versions; an upgrade needs the probe again.
- **Login:** the factory `CODEX_HOME` needs its own login (`CODEX_HOME=<home> codex login`). Linking the owner's
  `auth.json` is for short probes only: a token refresh could rotate the shared refresh token.
- No model gets any approval authority. This is an engineering comparison, not a qualification of Codex as a tool
  under ISO 26262.
