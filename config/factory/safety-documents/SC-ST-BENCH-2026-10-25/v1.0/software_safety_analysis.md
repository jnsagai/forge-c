# Software Safety Analysis — ST STM32CubeN6 LL drivers CRC, SPI1, USART1, GPIOA, TIM2 (delivered code, FROZEN)

| Field | Value |
|---|---|
| Document | SSA-STB-001, version 1.0 |
| Status | **DRAFT — for the owner's review, not reviewed, not approved** |
| Safety scopes | SC-CRC-2026-10-25, SC-SPI-2026-10-25, SC-USART-2026-10-25, SC-GPIO-2026-10-25, SC-TIM-2026-10-25; target ASIL B for each (owner decision OD-2026-10-25-02) |
| Product | ST STM32CubeN6 v1.4.0 LL code (stm32n6xx-hal-driver v1.4.0, BSD-3-Clause), delivered FROZEN: `stm32n6xx_ll_crc.h` (`0014c-st-cube-crc`), `stm32n6xx_ll_spi.h` (`0011c-st-cube-spi`), `stm32n6xx_ll_usart.h` (`0012c-st-cube-usart`), `stm32n6xx_ll_gpio.h` (`0010c-st-cube-gpio`), `stm32n6xx_ll_tim.h` (`0013c-st-cube-tim`) |
| Basis | Work order inputs, source requirements hash per scope: CRC `76d9347ef9a5d9e0e2f49a9c6c41f0fa0cbf52e8fe953ab433274f5ee1ba372a`, SPI `0700c04fa15af5fcdd4539d4de951da186d7d2e15f67bfa88819558b5a4949af`, USART `8a172ad502f3d75bcc0fcff7ac25ad586cc9e3bb0fd7f71df0a278cd28cecfc1`, GPIO `068be9376a6832b0da92eadd900f0db0a1ee5796520dcd263c5970c9b68e4d4e`, TIM `771f73af66c754cc43e54a35b761624cd389b640b123b0be233520d40b8f0283` |
| Analysed work products | CRC: `WO-AFO-eca972eb13bc60d1-a1` (CRC-R3, SWE.1–SWE.6 passed); SPI: `WO-AFO-7a6810a8baf9b9c4-a1` (SWE.1–SWE.6 passed), `WO-AFO-0756ac55b8ea81e6-a1` (SPI-R2, stopped at SWE.4, section 9); USART, GPIO, TIM: the delivered code and the scope only — their first runs were queued when this draft was written (section 10) |
| Drafted by | Claude Opus 5.5 (Claude Code), 2026-10-25, from the delivered code, RM0486 Rev 4 and the factory records listed in section 12 |
| Responsible engineer | Jefferson Nascimento (owner) |

> Draft for the owner's review (OD-2026-10-19-11). It counts for a work order only after the owner signs it and its
> register entries are completed; any later edit, or a change to the work order inputs, un-signs it. It records the
> reviewer's engineering judgement; it is not a safety approval or a certification.

## 1. Purpose and scope

This document analyses how the delivered ST LL code of the five benchmark drivers can fail, what each failure does
at the driver boundary, what the design and the verification already cover, and what is left to the integrating
system. It is written once for the product (one analysis for the five scopes, one section each) and applies to every
benchmark work order whose inputs match the basis hash of its scope.

The code is **delivered FROZEN**: the factory never changes it. A disagreement between the code and the requirements
becomes a finding for the owner, not a correction. The requirements are derived from RM0486 and the owner's scope
**before** the code enters the work order (SWE.1 roles cannot read the delivered files).

**In scope**: the functions named in each work order's delivery scope (CRC 10, SPI 22, USART 21, GPIO 15, TIM 22),
all `__STATIC_INLINE` register accessors on the CMSIS device structure (secure aliases: CRC 0x56024C00, SPI1
0x52003000, USART1 0x52001000, GPIOA 0x56020000, TIM2 0x50000000; RM0486 pp.176–181).

