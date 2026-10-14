# Feature Specification 003 — Manufacturing-Inspired KPIs for Forge-C

**Version:** 0.5.0 · **Status:** PROPOSED / ready for Claude Code; NOT implemented · **Date:** 2026-10-14
**Baseline dependency:** `002-self-healing-factory` events and dashboard, especially M3 supervisor, M6 telemetry and M7 offline packager.
**Product:** Open-source Forge-C factory for low-footprint C HAL/LLD; Automotive SPICE SWE.1–SWE.6 and safety evidence targeting ISO 26262 ASIL B.

## Outcome and invariant

Deterministically compute manufacturing-inspired software-factory KPIs from trustworthy run events, independently verified engineering outcomes, tool results and frozen package metadata. Present them in a read-only production-control dashboard with drilldown by work order, SWE phase, MCU, driver complexity, model, toolchain, version, and review status; include metric provenance in offline package.

**Never score safety as a tradeable productivity dimension.** A missing safety requirement, unsupported MISRA rule, failing gate or invalid evidence cannot be offset by high throughput, smaller Flash, fewer tokens or a high OEE score. `READY_FOR_OFFLINE_REVIEW` is not `ASIL_B_APPROVED`.

## Production semantics

- **Work order (unit started):** one immutable, uniquely identified driver-development request, including source revision, target MCU, configuration, safety scope and acceptance criteria. Attempts/restarts link to the same order; retries are not new production units.
- **Station:** SWE.1, SWE.2, SWE.3, SWE.4, SWE.5, SWE.6; independent AI inspection is the station's quality check. Optimization and Release Manager are downstream manufacturing operations, not substitutes for inspections.
- **First-pass success:** station's *initial* independent inspection passes against a frozen revision, before corrective work. Reinspection cannot rewrite first-pass outcome. Quality gate results are authoritative deterministic records, not AI assertions.
- **Finished good:** immutable complete offline review package with state `READY_FOR_OFFLINE_REVIEW`. `BLOCKED` packages are mandatory tracked output/evidence, but do not count as successful production yield. Offline human approval is a separate event and must never be synthesized.
- **Production time:** explicit planned windows + admitted work; distinguish active, waiting, intentional idle, infrastructure downtime, AI/model wait, review/rework, unknown telemetry. Never interpret idle/no work as an outage.
- **Comparability:** performance baselines are keyed by driver class/complexity, MCU, compiler optimization, tool configuration and safety profile; uncalibrated categories show `INSUFFICIENT_BASELINE`, never an invented ideal time.

## Manufacturing KPIs — canonical definitions

The metric catalog in `contracts/kpi-catalog.json` is normative, together with formulas and source-event definitions below. Every displayed percentage includes numerator, denominator, window and data status.

