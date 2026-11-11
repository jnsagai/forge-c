---
title: "Your first work order"
description: "## Before you run"
---

## Before you run

Complete [installation](/docs/getting-started/installation/), confirm the services are ready, and obtain the approved inputs referenced by the selected example. The repository records provenance for MCU documents, but does not redistribute their licensed text. A fresh clone alone is insufficient for the STM32N6 pilot.

A work order declares the driver, target, scope, budgets, input paths, and API layer. Review [the generated example index](/docs/reference/generated/examples/) before choosing an order. Commands on this page launch real factory work; documentation builds do not execute them.

## Start with the low-level layer

Use a unique work-order identifier. From the repository root, in a shell with the environment loaded:

```sh
. scripts/forge-env.sh
python -m forge_factory.workorder   --example examples/0002a-arm_55_rcc_ll   --wo WO-RCC-LL-demo   --detach
```

This selects the RCC low-level (LL) driver. The default model/provider flags select the local Ollama path. The order runs intake, preflight, the six SWE phases, and packaging. Input or permission failures stop the work rather than silently weakening the checks.

The submitted order returns a run identifier. Use that returned identifier to observe progress:

```sh
python -m forge_factory.fabro.progress <run-id>
```

## Build a HAL on verified LL

LL and HAL are separate orders. The HAL order consumes the previously verified LL header and records its provenance. It cannot change that provided header.

After the LL order has passed all six phase gates:

```sh
python -m forge_factory.workorder   --example examples/0002b-arm_55_rcc_hal   --wo WO-RCC-HAL-demo   --provided-from WO-RCC-LL-demo   --detach
```

A missing, unverified, or incorrectly layered dependency is refused during preparation. See [LL and HAL](/docs/guides/ll-and-hal/) for the boundary and source decision.

## Read the result

Archives are written beneath `FORGE_ARCHIVE_DIR` with recorded hashes and evidence. A package has one of two terminal statuses:

| Status | Meaning |
| --- | --- |
| `READY_FOR_OFFLINE_REVIEW` | The configured gates passed. The result is a candidate for independent human review. |
| `BLOCKED` | A required check, input, or artifact is missing or failed. Review the explicit findings. |

Follow the [offline review guide](/docs/guides/offline-review/). Neither status authorizes deployment or establishes safety compliance.

## When the order stops

Start with `REVIEW_SUMMARY.md`, `missing_artifacts.json`, and the recorded gates. Resolve the actual input or tool issue and use the documented recovery path. Never change a protected policy or mark an artifact approved just to make a run pass.

All current flags, including intake-only and configured model adapters, are listed in [command reference](/docs/reference/generated/commands/).
