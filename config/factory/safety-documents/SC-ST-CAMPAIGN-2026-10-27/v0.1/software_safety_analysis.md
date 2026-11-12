# Software Safety Analysis — ST STM32CubeN6 LL drivers WWDG, RNG, LPTIM1 (delivered code, FROZEN)

| Field | Value |
|---|---|
| Document | SSA-STC-001, version 0.1 |
| Status | **DRAFT — for the owner's review, not reviewed, not approved** |
| Safety scopes | SC-WWDG-2026-10-27, SC-RNG-2026-10-27, SC-LPTIM-2026-10-27; target ASIL B for each (owner decision OD-2026-10-27-01) |
| Product | ST STM32CubeN6 v1.4.0 LL code (stm32n6xx-hal-driver v1.4.0, BSD-3-Clause), delivered FROZEN: `stm32n6xx_ll_wwdg.h` (`0016c-st-cube-wwdg`), `stm32n6xx_ll_rng.h` (`0017c-st-cube-rng`), `stm32n6xx_ll_lptim.h` (`0018c-st-cube-lptim`) |
| Basis | Work order inputs, source requirements hash per scope: WWDG `30ec84e960beee4bfff8515ee813ec6dffbdff3aedc22ba9d73faa1f37af1801`, RNG `fe6e9312cd4c04d9846170b9af1ca228d0c79c3c12da988a66f00a89578e3b96`, LPTIM1 `062a1ad94ec1edf8b880dc920b1351f6b5ff81ac7ab5ed9a9d57857b6c0d3012` |
| Analysed work products | None yet: the delivered code and the scope only. The first runs of the three scopes are the real work of the Feature 014 operation-24 campaign, which has not started (section 10) |
| Drafted by | Claude Opus 5.5 (Claude Code), 2026-10-27, from the delivered code, RM0486 Rev 4 and the factory records listed in section 12 |
| Responsible engineer | Jefferson Nascimento (owner) |

> Draft. It counts for a work order only after the owner reviews and signs it and its register entry is completed
> (config/factory/safety-documents/README.md). Any edit after signing, or a change to the work order inputs, un-signs
> it until it is re-reviewed. It records the drafter's analysis; it is not a safety approval or certification.

## 1. Purpose and scope

This document analyses how the delivered ST LL code of the three campaign drivers can fail, what each failure does at
the driver boundary, what the design and the factory verification will cover, and what is left to the integrating
system. It is written once for the product (one analysis for the three scopes, one section each) and applies to every
work order of a scope whose inputs match its basis hash.

The code is **delivered FROZEN**: the factory never changes it. A disagreement between the code and the requirements
becomes a finding for the owner, not a correction. The requirements are derived from RM0486 and the owner's scope
**before** the code enters the work order (SWE.1 roles cannot read the delivered files).

**In scope**: the functions named in each work order's delivery scope (WWDG 12, RNG 17, LPTIM1 21), all
`__STATIC_INLINE` register accessors on the CMSIS device structure (secure aliases: WWDG 0x50002C00, RNG 0x54020000,
LPTIM1 0x50002400; RM0486 pp.177 and 181).

**Out of scope**: the HAL, the LL init/deinit functions of the `.c` files, interrupt handlers, DMA, the other LPTIM
instances and every feature each scope excludes (listed in the work orders and the peripheral profiles).

## 2. Safety context — element developed out of context

No item definition, safety goal, technical safety requirement, hardware-software interface or allocated software
safety requirement exists for these drivers: `upstream/upstream-inputs.yaml` is an unfilled template, the HSI and the
allocation review are PENDING in each scope (`hsi_hash` and `allocation_review_ref` are null). The drivers are
therefore analysed as **components developed out of context**: this document states the safety requirements it
**assumes** (section 3) and the conditions the integrating system must guarantee (section 8). Where they do not hold
for a real system, this analysis does not apply.

Two of the three peripherals are typically used as, or inside, a **safety mechanism**: the WWDG supervises program
flow timing; the LPTIM can provide a time base for a monitor. The RNG is mainly a security function; its safety
relevance depends on the use (e.g. random test patterns, protocol nonces).

## 3. Assumed safety requirements

