---
title: "Assess existing C code"
description: "A brownfield order starts with a supplier delivery, vendor driver, or legacy C implementation. It also needs authoritative reference documents and a clearl"
---

A brownfield order starts with a supplier delivery, vendor driver, or legacy C implementation. It also needs authoritative reference documents and a clearly bounded scope.

Requirements are derived from the approved reference documents before the delivered code is injected. Existing code is not treated as its own specification.

## Choose the modification policy

| Mode | Allowed behavior |
| --- | --- |
| `FROZEN` | Assess the delivered code without changing it; code defects are escalated. |
| `FIX_ALLOWED` | Permit changes only for an eligible code defect, in the declared scope, with a license allowing modification. |

The `delivery` block records origin, license, permission to modify, source files and fingerprints, and scope. Intake rejects missing provenance or incompatible modification permissions.

## Follow conformance

The checks compare requirement cases with the delivered function's actual register effects. Findings include a requirement with no implementation, delivered behavior without a requirement, and contradictory effects.

Delivered-file fingerprints and open conformance findings are checked again during packaging. The change report and delivery provenance remain part of the review evidence.

## A broader STM32N6 benchmark

The [26 October ST-driver benchmark](https://github.com/jnsagai/forge-c/blob/main/evidence/v0.4/benchmark/st-drivers/record.md) used frozen STM32CubeN6 low-level drivers for GPIO, SPI, USART, TIM, and CRC. The record includes both successful offline-review candidates and blocked attempts. Its results are scoped to the selected delivered functions, tools, inputs, and owner decisions.

## Start from an existing example

- `0008a-rcc-ll-delivered`: delivered low-level RCC code.
- `0008b-rcc-hal-delivered`: delivered HAL code.
- `0008c-st-cube-rcc`: CMSIS-style RCC pilot.

Use the [example index](/docs/reference/generated/examples/) and [brownfield contract](/docs/reference/generated/contracts/) to inspect the current source. The [original brownfield guide](https://github.com/jnsagai/forge-c/blob/main/docs/BROWNFIELD-WORK-ORDERS.md) contains historical limitations; newer campaign evidence on the [status page](/docs/status/) records subsequent progress. A successful pilot does not generalize to arbitrary vendor code.
