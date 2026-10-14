# Implementation Plan — Forge-C v0.4 Self-Healing Dark Factory

**Spec Kit feature:** `002-self-healing-factory`  
**Implementation owner:** Claude Code  
**Execution posture:** open-source, local-first, unattended; offline reviewer remains external.  
**Plan status:** concrete implementation design; interfaces marked *proposed* until tested against installed Fabro.

## 0. Baseline and exact starting point

This package contains the Forge-C OSS v0.1 C/RCC host demo, its existing `specs/001-factory/` feature, v0.3 release-packager reference code under `factory/release-manager/`, six SWE inspection checklists, and the v0.4 editable `.drawio` architecture under `architecture/`. Do not overwrite working v0.1 evidence with synthetic v0.4 results. The v0.2/v0.3 workflow designs are **not** an executed Fabro implementation.

Claude MUST first inspect tool versions and actual Fabro runtime interfaces; resolve discrepancies between design and installed version by implementing versioned adapters and documenting decisions. Do not present pseudocode as runnable `.fabro` DSL. Do not modify original safety gates or v0.3 archive policy in place: add new schema/policy versions and migration tests.

## 1. Reference architecture and boundaries

```text
          Approved product inputs (read-only immutable baseline)
                              |
                   Fabro orchestrator (OSS)
                              |
       Skills registry + agent-scoped MCP gateway / tool registry
                              |
 SWE.1 author<->inspector -> SWE.2 ... SWE.6 -> gates -> optimizer
                              |
                      Release Manager agent
                              |
                 deterministic packager -> immutable ZIP
                              |
                  EXTERNAL OFFLINE HUMAN REVIEW

   +------------------------------------------------------------+
   |        INDEPENDENT FACTORY CONTROL PLANE (NO LLM)          |
   |  OS daemon/systemd watchdog  ->  Supervisor poller          |
   |         |                 |                 |              |
   |     Fabro run API     MCP health        Store health        |
   |         |                 |                 |              |
   |      incident ledger --> policy router --> repair dispatch  |
   |                                            |                |
   |                                    AI Repair Agent         |
   |                               isolated repair worktree     |
   |                                            |                |
   |                              tests + promote/rollback      |
   |                                            |                |
   |                              validated lesson candidate   |
   |                                  |                         |
   |                       shared knowledge store              |
   |  structured event bus -> trace store -> dashboard/API      |
   +------------------------------------------------------------+
```

**Fabro integration constraints (verify on pinned upstream version):** Fabro can discover skills and MCP tools, but also provides native agent tools. A successful MCP handshake does **not** imply that native shell/file-edit capabilities have been disabled, and Fabro may skip an unavailable MCP server while continuing to run. The factory must therefore enforce role-specific sandbox permissions independently, fail a separate required-tool preflight, and prove that the agent cannot use native tools to bypass MCP grants. Do not rely on a role's SKILL text alone to enforce access control. Built-in tools may be used by Claude during implementation; they are not authorized as unmediated production engineering interfaces.

**Trust boundaries:** (A) product source/workproducts; (B) supervisor/control plane; (C) isolated repair worktree; (D) append-only evidence and knowledge/audit stores; (E) offline human domain. The Repair Agent may not change A's baselined evidence or D's past records. Tool grants are imposed by MCP server, not only by prompt. Human offline acceptance is not represented as an AI quality gate.

**Runtime choices (open source):** Python 3.12 (supervisor, wrappers, API), MCP Python SDK or pinned Rust MCP SDK, FastAPI + SSE + server-rendered HTML/vanilla JS dashboard, SQLite WAL (single-host pilot) with migration interface, Pydantic/jsonschema for contracts, systemd service/timer/watchdog (Ubuntu), structured JSONL + SQLite indexed events; optional OpenTelemetry exporter and Prometheus metrics. Fabro own events/API are the primary source of run progress; do not scrape its UI or manipulate undocumented DB tables. Local Ollama serves Qwen; one GPU model at a time by default for RTX 4070 8 GB. All OS/SDK commands MUST be version checked before implementation.

## 2. Agent Skills registry (new)

