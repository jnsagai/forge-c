# Tasks: Factory KPI Control Room

**Input**: Design documents from `specs/007-kpi-control-room/` (spec.md, plan.md, research.md, data-model.md,
contracts/, quickstart.md)

**Tests**: required. The constitution (II) and CLAUDE.md say a task is complete only with verifiable test
evidence, so every story has its tests.

**Completion rule**: tick a box only after the named test or check has run and passed, with the evidence path
recorded. A task that could not run is recorded NOT_RUN with the reason, never ticked.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: the user story (US1–US5) a task belongs to
- Paths are relative to the repository root.

## Phase 1: Setup

- [ ] CR-T001 Create the package `factory/python/forge_factory/controlroom/__init__.py` with a module docstring stating the model-free, read-only contract (FR-020, FR-026)
- [ ] CR-T002 [P] Create `config/factory/controlroom.yaml` with the defaults from data-model.md (tz Europe/Lisbon, one 24 h Day shift, staleness_s 120, idle_threshold_s 600, lead_time_limit_s 21600, rework_near_ratio 0.66, yield_threshold 0.5, spc block, empty prices)
- [ ] CR-T003 [P] Implement `factory/python/forge_factory/controlroom/config.py`: load and validate `config/factory/controlroom.yaml` against `specs/007-kpi-control-room/contracts/controlroom-config.schema.json`, and fail closed with a clear error on an invalid file

## Phase 2: Foundational (blocking for all stories)

- [ ] CR-T004 Write `factory/python/tests/controlroom_fixtures.py`: builders for fixture workspaces (manifest, gate-log rows using the real step/result/gate.decision vocabulary from research R2, package.json, fabro_run_id, model-profile.json, acp proxy usage lines) plus a fake Fabro client (lifecycle status, usage)
- [ ] CR-T005 Implement the incremental gate-log reader in `factory/python/forge_factory/controlroom/floor.py` (`GateLogReader`): byte-offset tail keyed by path/size/mtime, tolerant of a partial last line, de-duplicated by (path, line number)
- [ ] CR-T006 [P] Implement `factory/python/forge_factory/controlroom/windows.py`: shift/today/7d/30d/custom windows and the same-length previous window, computed in the configured IANA zone and converted to UTC (DST-safe)
- [ ] CR-T007 [P] Test windows in `factory/python/tests/test_controlroom_windows.py`, including the 2026-10-25 Europe/Lisbon DST change (25 h day), a shift spanning midnight, and the previous-period length

**Checkpoint**: config, fixtures, the gate-log reader and windows are ready.

## Phase 3: User Story 1 - Live shop-floor board with andon status (Priority: P1) 🎯 MVP

**Goal**: every work order shown at its station with an andon (RUNNING/REWORK/BLOCKED/IDLE) and the recorded reason, updated live.

**Independent Test**: append fixture gate-log rows and check that the floor snapshot and the SSE stream reflect each transition within 5 s, with the reason text, without a page reload.

### Tests for User Story 1

- [ ] CR-T008 [P] [US1] Write unit tests for andon and unit derivation in `factory/python/tests/test_controlroom_floor.py`:
  - RUNNING, REWORK (route REWORK, author REJECTED), BLOCKED (route BLOCKED with gate.reason, governor TOKEN_BUDGET_EXHAUSTED);
  - STOPPED (run ended without a package), READY/BLOCKED at SHIPPING;
  - IDLE stations, NO_WIP factory status;
  - retries `-rN` as one order;
  - the first_pass immutability across attempts;
  - the elapsed time growing live.
- [ ] CR-T009 [P] [US1] Write a schema test in `factory/python/tests/test_controlroom_floor.py`: every snapshot validates against `specs/007-kpi-control-room/contracts/floor-snapshot.schema.json`, and content_hash is stable for identical records
- [ ] CR-T010 [P] [US1] Write API tests in `factory/python/tests/test_controlroom_api.py`:
  - `/api/v1/control-room/floor` needs auth (401) and returns the snapshot;
  - `/control-room` serves the page;
  - no POST, PUT or DELETE route exists under `/api/v1/control-room`.
- [ ] CR-T011 [US1] Write the SSE latency test in `factory/python/tests/test_controlroom_api.py`: over 100 appended gate-log rows, at least 95 % of `floor` events arrive within 5 s (SC-001); the heartbeat carries data_age_s

