# Claude Code — Forge-C v0.5 Production KPI extension

Use the existing Forge-C v0.4 Spec Kit implementation plan as the baseline. **Do not substitute this proposed KPI extension for features 002 (self-healing, skills, MCP, dark workflow, ASIL offline release).**

Read:
1. `.specify/memory/constitution.md` and `CLAUDE.md`.
2. `specs/002-self-healing-factory/{spec,plan,tasks}.md` and event/schema/dashboard contracts.
3. `specs/003-manufacturing-kpis/{spec,plan,tasks,acceptance-tests}.md`.
4. `specs/003-manufacturing-kpis/contracts/`, `config/factory/kpi-policy.yaml`, `docs/KPI-OPERATOR-DASHBOARD-v0.5.md`.
5. `architecture/Forge-C_Fabro_DarkFactory_v0.5.drawio`, last tab **12 Manufacturing KPIs**.

Implement feature 003 using Spec Kit with task IDs KPI-T001..KPI-T020 and tests. Only mark a task complete when executable deterministic evidence exists; these files are **design specifications**, not a claim of a working KPI engine. Keep the supervisor entirely model-free during healthy polling, and compute KPIs without model inference. All model-accessible KPI operations should be read-only through `forge-observer-mcp` and scoped. Reuse existing v0.4 dashboard, event store, release packager and configurable trace filters.

Required behavior: unique production units = driver orders; six station FPY values and package RTY; READY vs BLOCKED separation; deterministic evidence coverage; SFOEE=A×P×Q only with frozen calibrated baselines; no invented metrics when input unknown; batch/replay idempotence; fully traceable KPI snapshots embedded in both READY and BLOCKED handover archives. Throughput, OEE, tokens and footprint NEVER override ASPICE/safety process gates, and no AI signoff of ASIL B.

Response: minimal status/issue lines, tests and evidence paths. Write engineering rationale into documents, not token-heavy chat output.
