# Software Safety Analysis — STM32N6 RCC LL and HAL drivers (generated and delivered code)

| Field | Value |
|---|---|
| Document | SSA-RCC-001, version 1.1 |
| Status | **Approved with open findings** — signed by Jefferson Nascimento (owner), 2026-10-20 |
| Safety scope | SC-RCC-2026-10-18, target ASIL B (owner decision 2026-10-18) |
| Product | RCC LL driver (example `0002a-arm_55_rcc_ll`) and RCC HAL driver (example `0002b-arm_55_rcc_hal`); delivered RCC code (brownfield examples `0008a-rcc-ll-delivered`, `0008b-rcc-hal-delivered`, `0008c-st-cube-rcc`) |
| Basis | Work order inputs, source requirements hash `c62aa88ca3c53f3a58de023f1e6f164df97da8b053d5ddbcaa92cbd58121f7d4` |
| Analysed work products | LL `WO-0002A-STM32N6-RCC-LL-r168`, HAL `WO-0002B-STM32N6-RCC-HAL-r164` (SWE.1–SWE.6); brownfield `WO-0008A-STM32N6-RCC-LL-b001`, `WO-0008B-STM32N6-RCC-HAL-b004`, `WO-0008C-ST-RCC-LL-b005` (section 12) |
| Drafted by | Claude Opus 5.5 (Claude Code), v1.0 2026-10-19, v1.1 2026-10-20, from the factory records listed in sections 10 and 12 |
| Responsible engineer | Jefferson Nascimento (owner) |

> Signed version (owner decision OD-2026-10-20-05). It applies to RCC work orders (generated and delivered code) whose inputs match the basis
> above. Any edit to this file, or a change to the work order inputs, un-signs it until it is re-reviewed. It
> records the reviewer's engineering judgement; it is not a safety approval or certification.
> It supersedes version 1.0 (OD-2026-10-19-12, file `../software_safety_analysis.md`, kept unchanged for the record).

## Change log v1.0 → v1.1

| Change | Where |
|---|---|
| Scope extended to delivered (brownfield) RCC code: factory-generated deliveries 0008a (LL, FROZEN) and 0008b (HAL, FIX_ALLOWED), and ST STM32CubeN6 v1.4.0 LL code 0008c (FROZEN). Same inputs, same basis hash (verified 2026-10-20 for 0002a, 0002b, 0008a, 0008b, 0008c). | Header, section 12 |
| CAPA-051 finding: `swe3_hal_author` (HAL code) and `swe4_test_author` (unit tests) ran on DeepSeek in every run before CAPA-051; in HAL r164 the inspectors and the Release Manager also ran on DeepSeek (no `--acp-inspectors`). DF-05 corrected; DeepSeek suspended (OD-2026-10-20-03). | DF-05, SSA-FND-06 |
| FM-01 and Q-04: RM0486 provides set/clear registers (RCC_CSR/RCC_CCR, RCC_AHB1ENSR/RCC_AHB1ENCR, RCC_AHB1RSTSR) and the ST code uses them; information for Q-04, not an answer. | FM-01, Q-04 |
| New fault modes and findings for delivered code (FM-18 to FM-22, SSA-FND-06 to SSA-FND-08), new questions Q-08 to Q-10. | Sections 5, 8, 9, 12 |
| Section 11 left blank for the v1.1 signature; the v1.0 signature record is kept in the v1.0 file. | Section 11 |

## 1. Purpose and scope

This document analyses how the RCC driver software can fail, what the effect of each failure is at the driver
boundary, which measures in the design and verification already address it, and what is still open. It is written
once for the product and applies to every RCC work order whose inputs match the basis hash above. A change to the
work order inputs (scope, reference documents, upstream inputs) invalidates it until it is re-reviewed.

**In scope** (the functions the work orders actually implement):

- LL: HSI and HSE oscillator enable, disable and ready query; GPDMA1 and ADC12 clock enable, disable and query;
  GPDMA1 and ADC12 reset assert and release. 16 header-only `static inline` functions on the register block
  `ll_rcc_regs`.
- HAL: 10 functions returning `hal_status_t` (HAL_OK, HAL_ERROR, HAL_TIMEOUT) built only on the LL: oscillator
  enable with a bounded ready wait, oscillator disable, peripheral clock enable/disable, peripheral reset.

