# Implementation Tasks — Forge-C v0.5 KPI Production Control (for Claude Code)

Status: proposed. Do not mark complete without tests and evidence. Complete `002` event schema/M6 before runtime KPI aggregator; shared dictionary/schema can be authored in parallel.

## K0 — Contracts

- [ ] **KPI-T001 [P0]** Validate and freeze `contracts/kpi-catalog.json` (IDs K01–K20, formulas, eligibility, dimensions, quality flags), reviewed examples; **KPI-FR-005, KPI-FR-009**.
- [ ] **KPI-T002 [P0]** Extend 002 typed event schema with versioned KPI source-event payloads and conversion tests; **KPI-FR-001, KPI-FR-003**.
- [ ] **KPI-T003 [P0]** Define work order lifecycle, unique driver order vs attempt, classification policy, clock semantics and append-only first-inspection result; **KPI-FR-001, KPI-FR-004, KPI-FR-007**.
- [ ] **KPI-T004 [P0]** Add versioned `config/factory/kpi-policy.yaml`: windows, inclusion, pilot targets, baseline minimum, data quality and safety non-negotiables; **KPI-FR-006, KPI-FR-008, KPI-FR-017**.

## K1 — Deterministic metrics service

- [ ] **KPI-T005 [P0]** Implement model-free replay-safe aggregation with event idempotency, timestamp ordering, formula hash and test event fixtures; **KPI-FR-002, KPI-FR-003, KPI-FR-015**.
- [ ] **KPI-T006 [P0]** Implement FPY, RTY, READY/BLOCKED throughput, WIP, lead/stage cycle time and rework; test duplicate retries and six-step SWE histories; **KPI-FR-004, KPI-FR-007, KPI-FR-009**.
- [ ] **KPI-T007 [P0]** Implement evidence/requirements/traceability/MISRA/coverage/footprint dimensions from verified tool records; test N/A, unsupported rules, unverified objectives; **KPI-FR-003, KPI-FR-008, KPI-FR-009**.
- [ ] **KPI-T008 [P0]** Implement supervisor availability, incident/repair recovery, recurrence, token/resource consumption and provenance quality; assert zero supervisor model calls; **KPI-FR-002, KPI-FR-013**.
- [ ] **KPI-T009 [P0]** Implement guarded SFOEE A×P×Q, immutable complexity-class reference baseline, invalid/sparse baseline no-value; **KPI-FR-006, KPI-FR-017**.
- [ ] **KPI-T010 [P0]** Implement snapshot schema validation and deterministic checksum-ready serialization, with number/numerator/denominator/sample counts/formula hash; **KPI-FR-003, KPI-FR-009, KPI-FR-015**.

## K2 — Dashboard + MCP

- [ ] **KPI-T011 [P1]** Extend existing dashboard with production overview, SWE station quality, rework Pareto, footprint/coverage, infrastructure and AI-cost tabs. Real data only, N/A clearly visible; **KPI-FR-010, KPI-FR-011**.
- [ ] **KPI-T012 [P0]** Add read-only `forge-observer-mcp.get_kpis` and `get_kpi_evidence`, schema/permission tests; MCP output bounded and never direct SQL arbitrary access; **KPI-FR-012**.
- [ ] **KPI-T013 [P0]** Correlate KPI values to event IDs and immutable evidence hash via existing trace filters, preserving capture/view isolation; **KPI-FR-003, KPI-FR-011**.
- [ ] **KPI-T014 [P1]** Control series cardinality, aggregation latency and report accuracy when live SSE reconnects; **KPI-FR-018**.

## K3 — Release archive

- [ ] **KPI-T015 [P0]** Include versioned catalog/snapshot/baseline and exact status/quality flags in deterministic Release Manager packager for READY and BLOCKED; **KPI-FR-014**.
- [ ] **KPI-T016 [P0]** Cross-check archive metrics against event evidence, package status and no safety approval; **KPI-FR-007, KPI-FR-008, KPI-FR-014**.

## K4 — Adversarial verification and pilot

- [ ] **KPI-T017 [P0]** Replay exactly-once tests (duplicate event IDs, retransmission, order retries, crashes, replay snapshot parity); **KPI-FR-002, KPI-FR-004, KPI-FR-015**.
- [ ] **KPI-T018 [P0]** Test no completed order, N/A baseline, missing inspector, false AI PASS, unit/cpu target mismatch, offline feedback, faults/repairs and metric alert cannot bypass gates; **KPI-FR-006, KPI-FR-008, KPI-FR-009, KPI-FR-016**.
- [ ] **KPI-T019 [P1]** Establish measurement-only calibration dataset split by driver class/target/compilation profile; do not invent SLA or throughput benchmark; **KPI-FR-017**.
- [ ] **KPI-T020 [P0]** Run pilot work order end-to-end, reconcile dashboard/snapshot with raw evidence, document blocked runs and known limitations; **all KPI-FR**.

## Completion evidence

- Unit tests for each metric formula with known synthetic fixtures, no model dependency.
- Dashboard browser smoke tests for filters and trace drilldowns.
- MCP allow/deny and read-only enforcement tests.
- One sealed READY fixture and one BLOCKED fixture, archives containing consistent KPI snapshot and data-quality declarations.
