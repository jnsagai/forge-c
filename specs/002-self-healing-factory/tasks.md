# Implementation Tasks — Forge-C v0.4 (Claude Code)

**Feature:** `002-self-healing-factory`  
**Rule:** complete tasks in dependency order; each checked task requires committed tests + verifiable output (not an agent's statement). `[P]` means safely parallel after prerequisite gates.  
**Acceptance:** `M0` through `M7` in [`plan.md`](plan.md).  
**Scope:** architecture and starter contracts in this package are a specification; **the production control plane/MCP adapters/dashboard are not implemented**.

## M0 — Establish reproducible baseline

- [X] **T001 [P0]** Pin Fabro, Ollama/Qwen, Python/MCP SDK, LLVM/GCC, Cppcheck, CBMC and dashboard dependencies with OSS licence inventory and tool matrix. Check versions actually installed. **[FR-039]** Test: recorded lockfile/SBOM; no hardcoded proprietary dependencies. ✅ Evidence: `evidence/v0.4/runs/T001/latest.json`
- [X] **T002 [P0]** Run current OSS v0.1 host RCC tests/LLVM coverage and the v0.3 reference packager tests unchanged. Preserve original reports and source hashes. **[FR-031,FR-032]** Test: baseline reports stored with tool/host provenance. ✅ Evidence: `evidence/v0.4/runs/T002-v01-gates/latest.json`, `evidence/v0.4/runs/T002-v03-packager/latest.json`, `evidence/v0.4/runs/T002-design/latest.json`, `evidence/v0.4/runs/T002-oss-demo/latest.json`, `evidence/v0.4/runs/T002-clang-analyzer/latest.json`, `evidence/v0.4/runs/T002-host-size/latest.json`
- [X] **T003 [P0]** Create versioned `factory/` Python packages (not new source overlay hacks), lint/type-check/pytest coverage and reproducible Dev Container/Ubuntu setup. **[FR-039]** Test: clean environment bootstrap, no paid services. ✅ Evidence: `evidence/v0.4/runs/T003/latest.json`
- [X] **T004 [P0]** Audit actual Fabro version's run API/events, MCP config, skills discovery, DOT loops, recovery hooks and known limitations. Document in ADRs before coding unsupported assumptions. **[FR-001,FR-004,FR-034]** Test: CLI/API smoke tests where available, mocked fallback elsewhere. ✅ Evidence: `evidence/v0.4/runs/T004/latest.json`

## M1 — Every AI agent has a SKILL; enforce roles

- [X] **T005 [P0]** Implement `agents.yaml` loader and JSON/Pydantic schema validator: unique role, `SKILL.md` path/hash, model, grants, caps, outputs. **[FR-001,FR-002]** Test: invalid/missing/duplicate SKILL fails preflight. ✅ Evidence: `evidence/v0.4/runs/T005/latest.json`
- [X] **T006 [P0] [P]** Complete all 20 `.fabro/skills/<role>/SKILL.md` from starter contracts; verify Fabro discovery and YAML frontmatter. **[FR-001,FR-002,FR-027]** Test: every role loaded; no unbound agent declared by workflows. ✅ Evidence: `evidence/v0.4/runs/T006/latest.json`
- [X] **T007 [P0]** Build role- and phase-aware tool authorization at MCP gateway and in the execution sandbox (independent of prompt), including prevention of bypass by Fabro built-in shell and filesystem tools. **[FR-003,FR-006]** Test: inspector cannot edit workproducts, Release Manager cannot waive a finding, Repair Agent cannot access product baselines, and attempted native-tool bypass is denied. ✅ Evidence: `evidence/v0.4/runs/T007/latest.json`
- [X] **T008 [P0]** Implement compact agent result schema/parser (`status, artifacts, issues, next_action`) and block freeform status prose in lifecycle controls. **[FR-027,FR-028]** Test: invalid/unbounded response rejected, findings preserved. ✅ Evidence: `evidence/v0.4/runs/T008/latest.json`
- [X] **T009 [P0]** Wire author/inspector role separation, frozen baseline, checklist evidence and reinspection after changes into Fabro, preserving all six SWE process loops. **[FR-003,FR-038]** Test: stale inspector hash rejects pass; blocked finding loops or packages. ✅ Evidence: `evidence/v0.4/runs/T009/latest.json`

## M2 — MCP for every engineering tool

- [X] **T010 [P0]** Implement `mcp-registry.yaml` loader: logical tool, server, operation, mandatory flag, expected schema, timeout, version/availability and permissions. **[FR-004,FR-005,FR-040]** Test: missing mandatory MCP blocks run and emits precise issue. ✅ Evidence: `evidence/v0.4/runs/T010/latest.json`
- [X] **T011 [P0]** Implement shared MCP wrapper SDK: JSON input validation, canonical restricted paths, `subprocess` with argv arrays/no shell, resource limits, stdout/stderr evidence hashing, bounded response, redaction and audited access control. **[FR-006,FR-028]** Tests: traversal, injection, overlong output, timeout, denied operations. ✅ Evidence: `evidence/v0.4/runs/T011/latest.json`
- [X] **T012 [P0] [P]** Build `forge-build-mcp` adapters for CMake/Ninja/Clang/GCC/binutils, size/map/stack; target flag allowlist and pinned tool provenance. **[FR-004,FR-006]** Tests: native RCC compile/ELF size, mocked missing GNU Arm toolchain. ✅ Evidence: `evidence/v0.4/runs/T012/latest.json`
- [X] **T013 [P0] [P]** Build `forge-analysis-mcp` for Clang analyzer, Cppcheck MISRA **subset**; plug CBMC/Frama-C/Clang-Tidy only when verified and installed. **[FR-004,FR-040]** Tests: clean defect fixture, broken fixture, unknown MISRA-rule coverage explicit. ✅ Evidence: `evidence/v0.4/runs/T013/latest.json`
- [X] **T014 [P0] [P]** Build `forge-tests-mcp` for Unity/CMock/CTest and LLVM-Cov/llvm-profdata; gcovr optional; distinguish host/target. **[FR-004]** Tests: negative unit, branch and MC/DC fixture, raw coverage evidence intact. ✅ Evidence: `evidence/v0.4/runs/T014/latest.json`
- [X] **T015 [P0] [P]** Build `forge-sim-mcp` for Renode and HwSim with optional dependency checks and deterministic fault injection interface. **[FR-004,FR-040]** Tests: mocked device model, unavailable simulator reports UNSUPPORTED/disabled. ✅ Evidence: `evidence/v0.4/runs/T015/latest.json`
- [X] **T016 [P0] [P]** Build `forge-evidence-mcp` wrapping trace/gate/inspection tools and existing immutable release packager; `forge-repo-mcp` exposing tightly scoped Git operations. **[FR-004,FR-006,FR-031]** Tests: phase artifacts immutable, release read-only, no arbitrary git push. ✅ Evidence: `evidence/v0.4/runs/T016/latest.json`
- [X] **T017 [P0] [P]** Build `forge-observer-mcp`, `forge-knowledge-mcp`, `forge-docs-mcp` for status, lessons and documentation validation. **[FR-004,FR-019]** Tests: reads bound, unsafe lesson promotion denied, generator output provenance. ✅ Evidence: `evidence/v0.4/runs/T017/latest.json`
- [X] **T018 [P0]** Integrate Fabro MCP configuration via documented settings/run-config paths; perform `tools/list`, health and permission preflight. **[FR-005,FR-040]** Test: full required-tool discovery, missing tool -> BLOCKED not shell fallback. ✅ Evidence: `evidence/v0.4/runs/T018/latest.json`

## M3 — External deterministic supervisor

- [X] **T019 [P0]** Implement persisted incident DB and state transitions from `data-model.md` and `contracts/incident.schema.json`. **[FR-010]** Tests: transactional transition guards, power loss/restart resume, fingerprint dedup. ✅ Evidence: `evidence/v0.4/runs/T019/latest.json`
- [X] **T020 [P0]** Build non-LLM scheduler/service with interval config validation, jitter, independent progress checkpoints and OS/service-manager watchdog. **[FR-007,FR-008,FR-034]** Test: 100 healthy polls and mocked LLM invocation counter = exactly ZERO. ✅ Evidence: `evidence/v0.4/runs/T020/latest.json`
- [X] **T021 [P0] [P]** Add health probes for Fabro liveness, run deadlines, stalls, MCP handshake, queue, storage, dashboard and resource pressure with unknown-data states. **[FR-009]** Tests: injected Fabro crash, frozen stage, MCP timeout, disk full, unreachable telemetry. ✅ Evidence: `evidence/v0.4/runs/T021/latest.json`
- [X] **T022 [P0]** Implement incident routing, active incident leases, backoff, cooldown, max attempts and repair dispatch queue. **[FR-010,FR-011,FR-015]** Test: only one repair for duplicate root-cause, breaker after configured exhaustion. ✅ Evidence: `evidence/v0.4/runs/T022/latest.json`
- [X] **T023 [P0]** Implement Fabro-independent repair launch path for Fabro-down condition (isolated local repair worker), plus Fabro child-run pathway for healthy engine; test both. **[FR-011,FR-034]** Test: Fabro killed -> Repair Agent starts through fallback. ✅ Evidence: `evidence/v0.4/runs/T023/latest.json`
- [X] **T024 [P0]** Persist heartbeat/watchdog and reboot resume procedures with systemd services; document container-only fallback. **[FR-007,FR-034]** Tests: supervisor SIGKILL -> OS restarts, incident DB still valid. ✅ Evidence: `evidence/v0.4/runs/T024/latest.json`

## M4 — Isolated autonomous repair

- [X] **T025 [P0]** Instantiate `fabric-repair` SKILL with incident-only context and bounded MCP grants; avoid copying broad run context into model. **[FR-011,FR-012,FR-027,FR-028]** Test: input token budget and allowed path test. ✅ Evidence: `evidence/v0.4/runs/T025/latest.json`
- [X] **T026 [P0]** Create restricted repair worktree/process sandbox and protected path denylist; prefer OS permissions and a syscall/process policy over prompt restrictions. **[FR-012,FR-013]** Test: attempted editing of safety policies/release evidence fails regardless of agent intent. ✅ Evidence: `evidence/v0.4/runs/T026/latest.json`
- [X] **T027 [P0]** Implement deterministic repair promotion controller: patch hash, tests, health stability, atomic switch and rollback; no agent self-approval. **[FR-014]** Test: successful induced service config fix, failed test -> rollback. ✅ Evidence: `evidence/v0.4/runs/T027/latest.json`
- [X] **T028 [P0]** Record repair outcomes, restored health, elapsed time, token consumption, and unresolved failures into incident ledger and downstream release evidence. **[FR-016,FR-031]** Tests: unfixable fault -> `REQUIRES_OFFLINE_ATTENTION` and blocked package if relevant. ✅ Evidence: `evidence/v0.4/runs/T028/latest.json`
- [X] **T029 [P0]** Ensure repairing factory infrastructure never silently repairs/changes product requirements, safety allocations or completed workproduct baselines. **[FR-013,FR-038]** Test: source+evidence SHA unchanged before/after infrastructure repair. ✅ Evidence: `evidence/v0.4/runs/T029/latest.json`

## M5 — Durable lessons learned and cross-workflow reuse

- [X] **T030 [P0]** Implement lesson candidate schema, SQLite store and validation state machine with provenance, expirations and affected versions. **[FR-017,FR-018]** Tests: unverified repair cannot become `VALIDATED`. ✅ Evidence: `evidence/v0.4/runs/T030/latest.json`
- [X] **T031 [P0]** Implement `lessons-curator` process and deterministic validators for secrets, unsafe policy edits, duplicate/unsupported prescriptions and regression check references. **[FR-018,FR-019]** Tests: malformed/prompt-injection lesson quarantined. ✅ Evidence: `evidence/v0.4/runs/T031/latest.json`
- [X] **T032 [P0]** Implement scoped top-K retrieval (FTS5 first), tool/error/version relevance and token-size budgets, injecting only trusted lessons. **[FR-019,FR-028,FR-029]** Test: next workflow receives approved lesson, never unapproved candidate. ✅ Evidence: `evidence/v0.4/runs/T032/latest.json`
- [X] **T033 [P1]** Implement lesson retraction, impact list of consuming runs, and dependency invalidation on tool/version regression. **[FR-035]** Test: revoked lesson no longer retrieved. ✅ Evidence: `evidence/v0.4/runs/T033/latest.json`

## M6 — Events, configurable traces and dashboard

- [X] **T034 [P0]** Implement normalized event collector for Fabro native run events + factory events with idempotent offsets and `event.schema.json` validation. **[FR-026]** Test: replay identical stream yields identical unique event set, no lost order/correlation. ✅ Evidence: `evidence/v0.4/runs/T034/latest.json`
- [X] **T035 [P0]** Implement channel/severity capture policy validation and live reload with hard minimum audit/security capture. **[FR-022,FR-023,FR-024]** Test: turning audit OFF is rejected, dashboard filters do not alter capture. ✅ Evidence: `evidence/v0.4/runs/T035/latest.json`
- [X] **T036 [P0]** Implement secret redactor, raw AI capture opt-in, immutable artifact-backed tool logs and configurable per-channel retention. **[FR-025,FR-028]** Test: credentials never persisted in any trace level, no hidden reasoning capture. ✅ Evidence: `evidence/v0.4/runs/T036/latest.json`
- [X] **T037 [P0]** Implement API queries for health/runs/inspections/agents/MCP/incidents/lessons/packages/tokens and event filters. **[FR-020,FR-021]** Test: role-limited read endpoints and pagination/search correctness. ✅ Evidence: `evidence/v0.4/runs/T037/latest.json`
- [X] **T038 [P0]** Build responsive UI with health badge, run stage view, incident/repair panel, MCP status, inspection findings, release status, resource and token charts. **[FR-020]** Test: browser smoke test at mobile and desktop widths. ✅ Evidence: `evidence/v0.4/runs/T038/latest.json`
- [X] **T039 [P0]** Implement per-user display controls (channels/severity/run/agent/search), independent from capture policy; minimal default HUMAN view. **[FR-021,FR-022,FR-024]** Test: hidden channels remain queryable to authorized user, audit preserved. ✅ Evidence: `evidence/v0.4/runs/T039/latest.json`
- [X] **T040 [P1]** Add SSE with polling fallback, stored offset/reconnect and no direct DB exposure to browser. **[FR-037]** Test: interrupted client reconnects without duplicate display or event loss. ✅ Evidence: `evidence/v0.4/runs/T040/latest.json`
- [X] **T041 [P0]** Implement tool/AI/phase token and output-size metrics with unknown/estimated flag; never silently invent provider token counts. **[FR-020,FR-029]** Tests: input/output budgets and dashboard sums accurate. ✅ Evidence: `evidence/v0.4/runs/T041/latest.json`

## M7 — Token budget enforcement and complete offline package

- [X] **T042 [P0]** Implement stage budget governor (turns, total tokens, MCP bytes, retries, lesson K) and `TOKEN_BUDGET_EXHAUSTED` behavior. **[FR-029,FR-030]** Test: forced budget exhaustion -> safe phase failure, not false PASS. ✅ Evidence: `evidence/v0.4/runs/T042/latest.json`
- [X] **T043 [P0]** Enforce compact JSON agent result, short human status <=160 chars, evidence-by-reference and bounded MCP return payload. **[FR-027,FR-028]** Test: 5 MB compiler log returned as small agent payload but full hashed log retained. ✅ Evidence: `evidence/v0.4/runs/T043/latest.json`
- [X] **T044 [P1]** Implement resumable idempotent Fabro stage boundaries and change-impact reinspection mapping, conditional on verified Fabro capabilities. **[FR-036,FR-003]** Test: interrupted stage resumes without rewriting prior release evidence. ✅ Evidence: `evidence/v0.4/runs/T044/latest.json`
- [X] **T045 [P0]** Extend existing v0.3 packager through versioned v0.4 operational inventory and strict gap report; preserve all previous ASIL-oriented checks. **[FR-031,FR-032,FR-033]** Test: every required skills/MCP/incidents/lessons/token provenance path indexed/hashed. ✅ Evidence: `evidence/v0.4/runs/T045/latest.json`
- [X] **T046 [P0]** Ensure **every** Fabro terminal path, including crashed/exhausted/blocked, invokes the final Release Manager or safe external finalizer. **[FR-031,FR-032]** Test: inject failing SWE.3 static check -> BLOCKED archive without human interaction. ✅ Evidence: `evidence/v0.4/runs/T046/latest.json`
- [X] **T047 [P0]** Prove inspector-review loops and infrastructure repair loops are separated and bounded. **[FR-003,FR-015,FR-038]** Test: driver defect routes SWE loop; Fabro process defect routes Repair Agent. ✅ Evidence: `evidence/v0.4/runs/T047/latest.json`
- [X] **T048 [P0]** Execute offline generic RCC end-to-end on local Qwen using real Fabro: full workproducts, inspections, tests, footprint, coverage, health/trace reports and review archive. **[FR-001..FR-040]** Test: one command starts and completes without human prompt; status is valid and evidence reproduces. ✅ Evidence: `evidence/v0.4/runs/T048/latest.json` — acceptance test passed on WO-0002-STM32N6-RCC-r10 (unattended, local qwen3:8b, valid BLOCKED package). **Product outcome: BLOCKED at SWE.3; full SWE.4–6 workproducts NOT produced by the 8B model; no READY package.**
- [X] **T049 [P0]** Perform threat-model/security tests: prompt injection in lessons, path traversal in MCP, malicious repair patch, secrets in traces, forged AI PASS and archive tampering. **[FR-006,FR-013,FR-018,FR-025,FR-033]** Test: every prohibited operation blocked with audit event. ✅ Evidence: `evidence/v0.4/runs/T049/latest.json`
- [X] **T050 [P0]** Document Ubuntu setup, service lifecycle, backup/restore, trace retention, dashboard auth, upgrade/rollback, failure runbook, review instructions and known safety-tool gaps. **[FR-039]** Test: clean workstation reproduces demo and fault injections. ✅ Evidence: `evidence/v0.4/runs/T050/latest.json`
- [X] **T051 [P0]** Generate final FR→task→test coverage matrix, run all contract/acceptance suites, stamp evidence/commit hashes and produce a self-contained implementation status report (PASS/FAIL/NOT_RUN). **[FR-001..FR-040]** Test: no P0 feature without a deterministic test or explicit BLOCKED gap. ✅ Evidence: `evidence/v0.4/runs/T051/latest.json`

## Mandatory independent verification before marking a task complete

- Agent-generated patches must be inspected by a different role/session; the deterministic test runner must be separate from review agent assertions.
- Evidence must show exact command/adapter, pinned tool version, exit code and file hash. A textual `PASS` is not evidence.
- Any unresolved P0 requirement or required tool without MCP means NOT DONE and the resulting handover status is BLOCKED.
- Do not mark ASIL B safety approval or ASPICE process capability as achieved. All safety approval remains an offline human responsibility.

## Claude execution hints

Use Spec Kit skill commands installed for Claude (`/speckit-plan`, `/speckit-tasks`, `/speckit-implement` on skill-based versions; confirm actual available names). The feature documents are **already authored**; do not overwrite them with generic summaries. Begin with task T001 and report concise progress: `Tnnn PASS/FAIL — artifact_ref — issue_count`. Ensure every updated tool uses MCP and every new AI agent receives a SKILL before wiring it into the workflow.


## v0.5 extension

- [ ] Execute feature `003-manufacturing-kpis` tasks **KPI-T001–KPI-T020** per its dependency matrix after the relevant 002 instrumentation milestones. Do not label v0.4 M6 complete solely because KPI specs exist.
