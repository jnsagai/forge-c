---
title: "Repository map"
description: "| Path | Responsibility |\n| --- | --- |\n| `factory/python/forge_factory/` | Workflow, gateway, MCP servers, policies, supervisor, incidents, lessons, event"
---

| Path | Responsibility |
| --- | --- |
| `factory/python/forge_factory/` | Workflow, gateway, MCP servers, policies, supervisor, incidents, lessons, events, KPIs, assurance, and packaging. |
| `.fabro/skills/` | Versioned production agent roles. |
| `config/factory/` | Permissions, tool registry, safety, supervision, traces, tokens, and KPI policy. |
| `examples/` | Work-order specifications and approved-input provenance. |
| `specs/` | Feature requirements, plans, contracts, tasks, and acceptance criteria. |
| `drivers/` | Baseline C demonstrations. |
| `tests/` and `factory/python/tests/` | Design, C, Python, integration, and reliability checks. |
| `evidence/` | Recorded runs, reports, review packs, and provenance. |
| `docs/adr/` | Architectural and authority decisions. |
| `architecture/` | Editable architecture diagrams. |
| `website/` | Public landing page, documentation, generated references, and build checks. |

Browse the [public source tree](https://github.com/jnsagai/forge-c). The website is built independently of the factory's runtime environment and does not require the licensed inputs needed by a real target order.