`config/factory/agents.yaml` enumerates one primary skill per agent role, allowed MCP operations, model route, output schema, token budget and phase role. Install SKILL at `.fabro/skills/<role>/SKILL.md`, conforming to Open Agent Skills frontmatter. Provision the skill in Fabro session before using any engineering tool; validate discovered tool availability before invoking it.

**Roles (20):** `intake-analyst`; `swe1-author` through `swe6-author`; `swe1-inspector` through `swe6-inspector`; `misra-auditor`; `footprint-optimizer`; `safety-evidence-auditor`; `release-manager`; `fabric-repair`; `lessons-curator`; `mcp-integrator`.

Each SKILL defines: mission, read-only authoritative context, input manifest, permitted MCP tools, expected workproducts, test/inspection responsibilities, exit status and negative scope. Every AI tool invocation is scoped to a role/tool permission table enforced outside the model. Inject only the needed skill plus a small delta/context snapshot, not the full tool catalogue and process rationale. The supervisor and deterministic packager are **not AI agents**.

**Role privileges note:** `readonly: true` means the role must not modify frozen product workproducts or safety baselines; a narrowly granted append-only derived output (release archive for Release Manager or lesson proposal for Lessons Curator) is permissible when written by the deterministic, scope-enforcing MCP operation.

## 3. MCP gateway and wrapper strategy

1. Catalogue underlying executables by exact program/version, license and availability using `config/factory/mcp-registry.yaml`.
2. Prefer an existing, maintained and compatible MCP server if one is verified. Wrap tools lacking MCP behind domain servers rather than implementing a per-tool daemon: `forge-build-mcp`, `forge-analysis-mcp`, `forge-tests-mcp`, `forge-sim-mcp`, `forge-evidence-mcp`, `forge-repo-mcp`, `forge-observer-mcp`, `forge-knowledge-mcp`, `forge-docs-mcp`. Fabro's **native** MCP server/client capabilities handle orchestration.
3. Per-tool JSON schemas, declared side effects, assigned role grants, timeout, output truncation and artifact references are non-optional. Tool call gateway checks canonical repository paths, executable argv allowlist, size caps, no shell injection, no network access by default, pinned files/versions and process exit status.
4. Require MCP health probe/handshake/tool-list compatibility for all **mandatory** tools before a run. Optional missing tools are visibly `DISABLED` with safety-plan impact recorded. No silent direct CLI substitution inside product agent workflow.
5. Return `status`, `summary`, `metrics`, `artifact_refs`, `issues` and `provenance` from adapters. Preserve raw logs by hash in immutable evidence directory, do not flood LLM tool output.
6. Keep compile/test/coverage generation deterministic. The MCP interface does NOT itself validate tool suitability/qualification for ISO 26262.

**Initial operations:**

| MCP server | First operations (names are proposed, not upstream API assertions) | Backing software |
|---|---|---|
| `forge-build-mcp` | `configure`, `compile`, `measure_elf`, `stack_usage`, `disassemble` | CMake, Ninja, GCC/Clang, GNU binutils |
| `forge-analysis-mcp` | `cppcheck`, `clang_analyze`, `clang_tidy`, `cbmc_verify`, `frama_check` | Cppcheck MISRA subset, Clang, CBMC, Frama-C |
| `forge-tests-mcp` | `run_unit`, `run_integration`, `llvm_coverage`, `gcov_coverage` | Unity/CMock, CTest, LLVM-Cov, gcovr |
| `forge-sim-mcp` | `run_renode`, `run_hwsim`, `inject_fault` | Renode, HwSim |
| `forge-evidence-mcp` | `freeze_baseline`, `validate_trace`, `check_inspection`, `build_package` | Python gates, checksum packager |
| `forge-repo-mcp` | `diff_scoped`, `create_worktree`, `commit_candidate`, `get_commit` | Git scoped adapter |
| `forge-observer-mcp` | `get_status`, `get_incident`, `query_events` | read-only observer API |
| `forge-knowledge-mcp` | `find_lessons`, `propose_lesson`, `retract_lesson` | validated lesson store |
| `forge-docs-mcp` | `render_diagram`, `build_docs`, `validate_artifact` | PlantUML, MkDocs, document gates |

Do **not** expose direct access to kernel flashing, release approval, unbounded shell, privileged package installs, safety policy override, deleting archives, or secrets through any generic MCP tool.

