# Tasks: Peripheral onboarding as a factory pipeline stage (feature 016)

**Input**: [spec.md](spec.md), [plan.md](plan.md), [research.md](research.md), [data-model.md](data-model.md),
[contracts/](contracts/), [quickstart.md](quickstart.md)

**Rules**
- Tick a task only with `scripts/mark_task.py`, using run evidence from
  `python -m forge_factory.evidence_run --task OB-Tnnn -- <cmd>`.
- Record BLOCKED or NOT_RUN explicitly. Never tick on intent.
- Every factory change passes the CRE gate
  (`python -m forge_factory.reliability.promotion <cand> <base> --kind CHANGE --repo ../..`), frozen in an oracle
  commit, before any deploy.
- The owner signs every approval in their own terminal. The implementation engineer never signs.
- Paths are relative to the repository root. Python lives under `factory/python/forge_factory/` (abbreviated
  `ff/`), tests under `factory/python/tests/`.

**Format**: `- [ ] **OB-Tnnn** [P?] [USn?] description`. `[P]` means it can run in parallel (different files, no
open dependency).

## Phase 1: Setup

- [ ] **OB-T001** Create the package skeleton `ff/onboarding/__init__.py` with an argparse CLI
  `python -m forge_factory.onboarding {derive,summary,verify,prompts,check-model}`. Each subcommand exits 2 with
  `NOT_IMPLEMENTED` until its slice lands.
- [ ] **OB-T002** [P] Create `config/factory/onboarding/oracle-exceptions.yaml` (schema header, empty `exceptions:`
  list, each entry `{example, fact, hand_value, derived_value, explanation, reviewed_by}`) and a loader in
  `ff/onboarding/oracle.py`.
- [ ] **OB-T003** [P] Add a contract test, `tests/test_onboarding_contracts.py`. It validates
  `specs/016-peripheral-onboarding/contracts/*.example.json` against their schemas (Draft 2020-12), and checks that
  the four invalid cases are rejected: DERIVED without a source, NOT_DERIVED with a value, CONFLICT without an owner
  question, 4 attempts.

## Phase 2: Foundational (slice A: package model, hash, work-order schema)

These are blocking: every story writes or reads the package.

- [ ] **OB-T004** Implement `ff/onboarding/facts.py`:
  - `Fact`, `Source`, `AuthoredItem`, `Assumption` and `Gap` dataclasses following `data-model.md`;
  - `gaps_from(facts, items, assumptions)` (deterministic ids `GAP-OB-nnn` in fact-name order);
  - `canonical_hash(package)` (sorted keys, compact separators, excluding `sha256` and `created_at`);
  - `write_package(ws, package)` (validates against `contracts/onboarding-package.schema.json` before writing
    `onboarding/package.json`). (FR-005, FR-015)
- [ ] **OB-T005** [P] Write `tests/test_onboarding_facts.py`:
  - status/value/source rules;
  - gap derivation, including `blocks_approval` for CONFLICT, ASSUMPTION_UNCONFIRMED and MISSING_INPUT;
  - the hash is stable under key order and changes on any fact change;
  - writing an invalid package raises.
- [ ] **OB-T006** Extend `specs/008-brownfield-work-orders/contracts/brownfield-workorder.schema.json` and the work
  order loader in `ff/workorder.py`:
  - `target.instance`;
  - top-level `onboarding: true`;
  - `delivery.files`, `delivery.dependencies` and `configure` optional when `onboarding` is true;
  - an RM PDF input `{path, role: reference_manual, chapter, memory_map_pages}`.

  Work orders without `onboarding` must validate and prepare exactly as before.
- [ ] **OB-T007** [P] Write `tests/test_onboarding_workorder.py`. Every existing example under `examples/` still
  validates. A minimal onboarding work order (owner inputs only) validates. `onboarding: true` without
  `target.instance` validates, with the instance left NOT_DERIVED later.

**Checkpoint**: the full suite, `tests/spec/validate_design.py`, then the CRE gate for slice A.

## Phase 3: User Story 1 — deterministic onboarding facts (P1) 🎯 MVP

**Goal**: given the owner inputs, derive every derivable fact with its sources, with zero model calls and a
repeatable hash.