**Out of scope** (not implemented, so not analysed): PLLs, clock-tree switching and system clock selection,
security and privilege configuration, interrupts, low-power modes, peripherals other than GPDMA1 and ADC12, and the
clock security system.

## 2. Safety context — element developed out of context

No item definition, safety goal, technical safety requirement, hardware-software interface (HSI) or software
safety requirement has been provided for the RCC driver. `upstream/upstream-inputs.yaml` is still an unfilled
template for both examples, and `safety/software_safety_requirements.md` in both work orders states that no
software safety requirement is allocated yet. There is therefore no system context from which to derive the
safety relevance of an RCC failure, no fault tolerant time interval and no defined safe state.

This analysis treats the driver as a **component developed without a known system context**: it states the
safety requirements it **assumes** the driver must meet (section 3) and the conditions the integrating system must
guarantee (section 7). An integrator must check both against the real system; where they do not hold, this
analysis does not apply.

## 3. Assumed safety requirements

These requirements are **assumptions made by the drafter**. They must be accepted, changed or rejected by the
reviewer (question Q-01). The right column shows which development requirements (SWR, regenerated by each work
order; ids from r168/r164) currently implement each one.

| ID | Assumed safety requirement | Implemented today by |
|---|---|---|
| ASR-01 | The driver shall change only the RCC bit addressed by a request; every other RCC bit and register keeps its value. | LL SWR-017 (masked read-modify-write); HAL SWR-015 (register access only through the LL) |
| ASR-02 | The driver shall not write any RCC register except on an explicit caller request (no writes at startup or on its own). | LL SWR-018; HAL SWR-010, SWR-011 |
| ASR-03 | Every driver call shall return within a bounded number of CPU instructions. | LL: no loops; HAL SWR-009 (≤ timeout ≤ 1000 polling iterations) |
| ASR-04 | The HAL shall reject an invalid request (NULL configuration, unknown selector, timeout out of range) without writing any register, and report HAL_ERROR. | HAL SWR-008 |
| ASR-05 | When an oscillator does not become ready within the caller's budget, the HAL shall report HAL_TIMEOUT and leave the oscillator in a defined state. | HAL SWR-007 (enable bit cleared) |
| ASR-06 | The HAL shall not report success for a clock or reset request that did not take effect. | HAL SWR-001, SWR-002 for oscillators only (ready flag); **not met** for peripheral clocks and resets (finding SSA-FND-01) |
| ASR-07 | The driver shall use no memory other than the RCC register block and its own stack. | LL SWR-020 (0 B static RAM); HAL SWR-013 (≤ 64 B; measured 0 B) |

## 4. Method

1. **Fault-mode analysis per unit and interface** (section 5). For each LL and HAL function and for the two
   interfaces (caller → driver, driver → register block), the guide words *omission*, *commission*,
   *wrong value / wrong bit*, *too early / too late*, *stuck*, and *corruption by another writer* were applied. For
   each fault mode the table records the cause, the effect at the driver boundary, the assumed requirement it
   would violate, the existing measure and its verification, and what remains open.
2. **Dependent-failure analysis** (section 6): shared resources (RCC registers, memory, CPU time) and common causes
   in development and verification (same source document, same AI model family, simulator instead of silicon).
3. **Evidence used**: the work products and tool records of LL r168 and HAL r164 (section 10). No hardware or HIL
   evidence exists; all target evidence comes from the Renode behavioural model and is marked
   `silicon_verified: false`.

## 5. Fault-mode analysis

Legend: **Measure** = what the design already does; **V** = how it is verified; **Open** = remaining gap, finding
or assumption of use.

