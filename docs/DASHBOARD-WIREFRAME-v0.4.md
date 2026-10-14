# Human supervisor dashboard — product requirements

**Role:** authenticated, read-only human observer. Normal run never stops for interactive approval. Emergency stop/administrative actions, if implemented later, use separate authenticated controls and are not part of this v0.4 run contract.

## Main view (desktop and mobile)

- Header: factory status, Fabro process health, last successful deterministic supervisor poll, current run, package status, run elapsed time, storage alert, local model readiness.
- Run timeline: intake, SWE.1–SWE.6 author/checklist-inspector gates, optimization, release packaging. Each stage displays run ID, revision hash, elapsed time, retry count, open blockers.
- Infrastructure: MCP server/operation readiness, delayed agents, tool versions, CPU/RAM/GPU memory, disk free, DB and dashboard health.
- Incidents: new/eligible/repairing/validated/rolled-back/offline-attention status, timestamps, repair attempt, patch hash, matched lessons, deterministic checks.
- Evidence: workproduct refs, outstanding missing items, readiness state and ZIP manifest link.
- Metrics: tokens in/out per role/run/tool; context length and tool output payload bytes. Unknown model usage is explicitly `unknown`, not zero.

## Viewer-configurable traces

A visible channel multi-select with `HUMAN`, `WORKFLOW`, `TOOLS`, `AI`, `SUPERVISOR`, `REPAIR`, `SECURITY`, `AUDIT`, `METRICS`, `KNOWLEDGE`; native selection is case-insensitive but persisted to standardized lowercase event categories. Additional independent controls: minimum severity, run/phase/agent, text search, time window, saved view presets. Default channels `human`, `workflow`, `supervisor` and severity `INFO`.

The trace capture configuration (`config/factory/trace-policy.yaml`) is **not** changed by dashboard filters. Mandatory audit/security capture cannot be switched off. Show redacted sanitized tool-call arguments and evidence links; full logs available via authenticated artifact viewer. AI category logs tool status, model routing, metadata and token accounting; it must never collect hidden chain-of-thought. Raw prompt/output storage is OFF by default, even at TRACE.

## Data flow and API

Typed events → redaction → validation → SQLite WAL/JSONL (hashed retained raw artifacts) → paginated API → SSE with poll fallback. Viewer receives auth-protected summaries, not local DB or direct unchecked file paths. All operational events carry run_id, stage_id where applicable, agent_id where applicable, category, severity, event_id, timestamp and correlation ID. Dashboard is only one consumer, not a precondition for factory progress.

## Baseline nonfunctional targets

- New persisted event visible <5 seconds while UI connection healthy.
- Supports mobile 320px without invisible filters or horizontal page overflow.
- Display filter change does not affect capture/retention of previous or future events.
- Tamper test: no secret appears in query results/export even if injected in original model or tool result.
- Access and UI test: an authenticated observer cannot mutate workflows through the read-only dashboard API.