| ID | Name | Formula or operation | Scope / guardrail |
|---|---|---|---|
| K01 | Factory availability | healthy planned production seconds / eligible planned production seconds | Idle excluded; downtime reason breakdown available; `N/A` if denominator zero. |
| K02 | Station First Pass Yield (FPY) | initial station inspection PASS / initial station inspections with terminal verdict | Separate SWE.1–SWE.6; no cherry-picking reruns. |
| K03 | Rolled Throughput Yield (RTY) | closed work orders that passed ALL six initial SWE inspections and applicable gates on first try / all closed work orders | Calculate from unique order history, not multiplication of station percentages; blocked orders fail. |
| K04 | Factory review-ready throughput | sealed `READY_FOR_OFFLINE_REVIEW` unique packages / time window | Always display BLOCKED packages separately. |
| K05 | End-to-end lead time | p50/p95 of sealed time minus admission time | Show READY and BLOCKED distributions separately; includes waiting/rework. |
| K06 | Stage cycle time | p50/p95 active station execution duration by SWE stage | Exclude queue idle, show rework time separately. |
| K07 | Rework effort share | active correction + reinspection seconds / all SWE productive active seconds | Infrastructure repair excluded; include correction loops and escalations. |
| K08 | Defect leakage | confirmed findings first detected downstream of their adjudicated origin phase / all confirmed findings with assigned origin | Unknown origin is explicit, not counted as zero; include offline feedback if available. |
| K09 | Applicable evidence completeness | validated evidence slots present / required applicable evidence slots | Policy/revision-specific; a file existing is not evidence of content validity. |
| K10 | Requirements verification | requirements verified with valid results / applicable requirements | Unverified, not-applicable and invalid separate; source verification tools. |
| K11 | Traceability consistency | semantically validated required links / total required links | Mere link existence is insufficient; include consistency verdict. |
| K12 | MISRA assessment coverage | assessed applicable MISRA rules / applicable MISRA rules | Report unsupported/unchecked rules separately, plus unresolved findings and deviations; never imply full compliance. |
| K13 | Verification coverage | statement, branch, and if configured MC/DC covered/total, each separately | Instrumentation, host/target provenance and exclusions required; no blanket 100% threshold. |
| K14 | Memory and timing envelope | flash, static RAM, stack, cycles/WCET measurement vs pinned approved budgets | Show absolute units + headroom and estimation method; safety constraints are hard gates. |
| K15 | Inference efficiency | tokens over ALL production attempts / READY packages, plus per-stage tokens | `N/A` if zero READY; estimated/unknown usage labeled; not weighted by verbosity. |
| K16 | Autonomous repair effectiveness | automatically health-restored terminal eligible incidents / terminal eligible incidents | Retry storms count as one deduplicated incident; also plot p50/p95 restore time. |
| K17 | Recurrence ratio | resolved root-cause fingerprints recurring within policy window / resolved fingerprints with full observation window | Do not claim lesson prevented faults without supported comparisons. |
| K18 | WIP | count of admitted, not terminal unique work orders at observation time | Show age and blocked/queued distributions, not incentivized as large. |
| K19 | Software Factory OEE (SFOEE) | availability × normalized performance × first-pass package quality | Experimental operations metric; publish factors, sample sizes and baseline version; suppress if any factor invalid. |
| K20 | Safety/process protection | count of skipped mandatory inspections, bypassed gates, or invalid approval assertions | **Zero tolerated; hard violation, not a weighted score.** |

### SFOEE normalization

- **A:** K01 availability (0–1).
- **P:** `min(1, Σ(class_frozen_reference_cycle_seconds for completed attempts) / Σ(observed_eligible_active_cycle_seconds))`, calculated only within properly matched class and with a frozen calibrated reference dataset. Reference times must be independently versioned; use a robustness policy against gaming through easy-order selection.
- **Q:** first-pass **package** quality = number of closed work orders passing all applicable SWE inspections/quality gates first time and reaching READY / number of closed orders. Contrast with K03 to ensure equivalent definitions; do not count BLOCKED packages as good.
- **SFOEE = A × P × Q**; report underlying factors and data sufficiency. If no eligible scheduled activity, no reference baseline, incomplete audit log, or missing denominator, set `value: null` and `status: NOT_COMPUTABLE`. SFOEE is diagnostic, not release acceptance.

## User stories

**US-K01 Production control (P0):** Factory owner sees throughput, WIP, A/P/Q, SFOEE when computable, p50/p95 lead/cycle time, rework Pareto and bottleneck per SWE station. Filters for time period and production class update numerator and denominator consistently. `SFOEE` initially N/A until baseline exists.

**US-K02 Station quality (P0):** Each SWE inspection emits signed/hashed machine-readable inspection outcome and findings. The dashboard shows first-pass yield by phase, reinspection cycles, defect origin phase, severity and downstream escape. Rework improves candidate quality but never changes the initial FPY observation.

**US-K03 Compliance and optimized firmware (P0):** Dashboard shows evidence completeness, traceability consistency, unresolved MISRA violations, uncovered rule families, verification objectives, Flash/RAM/stack and timing budget margins by target/compiler/baseline. Any unknown/budget violation is visible even if packages pass other scores.

**US-K04 Token and compute efficiency (P0):** Models, tools and agents are measured using actual usage counters, not conversational self-report. Source provider unavailable -> `ESTIMATED` with method or `UNKNOWN`, never zero. Show costs in token, GPU-seconds, CPU-seconds, and optional energy estimates; do not label simulated estimates as actual electrical usage.

**US-K05 Reliable self-healing (P0):** Supervisor health metrics, incident counts, MTTR and recurrence are computed without model calls. Auto-repair does not change KPI formulas, safety thresholds or retroactively modify past evidence. Retractions preserve prior lesson impact history.

**US-K06 KPI dashboard and trace linkage (P0):** KPI tiles and time-series charts drill down to typed trace events and immutable artifacts with correlation IDs. User-selectable view filters do not alter capture. KPI events have distinct provenance from AI-generated summaries. Time-window rates remain stable across replay and restart.

