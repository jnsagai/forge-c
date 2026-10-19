# Feature Specification: Factory KPI Control Room

**Feature Branch**: `feat/007-kpi-control-room`

**Created**: 2026-10-19

**Status**: Draft

**Input**: User description: "I want you to implement a new feature, that will be a dashboard for Forge-C where I can monitor the KPIs as a manager of the Fabric usually does on real-time" (owner, 2026-10-19). Build on the existing local dashboard, the feature-003 KPI engine (K01–K20), and the read views of features 004 (reliability), 005 (autonomy) and 006 (assurance).

## Context

Forge-C already computes 20 deterministic production KPIs (K01–K20, feature 003) and shows them, together with reliability, assurance and autonomy data, as tiles and tables on one long page. That page answers "what are the numbers" for an engineer who knows where to look. It does not answer the questions a plant manager asks at a glance during a shift:

- what is on the floor right now;
- which station is stopped and why;
- are we producing to plan;
- is quality drifting;
- where are we losing output;
- what does it cost.

This feature adds that manager view, the **Control Room**. It shows the same deterministic data, organised the way a production floor is run. Nothing in it is computed by a model, guessed, or allowed to hide a quality or safety gate.

**Factory vocabulary used in this spec:**
- **Production unit:** a work order, i.e. one driver order.
- **Station:** one of the six SWE phases, SWE.1–SWE.6.
- **Shipping:** the release station that produces a READY_FOR_OFFLINE_REVIEW or BLOCKED package.
- **Andon:** a station's live status signal.
- **Scrap:** a work order that ends BLOCKED.
- **Rework:** a rework cycle within a station.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Live shop-floor board with andon status (Priority: P1)

The manager opens the Control Room and immediately sees every work order on the floor, laid out as a flow through the six stations and shipping. Each station shows an andon colour:
- running (green);
- rework in progress (amber);
- blocked or stopped (red);
- idle (grey).

Each station shows its current units and how long the oldest unit has waited. The board updates within seconds when a unit changes station, fails a gate or ships. Selecting a red station shows the reason, for example "SWE.4 BLOCKED: rework budget exhausted (3 failed cycles)" or "SWE.3 BLOCKED: NO_REGISTERS_FROM_SWE2_TABLE", with a link to the underlying gate record.

**Why this priority**: knowing in real time what is running, what is stopped and why is the core of floor management. Every other view is analysis on top of it.

**Independent Test**: start or replay a work order and watch the board. The unit appears at SWE.1, moves station by station, shows amber during rework and red with the recorded reason when blocked. The page is not reloaded.

**Acceptance Scenarios**:

1. **Given** a work order in progress at SWE.2, **When** its SWE.2 baseline freezes and inspection passes, **Then** within 5 seconds the unit appears at SWE.3 and the SWE.2 cycle time is recorded.
2. **Given** a station gate records BLOCKED, **When** the manager looks at the board, **Then** that station's andon is red and shows the recorded reason text, the work order ID and the time it stopped.
3. **Given** no work order has been active for the configured idle threshold, **When** the board is shown, **Then** all stations show idle and the factory status reads "no WIP", not "healthy production".
4. **Given** the data feed is interrupted, **When** the manager looks at the board, **Then** a stale-data banner shows the age of the last update, and no tile keeps presenting old values as live.

---

### User Story 2 - Shift and day production scorecard (Priority: P1)

The manager sees a scorecard for the current shift, today, the last 7 days and the last 30 days, with the trend against the previous period of the same length:
- units started;
- units shipped READY;
- units shipped BLOCKED (scrap);
- WIP;
- throughput;
- lead time (median and 95th percentile);
- first-pass yield per station and rolled throughput yield;
- rework share;
- factory OEE (only where calibrated baselines exist).

Each value shows its sample size. A value whose inputs are missing shows NOT_MEASURED with the reason.

**Why this priority**: shift and day results against the previous period are how output is managed and reported.

**Independent Test**: load a fixed set of recorded events. Every scorecard value equals the value the existing deterministic KPI engine computes for the same window, and every missing input shows NOT_MEASURED.