| ID | Element | Fault mode | Cause | Effect at driver boundary | ASR | Measure / V | Open |
|---|---|---|---|---|---|---|---|
| FM-01 | LL mutators (all `_Enable`, `_Disable`, `_ForceReset`, `_ReleaseReset`) | Lost update: another bit of the same register is overwritten | Pre-emption or a second core/master writes the register between the driver's read and write | An unrelated clock or reset changes state | ASR-01 | Factory LL (0002a, 0008a): masked read-modify-write; V: unit UT-017, Renode preservation scenario. ST LL (0008c): writes the set/clear registers, so no read-modify-write race | Factory LL only safe if callers serialise every writer of the register (AOU-01). v1.1: RM0486 does provide RCC_CSR/RCC_CCR, RCC_AHB1ENSR/RCC_AHB1ENCR and RCC_AHB1RSTSR (sections 14.10.128, 14.10.185, 14.10.147, 14.10.204, 14.10.132); the v1.0 statement that they were not in the supplied inputs was wrong (Q-04). |
| FM-02 | LL mutators | Write has no effect | Access rights or security filtering ignore the write; bus error | Clock or reset not applied; LL reports nothing | ASR-06 | None in the LL (void functions) | Caller must verify or use the HAL (AOU-04). |
| FM-03 | HAL peripheral clock enable/disable, HAL reset | Success reported for a request that had no effect | Same as FM-02 | HAL_OK returned, peripheral clock or reset not applied | ASR-06 | None: no read-back | **SSA-FND-01**: add read-back through `LL_RCC_*_IsEnabled` and return HAL_ERROR on mismatch. |
| FM-04 | `HAL_RCC_HSI_Enable`, `HAL_RCC_HSE_Enable` | Oscillator never becomes ready | Oscillator or crystal fault, wrong board configuration | HAL_TIMEOUT after the budget; the enable bit is cleared | ASR-05 | Bounded do-while poll and rollback; V: Renode `never_ready` image (LL 14, HAL 27 checks), unit tests | See FM-05 and FM-06. |
| FM-05 | HAL oscillator enable rollback | Rollback switches off an oscillator that was already running | The rollback clears the enable bit even if it was set on entry (HSI is on after reset) | A running HSI (possibly a clock source for the CPU or peripherals) is switched off after a failed or too-short wait | ASR-05 | None | **SSA-FND-02**: roll back only if the bit was clear on entry. Check in RM0486 whether the hardware keeps an oscillator on while it is the system clock source (Q-03). |
| FM-06 | HAL oscillator enable | False timeout | Caller budget shorter than the real start-up time; the budget counts polling iterations, not time, so it depends on CPU frequency and bus wait states | HAL_TIMEOUT and oscillator switched off although healthy | ASR-05 (availability) | Range check 1–1000 (SWR-008) | Caller derives the budget from the start-up time in DS14791 and its own CPU clock (AOU-05). No time-based or cycle-measured bound exists (**SSA-FND-04**). |
| FM-07 | HAL oscillator enable | False ready | Ready flag read as 1 while the oscillator is not stable (hardware fault, stuck bit) | HAL_OK with an unstable clock | ASR-06 | None in software; one read per iteration | Clock monitoring belongs to the system (clock security system, external watchdog): AOU-06. |
| FM-08 | LL register definitions (offsets, masks) | Wrong register or bit addressed | Error in the RM0486 conversion or in the generated header | Another clock or reset is changed; the intended one is not | ASR-01, ASR-06 | `inspection.regmap` generates and checks every register cell against the RM0486 section files; independent register contract and oracle; Renode model; SWE.3 inspector | Common cause: model, contract and code all derive from the same converted RM0486 text (DF-04). LL mutation run r168: 3 survivors (LSEON/LSION masks, SR offset), observe-only. |
| FM-09 | Register block placement `ll_rcc_regs` | Driver accesses the wrong memory | Linker places the array somewhere other than the RCC base 0x56028000 | Writes corrupt RAM or another peripheral; reads return garbage | ASR-01, ASR-07 | Placement is an integration assumption; target images use the factory linker script | **SSA-FND-03**: add a link-time check of the symbol address in the target build. AOU-02. |
| FM-10 | Register block placement | All RCC registers written at startup | Array placed in a zero-initialised section | Every clock and reset cleared before `main` | ASR-02 | Integration assumption (non-initialised section) | Covered by SSA-FND-03; AOU-02. |
| FM-11 | `HAL_RCC_*_Reset` | Reset pulse too short | Assert followed immediately by release, with no delay | Peripheral not fully reset | ASR-06 | None | Check in RM0486 whether a minimum reset duration applies (Q-05). |
| FM-12 | Clock disable, reset | Applied while the peripheral is in use | Caller sequencing error (DMA transfer or ADC conversion running) | Lost or corrupted transfer, bus stall | — (consumer) | None in the driver | AOU-03. |
| FM-13 | All HAL functions | Status not checked | Caller ignores the return value | Failure goes unnoticed | ASR-05, ASR-06 | `hal_status_t` return | AOU-04; a static check for unused return values in the integrating code is recommended. |
| FM-14 | HAL oscillator enable | Two contexts operate on the same oscillator | Concurrent enable/wait/rollback transactions | One context's rollback switches off the oscillator the other relies on | ASR-05 | None | AOU-01 (serialise the whole transaction). |
| FM-15 | All functions | Stack overflow | Deeper call chain than measured | Memory corruption | ASR-07 | Per-function frames measured: LL 0 B, HAL max 8 B (`-fstack-usage`) | Worst-case call-graph stack not computed (**SSA-FND-05**). |
| FM-16 | HAL oscillator enable | Excessive execution time | 1000 iterations at a slow clock | Caller deadline missed | ASR-03 | Iteration bound verified by unit and Renode tests | No cycle measurement on target (SSA-FND-04). |
| FM-17 | HAL invalid input | Invalid input not rejected | Missing check | Wrong register write | ASR-04 | Checks run before any LL call; V: unit tests with 100 % MC/DC (HAL r164), negative cases | The EASA gate did not accept the SWE.4 negative-boundary evidence (observe-only); reviewer to decide whether it is sufficient (Q-06). |

