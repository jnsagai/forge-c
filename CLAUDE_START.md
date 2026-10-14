# Copy-paste this into Claude Code at the Forge-C repository root

Implement Forge-C v0.4 using **the existing GitHub Spec Kit specification and plan** in `specs/002-self-healing-factory/`.

Read `CLAUDE.md`, `.specify/memory/constitution.md`, `spec.md`, `plan.md`, `tasks.md`, `data-model.md`, `acceptance-tests.md`, `quickstart.md`, all JSON contracts and `contracts/dashboard-api.openapi.yaml`, and `architecture/Forge-C_Fabro_DarkFactory_v0.4.drawio` first.

Requirements are non-negotiable: a SKILL.md for every AI role; an MCP interface for every engineering tool callable by agents (create OSS adapters if absent); a deterministic no-model supervisor independent of Fabro polling periodically; autonomous Repair Agent with isolation, deterministic tests, rollback, incident records and validated lessons shared across workflows; dashboard for supervision and user-selected human/tool/AI/supervisor/audit trace channels with independent capture levels; zero healthy supervisor tokens; tight agent tokens, compact JSON status+issue output and no unnecessary explanation; complete offline software/ASPICE SWE.1-6/ASIL B evidence packaging by final Release Manager, with human approval only offline.

Start with **M0/T001** and work through milestones M0–M7. Implement functional code, tests, runnable workflow, documentation and reliable migration. Reuse original open-source Forge-C demo and v0.3 reference packager; do not break them. Verify each task with deterministic tests; do not mark something implemented if only documented. Do not invent Fabro CLI/MCP/DOT capabilities; confirm installed versions. Ensure memory/footprint and safety quality gates cannot be bypassed by auto-repair. Product runtime must remain open-source + local Qwen, even though Claude Code implements the factory.

Respond with concise per-task status and exact evidence paths; put engineering detail in versioned files, not in terminal narration. Do not ask for human interaction during normal dark-factory execution. Final status must be READY_FOR_OFFLINE_REVIEW or BLOCKED, never `ASIL_B_APPROVED`.


### v0.5 mandatory continuation

After reviewing v0.4 M0–M7, also read `KPI_CLAUDE_START.md` and `specs/003-manufacturing-kpis/` for the versioned software manufacturing KPIs, with dependency-aware K0–K4 tasks. Factory output includes evidence-linked KPI snapshots; all KPI computations are model-free.