**Acceptance Scenarios**:

1. **Given** 4 units shipped READY and 1 BLOCKED today, **When** the manager selects "today", **Then** READY = 4 and BLOCKED = 1 appear separately; BLOCKED is never counted as output.
2. **Given** no calibrated performance baseline exists, **When** the scorecard is shown, **Then** factory OEE shows NOT_MEASURED ("no calibrated baseline") and no substitute value.
3. **Given** a station had zero units in the window, **When** its first-pass yield is shown, **Then** it reads "n = 0" and not 0 % or 100 %.

---

### User Story 3 - Quality and loss analysis: yield trends, SPC and Pareto (Priority: P2)

The manager sees, per station:
- first-pass yield and cycle time as time-trend charts, with statistical process control limits computed from history;
- a Pareto of the reasons units failed or were blocked (finding codes and corrective-action IDs), for the selected window;
- open and in-effectiveness-check corrective actions and their latest effect.

Points outside control limits or matching run rules are highlighted. Each chart point links to the units and evidence behind it.

**Why this priority**: once the floor is visible, the next management question is where output is lost and whether a process is drifting. This reuses the reliability data of feature 004.

**Independent Test**: from recorded history, the Pareto order and counts match the reliability records, and the control limits match a reference calculation on the same points.

**Acceptance Scenarios**:

1. **Given** 30 days of history, **When** the manager opens SWE.4 quality, **Then** the Pareto lists failure reasons by count, with a cumulative percentage, and links each bar to its units.
2. **Given** fewer points than the control-chart method needs, **When** the chart is shown, **Then** the limits read "insufficient data (n = k)" and no limits are drawn.

---

### User Story 4 - Model usage and cost per unit (Priority: P2)

The manager sees, per run, per station and per model:
- token usage, split into the author model and the inspector model (currently the Codex Sol 6.1 authors and the Claude Opus 5.5 inspectors);
- tokens per READY unit;
- agent time per station;
- the share of runs whose usage was not reported.

Money cost is shown only where a price table has been configured. For the subscription-based models it reads NOT_MEASURED ("subscription; no per-token price").

**Why this priority**: model consumption is the factory's main variable cost and capacity limit.

**Independent Test**: for a recorded run with known usage events, the totals per model and per station equal the sums of the recorded usage. A run without usage records is counted as "not reported" and is not treated as zero.

**Acceptance Scenarios**:

1. **Given** a run whose inspectors report usage and whose authors do not, **When** the manager views model usage, **Then** the inspector tokens are shown, the author tokens show "not reported", and the total is flagged incomplete.
2. **Given** no price is configured for a model, **When** cost is shown, **Then** it reads NOT_MEASURED with the reason, never 0.

---

### User Story 5 - Alerts and attention list (Priority: P3)

The manager sees an attention list and receives on-screen (and, if allowed, browser) notifications for:
- a station turning red;
- a unit exceeding its lead-time limit;
- a rework budget nearly exhausted;
- a yield falling below its threshold or outside control limits;
- a hard safety or process violation;
- the data feed going stale.

Alerts can be acknowledged in the manager's own view. Acknowledging changes nothing in the factory.

**Why this priority**: it lets the manager work elsewhere and come back only when attention is needed. It builds on stories 1–3.

**Independent Test**: replaying a recorded BLOCKED event raises exactly one alert with the reason. Acknowledging it removes it from the open list and changes no factory state or record.

**Acceptance Scenarios**:

1. **Given** a safety-process violation is recorded, **When** the Control Room is open, **Then** a red alert appears that cannot be hidden by any filter, and the scorecard cannot show the factory as green while it is open.
2. **Given** the same station stays blocked, **When** further events arrive for it, **Then** the alert is updated, not duplicated.

---

### Edge Cases

