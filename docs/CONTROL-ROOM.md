# Forge-C Control Room (feature 007)

The Control Room is the factory manager's real-time view of the software factory. It runs inside the local
dashboard at `http://127.0.0.1:8765/control-room` (loopback only) and uses the same sign-in tokens
(`state/dashboard/tokens.json`).

It is read-only and model-free:

- every number is computed deterministically from records the factory already writes;
- no value comes from a model;
- nothing on the page changes the factory.

## Sign-in and mobile access

- **Sign-in is off until deployment** (owner decision OD-2026-10-19-09, `config/factory/dashboard-access.yaml`).
  It is off only for this machine: a browser here opens the Control Room directly, with the viewer role.
- **Trusted devices need no token either** (owner decision OD-2026-10-19-10). They are listed under
  `trusted_devices` by their Tailscale address, and are let in only over Tailscale (the connection must arrive on a
  Tailscale listen address). Today the list holds the owner's phone. Tailscale authenticates each device, so its
  address identifies it; a Wi-Fi address does not, so the same phone over Wi-Fi still needs the token.
- **Any other device needs the viewer token once**, for example a phone over Wi-Fi. Open the login
  link (`/login?next=/control-room&token=<viewer token>`); a cookie then keeps the phone signed in.
- **To serve the phone**, start the dashboard with extra listen addresses:
  `python -m forge_factory.dashboard.app --host 127.0.0.1 --host <tailscale-ip> [--host <wifi-ip>]`.
  - Tailscale (`http://<machine>.<tailnet>.ts.net:<port>/control-room`) works from anywhere, for your own devices.
  - The Wi-Fi address works only on the same network.
- **At deployment:** set `auth: token` and restart. Every client then signs in, this machine and the trusted
  devices included.
- The AFO operator actions (pause/drain/resume) always require the operator token.

## Panels

| Panel | What it shows | Source |
|---|---|---|
| Attention | Open alerts: a stopped station, lead time over its limit, a rework budget nearly used, a yield below threshold or out of control, a stale feed, a safety/process violation. Acknowledging hides an alert in your browser only; a safety/process violation is never hidden. | floor, scorecard (K20, K02), quality charts |
| Production scorecard | Current shift, today, 7 days or 30 days against the previous period of the same length: READY vs BLOCKED packages, runs started, WIP, rolled throughput yield, first-pass yield per station, lead time, factory OEE, tokens per READY package, safety/process violations. | the feature-003 KPI engine (K01–K20), unchanged |
| Shop floor | SWE.1–SWE.6 and Shipping as stations, each with an andon: ▶ RUNNING, ↻ REWORK, ■ STOPPED (with the recorded reason), – IDLE. Unit cards show the time at the station, total time, current node and models. "Stopped here in 24 h" lists the units blocked at each station. | gate logs, packages, Fabro run status; live over SSE (≤ 5 s) |
| Shipped in the last 24 h | Each finished run: READY or BLOCKED (scrap), with the cause, lead time and age. | sealed package records |
| Quality and losses | Per station: a first-pass yield p-chart (daily) and an I-MR chart of time to pass, both spc-v1 with Western Electric rules 1–3; a Pareto of recorded loss reasons; the CRE corrective actions. | gate logs, inspection records, CRE store |
| Model usage and cost | New tokens (input + output) and cache reads by model, role and station; the share of stages with no usage record; tokens per READY package; cost. | Fabro usage (native nodes) and the forge ACP proxy's usage lines (Codex/Claude nodes) |
| All KPIs K01–K20 | Every KPI row with scope, value or NOT MEASURED and the reason, n, and the previous period. | feature-003 engine |

## Reading the numbers

- **NOT MEASURED** means the inputs do not exist: no READY package, no calibrated baseline, a denominator of 0,
  or usage not reported. The reason is always shown. A missing input is never shown as 0 or 100 %.
- **low sample** marks a value computed from fewer units than the KPI engine's sample threshold.
- **Cohort.** "All runs" includes cloud-model runs, which every run has used since owner decisions
  OD-2026-10-19-06/08. "Production (local-only)" is the feature-003 production KPI definition, unchanged.
- **Driver order vs run.** Retries of a work order (`-rN`) are runs of one driver order. Lead time (K05) runs
  per driver order, from its first admission to its close.
- **Not reported usage.** Fabro reports no usage for ACP nodes. Since feature 007 the forge ACP proxy records
  the counts each prompt result reports, never content. Earlier ACP runs show as not reported, never as 0 tokens.
- **Cost** appears only for models with a price in `config/factory/controlroom.yaml` (`prices`). A subscription
  model shows NOT MEASURED.

## Configuration: `config/factory/controlroom.yaml`

Schema: `specs/007-kpi-control-room/contracts/controlroom-config.schema.json`. An invalid file fails closed with
the reason.

- **Time and shifts:** time zone (default `Europe/Lisbon`) and named shifts (default one 24 h day).
- **Thresholds:**
  - staleness 120 s;
  - lead-time limit 6 h;
  - rework-near ratio 0.66 (2 of 3 cycles);
  - per-station yield threshold 0.5.
- **SPC minimums:** 10 daily subgroups with n ≥ 50 for the p-chart, and 15 points for the I-MR chart.
- **Price table:** optional, per model ID.

## Export

Every panel offers a CSV and a JSON export: `/api/v1/control-room/export?view=floor|scorecard|quality|usage`.
Each row carries its evidence references (gate-log lines, event and archive references).

## Limits

- **No control actions.** The Control Room starts, stops, routes and approves nothing. The feature-005
  operator actions stay on the engineering dashboard with their own token.
- **No compliance claim.** Quality signals are engineering evidence. They are not ASPICE, ISO 26262 or safety
  approvals.
- **Cold start.** After the dashboard starts, the scorecard and usage panels warm up for about a minute while
  run records are read.

API contract: `specs/007-kpi-control-room/contracts/control-room-api.openapi.yaml`.