## 4. Model-free supervisor design

- Run as a separate unprivileged systemd service, with `Restart=on-failure`, health heartbeat and watchdog; emit a self-heartbeat to an independent monitored file/endpoint.
- Poll loop uses asynchronous I/O and rules only, with `poll_interval_seconds=60` and jitter configurable if needed. Periodic checks: Fabro API readiness, active run heartbeat/progress, stage execution deadline, MCP list/ping, repository/evidence/DB writability, disk available, memory pressure, GPU memory pressure (optional NVML/nvidia-smi), queue age, dashboard API. Mark unsupported metrics `UNKNOWN`, never `PASS`.
- Incident key is a stable fingerprint (component + failure type + relevant run + version) with dedup and persistent state machine: `DETECTED -> TRIAGED -> REPAIRING -> VERIFYING -> RESOLVED` or `ROLLED_BACK -> REQUIRES_OFFLINE_ATTENTION`.
- If Fabro down, dispatcher invokes a local supervised repair runner separate from Fabro, restricted to repair role/skills/MCP toolset; once Fabro recovered, it may use Fabro run management. No circular dependency.
- A detected incident *requests an AI repair* if eligible and within budget. Cheap deterministic actions (e.g., a safe service restart) may be prerequisites but never hide the incident or skip the requested repair triage.
- Incident locking and global quota stop concurrency storms. Repair never modifies active product workspace; isolation via git worktree/container, restricted OS user and network-deny sandbox.
- Promotion rule: exact protected paths unchanged, lint/unit/contract/e2e tests pass, expected health restored for N consecutive polls, atomic pointer/service switch and rollback on regression. Safety policy changes are out of automatic repair scope and produce an offline request.
- Route *product* defects to SWE author/inspection loops, not fabric repair. Incident and SWE finding objects have different schemas and owners.

## 5. Repair Agent, closed-loop improvement and lessons

- Incident bundle contains only relevant service status, last failing checks, agent/tool/stage IDs, sanitized tail, current versions, recent change hash, and allowed paths. No unbounded entire factory log.
- `fabric-repair` SKILL returns a patch and concise machine-readable result; privileged deployment remains in deterministic service, not agent MCP.
- All attempted fixes generate incident evidence; successful validated fixes generate a **lesson candidate** with triggering symptoms, root cause, proven action, verification, constraints, source hashes, affected versions, TTL and trust state.
- `lessons-curator` SKILL normalizes and deduplicates; policy/validator promotes only verified, non-secret, non-policy-weakening records. Shared lesson queries use top-K lexical retrieval initially (SQLite FTS5); vector retrieval is optional and cannot require a model call for the supervisor.
- Track when each lesson was used by each run and record impact. On regression, retract and invalidate derived promotions. Lessons are reference material, not new system instructions; protect against prompt injection.

## 6. Observability and dashboard

**Event source:** Fabro native ordered run-event API + forge-created structured domain events, normalized to `contracts/event.schema.json` and persisted locally; ingestion must be idempotent and resumable using source offset/event ID. Timestamp in UTC. Propagate correlation IDs from workflow -> phase -> agent -> MCP tool -> incident -> release package.

**Channels:** `human`, `workflow`, `tools`, `ai`, `supervisor`, `repair`, `security`, `audit`, `metrics`, `knowledge`; per-channel level `OFF|ERROR|WARN|INFO|DEBUG|TRACE`. Mandatory audit/security classes always retained. AI content capture is **OFF by default** and cannot contain hidden reasoning; metadata (model, tokens, latency, outcomes) is independent of raw text capture.

**UI:** top status bar (healthy/degraded/blocked), runs and phase board, inspections and loop count, MCP status, incidents/repairs/lessons, candidate package and release gaps, footprint and coverage highlights, token and time charts, and trace viewer with channel/severity/phase/agent/search filters. The UI follows selected *display* filters without modifying *capture* settings. Authenticated read-only user by default; role-based audit for optional administrative controls. Use SSE or polling fallback; no third-party cloud dependency.

**Retention:** per-channel policy configurable, bounded disk quotas, redact before write, protect audit via append-only/hashed segments, export raw and filtered traces with hashes for offline review; no plaintext credentials in events, lessons or archives.