**Independent test**: `python -m forge_factory.onboarding derive examples/0012d-st-cube-usart-hal WO-OB-U --no-author`
gives the facts listed in quickstart §1. The regression oracle passes over the eleven ST delivery examples.

### Slice B: identity facts

- [ ] **OB-T008** [US1] In `ff/onboarding/identity.py`, implement `instance(wo)` from `target.instance`. When it is
  absent, scan the scope text for one instance token of the device header. None or several gives NOT_DERIVED with an
  owner question; a field that disagrees with the scope text gives CONFLICT.
- [ ] **OB-T009** [US1] In `ff/onboarding/identity.py`, implement `base_address(ws, instance)`:
  - evaluate the CMSIS `#define` chain (`<INST>_BASE_S`/`_NS` from the build's secure define, via
    `brownfield.cmsis` build settings) with file:line;
  - read the RM memory-map row for the instance with its page;
  - two values that differ give CONFLICT, and a missing page gives `mm_page` NOT_DERIVED.
- [ ] **OB-T010** [US1] In `ff/onboarding/identity.py`, implement:
  - `register_prefix` (the `<P>_TypeDef` the instance casts to, checked against the RM heading prefix);
  - `register_index`, reusing `assurance.hardware.index` with reset values and access types per field;
  - `driver_style` (LL / HAL_ON_LL / HAL_STANDALONE from the delivered files and the handle parameter);
  - `headers` and `function_prefix`, from the scope functions and their declaring headers.
- [ ] **OB-T011** [P] [US1] Write `tests/test_onboarding_identity.py`. On the real ST inputs (skip when absent):
  USART1 0x52001000 p.180, GPIOA 0x56020000 p.176, SPI1 0x52003000 p.180, TIM2 0x50000000 p.181, CRC 0x56024C00
  p.176. On synthetic headers: CONFLICT and NOT_DERIVED cases, and driver-style classification for `0008c`, `0009b`
  and `0014d`.

### Slice C: behaviour facts

- [ ] **OB-T012** [US1] In `ff/onboarding/behaviour.py`, implement on the `brownfield.scope` call graph of the scope
  functions:
  - `time_base` (reached calls to a framework `uint32_t f(void)` compared against a `Timeout` parameter);
  - `timeout_constants`;
  - `waits` (flag-polling loops, each classified as bounded by time base, by constant, or unbounded).
- [ ] **OB-T013** [US1] In `ff/onboarding/behaviour.py`, implement `undelivered_externals(ws)`. Compile the delivered
  sources and link them with an empty `main` on host (LLVM) and target (Arm GNU) using the existing `mcp/servers`
  build flags. Parse the undefined references, drop libc and compiler runtime, and attach each symbol's declaration
  (file:line) and call sites. Then mark `feeds` (the registers its result reaches by data flow inside the reached
  function), which propose an `Assumption`. (FR-007)
- [ ] **OB-T014** [US1] In `ff/onboarding/behaviour.py`, implement `instance_comparisons` (`Instance ==/!= X` and the
  macros that expand to them, in reached code) and `host_instance`: the scope instance when it is compared, else
  absent.
- [ ] **OB-T015** [US1] In `ff/onboarding/behaviour.py`, implement `file_map_and_modules(ws)`:
  - start from the scope module's `.c`/`.h` plus the framework headers;
  - iterate the existing intake build check (`brownfield.delivery`, `configure_hal_conf`) for at most 8 rounds,
    mapping each unknown type or implicit declaration to the vendor header that declares it, and that header to its
    `hal_conf` module;
  - result: `file_map` and `framework_modules`. A name that no vendor file declares gives MISSING_INPUT.
- [ ] **OB-T016** [P] [US1] Write `tests/test_onboarding_behaviour.py`:
  - USART HAL: time base `HAL_GetTick`, external `HAL_RCCEx_GetPeriphCLKFreq` feeding `USART_BRR`, host instance
    USART1, modules ⊇ {UART, DMA, RCC};
  - CRC HAL: no time base, no externals, modules {CRC};
  - TIM HAL: modules ⊇ {TIM, DMA};
  - a synthetic unbounded wait is classified unbounded;
  - an injected missing header gives MISSING_INPUT.
