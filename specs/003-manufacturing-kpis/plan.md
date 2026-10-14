# Implementation Plan — Forge-C Manufacturing KPIs (Feature 003)

**Version:** 0.5.0 · **Status:** proposed; code not implemented
**Execution by:** Claude Code, using Spec Kit; factory runtime remains OSS Fabro + Qwen local.

## Architecture

```text
Fabro stage events + MCP tool results + inspection verdicts + supervisor incidents
                           |
                    Typed event ledger
             (schema v0.4; append-only)
                           |
             Deterministic KPI Aggregator
                (no LLM and no shell)
                           |
          Versioned SQLite aggregates / snapshots
           |                  |                 |
    Dashboard REST/SSE    Observer MCP      Release Manager
    KPI / production UI  read-only metrics  Offline evidence ZIP
```

**Data flow:** metrics are *derived* from authoritative records; agent-authored status is never the source of pass/fail, coverage or size numbers. Use the existing typed event store and dashboard; don't build a second overlapping telemetry infrastructure. Add a read-only `get_kpis`/`get_kpi_evidence` entry point to `forge-observer-mcp`, with minimum necessary result output and policy scopes.

## Work breakdown and ordering

- **K0 — Dictionary and contracts (after baseline M0; parallel to M6):** canonical production units, event taxonomy, all 20 KPI definitions with numerator/denominator, unit, comparability dimensions, formula version, samples and missing-data status. Add JSON schema and policy file. Accept only validated emitted event types.
- **K1 — Metrics engine (after 002 M6 event storage):** implement pure deterministic, incremental + full replay aggregation, idempotent event handling, immutable first-pass history, phase/driver segmentation, percentile functions, snapshots and frozen performance baseline versioning. No model invocation.
- **K2 — Dashboard panels and MCP (after K1):** production overview, SWE station FPY funnel, finding/rework Pareto, resource/token efficiency, outage/self-heal, compliance and footprint panels. Trace correlation links and role-scoped read-only observer MCP.
- **K3 — Offline evidence (after K1 + original M7 packager):** include KPI snapshots/catalog/baseline hashes, numerator/denominator, missing data, alert breaches and provenance in READY and BLOCKED packages; avoid derived values inconsistent with final review manifest.
- **K4 — Fault injection + tuning (after K1–K3):** replay/duplicates, restart, stalled and sparse telemetry, resource unknown, no completed packages, faked AI success, invalid inspection revision, baseline mismatch, blocked run, repair incident, leaked false pass. Pilot measurement-only baseline; no KPI auto-tuning of safety rules.

### Event vocabulary to implement (not assumed available)

- `work_order.admitted`, `work_order.closed` with `run_id`, `order_id`, target, complexity, safety scope, creation timestamp.
- `stage.started`, `stage.paused`, `stage.resumed`, `stage.completed` plus `stage_kind`, work order, monotonic duration or timestamp source.
- `inspection.completed` with inspection_id, phase, revision digest, sequence (=1 for initial), checklist/version, machine-verified outcome.
- `finding.recorded`, `finding.resolved` with detected phase, adjudicated origin phase, category, severity, duration/effort origin.
- `quality_gate.evaluated` with gate id, version and signed tool-produced evidence reference.
- `artifact.evidence_validated`, `requirements.verification_recorded`, `traceability.link_verified`, `misra.rule_assessed`.
- `firmware.footprint_measured` with target and compile configuration, measurement method, units, budget version.
- `agent.usage_recorded` with measured/estimated/unknown status; `incident.detected`, `incident.resolved`, `repair.completed`.
- `package.sealed` with state READY or BLOCKED, deterministic package fingerprint, no AI-created sign-off.

### Essential integration boundaries

- Integrate with existing `002` contract `event.schema.json`, not a second source-of-truth.
- Reuse `forge-observer-mcp` and dashboard API; operations are read-only and opt-in for AI, never model-run on a healthy poll.
- Validate KPI formula changes in version-controlled review with migration and historical comparability notice.
- For SFOEE, compute only if the eligible planned window, matched class baseline and complete first-pass outcome data exist; otherwise not computable.
- All breakdowns preserve confidentiality: do not expose raw prompts, hidden reasoning, secrets or unsanitized driver source to dashboard users.

## Deliverables

1. Metric registry, frozen baseline policy and quality flags.
2. KPI aggregation service + replay engine, unit/integration tests and benchmark fixtures.
3. Dashboard KPI route/components with filters and trace evidence drilldown.
4. Observer MCP read-only operations + enforcement tests.
5. Immutable `kpi-snapshot.json` and trace provenance in offline package.
6. Updated Spec Kit traceability across new KPI-FR-001–018 to KPI tasks and tests.

## Definition of done

The 20 catalog metrics are implemented or explicitly `NOT_COMPUTABLE` with evidence, source events are replay-idempotent, aggregate views reconcile with archived raw events, no KPI service calls a model, no safety gate can be weakened by dashboards/agents, and both READY/BLOCKED packages export KPI definitions and evidence. Numeric dashboard values MUST originate from deterministic events, not claimed by an agent.