### Implementation for User Story 1

- [ ] CR-T012 [US1] Implement unit derivation in `factory/python/forge_factory/controlroom/floor.py`:
  - **Inputs:** manifest, gate-log, package.json, model-profile.json and Fabro lifecycle (cached 5 s per run, via `fabro.client.client_for_workspace`).
  - **Derived per unit:** station, status, reason, rework_cycles, first_pass, station_since, elapsed_s and package.
- [ ] CR-T013 [US1] Implement station andon aggregation, factory_status (VIOLATION > STOPPED/ATTENTION > PRODUCING > NO_WIP), data_age_s/stale and content_hash in `factory/python/forge_factory/controlroom/floor.py` (`snapshot()`)
- [ ] CR-T014 [US1] Add `GET /api/v1/control-room/floor`, `GET /api/v1/control-room/stream` (SSE: `floor` event on a content_hash change, `heartbeat` every 1 s) and `GET /control-room` to `factory/python/forge_factory/dashboard/app.py`, reusing `role()` auth
- [ ] CR-T015 [US1] Create `factory/python/forge_factory/dashboard/static/control-room.html` with the floor board:
  - seven station columns, each with an andon label, an icon and a colour;
  - unit cards showing the work order, time at the station, total elapsed time and reason;
  - a stale-data banner;
  - SSE with a 5 s polling fallback;
  - a sign-in reusing the dashboard token cookie;
  - light and dark themes;
  - a collapse to a station list at phone width.
- [ ] CR-T016 [US1] Add a "Control Room" link to the header of `factory/python/forge_factory/dashboard/static/index.html`

**Checkpoint**: the live floor works on its own (the MVP).

## Phase 4: User Story 2 - Shift and day production scorecard (Priority: P1)

**Goal**: shift, today, 7-day and 30-day counts and K01–K20, each with the previous period, NOT_MEASURED where inputs are missing, and READY separate from BLOCKED.

**Independent Test**: on a frozen fixture event set, every scorecard value equals `kpi.engine.snapshot` for the same window, and missing inputs show NOT_MEASURED.

### Tests for User Story 2

- [ ] CR-T017 [P] [US2] Write tests in `factory/python/tests/test_controlroom_scorecard.py`:
  - equality with `kpi.engine.snapshot` per window (SC-003);
  - READY and BLOCKED shown separately, with BLOCKED never counted as output;
  - OEE NOT_MEASURED without baselines;
  - n = 0 stations shown as n = 0 rather than 0 % or 100 %;
  - replaying the records twice gives identical values (SC-004);
  - the previous window has the same length.
- [ ] CR-T018 [P] [US2] Write API tests for `/api/v1/control-room/scorecard` (each window kind, a custom window with a bad range → 422) in `factory/python/tests/test_controlroom_api.py`

### Implementation for User Story 2

- [ ] CR-T019 [US2] Implement `factory/python/forge_factory/controlroom/scorecard.py`:
  - counts (started, ready, blocked, stopped, wip) from `kpi.sources.collect_all()` events;
  - K01–K20 from `kpi.engine.snapshot(events, start, end, "IN_PROGRESS", load_baselines())` for the window and the previous window;
  - violations_open;
  - a 30 s cache shared with the existing KPI cache.
- [ ] CR-T020 [US2] Add `GET /api/v1/control-room/scorecard` to `factory/python/forge_factory/dashboard/app.py`
- [ ] CR-T021 [US2] Add the scorecard panel to `factory/python/forge_factory/dashboard/static/control-room.html`:
  - window selector;
  - tiles with value, unit, n and the delta against the previous period;
  - NOT_MEASURED with its reason;
  - READY and BLOCKED tiles side by side;
  - each tile linking to the KPI evidence drill-down.

**Checkpoint**: US1 and US2 work independently.

## Phase 5: User Story 3 - Quality and loss analysis (Priority: P2)

**Goal**: per-station SPC trend charts (first-pass yield p-chart, cycle-time I-MR), a Pareto of loss reasons, and the CAPA list.

**Independent Test**: on fixture history, the control limits match hand-computed references, too little data gives INSUFFICIENT_DATA, and the Pareto order and shares match the counted rows.

### Tests for User Story 3

