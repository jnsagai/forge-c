# Feature Specification: Forge-C v0.4 — Self-Healing, Observable Dark Factory

**Feature ID:** 002-self-healing-factory  
**Version:** 0.4.0 — 2026-10-14  
**Status:** PROPOSED / ready for Claude implementation; NOT implemented or validated  
**Baseline:** Forge-C OSS v0.1 demonstration + v0.2 formal SWE inspections + v0.3 offline-release package.  
**Primary actor:** Human engineering supervisor, observing but not interacting with normal factory execution.  
**Implementation agent:** Claude Code through GitHub Spec Kit; production workflow agents use local Qwen via Fabro.

## Outcome

Forge-C develops ultra-low-footprint C HAL and low-level drivers and autonomously generates SWE.1–SWE.6 workproducts, safety-oriented evidence, formal independent-agent inspections, deterministic verification, and a complete offline handover package. It must self-monitor, recover from infrastructure faults within defined policy, learn only from *validated* repairs, and expose selectable, privacy-controlled trace channels. No AI agent, supervisor, or automatic recovery action may claim ISO 26262 ASIL B approval or weaken safety verification gates.

## Clarifications

### Session 2026-10-14

- Q: Which syntax must SWE.1 software requirements use, and how is it inspected? → A: Every SWE.1 software requirement statement MUST use **EARS** (Easy Approach to Requirements Syntax: ubiquitous, state-driven `While`, event-driven `When`, optional-feature `Where`, unwanted-behaviour `If … then`, or complex combinations), with exactly one `shall` and the specified system named. The SWE.1 inspection checklist v0.4 overlay adds mandatory item **SWE1-07**, decided by the deterministic EARS checker (`forge_factory.inspection.ears`, exposed via `forge-docs-mcp.validate_artifact`); a non-conformant requirement is a major finding that loops back to `swe1-author`. The baselined v0.3 checklist is extended, not modified. (Applies to FR-002, FR-003.)
- Q: How is generated driver code shown to follow the supplied driver development guideline? → A: SWE.3 has a mandatory **deterministic verification node** (`gate --step verify --check hal_guideline`) between author and inspector, plus v0.4 checklist item **SWE3-07**. It checks the automatable rule subset of the guideline (`config/factory/guidelines/st-cube2-hal-v1.2.yaml`, pinned to the guideline SHA-256): file layout, header guards, naming/prefixes, lower-case `_t` types, const config pointers, no device-RPN conditionals, timeout-bounded loops, local arrays ≤128 bytes, no register-access HAL macros. Any violation loops back to `swe3-author`; judgement-based guideline content remains a manual inspection item. (Applies to FR-003, FR-038.)

## Clarified boundaries and invariants

1. **Dark operation:** no LLM-driven action during a healthy supervisory poll; no interactive human gates from intake to packaged result; human oversight via read-only dashboard and after-run offline review.
2. **Skills for every AI role:** one versioned Open Agent Skills `SKILL.md` for each declared role, including every SWE author and inspector, Release Manager, Repair Agent, Knowledge Curator and dedicated engineering roles. Runtime registration fails closed on a missing/invalid skill or permissions manifest. Non-AI daemon services are not agents and do not need LLM skills.
3. **MCP for every engineering tool exposed to AI:** all production AI-accessible engineering operations flow through a discoverable, versioned MCP tool. Reuse upstream MCP where suitable; otherwise create a thin open-source adapter. Fabro internal execution, external monitoring and deterministic system services may use native APIs; no claim that each executable must host a separate MCP daemon. Disallow unrestricted shell MCP in production policy.
4. **Independent deterministic supervisor:** separate OS-managed service outside the Fabro process; it does not instantiate, prompt, or call any model during normal health polling. A detected fault generates an incident and dispatches an isolated Repair Agent only when policy allows. Watchdog/backoff protect against infinite repair.
5. **Validation before reuse:** recovery patches are applied to an isolated factory branch/worktree, pass deterministic regression and policy-integrity tests, then are atomically promoted or rolled back. No unreviewed edits to safety gates, release policy, tool assurance or existing delivered evidence.
6. **Lessons are not instructions by default:** sanitized, evidence-linked, versioned lessons only become retrievable across workflows after deterministic validation and explicit machine-policy acceptance. Unvalidated suggestions are quarantined. The lesson store cannot modify safety-critical policies automatically.
7. **Dual logging control:** capture policy determines what may be recorded, dashboard filter determines what a human sees. User display settings never increase collection/retention; mandatory audit records cannot be disabled. Private model reasoning/chains-of-thought are never extracted or persisted.
8. **Evidence over narration:** AI agents return compact machine-readable status and issues, no gratuitous rationale, no full raw tool logs in model context, artifact references instead of pasted files. Token spending is metered, budgeted and visible.
9. **Offline handover:** a final Release Manager collects code, SWE + support + safety workproducts, tests, inspection findings, run/health/repair/knowledge audit, tool and skill manifests, model usage, gaps and hashes. Always package `READY_FOR_OFFLINE_REVIEW` or `BLOCKED` where storage permits. No AI release approval.
10. **Open-source-first:** Fabro, local LLM inference, SQLite/PostgreSQL, FastAPI/SSE, MCP SDK, Prometheus/OpenTelemetry-compatible outputs, C toolchains and analyzers. No paid SaaS or proprietary analyzer is mandatory; MISRA standard access remains an organizational requirement.

