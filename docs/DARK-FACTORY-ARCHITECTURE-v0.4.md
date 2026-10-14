# Forge-C v0.4 architecture decisions (implementation reference)

The [editable draw.io file](../architecture/Forge-C_Fabro_DarkFactory_v0.4.drawio) contains the canonical diagrams. Its eleven tabs include seven inherited v0.3 pages (with a redesigned v0.4 overview) and four new detailed pages for external supervision, role Skills/MCP, observability, and cross-run knowledge.

## Execution lanes

**Product plane:** Approved immutable input baseline → Fabro → SWE.1–SWE.6 author + separate inspector sessions and checklist gates → deterministic C verification and footprint gates → Release Manager → deterministic review package. Any issue loops to responsible author and reinspection; upstream causes invalidate dependent baselines. Exhaustion returns a BLOCKED package. The human reviews offline.

**Tool plane:** All production AI-accessible operations require discoverable MCP capabilities with allowlisted arguments, provenance, scoped filesystem permissions, bounded output and role-grant enforcement. Fabro may still supply native tools; privilege enforcement must be outside the model and include native-tool sandbox restrictions. Do not claim adapters already exist.

**Control plane:** Independent periodic deterministic OS supervisor → health probes → durable incident and eligibility → scoped AI Repair Agent dispatched through independent fallback if Fabro is down → isolated candidate patch → deterministic tests + atomic promotion/rollback → lesson candidate. The model-free supervisor itself never submits prompts, even during faults; only the dispatcher can authorize an AI worker after an eligible incident. Protected safety and release evidence are immutable to the repair worker.

**Knowledge plane:** Verified repairs become sanitized, provenance-linked lesson candidates. Validator must prove referenced regression evidence and deny bypass advice; approved lessons are versioned, retracted on invalidating regressions, and available as top-K limited retrieval to later workflows, never as higher-priority instructions.

**Observability plane:** Typed event sources → normalization/redaction → configurable per-channel capture policy → hashed event store → authenticated read-only dashboard with per-view channels, severity, search and time filters. AI metadata includes model ID, token counts, tool calls, outcome and sanitized optional excerpts; **never hidden chain-of-thought**. Capture policy and display filters are orthogonal; audit is non-disableable.

**Optimization plane:** Per-role token and turn budgets, small JSON status payloads and artifact references; avoid rationale in logs but include complete rationale required in detailed ASPICE workproducts. Compiler outputs stay in evidence, not prompt context. No degradation of coverage/analysis/inspection requirements for token savings.

## Intentional release semantics

The Release Manager is an AI collector; the hash-based packager is a deterministic service. Package status can be `READY_FOR_OFFLINE_REVIEW` or `BLOCKED` only; neither is safety approval or production-release authorization. No internet connection or commercial runtime tool is required by the design. Full MISRA coverage and qualification still require separate safety assurance arrangements.
