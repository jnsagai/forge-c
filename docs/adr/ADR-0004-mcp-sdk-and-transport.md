# ADR-0004 — MCP SDK and transport

- **Status:** Accepted · **Tasks:** T011–T018 · **FR:** FR-004–FR-006
## Decision
Python MCP SDK **2.3.0** (`mcp.server.mcpserver.MCPServer`, MIT) over **stdio**, one process per Forge
domain server per agent session, launched by Fabro from generated `[run.agent.mcps.*]` entries.
stdio needs no listening port, inherits the per-run environment (`FORGE_ROLE`, `FORGE_PHASE`,
`FORGE_RUN_ID`) and dies with the session. Every domain server enforces role grants itself (defence in
depth with the Fabro hook), validates JSON input against the declared schema, and returns the
`tool-result.schema.json` envelope bounded to `max_tool_result_bytes`.
## Verified
Round-trip handshake (`initialize` protocol `2025-11-25`), `tools/list`, schema rejection of bad
arguments, and Fabro-launched stdio server call (T004 probe).
