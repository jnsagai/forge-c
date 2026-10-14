# Forge-C v0.5 — Complete Claude Implementation Handoff

This is the **entire Forge-C working baseline and Spec Kit plan**, not only the KPI extension. The project retains versions 001, 002, and 003 in their source directories. Do not throw away preceding milestones or generate a competing greenfield implementation.

## Mandatory reading order

1. `README.md`, `CLAUDE.md`, `CLAUDE_START.md`, `.specify/memory/constitution.md`.
2. `specs/001-factory/{spec,plan,tasks}.md`: existing OSS HAL driver baseline.
3. `specs/002-self-healing-factory/{spec,plan,tasks,data-model,acceptance-tests}.md` plus all schemas, `config/factory/*.yaml`, all `SKILL.md`, and release manager specifications.
4. `specs/003-manufacturing-kpis/{spec,plan,tasks,acceptance-tests}.md`, its JSON contracts, `config/factory/kpi-policy.yaml`, and `KPI_CLAUDE_START.md`.
5. `architecture/Forge-C_Fabro_DarkFactory_v0.5.drawio` (canonical, 12 editable tabs). Older diagrams are reference history.

## Implementation sequencing

- **Foundation (002 M0–M2):** baseline tests, version/OSS-license inventory, Fabro API capability validation, agents SKILL enforcement, MCP wrappers and permission tests. Require real MCP handshake; no direct-shell fallback for production agents.
- **Operational control (002 M3–M5):** independent model-free health supervisor, externally dispatched repair agent for Fabro failures, rollback and durable lessons; implement read-only human dashboard and configurable trace channel capture/viewing.
- **Process/release (002 M6–M7):** SWE phase author/inspector loops; freeze/rework/reinspect baselines; reproduce static, unit, coverage and footprint gates; integrate release packager and offline handover states.
- **Manufacturing KPIs (003 K0–K4):** start event/storage instrumentation when 002 event schema is stable, then deterministic analytics, read-only operator dashboard drilldown, KPI snapshots integrated into READY/BLOCKED packages. Follow task dependencies; KPI schema/contracts exist now, engine doesn't.

## Critical acceptance invariants

- No production agents without a validated SKILL and scoped MCP access.
- Supervisor healthy polling never calls AI models. When Fabro is unavailable, external repair dispatch still works.
- A repairing agent never changes immutable evidence, released archives, baselined safety policies, or historical KPIs.
- Each SWE station uses a different author/inspector role, checklist, frozen revision and immutable initial verdict. Failed inspections loop back and upstream failures revalidate impacted downstream baselines.
- Deliver a checksummed `READY_FOR_OFFLINE_REVIEW` or `BLOCKED` package with explicit missing evidence; no autonomous safety signoff.
- KPI numerators/denominators/event provenance included, missing data shows UNKNOWN/N/A/NOT_COMPUTABLE as appropriate. No fabricated OEE baseline.
- Source, tests, verification and real implementation remain open-source. Claude implementation can use Claude Code; local Qwen is the intended production inference model.

## Commands to verify what already exists

```bash
python3 tests/spec/validate_design.py
python3 -m unittest discover -s tests -v
python3 -m unittest discover -s factory/release-manager/tests -p 'test_*.py' -v
python3 scripts/verify_bundle.py
./scripts/run_oss_demo.sh  # only with required LLVM toolchain available
```

## Suggested starting Claude prompt

> Implement Forge-C v0.5 using CLAUDE.md, CLAUDE_START.md, and PROJECT_HANDOFF_v0.5.md as the contract. Preserve the existing OSS C driver, gates and v0.3 reference packager. Deliver all remaining feature 002 tasks M0–M7, then dependent feature 003 KPI tasks K0–K4, using the authored Spec Kit acceptance tests. Verify actual Fabro MCP/Skills APIs and pin open-source tool versions. Every agent needs a SKILL and scoped MCP operations; the non-AI supervisor must self-heal and capture lessons, the dashboard must support configurable independent trace filters, and the release manager must package full SWE.1–SWE.6 and ASIL B-target evidence for offline review, including deterministic KPI snapshots. Output terse status and issue codes; keep rationale in artifacts and show tests/evidence for each closed task. Never claim compliance or functionality without valid evidence.

## Explicitly not provided

No licensed MISRA standard, commercial analyzers, AI model weights, hardware BSP, production deployment, ASIL B approval, or implemented autonomous supervision/repair/KPI runtime is bundled. Those remain prerequisites/implementation tasks, not fabricated deliverables.
