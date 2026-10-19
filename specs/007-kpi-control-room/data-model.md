# Data Model: Factory KPI Control Room (Phase 1)

All entities are **derived, read-only projections** of existing records. Nothing here is persisted by the
Control Room, except the proxy usage lines (R7) and the per-viewer acknowledgements in the browser.

## Station

| Field | Type | Rule |
|---|---|---|
| `station_id` | enum `SWE.1`…`SWE.6`, `SHIPPING` | fixed order |
| `andon` | enum `RUNNING`, `REWORK`, `BLOCKED`, `IDLE` | worst status over its current units (R2); `IDLE` when there are none |
| `units` | list of unit IDs | units whose current station is this one |
| `oldest_wait_s` | number \| null | now minus the earliest arrival among current units |
| `reason` | string \| null | the reason of the unit that sets the andon (BLOCKED, otherwise REWORK) |
| `evidence` | list of refs | gate-log row refs `<work_order>/gate-log.jsonl#<line>` |

## Production unit (work order)

| Field | Type | Rule |
|---|---|---|
| `work_order` | string | workspace parent directory name |
| `order_id` | string | `kpi.sources.order_of` (retries `-rN` belong to one order) |
| `class` | object | `layer`, `driver`, `target_mcu` from the manifest |
| `admitted_at` | UTC timestamp | manifest `created_at` |
| `station` | Station ID | first phase without PASS, or `SHIPPING` once a package exists |
| `status` | enum `RUNNING`, `REWORK`, `BLOCKED`, `READY`, `STOPPED` | R2. `STOPPED` = run ended with no package |
| `station_since` | UTC timestamp | timestamp of the first gate row of the current station |
| `elapsed_s` | number | now (or `finalized_at`) minus `admitted_at`; grows live |
| `rework_cycles` | object per phase | count of `route` REWORK/UPSTREAM/REINSPECT rows |
| `first_pass` | object per phase: `PASS` \| `FAIL` \| null | first inspection outcome of the phase (KPI-T003 rule: first across all attempts) |
| `package` | object \| null | `package_status`, `finalized_at`, `archive_sha256`, `gap_count` |
| `run` | object | `fabro_run_id`, `lifecycle` (`running`/`succeeded`/`failed`/`unknown`) |
| `models` | object | from the model profile: `authors` and `inspectors` (`model`, `provider`, `nodes`) |

**State transitions:**

- **Main path:** `RUNNING` (SWE.n) ⇄ `REWORK` (SWE.n) → `RUNNING` (SWE.n+1) … → `SHIPPING` → `READY` or
  `BLOCKED`.
- **Blocked mid-run:** any state → `BLOCKED` (`route` BLOCKED), which is final for that attempt.
- **Stopped:** `RUNNING` → `STOPPED` when the Fabro run ends without a package.

## Floor snapshot

| Field | Type |
|---|---|
| `schema` | `forge-c/control-room-floor/0.1` |
| `generated_at` | UTC timestamp |
| `data_age_s` | seconds since the newest underlying record (staleness, FR-004) |
| `stale` | boolean: `data_age_s` > `staleness_s` **and** at least one unit is RUNNING or REWORK |
| `factory_status` | enum `PRODUCING`, `ATTENTION`, `STOPPED`, `NO_WIP`, `VIOLATION` (VIOLATION overrides all) |
| `stations` | list of Station |
| `units` | list of Production unit (in-progress units, plus units finished in the last 24 h) |
| `content_hash` | sha256 of the canonical snapshot without timestamps (SSE change detection) |

The full JSON Schema is `contracts/floor-snapshot.schema.json`.

## Window

| Field | Type | Rule |
|---|---|---|
| `kind` | enum `shift`, `today`, `7d`, `30d`, `custom` | |
| `start_utc`, `end_utc` | timestamps | local boundaries in `tz`, converted to UTC (DST-safe) |
| `previous` | Window | same length, immediately before |
| `tz` | IANA zone | from config |
| `shift` | name \| null | for `kind = shift` |

## Scorecard