- [ ] **OB-T017** [US1] Wire `derive` in `ff/onboarding/__init__.py`. It runs after `workorder.prepare`'s intake (no
  intake check weakened, FR-002), converts PDF RM inputs with `docs.pdf2md` and writes their hash manifests (FR-003),
  assembles facts, assumptions and gaps, and writes `onboarding/package.json` with status READY_FOR_OWNER or BLOCKED.
  It emits factory events and asserts 0 model calls for the work order. (FR-002, FR-003, FR-022)
- [ ] **OB-T018** [P] [US1] Write `tests/test_onboarding_derive.py`. A second `derive` on the same inputs gives an
  identical `sha256`. Editing one delivered byte changes `inputs[].sha256` and the package hash. The event log of the
  derive has no model-call events. A timing assertion is recorded (not gating) for SC-004. (FR-006)

### Slice D: regression oracle

- [ ] **OB-T019** [US1] Implement `ff/onboarding/oracle.py` `compare(example)`. It derives the package for an
  existing example and compares, field by field, with `config/factory/peripherals/<id>.yaml` and the example's
  `workorder.json`: instance, base_address, mm_page, register_prefix, ll/hal headers, function prefixes,
  hal.time_base, hal.clock_stub symbol, hal.host_instance, delivery.files, dependencies and configure.hal_modules.
- [ ] **OB-T020** [US1] Write `tests/test_onboarding_oracle.py`, parametrised over `0008c-st-cube-rcc`,
  `0010c`–`0014c` and `0010d`–`0014d` (no ST IWDG delivery exists; correction 2026-10-27). Every difference must be listed in
  `oracle-exceptions.yaml` with an explanation; an unlisted difference fails. Review and commit each exception with
  its reason.

**Checkpoint (US1 done)**: quickstart §1 and §2 run with evidence, full suite, CRE gate. Tick OB-T008…OB-T020.

## Phase 4: User Story 2 — owner approval gates the ASPICE work (P1)

**Goal**: SWE.1 cannot start without an owner-signed approval of the current package hash.

**Independent test**: quickstart §3, both refusals and the accepted start.

### Slice E: derived profile and package-driven work orders

- [ ] **OB-T021** [US2] Implement `ff/onboarding/profile.py` `derived_profile(package, approval)`. It maps facts to
  the feature 009 profile fields (plus `derived_from {package, sha256, approval_id}`), adds `hal.clock_stub` and
  `hal.time_base` from confirmed assumptions and facts, and validates against
  `specs/009-peripheral-generic-iwdg/contracts/peripheral-profile.schema.json` (extended with `derived_from`).
- [ ] **OB-T022** [US2] In `ff/peripheral.py`, make `of_ws(ws)` return the approved package profile when the manifest
  has `onboarding.sha256` and `approval_id`. In `ff/workorder.py`, write the manifest `onboarding` block. Every phase
  gate record (`ff/inspection/engine.py` gate log) copies `onboarding.sha256` (FR-018).
- [ ] **OB-T023** [P] [US2] Write `tests/test_onboarding_profile.py`:
  - the derived USART profile validates;
  - `of_ws` prefers it only when it is approved;
  - a work order without `onboarding` gets the hand profile, and its built workflow is byte-identical to before
    (graph and prompts for `0012c` and `0014d`);
  - a gate record carries the package hash.

### Slice F: approval

- [ ] **OB-T024** [US2] Implement `ff/onboarding/approval.py`:
  - `summary(ws)` writes `onboarding/summary.md`: facts table with sources, authored items with verdicts,
    assumptions to confirm, gaps, and the exact signing command;
  - `verify(ws)` runs `ssh-keygen -Y verify -n forge-onboarding-approval` with `config/factory/afo-allowed-signers`
    and validates `contracts/onboarding-approval.schema.json`;
  - it refuses a stale `package_sha256`, a missing CONFLICT resolution, a missing assumption confirmation, an
    unlisted non-blocking gap, or REJECTED without a reason.

  Codes: `APPROVAL_OK`, `APPROVAL_STALE`, `APPROVAL_INCOMPLETE:<what>`, `APPROVAL_BAD_SIGNATURE`.
- [ ] **OB-T025** [US2] Implement invalidation: any input hash change on re-derive voids the approval
  (`approval.json` moved to `onboarding/void/` with the reason), and the manifest block is removed. (FR-017)
