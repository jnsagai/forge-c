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