## 6. Dependent-failure analysis

| ID | Shared resource or common cause | Analysis | Conclusion |
|---|---|---|---|
| DF-01 | RCC registers shared with other software (other drivers, RTOS, boot code, other cores or bus masters) | The driver uses non-atomic read-modify-write and has no locking. | Freedom from interference against other RCC writers **cannot be claimed by the driver**; it relies on AOU-01. |
| DF-02 | Memory | No static RAM, no heap; only the register block and the stack. | No interference with other software's memory if AOU-02 holds and the stack bound holds (FM-15). |
| DF-03 | CPU time | Only the HAL ready wait loops, bounded by the caller's budget ≤ 1000 iterations. No interrupts are used. | Bounded, subject to SSA-FND-04. |
| DF-04 | Single source document | The requirements, the register header, the Renode RCC model, the register contract and the test oracle all derive from the same converted RM0486 chapter 14. An error in the source or its conversion would be consistent everywhere and not detected by the factory's tests. | Residual common cause. Mitigation: an independent review of the register cells against the original RM0486 PDF, and a test on silicon (Q-07). |
| DF-05 | AI development and verification | Intended: authors on Codex Sol 6.1, inspectors on Claude Opus 5.5. **Actual before CAPA-051 (v1.1 correction):** `swe4_test_author` ran on DeepSeek in every run, and `swe3_hal_author` — the author of the HAL code — ran on DeepSeek in every LL+HAL run; in HAL r164 the inspectors and the Release Manager also ran on DeepSeek (that run had no Claude inspectors). The HAL r164 code (and the 0008b delivery derived from it) was therefore authored and inspected by the same model family. Since CAPA-051 (factory a76e957) every agent node runs on Codex or Claude and DeepSeek is refused (OD-2026-10-20-03). Deterministic gates do not depend on any model; the EASA gate flags AI inspection PASS as not independent evidence for SWE.1–SWE.4. | Model diversity was **not** present for the HAL r164 code. Human review of the HAL code is required before relying on it (SSA-FND-06). See TAA-RCC-001 v1.1. |
| DF-06 | Simulator instead of hardware | All target tests run on the Renode behavioural model: no clock timing, bus faults, security filtering, errata or concurrency. | Target behaviour is not verified on silicon (Q-07). |

## 7. Assumptions of use (to be met by the integrating system)

