---
title: "Reference overview"
description: "These indexes are generated from tracked source on every website build. They expose selected structural metadata, not a running factory."
---

These indexes are generated from tracked source on every website build. They expose selected structural metadata, not a running factory.

- [Commands](/docs/reference/generated/commands/): work-order options from Python AST and developer targets from the Makefile.
- [Configuration and contracts](/docs/reference/generated/contracts/): selected schemas and configuration source locations.
- [Example work orders](/docs/reference/generated/examples/): driver, target, layer, and delivery mode from tracked `workorder.json` files.
- [Python entry points](/docs/reference/generated/python/): installed scripts and selected public functions with source locations.

The build never imports production Python modules or starts models, services, hardware tools, or work orders. It never reads the input documents referenced by work orders. The publication manifest records the source revision and hashes of the selected inputs.

For complete implementation details, use the linked source files. These pages are a navigation reference, not a guarantee that a command or target will succeed on your host.