**US-K07 Offline handover (P0):** Release Manager packages `kpi-snapshot.json`, `kpi-catalog.json`, period and run denominators, quality/footprint references, series exports and KPI engine formula/configuration hashes. KPIs never fabricate safety approval; blocked outcomes still contain available valid metrics and missing-data explanations.

## Functional requirements

| ID | Requirement | Priority |
|---|---|---|
| KPI-FR-001 | Production work orders MUST have immutable unique IDs, type/safety/target metadata, and lifecycle events with consistent timestamps. | P0 |
| KPI-FR-002 | Metric aggregation MUST be deterministic, idempotent under event replay and model-free. | P0 |
| KPI-FR-003 | All metric records MUST link to original tool/inspection/package evidence and formula-version hash. | P0 |
| KPI-FR-004 | Initial inspection outcomes MUST be append-only and remain unchanged by rework or reinspection. | P0 |
| KPI-FR-005 | K01–K20 MUST be in a typed, versioned, machine-readable catalog with calculation/eligibility/unit/source. | P0 |
| KPI-FR-006 | OEE-like metrics MUST report A/P/Q separately and show N/A for insufficient comparable baselines. | P0 |
| KPI-FR-007 | Throughput MUST count only unique sealed READY packages, and show BLOCKED separately. | P0 |
| KPI-FR-008 | Safety/process constraints MUST remain hard gates, never compensable by economic or production metrics. | P0 |
| KPI-FR-009 | KPI computations MUST provide explicit UNKNOWN, NOT_APPLICABLE and NOT_COMPUTABLE instead of false pass or zero. | P0 |
| KPI-FR-010 | Dashboard MUST support run/phase, MCU, driver class, model, tool version, baseline, status and time filters with synchronized denominators. | P1 |
| KPI-FR-011 | Dashboard MUST preserve capture/view trace isolation and show source event/artifact drilldown. | P0 |
| KPI-FR-012 | KPI engine MUST expose read-only API, with model-access via observer MCP only when explicitly authorized. | P0 |
| KPI-FR-013 | Resource and token measurements MUST identify measured, estimated and unknown provenance. | P0 |
| KPI-FR-014 | Release archives MUST include metric definitions, snapshots, raw references, baselines, calculation versions and deficits. | P0 |
| KPI-FR-015 | Full replays and incremental updates MUST produce the same metric record for the same event set and policy. | P0 |
| KPI-FR-016 | KPI anomaly alerts MAY recommend investigation but MUST NOT weaken inspection/validation policy or invoke repair unless a genuine infrastructure incident is detected. | P0 |
| KPI-FR-017 | Metric quality/control limits MUST be configurable per class with an initial measurement-only baseline period. | P1 |
| KPI-FR-018 | Data stores MUST limit cardinality in Prometheus-like backends and keep high-cardinality join keys in event store. | P1 |

## Guardrails and operational acceptance

1. Pilot with **measurement-only KPIs**. Calibrate performance references after sufficient homogeneous samples; 20 comparable runs is a provisional sampling objective, *not* a statistically universal threshold. If insufficient, show N/A.
2. Start with K01–K07, K09, K14–K16, K20 on front page; drill down to traceability, MISRA and detailed coverage. Do not optimize towards a synthetic all-in-one quality number.
3. p50 and p95 are empirical quantiles with sample count; low sample sizes show a caution tag and no SLO claim.
4. Never compare compile/review efficiency of different MCU families, HAL complexity or target optimizations as if identical.
5. Safety gate results may influence READY/BLOCKED categorization, but production KPI alerts cannot silently change hard quality/safety thresholds.
6. Production agents SHOULD NOT be prompted to calculate KPI values. They emit limited structured events; the deterministic metrics service calculates values.
7. The addendum is a **specification for Claude to implement**, not an assertion of completed runtime functionality.

## Conceptual references (adapted, not normative for ASPICE/ASIL)

- Manufacturing OEE decomposition: https://www.oee.com/calculating-oee/ — availability, performance and first-pass quality.
- DORA software-delivery throughput/instability metrics (not directly equivalent to offline review packages): https://dora.dev/insights/dora-metrics-history/
- Google SRE monitoring golden signals — latency, traffic, errors, saturation: https://sre.google/sre-book/monitoring-distributed-systems/
- Automotive SPICE process activities are scoped to the project's approved PAM baseline; process evidence requirements take priority over aggregate KPI scores.
