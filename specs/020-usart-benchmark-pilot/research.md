# Research: USART benchmark pilot - SWE.1 the benchmark way

All facts below were read from the feature branch checkout (`factory/python/forge_factory` = F) on 2026-11-12.
File:line references are to that checkout.

## R1. Which SWE.1 path the pilot uses

- **Fact.** The structured SWE.1 author (`F/lrtx/swe1.py`) is LL-only and register-driven: one task per register
  group, requirement schema with `source_page`, `effects[]` and `verified_by` (`REQ_SCHEMA` 145-152,
  `additionalProperties: false`). Under the owner-lane profile, `phases_by_layer` gives structured phases only to LL;
  HAL and LL+HAL orders run SWE.1 as a native agent with the register-level prompt (`prompts.py:153-192`). The
  feature 018 two-phase inspection needs SWE.1 among the structured phases (`workorder.py:875-878`).
- **Decision.** A new structured author for functional-level SWE.1 (`F/lrtx/swe1_functional.py`), selected only by the
  order's SWE.1 level setting. For such orders SWE.1 is structured regardless of the profile's `phases_by_layer`
  (code-side rule keyed by the manifest), so the two-phase inspection applies.
- **Rationale.** Only a structured author gives deterministic validation, per-requirement splicing for phase 1 and
  reproducible assembly; the native path cannot be checked attribute by attribute. The owner profile is hash-pinned
  (`owner_supervised_development.py:76`) and cannot carry the switch.
- **Alternatives.** Extend `swe1.py` with a mode: rejected - its task model (register groups) and validators are
  register-specific through and through; a mode flag would touch every function and risk the register-level byte
  identity. Native agent with a new prompt: rejected - no deterministic per-requirement checks, no phase 1.

## R2. The SWE.1 level setting

- **Fact.** No manifest/layer/profile key switches the register-level page and inventory rules. The only switch is
  `manifest.register_contract == "rc-v1"` (`layer.py:63-68`), always stamped by `prepare` (`workorder.py:416`), and it
  also drives SWE.2/SWE.3 contract checks (`gate.py:154-165`). Resume compares `CONTRACT_FIELDS`
  (`brownfield/resume.py:30-33`); a key added only when set leaves existing orders unchanged.
