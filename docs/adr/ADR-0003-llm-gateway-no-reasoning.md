# ADR-0003 — Local LLM gateway: no hidden reasoning, reported token metering

- **Status:** Accepted · **Tasks:** T004, T036, T041 · **FR:** FR-025, FR-029
## Context
Qwen3 on Ollama thinks by default; Fabro 0.362 stores the returned `reasoning` text in run events and,
when the first turn carried reasoning, the follow-up request failed with
`model ollama/qwen3:8b does not support reasoning`.
## Decision
`forge_factory.llm_gateway` (FastAPI, loopback `:11436`) sits between Fabro and Ollama. It forces
`reasoning_effort="none"`, strips `reasoning*`/`thinking` keys from requests, responses and stream
deltas, and appends provider-reported usage (`basis=reported`, else `unknown`) to
`$FORGE_STATE_DIR/llm-gateway/usage.jsonl`. It makes no model calls itself and holds no credentials.
Fabro's `ollama` provider `base_url` points to the gateway with `reasoning_by_default=false`.
## Evidence
`factory/python/tests/test_llm_gateway.py` (mock upstream with canary reasoning text) and the live
T004 probe: zero `reasoning` fields in `agent.message` events after routing.
## Addendum (2026-10-15) — role-scoped tool offering
To keep the 8B model's 24k context and its tool choice focused, the gateway also narrows the `tools` list
offered to the model. It does this when a user or system message contains `skill_name <agent-id>`. It keeps
that role's granted MCP tools plus the safe native tools. This is an *offering* optimisation only. It is not
a security control: authorization stays in the fail-closed `pre_tool_use` hook (T007), which every call
passes through regardless of what was offered. Infrastructure probes that must offer denied tools to prove
the hook denies them (the T004 probe) therefore name the skill without the `skill_name <id>` phrase.
