# Factory Production Dashboard — v0.5 proposed panels

> **Implemented manager view:** the Control Room (feature 007), at `/control-room`. See [CONTROL-ROOM.md](CONTROL-ROOM.md).

## Level 1: Executive production board (default)

- Tiles: **SFOEE** (A×P×Q, or N/A), **READY packages / 7d**, **Station FPY / SWE1..6**, **p95 Lead Time**, **Blocking findings**, **Tokens per READY package**.
- Always-visible status: `READY_FOR_OFFLINE_REVIEW` and `BLOCKED` counts; critical safety/quality violations are separate and cannot be hidden in SFOEE.
- Filters: window, target MCU, driver class/complexity, optimization configuration, safety profile, toolchain revision, model and run status.

## Level 2: Factory manufacturing stations

Pipeline WIP with station queues, cycle and wait times; six independent FPY and rework rates; Pareto of defects by origin/category; first-pass result is immutable; downstream leakage drilldown.

## Level 3: Quality, footprint, safety evidence

Requirement verification, traceability consistency and evidence completeness with denominators; MISRA assessed/unassessed rule sets; statement/branch/MC/DC with host vs target, applicable objectives and measured methods. Flash/RAM/stack/budget margins plus CPU/WCET estimates for the same pinned compiler/profile. Red hard-gate failures cannot be masked by green operational metrics.

## Level 4: AI and factory reliability

Token usage by stage/agent/model and tokens per READY output; CPU/GPU/VRAM and inference latency; run heartbeats, failed MCP calls, MTTR, incidents vs resolutions, autonomous repair rate and recurrence. Distinguish real measurements from estimates and unknown.

## Level 5: Trace / audit drilldown

Every KPI chart point links back to run ID, event IDs, affected SWE phase, tool result artifact hashes and review checklists. Existing dashboard trace toggles filter *presentation*, not capture. Audit/security remain non-disableable. Allow CSV/JSON export of calculated metric values and evidence refs; offline package retains versioned frozen KPI snapshot regardless of UI filters.

## UI design constraints

The dashboard may use FastAPI/SSE and local SQLite already specified in v0.4. Do not add paid SaaS or duplicate collector. Where relevant, instrumentation should align with OpenTelemetry/Prometheus conventions, keeping high-cardinality run/driver identifiers out of Prometheus labels. Default model-free aggregation and one-second-to-five-second refresh goal for persisted event state are proposals to validate, not prior implementation claims.