## User stories and acceptance scenarios

### US-01 — Skill-governed agents (P0)
As the factory owner, I want every AI role bound to exactly one discoverable primary SKILL, so responsibilities, permissions and output format can be audited.

- **Given** an agent manifest missing its referenced `SKILL.md`, **when** a workflow starts, **then** the preflight fails before any agent call and emits `AGENT_SKILL_MISSING`.
- **Given** a SWE.3 author and SWE.3 inspector, **when** they operate, **then** role identities, contexts, SKILL hashes, tool grants and inspection evidence are distinct.
- **Given** an agent request for an undeclared tool, **then** the MCP policy denies it and writes a security/audit event.

### US-02 — All engineering tools behind MCP (P0)
As the owner, I want consistent MCP contracts for compilers, analyzers, testers, simulators, traceability and packaging.

- Preflight enumerates all tools required by enabled workflows, resolves each to a healthy MCP server and validates its `tools/list` signatures, or rejects startup with precise missing capability and alternative/degraded disposition.
- A nonexistent adapter is implemented as an isolated OSS MCP wrapper with strict argument validation, workspace path restrictions, subprocess argv allowlists, bounded time/memory and machine-readable artifact handles; no arbitrary shell passthrough.
- Unit and integration tests verify MCP handshake, allowed calls, denied calls, failure codes and output provenance, using mock executable fixtures where tools are not installed.

### US-03 — Model-free periodic health supervision (P0)
As the owner, I want automatic health verification even when Fabro is stalled or down.

- A service independently polls Fabro readiness/liveness, run progress heartbeat, agent/stage timeout, queue age, failed MCP tools, evidence store writability, memory/disk/CPU/GPU pressure (when observable) and dashboard service health.
- Default poll interval is 60 s (configurable 15–300 s). Incident de-duplication prevents more than one active repair of the same root-cause fingerprint.
- **Given** 100 healthy polling cycles, **then** model request count and token usage from supervisor equal exactly zero; health events still exist.
- **Given** Fabro exits and fails an independently observed health check, **then** the supervisor records an incident without needing any Fabro API to remain alive.

### US-04 — Autonomous repair without safety-policy bypass (P0)
As the owner, I want an autonomous AI maintainer to fix genuine fabric failures and preserve evidence of the intervention.

- A permitted incident triggers an MCP/Fabro repair child run or independently launchable local repair worker; choose the path that survives loss of Fabro availability. Recovery launch has no circular dependency on the failed process.
- Repair Agent has a dedicated SKILL and a minimal incident bundle; it may change allowed factory infrastructure paths only in isolated worktrees, and cannot change protected safety rules, safety attestations, baselined driver evidence or existing release archives.
- Deterministic tests, service probes, tool contract tests and unchanged-protected-files checks decide whether repair is promoted. On failure, rollback atomically, preserve incident status and forensic records.
- Configurable bounded attempts (default max 2 per incident, max 3 per hour), cooldown, backoff, circuit breaker and resource/token budget; exhausting retries marks incident `REQUIRES_OFFLINE_ATTENTION` without halting packaging of available work.
- A hard failure of the supervisor process is observable through OS service manager watchdog / independent heartbeat mechanism.