- [ ] **OB-T026** [P] [US2] Write `tests/test_onboarding_approval.py` with a throwaway test key and a test
  allowed-signers file (never the owner's key): signature OK, wrong namespace, wrong principal, stale hash, an open
  CONFLICT, an unconfirmed assumption, an unlisted gap, invalidation after an input edit.

### Slice G: AFO integration

- [ ] **OB-T027** [US2] In `ff/afo/queue.py`, add the states `ONBOARDING` (counted in `ACTIVE_STATES`) and
  `WAITING_OWNER_APPROVAL` (not active; TTL from `afo-policy.yaml` `onboarding.approval_ttl_s`, default 7 days). TTL
  expiry finalizes `BLOCKED: WAITING_OWNER_APPROVAL_TTL` with the onboarding package as the gap package. Follow the
  `WAITING_EXTERNAL_CHANGE` pattern.
- [ ] **OB-T028** [US2] In `ff/afo/dispatch.py` and `ff/afo/conductor.py`:
  - an order whose work order has `onboarding: true` runs `derive` (and the onboarding Fabro run when
    `package.authored` needs it);
  - on READY_FOR_OWNER it moves to `WAITING_OWNER_APPROVAL`;
  - each tick runs `approval.verify`. On `APPROVAL_OK` the SWE run is admitted; on REJECTED the order is BLOCKED
    with the reason; on an input change it goes back to ONBOARDING.
- [ ] **OB-T029** [US2] In `ff/workorder.py` and `ff/workflow/builder.py`, refuse to build or launch an SWE run for an
  onboarding work order without `APPROVAL_OK`, with the code `ONBOARDING_NOT_APPROVED`. The refusal is enforced
  outside AFO too (direct CLI runs). (FR-021)
- [ ] **OB-T030** [P] [US2] Write `tests/test_onboarding_afo.py`. These are state-machine tests with a fake launcher:
  ONBOARDING → WAITING_OWNER_APPROVAL → admitted after a verified approval; REJECTED → BLOCKED; TTL → BLOCKED;
  input change → ONBOARDING; `max_concurrent_runs` counts ONBOARDING; a direct launch without approval is refused.

**Checkpoint (US2 done)**: full suite, CRE gate. The deploy waits until US3 and US4 are ready for the acceptance.

## Phase 5: User Story 3 — prompts built from the package (P2)

**Goal**: no hand-written per-peripheral prompt text for package-driven work orders. Authored domain texts are gated
and inspected.

**Independent test**: quickstart §4 with 0 leftover findings for the four acceptance drivers.

### Slice H: generator and leftover check

- [ ] **OB-T031** [US3] Implement `ff/onboarding/texts.py`:
  - template sets `ll` and `st_hal`, holding the generic CRC entries of `config/factory/peripherals/crc.yaml`
    (`prompt_st_hal`) as templates with placeholders;
  - fill from facts: names, headers, handle type and `Init` fields from the delivered header, instance, base,
    page, time base, clock stubs, host instance;
  - authored slots: `requirement_example`, `failure_responses`, `contract_rule`, `dynamic_view`, `args_example`,
    `ut_example`, `ut_rule`, `integration`, `target_tests`, `target_model`, `query_example`;
  - every value carries `from: template:<id>|authored:<item>`.
- [ ] **OB-T032** [US3] In `ff/workflow/prompts.py` `peripheralize`, for a package-driven work order, take `t` only
  from `package.texts` and never from the profile's `prompt`/`prompt_st_hal`. Hand-onboarded work orders keep
  today's path unchanged. (FR-012)
- [ ] **OB-T033** [US3] Implement `ff/onboarding/leftovers.py` `check(ws)`. It builds every SWE.1–SWE.6 node's
  instruction with `workflow.builder` (the full node set, not a regex over the dot text) and flags:
  - identifiers of another registered peripheral prefix;
  - another layer's identifiers (`LL_`, `ll_*_regs`, `stm32n6xx_ll_` for HAL_STANDALONE);
  - registers and fields absent from `register_index`;
  - functions and types absent from the delivered headers.

  Codes `LEFTOVER:<node>:<token>`.
- [ ] **OB-T034** [P] [US3] Write `tests/test_onboarding_texts.py`:
  - the generated CRC HAL texts with authored slots stubbed from the existing CRC overlay pass the leftover check;
  - a planted `LL_USART_` in a USART HAL text is flagged;
  - a planted `CRC_CR` in a GPIO text is flagged;
  - an unknown field is flagged;
  - a hand-onboarded work order's prompts are unchanged.

### Slice J (text part): authored domain texts

- [ ] **OB-T035** [US3] Add the roles `onboard-text-author` and `onboard-text-inspector` to `config/factory/agents.yaml`
  (budgets, MCP ops: `forge-docs-mcp` read ops; `write_file` for the author) and render their SKILL.md with
  `ff/registry/skillgen.py` into `.fabro/skills/`. Add authz write prefixes in `ff/policy/authz.py`
  (`onboard-text-author`: `onboarding/texts.json` only; the inspector writes nothing).
- [ ] **OB-T036** [US3] Implement the text gate in `ff/onboarding/texts.py` `check_authored(ws)` (FR-010): every
  register and field is in `register_index`, every function, type and constant is declared by the delivered
  headers, and every expected value cites an RM page. Then the leftover check.
- [ ] **OB-T037** [US3] In `ff/workflow/builder.py`, implement the onboarding graph `onboarding.fabro`: a text author
  node → deterministic text gate → inspector → a bounded loop of at most 3 attempts → the item becomes a gap. The
  graph is emitted only for the slots the package needs. Validate it with Fabro's graph validation in
  `tests/test_onboarding_graph.py`. (FR-009, FR-022)

**Checkpoint (US3 done)**: full suite, CRE gate.

## Phase 6: User Story 4 — simulation model behind a gate (P3)

**Goal**: a model, existing or authored, is gated against the RM and runs the delivered code.

**Independent test**: quickstart §5 on the existing models; SC-007 held-out CRC authoring.

### Slice I: model gate

- [ ] **OB-T038** [US4] Add a `check_model` operation to `ff/mcp/servers/sim.py`. It runs four checks:
  - load (platform plus model);
  - reset values (Renode monitor reads of every `register_index` offset after reset, compared with the RM reset);
  - access types (r / rc_w1 / rc_w0 fields only);
  - smoke (a target image built from the delivered code with the derived file map, initialising the scope instance
    with default configuration, plus one query, which must reach the end marker).

  Fields listed in the model's `MODEL_LIMITS` are reported as limits, not failures. The result is
  `{verdict, findings, limits, tool, version, invocation_id}`.
- [ ] **OB-T039** [US4] In `ff/assurance/hardware.py` / `ff/assurance/target.py`, use the `check_model` result as the
  simulator limitation when a package exists, instead of `SIMULATOR_MODEL_NOT_COMPARABLE`. RCC's existing comparison
  is unchanged.
- [ ] **OB-T040** [P] [US4] Write `tests/test_onboarding_model_gate.py`. Run `check_model` on the existing GPIO, SPI,
  USART, TIM and CRC models (skip without Renode) and record the results. Any real mismatch found becomes either a
  model fix (its own CRE decision) or a declared `MODEL_LIMITS` entry, reviewed. A deliberately broken reset value is
  caught, and the IronPython-2.7-incompatible syntax of feature 015 is caught at load.

### Slice J (model part) and slice K

- [ ] **OB-T041** [US4] Add the roles `onboard-model-author` (MCP: `forge-docs-mcp` reads, `forge-sim-mcp check_model`,
  `write_file` under `onboarding/model/`) and `onboard-model-inspector` to `config/factory/agents.yaml`, with
  SKILL.md rendered, authz prefixes, and the onboarding-graph nodes (model author → `check_model` → inspector,
  bounded at 3).
- [ ] **OB-T042** [US4] When a model exists for the peripheral, the onboarding stage re-gates it (`reused: true`) and
  never authors one. When none exists, it authors one. Implement this in `ff/onboarding/__init__.py`.
- [ ] **OB-T043** [US4] Held-out authoring (SC-007). Run onboarding for `0014c` with the hand CRC model hidden (an
  onboarding option `--hide-model crc`, test-only, recorded in the package). Expected: an authored model passes
  `check_model` and the inspection, and the existing `0014c` target tests pass on it. Record the evidence under
  `evidence/v0.4/runs/OB-T043/`.

**Checkpoint (US4 done)**: full suite, CRE gate.

## Phase 7: User Story 5 — the four ST HAL drivers end to end (P2)

**Goal**: GPIO, SPI, USART and TIM ST HAL onboarded from owner inputs alone, approved by the owner, then run
SWE.1–SWE.6.

**Independent test**: the frozen record with packages, approvals, run ids and release packages; the SC-001 audit.

- [ ] **OB-T044** [US5] Create the acceptance work orders `examples/0010e-st-cube-gpio-hal-ob`,
  `0011e-st-cube-spi-hal-ob`, `0012e-st-cube-usart-hal-ob` and `0013e-st-cube-tim-hal-ob`. They hold owner inputs
  only: driver, target with `target.instance`, the RM chapter and memory-map inputs, delivery source, provenance and
  licence, FROZEN, scope (copied verbatim from the `00NNd` scope statements, which are owner scope text), budgets and
  `onboarding: true`. No `files`, `dependencies` or `configure`.
- [ ] **OB-T045** [US5] Add queue items and AFO launch manifests `config/factory/benchmark/afo/<p>-st-hal-ob.json`
  (model profile codex-claude), with the driver classes covered by the owner's authorization
  AUTH-AFO-PILOT-20261027. If a new class is needed, prepare an UNSIGNED authorization for the owner to sign.
  Never sign it.
- [ ] **OB-T046** [US5] Deploy (deploy pattern; cloud gateway disabled). Submit `BENCH-GPIO-ST-HAL-OB` and let it
  reach `WAITING_OWNER_APPROVAL`. Hand the owner `summary.md` and the signing command.
- [ ] **OB-T047** [US5] **Owner approval, GPIO**: the owner reviews `summary.md` for `BENCH-GPIO-ST-HAL-OB`, writes
  or approves `approval.json` (conflicts, assumptions, accepted gaps), and signs it in their own terminal. The
  implementation engineer verifies with `onboarding verify` and commits the signed copy to
  `evidence/easa/owner-decisions/` in an owner-decision commit.
- [ ] **OB-T048** [US5] Run `BENCH-GPIO-ST-HAL-OB` SWE.1–SWE.6 to READY_FOR_OFFLINE_REVIEW or BLOCKED with gaps. Fix
  any factory defect through the CRE process (registry → CAPA → reproducer → promotion) and retry with new request
  ids `-R<n>`.
- [ ] **OB-T049** [US5] Submit `BENCH-SPI-ST-HAL-OB` to `WAITING_OWNER_APPROVAL`.
- [ ] **OB-T050** [US5] **Owner approval, SPI** (as OB-T047; the owner signs).
- [ ] **OB-T051** [US5] Run `BENCH-SPI-ST-HAL-OB` to a release package (as OB-T048).
- [ ] **OB-T052** [US5] Submit `BENCH-USART-ST-HAL-OB` to `WAITING_OWNER_APPROVAL`. Expected assumption:
  `ASM-CLOCK-USART1` (kernel clock for `HAL_RCCEx_GetPeriphCLKFreq`).
- [ ] **OB-T053** [US5] **Owner approval, USART**, including the owner's confirmed kernel clock value (as OB-T047;
  the owner signs).