| ID | Assumption |
|---|---|
| AOU-01 | All writers of an RCC register (tasks, interrupts, other cores, other bus masters) are serialised for the whole register, and HAL oscillator transactions (enable, wait, rollback) are serialised per oscillator. Interrupt masking alone is not enough on multi-master systems. |
| AOU-02 | `ll_rcc_regs` is linked at the RCC base 0x56028000 in a section that is not initialised at startup. |
| AOU-03 | A peripheral is quiescent before its clock is disabled or its reset is asserted; the caller owns the clock-consumer sequencing. |
| AOU-04 | The caller checks every `hal_status_t` result and has its own reaction to HAL_ERROR and HAL_TIMEOUT. Callers of the LL directly verify the result themselves and bound their own polling. |
| AOU-05 | The caller sets the oscillator ready budget from the start-up time in DS14791 and its own CPU clock, with margin. |
| AOU-06 | Clock monitoring (clock security system, watchdog or equivalent) and the safe state on a clock failure are provided by the system, not by this driver. |
| AOU-07 | The caller holds the access and privilege rights the RCC registers require (RM0486 pp. 480, 482, 548, 575). |
| AOU-08 | The silicon revision used is checked against the errata, since the work orders do not specify one. |

## 8. Findings and proposed measures

| ID | Finding | Proposed measure | Priority (reviewer to confirm) |
|---|---|---|---|
| SSA-FND-01 | HAL reports HAL_OK for peripheral clock and reset requests without checking that they took effect (FM-03). | Read back through `LL_RCC_*_IsEnabled` after enable/disable and return HAL_ERROR on mismatch; add a requirement and tests. | High |
| SSA-FND-02 | A failed HAL oscillator enable switches off an oscillator that was already running (FM-05). | Roll back only when the enable bit was clear on entry; add a requirement and a Renode scenario. | High |
| SSA-FND-03 | Nothing checks that `ll_rcc_regs` is at the RCC base and not zero-initialised (FM-09, FM-10). | Link-time or map-file check in the SWE.5 target build. | Medium |
| SSA-FND-04 | The wait bound is in polling iterations, with no measured execution time on the target (FM-06, FM-16). | Measure cycles per iteration on the target, and state the budget in time units in the API documentation. | Medium |
| SSA-FND-05 | Worst-case stack is not computed over the call graph (FM-15). | Compute the call-graph worst case in SWE.5. | Low |
| SSA-FND-06 | (v1.1) The HAL r164 code, also delivered as 0008b, was written and inspected on DeepSeek (DF-05, CAPA-051). | Human review of the HAL code, or regenerate it on a factory revision with CAPA-051 and re-run. | High |
| SSA-FND-07 | (v1.1) ST's `LL_AHB1_GRP1_*` functions take a peripheral bit mask and write it to the set/clear register without checking it (FM-19). | Caller obligation (AOU-09), or a wrapper that admits only the scoped GPDMA1/ADC12 bits. | Medium |
| SSA-FND-08 | (v1.1) The ST pilot (b005) is blocked at SWE.3 by checklist items written for factory-style code; no SWE.4–SWE.6 evidence exists for the ST code yet (section 12). | Brownfield checklist v0.4-brownfield (owner decision OD-2026-10-20-02) and a new run. | Medium |

Implementing SSA-FND-01 to SSA-FND-04 changes the work order scope or the factory, which changes the basis of this
analysis; it is then re-reviewed.

## 9. Open questions for the reviewer

| ID | Question |
|---|---|
| Q-01 | Do you accept ASR-01 to ASR-07 as the assumed safety requirements, or should they be changed? |
| Q-02 | Should the findings in section 8 be fixed before signing, or accepted as open items listed in the package limitations? |
| Q-03 | Does RM0486 keep an oscillator enabled while it is the system clock source (affects FM-05)? |
| Q-04 | Should the LL use the RCC set/clear registers (if RM0486 provides them for these bits) instead of read-modify-write (FM-01)? |
| Q-05 | Does RM0486 require a minimum reset assertion time for GPDMA1 or ADC12 (FM-11)? |
| Q-06 | Is the SWE.4 negative and boundary test evidence sufficient for ASR-04, given that the EASA gate did not accept it (observe-only)? |
| Q-07 | When will the register header be reviewed against the original RM0486 PDF, and when will tests run on silicon (DF-04, DF-06)? |
| Q-08 | (v1.1) Do you accept that one analysis covers both the generated and the delivered RCC code for the same inputs, or should the ST code (0008c) get its own analysis? |
| Q-09 | (v1.1) Is FROZEN-mode evidence (findings recorded as package gaps, code not changed) acceptable for ASIL B use of the ST code, or must every finding be fixed in a FIX_ALLOWED work order first? |
| Q-10 | (v1.1) How is the HAL r164 / 0008b code reviewed, given that it was authored and inspected on DeepSeek (SSA-FND-06)? |