| ID | Assumed safety requirement | Drivers |
|---|---|---|
| ASR-01 | Each configuration function shall leave the addressed field with exactly the requested value and every other field of the register unchanged. | all |
| ASR-02 | No function shall write a register that its requirement does not name. | all |
| ASR-03 | Each status query shall report the state of exactly the named flag, without changing any register. | all |
| ASR-04 | Each flag clear shall clear exactly the named flag and no other. | all |
| ASR-05 | A counter refresh of the WWDG shall write exactly the given counter value and keep the watchdog active. | WWDG |
| ASR-06 | A random data read shall return the content of RNG_DR without modification. | RNG |
| ASR-07 | No function shall block: every wait is left to the caller, who bounds it. | all |
| ASR-08 | A change of the RNG clock error detection shall be applied with the conditioning reset RM0486 47.7.1 requires. | RNG |

## 4. Method

For each scope function the analysis applies the guide words omission, commission (wrong register or bits), lost
update, ignored write, stale read and wrong value to the register accesses of ST's code (read from the delivered
header; once runs exist, the factory's extracted register effects are in `workproducts/SWE.3/delivered_code_facts.json`
of each run). For each fault mode it states the effect at the driver boundary, the existing measure in the code or the
planned verification, and what remains for the integrator. Hardware faults of the peripheral itself are outside this
software analysis except where the software can detect them.

## 5. Fault modes common to the three drivers

| ID | Fault mode | Cause in the delivered code | Effect | Existing measure | Remaining |
|---|---|---|---|---|---|
| FM-C1 | Lost update of a shared configuration register | ST uses `MODIFY_REG`/`SET_BIT`/`CLEAR_BIT` (read-modify-write, not atomic) on WWDG_CR/CFR, RNG_CR, LPTIM_CR/CFGR/DIER/ARR | A concurrent writer (interrupt, other task, other core) loses its change | Requirement-based tests check preservation of other fields (single context) | AOU-01: one writer per register, or the caller serialises |
| FM-C2 | Invalid argument written | LL functions do not validate arguments | A value outside the field's encoding reaches reserved bits or selects an unintended mode | None in the code | AOU-02: the caller passes only the documented LL constants and values |
| FM-C3 | Write ignored by the hardware | RM write constraints (LPTIM_CFGR only while disabled; LPTIM_ARR/DIER only while enabled; RNG CED only with CONDRST), bus or access-right errors (TrustZone, RIF) | The configuration silently stays at the old value; no function reports it | Target tests on the behavioural models show the constraints that are modelled (LPTIM) | AOU-03: follow the RM call order; AOU-04: read back safety-relevant configuration |
| FM-C4 | Stale or wrong flag reported | A flag read races with the hardware setting/clearing it | The caller decides on an outdated state | Queries read the register once, no caching | AOU-05: the caller tolerates one-poll latency |
| FM-C5 | Unbounded wait | None in the LL (no loops in scope functions) | — | ASR-07 holds by construction | AOU-06: the caller bounds every polling loop (ARROK, DIEROK, DRDY, COUNTRST) |
| FM-C6 | Wrong instance | Functions take an instance pointer; nothing checks it | Another peripheral is configured | Static typing only | AOU-02 |

## 6. Driver sections

### 6.1 WWDG (`stm32n6xx_ll_wwdg.h`, 12 functions)

The WWDG is itself a **safety mechanism**: it resets the device when the counter is refreshed too late (T6 cleared)
or outside the window (refresh while T > W). Its failure is latent until the supervised software misbehaves.

