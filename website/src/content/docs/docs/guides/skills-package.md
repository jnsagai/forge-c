---
title: "Use Forge-C as skills in your coding agent"
description: "forge-c-hi packages the factory's know-how as APM skills: author and independent-inspector pairs for every V-model stage, deterministic gates, and sealed review packages, in Claude Code, Codex, Copilot and others."
---

The factory runs unattended on your own machine. **forge-c-hi** brings the same discipline into the coding agent you
already use, as an [APM](https://github.com/microsoft/apm) package in
[`packages/forge-c-hi/`](https://github.com/jnsagai/forge-c/tree/main/packages/forge-c-hi).

## What you get

- An **author** and an **independent, read-only inspector** skill for each V-model stage, from system requirements to
  system qualification.
- **Deterministic gates** (schema, requirement-quality rules, traceability, write scope, reference-document citations,
  build, static analysis, unit tests, coverage). A check that cannot run is NOT_RUN and counts as a gap.
- **Standard profiles**: a generic baseline, ISO 26262, IEC 61508 and ASPICE 4.0, with a template for DO-178C,
  EN 50716 or IEC 62304. Switching profile changes configuration, not skills.
- **Any model per role**: Claude Code, Codex, a local Ollama model through Codex, or any CLI bound as a custom role.
- A sealed **offline review package**, `READY_FOR_OFFLINE_REVIEW` or `BLOCKED` with the gap list.

## Install

```sh
apm install jnsagai/forge-c/packages/forge-c-hi#forge-c-hi-v0.1.0 --target claude,codex
```

Then follow the package README: it walks through the Safety Supervisor example on an STM32N6, from stakeholder needs
to software requirements, with Claude as author and GPT as inspector.

## How it relates to the factory

| | Factory | forge-c-hi |
|---|---|---|
| Runs | unattended, Fabro workflows, supervisor, self-repair | in your coding agent, or with the package's conductor script |
| Process | ASPICE SWE.1–SWE.6 for drivers | the whole V from system requirements, under a chosen standard profile |
| Inputs | work orders for drivers | natural-language needs (middleware, application) or reference documents (HAL, LL) |
| Output | sealed review package | sealed review package |

Neither certifies anything: both produce input for an offline review by qualified people.
