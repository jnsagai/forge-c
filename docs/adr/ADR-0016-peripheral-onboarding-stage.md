# ADR-0016: Peripheral onboarding as a factory stage

Status: accepted (2026-10-27) · Feature 016 · Tasks: OB-T001..OB-T034, OB-T038..OB-T040, OB-T042, OB-T061, OB-T063

## Context

Until feature 015, the implementation engineer onboarded every new peripheral and driver style by hand:
- the peripheral profile and about 30 prompt texts;
- the ST HAL prompt overlays;
- the work order's delivery file map and `hal_conf` modules;
- the facts the harnesses need (time base, kernel-clock stub, host instance).

The owner asked (2026-10-27) for this preparation to become part of the factory pipeline, so that a factory running
any model profile can work from the datasheet, the reference manual, the delivered code and the owner's scope alone.

## Decisions

1. **Three steps, owner gate between runs.**
   - A deterministic derivation runs with no model call. Every fact is DERIVED, NOT_DERIVED or CONFLICT, with
     sources.
   - Authored items come only where nothing can be derived.
   - The owner then signs an approval of the package hash, outside any Fabro run (Constitution III). The signature
     uses `ssh-keygen -Y sign -n forge-onboarding-approval` and is verified against the AFO allowed-signers file.
   - The factory never signs.
2. **The package carries a derived feature 009 profile.** A work order prepared from an approved package names
   `onboarded:<key>` as its peripheral. `peripheral.load` returns the approved profile, so every existing consumer
   (layer helpers, host device, scaffold, simulator, prompts) works unchanged. Hand-written profiles stay valid for
   hand-onboarded work orders (FR-019).
3. **Generated texts, not authored overlays.**
   - The prompt keys come from a template set per driver style, filled with facts, the owner's scope statements and
     the simulation model's own behaviour description.
   - Each value records its origin.
   - For ST's classic HAL no free text has to be authored.
   - A leftover check builds every SWE.1–SWE.6 instruction with the real builder and fails on names of another
     peripheral or layer, or names neither the package nor the delivered code declares.
4. **The model gate is independent of the model's code.**
   - Renode reads every RM register (reset values) and exercises read-only and rc_w0 access.
   - A smoke image of the delivered code runs on the model.
   - An existing model is reused and re-gated; its limits come from its own description and from `MODEL_LIMITS`.
   - The gate replaces `SIMULATOR_MODEL_NOT_COMPARABLE` for package-driven work orders.
5. **AFO gets no new queue states** (research R1 amendment).
   - The owner approves before submission, and AFO intake refuses an onboarding work order without a verified
     approval.
   - Packages are keyed by the work order's example, so every attempt of an order shares the approval.
   - `prepare` re-derives at every launch, so a changed input voids the approval.
   - The factory revision is recorded in the package but is not part of the approval subject.
6. **Recovery cannot rework a FROZEN delivery.** The planner validator refuses three kinds of plan:
   - plans whose scope reaches the delivered code;
   - plans answering a gate demand for a delivered-code output;
   - reworks of a phase whose failing tests reproduce escalated delivered-code defects. That outcome needs the
     owner's disposition.

## Consequences

- **The regression oracle:** the derivation reproduces the hand-written facts of all 11 ST delivery examples. Its 3
  reviewed differences are hand errors or engineer choices: the TIM LL instance chosen by the engineer, not the owner,
  and an over-included DMA module in the USART HAL map.
- **Real defects found in feature 015 models:**
  - GPIO's `SECCFGR`/`PRIVCFGR` reset values;
  - SPI's read-only CRC registers;
  - a host-test gap: the `IS_<P>_*_INSTANCE` macros compare the CMSIS aliases `<INST>_S`/`_NS`, which the host
    header now maps.
- **Migration:** migrating a hand-onboarded peripheral to the package-driven path is an owner choice. A driver style
  without a template set, today the register-level LL, cannot use the package-driven path until one is written.
- **Model authoring:** two opt-in role and MCP overlays preserve the canonical 20-role registry. A separate graph
  unrolls three author → deterministic model gate → independent inspector attempts, using the approved Codex/Claude
  profile. Only the model directory is author-writable. The gate freezes the exact inspected bytes; acceptance
  requires the inspector to cite that hash. Authored execution uses an offline filesystem/network namespace plus
  a restricted Python request language and output/time limits. Content-addressed accepted bundles are hash-checked
  on reuse, approval verification and target execution. Existing models retain their reuse path.
- **Evidence limit:** deterministic implementation checks do not establish the held-out CRC result. SC-007 is
  NOT_RUN while the approved Claude inspector is out of quota. A local-model onboarding run also remains NOT_RUN.