**Out of scope**: the HAL, the LL init/deinit functions of the `.c` files, interrupts, DMA, the other instances and
every feature each scope excludes (listed in the work orders).

## 2. Safety context — element developed out of context

No item definition, safety goal, technical safety requirement, hardware-software interface or allocated software
safety requirement exists for these drivers: `upstream/upstream-inputs.yaml` is an unfilled template, the HSI and the
allocation review are PENDING in each scope, and the runs record that no software safety requirement is allocated.
The drivers are therefore analysed as **components developed out of context**: this document states the safety
requirements it **assumes** (section 3) and the conditions the integrating system must guarantee (section 8). Where
they do not hold for a real system, this analysis does not apply.

## 3. Assumed safety requirements

| ID | Assumed safety requirement | Drivers |
|---|---|---|
| ASR-01 | Each configuration function shall leave the addressed field with exactly the requested value and every other field of the register unchanged. | all |
| ASR-02 | No function shall write a register that its requirement does not name. | all |
| ASR-03 | Each status query shall report the state of exactly the named flag, without changing any register. | all |
| ASR-04 | Each flag clear shall clear exactly the named flag and no other. | SPI, USART, TIM |
| ASR-05 | A data write shall transfer exactly the given value to the data register with the access width the hardware requires; a data read shall return the received value. | CRC, SPI, USART, GPIO |
| ASR-06 | The CRC computation configured by the driver shall equal the configured algorithm (polynomial, size, initial value, reversal) for every input. | CRC |
| ASR-07 | No function shall block: every wait is left to the caller, who bounds it. | all |
| ASR-08 | A pin set, reset or toggle shall change only the pins of the given mask. | GPIO |

## 4. Method

For each scope function the analysis applies the guide words omission, commission (wrong register or bits), lost
update, ignored write, stale read and wrong value to the register accesses of ST's code (read from the delivered
header; the factory's extracted register effects are in `workproducts/SWE.3/delivered_code_facts.json` of each run).
For each fault mode it states the effect at the driver boundary, the existing measure in the code or the
verification, and what remains for the integrator. Hardware faults of the peripheral itself are outside this
software analysis except where the software can detect them.

## 5. Fault modes common to the five drivers

| ID | Fault mode | Cause in the delivered code | Effect | Existing measure | Remaining |
|---|---|---|---|---|---|
| FM-C1 | Lost update of a shared configuration register | ST uses `MODIFY_REG` (read-modify-write, not atomic) for every multi-field register, except `ATOMIC_MODIFY_REG` in `LL_USART_SetTransferDirection` | A concurrent writer (interrupt, other task, other core) loses its change | Requirement-based tests check preservation of other fields (single context) | AOU-01: one writer per register, or the caller serialises |
| FM-C2 | Invalid argument written | LL functions do not validate arguments (no `assert_param` in the LL accessors) | A value outside the field's encoding reaches reserved bits or selects a reserved mode | None in the code | AOU-02: the caller passes only the documented LL constants |
| FM-C3 | Write ignored by the hardware | Write protection while enabled (SPI CFG1/CFG2 with SPE = 1, USART CR2/BRR/PRESC and the locked CR1 fields with UE = 1), bus or access-right errors (TrustZone, RIF) | The configuration silently stays at the old value; no function reports it | Target tests (Renode) show the ignored write for SPI and USART | AOU-03: configure only while disabled; AOU-04: read back safety-relevant configuration |
| FM-C4 | Stale or wrong flag reported | A flag read races with the hardware setting/clearing it | The caller decides on an outdated state | Queries read the register once, no caching | AOU-05: the caller tolerates one-poll latency |
| FM-C5 | Unbounded wait | None in the LL (no loops in scope functions) | — | ASR-07 holds by construction | AOU-06: the caller bounds every polling loop |
| FM-C6 | Wrong instance | Functions take an instance pointer; nothing checks it | Another peripheral is configured | Static typing only | AOU-02 |

## 6. Driver sections

### 6.1 CRC (`stm32n6xx_ll_crc.h`, 10 functions)