## 10. Sources

- Work order scopes: `examples/0002a-arm_55_rcc_ll/workorder.json`, `examples/0002b-arm_55_rcc_hal/workorder.json`.
- Safety scope: `config/factory/safety-scope.yaml` (SC-RCC-2026-10-18).
- LL r168 and HAL r164 workspaces: `workproducts/SWE.1`–`SWE.6`, `safety/software_safety_requirements.md`,
  `software/ll/stm32n6xx_ll_rcc.h`, `software/hal/stm32n6xx_hal_rcc.{c,h}`, `traceability/upstream_gaps.md`,
  `evidence/tool-results.jsonl`, `.forge-run/gates/gate-log.jsonl`, `.forge-run/assurance/gate-log.jsonl`,
  `.forge-run/owner_dispositions.json` (OD-2026-10-18-01).
- The HAL r164 work order uses the LL header from LL r125; it differs from LL r168 only in comments, indentation
  and function order (register expressions identical).

## 11. Review and signature (v1.1)

| Field | Value |
|---|---|
| Reviewed by (name, role) | Jefferson Nascimento, owner and responsible engineer |
| Reviewer's statement | "I approve all" (2026-10-20), in reply to "Sign the drafts in PR #16 when you're satisfied with them" |
| Answers to Q-01 to Q-10 | Q-01: ASR-01 to ASR-07 accepted (v1.0). Q-02: the findings stay open and are listed with the package. Q-08: one analysis for the generated and the delivered RCC code accepted as drafted. Q-03 to Q-07, Q-09 and Q-10: not answered at signing; they remain open. |
| Changes made during review | None to the analysis; status, version and this section completed on signing |
| Decision | ☐ Approved ☒ Approved with open findings (listed in the package limitations) ☐ Rejected |
| Date | 2026-10-20 |

Signing records the reviewer's engineering judgement on this analysis for the stated basis. It is not a safety
approval of an item, a release decision or a certification.

## 12. Delivered (brownfield) RCC code — added in v1.1

### 12.1 What is delivered

| Example | Code mode | Delivered code | Origin and licence | Run analysed |
|---|---|---|---|---|
| `0008a-rcc-ll-delivered` | FROZEN | `software/ll/stm32n6xx_ll_rcc.h`, `software/src/stm32n6xx_ll_rcc.c` | Factory-generated, greenfield LL r170 (2026-10-20); Apache-2.0 | b001: SWE.1–SWE.6 PASS, conformance 0 findings; official package affected by a finalizer defect (fixed), scratch re-finalize: 2 gaps (these documents) |
| `0008b-rcc-hal-delivered` | FIX_ALLOWED | `software/hal/stm32n6xx_hal_rcc.{c,h}` | Factory-generated, greenfield HAL r164 (2026-10-19) with a seeded defect (removed `LL_RCC_HSE_Disable()`, `delivery/SEEDED_DEFECT.md`); Apache-2.0 | b004: SWE.1–SWE.6 PASS; the seeded defect found by the SWE.2 author, fixed in SWE.3 with a one-line change byte-identical to r164, verified in SWE.4 |
| `0008c-st-cube-rcc` | FROZEN | ST `Inc/stm32n6xx_ll_rcc.h`, `Inc/stm32n6xx_ll_bus.h`; 11 scope functions (HSI/HSE enable/disable/ready, AHB1 clock enable/disable/query, reset assert/release); CMSIS device and core headers as dependencies | STMicroelectronics stm32n6xx-hal-driver v1.4.0, BSD-3-Clause, from ST's official GitHub tag v1.4.0 (archive SHA-256 `4b5330ed387814fff531dda0ef52ba1a4b86875f3e780e43d2fe91a347ff02bc`, `$FORGE_DATA_ROOT/inputs/st/stm32n6xx-hal-driver-v1.4.0/provenance.json`); CMSIS device v1.4.0 and CMSIS core from STM32CubeN6 v1.4.0, Apache-2.0 | b005: SWE.1 PASS, SWE.2 PASS (architecture recovered from the code), SWE.3 BLOCKED by SWE3-07/08/09 (checklist items for factory-style code); conformance CONFORMANT (0 findings) after a parser fix |

### 12.2 How the brownfield workflow treats delivered code