### US-05 — Validated shared lessons learned (P0)
As the owner, I want a repair to improve future runs without spreading unverifiable advice.

- Every attempted repair creates an evidence-linked record including incident fingerprint, root cause, patch hash, tests, outcome and affected tool versions; failed attempts remain searchable only as incidents, not approved prescriptions.
- Validated successful repairs produce candidate lessons; knowledge validation rejects secrets, ungrounded prescriptions, duplicate/noisy content and instructions to disable quality gates.
- Other workflows retrieve at most K relevant approved lessons (default K=3) by tool/phase/error signature; the lookup payload is bounded by tokens and includes source/provenance and confidence/expiry.
- A lesson invalidated by regression is retracted automatically and related runs are flagged for impact analysis. Cross-workflow knowledge cannot supersede authoritative HSI, requirements, safety plans or tool documentation.

### US-06 — Supervisory dashboard (P0)
As the owner, I need a single read-mostly interface for dark-factory health and run monitoring.

- Web UI shows factory health, run list and stages, active agents, phase inspection/rework counts, blocked findings, available MCP servers, outstanding repair incidents, release package status, token usage by agent, and CPU/GPU/VRAM/disk metrics when available.
- Default UI displays concise human trace events; user can toggle trace channels (`human`, `workflow`, `tools`, `ai`, `supervisor`, `repair`, `security`, `audit`, `metrics`, `knowledge`), severity, run/phase/agent/correlation, date/time and search.
- Filtering affects display only; never deletes stored events, changes their capture policy, or suppresses mandatory audit evidence.
- The UI is usable at phone and desktop widths, with SSE live updates and a polling fallback; read-only role by default. Human maintenance actions (pause/retry) are an explicitly separate authenticated admin mode and are never required for normal factory execution.

### US-07 — Configurable structured trace capture (P0)
As the owner, I need independently configurable per-channel logging, with meaningful event correlation and safe data handling.

- Each event includes schema version, event ID, UTC timestamp, run/workflow/stage/agent/tool/incident IDs where relevant, category, severity, concise message, payload reference, trace/span IDs, and redaction state.
- Channel levels are `OFF`, `ERROR`, `WARN`, `INFO`, `DEBUG`, `TRACE`. `audit` retains at least INFO for required security/fault/promotion events; `security` never OFF for critical events.
- Tool events record command/adapter, sanitized parameters, status, latency and artifact pointer. AI events record model name, tokens, tool-call IDs, output status and optional redacted prompt/response excerpts under explicit capture policy. **Never request or save hidden chain-of-thought.**
- Raw evidence logs can be stored outside model context and referenced via hashes; every operator-readable event is human-understandable in <=160 characters at INFO level.
- Sensitive strings, credentials, code secrets and private data are scrubbed before persistence; access is authenticated; configurable retention applies per channel with audit minimum retention.

### US-08 — Token-efficient agent contracts (P0)
As the owner, I want the dark factory to prioritize engineering output and minimize unnecessary model consumption.

- Every SKILL requires final response in compact JSON: `status`, `artifacts`, `issues`, `next_action`; brief issue descriptions and no general commentary. Full rationale belongs in required ASPICE workproducts, not model conversation/log chatter.
- Agent tools return summaries and artifact paths by default; raw logs are retrieved only on demand, with line/range limits. Workflow agents use frozen snapshots and diffs, not repeated full-context replays.
- Per-stage caps for model tokens, turns, retries, tool-call output bytes and retrieved lesson count; budgets configurable in `config/factory/token-policy.yaml` with measured counters.
- On budget exhaustion, report `TOKEN_BUDGET_EXHAUSTED`, preserve evidence and take controlled rework/BLOCKED path. The supervisor never spends tokens during healthy monitoring.
- Record baseline `tokens / accepted driver`, `tokens / passed phase`, retry count and tool-call payload sizes; optimize without skipping required inspections/evidence.