The CRC unit is itself typically a **safety mechanism** (integrity of memory or messages). Its failure is latent
unless the result is compared against an independently computed value.

| ID | Function(s) | Fault mode | Effect | Existing measure | Remaining |
|---|---|---|---|---|---|
| FM-CRC-01 | SetPolynomialSize, SetPolynomialCoef, SetInitialData, Set{Input,Output}DataReverseMode | Wrong configuration (FM-C1, FM-C2, FM-C3) | Every CRC computed is wrong in a consistent way; if sender and checker use the same configuration code, a corruption can still be detected but a wrong algorithm is not | CRC-R3: unit tests, integration tests and 14 Robot tests on the behavioural model (e.g. CRC-32 of 0x12345678 = 0xDF8A8A2B), all requirements verified | AOU-CRC-01: check the configured algorithm against a known-answer value at start-up |
| FM-CRC-02 | Set{Input,Output}DataReverseMode | Reversal mode and reversal type are one field pair in ST's code (`REV_IN` with `RTYPE_IN`) | A caller passing only the reversal bits clears the type | Scope and requirements follow ST's coupling (corrected after CRC r1) | — |
| FM-CRC-03 | ResetCRCCalculationUnit, FeedData32, ReadData32 | Interleaved use by two contexts | Two computations mix; the result belongs to neither | None in the code | AOU-CRC-02: exclusive use of the unit per computation |
| FM-CRC-04 | FeedData32 | Only 32-bit feeds are in scope | Byte/half-word data must be padded by the caller | Scope statement | AOU-CRC-03 |
| FM-CRC-05 | Write_IDR, Read_IDR | Independent data register used as scratch | No effect on the computation | Tests | — |

### 6.2 SPI1 (`stm32n6xx_ll_spi.h`, 22 functions)

| ID | Function(s) | Fault mode | Effect | Existing measure | Remaining |
|---|---|---|---|---|---|
| FM-SPI-01 | SetMode, SetClockPhase/Polarity, SetTransferBitOrder, SetBaudRatePrescaler, SetDataWidth, SetFIFOThreshold, SetNSSMode | Configuration while SPE = 1 is ignored (CFG1/CFG2 write-protected, RM0486 67.11.3/67.11.4) — FM-C3 | Wrong clock mode, speed or frame size; data is shifted with the old settings | Target test shows the protection on the model | AOU-03, AOU-04 |
| FM-SPI-02 | SetBaudRatePrescaler, SetNSSMode | Coupled fields (MBR with BPASS, SSM with SSOE) set by one value | A caller-composed value outside the LL constants sets an unintended combination | Requirements and tests follow the coupling | AOU-02 |
| FM-SPI-03 | ClearFlag_EOT, ClearFlag_OVR | `SET_BIT` on the write-only SPI_IFCR: correct on the device because a read returns the reset value 0 (RM0486 p.156) | On a RAM host the read returns stale bits — a test artifact, not a code fault (section 9) | Profile guidance and the conventions input since db6c68e | — |
| FM-SPI-04 | TransmitData8, ReceiveData8 | 8-bit access through a cast; 16/32-bit frames out of scope | Larger frames would need other functions | Tests on host and model | AOU-SPI-01 |
| FM-SPI-05 | IsActiveFlag_OVR | Overrun loses received frames | Data loss is reported only through the flag | Target overrun test on the model | AOU-SPI-02: the caller checks OVR and handles lost data; SPI CRC (out of scope) or an end-to-end check protects the data |

### 6.3 USART1 (`stm32n6xx_ll_usart.h`, 21 functions)