- [ ] **OB-T054** [US5] Run `BENCH-USART-ST-HAL-OB` to a release package (as OB-T048).
- [ ] **OB-T055** [US5] Submit `BENCH-TIM-ST-HAL-OB` to `WAITING_OWNER_APPROVAL`.
- [ ] **OB-T056** [US5] **Owner approval, TIM** (as OB-T047; the owner signs).
- [ ] **OB-T057** [US5] Run `BENCH-TIM-ST-HAL-OB` to a release package (as OB-T048).
- [ ] **OB-T058** [US5] Freeze the record `evidence/v0.4/benchmark/st-drivers-hal-ob/record.{json,md}`. Per attempt
  it holds: revision, input and package hashes, approval id, Fabro run ids, phase verdicts, package status and gaps,
  duration, tokens. Add a checker `evidence/v0.4/benchmark/st-drivers-hal-ob/ob_check.py` (inputs, outcome, SC-005:
  no gap caused by an onboarding fact).
- [ ] **OB-T059** [US5] SC-001 audit, scripted in `ob_check.py`: `git log` over `config/factory/peripherals/` and
  `examples/00NNe-*` shows no per-driver text added for the four drivers. Every prompt text of the four runs has
  `from` template or authored.
- [ ] **OB-T060** [US5] Owner review of the four release packages: the owner decides; the decisions are recorded in
  owner-decision records. Close feature 015 T065 by reference to OB-T058, through `mark_task.py` with this
  evidence.

