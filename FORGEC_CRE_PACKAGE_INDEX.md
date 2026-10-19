# Forge-C CRE 004 — Package Index

**Contents:** implementation specifications, plan, task backlog and schema/config examples for Claude Code. **No runtime CRE code is included or claimed as implemented.**

## Installation

From a copy of this extracted package, copy the `specs/004-continuous-reliability-engineering/` directory into the existing Forge-C repository. Place `CLAUDE_CRE_START.md` and optionally `FORGEC_CRE_IMPLEMENTATION_PLAN.md` in the repository root, taking care not to overwrite anything existing. Create a new feature branch before edits. Paste the execution block from `CLAUDE_CRE_START.md` into Claude Code.

## File map

- `FORGEC_CRE_IMPLEMENTATION_PLAN.md` — readable executive implementation plan and milestone table.
- `CLAUDE_CRE_START.md` — explicit Claude execution prompt, rules and actual source-audit obligations.
- `specs/004-continuous-reliability-engineering/spec.md` — 40 requirements.
- `specs/004-continuous-reliability-engineering/plan.md` — MAPE-K/CAPA/SPC architecture and technical design.
- `specs/004-continuous-reliability-engineering/tasks.md` — 42 ordered tasks.
- `specs/004-continuous-reliability-engineering/acceptance-tests.md` — 39 normative acceptance/fault-injection tests.
- `specs/004-continuous-reliability-engineering/planned-traceability.csv` — requirements→tasks→tests crosswalk; all statuses PLANNED.
- `specs/004-continuous-reliability-engineering/contracts/*.schema.json` — starter record contracts for CAPA, benchmarking, promotion and reliability statistics.
- `specs/004-continuous-reliability-engineering/contracts/*.example.yaml` — **examples only**, requiring reconciliation with the actual v0.5 implementation and pinned environment.
- `FORGEC_CRE_SHA256SUMS.txt` — SHA256 checksums of source delivery files.

## Source/project compatibility

- v0.5 **already specifies** a deterministic supervisor, Repair Agent, lesson store, customizable traces, dashboards, K01–K20 and offline release; implementing 004 cannot duplicate these as a greenfield system.
- As of the available v0.5 handoff, several platform components were only specified, not runtime deployed. Implementation status must be audited from the actual user's repository.
- ASPICE/ASIL claims require human process/safety review. Spec Kit convergence is **not** a production reliability proof.