- **Decision.** Work-order key `swe1: {level: "functional", template: "swe1-functional-v1"}` → manifest key
  `swe1_level` stamped **only when present**. For a functional order, `register_contract` is not stamped, the
  register-level SWE.1 validators never run, and SWE.2+ are refused with `SWE1_FUNCTIONAL_LATER_PHASES_NOT_YET` until
  the later feature defines them (the pilot's work orders stop after SWE.1).
- **Rationale.** Existing orders keep byte-identical manifests, graphs and checks (FR-013, SC-007). Refusing later
  phases explicitly is honest: register effects now belong to SWE.3, which is not designed yet.
- **Alternatives.** A profile key: impossible (pinned). Keeping `rc-v1` and skipping only the SWE.1 check: rejected -
  it would require `register_effects.json` at the presence gate (`engine.py:37-48`) and mislead SWE.2.

## R3. Where the governance step runs

- **Fact.** `prepare` is model-free; it copies inputs with sha into `manifest.inputs` and already renders generated
  inputs as listed inputs (`brownfield/interface` → `inputs/delivered-interface.json`, `workorder.py:367-373`). The
  delivery intake writes the delivered function scope (`brownfield/delivery.py:184-207`). Pre-launch refusals follow
  the INPUT_GAP pattern (`input_readiness.py`, `afo/line_orders.py:325-352`).
- **Decision.** Two parts.
  1. **Deterministic, in `prepare`** (model-free): the input register (from the order's inputs, each with role
     `requirement_source` or `implementation_under_analysis`), the delivered public API inventory (HAL from the
     delivery scope, LL from the delivered header), and its scope classification by the order's scope rule. Written as
     a listed, fingerprinted input `inputs/governance-inventory.json`. Missing scope rule or unclassifiable functions
     → INPUT_GAP before launch.
  2. **Model step, first node of the SWE.1 run**: actors, use cases (each naming the in-scope functions it exercises)
     and open points, as one structured task over the inventory; then a deterministic coverage check (every in-scope
     function and in-scope RM feature in a use case or an open point). Failure stops SWE.1 with the uncovered items
     named (FR-005). Output: `workproducts/SWE.1/governance/` (JSON + Markdown), versioned by fingerprint.
- **Rationale.** Use cases need judgement (a model); scope classification and coverage must be deterministic. Keeping
  the model out of `prepare` preserves its contract. Owner-provided use cases are merged as a declared input.
- **Alternatives.** All in `prepare` with a model call: rejected (breaks the model-free prepare). Onboarding `derive()`:
  rejected - it requires an owner-signed admit, and sign-offs are revoked.

## R4. The functional requirement object

- **Decision.** Per requirement: `key`, `title`, `statement`, `type` (functional | design_constraint |
  architectural), `precondition`, `origin_group` (use_case | out_of_context | hal_design_constraint | state_behaviour |
  awaiting_traceability), `links[]` (`kind` trace | derive, `input_id`, `locator`, `rationale` required for derive),
  `verification_method` (test | analysis | inspection | demonstration), `test_level` (unit | component | integration |
  qualification | not_testable), `use_cases[]`. Fixed by assembly, not by the model: `status` (draft), `asil` (QM),
  `cal` (0), `allocated_interface`/`allocated_operation` ("not applicable until SWE.2").
- **Deterministic validation** (per task and at the gate): all attributes present; group/link consistency (awaiting ⇔
  no links); every `input_id` exists in the input register with role `requirement_source`; no statement or link cites
  the delivered code; level rule (no register name, field name, register address or reset value from the RM index /
  CMSIS header; hex addresses refused); EARS conformance (as today); design-constraint requirements verified by
  inspection.
- **Rationale.** Mirrors the benchmark template (process only) while keeping the factory's EARS and ReqIF rules.

## R5. Assembly, markdown layout, ReqIF and matrices

- **Fact.** Parsers require the `**SWR-NNN**` line followed by `Source:` and `Verification:` lines (`review.py:309`,
  `swtrace.py:101-104,321-325`, `register_contract.py:30`). ReqIF (`inspection/reqif_export.py` `build_xml` 41-118)
  carries ForeignID, Text, EARS, Source; one relation type `verified-by`.
- **Decision.** Keep `SWR-NNN` IDs and the three leading lines (Source = the trace/derive locator list,
  Verification = method + criterion); append the new attributes as further indented lines after `Verification:`
  (precedent: owner obligations, `assurance/owner_obligations.py:151-170`), plus a machine file
  `workproducts/SWE.1/requirement_attributes.json`. ReqIF gains attribute definitions (Title, Type, Status, ASIL, CAL,
  Precondition, OriginGroup, VerificationMethod, TestLevel, AllocatedInterface, AllocatedOperation) and relation types
  `traces-to` and `derived-from` to SPEC-OBJECTs for the input register entries - only for functional orders.
- **Rationale.** No existing parser breaks; register-level orders keep byte-identical outputs.

## R6. Feature 018 two-phase inspection on functional requirements

- **Fact.** `swe1_quality.requirements()` reads `assembly.json` and task checkpoints by `key` and hashes the object;
  `iq_packet` hard-codes register wording; rework uses `swe1._req_schema`, `REGISTER_RULES`, `validate_group` and
  `self_check` (`swe1.py:1403-1467`).
- **Decision.** The functional author writes the same `assembly.json` shape. `swe1_quality` takes the level from the
  manifest and uses level-specific packet wording, schema and validators (functional variants live in
  `swe1_functional.py`); the criteria file is untouched (FR-022). Register-level packets stay byte-identical.

## R7. Launching the pilot without hand-written run inputs

- **Fact.** `derived_campaign()` makes ladder lineages ACTIVE with `LADDER_PHASES` and every other lineage ON_HOLD;
  there is no off-ladder ACTIVE option (`owner_supervised_development.py:159-187`).
- **Decision.** A new example `examples/0012u-st-cube-uart-module/` (one module, LL+HAL, FROZEN delivery of the HAL
  UART files and the LL USART header, the scope rule, the SWE.1 level setting, inputs including the interrupt mapping)
  and a new lineage `uart-module` in `LINEAGES`; a generic `PILOTS = {lineage_id: phases}` makes a pilot lineage
  ACTIVE with its own phases (here `["SWE.1"]`), outside the ladder and without `after` chaining. Driver class and
  any allowance/grant need are checked in the first task (UNVERIFIED today whether a new driver class needs a grant).
- **Rationale.** The line prepares and launches it like any lineage (feature 019 rule); the ladder is untouched.

## R8. Interrupt mapping input

- **Decision.** Extract the USART/UART interrupt lines from the reference manual's interrupt table into a new input
  `RM0486-rev4-interrupts-usart.md` with the same converter and manifest entry as the other RM extracts (sha in the
  inputs manifest; body in the line inputs cache, never committed). If the table cannot be found, the input register
  records it as an open point (spec assumption).

## R9. Benchmark comparison without benchmark content

- **Decision.** Benchmark metrics are computed by a small extractor run **outside the repository** on the private
  export and stored as numbers/category names in a private JSON (`/mnt/data/forge-c/model-service/private-benchmark/`,
  chmod 700). The factory's comparison tool (`F/benchmark/compare.py`) reads that JSON and our SWE.1 outputs and writes
  the side-by-side report (metrics only). A privacy test scans the repository for forbidden tokens given only as
  SHA-256 hashes (so the test itself does not contain the names).
- **Alternatives.** Committing the metrics JSON: acceptable only if it contains no names; kept private by default.

## R10. Decision log and way-of-working proposal

- **Decision.** `specs/020-usart-benchmark-pilot/decision-log.md` (append-only table: date, rule, decided by,
  rationale, evidence). The proposal (`way-of-working-proposal.md`) is assembled at the end by a deterministic script
  from the decision log and the comparison metrics; each rule row cites its log entry (SC-010).

## R11. Module-agnostic mechanisms

- **Decision.** Everything UART-specific is data in the example (inputs, components, scope rule, not-delivered list);
  the code reads the module, components and scope rule from the manifest. A second fixture module (a small synthetic
  peripheral in tests) is prepared with the same code to prove SC-009.
