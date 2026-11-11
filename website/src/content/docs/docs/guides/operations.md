---
title: "Operate the factory"
description: "Load `scripts/forge-env.sh` in each shell. Set `FORGE_DATA_ROOT` first when using a different volume from the reference installation."
---

Load `scripts/forge-env.sh` in each shell. Set `FORGE_DATA_ROOT` first when using a different volume from the reference installation.

## Observe service health

```sh
./scripts/forge_services.sh status
systemctl --user status forge-supervisor
python -m forge_factory.fabro.progress <run-id>
```

The independent supervisor polls service health, records incidents, dispatches policy-eligible repairs, and seals terminal runs that lack a package. Healthy polling makes no AI model calls.

## Preserve evidence during recovery

Repair has bounded attempts, isolation, validation, and rollback. It cannot rewrite released archives, historical evidence, baselined safety criteria, or protected policies. Verified lessons become reusable only after validation.

Use the failure diagnosis and backup procedures in the [operations runbook](https://github.com/jnsagai/forge-c/blob/main/docs/OPERATIONS-v0.4.md). Refer to [continuous reliability engineering](https://github.com/jnsagai/forge-c/blob/main/docs/cre-runbook.md) for incident, CAPA, rollback, and escalation workflows.

## Use private monitoring

```sh
python -m forge_factory.dashboard.app
make kpi
```

The operator dashboard is read-only and defaults to loopback. Follow its authentication configuration and use an authenticated reverse proxy for authorized remote access. This documentation site does not expose the dashboard or a runtime control endpoint.

## Treat AFO modes separately

Autonomous Factory Operations adds durable scheduling, recovery, and authority boundaries. The 21 October AFO status includes partial and blocked work and deferred reboot drills. On 26 October the owner signed a scope-bound PILOT authorization for the ST-driver benchmark; the [benchmark record](https://github.com/jnsagai/forge-c/blob/main/evidence/v0.4/benchmark/st-drivers/record.md) includes real AFO-launched runs. Implementation alone is not authorization for unattended active operation.

Read the [AFO operations guide](https://github.com/jnsagai/forge-c/blob/main/docs/afo/OPERATIONS-AFO.md), [limitations](https://github.com/jnsagai/forge-c/blob/main/docs/afo/LIMITATIONS-AFO.md), and [evidence-derived status](https://github.com/jnsagai/forge-c/blob/main/docs/afo/AFO-STATUS.md) before choosing any mode.

## Recorded Control Room view

[![Historical Forge-C Control Room capture from 19 October 2026](/media/control-room.png)](/media/control-room.png)

This is a recorded development screenshot, not a live dashboard. Historical values do not describe the current campaign. [Original evidence image](https://github.com/jnsagai/forge-c/blob/main/evidence/v0.4/runs/CR-T044/control-room-after-r168.png).