- [ ] CR-T022 [P] [US3] Write tests in `factory/python/tests/test_controlroom_spc_pareto.py`:
  - p-chart limits with a variable n;
  - I-MR limits (2.66·MR̄);
  - WE1/WE2/WE3 detection;
  - the INSUFFICIENT_DATA thresholds from config;
  - Pareto code normalisation (`CODE:detail` → `CODE`), order, cumulative share and refs.

### Implementation for User Story 3

- [ ] CR-T023 [P] [US3] Implement `factory/python/forge_factory/controlroom/spc.py` (method ID `spc-v1`): p-chart, I-MR, the run rules and the minimum-sample handling
- [ ] CR-T024 [P] [US3] Implement `factory/python/forge_factory/controlroom/pareto.py`: BLOCKED, REWORK and REJECTED reasons per station and window from gate logs, with refs
- [ ] CR-T025 [US3] Add `GET /api/v1/control-room/quality`, combining per-station charts, the Pareto and the CAPA list (read-only, from the CRE store via `reliability` read functions), to `factory/python/forge_factory/dashboard/app.py`
- [ ] CR-T026 [US3] Add the quality panel to `factory/python/forge_factory/dashboard/static/control-room.html`:
  - a station selector;
  - SVG control charts with the centre line, limits and highlighted violations;
  - an SVG Pareto with a cumulative line;
  - the CAPA table;
  - point and bar drill-down links.

## Phase 6: User Story 4 - Model usage and cost per unit (Priority: P2)

**Goal**: usage per run, station, role and model, including ACP nodes; tokens per READY unit; the share not reported; cost only from a price.

**Independent Test**: for fixture runs with known usage records, the totals equal the sums; unreported usage is counted as not reported, never zero; cost is NOT_MEASURED without a price.

### Tests for User Story 4

- [ ] CR-T027 [P] [US4] Write proxy tests in `factory/python/tests/test_acp_proxy.py`:
  - the proxy appends one `usage` line per prompt result (counts and model only, no prompt or response text), from both `result.usage` and `result._meta.quota` shapes;
  - nothing is appended when no usage is present.
- [ ] CR-T028 [P] [US4] Write tests in `factory/python/tests/test_controlroom_usage.py`:
  - merging Fabro native usage with ACP proxy usage;
  - roles from the binding;
  - not_reported_share;
  - tokens_per_ready_unit NOT_MEASURED when READY = 0;
  - cost from the Fabro catalogue, from a configured price, and NOT_MEASURED for subscription models;
  - `release.finalize.token_usage` no longer failing on model-null stages.

### Implementation for User Story 4