| ID | Function(s) | Fault mode | Effect | Existing measure | Remaining |
|---|---|---|---|---|---|
| FM-USART-01 | SetParity, SetDataWidth, SetStopBitsLength, SetOverSampling, SetTransferBitOrder, SetPrescaler, SetBaudRate | Write ignored while UE = 1 (RM0486 65.8) — FM-C3 | Frames on the line differ from the intended format or rate | Model enforces the protection; target tests | AOU-03, AOU-04 |
| FM-USART-02 | SetBaudRate | BRR is computed by the delivered code (clock, prescaler table, oversampling, rounding); a prescaler value above DIV256 or a baud rate of 0 writes nothing and reports nothing | Wrong or unchanged baud rate, silently | Not decidable by static conformance (DEFERRED_TO_TESTS); requirement-based unit tests for oversampling 16 and 8 | AOU-USART-01: the caller passes the true kernel clock and validates the arguments; AOU-04 |
| FM-USART-03 | SetTransferDirection | `ATOMIC_MODIFY_REG` (LDREX/STREX) — protected against FM-C1 for this field pair | — | — | — |
| FM-USART-04 | IsActiveFlag_ORE, ClearFlag_ORE | Overrun loses a received value | Reported only through the flag | Target overrun test on the model | AOU-USART-02 |
| FM-USART-05 | — | Parity, framing and noise error flags are out of scope | A corrupted frame is not reported by the in-scope functions | Scope statement | AOU-USART-03: an end-to-end protection (e.g. CRC) of the transported data |
| FM-USART-06 | TransmitData8, ReceiveData8 | 8-bit data only; 7/9-bit values out of scope | — | Scope statement | — |

### 6.4 GPIOA (`stm32n6xx_ll_gpio.h`, 15 functions)

| ID | Function(s) | Fault mode | Effect | Existing measure | Remaining |
|---|---|---|---|---|---|
| FM-GPIO-01 | SetPinMode, SetPinOutputType, SetPinSpeed, SetPinPull, SetAFPin_0_7/8_15 | Per-pin `MODIFY_REG` on a register shared by 16 pins (FM-C1) | A concurrent configuration of another pin of the port is lost — the pin may change function (e.g. an output becomes an input) | Tests check other pins are preserved (single context) | AOU-01 |
| FM-GPIO-02 | SetPinMode, SetPinSpeed, SetPinPull, SetAFPin_* | Take a single pin; a mask with several pins makes `POSITION_VAL` select the lowest pin only | Only one of the intended pins is configured | Scope: single representative pin per requirement | AOU-GPIO-01: one pin per call |
| FM-GPIO-03 | SetOutputPin, ResetOutputPin | Write-only GPIO_BSRR / GPIO_BRR: atomic per pin | — (no lost update) | ASR-08 by construction; tests | — |
| FM-GPIO-04 | TogglePin | Reads GPIO_ODR, then writes GPIO_BSRR: not atomic | A change of the same pin between read and write by another context is reverted | Deferred to tests (computed value) | AOU-01 for the toggled pins |
| FM-GPIO-05 | WriteOutputPort | Writes all 16 output bits | Pins owned by another function are overwritten | Scope statement | AOU-GPIO-02: port writes only when the caller owns all pins |
| FM-GPIO-06 | — | The configuration lock (GPIOx_LCKR) is out of scope | Errant software can reconfigure a safety-relevant pin | — | AOU-GPIO-03: lock or protect (MPU, RIF) safety-relevant pin configuration |
| FM-GPIO-07 | — | Reset state: most port A pins start in analog mode (GPIO_MODER reset 0xABFFEFFF, RM0486 15.4.1), a few in alternate function (debug); the driver writes nothing until called | Outputs are undefined until configured | Start-up requirement and tests | AOU-GPIO-04: safe state of outputs before configuration is the system's (external pull resistors) |

### 6.5 TIM2 (`stm32n6xx_ll_tim.h`, 22 functions)

