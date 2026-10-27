# Research: Peripheral onboarding as a factory pipeline stage

Each decision is grounded in the current code on `feat/016-peripheral-onboarding` (based on the ST HAL work of
feature 015, d9da03e) and in what the hand onboarding of feature 015 actually needed.

## R1. Where the stage runs, and the owner gate

**Decision.** Onboarding is its own unit of work, before the SWE run:

1. **Deterministic derivation.** Python, inside work-order preparation, after the delivery intake. It makes no
   model call.
2. **Onboarding run.** A separate Fabro run for the authored items, only when any are needed.
3. **Owner gate, between the two runs.** The owner signs an approval of the package hash. The SWE.1–SWE.6 run is
   launched only after that.

**Amendment (2026-10-27, during implementation).** AFO gets no new states. The owner approves the package before
the work order is submitted, and AFO intake refuses an onboarding work order without a verified approval. Packages
are keyed by the work order's example, so every attempt of an order shares the approval, and `prepare` re-derives the
package at every launch, so a changed input voids it. This keeps the feature 005 queue state machine unchanged (the
`ADMITTED` state has no edge to a waiting state, and the maintainer opens cases for `WAITING_EXTERNAL_CHANGE` orders,
which an approval wait must not trigger).

**Rationale.**
- Constitution III forbids a human approval gate inside a normal Fabro run. A gate between two runs is the same
  pattern as the AFO authorization (owner-signed, verified by the factory, not by an agent).
- Splitting the runs also lets the deterministic part be re-run and compared byte for byte (FR-006).

**Alternatives rejected.**
- *One Fabro run with a human node.* Violates III.
- *Onboarding as an SWE.0 phase inside the SWE run with no owner gate.* Violates FR-016.
- *Approval recorded by the implementation engineer on the owner's word,* as package reviews are today. That doesn't
  work for an unattended conductor, and it contradicts the standing rule that only the owner signs.

## R2. How the package reaches the existing factory

**Decision.**
- The package contains a **derived profile**: a document valid against the existing feature 009 peripheral-profile
  schema, extended with a `derived_from` block. It is stored with the work order (`onboarding/profile.json`), not in
  `config/factory/peripherals/`.
- `peripheral.of_ws(ws)` returns the approved package's profile when the manifest names one (`onboarding: {package,
  sha256}`). Otherwise it returns the hand-written profile, as today.
- Every existing consumer of the profile (layer helpers, cmsis host header, scaffold, simulator, prompts) works on
  package-driven work orders without changes.

**Rationale.**
- Feature 009 already routes every peripheral-specific question through the profile, so a profile-shaped package is
  the smallest change that reaches all consumers.
- FR-019 (existing peripherals unchanged) holds by construction.

**Alternatives rejected.**
- *Writing the derived profile into `config/factory/peripherals/`.* Mixes owner-approved per-work-order facts into
  shared factory configuration, and makes two work orders of the same peripheral interfere.
- *A new parallel facts API.* Every consumer would change.

## R3. Derivation method per fact

The method per fact (all deterministic), each recording `file:line` or `doc:page`:

| Fact | Method | Source |
|---|---|---|
| Instance | Owner scope names it: a new work-order field `target.instance`. Otherwise NOT_DERIVED. If the scope text and the field disagree: CONFLICT. | work order |
| Base address | CMSIS device header `<INSTANCE>_BASE_S`/`_NS` chain evaluated through `#define`s (the build's secure/non-secure define picks one). The RM memory-map table row for the instance is the second source. Disagreement: CONFLICT. | vendor header line; RM memory map page |
| Memory-map page | The page of the memory-map row above. | RM memory map |
| Register prefix | The `<P>_TypeDef` the instance macro casts to; checked against the RM register heading prefix. | device header; RM chapter |
| Register/field index | Existing parsers (`assurance.hardware.index`, `inspection.regmap.parse_section`). Reset values and access types are included. | RM chapter pages |
| Driver style | Delivered files: an LL header only → LL. HAL with a provided LL → factory HAL. HAL without LL whose functions take a `<P>_HandleTypeDef*` → standalone HAL. | delivered code |
| Function prefix and headers | The common prefix of the scope's functions; the headers that declare them. | delivered headers |
| Time base | Calls to `HAL_GetTick` (or any function declared `uint32_t f(void)` in the framework and used in a subtraction against a `Timeout` argument) reachable from the scope functions, using the existing scope call graph. | delivered source lines |
| Timeout constants | `#define <P>_*TIMEOUT*` used in reached code. | delivered headers |
| Undelivered externals | Link the delivered objects with an empty `main` on the host and target toolchains. Every undefined symbol that is not libc or compiler runtime is undelivered, together with its declaration and its call sites. | link log; declaration line |
| Values those externals feed | If an undelivered function's result reaches a register write (data flow inside the reached functions), it needs a **test-environment assumption** (R8). | source lines |
| Instance comparisons | Expressions `Instance == X` / `!= X` and macros expanding to them, in reached code. Every concrete instance named becomes a host-mapping fact; the scope's instance must be among them. | source lines |
| Framework modules and file map | Start from the scope module, then iterate the existing intake build check. Each "unknown type / implicit declaration" error is mapped to the vendor header that declares the name, and that header's module is added to `hal_conf`. The loop is bounded. Result: `delivery.files`, `delivery.dependencies` and `configure.hal_modules`. | build logs; vendor headers |
| Waits present | A loop in reached code whose exit depends on a register flag. Bounded by a time base, a constant, or unbounded. | source lines |