| ID | Function(s) | Fault mode | Effect | Existing measure | Remaining |
|---|---|---|---|---|---|
| FM-WWDG-01 | Enable | Activation is set-only (WDGA cleared only by a reset, RM0486 60.6.1); there is no disable | Once active, every later timing error resets the device — intended | Requirement and tests state set-only behaviour; the model keeps WDGA | — |
| FM-WWDG-02 | SetCounter | `MODIFY_REG(CR, T, Counter)`: a value with T6 = 0 (below 0x40) resets the device at once; a refresh while T > W resets the device | Spurious reset, or the supervised timing is wrong | None in the code (FM-C2); the window/late reset is **not modelled** in the Renode model | AOU-WWDG-01: refresh only with values 0x40..0x7F and only inside the window; AOU-WWDG-02: verify the reset behaviour on silicon |
| FM-WWDG-03 | SetCounter | Refresh issued by a faulty task that runs while the supervised one is stuck | The watchdog is defeated | — | AOU-WWDG-03: refresh only from the point that proves the supervised program flow (e.g. after a sequence check) |
| FM-WWDG-04 | SetPrescaler, SetWindow | Wrong time base or window (FM-C1, FM-C2) | Too wide a window hides late execution; too narrow causes spurious resets | Tests check the written fields | AOU-04, AOU-WWDG-04: derive the time base and window from the PCLK frequency and the timing budget, check at start-up |
| FM-WWDG-05 | ClearFlag_EWKUP | `WRITE_REG(SR, ~EWIF)`: EWIF is cleared by writing 0, writing 1 has no effect (RM0486 60.6.3) — clears only EWIF | — | Conformance accepts the idiom when the requirement writes 0 to EWIF; model test | — |
| FM-WWDG-06 | EnableIT_EWKUP | EWI is set-only; the early wake-up interrupt handler is out of scope | A last action before reset depends on the integrator's handler | Scope statement | AOU-WWDG-05: the handler must not refresh blindly (that would defeat FM-WWDG-03) |
| FM-WWDG-07 | — | The WWDG bus clock (RCC) is outside this driver | A stopped clock stops the countdown: no reset, no supervision | — | AOU-WWDG-06: system-level check that the watchdog clock runs |

### 6.2 RNG (`stm32n6xx_ll_rng.h`, 17 functions)

| ID | Function(s) | Fault mode | Effect | Existing measure | Remaining |
|---|---|---|---|---|---|
| FM-RNG-01 | ReadRandData32 | Returns RNG_DR without checking DRDY, SECS or CECS | A read without data ready returns 0 or a stale value; after a seed error the value must not be used | Requirement states the plain read; the model returns 0 without data | AOU-RNG-01: read only after DRDY = 1 and SECS = 0 / CECS = 0; discard data on an error |
| FM-RNG-02 | ReadRandData32 | Two consecutive reads return the same value (hardware fault) | Weak or repeated random numbers | None in the code; the hardware health tests (RNG_HTCR, out of scope) | AOU-RNG-02: the application checks for repeated values where randomness matters |
| FM-RNG-03 | EnableClkErrorDetect, DisableClkErrorDetect | `MODIFY_REG(CR, CED|CONDRST, value|CONDRST)` then `CLEAR_BIT(CR, CONDRST)`: the conditioning reset discards pending data and clears RNG_SR | Data in flight is lost; a caller polling DRDY sees it drop | Requirement states the sequence (ASR-08); model test | AOU-RNG-03: change CED only before using the generator, wait for DRDY again |
| FM-RNG-04 | DisableClkErrorDetect | Clock error detection disabled (CED = 1) | A wrong RNG clock is not reported | Requirement and test | AOU-RNG-04: keep the detection enabled in safety-relevant use |
| FM-RNG-05 | ClearFlag_CEIS, ClearFlag_SEIS | `WRITE_REG(SR, ~flag)`: rc_w0, clears only the named flag (other bits written 1 have no effect) | — | Conformance and tests | — |
| FM-RNG-06 | — | Seed error recovery sequence, the NIST configuration, noise source and health test registers are out of scope | A seed error is reported but not recovered by these functions | Scope statement | AOU-RNG-05: the integrator implements the RM0486 seed error recovery |
| FM-RNG-07 | — | Entropy quality is not verifiable by the factory: the Renode model returns a deterministic sequence, not entropy | Statistical defects of the hardware output remain undetected | Model limit stated in the profile | AOU-RNG-06: entropy and health-test qualification on silicon if randomness is safety-relevant |

### 6.3 LPTIM1 (`stm32n6xx_ll_lptim.h`, 21 functions)

