---
title: "Status and limitations"
description: "Pilot status. Evidence snapshot: 21 October 2026. This page reports recorded project evidence; it is not a live factory dashboard or a new verification cam"
---

**Pilot status. Evidence snapshot: 26 October 2026.** This page reports recorded project evidence; it is not a live factory dashboard or a new verification campaign.

## RCC and IWDG regression campaign

The regression campaign now has a `READY_FOR_OFFLINE_REVIEW` run for each of its seven work orders, with zero declared gaps in those successful packages. Five succeeded on the first pass. RCC LL and IWDG HAL reached review-ready in later runs after documented fixes and rework.

| Work-order family | Recorded successful run |
| --- | --- |
| Generated STM32N6 RCC LL | WO-0002A-STM32N6-RCC-LL-rc1 |
| Generated STM32N6 RCC HAL | WO-0002B-STM32N6-RCC-HAL-rc1 |
| Delivered RCC LL | WO-0008A-STM32N6-RCC-LL-rc1b |
| Delivered RCC HAL | WO-0008B-STM32N6-RCC-HAL-rc1 |
| CMSIS-style RCC LL | WO-0008C-ST-RCC-LL-rc1 |
| Generated STM32N6 IWDG LL | WO-0009A-STM32N6-IWDG-LL-rc1 |
| Generated STM32N6 IWDG HAL | WO-0009B-STM32N6-IWDG-HAL-rc4 |

The [campaign record](https://github.com/jnsagai/forge-c/blob/main/evidence/v0.4/runs/RC1/README.md) documents first-pass failures, CAPA-065/066/067, reruns, source revisions, and the final IWDG HAL result. These runs used configured Codex authors and Claude inspectors; they do not establish the same outcome for the default local model.

**Review-ready is not safety approval or production release.** Zero declared gaps is relative to that package's configured scope and recorded dispositions.

## STM32N6 frozen-driver benchmark

The 26 October benchmark covers **GPIO, SPI, USART, TIM, and CRC**, using the existing STM32CubeN6 low-level driver code in `FROZEN` mode. The factory creates the associated SWE workproducts and checks the delivered code against independently derived requirements.

The recorded benchmark includes `READY_FOR_OFFLINE_REVIEW` packages with zero declared gaps for all five peripherals, alongside earlier blocked attempts and their findings. Those successful benchmark runs were launched through AFO with Codex authors and Claude inspectors. Some recorded attempts have no package; the record preserves those outcomes rather than presenting them as successful runs.

The [benchmark record](https://github.com/jnsagai/forge-c/blob/main/evidence/v0.4/benchmark/st-drivers/record.md) identifies each run, revision, phase result, package status, gaps, duration, and reported model usage. The [feature specification](https://github.com/jnsagai/forge-c/blob/main/specs/015-st-driver-benchmark/spec.md) describes scope and source restrictions. Results remain bounded by each work order and its recorded dispositions.

## Factory implementation milestones

The [evidence-derived implementation report](https://github.com/jnsagai/forge-c/blob/main/docs/IMPLEMENTATION-STATUS-v0.4.md) records 51/51 tasks for the self-healing factory, 20/20 for manufacturing KPIs, and 54/54 for continuous reliability engineering at its dated revision.

The [AFO report](https://github.com/jnsagai/forge-c/blob/main/docs/afo/AFO-STATUS.md) records **66 pass, 3 partial, and 6 blocked** tasks in its 21 October snapshot. Subsequent 26 October benchmark evidence records real AFO-launched work orders and an owner-signed, scope-bound PILOT authorization for the benchmark. Deferred reboot and recovery drills, soak evidence, and operator readiness remain material limits; the earlier AFO status snapshot predates the benchmark.

The [enhanced assurance report](https://github.com/jnsagai/forge-c/blob/main/docs/assurance/EASA-STATUS.md) records 72 passing base tasks and seven passing owner-addendum tasks at its revision. Task completion does not independently establish safety compliance.

## Boundaries to keep visible

- Forge-C and its toolchain are not certified or automatically qualified under ISO 26262.
- No Automotive SPICE capability assessment is conferred by running the six phases.
- Cppcheck's MISRA addon covers a subset; full MISRA compliance is not claimed.
- Host, object-level, simulator, and hardware results must be distinguished and tied to the actual run.
- Licensed MCU manuals and normative standards are not distributed with the public website.
- Optional cloud or agent adapters have different service requirements from the local open-source runtime.
- Each safety, engineering acceptance, and production release decision needs competent external review.

## Reading older documents

Some baseline README, AFO, and operations sections predate target simulation, verifier integrations, the successful pilot packages, and the 26 October AFO benchmark. Treat them as historical context when they conflict with a later dated campaign record. Always follow the evidence revision and the package's actual limitations.
