# Research: Factory KPI Control Room (Phase 0)

All Technical Context items were resolvable from the existing code and records, so no NEEDS CLARIFICATION
remain. Each decision records what was chosen, why, and what else was considered.

## R1. Source of the live floor state

- **Decision:** derive units and station state from per-workspace records:
  - the manifest (`created_at`, `work_order`, `layer`, `target`);
  - `.forge-run/gates/gate-log.jsonl`: the deterministic gate decisions, append-only, about 2,800 rows over
    157 workspaces;
  - `.forge-run/package.json`: the final READY/BLOCKED status and `finalized_at`;
  - the Fabro run lifecycle status, via `client_for_workspace`, cached per run.

  Each gate log is read incrementally by byte offset, keyed on size and mtime.
- **Rationale:**
  - The gate log is the factory's own decision record (author freeze/reject, inspection PASS/REWORK, route
    REWORK/BLOCKED/UPSTREAM). It is what a station andon must reflect.
  - It is local, cheap to tail, and needs no new collector.
- **Alternatives considered:**
  - **The dashboard event store only:** it carries channel events but not every gate decision with its reason.
  - **Fabro events only:** they lack the factory's reasons, and ACP stages lack usage.
  - **A new database:** rejected, as it would duplicate records (constitution X: no duplicate collector).

## R2. Andon derivation rules

- **Decision:** the station status for a unit is decided in this order:
  1. **BLOCKED:** the last `route` decision is BLOCKED, or `inspect` BLOCKED, or `governor`
     TOKEN_BUDGET_EXHAUSTED. Reason = `gate.reason`, or the first issue code.
  2. **REWORK:** the last `route` decision is REWORK/UPSTREAM/REINSPECT, or the last `author` result is REJECTED.
     Reason = `gate.reason` or the first issue.
  3. **RUNNING:** the run is active and the phase has started but not passed.
  4. **DONE:** `inspect` PASS, or `route` PASS.

  Station andon = the worst status over its units (BLOCKED > REWORK > RUNNING), or IDLE with no units.
  - A unit's current station is the first phase without PASS, or SHIPPING once a package exists.
  - A work order whose Fabro run ended without a package shows "stopped (no package)" as BLOCKED with that reason.
- **Rationale:** these are the exact `step`/`result`/`gate.decision` values found in the records (frequency
  survey 2026-10-19), so nothing is inferred.
- **Alternatives considered:** a heuristic on file activity. Rejected: not evidence.

## R3. Real-time delivery

- **Decision:** a dedicated SSE endpoint, `/api/v1/control-room/stream`.
  - It recomputes the floor snapshot every 1 s.
  - It pushes a full snapshot when the content hash changes, plus a heartbeat with the data age.
  - The client falls back to polling `/floor` every 5 s if SSE fails.
- **Rationale:**
  - SSE already exists in the app (same auth and cookie).
  - A 1 s scan with incremental reads keeps the target of 5 s for at least 95 % of events.
  - Full snapshots are small (tens of units) and avoid diff-merge bugs.
- **Alternatives considered:**
  - **WebSockets:** not needed for a one-way feed.
  - **Pushing raw events:** that would force the browser to re-implement the andon rules.

## R4. Scorecard windows and comparison

- **Decision:**
  - Windows: current shift, today, 7 days, 30 days and custom, all in the configured IANA time zone (default:
    the host zone, Europe/Lisbon). Each window has a previous period of the same length.
  - Boundaries are computed in local time and converted to UTC, so DST days have correct 23 h or 25 h lengths.
  - K-metrics come from `kpi.engine.snapshot(events, start, end)`, unchanged. Floor counts (started, READY,
    BLOCKED, WIP) come from the same source events, so they cannot disagree with K04/K18.
- **Rationale:** one deterministic engine (FR-006, SC-003). The KPI engine already gives NOT_MEASURED and sample
  sizes.
- **Alternatives considered:** recomputing KPIs in the new package. Rejected: two formulas for one number.

## R5. SPC method