| ID | Function(s) | Fault mode | Effect | Existing measure | Remaining |
|---|---|---|---|---|---|
| FM-LPTIM-01 | SetPrescaler, SetUpdateMode | LPTIM_CFGR written while ENABLE = 1 is not allowed (RM0486 58.7.10, 58.4.13); the code does not check (FM-C3) | Time base unchanged or undefined | Requirement states the constraint; the model ignores such writes; target test | AOU-03: configure CFGR only while disabled |
| FM-LPTIM-02 | SetAutoReload, EnableIT_ARRM, DisableIT_ARRM | LPTIM_ARR and LPTIM_DIER only while enabled, and a new write only after ARROK / DIEROK (58.4.11); the code does not wait | A second write before ARROK/DIEROK is lost; the period or interrupt enable is not what the caller believes | Requirement states the constraint; queries of ARROK/DIEROK in scope; model sets them at once (latency not modelled) | AOU-LPTIM-01: poll ARROK / DIEROK (bounded) before the next write |
| FM-LPTIM-03 | StartCounter, ResetCounter | CNTSTRT/SNGSTRT/COUNTRST only while enabled; COUNTRST must read 0 before it is set again (58.7.11); `SET_BIT(CR, COUNTRST)` does not check | The counter does not start or does not reset | Requirement states the constraint; model honours ENABLE (3-clock synchronisation not modelled) | AOU-LPTIM-02: enable first; check COUNTRST = 0 before a new reset |
| FM-LPTIM-04 | GetCounter | One read of LPTIM_CNT; while running only two equal consecutive reads are reliable (58.7.14) | A wrong count is returned | Requirement states the single read | AOU-LPTIM-03: read twice until equal (bounded) |
| FM-LPTIM-05 | ClearFlag_ARRM, ClearFlag_ARROK, ClearFlag_DIEROK | `SET_BIT` on the write-only LPTIM_ICR: correct on the device because a read returns the reset value 0 (RM0486 1.2, register conventions input) | On a RAM host the read returns stale bits — a test artifact, not a code fault (as SSA-STB-001 SSA-FND-04 for SPI) | Profile guidance and the conventions input | — |
| FM-LPTIM-06 | SetUpdateMode (PRELOAD) | With PRELOAD = 1 a new ARR applies only at the end of the current period | The period keeps the old value for one period | Requirement and model (preload modelled) | AOU-LPTIM-04 |
| FM-LPTIM-07 | — | The kernel clock selection and enable (RCC) and the enable-to-ready latency are outside this driver / not modelled | A stopped or wrong clock stops or skews the time base without a report | Model limits stated in the profile | AOU-LPTIM-05: system-level clock monitoring |

## 7. Dependent-failure analysis

| ID | Dependency | Effect | Measure / remaining |
|---|---|---|---|
| DF-01 | Requirements, register contract, conformance oracle, Renode models and tests all derive from the same converted RM0486 text (chapters 47, 58, 60, memory map pp.177/181) | A conversion error or a misread register would be consistent everywhere and go undetected | TAA-STC-001 TAA-FND-06/-10: review against the original PDF, tests on silicon |
| DF-02 | The three drivers share the CMSIS device headers delivered with them | A wrong macro affects all | ST's headers are fingerprinted and FROZEN; the RM is the independent reference for field positions |
| DF-03 | A WWDG that supervises the program flow and an LPTIM that provides its time base share the clock tree | A clock fault can stop the supervised flow and its supervision together | System-level clock monitoring (AOU-WWDG-06, AOU-LPTIM-05) |
| DF-04 | All drivers depend on the RCC clock and reset configuration (outside these scopes; see SSA-RCC-001) | A clock fault affects every peripheral at once | System-level clock monitoring |
| DF-05 | In this campaign one local model family (Qwen) is expected to author requirements, design and tests **and** to inspect them (TAA-STC-001 section 3) | Common misunderstanding between author and inspector is more likely than with two model families | Deterministic gates and the delivered code as an independent artefact; human review; known inspector limits (KI-014-003) |

## 8. Assumptions of use (to be met by the integrating system)

| ID | Assumption |
|---|---|
| AOU-01 | Each peripheral register has one writer at a time, or the caller serialises all writers (interrupts, tasks, cores). |
| AOU-02 | The caller passes only the documented LL constants and values and a valid instance. |
| AOU-03 | Configuration functions are called in the order RM0486 requires (LPTIM_CFGR while disabled; LPTIM_ARR/DIER while enabled; RNG CED before using the generator). |
| AOU-04 | Safety-relevant configuration is read back after it is written. |
| AOU-05 | Decisions on status flags tolerate one-poll latency. |
| AOU-06 | Every polling loop on a status flag is bounded by the caller with a defined reaction on timeout. |
| AOU-WWDG-01..06 | Refresh values 0x40..0x7F inside the window only; reset behaviour verified on silicon; refresh only from the point that proves the program flow; time base and window derived from the clock and timing budget and checked at start-up; the early wake-up handler never refreshes blindly; the watchdog clock is monitored. |
| AOU-RNG-01..06 | Data read only after DRDY with no clock/seed error and discarded on an error; repeated values checked where randomness matters; CED changed only before use; clock error detection kept enabled; seed error recovery implemented by the integrator; entropy and health tests qualified on silicon where randomness is safety-relevant. |
| AOU-LPTIM-01..05 | ARROK / DIEROK polled (bounded) before the next ARR/DIER write; enabled before start/reset and COUNTRST = 0 checked; the counter read twice until equal while running; one period of delay accepted with preload; clock monitoring at system level. |