## Phase 8: Polish and cross-cutting

- [ ] **OB-T061** AFO planner validator (follow-up from the CRC HAL run, `afo-plan-97c64dc37304a1b2`). In
  `ff/afo/planner.py` (plan validation), reject any plan whose `artifact_scope` or remedy creates or edits files
  under a FROZEN delivery's code directories (`software/ll/`, `software/hal/`, `software/src/`,
  `software/include/`). Also reject a plan whose stated remedy is to produce an output that a gate demands but the
  driver style does not have. Reason codes `PLAN_REJECTED:FROZEN_CODE_SCOPE` and `PLAN_REJECTED:STYLE_OUTPUT`. Also: in a FROZEN delivery, a phase STUCK on failing checks that are all reproduced by ESCALATED CODE defects (CRC HAL R2, `WO-AFO-071ffed673bf5df5-a1`: DEF-002/003/004 in ST's CRC HAL, e.g. the polynomial scan never tests bit 31) is not reworkable: reject REWORK plans with `PLAN_REJECTED:FROZEN_DEFECTS_NEED_OWNER` and finalize the order BLOCKED with the defects as gaps for the owner's disposition. Test
  it in `tests/test_afo_planner_frozen.py` with the recorded plan as a fixture. CRE gate.
- [ ] **OB-T062** [P] Record the local-model onboarding run as NOT_RUN in `evidence/v0.4/runs/OB-T062/` (reason: no
  qualified local profile; see feature 014). If a profile is qualified later, run quickstart §1–§4 on omniverse2 and
  replace the record.
- [ ] **OB-T063** [P] Write an ADR, `docs/adr/ADR-00NN-peripheral-onboarding-stage.md`: the two-run design and
  owner gate (Constitution III), the derived profile, the template generator versus the legacy hand texts, and the
  migration policy for hand-onboarded peripherals (owner choice, FR-019).
- [ ] **OB-T064** Run the full suite, `tests/spec/validate_design.py`, the provenance scan, `safec_bridge.static_check`
  and quickstart §1–§6 with evidence. Then open the PR to `main`. Do not merge without the owner's acceptance; use
  merge commits only.

## Dependencies and execution order

- **Phase 1 → Phase 2 → US1**: US1 is the MVP. US2 needs US1's package.
- **US3** needs US1 (facts) and US2 slice E (package-driven work orders). **US4 slice I** needs US1 (register index,
  file map). US3 and US4 can proceed in parallel.
- **US5** needs US1–US3 and US4 slice I (OB-T038–OB-T040, OB-T042). It does not need the held-out authoring
  (OB-T043).
- Per driver in US5: submit → owner approval → run. The four drivers go in sequence (one run at a time on loop10,
  `max_concurrent_runs = 1`).
- **OB-T061** is independent and can land any time after Phase 2. It should land before US5, because recovery
  plans happen in those runs.

## Parallel examples

- US1: OB-T011, OB-T016 and OB-T018 (tests) can be written in parallel once OB-T004 exists. OB-T008–OB-T010
  (identity) and OB-T012–OB-T015 (behaviour) touch different files.
- US2: OB-T023, OB-T026 and OB-T030 (tests) are parallel. OB-T024 (approval) and OB-T027 (AFO states) are in
  different modules.
- US3 and US4: OB-T031–OB-T034 (texts) run in parallel with OB-T038–OB-T040 (model gate).

## Implementation strategy

1. **MVP = US1.** Deterministic facts plus the regression oracle. On their own they replace the hand-derived part of
   every profile and expose fixed assumptions.
2. Add **US2**: from then on, ASPICE work can only start from owner-approved facts.
3. Add **US3** and US4's gate (slice I). Then run **US5** driver by driver, fixing factory defects through CRE.
4. US4's authoring (OB-T041–OB-T043) completes the "inputs only" goal for peripherals without a model.
