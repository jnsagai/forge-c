# ADR-0002 — Fabro 0.362 capability audit (verified, not assumed)

- **Status:** Accepted · **Tasks:** T004 (feeds T007, T018, T023, T034, T044, T046, T048)
- **Evidence:** `evidence/v0.4/runs/T004/`, `evidence/v0.4/fabro-audit/fabro-0.362.0-openapi.json`,
  `factory/python/tests/fixtures/fabro-0.362-probe-*.jsonl`
- **Docs pinned to commit:** `a192bce20e063093417050792d49e457eea9b791`

## Verified on the installed server (live probe run, `test_live_probe_against_installed_fabro`)
| Capability | Result | How Forge-C uses it |
|---|---|---|
| Isolated server | `fabro server start --config <file> --storage-dir <dir>`; requires `[server.auth] methods=["dev-token"]` and `SESSION_SECRET`/`FABRO_DEV_TOKEN` in `<storage>/server.env` | Forge-C server on `127.0.0.1:32290`, storage on data volume; CLI uses an isolated `HOME` |
| Local model | Built-in `ollama` provider, overridable `base_url`; `fabro model test` ok | Routed via the Forge-C LLM gateway (ADR-0003) |
| Skills | Auto-discovery of all `{git_root}/.fabro/skills/*/SKILL.md`; `use_skill` tool; events `agent.skills.discovered`, `agent.skill.activated` | All 20 role skills are listed to every agent (≈506 tokens); role binding enforced by hook (below) |
| MCP | `[run.agent.mcps.<name>]` `type="stdio"`, `command=[…]`, `env`, timeouts; tools named `mcp__<server>__<tool>`; event `agent.mcp.server.ready` | Forge domain MCP servers are launched per run from generated config (T018) |
| Hooks | `[[run.hooks]] event="pre_tool_use" script=… blocking=true sandbox=false`; host hook gets full JSON context on stdin incl. `tool_name`, `tool_input`, `node_id`, `run_id`; exit 2 / `{"decision":"block"}` denies; **command hooks fail closed** | Deterministic role/phase authorization gate for *all* tools incl. native shell/file tools (T007) |
| Events/API | `GET /api/v1/runs/{id}/events?since_seq&limit` (monotonic `seq`), SSE `/attach?since_seq`, `/usage` (reported tokens), `/cancel`, `/system/info` | Idempotent collector (T034), token metrics (T041), supervisor probes (T021) |
| Loops | DOT `max_visits`, conditional edges `condition="outcome=…"`, `goal_gate=true` | Bounded SWE inspection loops (T009/T047) |

## Verified limitations (design must compensate)
1. **Native tools are always registered** (`shell`, `read_file`, `write_file`, `edit_file`, `grep`,
   `glob`, sub-agent tools) and workflow agents run auto-approved. MCP availability does not disable
   them → enforcement by the blocking host `pre_tool_use` hook + OS-level path permissions.
2. **A failed MCP server is skipped and the session continues** → Forge-C preflight (T018) must fail
   closed before launching agents.
3. **A failed stage followed by an unconditional edge still yields `run.completed status=succeeded`**
   (observed in the first probe) → Forge-C never trusts Fabro run status alone; workflows use
   `goal_gate`/conditional routing and an external finalizer reads stage outcomes (T046).
4. **Provider `reasoning` output is persisted in `agent.message` events** (observed with Qwen3) →
   all model traffic goes through the no-reasoning gateway (ADR-0003).
5. Prompt/agent hooks *fail open* → never used for policy. Only command hooks are used.
6. Skills cannot be scoped per node via documented config; the hook denies `use_skill` for any skill
   other than the node's bound role.
7. Skill discovery requires the run target to be the git root containing `.fabro/skills`.