- **Decision:**
  - **Yields** (first-pass outcome per unit per station): a p-chart over daily subgroups,
    p̄ ± 3·√(p̄(1−p̄)/nᵢ) with variable limits. Minimum 10 subgroups with a total n of at least 50.
  - **Cycle time:** an individuals and moving-range (I-MR) chart, x̄ ± 2.66·MR̄. Minimum 15 points.
  - **Run rules:** Western Electric rules 1 (outside 3σ), 2 (9 on one side) and 3 (6 trending), configurable.
  - Below the minimum sample the chart reports "insufficient data (n = k)" and no limits.
  - The method ID is versioned (`spc-v1`).
- **Rationale:** standard, simple and deterministic. It matches the spec assumption.
- **Alternatives considered:**
  - **EWMA/CUSUM:** more sensitive, but harder to read for a floor view. Could be added later.

## R6. Pareto of losses

- **Decision:** count per station and window:
  - `route` BLOCKED reasons;
  - `inspect` REWORK reasons (inspection finding IDs map to their major finding codes where recorded);
  - `author` REJECTED issue codes, normalised to their code prefix. For example
    `CONTRACT_SWR_NOT_COVERED:SWR-005 (...)` becomes `CONTRACT_SWR_NOT_COVERED`.

  Each bar links to `{work_order, phase, ts}` rows. CRE failure modes and CAPA come from the existing reliability
  API, read-only.
- **Rationale:** these reasons are what loses units today; the CRE fingerprints cover failed runs.
- **Alternatives considered:** CRE fingerprints alone. Rejected: completed-BLOCKED runs are not fingerprinted
  (known observation).

## R7. Model usage and cost

- **Decision:**
  - **Native Fabro stages:** from `/runs/{id}/usage`, with model, tokens and Fabro's catalogue cost.
  - **ACP stages:** model null in Fabro. The forge ACP proxy will append one usage line per prompt result to
    `.forge-run/acp/<node>.proxy.jsonl`:
    `{"event":"usage","model":…,"input":…,"output":…,"cache_read":…,"cache_write":…}`, read from the agent's
    `result.usage` or `result._meta.quota`. Counts only, no content.
  - **Anything without a record:** "not reported".
  - **Cost:** only from Fabro's reported cost or a configured price table. Subscription-backed ACP models give
    NOT_MEASURED ("subscription; no per-token price").
  - `release.finalize.token_usage` is fixed to skip stages whose model is null, instead of failing the whole run
    (today it returns "unknown" for every Codex-author run).
- **Rationale:** FR-014/015. The Claude probe showed the adapter returns usage in the prompt result.
- **Alternatives considered:** parsing agent logs. Rejected: content risk and fragile.

## R8. Alerts and acknowledgement

- **Decision:**
  - Alert ID = sha256 of (condition, subject), so a condition that holds is updated, not duplicated.
  - The conditions are listed in data-model.md.
  - Acknowledgements are stored per viewer in browser `localStorage` (try/catch). The server never stores them,
    so acknowledging cannot touch factory state (FR-018).
  - Browser notifications are opt-in via the Notification API.
  - Safety/process violations are computed server-side and are not filterable (FR-017).
- **Alternatives considered:** storing acknowledgements server-side. Rejected: it would add a writer and need
  auth beyond read-only.

## R9. Page technology

- **Decision:** one static `control-room.html` served by the app at `/control-room`.
  - Vanilla JS and CSS grid, with inline SVG for sparklines, control charts and the Pareto.
  - Light and dark themes via CSS variables.
  - Andon states carry a text label and an icon as well as colour.
- **Rationale:** no build step, no dependency, works offline on loopback. Same pattern as the existing
  `index.html`.
- **Alternatives considered:**
  - **Chart.js or ECharts vendored:** about 200 kB of extra code to review.
  - **A Grafana/Prometheus stack:** a new service, and high-cardinality run IDs (rejected by
    docs/KPI-OPERATOR-DASHBOARD).

## R10. Verification of SC-002/SC-008 (layout)

- **Decision:**
  - API and logic are tested with pytest.
  - Layout is checked with a headless Chromium screenshot at 1440 px and 390 px if a browser is available on the
    host (the check asserts no horizontal overflow via `scrollWidth`).
  - Otherwise the check is recorded as NOT_RUN with the reason, never claimed.
