# ADR-CRE-006: Operations eligible for autonomous recovery vs forbidden production mutation

Status: accepted (2026-10-16) · Tasks: CRE-T004, CRE-T011..T015, CRE-T027, CRE-T028

Two separate loops (spec §2, plan §2):

1. **Runtime recovery** (bounded): retries of idempotent operations for TRANSIENT_DEPENDENCY faults; 002 repair of
   *runtime configuration* in the infra repo (existing promotion with CAS + rollback); reversible operational
   actions from the catalogue (`restart_dashboard`, `restart_mcp_server`, `restart_llm_gateway`, `drain_queue`,
   `restart_collector`) — only in `ACTIVE` mode with an authorization block. Every path ends `RECOVERED` or
   `REQUIRES_OFFLINE_ATTENTION` within the policy budgets.
2. **Factory evolution** (evidence-gated, never autonomous): factory source changes, prompts, checklists, policies,
   tests and benchmarks are evaluated by the CRE promotion runner and at best marked
   `ELIGIBLE_FOR_OFFLINE_REVIEW`; the owner's change control promotes them.

Forbidden for any automatic path, in every mode: persistent factory code promotion, changes to safety/release/trace/
supervisor/reliability policies, quality-gate thresholds, approved baselines, released archives, evidence, test
oracles and holdout fixtures, hardware flashing and approvals. `PRODUCT_QUALITY` failures are routed to SWE rework,
never to infrastructure repair. The initial mode is `OBSERVE_ONLY`: CRE records, classifies, measures and proposes;
it does not act.
