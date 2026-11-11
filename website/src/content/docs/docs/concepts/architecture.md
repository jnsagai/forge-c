---
title: "Factory architecture"
description: "Forge-C separates AI work production from deterministic enforcement and external release authority."
---

Forge-C separates **AI work production** from **deterministic enforcement** and **external release authority**.

[![Forge-C architecture and authority boundaries](/media/factory-architecture.svg)](/media/factory-architecture.svg)

Simplified process map. Open the diagram to inspect the full-size SVG.

## The boundaries

| Boundary | Responsibility |
| --- | --- |
| Intake | Hash approved inputs, prepare an isolated workspace, and validate readiness. |
| Fabro workflow | Schedule SWE.1–SWE.6 author, inspection, gate, and rework nodes. |
| Agent skills | Version role instructions, input/output contracts, and permitted operations. |
| MCP and policy | Enforce role-specific tool access and fail closed on missing authorization. |
| Verification tools | Produce compiler, static-analysis, test, coverage, footprint, and configured target evidence. |
| Release Manager and finalizer | Collect workproducts, derive status from evidence, and seal the archive. |
| Independent supervisor | Observe service health, dispatch eligible bounded repairs, and finalize abandoned runs. |
| Human reviewer | Assess the package and retain engineering, safety, and release authority. |

## Production agent access

Every production AI role loads a versioned skill and uses approved MCP operations. Instructions in a prompt are not the security boundary: policy services enforce the permissions. Missing required skills, tools, or authorization block the run before agent execution.

The baseline documents 20 agent roles and nine MCP tool servers. Consult the [configuration index](/docs/reference/generated/contracts/) for the actual files at the built revision; extensions and installed capabilities must be checked against that revision.

## Supervision outside the workflow

The supervisor is independent of Fabro. Healthy polling makes no model calls. A model or orchestrator failure therefore cannot remove the basic health observer. Eligible repair is bounded and reversible; protected policies, immutable evidence, and released archives remain outside automatic repair authority.

## A local-first factory

The factory can run with local model serving and open-source verification tools. Optional model adapters do not change the policy or evidence requirements. Operators must configure the actual provider, tool versions, and authorization for their installation.

This public website is a static documentation site. It has no connection to an operator's factory services or private dashboard.

## Source design

- [Dark factory architecture](https://github.com/jnsagai/forge-c/blob/main/docs/DARK-FACTORY-ARCHITECTURE-v0.4.md)
- [Editable architecture diagrams](https://github.com/jnsagai/forge-c/tree/main/architecture)
- [Constitution](https://github.com/jnsagai/forge-c/blob/main/.specify/memory/constitution.md)
- [Source layout](/docs/development/repository/)