### US-09 — Complete offline handover (P0)
As the offline reviewer, I need a single reproducible archive including operational evidence.

- Preserve existing v0.3 release policy semantics and add versioned operational inventory: agent SKILL manifest/hashes, MCP catalog/tool versions, event schema/capture-policy snapshot, supervisor incident/repair/lesson ledger, run budgets/usage and dashboard export/review index.
- Approved safety workproducts, 6 inspections, QA findings, raw static/MISRA/coverage/footprint results and traceability remain the release requirements. Missing newly required operational evidence yields `BLOCKED` with gap entries; no synthetic placeholders.
- Release Manager (agent) only inventories/writes handover narration; deterministic packager signs/hashes indexes and assembles both successful/blocked packages. Human reviews entirely offline.

### US-10 — Fault-tolerant, resumable execution (P1)
As the owner, I need workflows to resume safely after recoverable infrastructure failures, without corrupting a baseline.

- Checkpoint confirmed source and evidence revision IDs; on recovery, resume from safe idempotent stage boundary; re-run an inspector if a dependency hash changed.
- Never automatically replay non-idempotent operations such as target flashing, approval, baseline sign-off or release artifact mutation.
- Repair of Fabro is logically separate from rework of generated product; defect in driver goes to SWE author loop, infrastructure incident to Repair Agent.

## Functional requirement index

| ID | Normative requirement | Priority |
|---|---|---|
| FR-001 | Every declared AI role MUST have a versioned, discoverable SKILL.md. | P0 |
| FR-002 | Skills MUST specify input, output, tool grants, evidence, concise output and exclusions. | P0 |
| FR-003 | Author and reviewer sessions MUST be different and review baselined revisions. | P0 |
| FR-004 | Every AI-callable engineering operation MUST have an MCP tool contract. | P0 |
| FR-005 | MCP preflight MUST fail closed on unavailable mandatory tooling. | P0 |
| FR-006 | MCP wrappers MUST enforce read/write scope, no arbitrary shell, timeout and provenance. | P0 |
| FR-007 | A separate model-free supervisor MUST poll at configurable interval. | P0 |
| FR-008 | Supervisor healthy polling MUST make zero model calls. | P0 |
| FR-009 | Supervisor MUST detect Fabro-down, stage-stall and tool/backend failures. | P0 |
| FR-010 | Incidents MUST be durable, deduplicated and traceable. | P0 |
| FR-011 | Eligible incidents MUST dispatch autonomous Repair Agent. | P0 |
| FR-012 | Repair Agent MUST work in isolated, restricted filesystem/worktree. | P0 |
| FR-013 | Protected safety/QA gates and delivered evidence MUST be immutable to repair. | P0 |
| FR-014 | Repair must pass deterministic regression and be atomically promoted or rolled back. | P0 |
| FR-015 | Repair loops MUST be bounded with cooldown and circuit breaker. | P0 |
| FR-016 | Failed repairs MUST be visible and included in offline handover. | P0 |
| FR-017 | Successful repairs MUST propose versioned, evidence-linked lessons. | P0 |
| FR-018 | Only validated, sanitized lessons MAY enter shared retrieval. | P0 |
| FR-019 | Retrieval MUST enforce relevancy, trust, token bounds and provenance. | P0 |
| FR-020 | Dashboard MUST show runs, phases, agents, MCP, health, incidents, release and tokens. | P0 |
| FR-021 | Dashboard MUST filter user-selected channels and severities per view. | P0 |
| FR-022 | Trace capture and visibility controls MUST remain distinct. | P0 |
| FR-023 | Log levels MUST be independently configurable per channel. | P0 |
| FR-024 | Mandatory audit/security evidence MUST never be disabled by user filters. | P0 |
| FR-025 | AI trace storage MUST exclude hidden reasoning and scrub secrets. | P0 |
| FR-026 | Event envelopes MUST be typed, versioned, correlated and timestamped. | P0 |
| FR-027 | Agents MUST emit compact structured status/issue outputs. | P0 |
| FR-028 | Raw logs MUST be referenced, not routinely inserted into LLM context. | P0 |
| FR-029 | Agent token, turn, retry and context budgets MUST be configured and enforced. | P0 |
| FR-030 | Budget exhaustion MUST generate an explicit non-success outcome. | P0 |
| FR-031 | Release Manager MUST package available operational and SWE/safety evidence. | P0 |
| FR-032 | Machine packaging MUST preserve `READY_FOR_OFFLINE_REVIEW`/`BLOCKED` semantics. | P0 |
| FR-033 | No model or daemon MAY self-approve ISO 26262/ASPICE compliance or production use. | P0 |
| FR-034 | Supervisory recovery MUST NOT depend solely on a healthy Fabro process. | P0 |
| FR-035 | Shared lessons MUST be retractable with impact traceability. | P1 |
| FR-036 | Workflows SHOULD resume from verified idempotent checkpoints. | P1 |
| FR-037 | Dashboard SHOULD provide SSE with polling fallback. | P1 |
| FR-038 | Infrastructure and engineering defects MUST follow separate incident routes. | P0 |
| FR-039 | OSS licenses of shipped adapters/dependencies MUST be checked and recorded. | P0 |
| FR-040 | Optional tools with no MCP MUST be disabled rather than silently accessed directly. | P0 |

