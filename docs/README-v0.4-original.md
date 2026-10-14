> HISTORICAL: initial v0.4 package README, preserved for context; use root README.md for v0.5.

# Forge-C Dark Factory v0.4 — Claude-ready Spec Kit implementation package

**DESIGN PACKAGE — NOT a deployed self-healing factory.** This repository combines the previously working OSS RCC host demonstrator (v0.1), v0.3 offline-release reference packager, a v0.4 feature specification, 51 actionable Spec Kit tasks, 20 draft agent SKILLs, a 34-operation MCP integration registry, policy prototypes and editable draw.io architecture.

**Start Claude Code with [`CLAUDE_START.md`](CLAUDE_START.md).** Claude implements this plan incrementally; **Fabro + local Qwen** are the intended eventual dark-factory runtime. No paid API or commercial checking tool is required for initial execution.

## Read these first

- [`CLAUDE.md`](CLAUDE.md) — implementation guardrails and first task prompt.
- [Feature specification](specs/002-self-healing-factory/spec.md) — behavior, acceptance scenarios and 40 FRs.
- [Implementation plan](specs/002-self-healing-factory/plan.md) — architecture, APIs, security, milestone M0–M7.
- [Tasks](specs/002-self-healing-factory/tasks.md) — 51 actionable tasks tied to requirements and tests.
- [Data model](specs/002-self-healing-factory/data-model.md) — event, incident, repair, lesson and release entities.
- [Agent registry](config/factory/agents.yaml) / [skills directory](.fabro/skills/) — 20 role-specific SKILL.md contracts.
- [MCP registry](config/factory/mcp-registry.yaml) — 9 planned MCP domain servers, 34 logical operations (NOT implemented).
- [Supervisor policy](config/factory/supervisor-policy.yaml), [trace policy](config/factory/trace-policy.yaml), [token policy](config/factory/token-policy.yaml).
- [Dashboard API design contract](specs/002-self-healing-factory/contracts/dashboard-api.openapi.yaml) and [acceptance scenarios](specs/002-self-healing-factory/acceptance-tests.md) — required for Claude, not implemented.
- [Editable draw.io architecture](architecture/Forge-C_Fabro_DarkFactory_v0.4.drawio) — 7 inherited design tabs (updated overview) + 4 new v0.4 control-plane tabs.

## Architecture

An independent model-free supervisor monitors Fabro, infrastructure and MCP. On faults it creates incidents and dispatches an isolated Repair Agent; deterministic validation promotes or rolls back its patch. Verified lessons become versioned shared knowledge. Dashboard shows health and selectable human/tool/AI/system traces; capture policies never change merely because the viewer hides a category. The Release Manager packages C/H, SWE.1–6, inspection, static/MISRA/coverage/footprint, safety and operational evidence for **human review offline only**.

## Verification — what is actually done

- **Previously executed:** the v0.1 host C/LLVM example and the v0.3 Python release packager were tested in earlier project versions; refer to their original evidence. This package preserves both codebases.
- **This release:** schema/manifest consistency checks can be executed with `python3 tests/spec/validate_design.py`. These check the *design artefacts only*.
- **NOT YET implemented:** MCP wrappers, model-free supervisor, autonomous repair dispatcher, lessons store, dashboard, production Fabro workflows, real target evidence. They are Claude's planned tasks.
- **ASIL B:** safety objective, not certification. MISRA Ccppcheck subset does not establish full MISRA compliance, nor does host coverage establish target verification. Unapproved safety evidence remains BLOCKED.

## Current code locations

- Existing C host RCC demo: `drivers/demo_rcc/` + `scripts/run_oss_demo.sh`.
- Existing SW verification scripts: `tools/`, `scripts/` and `workflows/`.
- Preserved v0.3 packager: `factory/release-manager/` (`tests/test_packager.py` executes against its unchanged v0.3 policy).
- New feature documents: `specs/002-self-healing-factory/` and `.specify/memory/constitution.md`.

## Validate design and legacy packager

```bash
python3 tests/spec/validate_design.py
python3 -m unittest discover -s factory/release-manager/tests -p 'test_*.py' -v
```

GitHub Spec Kit integration: `specify init --here --integration claude --non-interactive` after backing up/committing the repository; see `CLAUDE.md`. No repository or cloud deployment was performed as part of creating this design.