## 7. Token governance design

- Prioritize deterministic tools for compile/lint/test/coverage/inspection gate and health check; only ask an LLM to author, inspect or diagnose when needed.
- Per-agent role policy: allowed model, per-call tokens, per-stage token ceiling, max turns, maximum MCP response bytes, max consecutive repair/rework loops. CLI output summarized at MCP boundary (<=2 KiB by default) with artifact references, raw logs separate.
- Return strictly JSON `{status, artifacts, issues, next_action}`. Example: `{"status":"BLOCKED","artifacts":["SWE3-001"],"issues":["MISRA:2"],"next_action":"rework"}`. No optional prose; the formal workproduct can still contain full engineering justification.
- Avoid forcing every agent to load the full Spec Kit directory. Use phase-specific immutable input IDs + changed files + max 3 validated lessons. Reload docs only if hash changed. Cache model-independent context summaries by revision.
- The governor blocks further agent calls on budget exhaustion and records the stage as BLOCKED; no ad hoc reduction in inspection coverage. Dashboard shows consumed/remaining tokens; for local models, estimated token counts labeled `estimated` if provider lacks metering.
- Optimization KPI: cost/tokens per approved candidate and per accepted SWE phase, median tool output bytes, context re-read count, attempts per gate and defects found per inspector; tune only after measured baseline.

## 8. Release Manager v0.4 contract

Carry forward the v0.3 packager/quality policy; propose a versioned v0.4 overlay adding:

```text
operations/
  agents/skills-manifest.json       # role, skill version, checksum, provider, budget
  mcp/tool-registry.json            # server names, tools, versions, grants, availability
  supervisor/health-summary.json    # poll status and unresolved operational gaps
  incidents/incidents.jsonl        # detected/triaged/repair status & attempts
  repairs/repair-results.jsonl      # patch hashes, test evidence, promotion/rollback
  knowledge/lesson-ledger.json      # lesson IDs, approval/retraction, references
  telemetry/events-index.json      # event schema, capture policy, trace segments/hashes
  tokens/usage-by-agent.json       # model/provider, tokens, budget, turns
  dashboard/review-summary.html    # optional read-only standalone export
```

All records are immutable snapshots at packaging time. The Release Manager cannot invent missing operational evidence, erase incidents, reclassify failed checks or decide safety approval. A failed repair should not automatically block a *different already-complete run* unless it affects that run's evidence/provenance; the relation is deterministic via dependency map.

## 9. Phased delivery and acceptance gates

| Milestone | Deliverables | Deterministic exit |
|---|---|---|
| M0 — Protect baseline | Freeze runnable OSS v0.1 + v0.3 packager; inventory current Fabro SDK/API and licences | Both pre-existing test suites pass unchanged |
| M1 — Skills & policy | 20 valid SKILL files, `agents.yaml`, output contracts, preflight | Missing skill/tool denial tests; 100% role coverage |
| M2 — MCP infrastructure | Domain MCP servers and registry, mock tools + real build/static/coverage adapters | Tests prove handshake, least privilege, deterministic artifacts |
| M3 — Supervisor & incident store | systemd daemon, health checks, persistence, dedup, quota | 100 healthy polls -> 0 model calls; injected Fabro-down detected |
| M4 — Autonomous repair | isolated Repair Agent invocation, rollback, validation, evidence | Injected recoverable fault autonomously fixed and health restored; safety-path tamper attempt denied |
| M5 — Lessons | validated lesson store, retrieval/retraction APIs | Verified fix retrieved in second workflow; invalid lesson quarantined |
| M6 — Dashboard & traces | API, UI, SSE, channel-level capture/filter, redaction, tokens | Filter tests, no trace leak, metrics and incidents visible end-to-end |
| M7 — Release/e2e | v0.4 package overlay, Fabro workflow integration, docs, resilience tests | Unattended end-to-end generic RCC candidate or BLOCKED archive, valid hashes and no false safety claims |

**Order matters:** M0 -> M1 -> M2; M3 can start once event schema and Fabro API adapter exist; M4 after M3; M5 after M4; M6 after M3/events; M7 after all P0 controls. Parallelizing independent MCP adapters is allowed only after contracts and role permissions are frozen.