- [ ] CR-T029 [US4] Record prompt-result usage in `factory/python/forge_factory/acp/proxy.py` (track the `session/prompt` request IDs, read the matching response's `usage` or `_meta.quota`, append `{"event": "usage", ...}` counts to `.forge-run/acp/<node>.proxy.jsonl`)
- [ ] CR-T030 [US4] Make `token_usage` in `factory/python/forge_factory/release/finalize.py` skip stages whose model is null (record them as `not_reported`) instead of returning `unknown` for the whole run
- [ ] CR-T031 [US4] Implement `factory/python/forge_factory/controlroom/usage.py`: per-record merge, aggregates by model, station and role, and cost rules
- [ ] CR-T032 [US4] Add `GET /api/v1/control-room/usage` to `factory/python/forge_factory/dashboard/app.py`, and a usage panel (by-model bars, a by-station table, the not-reported share, tokens per READY unit, cost or NOT_MEASURED) to `factory/python/forge_factory/dashboard/static/control-room.html`

## Phase 7: User Story 5 - Alerts and attention list (Priority: P3)

**Goal**: deterministic alerts with stable IDs; violations that cannot be filtered; acknowledgement only in the viewer's browser.

**Independent Test**: a fixture BLOCKED row raises exactly one STATION_BLOCKED alert; a repeated condition updates it; a safety violation alert is present under every filter; the server has no acknowledgement endpoint.

### Tests for User Story 5

- [ ] CR-T033 [P] [US5] Write tests in `factory/python/tests/test_controlroom_alerts.py`:
  - each condition (STATION_BLOCKED, LEAD_TIME_OVER_LIMIT, REWORK_BUDGET_NEAR, YIELD_BELOW_THRESHOLD, YIELD_OUT_OF_CONTROL, SAFETY_PROCESS_VIOLATION, FEED_STALE);
  - stable IDs and de-duplication;
  - violations with `filterable: false`, which force factory_status VIOLATION (SC-005).

### Implementation for User Story 5

- [ ] CR-T034 [US5] Implement `factory/python/forge_factory/controlroom/alerts.py` from the floor snapshot, scorecard (K20) and SPC results
- [ ] CR-T035 [US5] Add `GET /api/v1/control-room/alerts` to `factory/python/forge_factory/dashboard/app.py`, and include open alerts in the SSE `floor` event
- [ ] CR-T036 [US5] Add the attention list to `factory/python/forge_factory/dashboard/static/control-room.html`:
  - severity order;
  - acknowledgement stored in localStorage in try/catch;
  - opt-in browser notifications;
  - a violation banner that no filter can hide.

## Phase 8: Polish & cross-cutting

- [ ] CR-T037 [P] Implement `factory/python/forge_factory/controlroom/export.py` and `GET /api/v1/control-room/export` (floor, scorecard, quality and usage; JSON or CSV; with evidence refs), with tests in `factory/python/tests/test_controlroom_api.py` (FR-023)
- [ ] CR-T038 [P] Write a no-model-call test in `factory/python/tests/test_controlroom_api.py`: patch the Fabro run-creation, LLM gateway and ACP entry points to raise, then exercise every Control Room endpoint (SC-007)
- [ ] CR-T039 [P] Write a test in `factory/python/tests/test_controlroom_api.py` that the page and API texts contain no compliance, certification or approval claim (word list from FR-025), and that every andon state has a text label
- [ ] CR-T040 Run the layout check at 390 px and 1440 px (scrollWidth ≤ clientWidth) with headless Chromium if available, saving screenshots to `evidence/v0.4/runs/CR-T040/`; otherwise record NOT_RUN with the reason (SC-008)
- [ ] CR-T041 Document the Control Room (purpose, panels, NOT_MEASURED meaning, configuration, alert rules) in `docs/CONTROL-ROOM.md`, and link it from `docs/KPI-OPERATOR-DASHBOARD-v0.5.md`
- [ ] CR-T042 Run ruff, `tests/spec/validate_design.py` and the full factory test suite; then restore `evidence/v0.4/kpi/pilot-snapshot.json` and the implementation-status docs; record the results under `evidence/v0.4/runs/CR-T042/`
- [ ] CR-T043 Run the CRE promotion gate `--kind CHANGE` for the feature commits (the proxy usage recording, the token_usage fix, the dashboard), and copy the decision to `evidence/cre/decisions/`
- [ ] CR-T044 Live validation per quickstart.md §2–3 on a separate port (8766) against the real state directory, including one live work order with Codex authors and Claude inspectors; record the observations and screenshots under `evidence/v0.4/runs/CR-T044/`

## Dependencies & Execution Order

- **Setup (CR-T001–T003)** → **Foundational (CR-T004–T007)** → the user stories.
- **US1** (CR-T008–T016) is the MVP, and US5 depends on its floor snapshot.
- **US2** (CR-T017–T021) is independent of US1, except for sharing the page file (do the UI tasks after CR-T015).
- **US3** (CR-T022–T026) is independent, and feeds the YIELD_OUT_OF_CONTROL alert in US5.
- **US4** (CR-T027–T032) is independent. Its proxy change (CR-T029) is a factory change covered by CR-T043.
- **US5** (CR-T033–T036) depends on US1, and uses the US2 (K20) and US3 (SPC) outputs when present.
- **Polish** (CR-T037–T044) comes after the stories it covers. CR-T043 comes before any merge, and CR-T044 is last.

## Parallel opportunities

- CR-T002 and CR-T003; CR-T006 and CR-T007.
- The test-writing tasks in each story ([P]) run in parallel with each other.
- CR-T023 and CR-T024 (spc and pareto are different files).
- CR-T037, CR-T038 and CR-T039.

## Implementation strategy

1. **MVP:** Setup, Foundational, then US1. The live floor and andon are usable on their own: validate them on
   the real state directory, then continue.
2. **US2** next: the scorecard. P1 is complete at this point.
3. **US3 and US4** in either order: quality analysis, then usage and cost.
4. **US5:** alerts, on top of the floor, scorecard and SPC.
5. **Polish:** export, cross-cutting tests, docs, the full regression, the CRE CHANGE promotion and live
   validation.