| ID | Function(s) | Fault mode | Effect | Existing measure | Remaining |
|---|---|---|---|---|---|
| FM-TIM-01 | SetPrescaler, SetAutoReload | PSC is buffered and takes effect only at the next update event; ARR is buffered when ARPE = 1 | The time base keeps the old period until an update event | Requirements state the register write; the model implements the shadows | AOU-TIM-01: generate an update event (GenerateEvent_UPDATE, with URS if no flag is wanted) after changing the time base |
| FM-TIM-02 | SetCounterMode | DIR with CMS set by one value; DIR is read-only in centre-aligned modes | A caller-composed value selects an unintended mode | Requirements and tests follow the coupling | AOU-02 |
| FM-TIM-03 | ClearFlag_UPDATE | `WRITE_REG(SR, ~UIF)`: rc_w0 — clears only UIF, no read-modify-write race | — | Conformance accepts the idiom only when the requirement writes 0 to UIF | — |
| FM-TIM-04 | DisableUpdateEvent (UDIS), SetUpdateSource (URS) | Update events suppressed or UG not flagged | A timing monitor based on UIF never fires | Requirements and tests | AOU-TIM-02: a timing monitor checks that updates occur |
| FM-TIM-05 | SetCounter, GetCounter | 32-bit counter (TIM2); UIF remapping out of scope | — | Tests | — |
| FM-TIM-06 | — | The timer's clock (RCC enable, kernel clock) is outside this driver | A stopped or wrong clock stops or skews the time base without a report | — | AOU-TIM-03: clock monitoring at system level |

## 7. Dependent-failure analysis

| ID | Dependency | Effect | Measure / remaining |
|---|---|---|---|
| DF-01 | Requirements, register contract, conformance oracle, Renode models and tests all derive from the same converted RM0486 text | A conversion error or a misread register would be consistent everywhere and go undetected | TAA-FND-06/-10: review against the original PDF, tests on silicon |
| DF-02 | The five drivers share the CMSIS device headers delivered with them | A wrong macro affects all | ST's headers are fingerprinted and FROZEN; the RM is the independent reference for field positions |
| DF-03 | SPI, USART and TIM pins depend on GPIO alternate-function configuration (FM-GPIO-01) | A GPIO fault silences or misroutes a communication or timing output | System-level pin configuration check (AOU-GPIO-03) |
| DF-04 | All drivers depend on the RCC clock and reset configuration (outside these scopes; see SSA-RCC-001) | A clock fault affects every peripheral at once | System-level clock monitoring |
| DF-05 | One AI author family (Codex) wrote requirements, design and tests; one family (Claude) inspected them | Common misunderstanding of a register between author and inspector is possible | Different families for author and inspector; deterministic gates and the delivered code as an independent artefact; human review |

## 8. Assumptions of use (to be met by the integrating system)

| ID | Assumption |
|---|---|
| AOU-01 | Each peripheral register has one writer at a time, or the caller serialises all writers (interrupts, tasks, cores). |
| AOU-02 | The caller passes only the documented LL constants and a valid instance; composed values are not used. |
| AOU-03 | Configuration functions are called only while the peripheral is disabled where RM0486 requires it (SPI SPE = 0, USART UE = 0). |
| AOU-04 | Safety-relevant configuration is read back after it is written. |
| AOU-05 | Decisions on status flags tolerate one-poll latency. |
| AOU-06 | Every polling loop on a status flag is bounded by the caller with a defined reaction on timeout. |
| AOU-CRC-01..03 | Known-answer check of the CRC configuration at start-up; exclusive use of the unit per computation; 32-bit feeds (padding by the caller). |
| AOU-SPI-01..02 | 8-bit frames only through these functions; OVR checked and handled; data protected end to end where needed. |
| AOU-USART-01..03 | True kernel clock and valid arguments for the baud rate; ORE checked and handled; end-to-end protection of transported data. |
| AOU-GPIO-01..04 | One pin per configuration call; port writes only for owned ports; safety-relevant pin configuration locked or protected; safe output state before configuration provided by the hardware. |
| AOU-TIM-01..03 | Update event after time-base changes; a monitor that update events occur; clock monitoring at system level. |

## 9. Findings

