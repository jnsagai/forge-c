---
title: "Separate LL and HAL orders"
description: "Forge-C builds the low-level register interface and the higher-level HAL in separate work orders. This keeps each requirement set and verification campaign"
---

Forge-C builds the low-level register interface and the higher-level HAL in **separate work orders**. This keeps each requirement set and verification campaign focused.

| Layer | Responsibility |
| --- | --- |
| LL | Header-level register operations, bit preservation, and flag queries. Callers bound their own polling. |
| HAL | Higher-level behavior, status codes, parameter checks, and timeouts, built on a verified LL. |

## The provided-LL boundary

A HAL order requires `--provided-from` pointing to an LL order whose six phase gates passed. The factory copies the header, marks it read-only, and records its source and hash. A missing or unverified LL dependency is refused at preparation.

This boundary prevents a HAL repair from silently changing the LL implementation on which its evidence depends.

## Examples

- `examples/0002a-arm_55_rcc_ll` → `examples/0002b-arm_55_rcc_hal`
- `examples/0009a-iwdg-ll` → `examples/0009b-iwdg-hal`

The original combined RCC example remains historical context. Prefer the separate orders for the current pilot workflow. See [your first work order](/docs/getting-started/first-work-order/) for a command sequence and [ADR-0009](https://github.com/jnsagai/forge-c/blob/main/docs/adr/ADR-0009-separate-ll-and-hal-work-orders.md) for the complete decision.
