---
title: "Forge-C documentation"
description: "Forge-C is an open-source, local-first software factory for embedded C drivers. It coordinates AI authors and separate inspectors across the Automotive SPI"
---

Forge-C is an open-source, local-first software factory for **embedded C drivers**. It coordinates AI authors and separate inspectors across the Automotive SPICE SWE.1–SWE.6 workflow, runs deterministic checks, and seals the results for offline human review.

The factory is a **pilot**. Its output is engineering evidence, not safety approval, an ASPICE assessment, or a production release.

## Start with a concrete task

- [Install the tools](/docs/getting-started/installation/) or try the host demonstration without an AI model.
- [Run your first work order](/docs/getting-started/first-work-order/) using the low-level RCC example.
- [Review an archive](/docs/guides/offline-review/) and understand what each terminal status means.
- [Assess delivered C code](/docs/guides/brownfield/) with an explicit modification boundary.

## Understand what runs

[Architecture](/docs/concepts/architecture/) describes the workflow, policy, verification, and supervision boundaries. [Workflow](/docs/concepts/workflow/) follows an order from approved inputs to a sealed archive. [Verification](/docs/concepts/verification/) explains why a passing tool result applies only to the recorded scope and assumptions.

## Find exact interfaces

The [reference section](/docs/reference/) includes build-generated indexes of command options, example work orders, configuration files, schemas, and Python entry points. These pages are extracted without starting the factory, importing production modules, or reading licensed MCU manuals.

Read [status and limitations](/docs/status/) before choosing an integration. The status page distinguishes the latest recorded pilot campaign from older baseline documentation.