**Rationale.**
- Feature 015 needed exactly these facts by hand: USART needed `HAL_GetTick`, the `HAL_RCCEx_GetPeriphCLKFreq` stub,
  the `USART1` host mapping and the UART/DMA/RCC module list.
- Every one of them came from reading code or a link failure. The CRC run's SWE.3 block and the views workaround
  came from style facts that fixed assumptions had wrong.

**Alternatives rejected.**
- *Asking an AI role to fill the profile.* Non-repeatable, and it guesses (FR-005).
- *libclang-based semantic extraction.* A new dependency. The existing scope extractor already resolves the call
  graph, macros and branches the scope reaches.

## R4. Generic, package-driven prompts

**Decision.** A **text generator** builds the keys the prompts already consume, from the package facts:

- the feature 009 `prompt` keys;
- for a standalone HAL, the `prompt_st_hal` keys, plus its `replace` list.

How it builds them:
- One template set per driver style: register-level LL, standalone handle-based HAL. The factory-HAL-on-LL style
  keeps today's RCC/IWDG texts.
- The templates are filled from facts: names, headers, handle type, `Init` fields, instance, base address, page,
  time base, clock stubs, host instance.
- The few keys that need domain content are filled only from **authored items** (R6). Examples: a worked requirement
  example, the target-test scenarios with expected values, the simulator behaviour summary.
- For a package-driven work order, `peripheralize` reads the generated keys **only**. Hand-written profile prompt
  texts are never read for it.
- A deterministic **leftover check** runs on every built instruction, over the same node set the builder emits. It
  fails on:
  - an identifier of another peripheral (any registered prefix other than this one);
  - an identifier of another layer (`LL_`, `ll_*_regs`, `stm32n6xx_ll_` for a standalone HAL);
  - any register, field, function or type not in the package.

**Rationale.**
- The prompts' structure (steps, gates, JSON contracts) is generic already. What varies per peripheral is names and
  domain examples.
- Replacing the RCC text-substitution engine in one go would touch every existing work order. Generating its inputs
  keeps FR-019 and removes the hand-written part (FR-012).
- The CRC HAL overlay (about 40 hand entries) is the reference. Its generic entries become template text; its
  domain entries become authored items.

**Alternatives rejected.**
- *Rewriting `prompts.py` as pure templates now.* Larger blast radius; it can follow once every peripheral is
  package-driven.
- *AI-written overlays per work order.* The same leftover risk, moved into a model.

## R5. Model gates

**Decision.** A generic model gate runs in the simulator, so it doesn't depend on how the model is written:

- **Load.** The platform with the model loads, and a read of each register succeeds.
- **Reset values.** After reset, every RM register in the index reads its RM reset value at its offset. Registers or
  fields the model declares unmodelled (a `MODEL_LIMITS` list in the model) are listed as limitations instead.
- **Access types.** A write of all ones then all zeros to each read-only field leaves it unchanged. Write-1-to-clear
  flags are cleared by writing 1 when set. Only fields the RM types as `r`, `rc_w1` or `rc_w0` are exercised; the
  others are not touched.
- **Smoke.** A target program built from the delivered code with the derived file map runs to its end marker:
  initialisation of the scope instance with a default configuration, plus one query. The program comes from the
  package facts. The gate checks completion and absence of a simulator fault, not functional correctness.

The existing `SIMULATOR_MODEL_NOT_COMPARABLE` limitation for non-RCC peripherals (`assurance.hardware`) is replaced
by this gate's result whenever a package exists.

**Rationale.**
- Every lesson from feature 015's models was found only in live runs and would have been caught by load and smoke:
  the IronPython 2.7 incompatibility of the USART model, and the FPU NOCP fault.
- Reset and access checks enforce Constitution I ("never invent reset behavior") on authored models.

**Alternatives rejected.**
- *Static comparison of model source with the RM.* That's today's RCC-only approach, and it doesn't generalize.
- *Re-running the feature 015 LL target tests as the gate.* They're per peripheral and hand-written; they serve as
  the SC-007 held-out check, not as the gate.

## R6. Authored items: roles, skills, MCP

**Decision.** Four new roles in the onboarding run, each with a versioned SKILL.md:

