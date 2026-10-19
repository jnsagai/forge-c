# Implementation Plan: Factory KPI Control Room

**Branch**: `feat/007-kpi-control-room` | **Date**: 2026-10-19 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/007-kpi-control-room/spec.md`

## Summary

A manager-facing "Control Room" page and a read-only API, added to the existing local dashboard. A new model-free
package, `forge_factory.controlroom`, derives everything from records the factory already writes:

- **Live floor state:** work-order manifests, per-workspace gate logs, Fabro run status and finalized packages;
- **Scorecards:** the feature-003 KPI engine run over the shift/day windows and their previous periods;
- **Quality:** SPC limits and a Pareto of failure reasons;
- **Usage and cost:** model usage from Fabro, plus ACP usage newly recorded by the forge ACP proxy;
- **Alerts:** deterministic alert conditions.

A single server-sent-event stream pushes floor changes within seconds. The page is static HTML/JS with inline SVG
charts: no build step, no chart library, no new runtime dependency.

## Technical Context

**Language/Version**: Python 3.12 (factory venv), browser JavaScript (ES2020, no transpiler)

**Primary Dependencies**:
- **Existing:** FastAPI, uvicorn and Starlette `StreamingResponse` (SSE), PyYAML, jsonschema.
- **New:** none. Charts are hand-written inline SVG.

**Storage**: none new. Everything is derived from existing records:
- `state/workorders/*/workspace`: `.forge-run/manifest.json`, `.forge-run/gates/gate-log.jsonl`,
  `.forge-run/fabro_run_id`, `.forge-run/model-profile.json`, `.forge-run/acp/*.proxy.jsonl`;
- the release package records;
- the CRE reliability store;
- the AFO store.

Derived state lives in an in-process cache keyed by file size/mtime. Alert acknowledgements are per viewer, in
browser storage only (FR-018).

**Testing**:
- pytest for unit tests (fixture workspaces) and API tests (FastAPI TestClient);
- replay and idempotence tests;
- an SSE latency test (SC-001);
- a layout check at 390 px with the headless browser if one is available, otherwise a recorded NOT_RUN.

**Target Platform**: Linux host, served on 127.0.0.1 by the existing dashboard process (port 8765).

**Project Type**: web service + static page inside the existing `forge_factory.dashboard` app.

**Performance Goals**:
- floor change visible within 5 s for at least 95 % of events (SC-001);
- floor snapshot computed in under 300 ms for 200 workspaces;
- scorecard in under 2 s, cached for 30 s like the existing KPI cache.

**Constraints**:
- zero model calls (constitution VI, SC-007);
- read-only, no new control action;
- loopback only;
- NOT_MEASURED instead of any default value;
- no horizontal scroll at 390 px.

**Scale/Scope**:
- hundreds of work orders and a few concurrent;
- one manager viewer, a few browser tabs;
- 30–90 days of history.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | How this feature complies | Status |
|---|---|---|
| I. Safety and correctness precede optimization | Gate decisions are displayed, never computed or altered. A safety or process violation forces a non-green summary and cannot be filtered (FR-017). Throughput/OEE never mask a gate. | PASS |
| II. Evidence driven | Every value carries its sample size, formula version and evidence references (FR-007, FR-019). The scorecard is checked against the KPI engine on a frozen event set (SC-003). | PASS |
| III. External release authority | No approval, release or routing action is added (FR-020). Package states are read from sealed records. | PASS |
| IV. AI roles require SKILLs | No AI role is added. | N/A |
| V. AI tool calls use MCP | No agent tool is added. The ACP proxy change only records usage counts. Gate and policy logic are untouched. | PASS |
| VI. Model-free supervision | All aggregation is deterministic Python. The healthy dashboard path makes zero model calls (SC-007 test). | PASS |
| VII. Evidence-based shared knowledge | Not affected. | N/A |
| VIII. Observable, privacy-preserving traces | Display filters change presentation only. The proxy usage record holds token counts and model IDs, never prompt or response content. Security/audit channels keep their role restrictions. | PASS |
| IX. Minimal model cost | Usage visibility per model and per READY unit. Unreported usage is shown as such, never as zero. | PASS |
| X. Open-source-first | No new dependency or service. Charts are inline SVG. No compliance claim (FR-025). | PASS |

The CRE rule (every factory change goes through a CHANGE promotion gate) applies to the ACP proxy usage
recording and to the dashboard changes. They are promoted with `--kind CHANGE` before merge.

**Post-design re-check (after Phase 1):** PASS. The design adds no writer to any factory store; the only new
writes are the proxy's usage lines in `.forge-run/acp/<node>.proxy.jsonl` (counts only).

## Project Structure

### Documentation (this feature)

```text
specs/007-kpi-control-room/
├── spec.md
├── plan.md              # this file
├── research.md          # Phase 0
├── data-model.md        # Phase 1
├── quickstart.md        # Phase 1
├── contracts/
│   ├── control-room-api.openapi.yaml
│   ├── floor-snapshot.schema.json
│   └── controlroom-config.schema.json
├── checklists/requirements.md
└── tasks.md             # Phase 2 (/speckit-tasks)
```

### Source Code (repository root)

```text
factory/python/forge_factory/
├── controlroom/                 # NEW, model-free
│   ├── __init__.py
│   ├── config.py                # shifts, time zone, thresholds, staleness, price table (config/factory/controlroom.yaml)
│   ├── floor.py                 # live floor: units, stations, andon derivation, incremental gate-log reader
│   ├── windows.py               # shift/day/7d/30d/custom windows + previous period, local time zone, DST-safe
│   ├── scorecard.py             # KPI-engine snapshot per window + floor counts (started, READY, BLOCKED, WIP)
│   ├── spc.py                   # I-MR and p-chart limits, run rules, minimum sample
│   ├── pareto.py                # failure/block reasons per station from gate logs + CRE failure modes
│   ├── usage.py                 # per run/station/role/model usage: Fabro (native) + ACP proxy records; cost
│   ├── alerts.py                # deterministic alert conditions with stable IDs
│   └── export.py                # CSV/JSON export with evidence refs
├── acp/proxy.py                 # CHANGED: record prompt-result usage counts per node visit (no content)
├── release/finalize.py          # CHANGED: token_usage tolerates ACP stages (model null) instead of failing
└── dashboard/
    ├── app.py                   # CHANGED: /control-room page + /api/v1/control-room/* + SSE stream
    └── static/control-room.html # NEW: Control Room page (vanilla JS, inline SVG, responsive)

config/factory/controlroom.yaml  # NEW: defaults (one 24 h shift in the host time zone), thresholds, price table

factory/python/tests/
├── test_controlroom_floor.py
├── test_controlroom_scorecard.py
├── test_controlroom_spc_pareto.py
├── test_controlroom_usage.py
├── test_controlroom_alerts.py
└── test_controlroom_api.py      # TestClient: auth, read-only, SSE latency, export, idempotence, no model calls
```

**Structure Decision**: extend the existing single Python project. The Control Room is a new package used by
the existing dashboard app, so auth, roles, loopback binding, the collector and the KPI cache are reused. No
second web server and no frontend build.

## Complexity Tracking

No constitution violations to justify.
