# Tasks: Forge-C High-Integrity V-Model Skills (APM package)

**Input**: Design documents from `specs/023-high-integrity-vmodel-skills/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: The owner asked for tests before implementation for the gates, guard, packager, MCP server and conductor
(the conductor is tested against a fake harness). Write each test task first and watch it FAIL before implementing.

**Organization**: tasks follow the plan's milestones (M0–M4). Inside each milestone they are grouped by user story.

**Owner-gated**: tasks marked **[OWNER-GATED: …]** must not start until the owner decides. Record the decision in
`specs/023-high-integrity-vmodel-skills/evidence/owner-decisions.md`.

**Evidence rule (CLAUDE.md)**: tick a box only when the run evidence is stored under `evidence/`. Otherwise record
BLOCKED or NOT_RUN.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency on incomplete tasks)
- **[Story]**: US1–US7 from spec.md

## Path conventions

- **Package root**: `packages/forge-c-hi/`, written `PKG/` below.
- **Skills**: `PKG/.apm/skills/<skill>/`. The engine package is `PKG/.apm/skills/hi-gates/scripts/forge_hi/`, written
  `ENG/` below.
- **Tests**: `PKG/tests/`.
- **Feature docs**: `specs/023-high-integrity-vmodel-skills/`, written `FEAT/` below.

---

## Phase 1: Setup (M0, Nov 22–23)

**Purpose**: package skeleton plus a verified install path.

- [x] T001 Create the package skeleton: `PKG/apm.yml` (name `forge-c-hi`, version `0.1.0`, description, author, license Apache-2.0, `includes: auto`), `PKG/LICENSE` (Apache-2.0 copied from the repo root), and the folders `PKG/.apm/{skills,agents,instructions,hooks}`, `PKG/examples/`, `PKG/tests/`, `PKG/tools/`
- [x] T002 [P] Add the pytest configuration `PKG/pyproject.toml` (tool.pytest only, `testpaths=["tests"]`, no runtime dependencies) and the shared fixtures `PKG/tests/conftest.py`. The fixtures are `tmp_project` (a git-initialised temporary dir) and `skills_root` (path to `PKG/.apm/skills`)
- [x] T003 [P] Write an install smoke test, `PKG/tests/test_apm_install.py`. It is skipped when `apm` is not on PATH. It runs `apm init -y --target claude,codex` and `apm install <PKG>` in a temporary consumer and asserts that `.claude/skills/hi-gates/SKILL.md`, `.agents/skills/hi-gates/SKILL.md`, `.claude/settings.json` hooks, `.codex/hooks.json` and the `.mcp.json` entry `forge-c-hi` all exist, and that `apm audit` exits 0
- [x] T004 Record the tool and licence inventory in `FEAT/evidence/m0-tool-inventory.md`: apm-cli, Python, Claude Code, Codex CLI, uv, and the optional poppler, gcc and cppcheck versions, with the commands used. Also create `FEAT/evidence/owner-decisions.md`, listing the decisions already made on 2026-11-22: generic standards, per-role models, Claude author and GPT inspector, constitution v0.5.0, no Omniverse2

---

## Phase 2: Foundational (M0, blocks every user story)

**Purpose**: neutral process data, the profiles, the engine core and the guard.

### Tests first

- [x] T005 [P] Write the schema tests `PKG/tests/test_schemas.py`. Every `FEAT/contracts/*.schema.json` copy in `ENG/../../references/schemas/` validates against draft 2020-12. Valid and invalid fixtures for project, requirement-set, trace, finding, gate-result, agent-status and review-manifest are accepted or rejected as expected (fixtures in `PKG/tests/fixtures/`)
- [x] T006 [P] Write the profile tests `PKG/tests/test_profiles.py`:
  - each profile in `hi-gates/references/profiles/` validates against `profile.schema.json`;
  - every HI level used by an example is mapped;
  - no `clause_refs` entry contains a sentence;
  - `generic` is the default when `profile` is absent;
  - an unmapped level makes `load_profile` raise `ConfigError`
- [x] T007 [P] Write the minimal JSON-Schema validator tests `PKG/tests/test_jsonschema_lite.py`. They cover type, required, enum, const, pattern, min/max, items, additionalProperties, oneOf and if/then: exactly the keywords our contracts use
- [x] T008 [P] Write the guard tests `PKG/tests/test_guard.py`. They feed Claude-style and Codex-style PreToolUse stdin JSON for Write, Edit, MultiEdit and apply_patch. Expected results:
  - inside the role's scope: exit 0;
  - outside the scope: exit 2 with the reason on stderr;
  - no `.hi/active-role.json`: exit 0;
  - malformed stdin: exit 2 (fail-closed while a role is active)
- [x] T009 [P] Write the locator test `PKG/tests/test_locator.py`. The sh locator finds `hi-gates/scripts/<file>` under `.claude/skills`, `.agents/skills`, `.github/skills`, `.cursor/skills` and `.kiro/skills`, and exits 127 with a message when none is found

### Implementation

- [x] T010 Copy the contracts into the package as runtime schemas: `PKG/.apm/skills/hi-gates/references/schemas/*.schema.json`, identical to `FEAT/contracts/`. A test asserts byte equality
- [x] T011 Implement the stdlib schema validator `ENG/jsonschema_lite.py` (the keyword subset from T007). Make T005 and T007 pass
- [x] T012 Write the neutral stage catalogue `PKG/.apm/skills/hi-gates/references/stages.json`: the 10 stages, side, level, counterpart, author and inspector skill names, output paths, checklist id and default gates, as in data-model.md
- [x] T013 [P] Write the neutral requirement checklists:
  - `hi-gates/references/checklists/requirements-item.json`: IQ-01..IQ-12, each with id, title, pass criterion, typical defect, and a deterministic flag for the R4 subset;
  - `requirements-set.json`: SQ-01..SQ-10.

  Port the content from `docs/SWE1-REQUIREMENTS-QUALITY-GUIDELINE.md` on GitHub ref `origin/publish/omniverse2-campaign-20261111` (`git show`). Make the wording level-neutral (system and software). Put attribution in `_source`
- [x] T014 [P] Write the checklists for the other stages in `hi-gates/references/checklists/{sys-arch,sw-arch,sw-design,unit-verif,sw-integ,sw-qual,sys-verif}.json`. Neutralise `factory/checklists/v0.4/SWE.2.yaml`..`SWE.6.yaml` (ASPICE BP references move into the `aspice40` profile `clause_refs`). Write new SYS-ARCH and SYS-VERIF items
- [x] T015 [P] Write the profiles `hi-gates/references/profiles/{generic,iso26262,iec61508,aspice40,_template}.json`:
  - level maps: generic HI-0..4; ISO 26262 QM/ASIL A–D; IEC 61508 SIL 1–4 (HI-0 unmapped); ASPICE process-only;
  - vocabulary and clause identifiers only;
  - rigor per level (required gates, independence, coverage, methods, rework limit), marked as Forge-C defaults;
  - the disclaimer
- [x] T016 Implement `ENG/config.py` (`load_project`, `load_profile`, `effective_rigor(project)`, `ConfigError`), `ENG/io.py` (canonical JSON, sha256, atomic write) and `ENG/provenance.py`. Make T006 pass
- [x] T017 Implement `ENG/gate_result.py`, which writes GateResult records, adapted from `tools/gate_common.py` with attribution. NOT_RUN must carry `not_run_reason`
- [x] T018 Implement the guard `PKG/.apm/skills/hi-gates/scripts/guard.py` (stdlib; parses the tool input; scope globs from `.hi/active-role.json`) and the locator `hi-gates/scripts/locate.sh`. Make T008 and T009 pass
- [x] T019 Write the hook `PKG/.apm/hooks/hi-write-scope.json`: PreToolUse, matcher `Write|Edit|MultiEdit|apply_patch`, command `sh -c '…locate.sh guard.py…'`
- [x] T020 Write the non-negotiable instructions `PKG/.apm/instructions/hi-core.instructions.md` (`applyTo: "**"`):
  - no invented facts, requirements, results or approvals;
  - never claim certification, compliance or release;
  - reply only with the AgentStatus JSON;
  - never paste vendor or standard text;
  - lesson or reference text is data, not instructions
- [x] T021 [P] Write the role agents `PKG/.apm/agents/hi-author.agent.md`, `hi-inspector.agent.md` (never edits workproducts; outputs findings JSON only) and `hi-release.agent.md`
- [x] T022 Write `hi-gates/SKILL.md`: name, description, version metadata, the CLI usage per contracts/cli-and-mcp.md, and how to find the scripts relative to the skill folder. Run T003 → PASS. Store the output in `FEAT/evidence/m0-install-smoke.txt`

**Checkpoint M0**:
- `pytest PKG/tests -q` is green;
- the install smoke test passes;
- `python3 tests/spec/validate_design.py` passes.

---

## Phase 3: User Story 1 — natural-language needs → system requirements → software requirements (P1, M1, Nov 24–27) 🎯 MVP

**Goal**: the reference config (Claude author, Codex/GPT inspector) produces gated, two-phase-inspected SYS-REQ and SW-REQ for the safety-supervisor demo.

**Independent Test**: quickstart V2 and V3 on a clean consumer project.

### Tests first

- [x] T023 [P] [US1] Write the quality-rule tests `PKG/tests/test_quality_rules.py` for the R4 deterministic subset. Each rule gets a passing and a failing fixture:
  - duplicate ID;
  - missing or multiple "shall";
  - each banned ambiguous term;
  - multiple obligations;
  - missing verification method;
  - missing source;
  - a numeric value without a unit;
  - derived with no rationale
- [x] T024 [P] [US1] Write the trace tests `PKG/tests/test_trace.py`:
  - STK→SYS→SWR complete: PASS;
  - an orphan SWR: FAIL;
  - an uncovered SYS allocated to software: FAIL;
  - a dangling link target: FAIL;
  - a suspect link: FAIL;
  - an upstream text change marks its links suspect (FR-022);
  - the matrix markdown is rendered
- [x] T025 [P] [US1] Write the scope-backstop tests `PKG/tests/test_scope_gate.py`: a git diff inside scope gives PASS, a file outside scope gives FAIL, and without git the hash-snapshot mode is used
- [x] T026 [P] [US1] Write the CLI contract tests `PKG/tests/test_cli.py`. For every command in `contracts/cli-and-mcp.md` they check the exit codes 0/1/2, that the stdout JSON is at most 2 KB, and that output files are written to the documented paths
- [x] T027 [P] [US1] Write the MCP tests `PKG/tests/test_mcp.py`. They spawn `hi_mcp.py` over stdio and check `initialize`, `tools/list` (all tools from the contract) and `tools/call hi_trace_check`, which must give the same result as the CLI. A bad tool name gives a JSON-RPC error
- [x] T028 [P] [US1] Write the conductor tests `PKG/tests/test_conductor.py` with a **fake harness** (`PKG/tests/fake_harness.py`, which emits scripted author JSON and inspector findings). They cover:
  - the author → gate → item inspect → rework only flagged items, each alone → re-judge only reworked → set inspect → gate sequence;
  - unresolved findings are carried to the set phase;
  - rework-limit exhaustion gives BLOCKED;
  - the inspector command is run with read-only settings and its file writes are rejected;
  - `events.jsonl` has no raw prompt unless enabled;
  - same-model-family under `separate-model-family` gives an independence gap

### Implementation

- [x] T029 [US1] Implement `ENG/quality.py` (the R4 rules; banned-term list in `hi-gates/references/ambiguous-terms.json`). Make T023 pass
- [x] T030 [US1] Implement `ENG/trace.py`, ported from `tools/trace_gate.py` with attribution and moved to neutral link types and levels. Include the suspect-link propagation and render `hi/trace-matrix.md`. Make T024 pass
- [x] T031 [US1] Implement `ENG/scope.py` (the diff and snapshot backstop). Make T025 pass
- [x] T032 [US1] Implement the CLI `hi-gates/scripts/hi.py` and `ENG/cli.py` (`init`, `validate`, `quality`, `trace`, `scope`, `gate`, `status`, `role set`). `gate` runs the profile's required gates for the stage and level. Make T026 pass
- [x] T033 [US1] Implement the MCP server `hi-gates/scripts/hi_mcp.py` (stdlib JSON-RPC 2.0, stdio, shared `ENG/` functions). Declare it in `PKG/apm.yml` under `dependencies.mcp` (`registry: false`, `transport: stdio`, `command: sh`, `args` = the locator). Make T027 pass
- [x] T034 [US1] Implement the conductor `PKG/.apm/skills/hi-conductor/scripts/conduct.py`:
  - per-role argv templates from `.hi/project.json`;
  - prompt files assembled from the skill, the inputs and the findings;
  - the AgentStatus JSON parsed from the inspector's stdout;
  - the batched two-phase loop and the rework limit;
  - writes `.hi/active-role.json` and `.hi/runs/<id>/events.jsonl`.

  Make T028 pass
- [x] T035 [P] [US1] Write `hi-conductor/SKILL.md` and `hi-conductor/references/harness-presets.json`. The presets are `claude-code` (`claude -p` with the allowed-tools list), `codex` (`codex exec -s read-only` for the inspector, `-s workspace-write` for the author), `codex-oss-ollama` (`--oss --local-provider ollama`), `manual`, and the reference config (Claude author, GPT inspector)
- [x] T036 [P] [US1] Write the `hi-intake/SKILL.md` skill plus the `hi init` input-hashing flow: choose the profile and level (default generic and an explicit level), the input class and entry stage, and hash the inputs into `.hi/inputs.lock.json`. Warn about personal data or secrets in the inputs
- [x] T037 [P] [US1] Write `hi-sys-req-author/SKILL.md`. It covers:
  - the mission;
  - the inputs (needs and constraints);
  - the output `hi/sys-req/requirements.json` per `requirement-set.schema.json`;
  - the authoring pattern (one "shall", trigger, response, observable outcome, units);
  - derived-requirement rationale;
  - open points instead of invention;
  - the write scope;
  - the AgentStatus reply;
  - versioned metadata
- [x] T038 [P] [US1] Write `hi-sys-req-inspector/SKILL.md`. It covers:
  - phase `item` (judge each requirement against IQ-01..12 without touching the others);
  - phase `set` (SQ-01..10 plus the carried findings);
  - findings JSON per `finding.schema.json`;
  - read-only;
  - severity rules
- [x] T039 [P] [US1] Write `hi-sw-req-author/SKILL.md` (software level; allocation from SYS; middleware and application focus; the driver mode section is added in US2) and `hi-sw-req-inspector/SKILL.md`
- [x] T040 [P] [US1] Write the demo inputs for the **Safety Supervisor** (owner decision 2026-11-22: one real STM32N6 project carried down the whole V): `PKG/examples/safety-supervisor/needs/stakeholder-needs.md` with original natural-language needs (alive, deadline and program-flow supervision of cyclic tasks; IWDG/WWDG servicing only while healthy; CRC self-test of code and configuration at start-up and periodically; safe state and reset within stated times; fault reporting over USART; status pin), `needs/constraints.md` (target STM32N657X0, Cortex-M55, Renode simulation, peripherals IWDG/WWDG/CRC/TIM/USART/GPIO/RCC, no vendor text) and `hi-project.example.json` (generic, HI-2, reference role bindings)
- [ ] T041 [US1] Run the P1 demo with the reference config (Claude Code author, Codex/GPT inspector) on a clean consumer project per quickstart V2. Store the run directory, the events, the gate results and the trace matrix in `FEAT/evidence/us1-p1-demo/`. Report READY or BLOCKED honestly
- [ ] T042 [US1] Run the quickstart V3 negative cases (a deleted link, a forced NOT_RUN, an out-of-scope write) and store them in `FEAT/evidence/us1-negative/`

**Checkpoint**: US1 is demonstrable on its own. This is the MVP.

---

## Phase 4: User Story 5 — sealed offline review package (P2, M1)

**Goal**: READY_FOR_OFFLINE_REVIEW or BLOCKED packages with verified hashes, at any point.

**Independent Test**: quickstart V2 `hi seal` after the passing run and after a failing run. The manifest hashes verify.

- [x] T043 [P] [US5] Write the packager tests `PKG/tests/test_seal.py`. They check:
  - all required gates PASS plus no blocking findings plus no suspect links: READY;
  - each gap type (FAIL, NOT_RUN, a blocking open point, suspect, independence) gives BLOCKED with a listed gap;
  - the manifest validates against the review-manifest schema;
  - every sha256 matches;
  - the disclaimer is present;
  - `.hi/docs/*.index.json` is excluded;
  - a package is still produced when stages failed
- [x] T044 [US5] Implement `ENG/seal.py` and `hi seal`. Adapt the manifest and hash logic from `factory/release-manager/scripts/build_review_package.py`, with attribution. Render `findings.md` and `gates.md`, and produce `review.tar.gz` deterministically (sorted entries, fixed mtime). Make T043 pass
- [x] T045 [P] [US5] Write `hi-release/SKILL.md`. The release role summarises the gaps, never upgrades a status, refuses certification or release claims (and records the request as a finding), then calls `hi seal`
- [ ] T046 [US5] Seal the US1 evidence run and verify it with an independent hash re-check script, `PKG/.apm/skills/hi-release/scripts/verify_package.py` (shipped with the release skill so consumers have it). Store the result in `FEAT/evidence/us5-seal/`

**Checkpoint M1**: the US1 and US5 evidence exists, `pytest` is green, and the regression `python3 tests/spec/validate_design.py` passes.

---

## Phase 5: User Story 2 — reference manual or datasheet → driver requirements (P1, M2, Nov 28–30)

**Goal**: driver-mode requirements cite a resolvable `{doc_id, section, page}`. The middleware project links down to them.

**Independent Test**: quickstart V4.

- [x] T047 [P] [US2] Write the doc-index tests `PKG/tests/test_doc_index.py`. A generated tiny PDF fixture (built at test time; no vendor content) gives the expected sections and pages. Without poppler the result is NOT_RUN with a reason. An unresolvable citation makes the trace FAIL
- [x] T048 [US2] Implement `ENG/doc_index.py` and `hi doc-index` (`pdfinfo` and `pdftotext -layout`; section-heading detection with numbered-heading regexes; page ranges). Extend `ENG/trace.py` with document-source resolution. Make T047 pass
- [x] T049 [US2] Add the driver mode to `hi-sw-req-author/SKILL.md`:
  - out-of-context entry;
  - DRV ids;
  - every hardware claim cites a section and page;
  - no register, timing or reset facts without a source, otherwise an open point;
  - never quote the document.

  Add the matching inspector checks (source-faithful, IQ-02) to `hi-sw-req-inspector/SKILL.md`
- [x] T050 [P] [US2] Write the demo `PKG/examples/iwdg-driver/`: `scope.md` (the IWDG peripheral, citing a public STM32 reference manual by document id and revision only, with a download note and no text from it) and `hi-project.example.json` (reference_document, entry sw-req)
- [x] T051 [US2] Implement cross-project links (`links[]` in project.json; the trace gate loads the linked project's driver_interface items). Add tests to `PKG/tests/test_trace.py`
- [ ] T052 [US2] Run the driver demo with the reference config against the owner's local copy of the reference manual. Link the safety-supervisor SW-REQ to the IWDG DRV items. Store the evidence in `FEAT/evidence/us2-driver/`, including the index hash but not the index content
- [ ] T053 [US2] Run the US2-AS3 negative case (missing or unreadable document gives BLOCKED at intake) and store it in `FEAT/evidence/us2-negative/`

---

## Phase 6: User Story 3 — choose the standard, not the tool (P2, M2)

**Goal**: changing the profile or level only changes the configuration. Reports use the profile's terms.

**Independent Test**: quickstart V5.

- [x] T054 [P] [US3] Write the profile-switch tests `PKG/tests/test_profile_switch.py`:
  - the same workproducts under generic, iso26262 and iec61508 give each profile's required gates and level names in `gates.md` and the manifest;
  - the skills tree hash is unchanged;
  - an unmapped level is refused
- [x] T055 [US3] Implement the profile vocabulary rendering in the reports (`ENG/report.py`). Make T054 pass
- [x] T056 [P] [US3] Write the profile-authoring guide `hi-gates/references/profiles/README.md`: how to add DO-178C, EN 50716 or IEC 62304 from `_template.json`; the identifiers-only rule; how rigor values are justified
- [ ] T057 [US3] Run the demo gates under ISO 26262 HI-2 and IEC 61508 HI-2 and store the evidence in `FEAT/evidence/us3-profiles/`, including `git diff --stat` of the skills, which must be empty

---

## Phase 7: User Story 4 — the whole V, right side included (P2, M2)

**Goal**: every remaining stage has an author, an inspector and gates, and runs at least once on the demo.

**Independent Test**: each later stage produces a valid workproduct, traces to its counterpart, and records gate verdicts.

- [x] T058 [P] [US4] Write the workproduct-schema tests for architecture, design, test-spec and verification-result in `PKG/tests/test_vmodel_workproducts.py` (one minimal valid and one invalid fixture each)
- [x] T059 [US4] Add the schemas `hi-gates/references/schemas/{architecture,design,test-spec,verification-result}.schema.json`. Copy them back to `FEAT/contracts/` and extend the trace rules for `allocates`, `realises`, `implements` and `verifies`. Make T058 pass
- [x] T060 [P] [US4] Write the code-stage gates `ENG/code_gates.py` and their tests `PKG/tests/test_code_gates.py`. The gates are build (gcc or clang), static analysis (cppcheck) and coverage (gcov/gcovr). A missing tool gives NOT_RUN. Coverage is compared with the profile targets
- [x] T061 [P] [US4] Write the skill pairs `hi-sys-arch-{author,inspector}/SKILL.md`
- [x] T062 [P] [US4] Write the skill pairs `hi-sw-arch-{author,inspector}/SKILL.md`
- [x] T063 [P] [US4] Write the skill pairs `hi-sw-design-{author,inspector}/SKILL.md` (detailed design and unit construction in C; the write scope includes `src/`)
- [x] T064 [P] [US4] Write the skill pairs `hi-unit-verif-{author,inspector}/SKILL.md`
- [x] T065 [P] [US4] Write the skill pairs `hi-sw-integ-verif-{author,inspector}/SKILL.md`
- [x] T066 [P] [US4] Write the skill pairs `hi-sw-qual-{author,inspector}/SKILL.md`
- [x] T067 [P] [US4] Write the skill pairs `hi-sys-verif-{author,inspector}/SKILL.md` (system integration and system qualification)
- [ ] T068 [US4] Run each later stage once on the safety-supervisor demo with the reference config and store the evidence in `FEAT/evidence/us4-full-v/`. Record honestly any stage that ends BLOCKED or NOT_RUN

---

## Phase 8: User Story 7 — hackathon submission with measurable impact (P1, M3–M4, Dec 1–5)

**Goal**: a published package, the README, impact evidence, a demo and the submission pack.

**Independent Test**: someone new follows the README from a clean machine. Every number in the impact report links to stored evidence.

- [x] T069 [P] [US7] Write the publish-check tests `PKG/tests/test_publish_check.py`. Each violation class is detected:
  - PDF or binary documents;
  - denylisted private identifiers (private benchmark name, private host IPs, local home paths, the private data root);
  - email addresses;
  - quoted passages over 25 words that contain "shall" and are attributed to an external standard or vendor;
  - hidden Unicode (delegated to `apm audit`)
- [ ] T070 [US7] Implement `PKG/tools/publish_check.py`. Make T069 pass. Run it on `PKG/` and store the result in `FEAT/evidence/us7-publish-check.txt` (SC-008)
- [ ] T071 [P] [US7] Build the seeded-defect corpus in `FEAT/evaluation/seeded/requirements.json`: at least 20 defects across the IQ and SQ classes, injected into a copy of the demo requirements. Keep the answer key in `FEAT/evaluation/seeded/answer-key.json`, which is never shown to the inspector
- [ ] T072 [P] [US7] Write the A/B protocol `FEAT/evaluation/PROTOCOL.md` and the runner `FEAT/evaluation/run_eval.py`. The baseline arm is the same author model with a plain prompt. The with-package arm uses the full skills, gates and inspector. Metrics are per data-model EvaluationRun. The targets (SC-005 ≥80%, SC-006 ≥50%) are written down before running
- [ ] T073 [US7] Run the evaluation (at least 1 baseline and at least 1 with-package run, plus the seeded-detection run) with the reference config. Store it in `FEAT/evidence/eval/` and write `FEAT/evidence/impact-report.md` with honest results and limitations
- [ ] T074 [US7] Write `PKG/README.md` with every FR-024 section:
  - the problem;
  - the users;
  - install (APM) and run;
  - inputs, outputs and parameters;
  - supported models (any harness or model via role bindings; tested: Claude and GPT, local if T080 ran);
  - prerequisites;
  - the benefits, with links to the impact report;
  - the examples;
  - the limitations and the non-certification statement;
  - the Forge-C factory as the reference implementation
- [ ] T075 [US7] Record the demo (terminal capture of the P1 demo and the seal) and screenshots into `FEAT/evidence/demo/`. Link them from the README
- [ ] T076 [US7] Clean-machine validation: a fresh user account or container with no Forge-C checkout follows the README only, installing from the git link. Time the hands-on minutes (SC-001) and store them in `FEAT/evidence/us7-clean-install.md`
- [ ] T077 [US7] Tag the package release `forge-c-hi-v0.1.0`, push the branch and tag to GitHub, and verify `apm install jnsagai/forge-c/packages/forge-c-hi#forge-c-hi-v0.1.0` from a clean consumer. **[OWNER-DECIDED 2026-11-22: public GitHub push and tag authorized now; only after T083 regression is green]**
- [ ] T078 [US7] Publish to Capgemini's Agentic AI Artifacts repository. **[OWNER-DECIDED 2026-11-22: done at submission time; the owner supplies the Capgemini route or access then]**
- [ ] T079 [US7] Assemble the submission pack `FEAT/submission/`: the install link, README, impact report, demo, and the legal/IP acknowledgement declaring the package Apache-2.0. **[OWNER-DECIDED 2026-11-22: licence Apache-2.0; the owner submits personally; deadline 2026-12-07 23:59 CET]**

---

## Phase 9: User Story 6 — same skills on cloud and local models (P2, M3)

**Goal**: the P1 demo also completes on a local model, using only a role-binding change.

**Independent Test**: quickstart V2 with the `codex-oss-ollama` preset (or another local endpoint). Provenance shows the local model.

- [ ] T080 [US6] Run the P1 demo with a local-model role binding (`codex exec --oss --local-provider ollama -m <model>` for author and/or inspector) and store the evidence in `FEAT/evidence/us6-local/`. Report the metrics side by side with T041, with no claim of equivalence. **[OWNER-DECIDED 2026-11-22: run locally on loop10, as the last task of the feature]**

---

## Phase 10: Polish and cross-cutting

- [x] T081 [P] Version and metadata audit: every `SKILL.md` has `name` equal to its folder, a description with "use when" triggers, `metadata.version`, `metadata.stage`, `metadata.role` and `metadata.write_scope`. Covered by `PKG/tests/test_skills.py` (frontmatter, stage mapping, cited paths, read-only inspectors)
- [x] T082 [P] Make the instructions and skill texts state compact output (AgentStatus ≤2 KB) consistently. Add a test that each author or inspector skill references `agent-status.schema.json`
- [x] T083 Regression: run the full existing repo suites (`python3 tests/spec/validate_design.py` and the existing pytest targets that ran on main before this branch) and confirm no change in results. Store the result in `FEAT/evidence/regression.md` (identical results on main and branch; rerun before T077 if factory code changes)
- [x] T084 Update the root `README.md` and `website/` with a short "Portable skills package (feature 023)" section, and update the constitution follow-up (the ⚠ item in the Sync Impact Report). Evidence: website unit tests pass; the local `astro build` cannot run on this host (Node 20 < 22 required by Astro), so the page build is left to the site CI
- [ ] T085 Run `/speckit-analyze` for cross-artifact consistency. Fix the findings, then mark the feature tasks complete only where evidence exists

---

## Dependencies and execution order

- **Setup (T001–T004)** comes first.
- **Foundational (T005–T022)** blocks every story. Tests T005–T009 come before T010–T019.
- **US1 (T023–T042)** must follow Foundational. Tests T023–T028 come before T029–T034. T041 needs T029–T040.
- **US5 (T043–T046)** needs the US1 engine (T030 and T032). T046 needs T041.
- **US2 (T047–T053)** needs US1. T051 and T052 need the US1 demo project.
- **US3 (T054–T057)** needs the US1 engine and can run in parallel with US2.
- **US4 (T058–T068)** needs US1. The skill pairs T061–T067 are all [P].
- **US7 (T069–T079)**: T073 needs T071, T072 and US1. T074 needs T073. T077 is followed by T078 and then T079 (owner-gated).
- **US6 (T080)** runs last, locally on loop10 (owner 2026-11-22). It needs US1.
- **Polish (T081–T085)** comes after the stories. T083 must run before T077.

## Parallel examples

```text
Foundational tests:   T005, T006, T007, T008, T009   (separate test files)
Foundational data:    T013, T014, T015, T021          (separate reference files)
US1 tests:            T023, T024, T025, T026, T027, T028
US1 skills/demo:      T035, T036, T037, T038, T039, T040
US4 skill pairs:      T061 … T067
US7 prep:             T069, T071, T072
```

## Implementation strategy

1. **MVP = US1 plus US5 (end of M1, Nov 27).** One natural-language demo through SYS-REQ and SW-REQ, sealed. This alone is a valid hackathon submission.
2. **M2:** US2 (driver), then US3 (profiles) and US4 (whole V) in parallel.
3. **M3:** the evaluation and README (US7 T069–T076).
4. **M4:** the GitHub tag (T077), then the local-model run (T080, last), then the Capgemini publish and submission (T078, T079) by Dec 5, with Dec 6–7 as buffer.
5. **Cut order if late:** first reduce US4 depth (keep the skills but record stage runs as NOT_RUN), then US6. US7 and US1 are never cut.