| Field | Type |
|---|---|
| `window`, `previous` | Window |
| `counts` | `started`, `ready`, `blocked`, `wip`, `stopped`: each `{value, n, evidence}` |
| `kpis` | list of KPI values from `kpi.engine.snapshot` (K01–K20), unchanged, with `metric_id`, `status`, `value`, `unit`, `n`, `formula_version`, `evidence_refs` |
| `previous_kpis` | the same list for the previous window |
| `violations_open` | integer (K20 plus open safety/process alerts); never filtered |

## Control chart

| Field | Type |
|---|---|
| `station`, `metric` | `first_pass_yield` (p-chart) or `cycle_time_s` (I-MR) |
| `method` | `spc-v1:p-chart` \| `spc-v1:i-mr` |
| `points` | `[{t, value, n, units:[…]}]` |
| `center`, `ucl`, `lcl` | number or list (variable p-chart limits) \| null |
| `status` | `OK` \| `INSUFFICIENT_DATA` (with `n`, `minimum`) |
| `violations` | `[{rule, point_index}]` (WE1/WE2/WE3) |

## Pareto entry

`{station, reason_code, count, cumulative_share, kind: BLOCKED|REWORK|REJECTED, refs:[{work_order, line}]}`,
sorted by count descending, then by `reason_code`.

## Model usage record

| Field | Type | Rule |
|---|---|---|
| `work_order`, `node`, `station`, `role` | strings | role = `author` \| `inspector` \| `release` \| `other` from the binding node role |
| `model`, `provider` | strings | from Fabro usage (native) or the proxy usage line (ACP) |
| `tokens` | `{input, output, cache_read, cache_write}` \| null | null = not reported |
| `basis` | `reported:fabro` \| `reported:acp-proxy` \| `not_reported` | |
| `cost` | `{value, currency, source}` \| `NOT_MEASURED` with reason | Fabro catalogue cost, or the config price table, else NOT_MEASURED |

Aggregates (per run, station, role, model, window): token sums over reported records only, plus
`not_reported_share` and `tokens_per_ready_unit` (NOT_MEASURED when READY = 0).

## Alert

| Field | Type | Rule |
|---|---|---|
| `alert_id` | `al-` + sha256(condition, subject)[:16] | stable per condition and subject |
| `condition` | enum | `STATION_BLOCKED`, `LEAD_TIME_OVER_LIMIT`, `REWORK_BUDGET_NEAR`, `YIELD_BELOW_THRESHOLD`, `YIELD_OUT_OF_CONTROL`, `SAFETY_PROCESS_VIOLATION`, `FEED_STALE` |
| `severity` | `critical` \| `warning` \| `info` | `SAFETY_PROCESS_VIOLATION` and `STATION_BLOCKED` are critical |
| `subject` | `{work_order?, station?}` | |
| `first_seen`, `last_seen` | timestamps | |
| `reason` | recorded reason text | |
| `evidence` | refs | |
| `filterable` | boolean | false for `SAFETY_PROCESS_VIOLATION` |

Acknowledgement: `{alert_id, acknowledged_at}` in the viewer's browser storage only.

## Configuration (`config/factory/controlroom.yaml`)

| Key | Default | Notes |
|---|---|---|
| `tz` | host zone (`Europe/Lisbon`) | IANA |
| `shifts` | `[{name: Day, start: "00:00", end: "24:00"}]` | |
| `staleness_s` | 120 | |
| `idle_threshold_s` | 600 | |
| `lead_time_limit_s` | 21600 | 6 h, the default work-order timeout |
| `rework_near_ratio` | 0.67 | 2 of 3 cycles used |
| `yield_threshold` | 0.5 | per-station FPY |
| `spc` | `{min_subgroups: 10, min_n: 50, min_points: 15, rules: [WE1, WE2, WE3]}` | |
| `prices` | `{}` | `{model_id: {input_per_mtok, output_per_mtok, currency}}`; absent = NOT_MEASURED |

The JSON Schema is `contracts/controlroom-config.schema.json`.
