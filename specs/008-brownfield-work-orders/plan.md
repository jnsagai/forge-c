# Implementation Plan: Brownfield Work Orders

**Branch**: `feat/008-brownfield-work-orders` | **Date**: 2026-10-20 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/008-brownfield-work-orders/spec.md`

## Summary

A brownfield work order is a greenfield work order plus a **delivery**: existing C files with their origin, licence,
fingerprints, a scope, and a code mode (FROZEN or FIX_ALLOWED). It reuses the SWE.1–SWE.6 workflow, agents, gates,
assurance, CRE and packaging, with these brownfield branches:

1. **Intake (deterministic, in `workorder.prepare`):**
   - validates the delivery: licence, origin, scope functions present, mode allowed by the licence;
   - fingerprints every file and stores the delivery content-addressed **outside** the workspace;
   - builds the in-scope code once in a scratch directory (build check).

   Any failure stops the work order before an agent runs.
2. **Requirements stay independent of the code:**
   - SWE.1 runs in a workspace that does not contain the delivered code.
   - A new deterministic node, `delivery_inject`, writes the delivered files into the workspace (read-only) only
     after the SWE.1 inspection gate has passed. It records the frozen SWE.1 baseline it followed.
   - Roles that author requirements are additionally denied read access to the delivered paths.
3. **Delivered code is protected by policy:**
   - The delivered paths become manifest-driven protected paths for every role in FROZEN mode.
   - In FIX_ALLOWED mode the SWE.3 fix author may write them only while a CODE defect is in fix.
   - A deterministic `verify_delivery` compares the fingerprints at SWE.3 verify, before verification, and at
     packaging. It produces the change report (FIX_ALLOWED).
4. **SWE.2 and SWE.3 describe the code as it is:**
   - The architecture and detailed design are recovered from the delivered code.
   - A side-car code trace map (`workproducts/SWE.3/code_trace_map.json`: function → unit → unit specs) replaces
     the Doxygen tags that frozen code cannot carry.
   - Deterministic checks compare the recovered work products with code facts: functions, files, fingerprints and
     register accesses.
   - Code generators (`swe3_regmap`, the LL and HAL authors) are removed from the brownfield chain.
5. **Conformance:**
   - A deterministic conformance check maps requirements → allocated functions → delivered code. Every gap becomes
     a conformance finding: no requirement, no code, or contradiction.
   - Test failures on delivered code become CODE defects. In FROZEN mode they are escalated to the owner (no
     rework loop); in FIX_ALLOWED mode the existing fix loop handles them, restricted to the defect's lines.
6. **Packaging:** the package carries the delivery record (origin, licence, fingerprints, mode), the conformance
   findings and, in FIX_ALLOWED mode, the change report. Any undispositioned finding or fingerprint mismatch keeps
   it BLOCKED.
7. **Safety drafts (US5):**
   - A brownfield safety step drafts the software safety analysis and the tool assurance assessment into
     `safety/drafts/`, marked unapproved.
   - The existing owner-signed document register is unchanged.
8. **ST pilot (US6):**
   - A vendor-style adapter: fingerprinted vendor dependency headers, a host device-header shim mapping `RCC` to
     RAM, a tick stub, an RCC set/clear register model in the simulator, and a CMSIS-style register-write scanner.
   - The pilot may end BLOCKED with every gap named (SC-006). Its value is the independent verification of vendor
     code.

Greenfield work orders are unchanged: every branch is keyed on the manifest `delivery` block, which greenfield
manifests do not have (FR-019).

## Technical Context

**Language/Version**:
- Python 3.13 (factory venv);
- C11 for the delivered code;
- host clang 19.1.7 and arm-none-eabi-gcc 10.3.1 (existing toolchain).

**Primary Dependencies**: existing only. The factory itself (Fabro workflow, MCP gate servers, inspection engine,
assurance, release finalize/packager), Renode 1.17, pytest. **New external inputs (pilot only):** ST
`stm32n6xx-hal-driver` v1.4.0 (BSD-3-Clause, already downloaded), ST `cmsis-device-n6` v1.4.0 (Apache-2.0) and
CMSIS 6 core headers (Apache-2.0). Each is fingerprinted, stored outside the repository and never executed.

**Storage**:
- **Delivery store:** `state/workorders/<wo>/delivered/`, content-addressed, read-only.
- **Workspace:** the manifest gets `delivery`, `code_mode` and `delivered` records.
- **Workspace work products:** `.forge-run/delivery/*.json` (intake, injection, verification, change report)
  and `workproducts/SWE.3/code_trace_map.json`.

**Testing**:
- pytest unit tests for intake, protection, verification, the trace map, conformance (including the five seeded
  mismatch kinds of SC-002), defect routing, packaging and the CMSIS adapter;
- an integration test that prepares a brownfield work order from the r170 LL delivery and drives the
  deterministic nodes;
- live runs: r170 LL in FROZEN mode, r164 HAL with a seeded defect in FIX_ALLOWED mode, and the ST pilot;
- the CRE CHANGE promotion gate, and the full regression for greenfield (SC-008).

**Target Platform**: Linux host; simulated Cortex-M55 (Renode) for target tests.

**Project Type**: extension of the factory CLI/workflow (`forge_factory` package).

**Performance Goals**: a brownfield LL run within 60 minutes (SC-007). Intake and deterministic nodes take seconds.

**Constraints**:
- deterministic gates decide; no model call in intake, injection, verification or conformance;
- the delivered code is never written by an agent in FROZEN mode;
- greenfield untouched;
- no ISO/MISRA text;
- open-source only.

**Scale/Scope**: deliveries up to tens of thousands of lines, of which a scope of tens of functions is analysed;
the excluded remainder is listed, not loaded.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | How this feature complies | Status |
|---|---|---|
| I. Safety and correctness precede optimization | Delivered code is judged against independently derived requirements; contradictions are findings that block. Hardware facts still come only from the baselined RM sections; vendor headers are inputs to be checked, not truth. | PASS |
| II. Evidence driven | Every delivered file, dependency and change is fingerprinted. Conformance and verification results come from deterministic checks and tool runs, never from agent replies. | PASS |
| III. External release authority | No approval inside the run. Findings against delivered code, deviations and FIX_ALLOWED selection are owner decisions; packages are offline review candidates or BLOCKED. | PASS |
| IV. AI roles require versioned SKILLs | No new AI role. Existing author/inspector roles get brownfield prompt variants. Their SKILL.md files gain a brownfield section, re-pinned in the skills lock. | PASS |
| V. AI tool calls use MCP | No new agent tool. Delivered-code checks are deterministic nodes and gate functions. Build/test servers get manifest-driven include dirs and defines, not agent-supplied ones. | PASS |
| VI. Model-free supervision | Intake, injection, verification and conformance make zero model calls. | PASS |
| VII. Evidence-based shared knowledge | Not affected. | N/A |
| VIII. Observable traces | Intake, injection, protection refusals and change reports are logged to the gate log and audit channel. | PASS |
| IX. Minimal model cost | FROZEN mode removes the code-writing nodes, so brownfield SWE.3 costs fewer tokens than greenfield. | PASS |
| X. Open-source-first | Vendor inputs are open-source (BSD-3-Clause, Apache-2.0), fingerprinted with their licences. No ISO or MISRA text is added. | PASS |
| Governance (protected policy) | The brownfield checklist variant (`factory/checklists/**`) and any release policy addition (`config/factory/*release*`) are protected paths. They are added as new versioned files in owner-decision commits (OD-2026-10-20-xx), never modified by a factory CHANGE candidate. Existing checklists and policies stay byte-identical. | PASS (by procedure) |

## Project Structure

### Documentation (this feature)

```text
specs/008-brownfield-work-orders/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── brownfield-workorder.schema.json     # the delivery block of a work order spec
│   ├── delivery-record.schema.json          # manifest delivery/delivered records and .forge-run/delivery/*.json
│   ├── code-trace-map.schema.json           # workproducts/SWE.3/code_trace_map.json
│   └── conformance-finding.schema.json      # conformance findings and the FIX_ALLOWED change report
└── tasks.md
```

### Source Code (repository root)

```text
factory/python/forge_factory/
├── brownfield/                 # NEW package
│   ├── __init__.py             # is_brownfield(manifest), code_mode(), delivered_paths()
│   ├── delivery.py             # spec validation, intake, fingerprints, delivery store, build check
│   ├── scope.py                # scope → delivered functions (C function/macro index), excluded list
│   ├── inject.py               # delivery_inject node: SWE.1 frozen check, write read-only, record
│   ├── verify.py               # verify_delivery: fingerprints, FIX_ALLOWED change report
│   ├── trace.py                # code_trace_map seeding and checking (replaces code tags)
│   ├── conformance.py          # requirement ↔ function conformance findings
│   └── cmsis.py                # vendor (CMSIS) adapter: host device shim, tick stub, write scanner (pilot)
├── workorder.py                # prepare(): delivery intake; manifest fields; resume guard
├── workflow/builder.py         # brownfield SWE.3 chain, delivery_inject node, safety draft node
├── workflow/prompts.py         # brownfield prompt variants (SWE.2/SWE.3 recover; SWE.1 unchanged)
├── policy/authz.py             # manifest-driven protected + read-denied delivered paths
├── inspection/engine.py        # brownfield checklist selection and deterministic item mapping
├── inspection/gate.py          # delivery_inject / verify steps; FROZEN CODE-defect escalation
├── inspection/defects.py       # escalation of CODE defects in FROZEN mode; owner disposition
├── inspection/swtrace.py       # code trace from the trace map in brownfield
├── inspection/implementation.py# brownfield existence + fingerprint check
├── mcp/servers/{build,tests,sim}.py  # manifest include dirs/defines (pilot)
└── release/finalize.py         # delivery record, findings, change report in the package
factory/checklists/v0.4-brownfield/   # NEW versioned checklist (owner-decision commit)
factory/sim/stm32n6/                  # RCC model: CSR/CCR set/clear, 8 KB window (pilot)
.fabro/skills/*/SKILL.md              # brownfield sections (re-pinned)
examples/0008a-rcc-ll-delivered/      # r170 LL as a delivery (FROZEN)
examples/0008b-rcc-hal-delivered/     # r164 HAL with a seeded defect (FIX_ALLOWED)
examples/0008c-st-cube-rcc/           # ST pilot (FROZEN)
factory/python/tests/test_brownfield_*.py
```

**Structure Decision**: a new `forge_factory.brownfield` package holds all new logic. Existing modules get small,
manifest-keyed hooks into it, so greenfield code paths keep their current behaviour and tests.

## Phases

| Phase | Content | Stories |
|---|---|---|
| A | Delivery model, intake, scope resolution, delivery store, build check, examples 0008a/b | US1 |
| B | SWE.1 isolation: delivery_inject node, read deny, SWE.1-frozen evidence | US2 |
| C | Protection and verify_delivery; FROZEN CODE-defect escalation; owner disposition of CODE findings | US3 |
| D | Brownfield SWE.2/SWE.3: prompts, chain, trace map, implementation/regmap/trace checks, brownfield checklist (owner decision) | US3 |
| E | Conformance check and the five seeded mismatch kinds; packaging of delivery records and findings | US2, US3 |
| F | FIX_ALLOWED: write window during IN_FIX, change report, out-of-scope refusal, regression rule | US4 |
| G | Safety drafts into `safety/drafts/` | US5 |
| H | Live validation: 0008a FROZEN run, 0008b FIX_ALLOWED run | SC-001..SC-004, SC-007 |
| I | ST pilot: vendor dependency inputs, CMSIS adapter, simulator set/clear model, pilot run | US6, SC-006 |
| J | Regression, CRE promotion, docs, PR | SC-008 |

## Complexity Tracking

| Item | Why needed | Simpler alternative rejected because |
|---|---|---|
| Delivery stored outside the workspace and injected after SWE.1 | FR-007 requires that the requirement author cannot read the code. Path deny alone is bypassable through grep roots and git history. | Copying the code at prepare time with a read deny leaves the code in the workspace's first commit and reachable by tree-walking tools. |
| Side-car code trace map | Frozen code cannot carry `@unit`/`@spec` tags. | Editing delivered code to add tags breaks FROZEN by definition. |
| Separate brownfield checklist version | Required checklist items cannot be marked not applicable. Code-generation items do not apply to delivered code. | Weakening the existing checklist would change greenfield gates (FR-019). |