## 9. Findings

| ID | Finding | Proposed measure |
|---|---|---|
| SSA-FND-01 | No allocated software safety requirement, HSI or allocation review exists (section 2). | The owner provides the upstream inputs, or accepts the assumed requirements (Q-01). |
| SSA-FND-02 | ST's LL does not validate arguments (FM-C2) and reports no error from the configuration functions (FM-C3); it does not wait for ARROK/DIEROK/DRDY (FM-LPTIM-02, FM-RNG-01). | Accept with AOU-02..AOU-06 and the driver AOUs, or add a checking wrapper (outside the FROZEN code). |
| SSA-FND-03 | Read-modify-write on shared registers (FM-C1). | Accept with AOU-01. |
| SSA-FND-04 | The WWDG reset (late or out-of-window refresh) is not modelled in Renode; the factory can verify the register behaviour only, not that the watchdog resets the device. | Verify on silicon (AOU-WWDG-02). |
| SSA-FND-05 | Verification runs only on the host and on behavioural models written from the RM text by an AI agent; no silicon (DF-01). The RNG model produces a deterministic sequence, not entropy (FM-RNG-07). | Tests on silicon or model validation. |
| SSA-FND-06 | No run of these scopes exists yet: every statement on verification coverage is planned, not evidenced (section 10). | Re-review after the first campaign runs (Q-04). |

## 10. Evidence at drafting

| Driver | Work order | Phases | Package |
|---|---|---|---|
| WWDG, RNG, LPTIM1 | none yet — campaign orders not submitted | — | — |

Onboarding evidence only (Feature 014 branch): profiles, examples and peripheral tests (`test_peripheral_{wwdg,rng,lptim}.py`
pass against ST's real headers, including the register-effect extraction); both RM parsers read every in-scope
register with its access type; the three Renode models were loaded and exercised in Renode 1.17.0 (smoke test,
2026-10-27). These show the factory can process the inputs; they are not verification of the delivered code.

## 11. Open questions for the reviewer

| ID | Question |
|---|---|
| Q-01 | Do you accept ASR-01 to ASR-08 as the assumed safety requirements? |
| Q-02 | Do you accept the assumptions of use (section 8) as the integrator's obligations? |
| Q-03 | Should the findings stay open (listed in the package limitations), or be closed before use? |
| Q-04 | Do you sign before the first campaign runs complete (as for USART/GPIO/TIM in SSA-STB-001), or after? |
| Q-05 | Do you accept SSA-FND-04 (WWDG reset behaviour verified only on silicon, outside the factory)? |
| Q-06 | Is one analysis for the three scopes acceptable, or should each driver get its own document? |
| Q-07 | Is the RNG safety-relevant in your use case at all, or should its scope be QM despite OD-2026-10-27-01? |

## 12. Sources

Delivered headers (`$FORGE_DATA_ROOT/inputs/st/stm32n6xx-hal-driver-v1.4.0`, provenance.json; SHA-256 recorded per work
order in `configuration/delivery.json` once runs exist); RM0486 Rev 4 chapters 47, 58, 60, memory map pp.177/181,
register conventions p.156 (`examples/0016-wwdg-st`, `0017-rng-st`, `0018-lptim-st` and `0015-rm0486-conventions`
inputs-manifest SHA-256); `config/factory/peripherals/{wwdg,rng,lptim}.yaml`; `factory/sim/stm32n6/{wwdg,rng,lptim}_model.py`;
SSA-STB-001 v1.0 (method, SSA-FND-04 precedent); SSA-RCC-001 v1.1 (DF-04); OD-2026-10-27-01.

## 13. Review and signature (to be completed by the owner)

| Field | Value |
|---|---|
| Reviewed by (name, role) | |
| Reviewer's statement | |
| Answers to Q-01 to Q-07 | |
| Changes made during review | |
| Decision | ☐ Approved ☐ Approved with open findings (listed in the package limitations) ☐ Rejected |
| Date | |

Signing records the reviewer's engineering judgement on this analysis for the stated basis. It is not a safety
approval of an item, a release decision or a certification.