- **Requirements first, independent of the code.** SWE.1 derives the requirements from RM0486 and the owner scope;
  SWE.1 roles cannot read the delivered files. The code is injected only after the SWE.1 inspection passes.
- **Fingerprints.** Every delivered file is stored read-only outside the workspace with its SHA-256 and re-verified
  at SWE.3 entry, at SWE.3 verify and at packaging.
- **FROZEN:** no write to a delivered file is possible; a disagreement with the requirements becomes a finding (a
  package gap for the owner), never a silent change.
- **FIX_ALLOWED:** a write window opens only while a CODE defect is IN_FIX, only inside scope functions, with no new
  code files; every change is diffed against the original and listed in the change report with its defect.
- **Conformance:** NO_CODE, NO_REQUIREMENT and CONTRADICTION findings from the register effects of the requirements,
  the architecture's API calls and the register effects extracted from the code (set/clear aliases mapped).
- **Trace:** a trace map replaces the factory's code tags (delivered code is not annotated).

### 12.3 Additional fault modes for delivered code

| ID | Element | Fault mode | Cause | Effect | ASR | Measure / V | Open |
|---|---|---|---|---|---|---|---|
| FM-18 | Delivered code (all) | Code differs from what was reviewed | File replaced or edited after intake | Unreviewed code in the package | ASR-01–ASR-07 | SHA-256 fingerprints re-verified three times; FROZEN refuses writes | None for the factory; the integrator must use the packaged files. |
| FM-19 | ST `LL_AHB1_GRP1_EnableClock`, `_DisableClock`, `_ForceReset`, `_ReleaseReset` | Wrong peripheral clocked or reset | The functions take a bit mask and write any bits given | Another peripheral's clock or reset changes | ASR-01 | Set/clear registers affect only the given bits | **SSA-FND-07**, AOU-09. |
| FM-20 | ST LL clock enable | Dummy read-back after enable | ST reads `RCC->AHB1ENR` after the set ("Delay after an RCC peripheral clock enabling") | None expected; whether the read has any side effect is NOT_VERIFIED (not checked against RM0486, not tested) | — | — | None. |
| FM-21 | Conformance and scope extraction | False CONFORMANT | The C index or register-effect extraction misses a write (macros, aliases) | A contradiction between code and requirement goes unreported | ASR-01, ASR-06 | Requirement-based tests SWE.4–SWE.6 on the delivered code, inspectors; two parser defects found and fixed in b002/b005 | No SWE.4–SWE.6 evidence yet for the ST code (SSA-FND-08). |
| FM-22 | FIX_ALLOWED correction | Fix introduces a new error | AI-authored change | New fault in a previously reviewed function | ASR-01–ASR-07 | One defect per change, inspection, re-run of SWE.4–SWE.6 tests, change report against the original | Human review of every change listed in the change report (AOU-10). |

### 12.4 Additional assumptions of use

| ID | Assumption |
|---|---|
| AOU-09 | Callers of ST's `LL_AHB1_GRP1_*` functions pass only the peripheral bits they own (here GPDMA1 and ADC12). |
| AOU-10 | Every FIX_ALLOWED change in the package change report is reviewed by a human before the code is used. |
| AOU-11 | ST's CMSIS device header is used in the version delivered (v1.4.0) and compiled for the secure Cortex-M55 configuration the build check used (`-mcpu=cortex-m55 -mthumb -mcmse`). |

### 12.5 Sources (v1.1)

`examples/0008a-rcc-ll-delivered/`, `examples/0008b-rcc-hal-delivered/`, `examples/0008c-st-cube-rcc/` (work orders
with the `delivery` block); `evidence/v0.4/runs/BF-T030/`, `BF-T031/`, `BF-T036/`, `BF-T039/`;
`docs/BROWNFIELD-WORK-ORDERS.md`; `$FORGE_DATA_ROOT/inputs/st/*/provenance.json`; model profiles of r164, r168,
r170, b001, b004, b005 (`.forge-run/model-profile.json`: `swe3_hal_author` and `swe4_test_author` absent from the
ACP node lists; r164 has no ACP inspectors); `evidence/cre/capa/i003-capas.json` (CAPA-051);
`evidence/easa/owner-decisions/OD-2026-10-20-03-deepseek-suspended.json`.
