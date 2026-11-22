# Implementation Plan: Forge-C High-Integrity V-Model Skills (APM package)

**Branch**: `feat/023-high-integrity-vmodel-skills` | **Date**: 2026-11-22 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/023-high-integrity-vmodel-skills/spec.md`

## Summary

We ship `forge-c-hi`, an APM package in `packages/forge-c-hi/`. It turns Forge-C's factory know-how into portable
skills for any coding agent. The package has six parts:

- **Skills:** an author and an independent inspector for each V-model stage (10 stages, system requirements down to
  unit construction and back up to system qualification).
- **Deterministic engine (`hi-gates` skill):** stdlib Python that does all of the following:
  - checks workproduct structure, traceability and requirement quality;
  - applies a standard profile (generic, ISO 26262, IEC 61508, ASPICE 4.0);
  - guards write scope;
  - seals READY_FOR_OFFLINE_REVIEW or BLOCKED packages.

  The same engine is exposed as a CLI and as an MCP server.
- **Conductor (`hi-conductor` skill):** runs a stage loop with a configurable harness and model per role. Reference
  setup: Claude Code author and Codex/GPT inspector (read-only).
- **Two demo projects:** a natural-language middleware project (watchdog/health-monitor manager) and a driver project
  (IWDG, traced to reference-manual section and page). They are linked into one V.
- **Evaluation kit:** an A/B comparison with and without the package, plus a seeded-defect corpus.
- **Submission material:** the README and the submission pack for the Capgemini hackathon. Target 2026-12-05, hard
  deadline 2026-12-07 23:59 CET.

## Technical Context

**Language/Version**: Python ≥3.10, standard library only, for the gates, CLI, MCP server, conductor, packager and eval.
Markdown and JSON for skills, profiles and checklists.

**Primary Dependencies**:
- **Required:** apm-cli ≥0.37 (MIT) to install.
- **Optional tools for the gates:**
  - `pdftotext`/`pdfinfo` (poppler) for the driver document index;
  - gcc/clang, cppcheck and gcov/gcovr for the code-stage gates;
  - git for the diff-based scope backstop.
- **Reference harnesses:** Claude Code 2.1.x and Codex CLI 0.171.x, both on the owner's accounts.

**Storage**: files in the user's project: `.hi/` for configuration, state and run logs, and `hi/` for workproducts and
packages.

**Testing**: pytest for the package's own tests (`packages/forge-c-hi/tests/`). An APM install smoke test in a temporary
consumer project. Regression on the existing suites (`python3 tests/spec/validate_design.py` plus the existing pytest
targets).

**Target Platform**: Linux and macOS with Python 3.10+. Windows best-effort, because the sh locator needs Git Bash or WSL.

**Project Type**: a distributable agent-skills package (APM) with a stdlib CLI/MCP engine.

**Performance Goals**: each deterministic gate finishes in under 5 s on a 200-requirement set. The P1 demo takes under
30 min of user hands-on time (SC-001).

**Constraints**:
- No paid API.
- No Omniverse2.
- No vendor or standard text in the package.
- No change to the existing factory's behaviour.
- The constitution v0.5.0 assisted mode applies.

**Scale/Scope**:
- 10 V stages, giving 20 stage skills plus intake, gates, conductor and release (24 skills);
- 4 profiles plus a template;
- 2 demo projects;
- at least 20 seeded defects.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design (below).* Constitution v0.5.0.

| Principle | How this feature complies | Status |
|---|---|---|
| I Safety/correctness first, no invented HW facts | FR-018. In driver mode every hardware claim needs a resolvable `{doc, section, page}`, otherwise there is an open point. No footprint work is in scope. | PASS |
| II Evidence-driven, standard profiles | Verdicts come only from gates (FR-011). Every gate result records the tool, version, exit code and hash. Profiles carry clause IDs only (FR-008). The packager keeps the manifest/hash approach. | PASS |
| III Unattended run, external release authority | The conductor runs a stage loop with no human approval inside it. Failures give BLOCKED with findings. The disclaimer says no approval or certification. In assisted mode the human is never a release approver. | PASS |
| IV Versioned SKILLs, author/inspector independence | Each role is a versioned `SKILL.md` with frontmatter metadata. The reference inspector is a different model family in a read-only sandbox. Profiles can require separation. | PASS |
| V MCP for production agent tools | `hi_mcp.py` exposes the gates as MCP tools. Assisted-mode harnesses keep their built-in shell, which the constitution accepts. Write scope is enforced by hook plus gate backstop. No shell or flashing is exposed through MCP. | PASS (see Complexity) |
| VI Model-free supervision/self-healing | Out of scope for the package. The factory supervisor is untouched. The conductor's own checks are deterministic and make zero model calls. | PASS (N/A) |
| VII Evidence-based lessons | Out of scope. The package does not ingest lessons into prompts. | PASS (N/A) |
| VIII Traces | `.hi/runs/<run>/events.jsonl` holds structured events: stage, role, harness, model, verdict, hashes. Raw prompts and completions are OFF by default. Chain-of-thought is never captured. | PASS |
| IX Minimal model cost | Agents return compact status JSON (contract). Rework is bounded by the profile. Only flagged requirements are reworked and re-judged. | PASS |
| X Open-source-first | Everything is Apache-2.0 and stdlib. Optional tools are OSS. No commercial API is mandatory. MISRA, ISO and IEC texts are not included. | PASS |

## Project Structure

### Documentation (this feature)

```text
specs/023-high-integrity-vmodel-skills/
├── spec.md, plan.md, research.md, data-model.md, quickstart.md
├── contracts/                 # JSON Schemas + CLI/MCP contract
├── checklists/requirements.md
├── evaluation/                # seeded-defect corpus, A/B protocol (answer key kept separate)
├── evidence/                  # run evidence referenced by tasks and the impact report
└── tasks.md                   # /speckit-tasks
```

### Source Code (repository root)

```text
packages/forge-c-hi/                       # the APM package (install root)
├── apm.yml                                # name forge-c-hi, version, targets, dependencies.mcp (hi-gates MCP)
├── README.md                              # hackathon-mandated sections (FR-024)
├── LICENSE                                # Apache-2.0
├── .apm/
│   ├── instructions/hi-core.instructions.md   # non-negotiables (no invention, no certification claims, compact status)
│   ├── agents/                            # hi-author, hi-inspector, hi-release role agents
│   ├── hooks/hi-write-scope.json          # PreToolUse → sh locator → guard.py
│   └── skills/
│       ├── hi-intake/                     # project config, profile + level, input class, hashing, doc index
│       ├── hi-gates/                      # deterministic engine (scripts/hi.py, hi_mcp.py, guard.py, forge_hi/…)
│       │   └── references/{profiles,checklists,schemas}/
│       ├── hi-conductor/                  # stage loop driver with per-role harness commands
│       ├── hi-release/                    # release role + packager invocation
│       ├── hi-sys-req-{author,inspector}/
│       ├── hi-sys-arch-{author,inspector}/
│       ├── hi-sw-req-{author,inspector}/  # incl. driver mode (reference documents)
│       ├── hi-sw-arch-{author,inspector}/
│       ├── hi-sw-design-{author,inspector}/      # detailed design + unit construction
│       ├── hi-unit-verif-{author,inspector}/
│       ├── hi-sw-integ-verif-{author,inspector}/
│       ├── hi-sw-qual-{author,inspector}/
│       └── hi-sys-verif-{author,inspector}/      # system integration + system qualification
├── examples/
│   ├── watchdog-manager/                  # class (a): natural-language needs → SYS → SW (middleware)
│   └── iwdg-driver/                       # class (b): reference-manual citations (no vendor text)
├── tests/                                 # pytest: gates, profiles, guard, packager, MCP, conductor (fake harness)
└── tools/publish_check.py                 # content check before publish (FR-003, SC-008)
```

**Structure Decision**: one self-contained package folder. Users install it from a subdirectory of this repo. It
imports nothing from `factory/` or `tools/`: reused logic is ported, with attribution in the file header. The factory
code is not modified. Tests run inside the package, and existing suites run as regression.

## Phasing and schedule (deadline-driven)

| Milestone | Dates | Content | Exit evidence |
|---|---|---|---|
| M0 Foundations | Nov 22–23 | scaffold, APM spike as a test, neutral checklists, profile schema plus 4 profiles, contracts | `apm install` smoke test passes, schemas validate |
| M1 Requirements V (P1) | Nov 24–27 | gates (validate, trace, quality rules), guard, MCP, conductor, the SYS-REQ and SW-REQ skill pairs, watchdog-manager demo, packager | P1 demo READY with the Claude author and Codex inspector; tests green |
| M2 Driver + whole V + profiles | Nov 28–30 | doc index plus source resolution, IWDG demo linked to the middleware, the other 7 stage pairs (lower depth), profile switching | US2/US3/US4 acceptance runs recorded |
| M3 Impact + README | Dec 1–3 | seeded corpus, A/B runs, impact report, README, demo recording, local-model run (if R10 decided) | evidence/ with run IDs; README checklist |
| M4 Publish | Dec 4–5 | publish check, tag, clean-machine install, Capgemini submission pack | install link works from a clean consumer |
| Buffer | Dec 6–7 | fixes only | submission sent |

## Risks

- **R10 local-model location.** loop10 is frozen and Omniverse2 is excluded. Needs the owner (SC-003). Non-blocking for
  submission.
- **Capgemini publication route** is internal and unknown. The fallback is a GitHub tag link.
- **Hackathon legal/IP terms.** The owner must review them before publishing.
- **Harness drift.** Claude Code or Codex flag changes could break the conductor. Commands are config templates, and a
  fake-harness test covers the loop.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| Assisted-mode harnesses keep their built-in shell (Principle V scope) | The skills must run in ordinary coding agents (hackathon, FR-001). Removing shell is not portable across harnesses. | Shell-free operation needs harness-specific tool allow-lists. The conductor uses them where available (`claude -p --allowedTools`, Codex `--sandbox read-only`), while hook plus gate backstop keep write scope fail-closed at gate level. |
| Hook and MCP scripts reached through an sh locator | APM does not copy hook scripts, and the skill roots differ per target (R1). | Hard-coding `.claude/skills` breaks Codex, Copilot and Kiro. A PyPI package would add an external publish step. |

## Post-design Constitution re-check

After Phase 1 (data model and contracts), all rows still pass:

- **Provenance:** every workproduct has a `provenance` block (FR-012, Principle II).
- **Inspector output:** findings and verdicts only, which the conductor persists (Principle IV).
- **Agent output:** the agent-status contract keeps output compact (Principle IX).
- **Profiles:** the profile schema forbids normative text fields beyond `clause_ref` identifiers (Principle X).