## Non-functional acceptance targets (pilot values, configurable)

| SLO / constraint | Proposed acceptance target |
|---|---|
| Supervisor poll | 60 seconds default; 15–300 s valid configuration |
| Healthy supervisor model calls | Exactly 0 per 100 polls |
| Fabro-down incident detection | <= 2 configured poll cycles after readiness failure |
| Duplicate active repair incidents | 0 per root-cause fingerprint |
| Repair | Max 2 automated attempts per incident, max 3/hour factory-wide |
| Repair regression | 100% prescribed checks pass before promotion; protected-file diff = empty |
| Dashboard update | New persisted event visible within 5 s when online |
| Trace filtering | Selected channels/severities match query correctly, no loss of audit records |
| Token reporting | Exact integer input/output/total counters when provider reports them; `unknown` otherwise |
| Artifact integrity | 100% of archive inventory paths and SHA-256 checked |
| AI final status | JSON parseable, at most 4 top-level fields, issues concise |
| Secure defaults | AI raw content capture OFF, viewer read-only, MCP least privilege |

## Dependencies, risks and explicit gaps

- Fabro's documented MCP support and Agent Skills are **existing upstream capabilities**; factory adapters, supervisor and dashboard are **not yet implemented**.
- Prototype wrapper signatures are implementation contracts, not claims that the underlying executable offers an official MCP server. Versions, CLI flags, license constraints and required OS support are verified and pinned during implementation.
- Device-specific RCC semantics require authoritative STM32N6 reference manual/errata, applicable HSI and safety requirements. Generic RCC host tests are not hardware verification.
- MISRA C checking via Cppcheck is partial; `MISRA_COMPLIANT` MUST never be inferred from scanner success. Publication of ISO 26262 and MISRA remains proprietary; no proprietary tools are necessary to execute the open-source factory.
- Asynchronous self-healing can create self-reinforcing faults. Circuit breaker, rollback, immutable release archives and tamper-evident audit events are mandatory before unattended deployment.
- The health supervisor is distinct from a model-based LLM judge. A model may be invoked only in the incident repair workflow.

## Traceability and definition of done

- Each FR maps to at least one task in `tasks.md` and one deterministic acceptance test or documented safety/offline gap.
- All enabled agents appear in both `config/factory/agents.yaml` and `.fabro/skills/<role>/SKILL.md`.
- All mandatory tools appear in `config/factory/mcp-registry.yaml` and are resolved through a working adapter or a validated upstream MCP server.
- `python3 tests/spec/validate_design.py` passes, then integration tests execute on Ubuntu with pinned toolchain, fake failure injections, and offline mode.
- Complete unattended RCC pilot ends in a verifiable review archive; ASIL B approval remains external.
