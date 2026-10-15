# Forge-C v0.5 — Complete Open-Source Dark Factory Project

**Project state: IMPLEMENTATION PLAN + TESTED BASELINE COMPONENTS, NOT A DEPLOYED FACTORY.**

Forge-C is an open-source, autonomous software factory focused on **ultra-low-memory-footprint embedded C HAL / low-level drivers**, using Fabro for orchestration and local Qwen for production agents. Claude Code is the implementation engineer for this repository, **not a mandatory production runtime model or paid dependency**. Engineering workproducts target **Automotive SPICE 4.0 SWE.1–SWE.6** and support an **ISO 26262 ASIL B development lifecycle**, with offline human safety review.

**Begin with [CLAUDE_START.md](CLAUDE_START.md) and [KPI_CLAUDE_START.md](KPI_CLAUDE_START.md).**

## Versioned feature plans (all included)

| Feature | Content | Primary source |
|---|---|---|
| 001 — OSS C driver bootstrap | Host RCC driver, CMake/Clang/LLVM tests, static check, footprint scripts, safety gates | [`specs/001-factory/`](specs/001-factory/) |
| 002 — Self-healing dark factory | 20 agent SKILLs; 9 MCP service definitions / 34 proposed operations; SWE.1–6 independent inspections; model-free supervisor; repair + lessons; trace dashboard; offline Release Manager | [`specs/002-self-healing-factory/`](specs/002-self-healing-factory/) |
| 003 — Manufacturing KPI system (v0.5) | 20 KPIs, deterministic aggregation design, event provenance, data contracts, release snapshots; dependent implementation backlog | [`specs/003-manufacturing-kpis/`](specs/003-manufacturing-kpis/) |

## Key project paths

| Purpose | Location |
|---|---|
| Claude implementation contract | [`CLAUDE.md`](CLAUDE.md) |
| Combined v0.5 handoff | [`PROJECT_HANDOFF_v0.5.md`](PROJECT_HANDOFF_v0.5.md) |
| 002 functional specs / milestone tasks | [`specs/002-self-healing-factory/spec.md`](specs/002-self-healing-factory/spec.md), [`tasks.md`](specs/002-self-healing-factory/tasks.md) |
| 003 KPI specs / milestone tasks | [`specs/003-manufacturing-kpis/spec.md`](specs/003-manufacturing-kpis/spec.md), [`tasks.md`](specs/003-manufacturing-kpis/tasks.md) |
| All editable draw.io diagrams | [`architecture/Forge-C_Fabro_DarkFactory_v0.5.drawio`](architecture/Forge-C_Fabro_DarkFactory_v0.5.drawio) (12 tabs), [`architecture/history/`](architecture/history/) |
| Agent SKILLs and permissions | [`.fabro/skills/`](.fabro/skills/), [`config/factory/agents.yaml`](config/factory/agents.yaml) |
| Planned MCP adapter registry | [`config/factory/mcp-registry.yaml`](config/factory/mcp-registry.yaml) |
| Supervisor, traces, token limits, KPI policies | [`config/factory/`](config/factory/) |
| RCC host demonstrator | [`drivers/demo_rcc/`](drivers/demo_rcc/), [`tests/c/`](tests/c/) |
| Build/verification tools | [`tools/`](tools/), [`scripts/`](scripts/) |
| Reference Release Manager packager | [`factory/release-manager/`](factory/release-manager/) |
| ASPICE/ASIL engineering templates | [`templates/`](templates/), [`docs/COMPLIANCE-MATRIX.md`](docs/COMPLIANCE-MATRIX.md) |
| Tests and design-contract validation | [`tests/`](tests/), [`factory/release-manager/tests/`](factory/release-manager/tests/) |
| Existing host demonstration evidence | [`evidence/oss-demo/`](evidence/oss-demo/) — host only, **not ASIL B target evidence** |
| File catalogue and integrity checks | [`PROJECT_MANIFEST.json`](PROJECT_MANIFEST.json), [`SHA256SUMS.txt`](SHA256SUMS.txt), [`scripts/verify_bundle.py`](scripts/verify_bundle.py) |