| ID | Finding | Proposed measure |
|---|---|---|
| SSA-FND-01 | No allocated software safety requirement, HSI or allocation review exists (section 2). | The owner provides the upstream inputs, or accepts the assumed requirements (Q-01). |
| SSA-FND-02 | ST's LL does not validate arguments (FM-C2) and reports no error from the configuration functions (FM-C3, FM-USART-02). | Accept with AOU-02/AOU-04, or add a checking wrapper (outside the FROZEN code). |
| SSA-FND-03 | Read-modify-write on shared registers (FM-C1, FM-GPIO-01, FM-GPIO-04). | Accept with AOU-01. |
| SSA-FND-04 | SPI-R2 (`WO-AFO-0756ac55b8ea81e6-a1`) escalated three CODE defects (DEF-001/003/004) against `LL_SPI_ClearFlag_EOT/OVR`. Analysis: not a code defect — RM0486 p.156 states that reading a write-only bit returns its reset value, so `SET_BIT` writes exactly the flag on the device; the host test preset the write-only register with other bits. | Close as not a defect; the register conventions input and guidance (db6c68e) apply from SPI-R3 on (TAA-FND-09). |
| SSA-FND-05 | Verification runs only on the host and on behavioural models written from the RM text; no silicon (DF-01). | Tests on silicon or model validation. |
| SSA-FND-06 | The parameter naming of the delivered code differs from the factory guideline (GL-ARG-01), dispositioned by the owner as ACCEPTED_VENDOR_NAMING_STYLE (OD-2026-10-25-01). | — (recorded in every package). |

## 10. Evidence at drafting

| Driver | Work order | Phases | Package |
|---|---|---|---|
| CRC | WO-AFO-eca972eb13bc60d1-a1 (CRC-R3, commit 5e8b5bc) | SWE.1–SWE.6 passed; conformance CONFORMANT; 14/14 requirements verified by Robot on Renode | BLOCKED only on the two owner documents |
| SPI | WO-AFO-7a6810a8baf9b9c4-a1 (ed40ee4) | SWE.1–SWE.6 passed | BLOCKED (48 gaps, mainly false conformance findings fixed in 164f11f) |
| SPI | WO-AFO-0756ac55b8ea81e6-a1 (5e8b5bc) | SWE.1–SWE.3 passed, SWE.4 stopped (SSA-FND-04) | BLOCKED (26 gaps) |
| SPI, USART, GPIO, TIM | AFO orders BENCH-SPI-ST-R3, BENCH-USART-ST, BENCH-GPIO-ST, BENCH-TIM-ST | in progress or queued | — |

The USART, GPIO and TIM sections rest on the delivered code and RM0486, not yet on run evidence. The reviewer may
sign now and re-review when their runs complete (Q-04).

## 11. Open questions for the reviewer

| ID | Question |
|---|---|
| Q-01 | Do you accept ASR-01 to ASR-08 as the assumed safety requirements? |
| Q-02 | Do you accept the assumptions of use (section 8) as the integrator's obligations? |
| Q-03 | Should the findings stay open (listed in the package limitations), or be closed before use? |
| Q-04 | Do you sign the USART, GPIO and TIM sections before their first runs complete, or after? |
| Q-05 | Do you accept SSA-FND-04 (SPI-R2 defects are a host-test artifact, not a code defect)? |
| Q-06 | Is one analysis for the five scopes acceptable, or should each driver get its own document? |

## 12. Sources

Delivered headers (SHA-256 in each work order's `configuration/delivery.json`); RM0486 Rev 4 chapters 15, 26, 54, 65,
67, memory map pp.176–181, register conventions p.156 (inputs-manifest SHA-256); the work orders listed in section 10
(`workproducts/SWE.1-6`, `.forge-run/{manifest.json, gates/gate-log.jsonl, defects/, delivery/conformance.json}`);
`config/factory/peripherals/*.yaml`; SSA-RCC-001 v1.1 (method and DF-04); OD-2026-10-25-01, OD-2026-10-25-02.

## 13. Review and signature (v1.0)

| Field | Value |
|---|---|
| Reviewed by (name, role) | |
| Reviewer's statement | |
| Answers to Q-01 to Q-06 | |
| Changes made during review | |
| Decision | ☐ Approved ☐ Approved with open findings (listed in the package limitations) ☐ Rejected |
| Date | |

Signing records the reviewer's engineering judgement on this analysis for the stated basis. It is not a safety
approval of an item, a release decision or a certification.
