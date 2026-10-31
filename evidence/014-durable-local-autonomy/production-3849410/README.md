# Dedicated Omniverse2 production cutover — 2026-10-27

The owner requested the factory running for production within eight hours at
20:50:49 UTC (deadline 2026-10-28 04:50:49 UTC), accepting imperfections. This
supersedes the earlier hold on dedicated-factory activation. It does not authorize
firmware release, private-key access, mission replenishment or fabricated readiness.

**Deployed source: `3849410a4de676266c0754ae86b91f1c82b0180f`.** The dedicated
controller started at 22:02:51 UTC on Omniverse2, under systemd with its separate
external watchdog timer. Backend Ollama, gateway and Fabro health checks pass.
This is **control-plane deployment, not yet production inference readiness**.
The owner explicitly authorized agent signing for the prepared production grant;
it is now signed, verified AUTH_OK and installed. Effective mode is PILOT. Scope:
local Qwen3.6/manual LL orders,one concurrent order,120ktokens and3attempts/order,
6h job limits,expiry2026-10-29T05:00Z. Existing SSH agent only; no private-key read
or copy. No Qwen request or
product attempt was made by this deployment.

## Runtime fixes and regression evidence

- `8dc8842af11861ce9c81a714b0f691741ee87667` fixes CRE policy selection:
  `FORGE_CRE_POLICY` had been ignored, preventing deployment-owned operational
  recovery recipes from taking effect. Explicit argument > environment > default;
  invalid authority fails closed. Malformed live updates retain the last valid
  holder policy. Local exact-revision regression: 124 PASS,17.041s.
- `3849410` fixes stack CLI parsing: REMAINDER consumed options after the command,
  passing the rendered unit's `--profile` into nsenter and ignoring the API bridge
  host-port selection. Tests cover both option positions, worker arguments after
  `--`, the host-port option and refusal of unknown non-exec arguments.
- Local affected regression:49 PASS/1 SKIP,10.381s. The skip required an explicit
  private SafeC engine pin. An earlier relative-PYTHONPATH invocation failed a
  subprocess import; retained, then corrected to an absolute checkout path.
- Omniverse2 affected deployment regression:50 PASS/1 SKIP,34.301s. The skipped
  interrupted-engine case separately passed against the existing pinned SafeC
  engine:1 PASS,0.903s. No inferred whole-suite or whole-private-engine result.
- Native initial runs exposed missing isolated test event roots and PlantUML
  toolchain references. Those failures remain in private deployment logs. Final
  fixtures use isolated state plus a read-only reference to the installed toolchain;
  no quality gate or assertion was weakened.

Commands and exact suites are recorded in regression.json. All local artifacts
are on loop10; native tests ran on Omniverse2. No competing GPU work was started.

## Actual cutover and recovery scope

Root: `/mnt/data/forge-c/production-local-014`; source checkout: `repo/`.
Only `forge-conductor-local-omniverse2.service` was replaced. Added dedicated
`forge-afo-watchdog-014-omniverse2.service` and `.timer`; generic services, Feature015
and the old runtime data were preserved. Do not use the all-unit installer here.
Backend components retain one admitted inference request and the pinned local
Qwen3.6 profile. The host Fabro API bridge binds 127.0.0.1:32491; it is not a public
web UI. New provider startup was model-free.

Before cutover the original root was explicitly selected, the old Fabro API
reported11 terminal runs and no active runs, and Ollama reported no resident
models. A first legacy-client probe used an unsupported context-manager API;
a second probe accidentally inherited the new root. Both are retained and are
not accepted as legacy quiescence evidence. The final explicit-root probe passed.

Four historical BLOCKED orders and20 attempts remain in the migrated database;
none were resumed or given a new allowance. Original unit and a consistent
read-only SQLite snapshot are retained in `deployment/rollback/`. Unit hash and
operator epoch were checked immediately before the bounded cutover. Operator
intent lives outside the authoritative application mount and remains epoch1.

Actual SIGTERM clean-exit smoke: systemd restarted the controller in10.602s,
MainPID changed, NRestarts incremented0→1, successful exit status retained.
The first fresh heartbeat reported `lease_held_elsewhere`: restoration of the
process is separate from the original120-second scheduler lease expiry. Later
heartbeats confirm resumed scheduling (`idle`), including healthy PILOT cycle31
at22:12:59Z. The initial unsupported systemctl option failed before signaling and
is retained. No crash/hang/reboot/mount-loss or multi-hour campaign claim follows.
The timer's first invocation raced startup and reported HEARTBEAT_MISSING; its
later invocation reported HEALTHY. That initial observation is not erased.

## Remaining production and qualification limits

- Production signature is current; no automatic renewal. Expiry remains29Oct05UTC.
- Product author/inspector capability receipts are not independently qualified.
  The product path lacks measured semantic obligations. Do not disable durable
  admission, manufacture receipts or treat protocol qualification as product
  qualification to get an inference call through.
- Exact source pinning must be respected by capability identity. Documentation
  commits do not automatically change the deployed checkout.
- API bridge recovery across a backend/host restart requires further verification;
  the running external watchdog currently restores namespace services separately.
- Existing WWDG verification-model mismatches, private original input gaps and
  inspector freeze remain. No full WWDG retry was made.
- RCC recovery,30-product benchmark, learning benefit and24/72/168-hour campaigns
  remain unproven/NOT_RUN. Formal ledger remains30/58; no task was newly ticked.

## Rollback and operator access

The owner requested pausing Codex to conserve the remaining weekly credits while
leaving Omniverse2 running overnight. Controller and recovery timer remain active.
Queue:4BLOCKED historical orders,20attempts,0new durable requests. There is no
eligible driver job; do not promise overnight Qwen engineering progress or campaign
qualification. Codex must remain paused until the owner resumes it. Latest native
status and signing delegation are retained with this evidence checkpoint.

Remote OS-authenticated operator wrapper:
`/mnt/data/forge-c/production-local-014/deployment/forge-c-operator status`.
It uses the private deployment environment and existing AFO CLI, with no new
scheduler, grant or model path. Use `list` to inspect orders and ordinary controls
with an explicit reason. Do not include the private environment or secrets in logs.

The deployment environment file is private and contains no private key. Use its
paths with the existing AFO CLI outside the namespace for OS-authenticated pause,
drain, resume and shutdown; preserve operator intent epochs. A future stop must
not be undone by replaying this one-time deployment script. Original unit backup:
`/mnt/data/forge-c/production-local-014/deployment/rollback/original-conductor.service`.
Rollback is an operator action: restore that exact unit, reload systemd and start
the old dedicated controller only after current native inference has settled.
Never replace historical data from the backup merely to clear a failure.