- **Empty factory:** no work orders ever recorded. Every value shows NOT_MEASURED or n = 0 with a clear "no production yet" state; nothing shows as 100 % or green by default.
- **Replayed or duplicated events:** after a restart, the same event arriving twice must not double-count units, yields or tokens.
- **Resumed work orders:** a unit resumed from a later phase must not count a first pass for the phases it skipped.
- **Clock and time zones:** shift and day boundaries use the configured local time zone, and a day with a clock change still has correct boundaries.
- **Long-running unit:** a single work order running for hours keeps its lead time growing live, rather than freezing at the last event.
- **Several runs of one work order:** retries and resumes are shown as one production unit with its attempt history.
- **Inspector or author model changes mid-period:** usage is split by the model recorded per run and never re-attributed.
- **Data source unavailable:** if the run engine or a store cannot be read, the affected tiles show "source unavailable" with the time of the last good value. The rest keeps working.
- **Phone width:** the board collapses to a station list with andon colours; nothing scrolls horizontally.

## Requirements *(mandatory)*

### Functional Requirements

**Live floor**
- **FR-001**: The Control Room MUST show every work order in progress at its current station (SWE.1–SWE.6 or shipping), with its time at the station and its total elapsed time.
- **FR-002**: Each station MUST show an andon status (running, rework, blocked, idle) derived only from recorded gate and run events, with the recorded reason for rework and blocked states.
- **FR-003**: Changes on the floor MUST appear without a page reload within 5 seconds of being recorded (see SC-001).
- **FR-004**: When the newest data is older than the configured staleness limit, the Control Room MUST show a stale-data banner with the data age and mark live tiles as stale.

**Scorecard and KPIs**
- **FR-005**: The Control Room MUST show a scorecard for the selected window (current shift, today, 7 days, 30 days, custom), with the same-length previous period for comparison.
- **FR-006**: Every KPI value MUST come from the existing deterministic KPI definitions (K01–K20) or from a newly specified deterministic definition with a documented formula. No value may be produced by model inference.
- **FR-007**: Every value MUST carry its sample size and status. Missing inputs MUST show NOT_MEASURED with a reason, and never a substituted or default number.
- **FR-008**: READY and BLOCKED output MUST always be shown separately. BLOCKED units count as scrap and never as output.
- **FR-009**: Factory OEE MUST be shown only where calibrated baselines exist (feature-003 rule), otherwise NOT_MEASURED.
- **FR-010**: Shifts MUST be configurable (names, start and end times, local time zone), defaulting to one 24-hour day shift.

**Quality and losses**
- **FR-011**: Per station, the Control Room MUST show trend charts of first-pass yield and cycle time with control limits computed by a documented method from recorded history. It MUST flag points that violate the limits or the configured run rules, and show "insufficient data" below the method's minimum sample.
- **FR-012**: The Control Room MUST show a Pareto of failure and block reasons per station and window, with counts and cumulative share. Each bar MUST link to the affected units and evidence.
- **FR-013**: The Control Room MUST list corrective actions (CAPA) with their state and their effectiveness status, read from the reliability records.

**Model usage and cost**
- **FR-014**: Token usage MUST be shown per run, station, role (author or inspector) and model, together with tokens per READY unit and the share of runs with unreported usage.
- **FR-015**: Money cost MUST be computed only from a configured price table. A model without a configured price, or used under a subscription, MUST show NOT_MEASURED with the reason.

**Alerts**
- **FR-016**: The Control Room MUST raise alerts for:
  - a station turning blocked;
  - lead time over limit;
  - rework budget near exhaustion;
  - yield below threshold or out of control;
  - a safety or process violation;
  - a stale feed.

  Each alert MUST be raised once per condition and updated while the condition holds.
- **FR-017**: Safety or process violation alerts and their counts MUST NOT be hideable by filters. While one is open, no summary may present the factory as green.
- **FR-018**: Acknowledging an alert MUST change only the viewer's own alert list. It MUST NOT change any factory state, gate, record or evidence.