## Run existing baseline checks (Ubuntu)

```bash
python3 tests/spec/validate_design.py
python3 -m unittest discover -s tests -v
python3 -m unittest discover -s factory/release-manager/tests -p 'test_*.py' -v
python3 scripts/verify_bundle.py

# Optional: if Clang/Ninja/LLVM tooling is present, execute host RCC demo:
./scripts/run_oss_demo.sh
```

The 002 design validator requires PyYAML and jsonschema (`python3 -m pip install PyYAML jsonschema` in an isolated development environment). Host demo requires installed LLVM/Clang build tools. These commands **do not** validate the unfinished autonomous platform or any real MCU/ASIL B release.

## Non-negotiable architecture

1. Each production AI role loads a versioned SKILL. Every engineering tool the agent can invoke is exposed through a least-privilege MCP adapter; implementation bootstrap may use local shell.
2. Fabro hosts SWE.1–SWE.6 production steps; a **different AI inspection role** checks each frozen workproduct using a versioned checklist. Failed inspections create findings and trigger bounded rework and reinspection.
3. A **model-less supervisor** runs separately from Fabro. Eligible incidents dispatch a repair agent into an isolated workspace, validate changes deterministically, rollback upon regression, and publish only verified lessons shared between workflows.
4. Operator dashboard supports independent event **capture** and user-selected **display** filters, including human, tool, AI summary, audit, supervisor and repair traces. No secrets or hidden reasoning in logs.
5. Token-efficient agents emit concise structured status/issues; verification reports and traceable workproducts remain complete on disk.
6. A final **Release Manager agent** always attempts a checksummed offline evidence package. State is `READY_FOR_OFFLINE_REVIEW` or `BLOCKED`; never an automatic ASIL B approval.
7. KPIs (software OEE, throughput, inspection FPY/RTY, tokens, resource footprint, recovery and evidence completeness) are calculated from deterministic events. KPIs cannot bypass quality/safety gates.

## Current implementation status (night run 2026-10-14/15, branch `night-run/2026-10-14`)

Status is generated from evidence records only: [`docs/IMPLEMENTATION-STATUS-v0.4.md`](docs/IMPLEMENTATION-STATUS-v0.4.md)
(task → FR → test → `evidence/v0.4/runs/<task>/latest.json`). Operations: [`docs/OPERATIONS-v0.4.md`](docs/OPERATIONS-v0.4.md).
Decisions: [`docs/adr/`](docs/adr/) (ADR-0001…0006).

- **Implemented and tested:** `factory/python/forge_factory/` — agent/SKILL registry + preflight (20 versioned SKILLs),
  deterministic Fabro policy hook (role/phase/path authorization, turn budget), 9 Forge MCP servers with one-time
  authorization tickets, no-reasoning local LLM gateway, SWE.1–SWE.6 inspection engine (EARS SWE1-07, HAL guideline
  verification node SWE3-07), generated fail-closed Fabro workflow, model-free supervisor (systemd, watchdog,
  zero model calls), isolated repair + CAS promotion/rollback, evidence-gated lessons, event store + capture policy,
  read-only dashboard (SSE), token governor, v0.4/v0.5 offline packager overlay, KPI engine K01–K20 (feature 003).
- **Live evidence on local qwen3:8b via Fabro 0.362:** autonomous repair (rollback then promotion, lesson validated and
  reused), policy denials of native-tool bypass, STM32N6 RCC work orders reaching first-pass SWE.1/SWE.2 inspections.
- **Final STM32N6 pilot outcome:** packages are `BLOCKED` (no target/simulator, model-limited SWE.3+ output); this is
  the correct dark-factory result, with every gap listed in the package.
- **Safety:** no automatic ISO 26262 approval or software release. MISRA Cppcheck checks are partial; real target and formal safety activities require competent offline review and applicable tool assurance.

See [PROJECT_HANDOFF_v0.5.md](PROJECT_HANDOFF_v0.5.md) for implementation order, dependencies, and acceptance criteria. Check [`TEST_RESULTS_v0.5.md`](TEST_RESULTS_v0.5.md) for this archive's verified tests.