| Role | Writes | Reads | Gate |
|---|---|---|---|
| `onboard-model-author` | `onboarding/model/<id>_model.py`, `.repl` | RM chapter sections, register index, derived facts | model gate (R5) |
| `onboard-model-inspector` | verdict only | model, RM chapter | n/a |
| `onboard-text-author` | `onboarding/texts.json` | RM chapter, delivered headers, facts | text checks (FR-010) + leftover check |
| `onboard-text-inspector` | verdict only | texts, RM chapter, headers | n/a |

The authors and inspectors are separate identities (IV). The MCP operations are existing `forge-docs-mcp` reads and
`write_file`, plus a new `forge-sim-mcp` operation `check_model`. Authz write prefixes restrict each author to its
path.

The loop is bounded: at most 3 author attempts per item. Then the item is a gap. The run uses the configured model
profile (FR-022).

**Rationale.**
- This reuses the feature 015 recovery-planner pattern: a Fabro run on the owner's login, MCP-only, least privilege.
- It reuses the phase author/inspector discipline.

**Alternatives rejected.**
- *A single onboarding author for everything.* Mixes privileges; the model needs simulator access, the texts don't.

## R7. Owner approval

**Decision.**
- Onboarding writes `onboarding/summary.md`, the review page, and `onboarding/package.json`, whose hash is the
  approval subject.
- The owner approves with
  `ssh-keygen -Y sign -f ~/.ssh/id_ed25519 -n forge-onboarding-approval` over an approval document
  (`contracts/onboarding-approval.schema.json`) that contains:
  - the package hash;
  - the resolution of every CONFLICT;
  - the confirmation of every test-environment assumption;
  - the decision (APPROVED or REJECTED) and a reason.
- The factory verifies the signature against the same allowed-signers file as the AFO authorization (`afo/authz.py`),
  in a new namespace.
- A copy of the signed approval goes to `evidence/easa/owner-decisions/` in an owner-decision commit.

**Rationale.**
- The signature is verifiable without trusting the implementation engineer.
- It reuses existing key material and verification code.
- It keeps "never sign for the owner" enforceable.

**Alternatives rejected.**
- *Unsigned owner-decision JSON.* An unattended conductor can't tell who wrote it.

## R8. Test-environment assumptions

**Decision.**
- When an undelivered function's result reaches a register write (R3), the package proposes an assumption: the name,
  the reason, the dependent registers, and a value field the owner must confirm in the approval.
- The value is proposed only if the inputs state one, for example a datasheet maximum kernel clock. Otherwise the
  field is empty and approval is refused until the owner fills it.
- Confirmed values become the clock-stub/time-base profile entries (`hal.clock_stub`) and limitations of every
  dependent result.

**Rationale.** The UART 64 MHz kernel clock of feature 015 was the implementation engineer's choice. It must become
the owner's (FR-007).

## R9. Instance as an owner input

**Decision.**
- The work-order schema (feature 008 brownfield contract) gains `target.instance`.
- `delivery.files`, `delivery.dependencies` and `configure` become **optional** for a package-driven work order:
  derived when absent, CONFLICT when present and different.
- The RM input may be the PDF with the chapter named (`role: reference_manual`, `chapter`, `memory_map_pages`).
  Onboarding converts it with `forge_factory.docs.pdf2md` and writes the hash manifest (FR-003). Already-converted
  markdown inputs with manifests are accepted unchanged.

**Rationale.**
- Feature 015 examples carry the file map and the module list by hand. They are exactly what derivation should
  produce.
- Keeping them accepted (and cross-checked) turns the existing examples into regression oracles (FR-020).

## R10. Regression oracle

**Decision.**
- A test derives the package facts for the existing examples:
  - `0008c` (RCC LL, ST);
  - `0010c`–`0014c` (ST LL);
  - `0010d`–`0014d` (ST HAL, hand-onboarded in feature 015).

  There is no ST IWDG delivery (`0009-iwdg-st` holds RM inputs only), and the factory-authored examples deliver no
  vendor code, so they are not oracle cases (correction 2026-10-27).
- It compares them with the hand-written profiles and work orders: instance, base address, page, prefix, headers,
  prefixes, time base, clock stub, host instance, file map, modules.
- Every known difference is listed in a reviewed exceptions file with its explanation. An unlisted difference fails.
- Factory-authored (greenfield) examples are out of scope: they have no delivered code.

## R11. Model profile and local models

**Decision.** The stage runs with whatever profile the work order uses. The acceptance runs on loop10 with Codex
authors and Claude inspectors. A local-model onboarding run is recorded NOT_RUN (spec assumption). The deterministic
part has no model dependency at all (SC-004).

## R12. Acceptance order and the CRC HAL baseline

**Decision.**
- The order is GPIO, then SPI, USART and TIM, the same queue as feature 015.
- The hand-onboarded CRC HAL run (`BENCH-CRC-ST-HAL`) is the comparison baseline once it reaches a terminal state on
  the deployed factory with the SWE.3 fix (d9da03e).
- The four acceptance work orders use new request ids, `BENCH-<P>-ST-HAL-OB`, so the feature 015 records stay
  separate.