## 10. Verification matrix and fault injection

- **Static/design:** validate all SKILL names and frontmatter, agent-registry parity, no mandatory tool with no MCP, schema examples, access matrix, trace taxonomy, policy versioning.
- **Supervisor:** 100 healthy polls + mock LLM gateway spy -> zero calls; Fabro process killed -> incident; stagnant heartbeat; missing tool; DB/disk unavailable; supervisor crash/restart; incident dedup; repair storm bound.
- **Repair:** controlled induced config break, recovery with test, simulated malicious request to disable QA, failed remediation rollback, two-attempt exhaustion, duplicate incident lock, startup when Fabro unavailable.
- **Knowledge:** successful remediation available in another workflow; unvalidated/expired/retracted lesson never used; malicious prompt injection preserved as data only; secret extraction/rejection; duplicate normalized.
- **Observability:** event schema and ordering/dedup; redaction with known secret canary; severity/category filtering; human INFO <=160 chars; audit cannot be disabled; AI raw trace capture OFF by default; SSE reconnect last-event-ID; old retention expiry.
- **Token budgets:** small stage returns compact JSON; huge tool log produces bounded model payload and full evidence; budget excess -> BLOCKED; inspect no hidden chain-of-thought logging.
- **Release:** synthetic v0.3 tests remain passing; missing v0.4 operational evidence blocks scoped run; success includes all hashes, health/repair history, tool+skill provenance; archive immutable; no safety signoff field auto-populated.
- **ASIL orientation:** confirm reviewed HSI, bounded memory/stack, target measurements and formal verification evidence requirements remain mandatory for hardware candidate; host coverage alone does not count as MCU verification.

## 11. Security/operational rollout plan

- Default bind dashboard to loopback, require auth before network exposure, disable internet by default in tool sandboxes, restrict filesystem and OS identity per service, cap log retention. Document backups/restoration of SQLite/knowledge store and replay offsets.
- Separate code repositories/branches for *factory infrastructure* repairs and *product* driver changes; disable auto-merge if protected files touched, untrusted dependencies introduced or CI tests cannot run. Distinguish offline reviewer from operations admin.
- Prefer reproducible pinned containers/lockfiles, generate SBOM and licence inventory for runtime/adapters, forbid automatic tool/model version upgrades in active baselines.
- Implement tests first for incident state transitions, privilege rules and recovery failure behavior; do not build a broad dashboard before the trustworthy telemetry model.

## 12. Claude implementation directions

1. Start at `CLAUDE.md` and `spec.md`; use `/speckit.analyze` to verify spec/plan/task consistency. Update task state with evidence as work proceeds.
2. Implement work **in `tasks.md` order**, write tests for each contract, run test commands, attach summarized status in commits. Never respond with lengthy rationale; maintain human-readable engineering docs and terse execution summaries.
3. For each upstream Fabro feature (MCP client, skills, events, run control), prefer real documented API to hypothetical DOT/supervisor syntax; where unsupported, use a local adapter and record an ADR.
4. During implementation Claude is allowed as developer; factory runtime defaults remain local Qwen/OSS. No cloud API requirement may be added without explicit authorization.
5. No safety approval or production release without offline human assessment.

## Document links

- [`spec.md`](spec.md) — normative behavior and user stories
- [`tasks.md`](tasks.md) — ordered actionable work with FR and test references
- [`data-model.md`](data-model.md) — state and event entities
- [`research.md`](research.md) — current verified Fabro/Spec Kit integration points
- [`contracts/`](contracts/) — JSON schemas and examples
- `../../config/factory/` — proposed registries and policies
- `../../architecture/Forge-C_Fabro_DarkFactory_v0.4.drawio` — editable architecture


## Follow-on mandatory feature — production KPIs (v0.5)

Add `specs/003-manufacturing-kpis/` as a dependent Spec Kit feature. Its **K0 dictionary/contracts** may begin alongside M6; its **K1 deterministic engine** requires the M6 event ledger; **K2 dashboard/MCP** requires K1; **K3 immutable KPI package** requires M7 packaging. KPI tasks must never override safety/inspection/release semantics. See `KPI_CLAUDE_START.md`. This section is a plan addendum, not an implementation claim.