**Drill-down, access and integrity**
- **FR-019**: Every tile, chart point and alert MUST link to its underlying records: work order, run, station, gate decision, events and evidence references.
- **FR-020**: The Control Room MUST be read-only. It MUST NOT offer control actions beyond the existing operator-token actions of feature 005, which keep their current authorization.
- **FR-021**: Access MUST use the existing dashboard sign-in and roles, and the Control Room MUST be served only on the local machine by default.
- **FR-022**: Repeated or replayed events MUST NOT change any computed value (idempotent aggregation).
- **FR-023**: The manager MUST be able to export the current scorecard and any chart's data, with its evidence references, as CSV or JSON.
- **FR-024**: The layout MUST work at desktop and phone widths without horizontal page scrolling. Andon colours MUST also be conveyed by text or icon, not by colour alone.
- **FR-025**: The Control Room MUST NOT state or imply ASPICE capability, ISO 26262 compliance, certification or safety approval. Quality signals are labelled as engineering evidence.
- **FR-026**: Showing the Control Room MUST NOT add model calls or change the healthy-state model-free supervision.

### Key Entities

- **Production unit**: a work order. It has an ID, product class (driver, layer, target MCU), current station, attempts or runs, start time, ship time, and outcome (READY, BLOCKED or in progress).
- **Station**: SWE.1–SWE.6 and shipping. It has its andon status, current units, queue, cycle-time history and first-pass outcomes.
- **Station event**: a recorded gate or run event (author freeze, inspection decision, rework, block, ship), with its timestamp, unit, station, reason code and evidence reference.
- **Shift**: a named local-time interval used to group production.
- **KPI value**: a metric ID, window, value or NOT_MEASURED, unit, sample size, status, formula version and evidence references.
- **Control chart**: the points, centre line, limits, method, minimum sample and rule violations for one station metric.
- **Alert**: a condition, severity, the unit or station concerned, first and last seen times, recorded reason and the viewer's acknowledgement.
- **Model usage record**: run, station, role, model, provider, tokens (or "not reported") and price-table reference.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A station change, block or shipment appears in the Control Room within 5 seconds of being recorded, in at least 95 % of 100 replayed events.
- **SC-002**: From opening the Control Room, the manager can name every stopped station and its reason in under 10 seconds, without scrolling, at desktop width.
- **SC-003**: For a frozen reference set of recorded events, 100 % of scorecard values equal the deterministic KPI engine's values for the same window, and 100 % of values with missing inputs show NOT_MEASURED.
- **SC-004**: Replaying the reference event set twice gives identical values (zero double counting).
- **SC-005**: An open safety or process violation is visible on every view and filter combination (0 views hide it).
- **SC-006**: Every displayed number can be traced to its records in at most 2 selections.
- **SC-007**: The Control Room adds zero model calls and zero tokens while showing a healthy factory.
- **SC-008**: The Control Room is fully usable at a 390-pixel-wide screen with no horizontal scrolling.

## Assumptions

- The manager is the factory owner, using the existing local dashboard sign-in. Multi-user roles beyond the existing reader and operator roles are out of scope.
- "Real time" means event-driven updates within seconds, from the factory's own recorded events. Sub-second industrial control timing is not required.
- Stations are the six SWE phases plus shipping (release). Deterministic sub-steps such as the SWE.3 register-map generator are shown as part of their station.
- Default control-chart method: individuals and moving-range (or p-chart for yields) with the standard minimum sample. The method is documented and versioned.
- Price tables are optional configuration. The current Codex and Claude subscriptions have no per-token price, so their cost shows NOT_MEASURED until the owner configures a value.
- Alerts are on-screen, plus browser notifications when the viewer allows them. No external paging, e-mail or paid notification service is used.
- Existing feature-003 KPI definitions, feature-004 reliability records, feature-005 autonomy records and feature-006 assurance records are the data sources. This feature adds views and the deterministic aggregations named above; it does not re-define K01–K20.
- History available today (runs since the KPI engine was introduced) is enough for the first trend charts. Older runs without the needed events show as NOT_MEASURED.

## Out of Scope

- Any control action from the Control Room: starting, stopping or re-routing work orders, or approving packages. The existing feature-005 operator actions are untouched.
- Forecasting, recommendations or explanations produced by a model.
- Remote or public hosting, multi-site aggregation, and mobile apps.
- Changes to release gates, safety policy, or the definitions of K01–K20.
